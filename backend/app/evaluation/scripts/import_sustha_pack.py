from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, init_db
from app.doctor.model import Doctor
from app.security.password import hash_password
from app.document.models import Document
from app.document.service import direct_upload_document
from app.evaluation.datasets.models.dataset import (
    BenchmarkCase,
    BenchmarkDataset,
    BenchmarkEvent,
    BenchmarkQuestion,
)
from app.evaluation.ground_truth.models.ground_truth import BenchmarkGroundTruth
from app.memory_systems.common.enums.status import SYSTEM_TYPES
from app.memory_systems.common.models.memory import CanonicalMemorySource
from app.memory_systems.common.repositories import memory_repository
from app.memory_systems.common.schemas.memory import MemorySyncRequest
from app.memory_systems.common.services.memory_service import (
    initialize_missing_system_instances,
    sync_system,
)
from app.patient.model import Patient
from app.patient_information.models import (
    Allergy,
    ClinicalEncounter,
    ClinicalNote,
    Measurement,
    MedicalCondition,
    Medication,
)
from app.storage.schemas import (
    SignedDownloadResult,
    SignedUploadResult,
    StorageHealthResult,
    StoredObjectMetadata,
    StoredObjectResult,
)


DATASET_NAME = "Sustha CSM Three-Patient Pilot"
DATASET_SPLIT = "pilot"
SOURCE_MARKER_PREFIX = "Evaluation source:"
DEFAULT_OUTPUT_ROOT = Path("evaluation/results")


