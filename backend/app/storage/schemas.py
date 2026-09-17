from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class UploadFileMetadata(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class FilePolicyResult(BaseModel):
    safe_filename: str
    normalized_content_type: str
    extension: str
    size_bytes: int
    checksum_sha256: Optional[str]


class StoredObjectResult(BaseModel):
    provider: str
    bucket: str
    object_path: str
    full_path: Optional[str] = None
    content_type: Optional[str] = None


class SignedUploadResult(BaseModel):
    provider: str
    bucket: str
    object_path: str
    signed_url: str
    token: Optional[str] = None
    expires_in: Optional[int] = None
    method: str = "PUT"
    required_headers: dict[str, str] = Field(default_factory=dict)


class SignedDownloadResult(BaseModel):
    provider: str
    bucket: str
    object_path: str
    signed_url: str
    expires_in: int


class StoredObjectMetadata(BaseModel):
    provider: str
    bucket: str
    object_path: str
    size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    etag: Optional[str] = None
    checksum: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class StorageHealthResult(BaseModel):
    status: str
    provider: str
    bucket: Optional[str] = None
    detail: str
    can_connect: bool = False
    bucket_available: bool = False


class StorageReadinessResponse(BaseModel):
    status: str
    provider: str
    bucket: Optional[str] = None
    detail: str
    can_connect: bool
    bucket_available: bool
