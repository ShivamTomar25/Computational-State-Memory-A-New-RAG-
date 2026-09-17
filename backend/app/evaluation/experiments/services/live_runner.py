from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from itertools import combinations
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.doctor.model import Doctor
from app.document.models import Document, DocumentText
from app.evaluation.common.enums.metrics import ExperimentStatus
from app.evaluation.datasets.models.dataset import BenchmarkCase, BenchmarkEvent, BenchmarkQuestion
from app.evaluation.datasets.repositories import dataset_repository
from app.evaluation.experiments.models.experiment import (
    Experiment,
    ExperimentClaim,
    ExperimentOutput,
    ExperimentSystemRun,
    ExperimentTurn,
)
from app.evaluation.experiments.repositories import experiment_repository
from app.evaluation.experiments.services.metric_evaluation_service import refresh_experiment_metrics
from app.evaluation.exports.services.export_service import create_inline_export
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.evaluation.judges.human_review.models import EvaluationAnnotation
from app.evaluation.metrics.models import EvaluationMetricResult
from app.evaluation.metrics.registry.registry import list_metric_definitions
from app.evaluation.statistics.models import StatisticalResult
from app.llm.common.services.answer_service import generate_grounded_answer
from app.memory_systems.common.enums.status import SYSTEM_TYPES
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.repositories import memory_repository
from app.memory_systems.common.schemas.memory import (
    MemoryConversationCreate,
    MemoryRetrieveRequest,
    MemorySyncRequest,
)
from app.memory_systems.common.services.memory_service import (
    create_conversation,
    initialize_missing_system_instances,
    retrieve_context,
    sync_system,
)
from app.patient.model import Patient
from app.patient_information.models import Allergy, ClinicalNote, Measurement, MedicalCondition, Medication


RUN_STATUSES = {
    "pending",
    "preparing",
    "synchronizing",
    "retrieving",
    "generating",
    "evaluating",
    "completed",
    "partially_failed",
    "failed",
    "cancelled",
}


class ProviderRateLimitExceeded(RuntimeError):
    pass


class ProviderRetryableTurnError(RuntimeError):
    pass


def run_live_experiment(db: Session, *, doctor: Doctor, experiment: Experiment, readiness: dict) -> Experiment:
    if experiment.status == ExperimentStatus.COMPLETED.value and experiment_repository.list_system_runs(db, experiment.id):
        return experiment

    cases = dataset_repository.list_cases(db, experiment.dataset_id)
    repeats = int(experiment.configuration.get("repeats", settings.evaluation_repeats))
    started_at = utc_now()
    failures = []

    experiment_repository.update_experiment(
        db,
        experiment,
        {
            "status": ExperimentStatus.RUNNING.value,
            "started_at": experiment.started_at or started_at,
            "completed_at": None,
            "failure_reason": None,
            "comparable": False,
        },
    )
    db.commit()

    patient_filter = set(experiment.configuration.get("patients") or [])
    system_filter = set(experiment.configuration.get("systems") or [])

    if patient_filter:
        cases = [case for case in cases if case.case_key in patient_filter]

    systems = [system for system in SYSTEM_TYPES if not system_filter or system in system_filter]

    repetition_filter = normalize_repetition_filter(experiment.configuration.get("repetition_filter") or [])

    for case in cases:
        patient = ensure_case_patient(db, doctor=doctor, case=case)
        materialize_case_events(db, doctor=doctor, patient=patient, case=case)
        initialize_missing_system_instances(db=db, patient_id=patient.id)
        questions = filter_questions(
            db,
            questions=dataset_repository.list_questions_for_case(db, case.id),
            question_filter=experiment.configuration.get("questions") or [],
        )

        for system_type in systems:
            for repetition in range(1, repeats + 1):
                if repetition_filter and repetition not in repetition_filter:
                    continue

                run = ensure_system_run(
                    db,
                    experiment=experiment,
                    case=case,
                    system_type=system_type,
                    repetition=repetition,
                )

                if run.status == "completed" and run.completed_at is not None:
                    continue

                try:
                    execute_system_run(
                        db,
                        doctor=doctor,
                        experiment=experiment,
                        patient=patient,
                        system_run=run,
                        questions=questions,
                    )
                except ProviderRateLimitExceeded as error:
                    experiment_repository.update_experiment(
                        db,
                        experiment,
                        {
                            "status": ExperimentStatus.INCOMPLETE.value,
                            "failure_reason": safe_error(error),
                        },
                    )
                    db.commit()
                    raise
                except ProviderRetryableTurnError as error:
                    experiment_repository.update_experiment(
                        db,
                        experiment,
                        {
                            "status": ExperimentStatus.INCOMPLETE.value,
                            "failure_reason": safe_error(error),
                        },
                    )
                    db.commit()
                    raise
                except Exception as error:
                    failures.append(f"{system_type}/{case.case_key}/rep{repetition}: {safe_error(error)}")
                    update_system_run(
                        db,
                        run,
                        {
                            "status": "failed",
                            "completed_at": utc_now(),
                            "failure_reason": safe_error(error),
                        },
                    )
                    db.commit()

    refresh_experiment_metrics(db, experiment.id)
    write_statistics(db, experiment.id)
    write_exports(db, experiment_id=experiment.id, readiness=readiness)

    runs = experiment_repository.list_system_runs(db, experiment.id)
    completed = sum(1 for run in runs if run.status == "completed")
    failed = sum(1 for run in runs if run.status == "failed")
    status = ExperimentStatus.COMPLETED.value

    if failed and completed:
        status = "partially_failed"
    elif failed and not completed:
        status = ExperimentStatus.FAILED.value

    experiment_repository.update_experiment(
        db,
        experiment,
        {
            "status": status,
            "completed_at": utc_now(),
            "failure_reason": "; ".join(failures[:12]) if failures else None,
            "comparable": completed == len(runs) and failed == 0 and len(runs) > 0,
        },
    )
    db.commit()
    db.refresh(experiment)
    return experiment


