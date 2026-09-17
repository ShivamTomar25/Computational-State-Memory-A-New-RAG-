from __future__ import annotations


class DocumentError(Exception):
    pass


class DocumentNotFound(DocumentError):
    pass


class DocumentConflict(DocumentError):
    pass


class DocumentUploadExpired(DocumentError):
    pass


class DocumentAlreadyUploaded(DocumentError):
    pass


class DocumentNotUploaded(DocumentError):
    pass


class DocumentNotVerified(DocumentError):
    pass


class DocumentInactive(DocumentError):
    pass


class InvalidDocumentStatusTransition(DocumentError):
    pass


class InvalidDocumentType(DocumentError):
    pass


class InvalidDocumentDate(DocumentError):
    pass


class EncounterDocumentMismatch(DocumentError):
    pass


class DocumentStorageMismatch(DocumentError):
    pass


class DocumentObjectMissing(DocumentError):
    pass


class DocumentSizeMismatch(DocumentError):
    pass


class DocumentChecksumMismatch(DocumentError):
    pass


class DocumentContentTypeMismatch(DocumentError):
    pass


class UnsupportedDocumentFormat(DocumentError):
    pass


class MalformedDocument(DocumentError):
    pass


class EncryptedPdfUnsupported(DocumentError):
    pass


class PasswordProtectedPdf(DocumentError):
    pass


class TextExtractionFailed(DocumentError):
    pass


class NoExtractableText(DocumentError):
    pass


class LowQualityExtractedText(DocumentError):
    pass


class OcrRequired(DocumentError):
    pass


class ProcessingAlreadyRunning(DocumentError):
    pass


class ProcessingNotAllowed(DocumentError):
    pass


class ProcessingJobNotFound(DocumentError):
    pass


class ProcessingRetryExhausted(DocumentError):
    pass


class DerivedArtifactFailure(DocumentError):
    pass
