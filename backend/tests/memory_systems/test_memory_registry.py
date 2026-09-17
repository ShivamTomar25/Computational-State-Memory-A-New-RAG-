from __future__ import annotations

import unittest

from app.memory_systems.common.enums.status import SYSTEM_METADATA, SYSTEM_TYPES
from app.memory_systems.common.registry.registry import MemorySystemRegistry, registry
from app.memory_systems.common.services.memory_service import list_registry
from app.memory_systems.long_context.adapter import LongContextAdapter


class MemorySystemRegistryTests(unittest.TestCase):
    def test_registry_contains_exactly_the_supported_systems(self):
        self.assertEqual(registry.keys(), SYSTEM_TYPES)
        self.assertEqual(len(registry.all()), 9)
        self.assertNotIn("letta_memory", registry.keys())
        self.assertNotIn("letta_memory", SYSTEM_METADATA)

    def test_each_system_has_required_metadata(self):
        for system_type in SYSTEM_TYPES:
            metadata = SYSTEM_METADATA[system_type]

            self.assertTrue(metadata["display_name"])
            self.assertTrue(metadata["description"])
            self.assertIsInstance(metadata["supported_retrieval_modes"], list)
            self.assertGreater(len(metadata["supported_retrieval_modes"]), 0)

    def test_registry_response_excludes_letta(self):
        response = list_registry()
        system_types = [system.system_type for system in response]

        self.assertEqual(system_types, list(SYSTEM_TYPES))
        self.assertEqual(len(system_types), 9)
        self.assertNotIn("letta_memory", system_types)

    def test_duplicate_adapter_registration_is_rejected(self):
        local_registry = MemorySystemRegistry()
        adapter = LongContextAdapter()

        local_registry.register(adapter)

        with self.assertRaisesRegex(ValueError, "already registered"):
            local_registry.register(adapter)


if __name__ == "__main__":
    unittest.main()
