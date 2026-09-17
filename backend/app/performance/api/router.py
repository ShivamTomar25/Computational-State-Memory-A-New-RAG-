from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.doctor.dependencies import CurrentDoctor
from app.performance.caching.dependencies import get_cache_backend
from app.performance.database.connection_pool import connection_pool_settings
from app.performance.instrumentation.api_metrics import api_metrics_store
from app.performance.instrumentation.database_metrics import database_metrics_store
from app.performance.instrumentation.job_metrics import job_metrics_summary
from app.performance.instrumentation.llm_metrics import llm_metrics_summary


router = APIRouter()


@router.get("/api/performance/summary")
def performance_summary(current_doctor: CurrentDoctor):
    ensure_performance_api_enabled()
    return {
        "monitoring_enabled": settings.performance_monitoring_enabled,
        "server_timing_enabled": settings.performance_server_timing_enabled,
        "api": api_metrics_store.summary(),
        "database": database_metrics_store.summary(),
        "cache": get_cache_backend().stats(),
        "jobs": job_metrics_summary(),
        "llm": llm_metrics_summary(),
    }


@router.get("/api/performance/routes")
def performance_routes(current_doctor: CurrentDoctor):
    ensure_performance_api_enabled()
    return api_metrics_store.routes()


@router.get("/api/performance/database")
def performance_database(current_doctor: CurrentDoctor):
    ensure_performance_api_enabled()
    return {
        "metrics": database_metrics_store.summary(),
        "pool": connection_pool_settings(),
    }


@router.get("/api/performance/cache")
def performance_cache(current_doctor: CurrentDoctor):
    ensure_performance_api_enabled()
    return get_cache_backend().stats()


@router.get("/api/performance/jobs")
def performance_jobs(current_doctor: CurrentDoctor):
    ensure_performance_api_enabled()
    return job_metrics_summary()


def ensure_performance_api_enabled() -> None:
    if not settings.performance_api_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performance API is disabled.")
