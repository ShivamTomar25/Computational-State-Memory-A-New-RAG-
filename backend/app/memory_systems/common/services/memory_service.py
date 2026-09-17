from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.doctor.model import Doctor
from app.llm.common.models.llm import AnswerClaim
from app.llm.common.services.answer_service import generate_grounded_answer
from app.memory_systems.common.canonical.source_collector import collect_sources
from app.memory_systems.common.enums.status import SYSTEM_METADATA
from app.memory_systems.common.exceptions.errors import (
    ConversationNotFound,
    IngestionRunNotFound,
    MemorySystemNotFound,
    MemorySystemNotInitialized,
)
from app.memory_systems.common.models.memory import MemoryConversation, MemorySystemInstance
from app.memory_systems.common.registry.registry import registry
from app.memory_systems.common.repositories import memory_repository as repository
from app.memory_systems.common.schemas.memory import (
    CapabilityStatus,
    MemoryConversationCreate,
    MemoryConversationResponse,
    MemoryIngestionRunDetailResponse,
    MemoryIngestionRunResponse,
    MemoryInitializeResponse,
    MemoryMessageCreate,
    MemoryMessagePostResponse,
    MemoryMessageResponse,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
    MemoryStatisticsResponse,
    MemorySyncRequest,
    MemorySystemInstanceResponse,
    MemorySystemRegistryItem,
)
from app.memory_systems.common.workflows.graphs import (
    build_conversation_graph,
    build_ingestion_graph,
    build_retrieval_graph,
)
from app.patient.model import Patient
from app.performance.caching.dependencies import get_cache_backend
from app.performance.caching.keys import memory_registry_key


def list_registry() -> list[MemorySystemRegistryItem]:
    cache = get_cache_backend()
    key = memory_registry_key()
    cached = cache.get(key)

    if cached is not None:
        return [MemorySystemRegistryItem(**item) for item in cached]

    items = [
        MemorySystemRegistryItem(
            system_type=adapter.system_type,
            display_name=adapter.display_name,
            description=adapter.metadata["description"],
            input_categories=["patient_information", "document", "conversation"],
            storage_summary=storage_summary(adapter.system_type),
            requires_embeddings=adapter.requires_embeddings,
            requires_llm=adapter.requires_llm,
            requires_external_provider=adapter.requires_external_provider,
            supports_incremental_ingestion=adapter.supports_incremental_ingestion,
            supports_conversation=True,
            supports_retrieval=True,
            supported_retrieval_modes=adapter.metadata["supported_retrieval_modes"],
            capability_status=adapter.capability_status(),
        )
        for adapter in registry.all()
    ]
    cache.set(key, [item.model_dump(mode="json") for item in items], ttl_seconds=30)
    return items


def list_patient_systems(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
) -> list[MemorySystemInstanceResponse]:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)
    existing = {
        instance.system_type: instance
        for instance in repository.list_instances(db=db, patient_id=patient_id)
    }

    return [
        build_instance_response(
            db=db,
            patient_id=patient_id,
            adapter=adapter,
            instance=existing.get(adapter.system_type),
        )
        for adapter in registry.all()
    ]


def initialize_all_systems(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
) -> list[MemorySystemInstanceResponse]:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)

    return list_patient_systems(db=db, doctor=doctor, patient_id=patient_id)


