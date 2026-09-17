from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import delete, or_, select

from app.database import Base, SessionLocal, init_db
from app.document.models import Document, DocumentArtifact
from app.doctor.model import Doctor
from app.main import app
from app.memory_systems.common.models.memory import (
    CanonicalMemorySource,
    MemoryConversation,
    MemoryIngestionRun,
    MemoryRetrievalRun,
    MemorySystemInstance,
)
from app.patient.model import Patient
from app.patient_information.models import ClinicalEncounter
from app.storage.dependencies import get_storage_provider


class SmokeFailure(Exception):
    pass


def main() -> int:
    init_db()
    marker = f"sustha-smoke-{int(time.time())}-{uuid4().hex[:8]}"
    email = f"{marker}@susthahealth.dev"
    password = "SmokePass123!"
    results = {}
    context = {"marker": marker, "email": email}

    cleanup_stale_smoke_data()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            auth = smoke_auth(client, email, password)
            headers = {"Authorization": f"Bearer {auth['access_token']}"}
            doctor_id = auth["doctor"]["id"]
            context["doctor_id"] = doctor_id
            results["doctor"] = {
                "registered": True,
                "login": True,
                "doctor_id": doctor_id,
            }

            patient = smoke_patient(client, headers, marker)
            patient_id = patient["id"]
            context["patient_id"] = patient_id
            results["patient"] = {
                "created": True,
                "patient_id": patient_id,
                "patient_code": patient["patient_code"],
            }
            results["auto_initialized_memory_systems"] = smoke_auto_initialized_memory_systems(
                client,
                headers,
                patient_id,
            )

            results["patient_information"] = smoke_patient_information(client, headers, patient_id)
            document = smoke_document(client, headers, patient_id)
            context["document_id"] = document["document_id"]
            results["document"] = document
            results["llm_status"] = request_json(client, "GET", "/api/llm/status", headers=headers)
            results["memory_systems"] = smoke_memory_systems(client, headers, patient_id)
            results["query_llm"] = smoke_query_llm(client, headers, patient_id)

    except Exception as error:
        cleanup_result = cleanup_smoke_data(context)
        print_json(
            {
                "status": "failed",
                "error": str(error),
                "partial_results": results,
                "cleanup": cleanup_result,
            },
        )
        return 1

    cleanup_result = cleanup_smoke_data(context)
    verification = verify_cleanup(context)
    results["cleanup"] = cleanup_result
    results["cleanup_verification"] = verification
    print_json({"status": "passed", "results": results})
    return 0


def smoke_auth(client: TestClient, email: str, password: str) -> dict:
    register_payload = {
        "full_name": "Sustha Smoke Doctor",
        "email": email,
        "password": password,
        "specialization": "Internal Medicine",
        "medical_license_number": f"SMOKE-{uuid4().hex[:12]}",
        "organization_name": "Sustha Smoke Test",
    }
    assert_response(client.post("/api/doctors/register", json=register_payload), "doctor register", {201})
    login = assert_response(
        client.post("/api/doctors/login", json={"email": email, "password": password}),
        "doctor login",
    )
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert_response(client.get("/api/doctors/me", headers=headers), "doctor me")
    return login


def smoke_patient(client: TestClient, headers: dict, marker: str) -> dict:
    patient_code = f"SMOKE-{marker[-8:].upper()}"
    payload = {
        "patient_code": patient_code,
        "full_name": "Sustha Smoke Patient",
        "date_of_birth": "1980-04-12",
        "sex": "female",
        "phone": "+1-555-0100",
        "email": f"patient-{marker}@susthahealth.dev",
        "address": "Temporary smoke test record",
        "emergency_contact_name": "Smoke Contact",
        "emergency_contact_phone": "+1-555-0101",
    }
    patient = assert_response(client.post("/api/patients", headers=headers, json=payload), "patient create", {201})
    assert_response(client.get(f"/api/patients/{patient['id']}", headers=headers), "patient get")
    list_result = assert_response(client.get("/api/patients?page=1&page_size=20", headers=headers), "patient list")

    if not any(item["id"] == patient["id"] for item in list_result["items"]):
        raise SmokeFailure("patient list did not include the smoke patient")

    return patient