class LocalFixtureStorageProvider:
    provider_name = "local_fixture"
    bucket = "sustha-three-patient-pack"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_bytes(self, *, object_path: str, content: bytes, content_type: str, overwrite: bool = False, metadata: Optional[dict] = None):
        path = self._path(object_path)

        if path.exists() and not overwrite:
            raise ValueError(f"Object already exists: {object_path}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredObjectResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=object_path,
            full_path=str(path),
            content_type=content_type,
        )

    def upload_stream(self, *, object_path: str, stream, content_type: str, overwrite: bool = False, metadata: Optional[dict] = None):
        return self.upload_bytes(
            object_path=object_path,
            content=stream.read(),
            content_type=content_type,
            overwrite=overwrite,
            metadata=metadata,
        )

    def create_signed_upload(self, *, object_path: str, content_type: str):
        return SignedUploadResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=object_path,
            signed_url=f"local://{object_path}",
            expires_in=3600,
        )

    def create_signed_download(self, *, object_path: str, expires_in: Optional[int] = None):
        return SignedDownloadResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=object_path,
            signed_url=f"local://{object_path}",
            expires_in=expires_in or 3600,
        )

    def object_exists(self, *, object_path: str) -> bool:
        return self._path(object_path).exists()

    def get_object_metadata(self, *, object_path: str):
        path = self._path(object_path)
        content = path.read_bytes() if path.exists() else b""
        return StoredObjectMetadata(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=object_path,
            size_bytes=len(content),
            etag=hashlib.sha256(content).hexdigest() if content else None,
            checksum=hashlib.sha256(content).hexdigest() if content else None,
        )

    def download_bytes(self, *, object_path: str, max_bytes: Optional[int] = None) -> bytes:
        content = self._path(object_path).read_bytes()

        if max_bytes is not None and len(content) > max_bytes:
            raise ValueError("Object exceeds max_bytes.")

        return content

    def delete_object(self, *, object_path: str) -> None:
        path = self._path(object_path)

        if path.exists():
            path.unlink()

    def health_check(self):
        return StorageHealthResult(
            status="ready",
            provider=self.provider_name,
            bucket=self.bucket,
            detail="Local fixture storage is available.",
            can_connect=True,
            bucket_available=True,
        )

    def _path(self, object_path: str) -> Path:
        cleaned = object_path.replace("..", "").lstrip("/")
        return self.root / cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="../sustha_three_patient_evaluation_pack")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        result = import_pack(
            db,
            pack_path=Path(args.pack).resolve(),
            reset=args.reset,
            skip_sync=args.skip_sync,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0
    finally:
        db.close()


def import_pack(
    db: Session,
    *,
    pack_path: Path,
    reset: bool = False,
    skip_sync: bool = False,
    output_dir: Optional[Path] = None,
) -> dict:
    if not pack_path.exists():
        raise ValueError(f"Evaluation pack does not exist: {pack_path}")

    if reset:
        reset_database(db)

    manifest = read_json(pack_path / "manifest.json")
    validation = read_json(pack_path / "validation_report.json")
    validate_pack(pack_path=pack_path, manifest=manifest, validation=validation)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = output_dir or (pack_path.parent / DEFAULT_OUTPUT_ROOT / "sustha_three_patient_pilot" / run_id)
    output_root.mkdir(parents=True, exist_ok=True)

    doctor = ensure_doctor(db, pack_path=pack_path)
    patient_dirs = sorted((pack_path / "patients").iterdir())
    patients = {}
    encounter_maps = {}
    document_maps = {}
    storage = LocalFixtureStorageProvider(root=pack_path.parent / ".fixture_storage")

    for patient_dir in patient_dirs:
        if not patient_dir.is_dir():
            continue

        patient = ensure_patient(db, doctor=doctor, patient_data=read_json(patient_dir / "patient.json"))
        patients[patient.patient_code] = patient
        encounter_maps[patient.patient_code] = import_structured_information(
            db,
            doctor=doctor,
            patient=patient,
            structured=read_json(patient_dir / "structured_information.json"),
        )
        document_maps[patient.patient_code] = import_documents(
            db,
            doctor=doctor,
            patient=patient,
            patient_dir=patient_dir,
            encounter_map=encounter_maps[patient.patient_code],
            storage_provider=storage,
        )

    set_duplicate_document_relationships(db, pack_path=pack_path, document_maps=document_maps)

    for patient_dir in patient_dirs:
        if not patient_dir.is_dir():
            continue

        patient = patients[patient_dir.name]
        initialize_missing_system_instances(db=db, patient_id=patient.id)
        import_source_conversations(
            db,
            doctor=doctor,
            patient=patient,
            conversations=read_json(patient_dir / "source_conversations.json"),
        )

    sync_results = (
        skipped_sync_results(patients=patients.values())
        if skip_sync
        else synchronize_all_systems(db, doctor=doctor, patients=patients.values())
    )
    dataset = import_benchmark_dataset(db, pack_path=pack_path, manifest=manifest)
    audit = build_source_ingestion_audit(db, patients=patients.values())
    audit_path = output_root / "source_ingestion_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    return {
        "status": "imported",
        "run_id": run_id,
        "pack_path": str(pack_path),
        "output_dir": str(output_root),
        "doctor_id": str(doctor.id),
        "doctor_email": doctor.email,
        "dataset_id": str(dataset.id),
        "dataset_name": dataset.name,
        "counts": {
            "patients": len(patients),
            "documents": sum(len(value) for value in document_maps.values()),
            "structured_records": count_structured_records(db, patients.values()),
            "source_conversation_messages": sum(
                len(read_json(patient_dir / "source_conversations.json"))
                for patient_dir in patient_dirs
                if patient_dir.is_dir()
            ),
            "canonical_sources": audit["totals"]["canonical_sources"],
            "questions": count_dataset_questions(db, dataset.id),
        },
        "validation": validation,
        "sync": sync_results,
        "source_ingestion_audit": str(audit_path),
    }


def validate_pack(*, pack_path: Path, manifest: dict, validation: dict) -> None:
    expected = validation.get("counts", {})

    if expected.get("patients") != 3:
        raise ValueError("Pack validation does not report exactly three patients.")

    if expected.get("documents") != 18:
        raise ValueError("Pack validation does not report 18 documents.")

    for item in manifest.get("files", []):
        path = pack_path / item["path"]

        if not path.exists():
            raise ValueError(f"Missing pack file: {item['path']}")

        digest = hashlib.sha256(path.read_bytes()).hexdigest()

        if digest != item["sha256"]:
            raise ValueError(f"Checksum mismatch for {item['path']}")


