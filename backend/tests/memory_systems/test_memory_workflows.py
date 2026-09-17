from __future__ import annotations

import unittest

from app.memory_systems.common.workflows.graphs import (
    build_conversation_graph,
    build_ingestion_graph,
    build_retrieval_graph,
)


class MemoryWorkflowTests(unittest.TestCase):
    def test_ingestion_workflow_runs_all_markers(self):
        result = build_ingestion_graph().invoke({})

        self.assertTrue(result["authorized"])
        self.assertTrue(result["sources_collected"])
        self.assertTrue(result["sources_normalized"])
        self.assertTrue(result["diff_calculated"])
        self.assertTrue(result["capabilities_validated"])
        self.assertTrue(result["system_invoked"])
        self.assertTrue(result["links_persisted"])
        self.assertTrue(result["finalized"])

    def test_retrieval_workflow_runs_all_markers(self):
        result = build_retrieval_graph().invoke({})

        self.assertTrue(result["authorized"])
        self.assertTrue(result["capabilities_validated"])
        self.assertTrue(result["sources_normalized"])
        self.assertTrue(result["system_invoked"])
        self.assertTrue(result["links_persisted"])
        self.assertTrue(result["finalized"])

    def test_conversation_workflow_runs_all_markers(self):
        result = build_conversation_graph().invoke({})

        self.assertTrue(result["authorized"])
        self.assertTrue(result["sources_collected"])
        self.assertTrue(result["system_invoked"])
        self.assertTrue(result["links_persisted"])
        self.assertTrue(result["finalized"])


if __name__ == "__main__":
    unittest.main()
