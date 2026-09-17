from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class MemoryWorkflowState(TypedDict, total=False):
    authorized: bool
    sources_collected: bool
    sources_normalized: bool
    diff_calculated: bool
    capabilities_validated: bool
    system_invoked: bool
    links_persisted: bool
    finalized: bool
    failed: bool


def build_ingestion_graph():
    graph = StateGraph(MemoryWorkflowState)
    graph.add_node("authorize_scope", mark("authorized"))
    graph.add_node("collect_sources", mark("sources_collected"))
    graph.add_node("normalize_sources", mark("sources_normalized"))
    graph.add_node("calculate_diff", mark("diff_calculated"))
    graph.add_node("validate_capabilities", mark("capabilities_validated"))
    graph.add_node("invoke_system_ingestion", mark("system_invoked"))
    graph.add_node("persist_source_links", mark("links_persisted"))
    graph.add_node("finalize_run", mark("finalized"))
    graph.add_edge(START, "authorize_scope")
    graph.add_edge("authorize_scope", "collect_sources")
    graph.add_edge("collect_sources", "normalize_sources")
    graph.add_edge("normalize_sources", "calculate_diff")
    graph.add_edge("calculate_diff", "validate_capabilities")
    graph.add_edge("validate_capabilities", "invoke_system_ingestion")
    graph.add_edge("invoke_system_ingestion", "persist_source_links")
    graph.add_edge("persist_source_links", "finalize_run")
    graph.add_edge("finalize_run", END)

    return graph.compile()


def build_retrieval_graph():
    graph = StateGraph(MemoryWorkflowState)
    graph.add_node("authorize_scope", mark("authorized"))
    graph.add_node("load_system_instance", mark("capabilities_validated"))
    graph.add_node("validate_readiness", mark("diff_calculated"))
    graph.add_node("normalize_query", mark("sources_normalized"))
    graph.add_node("invoke_system_retriever", mark("system_invoked"))
    graph.add_node("deduplicate_results", mark("links_persisted"))
    graph.add_node("persist_retrieval_trace", mark("finalized"))
    graph.add_edge(START, "authorize_scope")
    graph.add_edge("authorize_scope", "load_system_instance")
    graph.add_edge("load_system_instance", "validate_readiness")
    graph.add_edge("validate_readiness", "normalize_query")
    graph.add_edge("normalize_query", "invoke_system_retriever")
    graph.add_edge("invoke_system_retriever", "deduplicate_results")
    graph.add_edge("deduplicate_results", "persist_retrieval_trace")
    graph.add_edge("persist_retrieval_trace", END)

    return graph.compile()


def build_conversation_graph():
    graph = StateGraph(MemoryWorkflowState)
    graph.add_node("authorize_conversation", mark("authorized"))
    graph.add_node("append_user_message", mark("sources_collected"))
    graph.add_node("sync_new_message_to_own_system", mark("system_invoked"))
    graph.add_node("retrieve_context", mark("links_persisted"))
    graph.add_node("mark_generation_not_configured", mark("finalized"))
    graph.add_edge(START, "authorize_conversation")
    graph.add_edge("authorize_conversation", "append_user_message")
    graph.add_edge("append_user_message", "sync_new_message_to_own_system")
    graph.add_edge("sync_new_message_to_own_system", "retrieve_context")
    graph.add_edge("retrieve_context", "mark_generation_not_configured")
    graph.add_edge("mark_generation_not_configured", END)

    return graph.compile()


def mark(field: str):
    def node(state: MemoryWorkflowState) -> MemoryWorkflowState:
        return {**state, field: True}

    return node
