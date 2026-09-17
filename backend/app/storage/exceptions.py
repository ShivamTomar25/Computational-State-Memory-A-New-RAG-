from __future__ import annotations


class StorageProviderError(Exception):
    pass


class StorageConfigurationError(StorageProviderError):
    pass


class StorageConnectionError(StorageProviderError):
    pass


class StorageAuthenticationError(StorageProviderError):
    pass


class StorageAuthorizationError(StorageProviderError):
    pass


class StorageBucketNotFound(StorageProviderError):
    pass


class StorageObjectNotFound(StorageProviderError):
    pass


class StorageObjectConflict(StorageProviderError):
    pass


class StorageUploadError(StorageProviderError):
    pass


class StorageDownloadSigningError(StorageProviderError):
    pass


class StorageUploadSigningError(StorageProviderError):
    pass


class StorageInvalidPath(StorageProviderError):
    pass


class StorageInvalidFilename(StorageProviderError):
    pass


class StorageUnsupportedContentType(StorageProviderError):
    pass


class StorageFileTooLarge(StorageProviderError):
    pass


class StorageEmptyFile(StorageProviderError):
    pass
