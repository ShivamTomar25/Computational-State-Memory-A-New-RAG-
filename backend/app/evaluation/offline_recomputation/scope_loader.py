from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkEvent, BenchmarkQuestion
from app.evaluation.experiments.models.experiment import (
    Experiment,
    ExperimentClaim,
    ExperimentOutput,
    ExperimentSystemRun,
    ExperimentTurn,
)
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.llm.common.models.llm import LlmCall
from app.memory_systems.common.models.memory import CanonicalMemorySource, MemoryRetrievalItem, MemoryRetrievalRun, MemorySystemInstance
from app.memory_systems.csm.models import (
    CsmActivationItem,
    CsmActivationRun,
    CsmConflict,
    CsmStateDependency,
    CsmEvidence,
    CsmReviewRequest,
    CsmStateEvidenceLink,
    CsmStateHistory,
    CsmStateVariable,
)


SYSTEMS = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm"]
ALL_SYSTEMS = [*SYSTEMS, "csm_v3", "csm_v4"]
CSM_SYSTEMS = {"csm", "csm_v3", "csm_v4"}


@dataclass(frozen=True)
class OfflineTurn:
    patient: str
    experiment: Experiment
    system_run: ExperimentSystemRun
    turn: ExperimentTurn
    question: BenchmarkQuestion
    ground_truth: BenchmarkGroundTruth | None
    output: ExperimentOutput
    claims: list[ExperimentClaim]
    retrieval_items: list[MemoryRetrievalItem]
    retrieval_run: MemoryRetrievalRun | None
    llm_call: LlmCall | None


@dataclass(frozen=True)
class CsmBundle:
    states: list[CsmStateVariable]
    history: list[CsmStateHistory]
    evidence: list[CsmEvidence]
    links: list[CsmStateEvidenceLink]
    dependencies: list[CsmStateDependency]
    conflicts: list[CsmConflict]
    reviews: list[CsmReviewRequest]
    activation_runs: list[CsmActivationRun]
    activation_items: list[CsmActivationItem]


@dataclass(frozen=True)
class OfflineScope:
    experiment_id: UUID
    patient: str
    repetition: int
    turns: list[OfflineTurn]
    canonical_sources: dict[str, CanonicalMemorySource]
    source_aliases: dict[str, set[str]]
    events: list[BenchmarkEvent]
    csm: CsmBundle


def load_scope(db: Session, *, experiment_id: UUID, patient: str, repetition: int) -> OfflineScope:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment not found: {experiment_id}")

    run_rows = list(
        db.execute(
            select(ExperimentSystemRun, BenchmarkCase)
            .join(BenchmarkCase, ExperimentSystemRun.case_id == BenchmarkCase.id)
            .where(
                ExperimentSystemRun.experiment_id == experiment_id,
                ExperimentSystemRun.repetition_number == repetition,
                BenchmarkCase.case_key == patient,
                ExperimentSystemRun.system_type.in_(ALL_SYSTEMS),
            )
        ).all()
    )
    runs = [row[0] for row in run_rows]
    case_ids = {row[1].id for row in run_rows}
    run_by_id = {run.id: run for run in runs}
    if not run_by_id:
        return OfflineScope(experiment_id, patient, repetition, [], {}, {}, [], empty_csm())

    turns = list(
        db.scalars(
            select(ExperimentTurn)
            .where(ExperimentTurn.system_run_id.in_(list(run_by_id)), ExperimentTurn.status == "completed")
            .order_by(ExperimentTurn.turn_number.asc(), ExperimentTurn.id.asc())
        ).all()
    )
    turn_ids = [turn.id for turn in turns]
    question_ids = {turn.question_id for turn in turns}

    questions = {row.id: row for row in db.scalars(select(BenchmarkQuestion).where(BenchmarkQuestion.id.in_(question_ids))).all()}
    truths = latest_truths(db, question_ids)
    outputs = {row.turn_id: row for row in db.scalars(select(ExperimentOutput).where(ExperimentOutput.turn_id.in_(turn_ids))).all()}
    claims = claims_by_output(db, [output.id for output in outputs.values()])
    retrieval_items = retrieval_items_by_run(db, [turn.retrieval_run_id for turn in turns if turn.retrieval_run_id])
    retrieval_runs = retrieval_runs_by_id(db, [turn.retrieval_run_id for turn in turns if turn.retrieval_run_id])
    llm_calls = llm_calls_by_id(db, [turn.llm_call_id for turn in turns if turn.llm_call_id])

    offline_turns: list[OfflineTurn] = []
    for turn in turns:
        output = outputs.get(turn.id)
        question = questions.get(turn.question_id)
        if output is None or question is None:
            continue
        offline_turns.append(
            OfflineTurn(
                patient=patient,
                experiment=experiment,
                system_run=run_by_id[turn.system_run_id],
                turn=turn,
                question=question,
                ground_truth=truths.get(question.id),
                output=output,
                claims=claims.get(output.id, []),
                retrieval_items=retrieval_items.get(turn.retrieval_run_id, []),
                retrieval_run=retrieval_runs.get(turn.retrieval_run_id),
                llm_call=llm_calls.get(turn.llm_call_id),
            )
        )

    canonical_sources = load_canonical_sources(db, offline_turns)
    source_aliases = build_source_alias_map(canonical_sources.values())
    events = list(db.scalars(select(BenchmarkEvent).where(BenchmarkEvent.case_id.in_(case_ids)).order_by(BenchmarkEvent.sequence_number.asc())).all()) if case_ids else []
    csm = load_csm_bundle(db, offline_turns)
    return OfflineScope(experiment_id, patient, repetition, offline_turns, canonical_sources, source_aliases, events, csm)


