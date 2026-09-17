from __future__ import annotations

from app.config import settings
from app.storage.exceptions import StorageConfigurationError, StorageProviderError
from app.storage.schemas import StorageHealthResult
from app.storage.supabase.client import build_supabase_storage_config
from app.storage.supabase.provider import SupabaseStorageProvider


def check_storage_readiness(provider_factory=None) -> StorageHealthResult:
    try:
        if provider_factory is None:
            from app.storage.dependencies import get_storage_provider

            provider_factory = get_storage_provider

        provider = provider_factory()

        return provider.health_check()

    except StorageConfigurationError as error:
        return StorageHealthResult(
            status="not_configured",
            provider="supabase",
            bucket=settings.supabase_storage_bucket,
            detail=str(error),
            can_connect=False,
            bucket_available=False,
        )

    except StorageProviderError:
        return StorageHealthResult(
            status="unavailable",
            provider="supabase",
            bucket=settings.supabase_storage_bucket,
            detail="Storage provider is unavailable.",
            can_connect=False,
            bucket_available=False,
        )


def check_supabase_configuration_only() -> StorageHealthResult:
    try:
        storage_config = build_supabase_storage_config(settings)
    except StorageConfigurationError as error:
        return StorageHealthResult(
            status="not_configured",
            provider="supabase",
            bucket=settings.supabase_storage_bucket,
            detail=str(error),
            can_connect=False,
            bucket_available=False,
        )

    return StorageHealthResult(
        status="healthy",
        provider=SupabaseStorageProvider.provider_name,
        bucket=storage_config.bucket,
        detail="Storage configuration is present.",
        can_connect=False,
        bucket_available=False,
    )
