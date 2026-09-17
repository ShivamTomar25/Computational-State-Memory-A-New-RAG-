# Letta Removal

Letta/MemGPT is not an active memory system in Sustha.

Active comparison systems:

- `long_context`
- `rolling_summary`
- `dense_rag`
- `hybrid_rag`
- `graph_rag`
- `hippo_rag`
- `csm`

The backend registry no longer imports or registers `letta_memory`. Startup no longer imports Letta models, and `LETTA_PROVIDER` is not part of the runtime configuration.

The project does not currently have an Alembic environment. If an existing local database already has old Letta tables from previous `create_all()` runs, leave them untouched or drop them manually in that local database after confirming no data needs to be preserved. New API responses do not expose `letta_memory`.