def validate_scope(scope: OfflineScope) -> dict[str, Any]:
    counts = Counter(turn.system_run.system_type for turn in scope.turns)
    question_numbers_by_system = defaultdict(set)
    for turn in scope.turns:
        question_numbers_by_system[turn.system_run.system_type].add(turn.question.turn_number)
    errors = []
    expected_systems = expected_systems_for_scope(counts)
    expected_turns = 20 * len(expected_systems)
    if len(scope.turns) != expected_turns:
        errors.append(f"included_turns_expected_{expected_turns}_found_{len(scope.turns)}")
    observed_expected_systems = [system for system in expected_systems if counts[system] > 0]
    if len(observed_expected_systems) != len(expected_systems):
        errors.append(f"systems_expected_{len(expected_systems)}")
    for system in expected_systems:
        if counts[system] != 20:
            errors.append(f"{system}_questions_expected_20_found_{counts[system]}")
    missing = [str(turn.turn.id) for turn in scope.turns if not turn.output.answer_text]
    if missing:
        errors.append("missing_answer_text")
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "patient": scope.patient,
        "questions": 20,
        "systems": len(expected_systems),
        "expected_systems": expected_systems,
        "repetitions": 1,
        "completed_turns": len(scope.turns),
        "included_turns": len(scope.turns),
        "counts_per_system": {system: counts[system] for system in expected_systems},
        "questions_per_system": {system: len(question_numbers_by_system[system]) for system in expected_systems},
        "missing_answer_turn_ids": missing,
        "summary_label": "Sustha Single-Patient Synthetic Case-Study Results",
    }


def expected_systems_for_scope(counts: Counter) -> list[str]:
    observed = [system for system in ALL_SYSTEMS if counts[system] > 0]
    if observed in (["csm_v3"], ["csm_v4"]):
        return observed
    if "csm_v3" in observed or "csm_v4" in observed:
        return ALL_SYSTEMS
    return SYSTEMS


def latest_truths(db: Session, question_ids: set[UUID]) -> dict[UUID, BenchmarkGroundTruth]:
    truths: dict[UUID, BenchmarkGroundTruth] = {}
    if not question_ids:
        return truths
    for truth in db.scalars(select(BenchmarkGroundTruth).where(BenchmarkGroundTruth.question_id.in_(question_ids))).all():
        current = truths.get(truth.question_id)
        if current is None or truth.version > current.version:
            truths[truth.question_id] = truth
    return truths


def claims_by_output(db: Session, output_ids: list[UUID]) -> dict[UUID, list[ExperimentClaim]]:
    grouped: dict[UUID, list[ExperimentClaim]] = defaultdict(list)
    if not output_ids:
        return grouped
    rows = db.scalars(select(ExperimentClaim).where(ExperimentClaim.output_id.in_(output_ids)).order_by(ExperimentClaim.claim_id.asc())).all()
    for row in rows:
        grouped[row.output_id].append(row)
    return grouped


def retrieval_items_by_run(db: Session, retrieval_run_ids: list[UUID]) -> dict[UUID, list[MemoryRetrievalItem]]:
    grouped: dict[UUID, list[MemoryRetrievalItem]] = defaultdict(list)
    if not retrieval_run_ids:
        return grouped
    rows = db.scalars(
        select(MemoryRetrievalItem)
        .where(MemoryRetrievalItem.retrieval_run_id.in_(retrieval_run_ids))
        .order_by(MemoryRetrievalItem.retrieval_run_id.asc(), MemoryRetrievalItem.rank.asc())
    ).all()
    for row in rows:
        grouped[row.retrieval_run_id].append(row)
    return grouped


def retrieval_runs_by_id(db: Session, retrieval_run_ids: list[UUID]) -> dict[UUID, MemoryRetrievalRun]:
    if not retrieval_run_ids:
        return {}
    return {row.id: row for row in db.scalars(select(MemoryRetrievalRun).where(MemoryRetrievalRun.id.in_(retrieval_run_ids))).all()}


def llm_calls_by_id(db: Session, llm_ids: list[UUID]) -> dict[UUID, LlmCall]:
    if not llm_ids:
        return {}
    return {row.id: row for row in db.scalars(select(LlmCall).where(LlmCall.id.in_(llm_ids))).all()}


