from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str
    username: str


class LivenessResponse(BaseModel):
    status: str


class StorageHealthResponse(BaseModel):
    status: str
    provider: str
    bucket: Optional[str] = None
    detail: str
    can_connect: bool
    bucket_available: bool
