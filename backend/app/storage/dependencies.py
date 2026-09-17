from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.storage.interface import StorageProvider
from app.storage.supabase.client import (
    build_supabase_storage_config,
    get_supabase_client,
)
from app.storage.supabase.provider import SupabaseStorageProvider


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    storage_config = build_supabase_storage_config(settings)

    return SupabaseStorageProvider(
        client=get_supabase_client(),
        config=storage_config,
    )
