# Migrations

This backend currently initializes tables through `Base.metadata.create_all()` in `app/database.py`.

No Alembic environment exists in the project yet. The memory-system SQLAlchemy models are imported in `init_db()` so new local databases create the memory tables automatically on startup.

Before production deployment, add Alembic and generate an initial migration from:

`app/memory_systems/common/models/memory.py`

and each system folder:

`long_context`, `rolling_summary`, `dense_rag`, `hybrid_rag`, `graph_rag`, `hippo_rag`, `csm`.

Also include:

`app/llm/common/models/llm.py`