def reset_database(db: Session) -> None:
    tables = [table for table in reversed(Base.metadata.sorted_tables)]
    names = [engine.dialect.identifier_preparer.format_table(table) for table in tables]
    db.execute(text("TRUNCATE TABLE " + ", ".join(names) + " RESTART IDENTITY CASCADE"))
    db.commit()


def ensure_doctor(db: Session, *, pack_path: Path) -> Doctor:
    registration = read_json(pack_path / "doctor" / "registration.json")
    email = registration["email"].strip().lower()
    doctor = db.scalar(select(Doctor).where(Doctor.email == email))

    if doctor is not None:
        return doctor

    doctor = Doctor(
        full_name=registration["name"],
        email=email,
        password_hash=hash_password(registration["suggested_test_password"]),
        specialization=registration.get("specialty"),
        organization_name=registration.get("organization"),
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def ensure_patient(db: Session, *, doctor: Doctor, patient_data: dict) -> Patient:
    patient = db.scalar(
        select(Patient).where(
            Patient.doctor_id == doctor.id,
            Patient.patient_code == patient_data["patient_code"],
        )
    )
    data = {
        "full_name": patient_data["full_name"],
        "date_of_birth": parse_date(patient_data.get("date_of_birth")),
        "sex": patient_data.get("sex"),
        "phone": patient_data.get("phone"),
        "email": patient_data.get("email"),
        "address": patient_data.get("address"),
        "emergency_contact_name": patient_data.get("emergency_contact_name"),
        "emergency_contact_phone": patient_data.get("emergency_contact_phone"),
        "is_active": True,
    }

    if patient is None:
        patient = Patient(
            doctor_id=doctor.id,
            patient_code=patient_data["patient_code"],
            **data,
        )
        db.add(patient)
    else:
        for field, value in data.items():
            setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    return patient


def import_structured_information(db: Session, *, doctor: Doctor, patient: Patient, structured: dict) -> dict[str, str]:
    encounter_map = {}

    for row in structured.get("encounters", []):
        encounter = db.scalar(
            select(ClinicalEncounter).where(
                ClinicalEncounter.patient_id == patient.id,
                ClinicalEncounter.location == source_marker(row["id"]),
            )
        )
        started_at = parse_datetime(row.get("effective_date"))
        added_at = parse_datetime(row.get("added_date")) or started_at

        if encounter is None:
            encounter = ClinicalEncounter(
                patient_id=patient.id,
                created_by_doctor_id=doctor.id,
                encounter_type=normalize_status(row.get("encounter_type"), "outpatient"),
                status=normalize_status(row.get("status"), "completed"),
                started_at=started_at,
                ended_at=None,
                chief_complaint=row.get("title"),
                summary=append_marker(row.get("description"), row["id"]),
                location=source_marker(row["id"]),
                is_active=True,
                created_at=added_at,
                updated_at=added_at,
            )
            db.add(encounter)
            db.flush()

        encounter_map[row["id"]] = encounter.id

    for row in structured.get("conditions", []):
        if exists_by_source(db, MedicalCondition, patient.id, row["id"]):
            continue
        db.add(
            MedicalCondition(
                patient_id=patient.id,
                created_by_doctor_id=doctor.id,
                name=row.get("condition_name") or row.get("name"),
                category="problem-list",
                clinical_status=normalize_status(row.get("clinical_status"), "active"),
                verification_status=normalize_status(row.get("verification_status"), "confirmed"),
                onset_date=parse_date(row.get("onset_date")),
                notes=append_marker(row.get("notes"), row["id"]),
                source_type=row.get("source") or "evaluation_pack",
                source_reference=row["id"],
                is_active=True,
                recorded_at=parse_datetime(row.get("added_date")),
                created_at=parse_datetime(row.get("added_date")),
                updated_at=parse_datetime(row.get("added_date")),
            )
        )

    for row in structured.get("medications", []):
        if exists_by_source(db, Medication, patient.id, row["id"]):
            continue
        dose_value, dose_unit = parse_dose(row.get("dose"))
        recorded_at = parse_datetime(row.get("added_date") or row.get("start_date"))
        db.add(
            Medication(
                patient_id=patient.id,
                created_by_doctor_id=doctor.id,
                medication_name=row.get("medication_name"),
                dosage_value=dose_value,
                dosage_unit=dose_unit,
                route=row.get("route"),
                frequency=row.get("frequency"),
                instructions=source_marker(row["id"]),
                reason=row.get("reason"),
                medication_status=normalize_status(row.get("status"), "active"),
                start_date=parse_date(row.get("start_date")),
                end_date=parse_date(row.get("end_date")),
                source_type=row.get("source") or "evaluation_pack",
                source_reference=row["id"],
                is_active=True,
                recorded_at=recorded_at,
                created_at=recorded_at,
                updated_at=recorded_at,
            )
        )

    for row in structured.get("allergies", []):
        if exists_by_source(db, Allergy, patient.id, row["id"]):
            continue
        recorded_at = parse_datetime(row.get("recorded_date"))
        db.add(
            Allergy(
                patient_id=patient.id,
                created_by_doctor_id=doctor.id,
                substance=row.get("allergen") or row.get("substance"),
                allergy_type="drug" if "drug" in (row.get("allergen") or "").lower() else "other",
                category="medication",
                clinical_status=normalize_status(row.get("status"), "active"),
                verification_status=normalize_status(row.get("verification_status"), "confirmed"),
                reaction=row.get("reaction"),
                severity=row.get("severity"),
                onset_date=parse_date(row.get("recorded_date")),
                notes=source_marker(row["id"]),
                source_type=row.get("source") or "evaluation_pack",
                source_reference=row["id"],
                is_active=True,
                recorded_at=recorded_at,
                created_at=recorded_at,
                updated_at=recorded_at,
            )
        )

    for row in structured.get("measurements", []):
        if exists_by_source(db, Measurement, patient.id, row["id"]):
            continue
        observed_at = parse_datetime(row.get("effective_date"))
        added_at = parse_datetime(row.get("added_date")) or observed_at
        value_numeric, value_text = parse_measurement_value(row.get("value"))
        db.add(
            Measurement(
                patient_id=patient.id,
                created_by_doctor_id=doctor.id,
                observation_name=row.get("measurement_type") or row.get("name"),
                value_numeric=value_numeric,
                value_text=value_text,
                unit=row.get("unit"),
                interpretation=row.get("interpretation"),
                status=normalize_status(row.get("status"), "final"),
                observed_at=observed_at,
                source_type=row.get("source") or "evaluation_pack",
                source_reference=row["id"],
                notes=append_marker(row.get("reference_range"), row["id"]),
                is_active=True,
                recorded_at=added_at,
                created_at=added_at,
                updated_at=added_at,
            )
        )

    for row in structured.get("clinical_notes", []):
        if exists_by_source(db, ClinicalNote, patient.id, row["id"]):
            continue
        authored_at = parse_datetime(row.get("effective_date"))
        added_at = parse_datetime(row.get("added_date")) or authored_at
        db.add(
            ClinicalNote(
                patient_id=patient.id,
                created_by_doctor_id=doctor.id,
                note_type="evaluation",
                title=row.get("title"),
                content=append_marker(row.get("full_note_text") or row.get("content"), row["id"]),
                status=normalize_status(row.get("status"), "final"),
                authored_at=authored_at,
                source_type=row.get("source") or "evaluation_pack",
                source_reference=row["id"],
                is_active=True,
                created_at=added_at,
                updated_at=added_at,
            )
        )

    db.commit()
    return {key: str(value) for key, value in encounter_map.items()}


def import_documents(
    db: Session,
    *,
    doctor: Doctor,
    patient: Patient,
    patient_dir: Path,
    encounter_map: dict[str, str],
    storage_provider: LocalFixtureStorageProvider,
) -> dict[str, str]:
    document_map = {}

    for row in read_json(patient_dir / "document_metadata.json"):
        existing = find_document_by_package_id(db, patient_id=patient.id, package_id=row["document_id"])

        if existing is None:
            pdf_path = patient_dir / "documents" / row["filename"]
            response = direct_upload_document(
                db=db,
                doctor=doctor,
                patient_id=patient.id,
                original_filename=row["filename"],
                content_type="application/pdf",
                content=pdf_path.read_bytes(),
                document_type=map_document_type(row.get("document_type")),
                title=row.get("title"),
                description=document_description(row),
                document_date=parse_date(row.get("document_date")),
                encounter_id=encounter_map.get(row.get("encounter_id")),
                storage_provider=storage_provider,
            )
            document = db.scalar(select(Document).where(Document.id == response.document.id))
            apply_document_pack_metadata(db, document=document, row=row)
        else:
            document = existing

        document_map[row["document_id"]] = str(document.id)

    db.commit()
    return document_map


def import_source_conversations(db: Session, *, doctor: Doctor, patient: Patient, conversations: list[dict]) -> None:
    for system_type in SYSTEM_TYPES:
        instance = memory_repository.get_instance(db=db, patient_id=patient.id, system_type=system_type)
        existing = db.scalar(
            select(memory_repository.MemoryConversation).where(
                memory_repository.MemoryConversation.patient_id == patient.id,
                memory_repository.MemoryConversation.system_instance_id == instance.id,
                memory_repository.MemoryConversation.title == "Sustha evaluation source conversation",
            )
        )
        conversation = existing or memory_repository.create_conversation(
            db=db,
            data={
                "patient_id": patient.id,
                "doctor_id": doctor.id,
                "system_instance_id": instance.id,
                "system_type": system_type,
                "title": "Sustha evaluation source conversation",
                "status": "active",
                "last_message_at": None,
            },
        )

        for row in conversations:
            event_time = parse_datetime(row["timestamp"])
            content = append_marker(row["text"], row["message_id"])
            role = "assistant" if row.get("speaker") == "assistant" else "user"
            exists = db.scalar(
                select(memory_repository.MemoryMessage).where(
                    memory_repository.MemoryMessage.conversation_id == conversation.id,
                    memory_repository.MemoryMessage.event_time == event_time,
                    memory_repository.MemoryMessage.content == content,
                )
            )

            if exists is not None:
                continue

            memory_repository.create_message(
                db=db,
                conversation=conversation,
                data={
                    "role": role,
                    "content": content,
                    "event_time": event_time,
                    "token_count": max(1, (len(content) + 3) // 4),
                    "generation_status": "evaluation_source",
                    "retrieval_run_id": None,
                },
            )

    db.commit()


def synchronize_all_systems(db: Session, *, doctor: Doctor, patients) -> list[dict]:
    results = []

    for patient in patients:
        cutoff = datetime(2100, 1, 1, tzinfo=timezone.utc)

        for system_type in SYSTEM_TYPES:
            try:
                response = sync_system(
                    db=db,
                    doctor=doctor,
                    patient_id=patient.id,
                    system_type=system_type,
                    request=MemorySyncRequest(
                        cutoff_time=cutoff,
                        mode="evaluation_import",
                        include_patient_information=True,
                        include_documents=True,
                        include_conversation=True,
                    ),
                )
                results.append(
                    {
                        "patient_code": patient.patient_code,
                        "system_type": system_type,
                        "status": response.status,
                        "source_count": response.source_count,
                        "processed_count": response.processed_count,
                        "failed_count": response.failed_count,
                        "pipeline_version": response.pipeline_version,
                    }
                )
            except Exception as error:
                results.append(
                    {
                        "patient_code": patient.patient_code,
                        "system_type": system_type,
                        "status": "failed",
                        "source_count": None,
                        "processed_count": None,
                        "failed_count": None,
                        "pipeline_version": None,
                        "failure_code": error.__class__.__name__,
                        "failure_reason": str(error)[:500],
                    }
                )

    return results


def skipped_sync_results(*, patients) -> list[dict]:
    return [
        {
            "patient_code": patient.patient_code,
            "system_type": system_type,
            "status": "skipped",
            "source_count": None,
            "processed_count": None,
            "failed_count": None,
            "pipeline_version": None,
        }
        for patient in patients
        for system_type in SYSTEM_TYPES
    ]


def import_benchmark_dataset(db: Session, *, pack_path: Path, manifest: dict) -> BenchmarkDataset:
    dataset_info = read_json(pack_path / "benchmark" / "dataset.json")
    version = dataset_info.get("version") or "1.0"
    dataset = db.scalar(
        select(BenchmarkDataset).where(
            BenchmarkDataset.name == DATASET_NAME,
            BenchmarkDataset.version == version,
            BenchmarkDataset.split == DATASET_SPLIT,
        )
    )

    if dataset is None:
        dataset = BenchmarkDataset(
            name=DATASET_NAME,
            version=version,
            split=DATASET_SPLIT,
            description=json.dumps(
                {
                    "synthetic": True,
                    "dataset_id": dataset_info.get("dataset_id"),
                    "fixture_manifest": manifest.get("dataset_version"),
                    "declaration": dataset_info.get("disclaimer"),
                },
                sort_keys=True,
            ),
            case_count=3,
            checksum=hashlib.sha256(json.dumps(dataset_info, sort_keys=True).encode("utf-8")).hexdigest(),
            status="validated",
        )
        db.add(dataset)
        db.flush()

    events = read_json(pack_path / "benchmark" / "events.json")
    questions_payload = read_json(pack_path / "benchmark" / "questions.json")
    questions = questions_payload.get("questions", questions_payload) if isinstance(questions_payload, dict) else questions_payload
    questions_by_patient = group_by(questions, "patient_code")
    events_by_patient = group_by(events, "patient_code")

    for patient_code in dataset_info["patient_codes"]:
        case = db.scalar(
            select(BenchmarkCase).where(
                BenchmarkCase.dataset_id == dataset.id,
                BenchmarkCase.case_key == patient_code,
            )
        )

        if case is None:
            case = BenchmarkCase(
                dataset_id=dataset.id,
                case_key=patient_code,
                scenario_family="three_patient_pilot",
                seed=abs(hash(patient_code)) % 100000,
                manifest={
                    "patient_code": patient_code,
                    "source": "sustha_three_patient_evaluation_pack",
                    "question_count": len(questions_by_patient.get(patient_code, [])),
                },
            )
            db.add(case)
            db.flush()

        for index, event in enumerate(events_by_patient.get(patient_code, []), start=1):
            exists = db.scalar(
                select(BenchmarkEvent).where(
                    BenchmarkEvent.case_id == case.id,
                    BenchmarkEvent.sequence_number == index,
                )
            )

            if exists is None:
                db.add(
                    BenchmarkEvent(
                        case_id=case.id,
                        sequence_number=index,
                        event_type=event.get("event_type", "pack_event"),
                        valid_time=parse_datetime(event.get("effective_date")),
                        ingestion_time=parse_datetime(event.get("added_date")),
                        payload=event,
                        source_fixture=event.get("source_id") or event.get("event_id"),
                    )
                )

        for index, question in enumerate(questions_by_patient.get(patient_code, []), start=1):
            benchmark_question = db.scalar(
                select(BenchmarkQuestion).where(
                    BenchmarkQuestion.case_id == case.id,
                    BenchmarkQuestion.turn_number == index,
                )
            )

            if benchmark_question is None:
                benchmark_question = BenchmarkQuestion(
                    case_id=case.id,
                    turn_number=index,
                    question=question["question_text"],
                    question_type=(question.get("question_category") or "evaluation")[:80],
                    expected_decision_type=question.get("expected_decision_label"),
                    source_cutoff=parse_datetime(question["source_cutoff"]),
                )
                db.add(benchmark_question)
                db.flush()

            if db.scalar(select(BenchmarkGroundTruth).where(BenchmarkGroundTruth.question_id == benchmark_question.id)) is None:
                db.add(
                    BenchmarkGroundTruth(
                        question_id=benchmark_question.id,
                        truth=build_truth_payload(question),
                        version=version,
                        reviewer_status="synthetic_validated",
                    )
                )

    db.commit()
    db.refresh(dataset)
    return dataset


def build_truth_payload(question: dict) -> dict:
    relevant = question.get("expected_relevant_source_ids") or []
    claims = []

    for index, claim in enumerate(question.get("required_claims") or [], start=1):
        claims.append(
            {
                "claim_id": f"{question['question_id']}-required-{index}",
                "claim_text": claim,
                "subject": claim,
                "predicate": "claim",
                "value": claim,
                "status": "required",
                "supporting_source_ids": relevant,
            }
        )

    return {
        "question_id": question["question_id"],
        "answer_summary": question.get("expected_answer"),
        "claims": claims,
        "required_claims": question.get("required_claims") or [],
        "acceptable_claims": question.get("acceptable_claims") or [],
        "forbidden_claims": question.get("forbidden_claims") or [],
        "relevant_source_ids": relevant,
        "expected_citations": relevant,
        "decision_labels": [question["expected_decision_label"]] if question.get("expected_decision_label") else [],
        "temporal_assertions": question.get("expected_temporal_assertions") or [],
        "contradictions": question.get("expected_conflicts") or [],
        "correction_expectations": question.get("expected_corrections") or [],
        "expected_state_transitions": state_transition_labels(question.get("expected_state") or {}),
        "expected_state": question.get("expected_state") or {},
        "retrieval_ground_truth": question.get("retrieval_ground_truth") or {},
        "applicable_metrics": question.get("applicable_metrics") or [],
        "insufficient_evidence_expected": bool(question.get("insufficient_evidence_expected")),
        "requires_exact_quote": bool(question.get("requires_exact_quote")),
        "rare_detail_query": bool(question.get("rare_detail_query")),
    }


def build_source_ingestion_audit(db: Session, *, patients) -> dict:
    rows = []
    totals = {"canonical_sources": 0}

    for patient in patients:
        sources = list(
            db.scalars(
                select(CanonicalMemorySource)
                .where(CanonicalMemorySource.patient_id == patient.id)
                .order_by(CanonicalMemorySource.source_type.asc(), CanonicalMemorySource.source_subtype.asc())
            ).all()
        )
        totals["canonical_sources"] += len(sources)
        by_type = {}
        by_subtype = {}

        for source in sources:
            by_type[source.source_type] = by_type.get(source.source_type, 0) + 1
            key = f"{source.source_type}:{source.source_subtype}"
            by_subtype[key] = by_subtype.get(key, 0) + 1

        rows.append(
            {
                "patient_code": patient.patient_code,
                "patient_id": str(patient.id),
                "canonical_source_count": len(sources),
                "counts_by_source_type": by_type,
                "counts_by_source_subtype": by_subtype,
                "effective_dates": sorted({source.valid_time.isoformat() for source in sources if source.valid_time}),
                "ingestion_dates": sorted({source.recorded_time.isoformat() for source in sources if source.recorded_time}),
                "document_count": int(db.scalar(select(func.count()).select_from(Document).where(Document.patient_id == patient.id)) or 0),
            }
        )

    return {"patients": rows, "totals": totals}


def set_duplicate_document_relationships(db: Session, *, pack_path: Path, document_maps: dict[str, dict[str, str]]) -> None:
    for patient_dir in sorted((pack_path / "patients").iterdir()):
        if not patient_dir.is_dir():
            continue
        family_first = {}

        for row in read_json(patient_dir / "document_metadata.json"):
            family = row.get("duplicate_family_id")

            if not family:
                continue

            document_id = document_maps[patient_dir.name].get(row["document_id"])
            document = db.scalar(select(Document).where(Document.id == document_id))

            if family not in family_first:
                family_first[family] = document.id
            elif document.duplicate_of_document_id is None:
                document.duplicate_of_document_id = family_first[family]

    db.commit()


def apply_document_pack_metadata(db: Session, *, document: Document, row: dict) -> None:
    upload_at = datetime.combine(parse_date(row.get("upload_date")), time(hour=12), tzinfo=timezone.utc)
    document.description = document_description(row)
    document.uploaded_at = upload_at
    document.verified_at = upload_at
    document.created_at = upload_at
    document.updated_at = upload_at

    if document.processing_started_at:
        document.processing_started_at = upload_at

    if document.processing_completed_at:
        document.processing_completed_at = upload_at

    db.flush()


def find_document_by_package_id(db: Session, *, patient_id, package_id: str) -> Optional[Document]:
    return db.scalar(
        select(Document).where(
            Document.patient_id == patient_id,
            Document.description.contains(source_marker(package_id)),
        )
    )


def exists_by_source(db: Session, model, patient_id, source_id: str) -> bool:
    return db.scalar(
        select(model.id).where(
            model.patient_id == patient_id,
            model.source_reference == source_id,
        )
    ) is not None


def count_structured_records(db: Session, patients) -> int:
    patient_ids = [patient.id for patient in patients]
    return sum(
        int(db.scalar(select(func.count()).select_from(model).where(model.patient_id.in_(patient_ids))) or 0)
        for model in (ClinicalEncounter, MedicalCondition, Medication, Allergy, Measurement, ClinicalNote)
    )


def count_dataset_questions(db: Session, dataset_id) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(BenchmarkQuestion)
            .join(BenchmarkCase, BenchmarkQuestion.case_id == BenchmarkCase.id)
            .where(BenchmarkCase.dataset_id == dataset_id)
        )
        or 0
    )


