from __future__ import annotations

from typing import BinaryIO, Optional, Protocol

from app.storage.schemas import (
    SignedDownloadResult,
    SignedUploadResult,
    StorageHealthResult,
    StoredObjectMetadata,
    StoredObjectResult,
)


class StorageProvider(Protocol):
    provider_name: str
    bucket: str

    def upload_bytes(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
        overwrite: bool = False,
        metadata: Optional[dict] = None,
    ) -> StoredObjectResult:
        ...

    def upload_stream(
        self,
        *,
        object_path: str,
        stream: BinaryIO,
        content_type: str,
        overwrite: bool = False,
        metadata: Optional[dict] = None,
    ) -> StoredObjectResult:
        ...

    def create_signed_upload(
        self,
        *,
        object_path: str,
        content_type: str,
    ) -> SignedUploadResult:
        ...

    def create_signed_download(
        self,
        *,
        object_path: str,
        expires_in: Optional[int] = None,
    ) -> SignedDownloadResult:
        ...

    def object_exists(self, *, object_path: str) -> bool:
        ...

    def get_object_metadata(self, *, object_path: str) -> StoredObjectMetadata:
        ...

    def download_bytes(self, *, object_path: str, max_bytes: Optional[int] = None) -> bytes:
        ...

    def delete_object(self, *, object_path: str) -> None:
        ...

    def health_check(self) -> StorageHealthResult:
        ...