def initialize_missing_system_instances(db: Session, *, patient_id: UUID) -> None:
    existing = {
        instance.system_type: instance
        for instance in repository.list_instances(db=db, patient_id=patient_id)
    }
    changed = False

    for adapter in registry.all():
        now = utc_now()
        instance = existing.get(adapter.system_type)
        capability = adapter.capability_status()
        configuration = adapter.configuration()
        next_status = initial_status(capability)
        needs_initialization = (
            instance is None
            or instance.status == "not_initialized"
            or instance.initialized_at is None
        )

        if instance is None:
            instance = repository.create_instance(
                db=db,
                data={
                    "patient_id": patient_id,
                    "system_type": adapter.system_type,
                    "display_name": adapter.display_name,
                    "status": "not_initialized",
                    "capability_status": capability.model_dump(),
                    "configuration": configuration,
                    "pipeline_version": settings.memory_pipeline_version,
                    "initialized_at": now,
                    "last_synced_at": None,
                    "source_cutoff_time": None,
                    "failure_code": None,
                    "failure_reason": None,
                },
            )
        else:
            refresh_data = refreshed_instance_data(
                instance=instance,
                adapter=adapter,
                capability=capability,
                configuration=configuration,
                next_status=next_status,
                now=now,
            )

            if refresh_data:
                repository.update_instance(
                    db=db,
                    instance=instance,
                    data=refresh_data,
                )
                changed = True

        if needs_initialization:
            adapter.initialize(db, instance=instance)
            repository.update_instance(
                db=db,
                instance=instance,
                data={"status": next_status},
            )
            record_event(
                db=db,
                instance=instance,
                event_type="system_initialized",
                status="completed",
                metadata={"system_type": adapter.system_type, "mode": "automatic"},
            )
            changed = True

    if changed:
        db.commit()


def initialize_system(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
) -> MemoryInitializeResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    adapter = registry.get(system_type)
    instance = repository.get_instance(
        db=db,
        patient_id=patient_id,
        system_type=system_type,
    )
    now = utc_now()

    if instance is None:
        instance = repository.create_instance(
            db=db,
            data={
                "patient_id": patient_id,
                "system_type": system_type,
                "display_name": adapter.display_name,
                "status": "not_initialized",
                "capability_status": adapter.capability_status().model_dump(),
                "configuration": adapter.configuration(),
                "pipeline_version": settings.memory_pipeline_version,
                "initialized_at": now,
                "last_synced_at": None,
                "source_cutoff_time": None,
                "failure_code": None,
                "failure_reason": None,
            },
        )
    else:
        repository.update_instance(
            db=db,
            instance=instance,
            data={
                "capability_status": adapter.capability_status().model_dump(),
                "configuration": adapter.configuration(),
                "initialized_at": instance.initialized_at or now,
                "failure_code": None,
                "failure_reason": None,
            },
        )

    adapter.initialize(db, instance=instance)
    repository.update_instance(
        db=db,
        instance=instance,
        data={"status": initial_status(adapter.capability_status())},
    )
    record_event(
        db=db,
        instance=instance,
        event_type="system_initialized",
        status="completed",
        metadata={"system_type": system_type},
    )
    db.commit()
    db.refresh(instance)

    return MemoryInitializeResponse(
        instance=build_instance_response(
            db=db,
            patient_id=patient_id,
            adapter=adapter,
            instance=instance,
        )
    )


