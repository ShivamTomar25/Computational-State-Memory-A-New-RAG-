from __future__ import annotations


def job_metrics_summary() -> dict:
    return {
        "status": "not_configured",
        "message": "Dedicated background job metrics will be populated when long-running jobs are moved to a shared job runner.",
    }
