# Stabilization Report

## Repository Shape

The backend is organized by task folders: `doctor`, `patient`, `patient_information`, `document`, `document_processing`, `storage`, `memory_systems`, `llm`, and `health`.

The frontend is JavaScript/JSX and keeps backend API calls in `src/services`. Page code remains under `src/pages`.

## Baseline Checks

Backend compile check passed:

```bash
/usr/bin/env PYTHONPYCACHEPREFIX=/private/tmp/sustha-pycache venv/bin/python -m compileall app
```

Backend tests passed:

```bash
/usr/bin/env PYTHONPYCACHEPREFIX=/private/tmp/sustha-pycache venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Result:

```text
Ran 52 tests in 0.054s
OK
```

Frontend production build passed:

```bash
npm run build
```

## Database And Migrations

The project does not currently include a full Alembic environment. `migrations/README.md` states that the backend uses `Base.metadata.create_all()` through `app/database.py`.

`init_db()` imports the existing domain models and the new LLM call model so local startup creates the required tables.

## Memory Systems

The registry exposes the seven active memory systems:

- `long_context`
- `rolling_summary`
- `dense_rag`
- `hybrid_rag`
- `graph_rag`
- `hippo_rag`
- `csm`

Conversation posting remains system-private. The posted message is synchronized only into the active system, retrieval is run only for that system, and an assistant message is created only when grounded generation succeeds.

## Groq And LLM

The exposed Groq key from chat was not written to source, docs, frontend code, tests, or `.env.example`.

Groq is integrated behind `app/llm` with separate provider, schema, service, repository, prompt, safety, and API files.

`/api/llm/status` returns sanitized readiness data only. It never returns the key.

If `GROQ_API_KEY` is empty, patient chat returns `generation_status: "not_configured"` and does not create an assistant message.

## Frontend Integration

The memory registry page reads `/api/llm/status` and displays sanitized provider status.

The system workspace consumes the message API response fields for:

- generation status
- assistant message
- grounded answer
- citations
- model and prompt version
- token counts
- latency
- warnings

## Remaining Limitations

OCR is not implemented in this pass. The current repository still has pre-OCR document processing and OCR-requirement detection only.

There is no Alembic migration environment yet, so migration upgrade/downgrade checks cannot be run.

Rolling Summary, GraphRAG, HippoRAG, and CSM still need their full LLM-ingestion implementations. Current final-answer generation uses their existing retrieval output through the common answer service.

Streaming is not implemented yet.
