from uuid import UUID

from sqlalchemy.orm import Session

from app.doctor.model import Doctor
from app.memory_systems.common.services.memory_service import initialize_missing_system_instances
from app.patient import repository as patient_repository
from app.patient.exceptions import PatientNotFoundError
from app.patient.schemas import PatientResponse
from app.patient.workspace import repository
from app.patient.workspace.schemas import (
    PatientWorkspaceDocumentCounts,
    PatientWorkspaceInformationCounts,
    PatientWorkspaceSummaryResponse,
)
from app.performance.caching.dependencies import get_cache_backend
from app.performance.caching.keys import patient_workspace_summary_key


def get_patient_workspace_summary(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
) -> PatientWorkspaceSummaryResponse:
    cache = get_cache_backend()
    cache_key = patient_workspace_summary_key(doctor.id, patient_id)
    cached = cache.get(cache_key)

    if cached is not None:
        return PatientWorkspaceSummaryResponse(**cached)

    patient = patient_repository.get_patient_by_id(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )

    if patient is None:
        raise PatientNotFoundError("Patient not found.")

    initialize_missing_system_instances(db=db, patient_id=patient_id)

    summary = PatientWorkspaceSummaryResponse(
        patient=PatientResponse.model_validate(patient),
        information_counts=PatientWorkspaceInformationCounts(
            **repository.count_patient_information(db=db, patient_id=patient_id)
        ),
        document_counts=PatientWorkspaceDocumentCounts(
            **repository.count_documents(db=db, patient_id=patient_id)
        ),
        memory_systems=repository.list_memory_system_summaries(
            db=db,
            patient_id=patient_id,
        ),
        recent_conversations=repository.list_recent_conversation_summaries(
            db=db,
            doctor_id=doctor.id,
            patient_id=patient_id,
        ),
    )
    cache.set(cache_key, summary.model_dump(mode="json"), ttl_seconds=10)

    return summary