def load_canonical_sources(db: Session, turns: list[OfflineTurn]) -> dict[str, CanonicalMemorySource]:
    source_ids = set()
    patient_ids = set()
    instance_ids = {turn.system_run.system_instance_id for turn in turns if turn.system_run.system_instance_id}
    if instance_ids:
        for instance in db.scalars(select(MemorySystemInstance).where(MemorySystemInstance.id.in_(instance_ids))).all():
            patient_ids.add(instance.patient_id)
    for turn in turns:
        for item in turn.retrieval_items:
            if item.canonical_source_id:
                source_ids.add(item.canonical_source_id)
        for citation in turn.output.citations or []:
            if isinstance(citation, dict):
                value = citation.get("canonical_source_id") or citation.get("source_id")
                if value:
                    try:
                        source_ids.add(UUID(str(value)))
                    except ValueError:
                        pass
    filters = []
    if source_ids:
        filters.append(CanonicalMemorySource.id.in_(source_ids))
    if patient_ids:
        filters.append(CanonicalMemorySource.patient_id.in_(patient_ids))
    if not filters:
        return {}
    statement = select(CanonicalMemorySource).where(filters[0] if len(filters) == 1 else filters[0] | filters[1])
    return {str(row.id): row for row in db.scalars(statement).all()}


def build_source_alias_map(sources) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for source in sources:
        canonical_id = str(source.id)
        payload = source.structured_payload or {}
        candidates = [
            canonical_id,
            str(source.document_id) if source.document_id else None,
            str(source.section_id) if source.section_id else None,
            str(source.source_record_id) if source.source_record_id else None,
            payload.get("source_reference"),
            payload.get("source_fixture"),
            payload.get("evaluation_source_id"),
            payload.get("package_source_id"),
        ]
        candidates.extend(extract_evaluation_source_ids(source.content_text))
        for payload_value in payload.values():
            if isinstance(payload_value, str):
                candidates.extend(extract_evaluation_source_ids(payload_value))
        document = payload.get("document")
        if isinstance(document, dict):
            for payload_value in document.values():
                if isinstance(payload_value, str):
                    candidates.extend(extract_evaluation_source_ids(payload_value))
        for candidate in candidates:
            if not candidate:
                continue
            text = str(candidate)
            mapping[text].add(canonical_id)
            if ":" in text:
                mapping[text.rsplit(":", 1)[-1]].add(canonical_id)
    return dict(mapping)


def extract_evaluation_source_ids(text: str | None) -> list[str]:
    if not text:
        return []
    patterns = [
        r"\bDOC-P\d+-\d+\b",
        r"\bP\d+-(?:MEAS|NOTE|ENC|COND|MED|ALL|ALLERGY)-\d+\b",
        r"\bEV-P\d+-\d+\b",
        r"\bCHAT-P\d+-\d+\b",
    ]
    ids: list[str] = []
    for pattern in patterns:
        ids.extend(re.findall(pattern, text))
    return ids


def load_csm_bundle(db: Session, turns: list[OfflineTurn]) -> CsmBundle:
    instance_ids = {turn.system_run.system_instance_id for turn in turns if turn.system_run.system_type in CSM_SYSTEMS and turn.system_run.system_instance_id}
    if not instance_ids:
        return empty_csm()
    states = list(db.scalars(select(CsmStateVariable).where(CsmStateVariable.system_instance_id.in_(instance_ids))).all())
    state_ids = [state.id for state in states]
    evidence = list(db.scalars(select(CsmEvidence).where(CsmEvidence.system_instance_id.in_(instance_ids))).all())
    evidence_ids = [row.id for row in evidence]
    activation_runs = list(db.scalars(select(CsmActivationRun).where(CsmActivationRun.system_instance_id.in_(instance_ids))).all())
    activation_run_ids = [run.id for run in activation_runs]
    return CsmBundle(
        states=states,
        history=list(db.scalars(select(CsmStateHistory).where(CsmStateHistory.state_variable_id.in_(state_ids))).all()) if state_ids else [],
        evidence=evidence,
        links=list(db.scalars(select(CsmStateEvidenceLink).where(CsmStateEvidenceLink.evidence_id.in_(evidence_ids))).all()) if evidence_ids else [],
        dependencies=list(db.scalars(select(CsmStateDependency).where(CsmStateDependency.system_instance_id.in_(instance_ids))).all()),
        conflicts=list(db.scalars(select(CsmConflict).where(CsmConflict.system_instance_id.in_(instance_ids))).all()),
        reviews=list(db.scalars(select(CsmReviewRequest).where(CsmReviewRequest.system_instance_id.in_(instance_ids))).all()),
        activation_runs=activation_runs,
        activation_items=list(db.scalars(select(CsmActivationItem).where(CsmActivationItem.activation_run_id.in_(activation_run_ids))).all()) if activation_run_ids else [],
    )


def empty_csm() -> CsmBundle:
    return CsmBundle([], [], [], [], [], [], [], [], [])
