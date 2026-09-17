from __future__ import annotations


class MemorySystemError(Exception):
    pass


class MemorySystemNotFound(MemorySystemError):
    pass


class MemorySystemNotInitialized(MemorySystemError):
    pass


class MemorySystemNotReady(MemorySystemError):
    pass


class MemorySystemUnavailable(MemorySystemError):
    pass


class MemorySystemRequiresLLM(MemorySystemError):
    pass


class EmbeddingProviderUnavailable(MemorySystemError):
    pass


class GraphProviderUnavailable(MemorySystemError):
    pass


class HippoRAGProviderUnavailable(MemorySystemError):
    pass


class IngestionAlreadyRunning(MemorySystemError):
    pass


class IngestionRunNotFound(MemorySystemError):
    pass


class InvalidSystemTransition(MemorySystemError):
    pass


class ConversationNotFound(MemorySystemError):
    pass


class ConversationSystemMismatch(MemorySystemError):
    pass


class RetrievalNotAvailable(MemorySystemError):
    pass


class InvalidRetrievalMode(MemorySystemError):
    pass


class VectorIndexUnavailable(MemorySystemError):
    pass


class CanonicalSourceConflict(MemorySystemError):
    pass


class StaleSystemIndex(MemorySystemError):
    pass


class ContextBudgetExceeded(MemorySystemError):
    pass


class ProviderDependencyMissing(MemorySystemError):
    pass
