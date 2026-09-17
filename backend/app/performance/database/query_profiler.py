from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import event

from app.config import settings
from app.performance.instrumentation.database_metrics import database_metrics_store


logger = logging.getLogger("sustha.performance.sql")


@dataclass
class QueryStats:
    count: int = 0
    total_ms: float = 0


request_query_stats: ContextVar[Optional[QueryStats]] = ContextVar("request_query_stats", default=None)


def start_request_query_stats():
    return request_query_stats.set(QueryStats())


def finish_request_query_stats(token) -> QueryStats:
    stats = request_query_stats.get() or QueryStats()
    request_query_stats.reset(token)
    return stats


def install_query_profiler(engine) -> None:
    if getattr(engine, "_sustha_query_profiler_installed", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._sustha_query_started_at = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        started_at = getattr(context, "_sustha_query_started_at", None)

        if started_at is None:
            return

        duration_ms = (time.perf_counter() - started_at) * 1000
        slow = duration_ms >= settings.performance_slow_query_ms
        database_metrics_store.record_query(duration_ms=duration_ms, slow=slow)

        stats = request_query_stats.get()

        if stats is not None:
            stats.count += 1
            stats.total_ms += duration_ms

        if slow and settings.performance_monitoring_enabled:
            logger.warning(
                "slow_sql duration_ms=%.2f statement=%s",
                duration_ms,
                sanitize_statement(statement),
            )

    engine._sustha_query_profiler_installed = True


def sanitize_statement(statement: str) -> str:
    return " ".join(statement.split())[:500]
