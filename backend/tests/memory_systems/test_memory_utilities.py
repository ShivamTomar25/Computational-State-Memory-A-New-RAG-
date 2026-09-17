from __future__ import annotations

import unittest
from uuid import uuid4

from app.memory_systems.common.canonical.serializers import json_safe
from app.memory_systems.common.embeddings.providers import (
    DeterministicEmbeddingProvider,
    cosine_similarity,
)
from app.memory_systems.common.schemas.memory import MemoryContextItem
from app.memory_systems.common.token_budget.service import apply_token_budget, estimate_tokens


class MemoryUtilityTests(unittest.TestCase):
    def test_deterministic_embedding_repeats_for_same_text(self):
        provider = DeterministicEmbeddingProvider(dimension=16)

        first = provider.embed_query("blood pressure stable")
        second = provider.embed_query("blood pressure stable")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)
        self.assertAlmostEqual(cosine_similarity(first, first), 1.0)

    def test_token_budget_keeps_items_until_budget_is_full(self):
        items = [
            MemoryContextItem(rank=1, content_preview="one", token_count=2),
            MemoryContextItem(rank=2, content_preview="two", token_count=4),
            MemoryContextItem(rank=3, content_preview="three", token_count=3),
        ]

        result = apply_token_budget(items, token_budget=6)

        self.assertEqual([item.rank for item in result.included], [1, 2])
        self.assertEqual(result.excluded_count, 1)
        self.assertEqual(result.token_count, 6)

    def test_token_estimation_is_never_zero_for_content(self):
        self.assertEqual(estimate_tokens("abc"), 1)
        self.assertGreater(estimate_tokens("clinical note with multiple words"), 1)

    def test_json_safe_converts_uuid_values(self):
        value = uuid4()

        self.assertEqual(json_safe(value), str(value))


if __name__ == "__main__":
    unittest.main()
