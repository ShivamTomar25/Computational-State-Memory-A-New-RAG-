from __future__ import annotations

import unittest
from dataclasses import dataclass

from storage3.exceptions import StorageApiError

from app.storage.exceptions import (
    StorageAuthenticationError,
    StorageObjectConflict,
)
from app.storage.supabase.client import SupabaseStorageConfig
from app.storage.supabase.provider import SupabaseStorageProvider, map_supabase_error


@dataclass
class FakeUploadResponse:
    path: str
    full_path: str


class FakeBucket:
    def __init__(self):
        self.upload_calls = []
        self.remove_calls = []
        self.exists_value = True
        self.info_response = {
            "size": 12,
            "metadata": {
                "mimetype": "text/plain",
                "eTag": "etag-value",
            },
            "created_at": "2026-07-18T10:00:00+00:00",
        }

    def upload(self, path, content, file_options=None):
        self.upload_calls.append((path, content, file_options))

        return FakeUploadResponse(path=path, full_path=f"clinical-documents/{path}")

    def create_signed_upload_url(self, path):
        return {
            "signed_url": "https://storage.example/upload?token=private",
            "token": "private-token",
            "path": path,
        }

    def create_signed_url(self, path, expires_in):
        return {"signedUrl": f"https://storage.example/download/{path}?token=private"}

    def exists(self, path):
        return self.exists_value

    def info(self, path):
        return self.info_response

    def download(self, path):
        return b"hello"

    def remove(self, paths):
        self.remove_calls.append(paths)

        return [{"name": paths[0]}]


class FakeStorage:
    def __init__(self):
        self.bucket = FakeBucket()
        self.bucket_public = False

    def from_(self, bucket_name):
        return self.bucket

    def get_bucket(self, bucket_name):
        return type("Bucket", (), {"public": self.bucket_public})()


class FakeClient:
    def __init__(self):
        self.storage = FakeStorage()


class SupabaseStorageProviderTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.provider = SupabaseStorageProvider(
            client=self.client,
            config=SupabaseStorageConfig(
                url="https://example.supabase.co",
                secret_key="secret",
                bucket="clinical-documents",
                signed_upload_expiry_seconds=600,
                signed_download_expiry_seconds=300,
            ),
        )

    def test_upload_bytes_returns_normalized_result(self):
        result = self.provider.upload_bytes(
            object_path="development/test/object.txt",
            content=b"hello",
            content_type="text/plain",
        )

        self.assertEqual(result.bucket, "clinical-documents")
        self.assertEqual(result.object_path, "development/test/object.txt")
        self.assertEqual(
            self.client.storage.bucket.upload_calls[0][2]["upsert"],
            "false",
        )

    def test_signed_upload_returns_normalized_result(self):
        result = self.provider.create_signed_upload(
            object_path="development/test/object.txt",
            content_type="text/plain",
        )

        self.assertEqual(result.method, "PUT")
        self.assertEqual(result.token, "private-token")
        self.assertIsNone(result.expires_in)
        self.assertEqual(result.required_headers["content-type"], "text/plain")

    def test_signed_download_uses_configured_expiry(self):
        result = self.provider.create_signed_download(
            object_path="development/test/object.txt"
        )

        self.assertEqual(result.expires_in, 300)
        self.assertIn("https://storage.example/download", result.signed_url)

    def test_object_exists_returns_false_for_absent_object(self):
        self.client.storage.bucket.exists_value = False

        self.assertFalse(
            self.provider.object_exists(object_path="development/test/object.txt")
        )

    def test_metadata_mapping_does_not_fabricate_checksum(self):
        metadata = self.provider.get_object_metadata(
            object_path="development/test/object.txt"
        )

        self.assertEqual(metadata.size_bytes, 12)
        self.assertEqual(metadata.content_type, "text/plain")
        self.assertEqual(metadata.etag, "etag-value")
        self.assertIsNone(metadata.checksum)

    def test_download_bytes_delegates_to_bucket(self):
        content = self.provider.download_bytes(
            object_path="development/test/object.txt",
            max_bytes=10,
        )

        self.assertEqual(content, b"hello")

    def test_delete_delegates_to_bucket(self):
        self.provider.delete_object(object_path="development/test/object.txt")

        self.assertEqual(
            self.client.storage.bucket.remove_calls,
            [["development/test/object.txt"]],
        )

    def test_health_reports_public_bucket_as_degraded(self):
        self.client.storage.bucket_public = True

        result = self.provider.health_check()

        self.assertEqual(result.status, "degraded")

    def test_maps_duplicate_error(self):
        error = StorageApiError("resource already exists", "Duplicate", 409)

        with self.assertRaises(StorageObjectConflict):
            raise map_supabase_error(error, operation="upload")

    def test_maps_authentication_error_without_secret(self):
        error = StorageApiError("bad key", "Unauthorized", 401)

        with self.assertRaises(StorageAuthenticationError) as context:
            raise map_supabase_error(error, operation="upload")

        self.assertNotIn("secret", str(context.exception).lower())


if __name__ == "__main__":
    unittest.main()
