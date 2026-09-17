from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from urllib.parse import urlparse

from supabase import create_client
from supabase.client import ClientOptions

from app.config import Settings, settings
from app.storage.exceptions import StorageConfigurationError


@dataclass(frozen=True)
class SupabaseStorageConfig:
    url: str
    secret_key: str
    bucket: str
    signed_upload_expiry_seconds: int
    signed_download_expiry_seconds: int


def build_supabase_storage_config(config: Settings) -> SupabaseStorageConfig:
    url = clean_required_value(config.supabase_url, "SUPABASE_URL")
    secret_key = clean_required_value(
        config.supabase_secret_key,
        "SUPABASE_SECRET_KEY",
    )
    bucket = clean_required_value(
        config.supabase_storage_bucket,
        "SUPABASE_STORAGE_BUCKET",
    )

    parsed_url = urlparse(url)

    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise StorageConfigurationError("SUPABASE_URL must be a valid HTTP URL.")

    if config.supabase_signed_upload_expiry_seconds <= 0:
        raise StorageConfigurationError(
            "SUPABASE_SIGNED_UPLOAD_EXPIRY_SECONDS must be greater than zero."
        )

    if config.supabase_signed_download_expiry_seconds <= 0:
        raise StorageConfigurationError(
            "SUPABASE_SIGNED_DOWNLOAD_EXPIRY_SECONDS must be greater than zero."
        )

    return SupabaseStorageConfig(
        url=url,
        secret_key=secret_key,
        bucket=bucket,
        signed_upload_expiry_seconds=config.supabase_signed_upload_expiry_seconds,
        signed_download_expiry_seconds=config.supabase_signed_download_expiry_seconds,
    )


@lru_cache(maxsize=1)
def get_supabase_client():
    storage_config = build_supabase_storage_config(settings)

    return create_client(
        storage_config.url,
        storage_config.secret_key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            storage_client_timeout=20,
        ),
    )


def clean_required_value(value: Optional[str], env_name: str) -> str:
    if value is None or not value.strip():
        raise StorageConfigurationError(f"{env_name} is required for Supabase Storage.")

    return value.strip()
