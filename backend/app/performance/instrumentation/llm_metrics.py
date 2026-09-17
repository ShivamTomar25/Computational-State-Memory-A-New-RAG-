from __future__ import annotations


def llm_metrics_summary() -> dict:
    return {
        "status": "available_from_llm_calls_table",
        "message": "LLM request duration, token counts, and provider/model data are persisted in llm_calls.",
    }