def smoke_auto_initialized_memory_systems(client: TestClient, headers: dict, patient_id: str) -> dict:
    system_type = "dense_rag"
    systems = assert_response(
        client.get(f"/api/patients/{patient_id}/memory-systems", headers=headers),
        "auto-initialized patient memory systems",
    )
    systems = assert_response(
        client.post(f"/api/patients/{patient_id}/memory-systems/initialize-all", headers=headers),
        "initialize all memory systems",
    )
    statistics = assert_response(
        client.get(f"/api/patients/{patient_id}/memory-systems/{system_type}/statistics", headers=headers),
        "auto-initialized dense_rag statistics",
    )
    conversations = assert_response(
        client.get(f"/api/patients/{patient_id}/memory-systems/{system_type}/conversations", headers=headers),
        "auto-initialized dense_rag conversations",
    )
    runs = assert_response(
        client.get(f"/api/patients/{patient_id}/memory-systems/{system_type}/runs", headers=headers),
        "auto-initialized dense_rag runs",
    )
    missing_instances = [system["system_type"] for system in systems if not system.get("id")]
    not_initialized = [
        system["system_type"]
        for system in systems
        if system.get("status") == "not_initialized"
    ]

    if missing_instances:
        raise SmokeFailure(f"memory systems missing instances: {missing_instances}")

    if not_initialized:
        raise SmokeFailure(f"memory systems were not initialized: {not_initialized}")

    if statistics["status"] == "not_initialized":
        raise SmokeFailure("dense_rag statistics still reported not_initialized")

    if conversations:
        raise SmokeFailure("new dense_rag conversations should be empty")

    if runs:
        raise SmokeFailure("new dense_rag runs should be empty")

    return {
        "system_count": len(systems),
        "missing_instances": len(missing_instances),
        "not_initialized": len(not_initialized),
        "statistics_status": statistics["status"],
        "conversations": len(conversations),
        "runs": len(runs),
    }


