from __future__ import annotations

from app.memory_systems.hippo_rag.enums import HippoRAGProviderName
from app.memory_systems.hippo_rag.providers import OfficialHippoRAGLocalProvider, UnavailableHippoRAGProvider


def create_hipporag_provider(settings):
    provider_name = HippoRAGProviderName(settings.hipporag_provider)

    if provider_name == HippoRAGProviderName.OFFICIAL_LOCAL:
        return OfficialHippoRAGLocalProvider(
            storage_directory=settings.hipporag_storage_directory,
            embedding_model="facebook/contriever",
        )

    return UnavailableHippoRAGProvider()