def sync_system(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
    request: MemorySyncRequest,
) -> MemoryIngestionRunResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    adapter = registry.get(system_type)
    cutoff_time = request.cutoff_time or utc_now()
    now = utc_now()
    graph = build_ingestion_graph()
    graph.invoke({})
    run = repository.create_ingestion_run(
        db=db,
        data={
            "system_instance_id": instance.id,
            "patient_id": patient_id,
            "mode": request.mode,
            "status": "running",
            "cutoff_time": cutoff_time,
            "pipeline_version": settings.memory_pipeline_version,
            "configuration_snapshot": adapter.configuration(),
            "source_count": 0,
            "processed_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "queued_at": now,
            "started_at": now,
            "completed_at": None,
            "failure_code": None,
            "failure_reason": None,
        },
    )
    repository.update_instance(
        db=db,
        instance=instance,
        data={
            "status": "syncing",
            "source_cutoff_time": cutoff_time,
            "capability_status": adapter.capability_status().model_dump(),
            "configuration": adapter.configuration(),
        },
    )
    record_event(
        db=db,
        instance=instance,
        event_type="synchronization_started",
        status="running",
        metadata={"run_id": str(run.id), "mode": request.mode},
    )
    db.flush()

    try:
        collected = collect_sources(
            db,
            patient_id=patient_id,
            instance=instance,
            cutoff_time=cutoff_time,
            include_patient_information=request.include_patient_information,
            include_documents=request.include_documents,
            include_conversation=request.include_conversation,
        )
        canonical_sources = [
            repository.upsert_canonical_source(db=db, source=source)[0]
            for source in collected
        ]
        ingestion_results = adapter.ingest_sources(
            db=db,
            instance=instance,
            sources=canonical_sources,
        )

        for result in ingestion_results:
            repository.create_or_update_source_link(
                db=db,
                system_instance_id=instance.id,
                canonical_source_id=result.canonical_source_id,
                native_record_type=result.native_record_type,
                native_record_id=result.native_record_id,
                source_hash=result.source_hash,
                ingestion_status=result.status,
                indexed_at=utc_now(),
            )
            repository.add_ingestion_run_item(
                db=db,
                data={
                    "run_id": run.id,
                    "canonical_source_id": result.canonical_source_id,
                    "action": "upsert",
                    "status": result.status,
                    "native_record_id": result.native_record_id,
                    "failure_code": None,
                    "failure_reason": None,
                },
            )

        completed_at = utc_now()
        repository.update_ingestion_run(
            db=db,
            run=run,
            data={
                "status": "completed",
                "source_count": len(canonical_sources),
                "processed_count": len(ingestion_results),
                "skipped_count": max(0, len(canonical_sources) - len(ingestion_results)),
                "failed_count": 0,
                "completed_at": completed_at,
            },
        )
        repository.update_instance(
            db=db,
            instance=instance,
            data={
                "status": initial_status(adapter.capability_status()),
                "last_synced_at": completed_at,
                "failure_code": None,
                "failure_reason": None,
            },
        )
        record_event(
            db=db,
            instance=instance,
            event_type="synchronization_completed",
            status="completed",
            metadata={
                "run_id": str(run.id),
                "source_count": len(canonical_sources),
                "processed_count": len(ingestion_results),
            },
        )
        db.commit()
        db.refresh(run)

        return MemoryIngestionRunResponse.model_validate(run)

    except Exception as error:
        repository.update_ingestion_run(
            db=db,
            run=run,
            data={
                "status": "failed",
                "failure_code": error.__class__.__name__,
                "failure_reason": safe_error(error),
                "completed_at": utc_now(),
            },
        )
        repository.update_instance(
            db=db,
            instance=instance,
            data={
                "status": "failed",
                "failure_code": error.__class__.__name__,
                "failure_reason": safe_error(error),
            },
        )
        record_event(
            db=db,
            instance=instance,
            event_type="synchronization_failed",
            status="failed",
            metadata={"run_id": str(run.id), "failure_code": error.__class__.__name__},
        )
        db.commit()
        raise


def rebuild_system(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
    request,
) -> MemoryIngestionRunResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)

    if not request.confirm_rebuild:
        raise ValueError("Rebuild requires confirm_rebuild=true.")

    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    repository.delete_source_links_for_instance(db=db, system_instance_id=instance.id)
    registry.get(system_type).rebuild(db=db, instance=instance)
    db.flush()

    sync_request = MemorySyncRequest(
        cutoff_time=request.cutoff_time,
        mode="rebuild",
        include_patient_information=request.include_patient_information,
        include_documents=request.include_documents,
        include_conversation=request.include_conversation,
    )

    return sync_system(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type=system_type,
        request=sync_request,
    )


def get_system_status(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str) -> MemorySystemInstanceResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)
    adapter = registry.get(system_type)
    instance = repository.get_instance(db=db, patient_id=patient_id, system_type=system_type)

    return build_instance_response(db=db, patient_id=patient_id, adapter=adapter, instance=instance)


