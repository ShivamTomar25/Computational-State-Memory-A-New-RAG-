from __future__ import annotations

from app.memory_systems.graph_rag.enums import GraphRAGProviderName
from app.memory_systems.graph_rag.providers import MicrosoftGraphRAGLocalProvider, UnavailableGraphRAGProvider


def create_graphrag_provider(settings):
    provider_name = GraphRAGProviderName(settings.graphrag_provider)

    if provider_name == GraphRAGProviderName.MICROSOFT_LOCAL:
        return MicrosoftGraphRAGLocalProvider(
            storage_directory=settings.graphrag_storage_directory,
            vector_store="lancedb",
        )

    return UnavailableGraphRAGProvider()
