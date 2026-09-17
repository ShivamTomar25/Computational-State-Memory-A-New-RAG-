from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.memory_systems.graph_rag.enums import GraphRAGProviderName
from app.memory_systems.graph_rag.factory import create_graphrag_provider
from app.memory_systems.graph_rag.providers import MicrosoftGraphRAGLocalProvider, UnavailableGraphRAGProvider
from app.memory_systems.hippo_rag.enums import HippoRAGProviderName
from app.memory_systems.hippo_rag.factory import create_hipporag_provider
from app.memory_systems.hippo_rag.providers import OfficialHippoRAGLocalProvider, UnavailableHippoRAGProvider


class ProviderFactoryTests(unittest.TestCase):
    def test_unavailable_providers_are_selected_by_default(self):
        settings = SimpleNamespace(
            graphrag_provider=GraphRAGProviderName.UNAVAILABLE,
            graphrag_storage_directory=".local/graphrag",
            hipporag_provider=HippoRAGProviderName.UNAVAILABLE,
            hipporag_storage_directory=".local/hipporag",
        )

        self.assertIsInstance(create_graphrag_provider(settings), UnavailableGraphRAGProvider)
        self.assertIsInstance(create_hipporag_provider(settings), UnavailableHippoRAGProvider)

    def test_local_graphrag_provider_uses_storage_directory_and_lancedb(self):
        settings = SimpleNamespace(
            graphrag_provider="microsoft_graphrag_local",
            graphrag_storage_directory="/tmp/graphrag",
        )

        provider = create_graphrag_provider(settings)

        self.assertIsInstance(provider, MicrosoftGraphRAGLocalProvider)
        self.assertEqual(provider.storage_directory, "/tmp/graphrag")
        self.assertEqual(provider.vector_store, "lancedb")

    def test_local_hipporag_provider_uses_storage_directory_and_contriever(self):
        settings = SimpleNamespace(
            hipporag_provider="official_hipporag_local",
            hipporag_storage_directory="/tmp/hipporag",
        )

        provider = create_hipporag_provider(settings)

        self.assertIsInstance(provider, OfficialHippoRAGLocalProvider)
        self.assertEqual(provider.storage_directory, "/tmp/hipporag")
        self.assertEqual(provider.embedding_model, "facebook/contriever")


if __name__ == "__main__":
    unittest.main()
