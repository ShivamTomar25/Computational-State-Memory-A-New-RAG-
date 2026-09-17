from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings


def configure_compression(app: FastAPI) -> None:
    if settings.api_compression_enabled:
        app.add_middleware(
            GZipMiddleware,
            minimum_size=settings.api_compression_minimum_size_bytes,
        )
