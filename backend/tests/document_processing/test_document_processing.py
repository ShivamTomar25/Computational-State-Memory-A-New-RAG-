from __future__ import annotations

import unittest

from app.document.exceptions import UnsupportedDocumentFormat
from app.document_processing.detectors.file_signature import detect_file_signature
from app.document_processing.detectors.ocr_requirement import classify_ocr_requirement
from app.document_processing.detectors.pdf_text_quality import assess_text_quality
from app.document_processing.extractors.plain_text import PlainTextExtractor


class DocumentProcessingTests(unittest.TestCase):
    def test_detects_text_document_from_bytes(self):
        result = detect_file_signature(
            content=b"Patient report\nHbA1c improved.",
            filename="report.txt",
            declared_content_type="text/plain",
        )

        self.assertEqual(result.content_type, "text/plain")
        self.assertEqual(result.family, "text")

    def test_rejects_executable_content(self):
        with self.assertRaises(UnsupportedDocumentFormat):
            detect_file_signature(
                content=b"MZ\x00\x00",
                filename="report.txt",
                declared_content_type="text/plain",
            )

    def test_plain_text_extractor_normalizes_text(self):
        result = PlainTextExtractor().extract(
            b"Assessment:\r\n  Blood pressure stable.\r\n\r\nPlan: follow up."
        )

        self.assertEqual(result.page_count if hasattr(result, "page_count") else len(result.pages), 1)
        self.assertIn("Blood pressure stable.", result.normalized_text)
        self.assertGreater(result.pages[0].word_count, 3)

    def test_ocr_classification_for_empty_text(self):
        result = PlainTextExtractor().extract(b"   ")
        quality = assess_text_quality(result.pages)
        ocr = classify_ocr_requirement(quality)

        self.assertEqual(ocr.status, "required")


if __name__ == "__main__":
    unittest.main()