def filter_questions(db: Session, *, questions: list[BenchmarkQuestion], question_filter: list) -> list[BenchmarkQuestion]:
    allowed = normalize_question_filter(question_filter)

    if not allowed:
        return questions

    filtered = []

    for question in questions:
        if str(question.turn_number) in allowed or str(question.id) in allowed:
            filtered.append(question)
            continue

        truth = db.scalar(select(BenchmarkGroundTruth).where(BenchmarkGroundTruth.question_id == question.id))

        if truth is not None and str((truth.truth or {}).get("question_id")) in allowed:
            filtered.append(question)

    return filtered


def normalize_question_filter(values) -> set[str]:
    allowed = set()

    for value in values or []:
        if value is None:
            continue

        text = str(value).strip()

        if not text:
            continue

        if "-" in text and text.replace("-", "").isdigit():
            start, end = text.split("-", 1)
            allowed.update(str(number) for number in range(int(start), int(end) + 1))
        elif ".." in text:
            start, end = text.split("..", 1)
            match_start = re.match(r"^(.*?)(\d+)$", start)
            match_end = re.match(r"^(.*?)(\d+)$", end)

            if match_start and match_end and match_start.group(1) == match_end.group(1):
                prefix = match_start.group(1)
                width = max(len(match_start.group(2)), len(match_end.group(2)))
                allowed.update(
                    f"{prefix}{number:0{width}d}"
                    for number in range(int(match_start.group(2)), int(match_end.group(2)) + 1)
                )
            else:
                allowed.add(text)
        else:
            allowed.add(text)

    return allowed


def execute_system_run(
    db: Session,
    *,
    doctor: Doctor,
    experiment: Experiment,
    patient: Patient,
    system_run: ExperimentSystemRun,
    questions: list[BenchmarkQuestion],
) -> None:
    update_system_run(
        db,
        system_run,
        {
            "status": "preparing",
            "started_at": system_run.started_at or utc_now(),
            "completed_at": None,
            "failure_reason": None,
        },
    )
    ensure_metric_rows(db, experiment=experiment, system_run=system_run)
    independent_turns = bool(experiment.configuration.get("independent_turns", False))
    conversation = None if independent_turns else ensure_run_conversation(
        db,
        doctor=doctor,
        patient=patient,
        system_run=system_run,
    )
    instance = memory_repository.get_instance(db=db, patient_id=patient.id, system_type=system_run.system_type)

    for question in questions:
        turn = ensure_turn(db, system_run=system_run, question=question)

        if turn.status == "completed" and get_output_for_turn(db, turn.id) is not None:
            continue

        if turn.status not in {"pending", "synchronizing", "retrieving", "generating"}:
            continue

        turn_conversation = conversation or create_isolated_turn_conversation(
            db,
            doctor=doctor,
            patient=patient,
            system_run=system_run,
            question=question,
        )
        execute_turn(
            db,
            doctor=doctor,
            patient=patient,
            instance=instance,
            conversation=turn_conversation,
            system_run=system_run,
            turn=turn,
            question=question,
        )

    update_system_run(
        db,
        system_run,
        {
            "status": "evaluating",
            "source_cutoff": max((question.source_cutoff for question in questions), default=None),
            "completed_at": None,
        },
    )
    db.commit()
    refresh_experiment_metrics(db, experiment.id)
    update_system_run(
        db,
        system_run,
        {
            "status": "completed",
            "completed_at": utc_now(),
            "failure_reason": None,
        },
    )
    db.commit()


