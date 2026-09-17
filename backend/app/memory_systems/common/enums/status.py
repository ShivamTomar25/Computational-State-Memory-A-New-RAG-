from __future__ import annotations


SYSTEM_TYPES = (
    "long_context",
    "rolling_summary",
    "dense_rag",
    "hybrid_rag",
    "graph_rag",
    "hippo_rag",
    "csm",
    "csm_v3",
    "csm_v4",
)

CAPABILITY_STATES = {
    "available",
    "ready",
    "not_initialized",
    "initializing",
    "syncing",
    "stale",
    "degraded",
    "failed",
    "requires_embeddings",
    "requires_llm",
    "provider_not_installed",
    "provider_not_configured",
    "unavailable",
    "not_ready",
}

CANONICAL_SOURCE_TYPES = {
    "patient_information",
    "document",
    "conversation",
}

CANONICAL_SOURCE_SUBTYPES = {
    "encounter",
    "condition",
    "medication",
    "allergy",
    "measurement",
    "clinical_note",
    "document",
    "page",
    "section",
    "extracted_text",
    "user_message",
    "assistant_message",
    "system_message",
}

VISIBILITY_SCOPES = {
    "patient_shared",
    "system_private",
}

CONVERSATION_ROLES = {
    "user",
    "assistant",
    "system",
}

SYSTEM_METADATA = {
    "long_context": {
        "display_name": "Long Context",
        "description": "Ordered full-context baseline with deterministic token-budget truncation.",
        "requires_embeddings": False,
        "requires_llm": False,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["context"],
    },
    "rolling_summary": {
        "display_name": "Rolling Summary",
        "description": "Summary plus recent-window baseline; live summarization waits for the LLM phase.",
        "requires_embeddings": False,
        "requires_llm": True,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["summary"],
    },
    "dense_rag": {
        "display_name": "Dense RAG",
        "description": "Deterministic dense-vector retrieval over patient information, documents, and own conversation.",
        "requires_embeddings": True,
        "requires_llm": False,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["similarity"],
    },
    "hybrid_rag": {
        "display_name": "Hybrid RAG",
        "description": "Dense retrieval plus PostgreSQL-style lexical ranking with reciprocal-rank fusion.",
        "requires_embeddings": True,
        "requires_llm": False,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["hybrid"],
    },
    "graph_rag": {
        "display_name": "GraphRAG",
        "description": "Adapter-based GraphRAG baseline; graph extraction requires a configured LLM provider.",
        "requires_embeddings": True,
        "requires_llm": True,
        "requires_external_provider": True,
        "supported_retrieval_modes": ["local", "global"],
    },
    "hippo_rag": {
        "display_name": "HippoRAG",
        "description": "Adapter-based HippoRAG passage and graph baseline; OpenIE requires a configured LLM provider.",
        "requires_embeddings": True,
        "requires_llm": True,
        "requires_external_provider": True,
        "supported_retrieval_modes": ["ppr"],
    },
    "csm": {
        "display_name": "Computational State Memory",
        "description": "Deterministic state-memory foundation with evidence lineage and activation traces.",
        "requires_embeddings": False,
        "requires_llm": False,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["activation"],
    },
    "csm_v3": {
        "display_name": "CSM v3",
        "description": "Evidence-derived executable state memory with controlled state schema and selective activation.",
        "requires_embeddings": False,
        "requires_llm": False,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["activation"],
    },
    "csm_v4": {
        "display_name": "CSM v4",
        "description": "Balanced evidence-derived executable state memory with adaptive activation and evidence fallback.",
        "requires_embeddings": False,
        "requires_llm": False,
        "requires_external_provider": False,
        "supported_retrieval_modes": ["activation"],
    },
}