def get_system_statistics(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str) -> MemoryStatisticsResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)
    adapter = registry.get(system_type)
    instance = repository.get_instance(db=db, patient_id=patient_id, system_type=system_type)

    if instance is None:
        return MemoryStatisticsResponse(
            system_type=system_type,
            status="not_initialized",
            source_counts={
                "patient_information": 0,
                "document": 0,
                "conversation": 0,
            },
            storage={},
            capability_status=adapter.capability_status(),
        )

    return MemoryStatisticsResponse(
        system_type=system_type,
        status=instance.status,
        source_counts=repository.count_sources_by_type(
            db=db,
            patient_id=patient_id,
            system_instance_id=instance.id,
        ),
        storage=adapter.get_statistics(db, instance=instance),
        capability_status=CapabilityStatus(**instance.capability_status),
    )


def list_runs(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str) -> list[MemoryIngestionRunResponse]:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)
    registry.get(system_type)
    instance = repository.get_instance(db=db, patient_id=patient_id, system_type=system_type)

    if instance is None:
        return []

    return [
        MemoryIngestionRunResponse.model_validate(run)
        for run in repository.list_ingestion_runs(db=db, system_instance_id=instance.id)
    ]


def get_run(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str, run_id: UUID) -> MemoryIngestionRunDetailResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    run = repository.get_ingestion_run(db=db, system_instance_id=instance.id, run_id=run_id)

    if run is None:
        raise IngestionRunNotFound("Ingestion run not found.")

    data = MemoryIngestionRunResponse.model_validate(run).model_dump()
    items = [
        {
            "canonical_source_id": str(item.canonical_source_id),
            "action": item.action,
            "status": item.status,
            "native_record_id": str(item.native_record_id) if item.native_record_id else None,
        }
        for item in repository.list_ingestion_run_items(db=db, run_id=run.id)
    ]

    return MemoryIngestionRunDetailResponse(**data, items=items)


