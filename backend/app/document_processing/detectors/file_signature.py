from __future__ import annotations

from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile
from io import BytesIO

from app.config import settings
from app.document.exceptions import MalformedDocument, UnsupportedDocumentFormat
from app.document_processing.normalizers.text import decode_text_content, is_probably_binary
from app.document_processing.schemas import FileSignatureResult
from app.storage.file_policy import normalize_content_type


SUPPORTED_SIGNATURES = {
    "application/pdf": ("pdf", "pdf"),
    "text/plain": ("txt", "text"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "docx",
        "docx",
    ),
}


def detect_file_signature(
    *,
    content: bytes,
    filename: str,
    declared_content_type: str,
) -> FileSignatureResult:
    extension = PurePosixPath(filename).suffix.lower().lstrip(".")
    declared_type = normalize_content_type(declared_content_type)

    if content.startswith(b"MZ"):
        raise UnsupportedDocumentFormat("Executable files are not supported.")

    if content.startswith(b"%PDF-"):
        return FileSignatureResult(
            content_type="application/pdf",
            extension="pdf",
            family="pdf",
        )

    if is_docx(content):
        validate_docx_zip(content)
        return FileSignatureResult(
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            extension="docx",
            family="docx",
        )

    if is_text_document(
        content=content,
        extension=extension,
        declared_content_type=declared_type,
    ):
        return FileSignatureResult(
            content_type="text/plain",
            extension="txt",
            family="text",
        )

    raise UnsupportedDocumentFormat("Only PDF, DOCX, and TXT documents are supported.")


def is_docx(content: bytes) -> bool:
    if not content.startswith(b"PK"):
        return False

    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except BadZipFile:
        return False

    return "[Content_Types].xml" in names and "word/document.xml" in names


def validate_docx_zip(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
    except BadZipFile as error:
        raise MalformedDocument("DOCX file is malformed.") from error

    if len(entries) > settings.document_max_docx_entries:
        raise MalformedDocument("DOCX file contains too many internal entries.")

    total_uncompressed_size = sum(entry.file_size for entry in entries)

    if total_uncompressed_size > settings.document_max_docx_uncompressed_bytes:
        raise MalformedDocument("DOCX file is too large after decompression.")

    names = {entry.filename for entry in entries}

    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
        raise MalformedDocument("DOCX file is missing required document parts.")


def is_text_document(
    *,
    content: bytes,
    extension: str,
    declared_content_type: str,
) -> bool:
    if declared_content_type != "text/plain" and extension != "txt":
        return False

    if is_probably_binary(content):
        return False

    text = decode_text_content(content)

    return bool(text.strip())
