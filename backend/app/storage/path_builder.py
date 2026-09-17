from __future__ import annotations

import re
from pathlib import PurePosixPath
from uuid import UUID

from app.storage.exceptions import StorageInvalidFilename, StorageInvalidPath


MAX_OBJECT_PATH_LENGTH = 512
MAX_SAFE_FILENAME_LENGTH = 120
SAFE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def build_original_document_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
    filename: str,
) -> str:
    safe_filename = sanitize_filename(filename)

    return validate_object_path(
        "/".join(
            [
                sanitize_path_segment(environment),
                "patients",
                str(patient_id),
                "documents",
                str(document_id),
                "original",
                safe_filename,
            ]
        )
    )


def build_derived_text_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
) -> str:
    return build_derived_path(
        environment=environment,
        patient_id=patient_id,
        document_id=document_id,
        filename="extracted-text.txt",
    )


def build_raw_text_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
) -> str:
    return build_derived_path(
        environment=environment,
        patient_id=patient_id,
        document_id=document_id,
        filename="raw-text.txt",
    )


def build_normalized_text_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
) -> str:
    return build_derived_path(
        environment=environment,
        patient_id=patient_id,
        document_id=document_id,
        filename="normalized-text.txt",
    )


def build_processing_metadata_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
) -> str:
    return build_derived_path(
        environment=environment,
        patient_id=patient_id,
        document_id=document_id,
        filename="processing-metadata.json",
    )


def build_metadata_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
) -> str:
    return build_derived_path(
        environment=environment,
        patient_id=patient_id,
        document_id=document_id,
        filename="metadata.json",
    )


def build_page_artifact_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
    page_number: int,
    extension: str = "png",
) -> str:
    if page_number < 1:
        raise StorageInvalidPath("Page number must be greater than zero.")

    clean_extension = extension.strip().lower().lstrip(".")

    if not re.fullmatch(r"[a-z0-9]{1,12}", clean_extension):
        raise StorageInvalidPath("Page artifact extension is invalid.")

    return validate_object_path(
        "/".join(
            [
                sanitize_path_segment(environment),
                "patients",
                str(patient_id),
                "documents",
                str(document_id),
                "derived",
                "pages",
                f"{page_number}.{clean_extension}",
            ]
        )
    )


def build_derived_path(
    *,
    environment: str,
    patient_id: UUID,
    document_id: UUID,
    filename: str,
) -> str:
    return validate_object_path(
        "/".join(
            [
                sanitize_path_segment(environment),
                "patients",
                str(patient_id),
                "documents",
                str(document_id),
                "derived",
                sanitize_filename(filename),
            ]
        )
    )


def sanitize_filename(filename: str) -> str:
    raw_filename = filename.strip()

    if not raw_filename:
        raise StorageInvalidFilename("Filename is required.")

    if "\x00" in raw_filename or "/" in raw_filename or "\\" in raw_filename:
        raise StorageInvalidFilename("Filename cannot contain path separators.")

    if raw_filename.startswith(".") or raw_filename.startswith("-"):
        raise StorageInvalidFilename("Filename must start with a visible name.")

    if ".." in PurePosixPath(raw_filename).parts or ".." in raw_filename:
        raise StorageInvalidFilename("Filename cannot contain path traversal.")

    cleaned = re.sub(r"\s+", "-", raw_filename)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-.")

    if not cleaned:
        raise StorageInvalidFilename("Filename is invalid after sanitization.")

    cleaned = limit_filename_length(cleaned)

    if not SAFE_SEGMENT_PATTERN.fullmatch(cleaned):
        raise StorageInvalidFilename("Filename contains unsupported characters.")

    return cleaned


def sanitize_path_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-.")

    if not cleaned:
        raise StorageInvalidPath("Storage path segment cannot be empty.")

    if cleaned == ".." or not SAFE_SEGMENT_PATTERN.fullmatch(cleaned):
        raise StorageInvalidPath("Storage path segment is invalid.")

    return cleaned


def validate_object_path(object_path: str) -> str:
    normalized_path = "/".join(part for part in object_path.split("/") if part)

    if object_path.startswith("/") or object_path.startswith("\\"):
        raise StorageInvalidPath("Storage path cannot start with a slash.")

    if "\\" in object_path or "\x00" in object_path:
        raise StorageInvalidPath("Storage path contains unsupported characters.")

    if len(normalized_path) > MAX_OBJECT_PATH_LENGTH:
        raise StorageInvalidPath("Storage path is too long.")

    parts = normalized_path.split("/")

    if not normalized_path or any(not part for part in parts):
        raise StorageInvalidPath("Storage path cannot be empty.")

    if any(part == ".." for part in parts):
        raise StorageInvalidPath("Storage path cannot contain path traversal.")

    for part in parts:
        if not SAFE_SEGMENT_PATTERN.fullmatch(part):
            raise StorageInvalidPath("Storage path contains an invalid segment.")

    return normalized_path


def limit_filename_length(filename: str) -> str:
    if len(filename) <= MAX_SAFE_FILENAME_LENGTH:
        return filename

    if "." not in filename:
        return filename[:MAX_SAFE_FILENAME_LENGTH].rstrip("-.")

    stem, extension = filename.rsplit(".", 1)
    extension = extension[:12]
    available_stem_length = MAX_SAFE_FILENAME_LENGTH - len(extension) - 1

    return f"{stem[:available_stem_length].rstrip('-.')}.{extension}"
