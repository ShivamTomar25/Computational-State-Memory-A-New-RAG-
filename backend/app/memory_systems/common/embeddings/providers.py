from __future__ import annotations

import hashlib
import importlib.util
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.config import settings


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    model_revision: str
    dimension: int
    normalization: str
    batch_size: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...

    def health(self) -> str:
        ...


@dataclass
class DeterministicEmbeddingProvider:
    provider_name: str = "deterministic"
    model_name: str = "sustha-deterministic-hash-embedding"
    model_revision: str = "1"
    dimension: int = 64
    normalization: str = "l2"
    batch_size: int = 32

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0 for _ in range(self.dimension)]

        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            value = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += value

        return normalize_vector(vector)

    def health(self) -> str:
        return "available"


class HuggingFaceLocalEmbeddingProvider:
    provider_name = "huggingface_local"

    def __init__(self) -> None:
        self.model_name = settings.memory_embedding_model
        self.model_revision = "configured"
        self.dimension = settings.memory_embedding_dimension
        self.normalization = "l2" if settings.memory_embedding_normalize else "none"
        self.batch_size = settings.memory_embedding_batch_size
        self._model = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=settings.memory_embedding_normalize,
        )

        return [list(map(float, embedding)) for embedding in embeddings]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def health(self) -> str:
        if importlib.util.find_spec("sentence_transformers") is None:
            return "provider_not_installed"

        return "available"

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                settings.memory_embedding_model,
                device=settings.memory_embedding_device,
            )
            self.dimension = int(self._model.get_sentence_embedding_dimension())

        return self._model


class UnavailableEmbeddingProvider:
    provider_name = "unavailable"
    model_name = "none"
    model_revision = "none"
    dimension = 0
    normalization = "none"
    batch_size = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding provider is unavailable.")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("Embedding provider is unavailable.")

    def health(self) -> str:
        return "provider_not_configured"


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    if settings.memory_embedding_provider == "huggingface_local":
        return HuggingFaceLocalEmbeddingProvider()

    if settings.memory_embedding_provider == "deterministic":
        return DeterministicEmbeddingProvider(
            model_name=settings.memory_embedding_model,
            dimension=settings.memory_embedding_dimension,
            batch_size=settings.memory_embedding_batch_size,
        )

    return UnavailableEmbeddingProvider()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    return sum(a * b for a, b in zip(left, right))


def normalize_vector(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))

    if length == 0:
        return vector

    return [value / length for value in vector]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in text.split() if token.strip()]
