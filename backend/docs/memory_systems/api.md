# Memory Systems API

All patient-scoped routes require the logged-in doctor bearer token.

## Registry

`GET /api/memory-systems`

Returns the eight configured systems, their capabilities, retrieval modes, and provider status.

## Patient Systems

`GET /api/patients/{patient_id}/memory-systems`

Returns one entry for each supported system. Uninitialized systems are returned with `id: null`.

`POST /api/patients/{patient_id}/memory-systems/{system_type}/initialize`

Creates the patient-specific system instance.

`POST /api/patients/{patient_id}/memory-systems/{system_type}/sync`

Collects canonical sources and indexes them into that system.

`POST /api/patients/{patient_id}/memory-systems/{system_type}/rebuild`

Clears system source links and rebuilds with `confirm_rebuild: true`.

`GET /api/patients/{patient_id}/memory-systems/{system_type}/status`

Returns configuration, status, capability status, and storage statistics.

`GET /api/patients/{patient_id}/memory-systems/{system_type}/statistics`

Returns source counts and native system storage counts.

## Runs

`GET /api/patients/{patient_id}/memory-systems/{system_type}/runs`

Lists ingestion runs for the patient and system.

`GET /api/patients/{patient_id}/memory-systems/{system_type}/runs/{run_id}`

Returns one ingestion run with source-level items.

## Retrieval

`POST /api/patients/{patient_id}/memory-systems/{system_type}/retrieve`

Request body:

```json
{
  "query": "blood pressure history",
  "top_k": 8,
  "token_budget": 6000,
  "retrieval_mode": null,
  "conversation_id": null,
  "include_content": true,
  "include_citations": true
}
```

Response includes context items, citations, readiness status, warnings, and `generation_status`.

## Conversations

`POST /api/patients/{patient_id}/memory-systems/{system_type}/conversations`

Creates a system-private conversation.

`GET /api/patients/{patient_id}/memory-systems/{system_type}/conversations`

Lists conversations for only that patient and system.

`GET /api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation_id}/messages`

Lists messages for only that conversation and system.

`POST /api/patients/{patient_id}/memory-systems/{system_type}/conversations/{conversation_id}/messages`

Stores the user message, syncs that message into the same system only, retrieves context, and then asks the configured LLM provider for a grounded answer.

If no LLM key is configured, the response returns `generation_status: "not_configured"` and `assistant_message: null`.

When generation succeeds, the response includes `assistant_message`, `answer`, `llm_call_id`, model metadata, token counts, latency, citations, and warnings.
