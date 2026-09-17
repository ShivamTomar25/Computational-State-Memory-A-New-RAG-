from __future__ import annotations

from app.memory_systems.common.registry.registry import registry


def validate_all_systems_ready() -> dict:
    systems = []
    failures = []

    for adapter in registry.all():
        capability = adapter.capability_status()
        ready = capability.ingestion == "available" and capability.retrieval in {"available", "degraded"}
        status = "ready" if ready else capability.ingestion
        systems.append(
            {
                "system_type": adapter.system_type,
                "display_name": adapter.display_name,
                "status": status,
                "capability_status": capability.model_dump(),
            }
        )

        if not ready:
            failures.append(adapter.system_type)

    return {
        "ready": not failures,
        "systems": systems,
        "failures": failures,
    }
