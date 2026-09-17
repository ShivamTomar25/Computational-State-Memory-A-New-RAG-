from __future__ import annotations

from datetime import datetime
from typing import Any, BinaryIO, Optional

from httpx import RequestError, TimeoutException
from storage3.exceptions import StorageApiError

from app.storage.exceptions import (
    StorageAuthenticationError,
    StorageAuthorizationError,
    StorageBucketNotFound,
    StorageConnectionError,
    StorageDownloadSigningError,
    StorageObjectConflict,
    StorageObjectNotFound,
    StorageProviderError,
    StorageUploadError,
    StorageUploadSigningError,
)
from app.storage.path_builder import validate_object_path
from app.storage.schemas import (
    SignedDownloadResult,
    SignedUploadResult,
    StorageHealthResult,
    StoredObjectMetadata,
    StoredObjectResult,
)
from app.storage.supabase.client import SupabaseStorageConfig


class SupabaseStorageProvider:
    provider_name = "supabase"

    def __init__(
        self,
        *,
        client,
        config: SupabaseStorageConfig,
    ) -> None:
        self.client = client
        self.bucket = config.bucket
        self.signed_upload_expiry_seconds = config.signed_upload_expiry_seconds
        self.signed_download_expiry_seconds = config.signed_download_expiry_seconds

    def upload_bytes(
        self,
        *,
        object_path: str,
        content: bytes,
        content_type: str,
        overwrite: bool = False,
        metadata: Optional[dict] = None,
    ) -> StoredObjectResult:
        safe_path = validate_object_path(object_path)

        try:
            response = self.bucket_client().upload(
                safe_path,
                content,
                file_options=build_upload_options(
                    content_type=content_type,
                    overwrite=overwrite,
                    metadata=metadata,
                ),
            )
        except Exception as error:
            raise map_supabase_error(
                error,
                operation="upload",
                object_path=safe_path,
            ) from error

        return StoredObjectResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=safe_path,
            full_path=getattr(response, "full_path", None) or getattr(response, "fullPath", None),
            content_type=content_type,
        )

    def upload_stream(
        self,
        *,
        object_path: str,
        stream: BinaryIO,
        content_type: str,
        overwrite: bool = False,
        metadata: Optional[dict] = None,
    ) -> StoredObjectResult:
        safe_path = validate_object_path(object_path)

        try:
            response = self.bucket_client().upload(
                safe_path,
                stream,
                file_options=build_upload_options(
                    content_type=content_type,
                    overwrite=overwrite,
                    metadata=metadata,
                ),
            )
        except Exception as error:
            raise map_supabase_error(
                error,
                operation="upload",
                object_path=safe_path,
            ) from error

        return StoredObjectResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=safe_path,
            full_path=getattr(response, "full_path", None) or getattr(response, "fullPath", None),
            content_type=content_type,
        )

    def create_signed_upload(
        self,
        *,
        object_path: str,
        content_type: str,
    ) -> SignedUploadResult:
        safe_path = validate_object_path(object_path)

        try:
            response = self.bucket_client().create_signed_upload_url(safe_path)
        except Exception as error:
            mapped_error = map_supabase_error(
                error,
                operation="signed_upload",
                object_path=safe_path,
            )

            if isinstance(mapped_error, StorageProviderError):
                raise mapped_error from error

            raise StorageUploadSigningError("Could not create signed upload URL.") from error

        signed_url = response.get("signed_url") or response.get("signedUrl")
        token = response.get("token")

        if not signed_url:
            raise StorageUploadSigningError("Supabase did not return a signed upload URL.")

        return SignedUploadResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=safe_path,
            signed_url=signed_url,
            token=token,
            expires_in=None,
            method="PUT",
            required_headers={"content-type": content_type},
        )

    def create_signed_download(
        self,
        *,
        object_path: str,
        expires_in: Optional[int] = None,
    ) -> SignedDownloadResult:
        safe_path = validate_object_path(object_path)
        expiry = expires_in or self.signed_download_expiry_seconds

        try:
            response = self.bucket_client().create_signed_url(safe_path, expiry)
        except Exception as error:
            mapped_error = map_supabase_error(
                error,
                operation="signed_download",
                object_path=safe_path,
            )

            if isinstance(mapped_error, StorageProviderError):
                raise mapped_error from error

            raise StorageDownloadSigningError("Could not create signed download URL.") from error

        signed_url = response.get("signedUrl") or response.get("signedURL")

        if not signed_url:
            raise StorageDownloadSigningError("Supabase did not return a signed download URL.")

        return SignedDownloadResult(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=safe_path,
            signed_url=signed_url,
            expires_in=expiry,
        )

    def object_exists(self, *, object_path: str) -> bool:
        safe_path = validate_object_path(object_path)

        try:
            return bool(self.bucket_client().exists(safe_path))
        except Exception as error:
            mapped_error = map_supabase_error(
                error,
                operation="exists",
                object_path=safe_path,
            )

            if isinstance(mapped_error, StorageObjectNotFound):
                return False

            raise mapped_error from error

    def get_object_metadata(self, *, object_path: str) -> StoredObjectMetadata:
        safe_path = validate_object_path(object_path)

        try:
            response = self.bucket_client().info(safe_path)
        except Exception as error:
            raise map_supabase_error(
                error,
                operation="metadata",
                object_path=safe_path,
            ) from error

        return map_metadata(
            provider=self.provider_name,
            bucket=self.bucket,
            object_path=safe_path,
            response=response,
        )

    def download_bytes(self, *, object_path: str, max_bytes: Optional[int] = None) -> bytes:
        safe_path = validate_object_path(object_path)

        try:
            content = self.bucket_client().download(safe_path)
        except Exception as error:
            raise map_supabase_error(
                error,
                operation="download",
                object_path=safe_path,
            ) from error

        if max_bytes is not None and len(content) > max_bytes:
            raise StorageProviderError("Downloaded object exceeds the configured limit.")

        return content

    def delete_object(self, *, object_path: str) -> None:
        safe_path = validate_object_path(object_path)

        try:
            self.bucket_client().remove([safe_path])
        except Exception as error:
            raise map_supabase_error(
                error,
                operation="delete",
                object_path=safe_path,
            ) from error

    def health_check(self) -> StorageHealthResult:
        try:
            bucket = self.client.storage.get_bucket(self.bucket)
        except Exception as error:
            mapped_error = map_supabase_error(error, operation="health")

            if isinstance(mapped_error, StorageBucketNotFound):
                return StorageHealthResult(
                    status="unavailable",
                    provider=self.provider_name,
                    bucket=self.bucket,
                    detail="Configured storage bucket was not found.",
                    can_connect=True,
                    bucket_available=False,
                )

            if isinstance(mapped_error, StorageProviderError):
                return StorageHealthResult(
                    status="unavailable",
                    provider=self.provider_name,
                    bucket=self.bucket,
                    detail=str(mapped_error),
                    can_connect=False,
                    bucket_available=False,
                )

            return StorageHealthResult(
                status="unavailable",
                provider=self.provider_name,
                bucket=self.bucket,
                detail="Storage health check failed.",
                can_connect=False,
                bucket_available=False,
            )

        if getattr(bucket, "public", False):
            return StorageHealthResult(
                status="degraded",
                provider=self.provider_name,
                bucket=self.bucket,
                detail="Configured storage bucket is public.",
                can_connect=True,
                bucket_available=True,
            )

        return StorageHealthResult(
            status="healthy",
            provider=self.provider_name,
            bucket=self.bucket,
            detail="Storage bucket is reachable.",
            can_connect=True,
            bucket_available=True,
        )

    def bucket_client(self):
        return self.client.storage.from_(self.bucket)