def execute_turn(
    db: Session,
    *,
    doctor: Doctor,
    patient: Patient,
    instance,
    conversation,
    system_run: ExperimentSystemRun,
    turn: ExperimentTurn,
    question: BenchmarkQuestion,
) -> None:
    now = utc_now()
    apply_implementation_configuration(db=db, instance=instance, system_run=system_run)
    update_turn(db, turn, {"status": "synchronizing", "started_at": now, "completed_at": None})
    update_system_run(db, system_run, {"status": "synchronizing", "source_cutoff": question.source_cutoff})
    db.commit()

    if not system_run.configuration_snapshot.get("skip_sync"):
        sync_system(
            db=db,
            doctor=doctor,
            patient_id=patient.id,
            system_type=system_run.system_type,
            request=MemorySyncRequest(
                cutoff_time=question.source_cutoff,
                mode="evaluation",
                include_patient_information=True,
                include_documents=True,
                include_conversation=True,
            ),
        )
    db.refresh(system_run)
    update_system_run(
        db,
        system_run,
        {"source_snapshot_hash": source_snapshot_hash(db, patient_id=patient.id, cutoff_time=question.source_cutoff)},
    )

    user_message = memory_repository.create_message(
        db=db,
        conversation=conversation,
        data={
            "role": "user",
            "content": question.question,
            "event_time": now,
            "token_count": max(1, (len(question.question) + 3) // 4),
            "generation_status": "evaluation_prompt",
            "retrieval_run_id": None,
        },
    )
    update_turn(db, turn, {"user_message_id": user_message.id, "status": "retrieving"})
    update_system_run(db, system_run, {"status": "retrieving"})
    db.commit()

    retrieval = retrieve_context(
        db=db,
        doctor=doctor,
        patient_id=patient.id,
        system_type=system_run.system_type,
        request=MemoryRetrieveRequest(
            query=question.question,
            top_k=int(system_run.configuration_snapshot.get("top_k") or settings.memory_default_top_k),
            token_budget=int(system_run.configuration_snapshot.get("token_budget") or settings.memory_default_context_token_budget),
            conversation_id=conversation.id,
            include_citations=True,
        ),
    )
    db.refresh(turn)
    db.refresh(user_message)
    memory_repository.update_message_retrieval(db=db, message=user_message, retrieval_run_id=retrieval.retrieval_run_id)
    update_turn(db, turn, {"retrieval_run_id": retrieval.retrieval_run_id, "status": "generating"})
    update_system_run(db, system_run, {"status": "generating"})
    db.commit()

    history = memory_repository.list_messages(db=db, conversation_id=conversation.id)
    request_delay = float(system_run.configuration_snapshot.get("request_delay_seconds") or 0)

    generation = generate_grounded_answer(
        db,
        patient=patient,
        instance=instance,
        conversation=conversation,
        retrieval=retrieval,
        conversation_history=history,
        question=question.question,
        generation_options={
            "request_delay_seconds": request_delay,
            "max_retries": int(system_run.configuration_snapshot.get("max_retries") or settings.groq_max_retries),
        },
    )
    db.refresh(turn)

    if is_rate_limit_outcome(generation):
        update_turn(db, turn, {"status": "pending", "completed_at": None})
        db.commit()
        raise ProviderRateLimitExceeded(generation.error_reason or "LLM provider rate limit exceeded.")

    if is_retryable_provider_outcome(generation):
        update_turn(db, turn, {"status": "pending", "completed_at": None})
        db.commit()
        raise ProviderRetryableTurnError(generation.error_reason or "Retryable LLM provider failure.")

    assistant_message = None

    if generation.status == "completed" and generation.answer is not None:
        assistant_message = memory_repository.create_message(
            db=db,
            conversation=conversation,
            data={
                "role": "assistant",
                "content": generation.answer.answer,
                "event_time": utc_now(),
                "token_count": generation.output_tokens,
                "generation_status": "completed",
                "retrieval_run_id": retrieval.retrieval_run_id,
            },
        )

    output = upsert_experiment_output(
        db,
        turn=turn,
        retrieval=retrieval,
        generation=generation,
    )
    replace_experiment_claims(db, output=output, retrieval=retrieval, generation=generation)
    replace_automated_annotation(db, output=output, generation_status=generation.status, warnings=generation.warnings)
    update_turn(
        db,
        turn,
        {
            "assistant_message_id": assistant_message.id if assistant_message else None,
            "llm_call_id": UUID(generation.llm_call_id) if generation.llm_call_id else None,
            "status": "completed" if generation.status in {"completed", "not_configured"} else "failed",
            "completed_at": utc_now(),
        },
    )
    db.commit()


def is_rate_limit_outcome(generation) -> bool:
    if generation.status != "failed":
        return False

    text = " ".join(
        str(value or "")
        for value in (
            getattr(generation, "error_code", None),
            getattr(generation, "error_reason", None),
            " ".join(getattr(generation, "warnings", []) or []),
        )
    ).lower()

    return "rate limit" in text or "429" in text or "quota" in text or "exhaust" in text


def is_retryable_provider_outcome(generation) -> bool:
    if generation.status != "failed":
        return False

    text = " ".join(
        str(value or "")
        for value in (
            getattr(generation, "error_code", None),
            getattr(generation, "error_reason", None),
            " ".join(getattr(generation, "warnings", []) or []),
        )
    ).lower()

    retryable_markers = (
        "llmstructuredoutputfailed",
        "structured output",
        "timeout",
        "timed out",
        "connection",
        "temporar",
        "provider unavailable",
    )
    permanent_markers = (
        "authorization",
        "permission",
        "invalid benchmark",
        "invalid patient",
        "missing ground truth",
        "schema failure",
    )

    return any(marker in text for marker in retryable_markers) and not any(marker in text for marker in permanent_markers)


def ensure_case_patient(db: Session, *, doctor: Doctor, case: BenchmarkCase) -> Patient:
    patient_code = case.manifest.get("patient_code") or f"EVAL-{case.case_key}"
    patient = db.scalar(
        select(Patient).where(
            Patient.doctor_id == doctor.id,
            Patient.patient_code == patient_code,
        )
    )

    if patient is not None:
        return patient

    patient = Patient(
        doctor_id=doctor.id,
        patient_code=patient_code,
        full_name=f"Evaluation Patient {case.case_key}",
        date_of_birth=date(1975, 1, 1),
        sex="unknown",
        is_active=True,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def materialize_case_events(db: Session, *, doctor: Doctor, patient: Patient, case: BenchmarkCase) -> None:
    events = list(
        db.scalars(
            select(BenchmarkEvent)
            .where(BenchmarkEvent.case_id == case.id)
            .order_by(BenchmarkEvent.sequence_number.asc())
        ).all()
    )
    changed = False

    for event in events:
        reference = event.source_fixture or f"{case.case_key}:event-{event.sequence_number}"

        if event.event_type == "condition":
            changed = materialize_condition(db, doctor=doctor, patient=patient, event=event, reference=reference) or changed
        elif event.event_type == "medication":
            changed = materialize_medication(db, doctor=doctor, patient=patient, event=event, reference=reference) or changed
        elif event.event_type == "allergy":
            changed = materialize_allergy(db, doctor=doctor, patient=patient, event=event, reference=reference) or changed
        elif event.event_type == "measurement":
            changed = materialize_measurement(db, doctor=doctor, patient=patient, event=event, reference=reference) or changed
        elif event.event_type == "clinical_note":
            changed = materialize_note(db, doctor=doctor, patient=patient, event=event, reference=reference) or changed
        elif event.event_type == "document":
            changed = materialize_document(db, doctor=doctor, patient=patient, event=event, reference=reference) or changed

    if changed:
        db.commit()


def materialize_condition(db: Session, *, doctor: Doctor, patient: Patient, event: BenchmarkEvent, reference: str) -> bool:
    existing = db.scalar(
        select(MedicalCondition).where(
            MedicalCondition.patient_id == patient.id,
            MedicalCondition.source_reference == reference,
        )
    )
    if existing is not None:
        return False

    payload = event.payload or {}
    db.add(
        MedicalCondition(
            patient_id=patient.id,
            created_by_doctor_id=doctor.id,
            name=payload.get("name") or "Unspecified condition",
            category=payload.get("category") or "problem-list",
            clinical_status=payload.get("clinical_status") or "active",
            verification_status=payload.get("verification_status") or "confirmed",
            severity=payload.get("severity"),
            onset_date=event.valid_time.date(),
            notes=append_reference(payload.get("notes"), reference),
            source_type="evaluation",
            source_reference=reference,
            is_active=True,
            recorded_at=event.ingestion_time,
            created_at=event.ingestion_time,
            updated_at=event.ingestion_time,
        )
    )
    return True


def materialize_medication(db: Session, *, doctor: Doctor, patient: Patient, event: BenchmarkEvent, reference: str) -> bool:
    existing = db.scalar(
        select(Medication).where(
            Medication.patient_id == patient.id,
            Medication.source_reference == reference,
        )
    )
    if existing is not None:
        return False

    payload = event.payload or {}
    db.add(
        Medication(
            patient_id=patient.id,
            created_by_doctor_id=doctor.id,
            medication_name=payload.get("medication_name") or "Unspecified medication",
            generic_name=payload.get("generic_name"),
            dosage_value=Decimal(str(payload["dosage_value"])) if payload.get("dosage_value") is not None else None,
            dosage_unit=payload.get("dosage_unit"),
            route=payload.get("route"),
            frequency=payload.get("frequency"),
            instructions=append_reference(payload.get("instructions"), reference),
            reason=payload.get("reason"),
            medication_status=payload.get("medication_status") or "active",
            start_date=event.valid_time.date(),
            source_type="evaluation",
            source_reference=reference,
            is_active=True,
            recorded_at=event.ingestion_time,
            created_at=event.ingestion_time,
            updated_at=event.ingestion_time,
        )
    )
    return True


def materialize_allergy(db: Session, *, doctor: Doctor, patient: Patient, event: BenchmarkEvent, reference: str) -> bool:
    existing = db.scalar(
        select(Allergy).where(
            Allergy.patient_id == patient.id,
            Allergy.source_reference == reference,
        )
    )
    if existing is not None:
        return False

    payload = event.payload or {}
    db.add(
        Allergy(
            patient_id=patient.id,
            created_by_doctor_id=doctor.id,
            substance=payload.get("substance") or "Unspecified allergen",
            allergy_type=payload.get("allergy_type") or "drug",
            category=payload.get("category") or "medication",
            clinical_status=payload.get("clinical_status") or "active",
            verification_status=payload.get("verification_status") or "confirmed",
            criticality=payload.get("criticality"),
            reaction=payload.get("reaction"),
            severity=payload.get("severity"),
            onset_date=event.valid_time.date(),
            notes=append_reference(payload.get("notes"), reference),
            source_type="evaluation",
            source_reference=reference,
            is_active=True,
            recorded_at=event.ingestion_time,
            created_at=event.ingestion_time,
            updated_at=event.ingestion_time,
        )
    )
    return True


def materialize_measurement(db: Session, *, doctor: Doctor, patient: Patient, event: BenchmarkEvent, reference: str) -> bool:
    existing = db.scalar(
        select(Measurement).where(
            Measurement.patient_id == patient.id,
            Measurement.source_reference == reference,
        )
    )
    if existing is not None:
        return False

    payload = event.payload or {}
    db.add(
        Measurement(
            patient_id=patient.id,
            created_by_doctor_id=doctor.id,
            observation_name=payload.get("observation_name") or payload.get("name") or "Unspecified measurement",
            value_numeric=Decimal(str(payload["value_numeric"])) if payload.get("value_numeric") is not None else None,
            value_text=payload.get("value_text"),
            unit=payload.get("unit"),
            interpretation=payload.get("interpretation"),
            status=payload.get("status") or "final",
            observed_at=event.valid_time,
            source_type="evaluation",
            source_reference=reference,
            notes=append_reference(payload.get("notes"), reference),
            is_active=True,
            recorded_at=event.ingestion_time,
            created_at=event.ingestion_time,
            updated_at=event.ingestion_time,
        )
    )
    return True


def materialize_note(db: Session, *, doctor: Doctor, patient: Patient, event: BenchmarkEvent, reference: str) -> bool:
    existing = db.scalar(
        select(ClinicalNote).where(
            ClinicalNote.patient_id == patient.id,
            ClinicalNote.source_reference == reference,
        )
    )
    if existing is not None:
        return False

    payload = event.payload or {}
    db.add(
        ClinicalNote(
            patient_id=patient.id,
            created_by_doctor_id=doctor.id,
            note_type=payload.get("note_type") or "evaluation",
            title=payload.get("title"),
            content=append_reference(payload.get("content") or payload.get("text") or "", reference),
            status=payload.get("status") or "final",
            authored_at=event.valid_time,
            source_type="evaluation",
            source_reference=reference,
            is_active=True,
            created_at=event.ingestion_time,
            updated_at=event.ingestion_time,
        )
    )
    return True


def materialize_document(db: Session, *, doctor: Doctor, patient: Patient, event: BenchmarkEvent, reference: str) -> bool:
    existing = db.scalar(
        select(Document).where(
            Document.patient_id == patient.id,
            Document.storage_object_path == f"inline://evaluation/{patient.id}/{reference}",
        )
    )
    if existing is not None:
        return False

    payload = event.payload or {}
    text = payload.get("content") or payload.get("text") or ""
    document = Document(
        patient_id=patient.id,
        uploaded_by_doctor_id=doctor.id,
        document_type=payload.get("document_type") or "clinical_note",
        title=payload.get("title") or f"Evaluation source {reference}",
        description=append_reference(payload.get("description"), reference),
        original_filename=payload.get("original_filename") or f"{reference}.txt",
        safe_filename=f"{reference.replace(':', '-')}.txt",
        file_extension=".txt",
        declared_content_type="text/plain",
        detected_content_type="text/plain",
        size_bytes_expected=max(1, len(text.encode("utf-8"))),
        size_bytes_actual=max(1, len(text.encode("utf-8"))),
        checksum_algorithm="sha256",
        checksum_expected=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        checksum_actual=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        storage_provider="inline",
        storage_bucket="evaluation",
        storage_object_path=f"inline://evaluation/{patient.id}/{reference}",
        document_date=event.valid_time.date(),
        source_type="evaluation",
        upload_status="uploaded",
        verification_status="verified",
        processing_status="completed",
        text_extraction_status="completed",
        ocr_requirement_status="not_required",
        version_number=1,
        is_current_version=True,
        is_active=True,
        upload_deadline_at=event.ingestion_time,
        uploaded_at=event.ingestion_time,
        verified_at=event.ingestion_time,
        processing_started_at=event.ingestion_time,
        processing_completed_at=event.ingestion_time,
        created_at=event.ingestion_time,
        updated_at=event.ingestion_time,
    )
    db.add(document)
    db.flush()
    db.add(
        DocumentText(
            document_id=document.id,
            extraction_method="synthetic_fixture",
            extractor_name="sustha_evaluation",
            extractor_version="1",
            normalized_text=append_reference(text, reference),
            character_count=len(text),
            word_count=len(text.split()),
            page_count=1,
            quality_score=100,
            quality_status="good",
            created_at=event.ingestion_time,
            updated_at=event.ingestion_time,
        )
    )
    return True


def ensure_system_run(
    db: Session,
    *,
    experiment: Experiment,
    case: BenchmarkCase,
    system_type: str,
    repetition: int,
) -> ExperimentSystemRun:
    run = db.scalar(
        select(ExperimentSystemRun).where(
            ExperimentSystemRun.experiment_id == experiment.id,
            ExperimentSystemRun.case_id == case.id,
            ExperimentSystemRun.system_type == system_type,
            ExperimentSystemRun.repetition_number == repetition,
        )
    )
    if run is not None:
        run.configuration_snapshot = {
            **(run.configuration_snapshot or {}),
            "skip_sync": experiment.configuration.get("skip_sync", False),
            "request_delay_seconds": experiment.configuration.get("request_delay_seconds", 0),
            "max_retries": experiment.configuration.get("max_retries", settings.groq_max_retries),
            "top_k": experiment.configuration.get("top_k", settings.memory_default_top_k),
            "token_budget": experiment.configuration.get("token_budget", settings.memory_default_context_token_budget),
            "implementation_version": experiment.configuration.get("implementation_version"),
        }
        db.flush()
        return run

    run = experiment_repository.create_system_run(
        db,
        {
            "experiment_id": experiment.id,
            "case_id": case.id,
            "system_type": system_type,
            "repetition_number": repetition,
            "status": "pending",
            "source_cutoff": None,
            "source_snapshot_hash": None,
            "configuration_snapshot": {
                "profile": experiment.profile,
                "system_type": system_type,
                "model": settings.groq_model,
                "prompt_version": settings.llm_prompt_version,
                "top_k": experiment.configuration.get("top_k", settings.memory_default_top_k),
                "token_budget": experiment.configuration.get("token_budget", settings.memory_default_context_token_budget),
                "skip_sync": experiment.configuration.get("skip_sync", False),
                "request_delay_seconds": experiment.configuration.get("request_delay_seconds", 0),
                "max_retries": experiment.configuration.get("max_retries", settings.groq_max_retries),
                "implementation_version": experiment.configuration.get("implementation_version"),
            },
        },
    )
    db.commit()
    db.refresh(run)
    return run


def normalize_repetition_filter(values) -> set[int]:
    normalized = set()

    for value in values or []:
        if value is None:
            continue

        text = str(value)

        if "-" in text:
            start, end = text.split("-", 1)
            normalized.update(range(int(start), int(end) + 1))
        else:
            normalized.add(int(text))

    return normalized


def ensure_turn(db: Session, *, system_run: ExperimentSystemRun, question: BenchmarkQuestion) -> ExperimentTurn:
    turn = db.scalar(
        select(ExperimentTurn).where(
            ExperimentTurn.system_run_id == system_run.id,
            ExperimentTurn.question_id == question.id,
        )
    )
    if turn is not None:
        return turn

    turn = experiment_repository.create_turn(
        db,
        {
            "system_run_id": system_run.id,
            "question_id": question.id,
            "turn_number": question.turn_number,
            "status": "pending",
        },
    )
    db.commit()
    db.refresh(turn)
    return turn


def ensure_metric_rows(db: Session, *, experiment: Experiment, system_run: ExperimentSystemRun) -> None:
    changed = False

    for metric in list_metric_definitions():
        existing = db.scalar(
            select(ExperimentOutput.id)
            .select_from(ExperimentOutput)
            .join(ExperimentTurn, ExperimentOutput.turn_id == ExperimentTurn.id)
            .where(ExperimentTurn.system_run_id == system_run.id)
            .limit(1)
        )
        status = "not_applicable" if existing else "pending"
        reason = None if existing else "pending_live_evaluation_run"
        result = db.scalar(
            select(EvaluationMetricResult).where(
                EvaluationMetricResult.experiment_id == experiment.id,
                EvaluationMetricResult.system_run_id == system_run.id,
                EvaluationMetricResult.metric_name == metric.metric_id,
                EvaluationMetricResult.turn_id.is_(None),
            )
        )
        if result is not None:
            continue

        experiment_repository.create_metric_result(
            db,
            {
                "experiment_id": experiment.id,
                "system_run_id": system_run.id,
                "turn_id": None,
                "metric_name": metric.metric_id,
                "metric_version": metric.version,
                "value": None,
                "numerator": None,
                "denominator": None,
                "applicable": False,
                "reason_not_applicable": reason,
                "details": {
                    "status": status,
                    "system_type": system_run.system_type,
                    "case_id": str(system_run.case_id),
                    "repetition_number": system_run.repetition_number,
                },
            },
        )
        changed = True

    if changed:
        db.commit()


def ensure_run_conversation(db: Session, *, doctor: Doctor, patient: Patient, system_run: ExperimentSystemRun):
    instance = memory_repository.get_instance(db=db, patient_id=patient.id, system_type=system_run.system_type)

    if system_run.conversation_id:
        conversation = memory_repository.get_conversation(
            db=db,
            system_instance_id=instance.id,
            conversation_id=system_run.conversation_id,
        )
        if conversation is not None:
            return conversation

    response = create_conversation(
        db=db,
        doctor=doctor,
        patient_id=patient.id,
        system_type=system_run.system_type,
        request=MemoryConversationCreate(title=f"Evaluation {system_run.system_type}"),
    )
    conversation = memory_repository.get_conversation(
        db=db,
        system_instance_id=instance.id,
        conversation_id=response.id,
    )
    update_system_run(
        db,
        system_run,
        {
            "system_instance_id": instance.id,
            "conversation_id": conversation.id,
        },
    )
    db.commit()
    return conversation


def create_isolated_turn_conversation(
    db: Session,
    *,
    doctor: Doctor,
    patient: Patient,
    system_run: ExperimentSystemRun,
    question: BenchmarkQuestion,
):
    instance = memory_repository.get_instance(db=db, patient_id=patient.id, system_type=system_run.system_type)
    response = create_conversation(
        db=db,
        doctor=doctor,
        patient_id=patient.id,
        system_type=system_run.system_type,
        request=MemoryConversationCreate(
            title=f"Evaluation {system_run.system_type} turn {question.turn_number}",
        ),
    )
    conversation = memory_repository.get_conversation(
        db=db,
        system_instance_id=instance.id,
        conversation_id=response.id,
    )

    if system_run.conversation_id is None:
        update_system_run(
            db,
            system_run,
            {
                "system_instance_id": instance.id,
                "conversation_id": conversation.id,
            },
        )
        db.commit()

    return conversation


def upsert_experiment_output(db: Session, *, turn: ExperimentTurn, retrieval, generation) -> ExperimentOutput:
    output = get_output_for_turn(db, turn.id)
    answer = generation.answer
    structured = answer.model_dump(mode="json") if answer is not None else {}
    structured.update(
        {
            "generation_status": generation.status,
            "warnings": generation.warnings,
            "llm_provider": generation.provider,
            "llm_model": generation.model,
            "retrieval_run_id": str(retrieval.retrieval_run_id) if retrieval.retrieval_run_id else None,
            "retrieval_readiness_status": retrieval.readiness_status,
        }
    )
    citations = enriched_citations(retrieval, answer)
    data = {
        "answer_text": answer.answer if answer is not None else None,
        "structured_answer": structured,
        "answer_confidence": answer.confidence if answer is not None else None,
        "insufficient_evidence": bool(answer.insufficient_evidence) if answer is not None else True,
        "citations": citations,
        "conflicts": answer.conflicts if answer is not None else [],
    }

    if output is None:
        output = ExperimentOutput(turn_id=turn.id, **data)
        db.add(output)
        db.flush()
        return output

    for field, value in data.items():
        setattr(output, field, value)
    db.flush()
    return output


def replace_experiment_claims(db: Session, *, output: ExperimentOutput, retrieval, generation) -> None:
    db.execute(delete(ExperimentClaim).where(ExperimentClaim.output_id == output.id))

    if generation.answer is None:
        db.flush()
        return

    citation_map = context_citation_map(retrieval)

    for claim in generation.answer.atomic_claims:
        citation_ids = [
            citation_map.get(citation_id, citation_id)
            for citation_id in claim.citation_ids
        ]
        citation_ids = [str(value) for value in citation_ids if value]
        db.add(
            ExperimentClaim(
                output_id=output.id,
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                normalized_claim={
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                    "value": claim.value,
                    "normalized_value": claim.normalized_value,
                    "unit": claim.unit,
                    "status": claim.status,
                    "negation": claim.negation,
                    "confidence": claim.confidence,
                    "citation_ids": citation_ids,
                },
                confidence=claim.confidence,
                citation_ids=citation_ids,
                source_support_status=None,
            )
        )

    db.flush()


def replace_automated_annotation(db: Session, *, output: ExperimentOutput, generation_status: str, warnings: list[str]) -> None:
    db.execute(
        delete(EvaluationAnnotation).where(
            EvaluationAnnotation.output_id == output.id,
            EvaluationAnnotation.annotation_type == "automated_generation_status",
        )
    )
    db.add(
        EvaluationAnnotation(
            output_id=output.id,
            claim_id=None,
            reviewer_id=None,
            annotation_type="automated_generation_status",
            value=generation_status[:160],
            notes="; ".join(warnings)[:500] if warnings else None,
        )
    )
    db.flush()


def write_statistics(db: Session, experiment_id: UUID) -> None:
    db.execute(delete(StatisticalResult).where(StatisticalResult.experiment_id == experiment_id))
    metric_rows = experiment_repository.list_metric_results(db, experiment_id)
    runs = {run.id: run for run in experiment_repository.list_system_runs(db, experiment_id)}
    by_metric = {}

    for result in metric_rows:
        run = runs.get(result.system_run_id)
        if run is None or result.value is None:
            continue
        by_metric.setdefault(result.metric_name, {}).setdefault(run.system_type, {})[
            (str(run.case_id), run.repetition_number)
        ] = float(result.value)

    rows_to_add = []

    for metric_name, system_values in by_metric.items():
        pair_count = max(1, len(list(combinations(system_values.keys(), 2))))

        for system_a, system_b in combinations(sorted(system_values.keys()), 2):
            paired_keys = sorted(set(system_values[system_a]) & set(system_values[system_b]))

            if not paired_keys:
                continue

            diffs = [system_values[system_a][key] - system_values[system_b][key] for key in paired_keys]
            mean_diff = sum(diffs) / len(diffs)
            variance = sum((value - mean_diff) ** 2 for value in diffs) / (len(diffs) - 1) if len(diffs) > 1 else 0.0
            stddev = math.sqrt(variance)
            stderr = stddev / math.sqrt(len(diffs)) if diffs else 0.0
            z_score = abs(mean_diff / stderr) if stderr else None
            raw_p = math.erfc(z_score / math.sqrt(2)) if z_score is not None else None
            ci_low = mean_diff - 1.96 * stderr
            ci_high = mean_diff + 1.96 * stderr
            rows_to_add.append(
                StatisticalResult(
                    experiment_id=experiment_id,
                    metric_name=metric_name,
                    system_a=system_a,
                    system_b=system_b,
                    sample_count=len(diffs),
                    test_name="paired_difference_normal_approximation",
                    statistic=mean_diff,
                    raw_p_value=raw_p,
                    corrected_p_value=min(raw_p * pair_count, 1.0) if raw_p is not None else None,
                    effect_size=mean_diff / stddev if stddev else None,
                    confidence_interval={"low": ci_low, "high": ci_high, "level": 0.95},
                    details={"paired_keys": paired_keys, "differences": diffs},
                )
            )

    db.add_all(rows_to_add)
    db.commit()


def write_exports(db: Session, *, experiment_id: UUID, readiness: dict) -> None:
    runs = experiment_repository.list_system_runs(db, experiment_id)
    turns = experiment_repository.list_turns(db, experiment_id)
    metrics = experiment_repository.list_metric_results(db, experiment_id)
    statistics = experiment_repository.list_statistical_results(db, experiment_id)
    manifest = {
        "experiment_id": str(experiment_id),
        "systems": list(SYSTEM_TYPES),
        "metric_count": len(list_metric_definitions()),
        "metrics": [metric.metric_id for metric in list_metric_definitions()],
        "run_count": len(runs),
        "turn_count": len(turns),
        "readiness": readiness,
        "generated_at": utc_now().isoformat(),
    }
    results = {
        "manifest": manifest,
        "system_runs": [serialize_run(run) for run in runs],
        "turns": [serialize_turn(turn) for turn in turns],
        "metric_results": [serialize_metric(result) for result in metrics],
        "statistics": [serialize_statistical_result(result) for result in statistics],
    }
    csv_content = {"filename": "metric_results.csv", "content": metric_csv(metrics, runs)}
    create_inline_export(db, experiment_id=experiment_id, export_type="manifest_json", content=manifest)
    create_inline_export(db, experiment_id=experiment_id, export_type="results_json", content=results)
    create_inline_export(db, experiment_id=experiment_id, export_type="metric_results_csv", content=csv_content)


def source_snapshot_hash(db: Session, *, patient_id: UUID, cutoff_time: datetime) -> str:
    sources = list(
        db.scalars(
            select(CanonicalMemorySource)
            .where(
                CanonicalMemorySource.patient_id == patient_id,
                CanonicalMemorySource.is_active.is_(True),
                CanonicalMemorySource.recorded_time <= cutoff_time,
            )
            .order_by(CanonicalMemorySource.id.asc())
        ).all()
    )
    payload = [
        {
            "id": str(source.id),
            "hash": source.content_hash,
            "recorded_time": source.recorded_time.isoformat(),
        }
        for source in sources
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def enriched_citations(retrieval, answer) -> list[dict]:
    if answer is None:
        return []

    context_map = {
        f"C{index}": item
        for index, item in enumerate(retrieval.context_items, start=1)
    }
    citations = []

    for citation in answer.citations:
        data = citation.model_dump(mode="json")
        item = context_map.get(citation.citation_id)

        if item is not None:
            data["canonical_source_id"] = str(item.canonical_source_id) if item.canonical_source_id else None
            data["document_id"] = str(item.document_id) if item.document_id else None
            data["section_id"] = str(item.section_id) if item.section_id else None
            data["page_number"] = item.page_number
            data["source_type"] = item.source_type

        citations.append(data)

    return citations


def context_citation_map(retrieval) -> dict[str, str]:
    mapping = {}

    for index, item in enumerate(retrieval.context_items, start=1):
        if item.canonical_source_id is not None:
            mapping[f"C{index}"] = str(item.canonical_source_id)

    return mapping


def get_output_for_turn(db: Session, turn_id: UUID) -> Optional[ExperimentOutput]:
    return db.scalar(select(ExperimentOutput).where(ExperimentOutput.turn_id == turn_id))


def update_system_run(db: Session, run: ExperimentSystemRun, data: dict) -> None:
    status = data.get("status")
    if status and status not in RUN_STATUSES:
        raise ValueError(f"Unsupported evaluation system run status: {status}")
    for field, value in data.items():
        setattr(run, field, value)
    db.flush()


def update_turn(db: Session, turn: ExperimentTurn, data: dict) -> None:
    status = data.get("status")
    if status and status not in RUN_STATUSES:
        raise ValueError(f"Unsupported evaluation turn status: {status}")
    for field, value in data.items():
        setattr(turn, field, value)
    db.flush()


def apply_implementation_configuration(*, db: Session, instance, system_run: ExperimentSystemRun) -> None:
    implementation_version = (system_run.configuration_snapshot or {}).get("implementation_version")
    if not implementation_version or instance is None or instance.system_type not in {"csm", "csm_v3", "csm_v4"}:
        return

    configuration = dict(instance.configuration or {})
    if configuration.get("implementation_version") == implementation_version:
        return

    configuration["implementation_version"] = implementation_version
    instance.configuration = configuration
    db.flush()


def append_reference(text: Optional[str], reference: str) -> str:
    base = (text or "").strip()
    suffix = f"Evaluation source: {reference}"
    return f"{base}. {suffix}" if base else suffix


def serialize_run(run: ExperimentSystemRun) -> dict:
    return {
        "id": str(run.id),
        "case_id": str(run.case_id),
        "system_type": run.system_type,
        "repetition_number": run.repetition_number,
        "system_instance_id": str(run.system_instance_id) if run.system_instance_id else None,
        "conversation_id": str(run.conversation_id) if run.conversation_id else None,
        "status": run.status,
        "source_cutoff": run.source_cutoff.isoformat() if run.source_cutoff else None,
        "source_snapshot_hash": run.source_snapshot_hash,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "failure_reason": run.failure_reason,
    }


def serialize_turn(turn: ExperimentTurn) -> dict:
    return {
        "id": str(turn.id),
        "system_run_id": str(turn.system_run_id),
        "question_id": str(turn.question_id),
        "turn_number": turn.turn_number,
        "user_message_id": str(turn.user_message_id) if turn.user_message_id else None,
        "assistant_message_id": str(turn.assistant_message_id) if turn.assistant_message_id else None,
        "retrieval_run_id": str(turn.retrieval_run_id) if turn.retrieval_run_id else None,
        "llm_call_id": str(turn.llm_call_id) if turn.llm_call_id else None,
        "status": turn.status,
        "started_at": turn.started_at.isoformat() if turn.started_at else None,
        "completed_at": turn.completed_at.isoformat() if turn.completed_at else None,
    }


def serialize_metric(result) -> dict:
    return {
        "metric_name": result.metric_name,
        "system_run_id": str(result.system_run_id) if result.system_run_id else None,
        "value": result.value,
        "numerator": result.numerator,
        "denominator": result.denominator,
        "applicable": result.applicable,
        "reason_not_applicable": result.reason_not_applicable,
        "details": result.details,
    }


def serialize_statistical_result(result: StatisticalResult) -> dict:
    return {
        "metric_name": result.metric_name,
        "system_a": result.system_a,
        "system_b": result.system_b,
        "sample_count": result.sample_count,
        "test_name": result.test_name,
        "statistic": result.statistic,
        "raw_p_value": result.raw_p_value,
        "corrected_p_value": result.corrected_p_value,
        "effect_size": result.effect_size,
        "confidence_interval": result.confidence_interval,
        "details": result.details,
    }


def metric_csv(metrics: list, runs: list[ExperimentSystemRun]) -> str:
    runs_by_id = {run.id: run for run in runs}
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "system_type",
            "case_id",
            "repetition_number",
            "metric_name",
            "value",
            "applicable",
            "reason_not_applicable",
        ],
    )
    writer.writeheader()

    for result in metrics:
        run = runs_by_id.get(result.system_run_id)
        writer.writerow(
            {
                "system_type": run.system_type if run else "",
                "case_id": str(run.case_id) if run else "",
                "repetition_number": run.repetition_number if run else "",
                "metric_name": result.metric_name,
                "value": result.value if result.value is not None else "",
                "applicable": result.applicable,
                "reason_not_applicable": result.reason_not_applicable or "",
            }
        )

    return buffer.getvalue()


def safe_error(error: Exception) -> str:
    return str(error)[:500] or error.__class__.__name__


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
