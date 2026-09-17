from __future__ import annotations

from dataclasses import dataclass
from app.memory_systems.graph_rag.enums import GraphRAGProviderName


@dataclass(frozen=True)
class UnavailableGraphRAGProvider:
    name: GraphRAGProviderName = GraphRAGProviderName.UNAVAILABLE

    def provider_status(self) -> str:
        return "provider_not_configured"

    def configuration(self) -> dict:
        return {
            "provider": self.name.value,
            "status": self.provider_status(),
        }


@dataclass(frozen=True)
class MicrosoftGraphRAGLocalProvider:
    storage_directory: str
    vector_store: str = "lancedb"
    name: GraphRAGProviderName = GraphRAGProviderName.MICROSOFT_LOCAL

    def provider_status(self) -> str:
        return "available"

    def configuration(self) -> dict:
        return {
            "provider": self.name.value,
            "status": self.provider_status(),
            "implementation": "sustha_local_graph",
            "storage_directory": self.storage_directory,
            "vector_store": self.vector_store,
        }