def smoke_patient_information(client: TestClient, headers: dict, patient_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    encounter = assert_response(
        client.post(
            f"/api/patients/{patient_id}/encounters",
            headers=headers,
            json={
                "encounter_type": "outpatient",
                "status": "completed",
                "started_at": now,
                "chief_complaint": "Diabetes follow-up",
                "summary": "Patient has type 2 diabetes with A1c 6.8 and metformin plan.",
                "location": "Smoke Clinic",
            },
        ),
        "encounter create",
        {201},
    )
    encounter_id = encounter["id"]
    created = {
        "encounters": encounter_id,
        "conditions": post_record(
            client,
            headers,
            patient_id,
            "conditions",
            {
                "encounter_id": encounter_id,
                "name": "Type 2 diabetes mellitus",
                "clinical_status": "active",
                "verification_status": "confirmed",
                "severity": "moderate",
                "notes": "A1c improved to 6.8.",
            },
        ),
        "medications": post_record(
            client,
            headers,
            patient_id,
            "medications",
            {
                "encounter_id": encounter_id,
                "medication_name": "Metformin",
                "dosage_value": "500",
                "dosage_unit": "mg",
                "frequency": "twice daily",
                "reason": "Type 2 diabetes",
                "medication_status": "active",
            },
        ),
        "allergies": post_record(
            client,
            headers,
            patient_id,
            "allergies",
            {
                "encounter_id": encounter_id,
                "substance": "Penicillin",
                "clinical_status": "active",
                "verification_status": "confirmed",
                "reaction": "Rash",
                "severity": "mild",
            },
        ),
        "measurements": post_record(
            client,
            headers,
            patient_id,
            "measurements",
            {
                "encounter_id": encounter_id,
                "observation_name": "Hemoglobin A1c",
                "value_numeric": "6.8",
                "unit": "%",
                "status": "final",
                "observed_at": now,
                "notes": "Smoke test A1c result.",
            },
        ),
        "notes": post_record(
            client,
            headers,
            patient_id,
            "notes",
            {
                "encounter_id": encounter_id,
                "note_type": "progress",
                "title": "Diabetes follow-up note",
                "content": "A1c is 6.8. Continue metformin 500 mg twice daily. Avoid penicillin due to rash.",
                "status": "final",
                "authored_at": now,
            },
        ),
    }

    totals = {}

    for record_type in ["encounters", "conditions", "medications", "allergies", "measurements", "notes"]:
        list_result = assert_response(
            client.get(f"/api/patients/{patient_id}/{record_type}", headers=headers),
            f"{record_type} list",
        )
        totals[record_type] = list_result["total"]

        if totals[record_type] < 1:
            raise SmokeFailure(f"{record_type} list returned no records")

    return {"created": created, "totals": totals}


def post_record(client: TestClient, headers: dict, patient_id: str, record_type: str, payload: dict) -> str:
    result = assert_response(
        client.post(f"/api/patients/{patient_id}/{record_type}", headers=headers, json=payload),
        f"{record_type} create",
        {201},
    )
    return result["id"]


def smoke_document(client: TestClient, headers: dict, patient_id: str) -> dict:
    content = (
        "Discharge summary for type 2 diabetes. Hemoglobin A1c is 6.8 percent. "
        "Continue metformin 500 mg twice daily. Penicillin allergy causes rash."
    ).encode("utf-8")
    upload = assert_response(
        client.post(
            f"/api/patients/{patient_id}/documents/upload/direct",
            headers=headers,
            data={
                "document_type": "consultation_note",
                "title": "Smoke diabetes note",
                "description": "Temporary smoke test document",
                "document_date": "2026-07-20",
            },
            files={"file": ("smoke-diabetes-note.txt", content, "text/plain")},
        ),
        "document direct upload",
        {201},
    )
    document = upload["document"]
    document_id = document["id"]
    detail = assert_response(client.get(f"/api/patients/{patient_id}/documents/{document_id}", headers=headers), "document detail")
    processing = assert_response(client.get(f"/api/patients/{patient_id}/documents/{document_id}/processing", headers=headers), "document processing")
    text = assert_response(client.get(f"/api/patients/{patient_id}/documents/{document_id}/text", headers=headers), "document text")
    pages = assert_response(client.get(f"/api/patients/{patient_id}/documents/{document_id}/pages", headers=headers), "document pages")
    sections = assert_response(client.get(f"/api/patients/{patient_id}/documents/{document_id}/sections", headers=headers), "document sections")
    artifacts = assert_response(client.get(f"/api/patients/{patient_id}/documents/{document_id}/artifacts", headers=headers), "document artifacts")
    view_url = assert_response(client.post(f"/api/patients/{patient_id}/documents/{document_id}/view-url", headers=headers), "document view-url")
    download_url = assert_response(client.post(f"/api/patients/{patient_id}/documents/{document_id}/download-url", headers=headers), "document download-url")
    document_list = assert_response(client.get(f"/api/patients/{patient_id}/documents", headers=headers), "document list")
    reconcile = assert_response(client.get(f"/api/patients/{patient_id}/documents/reconcile", headers=headers), "document reconcile")

    if not text or "metformin" not in (text.get("normalized_text") or "").lower():
        raise SmokeFailure("document text did not contain expected extracted content")

    if not pages:
        raise SmokeFailure("document pages endpoint returned no pages")

    return {
        "document_id": document_id,
        "detail_status": detail["processing_status"],
        "text_words": text["word_count"] if text else 0,
        "pages": len(pages),
        "sections": len(sections),
        "artifacts": len(artifacts),
        "jobs": len(processing["jobs"]),
        "list_total": document_list["total"],
        "reconciliation_issues": reconcile["total"],
        "view_url_created": bool(view_url.get("signed_url")),
        "download_url_created": bool(download_url.get("signed_url")),
    }


def smoke_memory_systems(client: TestClient, headers: dict, patient_id: str) -> dict:
    registry = assert_response(client.get("/api/memory-systems", headers=headers), "memory registry")
    assert_response(client.get(f"/api/patients/{patient_id}/memory-systems", headers=headers), "patient memory systems")
    systems = [item["system_type"] for item in registry]
    expected = {
        "long_context",
        "rolling_summary",
        "dense_rag",
        "hybrid_rag",
        "graph_rag",
        "hippo_rag",
        "csm",
    }

    if set(systems) != expected:
        raise SmokeFailure(f"memory registry mismatch: {systems}")

    results = {}

    for system_type in systems:
        assert_response(
            client.post(f"/api/patients/{patient_id}/memory-systems/{system_type}/initialize", headers=headers),
            f"{system_type} initialize",
        )
        sync = assert_response(
            client.post(
                f"/api/patients/{patient_id}/memory-systems/{system_type}/sync",
                headers=headers,
                json={
                    "include_patient_information": True,
                    "include_documents": True,
                    "include_conversation": False,
                    "mode": "full",
                },
            ),
            f"{system_type} sync",
        )
        status = assert_response(
            client.get(f"/api/patients/{patient_id}/memory-systems/{system_type}/status", headers=headers),
            f"{system_type} status",
        )
        statistics = assert_response(
            client.get(f"/api/patients/{patient_id}/memory-systems/{system_type}/statistics", headers=headers),
            f"{system_type} statistics",
        )
        runs = assert_response(
            client.get(f"/api/patients/{patient_id}/memory-systems/{system_type}/runs", headers=headers),
            f"{system_type} runs",
        )
        retrieval = assert_response(
            client.post(
                f"/api/patients/{patient_id}/memory-systems/{system_type}/retrieve",
                headers=headers,
                json={
                    "query": "What is the patient's A1c and medication plan?",
                    "top_k": 6,
                    "token_budget": 4000,
                    "include_content": True,
                    "include_citations": True,
                },
            ),
            f"{system_type} retrieve",
        )
        results[system_type] = {
            "status": status["status"],
            "sync_status": sync["status"],
            "sync_processed": sync["processed_count"],
            "run_count": len(runs),
            "statistics_status": statistics["status"],
            "source_counts": statistics["source_counts"],
            "storage": statistics["storage"],
            "capability_status": statistics["capability_status"],
            "retrieval_readiness": retrieval["readiness_status"],
            "retrieval_context_count": len(retrieval["context_items"]),
            "retrieval_tokens": retrieval["token_count"],
            "generation_status": retrieval["generation_status"],
        }

        if retrieval["readiness_status"] not in {"ready", "degraded", "requires_llm"}:
            raise SmokeFailure(f"{system_type} retrieval is not ready: {retrieval['readiness_status']}")

    return results


def smoke_query_llm(client: TestClient, headers: dict, patient_id: str) -> dict:
    system_type = "dense_rag"
    conversation = assert_response(
        client.post(
            f"/api/patients/{patient_id}/memory-systems/{system_type}/conversations",
            headers=headers,
            json={"title": "Smoke LLM conversation"},
        ),
        "conversation create",
    )
    response = assert_response(
        client.post(
            f"/api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation['id']}/messages",
            headers=headers,
            json={"content": "Summarize the A1c result, medication plan, and allergy."},
        ),
        "conversation post message",
    )
    messages = assert_response(
        client.get(
            f"/api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation['id']}/messages",
            headers=headers,
        ),
        "conversation messages",
    )

    if response["generation_status"] != "completed":
        raise SmokeFailure(f"LLM generation did not complete: {response['generation_status']} {response.get('warnings')}")

    return {
        "system_type": system_type,
        "conversation_id": conversation["id"],
        "message_count": len(messages),
        "generation_status": response["generation_status"],
        "assistant_message_created": response["assistant_message"] is not None,
        "model": response["model"],
        "input_tokens": response["input_tokens"],
        "output_tokens": response["output_tokens"],
        "total_tokens": response["total_tokens"],
        "latency_ms": response["latency_ms"],
        "retrieval_context_count": len(response["retrieval"]["context_items"]),
        "answer_uncertainty": response["answer"]["uncertainty"] if response["answer"] else None,
        "citation_count": len(response["answer"]["citations"]) if response["answer"] else 0,
    }


def request_json(client: TestClient, method: str, path: str, **kwargs) -> dict:
    response = client.request(method, path, **kwargs)
    return assert_response(response, path)


def assert_response(response, label: str, expected_statuses: Optional[set[int]] = None):
    expected = expected_statuses or {200}

    if response.status_code not in expected:
        raise SmokeFailure(f"{label} returned HTTP {response.status_code}: {short_body(response)}")

    if response.status_code == 204:
        return None

    try:
        return response.json()
    except Exception as error:
        raise SmokeFailure(f"{label} did not return JSON") from error


def short_body(response) -> str:
    text = response.text or ""
    return text[:600]


def cleanup_stale_smoke_data() -> None:
    db = SessionLocal()

    try:
        doctors = db.execute(
            select(Doctor).where(Doctor.email.like("sustha-smoke-%@susthahealth.dev"))
        ).scalars().all()

        for doctor in doctors:
            patients = db.execute(select(Patient).where(Patient.doctor_id == doctor.id)).scalars().all()

            for patient in patients:
                cleanup_storage_objects(db, patient_id=patient.id)
                cleanup_database_rows(db, patient_id=patient.id, doctor_id=doctor.id, email=doctor.email)

        db.commit()
    finally:
        db.close()


def cleanup_smoke_data(context: dict) -> dict:
    db = SessionLocal()
    storage_cleanup = {}
    database_cleanup = {}

    try:
        doctor_id = context.get("doctor_id")
        patient_id = context.get("patient_id")
        email = context.get("email")

        if patient_id:
            storage_cleanup = cleanup_storage_objects(db, patient_id=patient_id)
            database_cleanup = cleanup_database_rows(
                db,
                patient_id=patient_id,
                doctor_id=doctor_id,
                email=email,
            )
        elif email:
            doctor = db.execute(select(Doctor).where(Doctor.email == email)).scalar_one_or_none()

            if doctor:
                database_cleanup = cleanup_database_rows(db, patient_id=None, doctor_id=doctor.id, email=email)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {"storage": storage_cleanup, "database": database_cleanup}


def cleanup_storage_objects(db, *, patient_id) -> dict:
    paths = []
    documents = db.execute(select(Document).where(Document.patient_id == patient_id)).scalars().all()

    for document in documents:
        paths.append(document.storage_object_path)
        artifacts = db.execute(
            select(DocumentArtifact).where(DocumentArtifact.document_id == document.id)
        ).scalars().all()
        paths.extend(artifact.storage_object_path for artifact in artifacts)

    deleted = 0
    failed = []

    if not paths:
        return {"deleted": deleted, "failed": failed}

    provider = get_storage_provider()

    for path in sorted(set(paths)):
        try:
            provider.delete_object(object_path=path)
            deleted += 1
        except Exception as error:
            failed.append({"object_path": path, "error": str(error)})

    return {"deleted": deleted, "failed": failed}


def cleanup_database_rows(db, *, patient_id, doctor_id, email) -> dict:
    ids = collect_related_ids(db, patient_id=patient_id, doctor_id=doctor_id)
    deleted_by_table = {}

    for table in reversed(Base.metadata.sorted_tables):
        conditions = []

        if patient_id and "patient_id" in table.c:
            conditions.append(table.c.patient_id == patient_id)

        if doctor_id and "doctor_id" in table.c:
            conditions.append(table.c.doctor_id == doctor_id)

        if doctor_id and "created_by_doctor_id" in table.c:
            conditions.append(table.c.created_by_doctor_id == doctor_id)

        if doctor_id and "uploaded_by_doctor_id" in table.c:
            conditions.append(table.c.uploaded_by_doctor_id == doctor_id)

        if ids["system_instance_ids"] and "system_instance_id" in table.c:
            conditions.append(table.c.system_instance_id.in_(ids["system_instance_ids"]))

        if ids["canonical_source_ids"] and "canonical_source_id" in table.c:
            conditions.append(table.c.canonical_source_id.in_(ids["canonical_source_ids"]))

        if ids["conversation_ids"] and "conversation_id" in table.c:
            conditions.append(table.c.conversation_id.in_(ids["conversation_ids"]))

        if ids["retrieval_run_ids"] and "retrieval_run_id" in table.c:
            conditions.append(table.c.retrieval_run_id.in_(ids["retrieval_run_ids"]))

        if ids["ingestion_run_ids"] and "run_id" in table.c:
            conditions.append(table.c.run_id.in_(ids["ingestion_run_ids"]))

        if ids["document_ids"] and "document_id" in table.c:
            conditions.append(table.c.document_id.in_(ids["document_ids"]))

        if ids["encounter_ids"] and "encounter_id" in table.c:
            conditions.append(table.c.encounter_id.in_(ids["encounter_ids"]))

        if email and table.name == "doctors" and "email" in table.c:
            conditions.append(table.c.email == email)

        if not conditions:
            continue

        result = db.execute(delete(table).where(or_(*conditions)))

        if result.rowcount:
            deleted_by_table[table.name] = result.rowcount

    return deleted_by_table


def collect_related_ids(db, *, patient_id, doctor_id) -> dict:
    system_instance_ids = []
    canonical_source_ids = []
    conversation_ids = []
    retrieval_run_ids = []
    ingestion_run_ids = []
    document_ids = []
    encounter_ids = []

    if patient_id:
        system_instance_ids = list(
            db.execute(select(MemorySystemInstance.id).where(MemorySystemInstance.patient_id == patient_id)).scalars()
        )
        canonical_source_ids = list(
            db.execute(select(CanonicalMemorySource.id).where(CanonicalMemorySource.patient_id == patient_id)).scalars()
        )
        conversation_ids = list(
            db.execute(select(MemoryConversation.id).where(MemoryConversation.patient_id == patient_id)).scalars()
        )
        retrieval_run_ids = list(
            db.execute(select(MemoryRetrievalRun.id).where(MemoryRetrievalRun.patient_id == patient_id)).scalars()
        )
        ingestion_run_ids = list(
            db.execute(select(MemoryIngestionRun.id).where(MemoryIngestionRun.patient_id == patient_id)).scalars()
        )
        document_ids = list(db.execute(select(Document.id).where(Document.patient_id == patient_id)).scalars())
        encounter_ids = list(
            db.execute(select(ClinicalEncounter.id).where(ClinicalEncounter.patient_id == patient_id)).scalars()
        )

    if doctor_id and not encounter_ids:
        encounter_ids = list(
            db.execute(select(ClinicalEncounter.id).where(ClinicalEncounter.created_by_doctor_id == doctor_id)).scalars()
        )

    return {
        "system_instance_ids": system_instance_ids,
        "canonical_source_ids": canonical_source_ids,
        "conversation_ids": conversation_ids,
        "retrieval_run_ids": retrieval_run_ids,
        "ingestion_run_ids": ingestion_run_ids,
        "document_ids": document_ids,
        "encounter_ids": encounter_ids,
    }


def verify_cleanup(context: dict) -> dict:
    db = SessionLocal()

    try:
        email = context.get("email")
        patient_id = context.get("patient_id")
        doctor_count = 0
        patient_count = 0
        document_count = 0

        if email:
            doctor_count = db.execute(select(Doctor).where(Doctor.email == email)).scalars().all()
            doctor_count = len(doctor_count)

        if patient_id:
            patient_count = len(db.execute(select(Patient).where(Patient.id == patient_id)).scalars().all())
            document_count = len(db.execute(select(Document).where(Document.patient_id == patient_id)).scalars().all())

        return {
            "doctor_rows": doctor_count,
            "patient_rows": patient_count,
            "document_rows": document_count,
        }
    finally:
        db.close()


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    sys.exit(main())