def group_by(rows: list[dict], key: str) -> dict:
    grouped = {}

    for row in rows:
        grouped.setdefault(row[key], []).append(row)

    return grouped


def state_transition_labels(state: dict) -> list[str]:
    labels = []

    for key, value in state.items():
        if isinstance(value, list):
            labels.extend(f"{key}:{item}" for item in value)
        else:
            labels.append(f"{key}:{value}")

    return labels


def document_description(row: dict) -> str:
    parts = [
        source_marker(row["document_id"]),
        f"Evidence IDs: {', '.join(row.get('evidence_ids') or [])}",
        f"Duplicate family: {row.get('duplicate_family_id')}" if row.get("duplicate_family_id") else None,
        f"Author/source: {row.get('author_source')}" if row.get("author_source") else None,
    ]
    return ". ".join(part for part in parts if part)


def map_document_type(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()

    if "lab" in normalized:
        return "lab_report"

    if "medication" in normalized or "prescription" in normalized or "treatment" in normalized:
        return "prescription"

    if "hospital" in normalized or "discharge" in normalized or "summary" in normalized:
        return "discharge_summary"

    if "clinic" in normalized or "clinical" in normalized or "note" in normalized or "letter" in normalized:
        return "consultation_note"

    return "other"


def append_marker(text_value: Optional[str], source_id: str) -> str:
    base = (text_value or "").strip()
    marker = source_marker(source_id)
    return f"{base}. {marker}" if base else marker


def source_marker(source_id: str) -> str:
    return f"{SOURCE_MARKER_PREFIX} {source_id}"


def parse_dose(value: Optional[str]) -> tuple[Optional[Decimal], Optional[str]]:
    if not value:
        return None, None

    match = re.match(r"^\s*([0-9.]+)\s*(.*)$", value)

    if not match:
        return None, value

    return Decimal(match.group(1)), match.group(2).strip() or None


def parse_measurement_value(value) -> tuple[Optional[Decimal], Optional[str]]:
    if value is None:
        return None, None

    try:
        return Decimal(str(value)), None
    except Exception:
        return None, str(value)


def parse_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    if "T" not in value:
        parsed = datetime.combine(date.fromisoformat(value), time.min)
    else:
        parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None

    if "T" in value:
        return datetime.fromisoformat(value).date()

    return date.fromisoformat(value)


def normalize_status(value: Optional[str], default: str) -> str:
    return (value or default).strip().lower().replace(" ", "_")[:40]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
