from __future__ import annotations

from app.config import settings


def connection_pool_settings() -> dict:
    return {
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout_seconds": settings.database_pool_timeout_seconds,
        "pool_recycle_seconds": settings.database_pool_recycle_seconds,
        "pool_pre_ping": True,
    }
