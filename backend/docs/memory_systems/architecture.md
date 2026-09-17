# Memory Systems Architecture

The memory-system backend is separated by responsibility so each issue has one place to inspect.

## Folder Layout

`app/memory_systems/common`

Shared infrastructure used by every memory system.

| Folder | Purpose |
| --- | --- |
| `api` | FastAPI routes for registry, initialization, sync, retrieval, runs, and conversations. |
| `canonical` | Converts patient information, processed documents, and system-private messages into canonical memory sources. |
| `embeddings` | Embedding provider interface and deterministic local embedding provider. |
| `enums` | Stable system identifiers and metadata. |
| `exceptions` | Typed memory-system errors. |
| `llm` | LLM provider interface. No live LLM answer generation is enabled yet. |
| `models` | Shared SQLAlchemy tables for systems, sources, runs, conversations, retrieval traces, and events. |
| `registry` | Registers the seven active memory-system adapters. |
| `repositories` | Database access helpers. |
| `retrieval` | Chunking and LangChain document conversion helpers. |
| `schemas` | Pydantic request and response models. |
| `services` | Business flow for initialize, sync, rebuild, retrieve, and conversation messages. |
| `token_budget` | Token estimation and context-budget filtering. |
| `workflows` | LangGraph workflow skeletons for ingestion, retrieval, and conversation flow. |

## System Folders

Each memory system has its own folder with its own `models.py` and `adapter.py`.

| Folder | Current behavior |
| --- | --- |
| `long_context` | Stores ordered context entries and retrieves by chronological priority under a token budget. |
| `rolling_summary` | Stores pending inputs and recent-window items. Summary generation returns `requires_llm`. |
| `dense_rag` | Chunks canonical sources and stores deterministic local embedding vectors in PostgreSQL JSONB. |
| `hybrid_rag` | Combines deterministic dense ranking with lexical matching and reciprocal-rank fusion. |
| `graph_rag` | Stages GraphRAG text units. Entity and community extraction return `requires_llm`. |
| `hippo_rag` | Stages HippoRAG passage nodes and index runs. OpenIE graph construction returns `requires_llm`. |
| `csm` | Builds deterministic state variables from structured patient information with evidence lineage. |

## Isolation Rules

Patient-shared sources are visible to every memory system for the same patient.

System-private conversation sources are visible only to the memory-system instance that created them.

Every request checks the logged-in doctor owns the patient before reading or writing memory-system records.

## Current Limits

Common grounded answer generation is enabled through `app/llm`. If no replacement Groq key is configured, conversation responses return `generation_status: "not_configured"` and no assistant message is stored.

OCR is not performed by memory systems. Only already processed document text is indexed.

`dense_rag` and `hybrid_rag` use deterministic local embeddings so smoke tests can run without external providers.
