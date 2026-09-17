from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import re
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.experiments.repositories import experiment_repository
from app.evaluation.experiments.repositories import experiment_result_repository as result_repository
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.calculators.result_calculator import calculate_run_metrics
from app.evaluation.metrics.registry.registry import get_metric_definition
from app.memory_systems.common.models.memory import CanonicalMemorySource, MemorySystemInstance


def refresh_experiment_metrics(db: Session, experiment_id: UUID) -> int:
    system_runs = experiment_repository.list_system_runs(db, experiment_id)

    if not system_runs:
        return 0

    turn_rows = result_repository.list_turns_with_questions(db, experiment_id)
    outputs_by_turn = {output.turn_id: output for output in result_repository.list_outputs(db, experiment_id)}
    claims_by_output = group_by_output_id(result_repository.list_claims(db, experiment_id))
    truth_by_question = {truth.question_id: truth for truth in result_repository.list_ground_truth(db, experiment_id)}
    retrieval_items_by_turn = group_pairs(result_repository.list_retrieval_items(db, experiment_id))
    llm_calls_by_turn = {turn_id: llm_call for turn_id, llm_call in result_repository.list_llm_calls(db, experiment_id)}
    turns_by_run = defaultdict(list)

    for turn, question in turn_rows:
        turns_by_run[turn.system_run_id].append((turn, question))

    updated_count = 0

    for system_run in system_runs:
        contexts = build_run_contexts(
            db,
            turns_by_run[system_run.id],
            system_run=system_run,
            outputs_by_turn=outputs_by_turn,
            claims_by_output=claims_by_output,
            truth_by_question=truth_by_question,
            retrieval_items_by_turn=retrieval_items_by_turn,
            llm_calls_by_turn=llm_calls_by_turn,
        )

        if not contexts:
            continue

        for metric_name, calculation in calculate_run_metrics(contexts).items():
            definition = get_metric_definition(metric_name)
            result = result_repository.get_metric_result(
                db,
                experiment_id=system_run.experiment_id,
                system_run_id=system_run.id,
                metric_name=metric_name,
            )

            if result is None:
                continue

            result_repository.save_metric_result(
                db,
                result,
                {
                    "metric_version": definition.version,
                    "value": calculation.value,
                    "numerator": calculation.numerator,
                    "denominator": calculation.denominator,
                    "applicable": calculation.applicable,
                    "reason_not_applicable": calculation.reason_not_applicable,
                    "details": {
                        **calculation.details,
                        "status": "measured" if calculation.value is not None else "not_applicable",
                        "system_type": system_run.system_type,
                        "case_id": str(system_run.case_id),
                        "repetition_number": system_run.repetition_number,
                    },
                },
            )
            updated_count += 1

    if updated_count:
        db.commit()

    return updated_count


def build_run_contexts(
    db: Session,
    turn_rows,
    *,
    system_run,
    outputs_by_turn: dict,
    claims_by_output: dict,
    truth_by_question: dict,
    retrieval_items_by_turn: dict,
    llm_calls_by_turn: dict,
) -> list[EvaluationTurnContext]:
    contexts = []
    source_id_map = build_fixture_source_id_map(db, system_run=system_run)

    for turn, question in turn_rows:
        output = outputs_by_turn.get(turn.id)

        if output is None:
            continue

        contexts.append(
            EvaluationTurnContext(
                turn=turn,
                question=question,
                ground_truth=resolve_ground_truth_sources(
                    truth_by_question.get(question.id),
                    source_id_map,
                ),
                output=output,
                claims=claims_by_output.get(output.id, []),
                retrieval_items=retrieval_items_by_turn.get(turn.id, []),
                llm_call=llm_calls_by_turn.get(turn.id),
            )
        )

    return contexts


def build_fixture_source_id_map(db: Session, *, system_run) -> dict[str, str]:
    if system_run.system_instance_id is None:
        return {}

    instance = db.scalar(
        select(MemorySystemInstance).where(MemorySystemInstance.id == system_run.system_instance_id)
    )

    if instance is None:
        return {}

    filters = [
        CanonicalMemorySource.patient_id == instance.patient_id,
        CanonicalMemorySource.is_active.is_(True),
    ]

    if system_run.source_cutoff is not None:
        filters.append(CanonicalMemorySource.recorded_time <= system_run.source_cutoff)

    sources = list(db.scalars(select(CanonicalMemorySource).where(*filters)).all())
    mapping = {}

    for source in sources:
        payload = source.structured_payload or {}
        candidates = [
            payload.get("source_reference"),
            payload.get("source_fixture"),
            payload.get("evaluation_source_id"),
            payload.get("package_source_id"),
            source.source_record_id,
        ]
        candidates.extend(extract_evaluation_source_ids(source.content_text))

        for payload_value in payload.values():
            if isinstance(payload_value, str):
                candidates.extend(extract_evaluation_source_ids(payload_value))

        if isinstance(payload.get("document"), dict):
            for payload_value in payload["document"].values():
                if isinstance(payload_value, str):
                    candidates.extend(extract_evaluation_source_ids(payload_value))

        for candidate in candidates:
            if not candidate:
                continue

            value = str(candidate)
            mapping[value] = str(source.id)

            if ":" in value:
                mapping[value.rsplit(":", 1)[-1]] = str(source.id)

    return mapping


def resolve_ground_truth_sources(ground_truth, source_id_map: dict[str, str]):
    if ground_truth is None or not source_id_map:
        return ground_truth

    truth = deepcopy(ground_truth.truth or {})
    resolve_source_lists(truth, source_id_map)
    return SimpleNamespace(
        id=ground_truth.id,
        question_id=ground_truth.question_id,
        truth=truth,
        version=ground_truth.version,
        reviewer_status=ground_truth.reviewer_status,
        created_at=ground_truth.created_at,
    )


def resolve_source_lists(value, source_id_map: dict[str, str]) -> None:
    source_fields = {
        "relevant_source_ids",
        "expected_citations",
        "required_citation_ids",
        "supporting_source_ids",
    }

    if isinstance(value, dict):
        for key, item in list(value.items()):
            if key in source_fields and isinstance(item, list):
                value[key] = [
                    resolved
                    for source_id in item
                    for resolved in resolve_source_id_value(str(source_id), source_id_map)
                ]
            else:
                resolve_source_lists(item, source_id_map)
    elif isinstance(value, list):
        for item in value:
            resolve_source_lists(item, source_id_map)


def resolve_source_id_value(source_id: str, source_id_map: dict[str, str]) -> list[str]:
    resolved = source_id_map.get(source_id)

    if resolved is None:
        return [source_id]

    if isinstance(resolved, list):
        return [str(item) for item in resolved]

    return [str(resolved)]


def extract_evaluation_source_ids(value: str) -> list[str]:
    return re.findall(r"\b(?:DOC|CHAT|EV|P[123]-(?:COND|MED|ALL|MEAS|NOTE|ENC))-[A-Z0-9-]+\b", value or "")


def group_by_output_id(claims: list) -> dict:
    grouped = defaultdict(list)

    for claim in claims:
        grouped[claim.output_id].append(claim)

    return grouped


def group_pairs(rows: list[tuple]) -> dict:
    grouped = defaultdict(list)

    for key, value in rows:
        grouped[key].append(value)

    return grouped