def retrieve_context(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
    request: MemoryRetrieveRequest,
) -> MemoryRetrieveResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    adapter = registry.get(system_type)
    top_k = bounded_top_k(request.top_k)
    token_budget = bounded_token_budget(request.token_budget)

    if request.conversation_id:
        conversation = repository.get_conversation(
            db=db,
            system_instance_id=instance.id,
            conversation_id=request.conversation_id,
        )

        if conversation is None:
            raise ConversationNotFound("Conversation not found.")

    graph = build_retrieval_graph()
    graph.invoke({})
    started = time.monotonic()
    items, warnings, readiness = adapter.retrieve(
        db,
        instance=instance,
        query=request.query.strip(),
        top_k=top_k,
        token_budget=token_budget,
        retrieval_mode=request.retrieval_mode,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    retrieval_run = repository.create_retrieval_run(
        db=db,
        data={
            "system_instance_id": instance.id,
            "patient_id": patient_id,
            "conversation_id": request.conversation_id,
            "query_text": request.query.strip(),
            "retrieval_mode": request.retrieval_mode or adapter.metadata["supported_retrieval_modes"][0],
            "requested_top_k": top_k,
            "requested_token_budget": token_budget,
            "result_count": len(items),
            "duration_ms": duration_ms,
            "configuration_snapshot": {
                **adapter.configuration(),
                "instance_configuration": instance.configuration or {},
            },
            "status": readiness,
        },
    )

    for item in items:
        repository.add_retrieval_item(
            db=db,
            data={
                "retrieval_run_id": retrieval_run.id,
                "canonical_source_id": item.canonical_source_id,
                "system_native_type": item.system_native_type,
                "system_native_id": item.system_native_id,
                "rank": item.rank,
                "raw_score": item.score,
                "normalized_score": item.score,
                "dense_rank": item.dense_rank,
                "lexical_rank": item.lexical_rank,
                "graph_score": item.graph_score,
                "source_type": item.source_type,
                "document_id": item.document_id,
                "page_number": item.page_number,
                "section_id": item.section_id,
                "content_preview": item.content_preview,
                "token_count": item.token_count,
            },
        )

    record_event(
        db=db,
        instance=instance,
        event_type="retrieval",
        status=readiness,
        metadata={
            "retrieval_run_id": str(retrieval_run.id),
            "result_count": len(items),
        },
    )
    db.commit()

    return MemoryRetrieveResponse(
        system_type=system_type,
        retrieval_run_id=retrieval_run.id,
        readiness_status=readiness,
        query=request.query.strip(),
        context_items=items,
        citations=build_citations(items) if request.include_citations else [],
        token_count=sum(item.token_count for item in items),
        excluded_result_count=0,
        warnings=warnings,
        generation_status="not_configured",
    )


def create_conversation(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
    request: MemoryConversationCreate,
) -> MemoryConversationResponse:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    conversation = repository.create_conversation(
        db=db,
        data={
            "patient_id": patient_id,
            "doctor_id": doctor.id,
            "system_instance_id": instance.id,
            "system_type": system_type,
            "title": request.title,
            "status": "active",
            "last_message_at": None,
        },
    )
    record_event(
        db=db,
        instance=instance,
        event_type="conversation_created",
        status="completed",
        metadata={"conversation_id": str(conversation.id)},
    )
    db.commit()
    db.refresh(conversation)

    return MemoryConversationResponse.model_validate(conversation)


def list_conversations(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str) -> list[MemoryConversationResponse]:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    initialize_missing_system_instances(db=db, patient_id=patient_id)
    registry.get(system_type)
    instance = repository.get_instance(db=db, patient_id=patient_id, system_type=system_type)

    if instance is None:
        return []

    return [
        MemoryConversationResponse.model_validate(conversation)
        for conversation in repository.list_conversations(db=db, system_instance_id=instance.id)
    ]


def get_conversation(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str, conversation_id: UUID) -> MemoryConversationResponse:
    conversation = ensure_conversation(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type=system_type,
        conversation_id=conversation_id,
    )

    return MemoryConversationResponse.model_validate(conversation)


def list_messages(db: Session, *, doctor: Doctor, patient_id: UUID, system_type: str, conversation_id: UUID) -> list[MemoryMessageResponse]:
    conversation = ensure_conversation(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type=system_type,
        conversation_id=conversation_id,
    )

    return [
        MemoryMessageResponse.model_validate(message)
        for message in repository.list_messages(db=db, conversation_id=conversation.id)
    ]


def post_message(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
    conversation_id: UUID,
    request: MemoryMessageCreate,
) -> MemoryMessagePostResponse:
    conversation = ensure_conversation(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type=system_type,
        conversation_id=conversation_id,
    )
    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    graph = build_conversation_graph()
    graph.invoke({})
    message = repository.create_message(
        db=db,
        conversation=conversation,
        data={
            "role": "user",
            "content": request.content.strip(),
            "event_time": utc_now(),
            "token_count": max(1, (len(request.content.strip()) + 3) // 4),
            "generation_status": "not_configured",
            "retrieval_run_id": None,
        },
    )
    db.flush()
    sync_system(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type=system_type,
        request=MemorySyncRequest(
            cutoff_time=utc_now(),
            mode="incremental",
            include_patient_information=False,
            include_documents=False,
            include_conversation=True,
        ),
    )
    retrieval = retrieve_context(
        db=db,
        doctor=doctor,
        patient_id=patient_id,
        system_type=system_type,
        request=MemoryRetrieveRequest(
            query=request.content.strip(),
            conversation_id=conversation_id,
        ),
    )
    repository.update_message_retrieval(
        db=db,
        message=message,
        retrieval_run_id=retrieval.retrieval_run_id,
    )
    history = repository.list_messages(db=db, conversation_id=conversation.id)
    patient = repository.get_owned_patient(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )
    generation = generate_grounded_answer(
        db,
        patient=patient,
        instance=instance,
        conversation=conversation,
        retrieval=retrieval,
        conversation_history=history,
        question=request.content.strip(),
    )
    assistant_message = None

    if generation.status == "completed" and generation.answer is not None:
        assistant_message = repository.create_message(
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
        db.flush()
        persist_answer_claims(
            db=db,
            patient_id=patient_id,
            instance=instance,
            conversation_id=conversation.id,
            answer_message_id=assistant_message.id,
            llm_call_id=generation.llm_call_id,
            answer=generation.answer,
        )
        sync_system(
            db=db,
            doctor=doctor,
            patient_id=patient_id,
            system_type=system_type,
            request=MemorySyncRequest(
                cutoff_time=utc_now(),
                mode="incremental",
                include_patient_information=False,
                include_documents=False,
                include_conversation=True,
            ),
        )

    record_event(
        db=db,
        instance=instance,
        event_type="user_message_inserted",
        status="completed",
        metadata={"conversation_id": str(conversation_id)},
    )
    db.commit()
    db.refresh(message)

    return MemoryMessagePostResponse(
        message=MemoryMessageResponse.model_validate(message),
        retrieval=retrieval,
        generation_status=generation.status,
        assistant_message=MemoryMessageResponse.model_validate(assistant_message)
        if assistant_message
        else None,
        answer=generation.answer,
        llm_call_id=generation.llm_call_id,
        model=generation.model,
        prompt_version=generation.prompt_version,
        input_tokens=generation.input_tokens,
        output_tokens=generation.output_tokens,
        total_tokens=generation.total_tokens,
        latency_ms=generation.duration_ms,
        warnings=generation.warnings,
    )


def ensure_owned_patient(db: Session, *, doctor: Doctor, patient_id: UUID) -> Patient:
    patient = repository.get_owned_patient(
        db=db,
        doctor_id=doctor.id,
        patient_id=patient_id,
    )

    if patient is None:
        raise MemorySystemNotFound("Patient not found.")

    return patient


def ensure_instance(db: Session, *, patient_id: UUID, system_type: str) -> MemorySystemInstance:
    registry.get(system_type)
    instance = repository.get_instance(db=db, patient_id=patient_id, system_type=system_type)

    if instance is None or instance.status == "not_initialized" or instance.initialized_at is None:
        initialize_missing_system_instances(db=db, patient_id=patient_id)
        instance = repository.get_instance(db=db, patient_id=patient_id, system_type=system_type)

    if instance is None:
        raise MemorySystemNotInitialized("Memory system is not initialized.")

    return instance


def ensure_conversation(
    db: Session,
    *,
    doctor: Doctor,
    patient_id: UUID,
    system_type: str,
    conversation_id: UUID,
) -> MemoryConversation:
    ensure_owned_patient(db=db, doctor=doctor, patient_id=patient_id)
    instance = ensure_instance(db=db, patient_id=patient_id, system_type=system_type)
    conversation = repository.get_conversation(
        db=db,
        system_instance_id=instance.id,
        conversation_id=conversation_id,
    )

    if conversation is None:
        raise ConversationNotFound("Conversation not found.")

    return conversation


def build_instance_response(
    *,
    db: Session,
    patient_id: UUID,
    adapter,
    instance: Optional[MemorySystemInstance],
) -> MemorySystemInstanceResponse:
    if instance is None:
        return MemorySystemInstanceResponse(
            id=None,
            patient_id=patient_id,
            system_type=adapter.system_type,
            display_name=adapter.display_name,
            status="not_initialized",
            capability_status=adapter.capability_status(),
            configuration=adapter.configuration(),
            pipeline_version=settings.memory_pipeline_version,
            statistics={},
        )

    return MemorySystemInstanceResponse(
        id=instance.id,
        patient_id=patient_id,
        system_type=instance.system_type,
        display_name=instance.display_name,
        status=instance.status,
        capability_status=CapabilityStatus(**instance.capability_status),
        configuration=instance.configuration,
        pipeline_version=instance.pipeline_version,
        initialized_at=instance.initialized_at,
        last_synced_at=instance.last_synced_at,
        source_cutoff_time=instance.source_cutoff_time,
        failure_code=instance.failure_code,
        failure_reason=instance.failure_reason,
        statistics=adapter.get_statistics(db, instance=instance),
    )


def refreshed_instance_data(
    *,
    instance: MemorySystemInstance,
    adapter,
    capability: CapabilityStatus,
    configuration: dict,
    next_status: str,
    now: datetime,
) -> dict:
    data = {
        "display_name": adapter.display_name,
        "capability_status": capability.model_dump(),
        "configuration": configuration,
        "pipeline_version": settings.memory_pipeline_version,
        "initialized_at": instance.initialized_at or now,
    }

    if should_refresh_instance_status(instance.status):
        data["status"] = next_status
        data["failure_code"] = None
        data["failure_reason"] = None

    return {
        field: value
        for field, value in data.items()
        if getattr(instance, field) != value
    }


def should_refresh_instance_status(status: str) -> bool:
    return status in {
        "not_initialized",
        "provider_not_configured",
        "provider_not_installed",
        "requires_embeddings",
        "requires_llm",
        "unavailable",
        "not_ready",
    }


def initial_status(capability: CapabilityStatus) -> str:
    if capability.ingestion in {"requires_llm", "provider_not_configured", "provider_not_installed"}:
        return capability.ingestion

    return "ready"


def storage_summary(system_type: str) -> str:
    summaries = {
        "long_context": "long_context_entries and snapshots",
        "rolling_summary": "pending inputs, recent window, immutable summary snapshots",
        "dense_rag": "dense_rag_chunks with local deterministic embeddings",
        "hybrid_rag": "hybrid_rag_chunks with dense vectors and lexical documents",
        "graph_rag": "GraphRAG text units and normalized graph artifacts",
        "hippo_rag": "Hippo passages, nodes, edges and PPR traces",
        "csm": "CSM evidence, state variables, history and activation traces",
        "csm_v3": "CSM v3 evidence, controlled state variables, history and selective activation traces",
        "csm_v4": "CSM v4 evidence-derived state, adaptive activation, support evidence and lineage traces",
    }

    return summaries[system_type]


def bounded_top_k(value: Optional[int]) -> int:
    return min(value or settings.memory_default_top_k, settings.memory_max_top_k)


def bounded_token_budget(value: Optional[int]) -> int:
    return min(
        value or settings.memory_default_context_token_budget,
        settings.memory_max_context_token_budget,
    )


def build_citations(items) -> list[dict]:
    return [
        {
            "rank": item.rank,
            "canonical_source_id": str(item.canonical_source_id) if item.canonical_source_id else None,
            "source_type": item.source_type,
            "source_subtype": item.source_subtype,
            "document_id": str(item.document_id) if item.document_id else None,
            "page_number": item.page_number,
            "section_id": str(item.section_id) if item.section_id else None,
        }
        for item in items
    ]


def record_event(db: Session, *, instance, event_type: str, status: str, metadata: dict) -> None:
    repository.create_event(
        db=db,
        data={
            "system_instance_id": instance.id,
            "patient_id": instance.patient_id,
            "event_type": event_type,
            "status": status,
            "safe_metadata": metadata,
            "request_id": None,
        },
    )


def persist_answer_claims(
    *,
    db: Session,
    patient_id: UUID,
    instance: MemorySystemInstance,
    conversation_id: UUID,
    answer_message_id: UUID,
    llm_call_id: Optional[str],
    answer,
) -> None:
    if answer is None:
        return

    for claim in answer.atomic_claims:
        db.add(
            AnswerClaim(
                patient_id=patient_id,
                system_instance_id=instance.id,
                conversation_id=conversation_id,
                answer_message_id=answer_message_id,
                llm_call_id=UUID(llm_call_id) if llm_call_id else None,
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                subject=claim.subject,
                predicate=claim.predicate,
                value=claim.value,
                normalized_value=claim.normalized_value,
                unit=claim.unit,
                status=claim.status,
                negation=claim.negation,
                valid_time=claim.valid_time,
                confidence=claim.confidence,
                uncertainty=claim.uncertainty,
                citation_ids=claim.citation_ids,
                source_support_status=None,
            )
        )


def safe_error(error: Exception) -> str:
    return (str(error) or "Memory system request failed.")[:500]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
