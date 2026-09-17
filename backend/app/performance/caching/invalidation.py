from __future__ import annotations

from app.performance.caching.dependencies import get_cache_backend
from app.performance.caching.keys import doctor_cache_prefix, patient_cache_prefix


def invalidate_doctor(doctor_id) -> int:
    return get_cache_backend().delete_prefix(doctor_cache_prefix(doctor_id))


def invalidate_patient(patient_id) -> int:
    return get_cache_backend().delete_prefix(patient_cache_prefix(patient_id))


def invalidate_key(key: str) -> None:
    get_cache_backend().delete(key)
