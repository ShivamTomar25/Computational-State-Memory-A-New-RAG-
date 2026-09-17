from __future__ import annotations

import unittest

from app.storage.exceptions import (
    StorageEmptyFile,
    StorageFileTooLarge,
    StorageInvalidFilename,
    StorageUnsupportedContentType,
)
from app.storage.file_policy import DocumentFilePolicy, normalize_content_type
from app.storage.schemas import UploadFileMetadata


class FilePolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = DocumentFilePolicy(
            allowed_content_types={
                "application/pdf",
                "text/plain",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
            max_size_bytes=20,
        )

    def test_accepts_pdf(self):
        result = self.policy.validate_upload_metadata(
            UploadFileMetadata(
                filename="report.pdf",
                content_type="application/pdf",
                size_bytes=10,
            )
        )

        self.assertEqual(result.safe_filename, "report.pdf")
        self.assertEqual(result.normalized_content_type, "application/pdf")

    def test_accepts_text_with_charset(self):
        result = self.policy.validate_upload_metadata(
            UploadFileMetadata(
                filename="notes.txt",
                content_type="text/plain; charset=utf-8",
                size_bytes=10,
            )
        )

        self.assertEqual(result.normalized_content_type, "text/plain")

    def test_accepts_docx(self):
        result = self.policy.validate_upload_metadata(
            UploadFileMetadata(
                filename="summary.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                size_bytes=10,
            )
        )

        self.assertEqual(result.extension, "docx")

    def test_rejects_executable_content_type(self):
        with self.assertRaises(StorageUnsupportedContentType):
            self.policy.validate_upload_metadata(
                UploadFileMetadata(
                    filename="tool.exe",
                    content_type="application/x-msdownload",
                    size_bytes=10,
                )
            )

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(StorageInvalidFilename):
            self.policy.validate_upload_metadata(
                UploadFileMetadata(
                    filename="report.exe",
                    content_type="application/pdf",
                    size_bytes=10,
                )
            )

    def test_rejects_zero_bytes(self):
        with self.assertRaises(StorageEmptyFile):
            self.policy.validate_upload_metadata(
                UploadFileMetadata(
                    filename="report.pdf",
                    content_type="application/pdf",
                    size_bytes=0,
                )
            )

    def test_rejects_oversized_file(self):
        with self.assertRaises(StorageFileTooLarge):
            self.policy.validate_upload_metadata(
                UploadFileMetadata(
                    filename="report.pdf",
                    content_type="application/pdf",
                    size_bytes=21,
                )
            )

    def test_rejects_malformed_checksum(self):
        with self.assertRaises(StorageInvalidFilename):
            self.policy.validate_upload_metadata(
                UploadFileMetadata(
                    filename="report.pdf",
                    content_type="application/pdf",
                    size_bytes=10,
                    checksum_sha256="abc",
                )
            )

    def test_normalizes_content_type(self):
        self.assertEqual(
            normalize_content_type(" Text/Plain; Charset=UTF-8 "),
            "text/plain",
        )


if __name__ == "__main__":
    unittest.main()
