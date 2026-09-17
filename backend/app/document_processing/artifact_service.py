from __future__ import annotations

import hashlib
import json

from app.config import settings
from app.document.models import Document
from app.document_processing.enums import ARTIFACT_TYPES
from app.storage.interface import StorageProvider
from app.storage.path_builder import (
    build_normalized_text_path,
    build_processing_metadata_path,
    build_raw_text_path,
)


def persist_processing_artifacts(
    *,
    document: Document,
    raw_text: str,
    normalized_text: str,
    metadata: dict,
    storage_provider: StorageProvider,
    processor_name: str,
    processor_version: str,
) -> list[dict]:
    artifacts: list[dict] = []

    if settings.document_store_raw_extracted_text:
        artifacts.append(
            upload_text_artifact(
                document=document,
                storage_provider=storage_provider,
                object_path=build_raw_text_path(
                    environment=settings.document_storage_environment,
                    patient_id=document.patient_id,
                    document_id=document.id,
                ),
                artifact_type="raw_extracted_text",
                text=raw_text,
                processor_name=processor_name,
                processor_version=processor_version,
            )
        )

    if settings.document_store_normalized_text:
        artifacts.append(
            upload_text_artifact(
                document=document,
                storage_provider=storage_provider,
                object_path=build_normalized_text_path(
                    environment=settings.document_storage_environment,
                    patient_id=document.patient_id,
                    document_id=document.id,
                ),
                artifact_type="normalized_text",
                text=normalized_text,
                processor_name=processor_name,
                processor_version=processor_version,
            )
        )

    metadata_content = json.dumps(metadata, sort_keys=True, indent=2).encode("utf-8")
    metadata_path = build_processing_metadata_path(
        environment=settings.document_storage_environment,
        patient_id=document.patient_id,
        document_id=document.id,
    )
    metadata_result = storage_provider.upload_bytes(
        object_path=metadata_path,
        content=metadata_content,
        content_type="application/json",
        overwrite=True,
    )

    artifacts.append(
        {
            "artifact_type": "processing_metadata",
            "storage_provider": metadata_result.provider,
            "storage_bucket": metadata_result.bucket,
            "storage_object_path": metadata_result.object_path,
            "storage_object_version": None,
            "content_type": "application/json",
            "size_bytes": len(metadata_content),
            "checksum": hashlib.sha256(metadata_content).hexdigest(),
            "processor_name": processor_name,
            "processor_version": processor_version,
        }
    )

    return [artifact for artifact in artifacts if artifact["artifact_type"] in ARTIFACT_TYPES]


def upload_text_artifact(
    *,
    document: Document,
    storage_provider: StorageProvider,
    object_path: str,
    artifact_type: str,
    text: str,
    processor_name: str,
    processor_version: str,
) -> dict:
    content = text.encode("utf-8")
    result = storage_provider.upload_bytes(
        object_path=object_path,
        content=content,
        content_type="text/plain",
        overwrite=True,
        metadata={
            "document_id": str(document.id),
            "artifact_type": artifact_type,
        },
    )

    return {
        "artifact_type": artifact_type,
        "storage_provider": result.provider,
        "storage_bucket": result.bucket,
        "storage_object_path": result.object_path,
        "storage_object_version": None,
        "content_type": "text/plain",
        "size_bytes": len(content),
        "checksum": hashlib.sha256(content).hexdigest(),
        "processor_name": processor_name,
        "processor_version": processor_version,
    }