def build_upload_options(
    *,
    content_type: str,
    overwrite: bool,
    metadata: Optional[dict],
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "content-type": content_type,
        "upsert": "true" if overwrite else "false",
    }

    if metadata:
        options["metadata"] = metadata

    return options


def map_metadata(
    *,
    provider: str,
    bucket: str,
    object_path: str,
    response: dict[str, Any],
) -> StoredObjectMetadata:
    metadata = response.get("metadata") or {}

    return StoredObjectMetadata(
        provider=provider,
        bucket=bucket,
        object_path=object_path,
        size_bytes=coerce_optional_int(
            response.get("size") or metadata.get("size") or metadata.get("contentLength")
        ),
        content_type=(
            response.get("content_type")
            or response.get("contentType")
            or metadata.get("mimetype")
            or metadata.get("contentType")
        ),
        etag=response.get("etag") or metadata.get("eTag") or metadata.get("etag"),
        checksum=metadata.get("checksum") or metadata.get("sha256"),
        created_at=parse_datetime(response.get("created_at") or response.get("createdAt")),
        updated_at=parse_datetime(response.get("updated_at") or response.get("updatedAt")),
        provider_metadata={
            "cache_control": response.get("cache_control") or response.get("cacheControl"),
            "last_accessed_at": response.get("last_accessed_at")
            or response.get("lastAccessedAt"),
        },
    )


def map_supabase_error(
    error: Exception,
    *,
    operation: str,
    object_path: Optional[str] = None,
) -> StorageProviderError:
    if isinstance(error, StorageApiError):
        status = coerce_optional_int(error.status)
        code = str(error.code or "").lower()
        message = str(error.message or "").lower()

        if status == 401:
            return StorageAuthenticationError("Storage authentication failed.")

        if status == 403:
            return StorageAuthorizationError("Storage authorization failed.")

        if status == 404:
            if operation == "health":
                return StorageBucketNotFound("Storage bucket was not found.")

            return StorageObjectNotFound("Storage object was not found.")

        if status == 409 or "duplicate" in code or "already exists" in message:
            return StorageObjectConflict("Storage object already exists.")

        if operation == "signed_upload":
            return StorageUploadSigningError("Could not create signed upload URL.")

        if operation == "signed_download":
            return StorageDownloadSigningError("Could not create signed download URL.")

        if operation == "upload":
            return StorageUploadError("Storage upload failed.")

        return StorageProviderError("Storage provider request failed.")

    if isinstance(error, (TimeoutError, TimeoutException)):
        return StorageConnectionError("Storage provider request timed out.")

    if isinstance(error, RequestError):
        return StorageConnectionError("Storage provider connection failed.")

    if operation == "signed_upload":
        return StorageUploadSigningError("Could not create signed upload URL.")

    if operation == "signed_download":
        return StorageDownloadSigningError("Could not create signed download URL.")

    if operation == "upload":
        return StorageUploadError("Storage upload failed.")

    return StorageProviderError("Storage provider operation failed.")


def coerce_optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    return None
