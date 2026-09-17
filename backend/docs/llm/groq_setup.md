# Groq LLM Setup

The pasted Groq key from chat is exposed and must not be used. Revoke it in Groq, create a replacement key, and place only the replacement value in `backend/.env`.

```env
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
LLM_PROVIDER=groq
LLM_EXTERNAL_DATA_MODE=synthetic_or_deidentified
LLM_ALLOW_IDENTIFIABLE_CLINICAL_DATA=false
```

Do not add real keys to `.env.example`, frontend files, tests, docs, or logs.

## Backend Flow

`/api/llm/status` returns a sanitized provider status. It only says whether a key is configured and never returns the key.

Patient chat messages call the selected memory system first, then send retrieved context to the LLM answer service. If `GROQ_API_KEY` is empty, the response returns `generation_status: "not_configured"` and no assistant message is stored.

When Groq is configured, the backend uses `langchain-groq` with structured output and validates citations against retrieved context before saving an assistant message.

## Safety Defaults

The default external data mode is `synthetic_or_deidentified`. Patient direct identifiers are removed before a prompt can leave the backend. Set `LLM_ALLOW_IDENTIFIABLE_CLINICAL_DATA=true` only after you have explicit authorization and a clear compliance reason.

The frontend never reads or stores the Groq key. It only reads `/api/llm/status` and displays sanitized provider metadata.
