from __future__ import annotations

from app.config import settings


def cache_key(*parts) -> str:
    normalized = ":".join(str(part).strip().replace(":", "_") for part in parts if part is not None)
    return f"{settings.cache_key_prefix}:{normalized}"


def doctor_cache_prefix(doctor_id) -> str:
    return cache_key("doctor", doctor_id)


def patient_cache_prefix(patient_id) -> str:
    return cache_key("patient", patient_id)


def patient_workspace_summary_key(doctor_id, patient_id) -> str:
    return cache_key("patient", patient_id, "doctor", doctor_id, "workspace-summary")


def memory_registry_key() -> str:
    return cache_key("memory-systems", "registry", settings.memory_pipeline_version)
