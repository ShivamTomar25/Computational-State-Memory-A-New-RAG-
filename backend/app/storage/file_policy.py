from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.config import Settings, settings
from app.storage.exceptions import (
    StorageEmptyFile,
    StorageFileTooLarge,
    StorageInvalidFilename,
    StorageUnsupportedContentType,
)
from app.storage.path_builder import sanitize_filename
from app.storage.schemas import FilePolicyResult, UploadFileMetadata


CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "text/plain": {".txt"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
}
SHA256_PATTERN = re.compile(r"^[A-Fa-f0-9]{64}$")


class DocumentFilePolicy:
    def __init__(
        self,
        *,
        allowed_content_types: set[str],
        max_size_bytes: int,
    ) -> None:
        if not allowed_content_types:
            raise StorageUnsupportedContentType("At least one content type is required.")

        if max_size_bytes <= 0:
            raise StorageFileTooLarge("Maximum file size must be greater than zero.")

        self.allowed_content_types = allowed_content_types
        self.max_size_bytes = max_size_bytes

    def validate_upload_metadata(
        self,
        metadata: UploadFileMetadata,
    ) -> FilePolicyResult:
        safe_filename = sanitize_filename(metadata.filename)
        normalized_content_type = normalize_content_type(metadata.content_type)
        extension = extract_extension(metadata.filename)

        if metadata.size_bytes <= 0:
            raise StorageEmptyFile("File size must be greater than zero.")

        if metadata.size_bytes > self.max_size_bytes:
            raise StorageFileTooLarge("File size exceeds the configured limit.")

        if normalized_content_type not in self.allowed_content_types:
            raise StorageUnsupportedContentType("File content type is not supported.")

        allowed_extensions = CONTENT_TYPE_EXTENSIONS.get(normalized_content_type, set())

        if extension not in allowed_extensions:
            raise StorageInvalidFilename("File extension does not match the content type.")

        if metadata.checksum_sha256 and not SHA256_PATTERN.fullmatch(metadata.checksum_sha256):
            raise StorageInvalidFilename("SHA-256 checksum is malformed.")

        return FilePolicyResult(
            safe_filename=safe_filename,
            normalized_content_type=normalized_content_type,
            extension=extension.lstrip("."),
            size_bytes=metadata.size_bytes,
            checksum_sha256=metadata.checksum_sha256.lower()
            if metadata.checksum_sha256
            else None,
        )


def get_document_file_policy() -> DocumentFilePolicy:
    return build_document_file_policy(settings)


def build_document_file_policy(config: Settings) -> DocumentFilePolicy:
    return DocumentFilePolicy(
        allowed_content_types=parse_allowed_content_types(
            config.document_allowed_content_types
        ),
        max_size_bytes=config.document_max_file_size_bytes,
    )


def parse_allowed_content_types(value: str) -> set[str]:
    return {
        normalize_content_type(item)
        for item in value.split(",")
        if normalize_content_type(item)
    }


def normalize_content_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def extract_extension(filename: str) -> str:
    raw_filename = filename.strip()

    if not raw_filename:
        raise StorageInvalidFilename("Filename is required.")

    if "\x00" in raw_filename or "/" in raw_filename or "\\" in raw_filename:
        raise StorageInvalidFilename("Filename cannot contain path separators.")

    if ".." in PurePosixPath(raw_filename).parts or ".." in raw_filename:
        raise StorageInvalidFilename("Filename cannot contain path traversal.")

    extension = PurePosixPath(raw_filename).suffix.lower()

    if not extension:
        raise StorageInvalidFilename("File extension is required.")

    return extension
