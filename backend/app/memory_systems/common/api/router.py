from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.doctor.dependencies import CurrentDoctor
from app.memory_systems.common.exceptions.errors import (
    ConversationNotFound,
    IngestionRunNotFound,
    MemorySystemError,
    MemorySystemNotFound,
    MemorySystemNotInitialized,
)
from app.memory_systems.common.schemas.memory import (
    MemoryConversationCreate,
    MemoryConversationResponse,
    MemoryIngestionRunDetailResponse,
    MemoryIngestionRunResponse,
    MemoryInitializeResponse,
    MemoryMessageCreate,
    MemoryMessagePostResponse,
    MemoryMessageResponse,
    MemoryRebuildRequest,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
    MemoryStatisticsResponse,
    MemorySyncRequest,
    MemorySystemInstanceResponse,
    MemorySystemRegistryItem,
)
from app.memory_systems.common.services.memory_service import (
    create_conversation,
    get_conversation,
    get_run,
    get_system_statistics,
    get_system_status,
    initialize_all_systems,
    initialize_system,
    list_conversations,
    list_messages,
    list_patient_systems,
    list_registry,
    list_runs,
    post_message,
    rebuild_system,
    retrieve_context,
    sync_system,
)


router = APIRouter(tags=["Memory Systems"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("/api/memory-systems", response_model=list[MemorySystemRegistryItem])
def get_memory_system_registry() -> list[MemorySystemRegistryItem]:
    return list_registry()


@router.get(
    "/api/patients/{patient_id}/memory-systems",
    response_model=list[MemorySystemInstanceResponse],
)
def get_patient_memory_systems(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[MemorySystemInstanceResponse]:
    try:
        return list_patient_systems(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/initialize-all",
    response_model=list[MemorySystemInstanceResponse],
)
def initialize_patient_memory_systems(
    patient_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[MemorySystemInstanceResponse]:
    try:
        return initialize_all_systems(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/{system_type}/initialize",
    response_model=MemoryInitializeResponse,
)
def initialize_patient_memory_system(
    patient_id: UUID,
    system_type: str,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryInitializeResponse:
    try:
        return initialize_system(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/{system_type}/sync",
    response_model=MemoryIngestionRunResponse,
)
def sync_patient_memory_system(
    patient_id: UUID,
    system_type: str,
    request: MemorySyncRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryIngestionRunResponse:
    try:
        return sync_system(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            request=request,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/{system_type}/rebuild",
    response_model=MemoryIngestionRunResponse,
)
def rebuild_patient_memory_system(
    patient_id: UUID,
    system_type: str,
    request: MemoryRebuildRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryIngestionRunResponse:
    try:
        return rebuild_system(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            request=request,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/status",
    response_model=MemorySystemInstanceResponse,
)
def get_patient_memory_system_status(
    patient_id: UUID,
    system_type: str,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemorySystemInstanceResponse:
    try:
        return get_system_status(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/statistics",
    response_model=MemoryStatisticsResponse,
)
def get_patient_memory_system_statistics(
    patient_id: UUID,
    system_type: str,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryStatisticsResponse:
    try:
        return get_system_statistics(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/runs",
    response_model=list[MemoryIngestionRunResponse],
)
def get_patient_memory_system_runs(
    patient_id: UUID,
    system_type: str,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[MemoryIngestionRunResponse]:
    try:
        return list_runs(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/runs/{run_id}",
    response_model=MemoryIngestionRunDetailResponse,
)
def get_patient_memory_system_run(
    patient_id: UUID,
    system_type: str,
    run_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryIngestionRunDetailResponse:
    try:
        return get_run(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            run_id=run_id,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/{system_type}/retrieve",
    response_model=MemoryRetrieveResponse,
)
def retrieve_patient_memory_context(
    patient_id: UUID,
    system_type: str,
    request: MemoryRetrieveRequest,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryRetrieveResponse:
    try:
        return retrieve_context(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            request=request,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/{system_type}/conversations",
    response_model=MemoryConversationResponse,
)
def create_patient_memory_conversation(
    patient_id: UUID,
    system_type: str,
    request: MemoryConversationCreate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryConversationResponse:
    try:
        return create_conversation(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            request=request,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/conversations",
    response_model=list[MemoryConversationResponse],
)
def list_patient_memory_conversations(
    patient_id: UUID,
    system_type: str,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[MemoryConversationResponse]:
    try:
        return list_conversations(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation_id}",
    response_model=MemoryConversationResponse,
)
def get_patient_memory_conversation(
    patient_id: UUID,
    system_type: str,
    conversation_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryConversationResponse:
    try:
        return get_conversation(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            conversation_id=conversation_id,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.get(
    "/api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation_id}/messages",
    response_model=list[MemoryMessageResponse],
)
def get_patient_memory_messages(
    patient_id: UUID,
    system_type: str,
    conversation_id: UUID,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> list[MemoryMessageResponse]:
    try:
        return list_messages(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            conversation_id=conversation_id,
        )
    except Exception as error:
        raise_memory_http_error(error)


@router.post(
    "/api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation_id}/messages",
    response_model=MemoryMessagePostResponse,
)
def post_patient_memory_message(
    patient_id: UUID,
    system_type: str,
    conversation_id: UUID,
    request: MemoryMessageCreate,
    current_doctor: CurrentDoctor,
    db: DatabaseSession,
) -> MemoryMessagePostResponse:
    try:
        return post_message(
            db=db,
            doctor=current_doctor,
            patient_id=patient_id,
            system_type=system_type,
            conversation_id=conversation_id,
            request=request,
        )
    except Exception as error:
        raise_memory_http_error(error)


def raise_memory_http_error(error: Exception):
    if isinstance(error, HTTPException):
        raise error

    if isinstance(
        error,
        (
            MemorySystemNotFound,
            MemorySystemNotInitialized,
            ConversationNotFound,
            IngestionRunNotFound,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    if isinstance(error, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    if isinstance(error, MemorySystemError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Memory system request failed.",
    ) from error
