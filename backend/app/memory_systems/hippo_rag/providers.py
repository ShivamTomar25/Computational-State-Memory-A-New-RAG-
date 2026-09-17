from __future__ import annotations

from dataclasses import dataclass
from app.memory_systems.hippo_rag.enums import HippoRAGProviderName


@dataclass(frozen=True)
class UnavailableHippoRAGProvider:
    name: HippoRAGProviderName = HippoRAGProviderName.UNAVAILABLE

    def provider_status(self) -> str:
        return "provider_not_configured"

    def openie_status(self) -> str:
        return "unavailable"

    def configuration(self) -> dict:
        return {
            "provider": self.name.value,
            "status": self.provider_status(),
            "openie_provider": self.openie_status(),
            "ppr": {"status": "not_ready"},
        }


@dataclass(frozen=True)
class OfficialHippoRAGLocalProvider:
    storage_directory: str
    embedding_model: str = "facebook/contriever"
    name: HippoRAGProviderName = HippoRAGProviderName.OFFICIAL_LOCAL

    def provider_status(self) -> str:
        return "available"

    def openie_status(self) -> str:
        return "local_entity_extraction"

    def configuration(self) -> dict:
        return {
            "provider": self.name.value,
            "status": self.provider_status(),
            "implementation": "sustha_local_hippo_graph",
            "storage_directory": self.storage_directory,
            "embedding_model": self.embedding_model,
            "openie_provider": self.openie_status(),
            "ppr": {"status": "available", "mode": "local_entity_propagation"},
        }
