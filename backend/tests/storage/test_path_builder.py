from __future__ import annotations

import unittest
from uuid import UUID

from app.storage.exceptions import StorageInvalidFilename, StorageInvalidPath
from app.storage.path_builder import (
    build_derived_text_path,
    build_metadata_path,
    build_original_document_path,
    build_page_artifact_path,
    sanitize_filename,
    validate_object_path,
)


PATIENT_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")


class StoragePathBuilderTests(unittest.TestCase):
    def test_original_document_path_uses_uuids_and_safe_filename(self):
        path = build_original_document_path(
            environment="Development",
            patient_id=PATIENT_ID,
            document_id=DOCUMENT_ID,
            filename="Lab Result Final.pdf",
        )

        self.assertEqual(
            path,
            (
                "development/patients/11111111-1111-4111-8111-111111111111/"
                "documents/22222222-2222-4222-8222-222222222222/original/"
                "Lab-Result-Final.pdf"
            ),
        )

    def test_derived_paths_are_deterministic(self):
        self.assertEqual(
            build_derived_text_path(
                environment="development",
                patient_id=PATIENT_ID,
                document_id=DOCUMENT_ID,
            ),
            (
                "development/patients/11111111-1111-4111-8111-111111111111/"
                "documents/22222222-2222-4222-8222-222222222222/derived/"
                "extracted-text.txt"
            ),
        )
        self.assertTrue(
            build_metadata_path(
                environment="development",
                patient_id=PATIENT_ID,
                document_id=DOCUMENT_ID,
            ).endswith("/derived/metadata.json")
        )
        self.assertTrue(
            build_page_artifact_path(
                environment="development",
                patient_id=PATIENT_ID,
                document_id=DOCUMENT_ID,
                page_number=3,
            ).endswith("/derived/pages/3.png")
        )

    def test_sanitize_filename_rejects_path_traversal(self):
        with self.assertRaises(StorageInvalidFilename):
            sanitize_filename("../report.pdf")

    def test_sanitize_filename_rejects_empty_filename(self):
        with self.assertRaises(StorageInvalidFilename):
            sanitize_filename("   ")

    def test_validate_object_path_rejects_leading_slash(self):
        with self.assertRaises(StorageInvalidPath):
            validate_object_path("/development/object.txt")

    def test_validate_object_path_normalizes_duplicate_separators(self):
        self.assertEqual(
            validate_object_path("development//folder///object.txt"),
            "development/folder/object.txt",
        )


if __name__ == "__main__":
    unittest.main()
