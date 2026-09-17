from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.config import Settings
from app.storage.exceptions import StorageConfigurationError
from app.storage.health import check_storage_readiness
from app.storage.schemas import StorageHealthResult
from app.storage.supabase.client import build_supabase_storage_config


class StorageConfigAndHealthTests(unittest.TestCase):
    def test_valid_storage_config_loads(self):
        config = Settings(
            _env_file=None,
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            jwt_secret_key="secret",
            supabase_url="https://project.supabase.co",
            supabase_secret_key="backend-secret",
        )

        storage_config = build_supabase_storage_config(config)

        self.assertEqual(storage_config.bucket, "clinical-documents")

    def test_missing_supabase_url_is_clear(self):
        config = Settings(
            _env_file=None,
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            jwt_secret_key="secret",
            supabase_url=None,
            supabase_secret_key="backend-secret",
        )

        with self.assertRaisesRegex(StorageConfigurationError, "SUPABASE_URL"):
            build_supabase_storage_config(config)

    def test_missing_secret_key_is_clear(self):
        config = Settings(
            _env_file=None,
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            jwt_secret_key="secret",
            supabase_url="https://project.supabase.co",
            supabase_secret_key=None,
        )

        with self.assertRaisesRegex(StorageConfigurationError, "SUPABASE_SECRET_KEY"):
            build_supabase_storage_config(config)

    def test_invalid_expiry_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                database_url="postgresql+psycopg://user:pass@localhost:5432/db",
                jwt_secret_key="secret",
                supabase_signed_download_expiry_seconds=0,
            )

    def test_empty_bucket_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                database_url="postgresql+psycopg://user:pass@localhost:5432/db",
                jwt_secret_key="secret",
                supabase_storage_bucket=" ",
            )

    def test_storage_health_missing_config_returns_not_configured(self):
        def provider_factory():
            raise StorageConfigurationError("SUPABASE_URL is required.")

        result = check_storage_readiness(provider_factory=provider_factory)

        self.assertEqual(result.status, "not_configured")
        self.assertNotIn("backend-secret", result.detail)

    def test_liveness_style_health_can_remain_healthy_when_storage_down(self):
        def provider_factory():
            return type(
                "Provider",
                (),
                {
                    "health_check": lambda self: StorageHealthResult(
                        status="unavailable",
                        provider="supabase",
                        bucket="clinical-documents",
                        detail="Storage provider is unavailable.",
                        can_connect=False,
                        bucket_available=False,
                    )
                },
            )()

        result = check_storage_readiness(provider_factory=provider_factory)

        self.assertEqual(result.status, "unavailable")


if __name__ == "__main__":
    unittest.main()
