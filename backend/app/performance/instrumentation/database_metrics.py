from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class DatabaseMetricSnapshot:
    query_count: int = 0
    total_query_ms: float = 0
    slow_query_count: int = 0


class DatabaseMetricsStore:
    def __init__(self) -> None:
        self._snapshot = DatabaseMetricSnapshot()
        self._lock = Lock()

    def record_query(self, duration_ms: float, slow: bool) -> None:
        with self._lock:
            self._snapshot.query_count += 1
            self._snapshot.total_query_ms += duration_ms
            if slow:
                self._snapshot.slow_query_count += 1

    def summary(self) -> dict:
        with self._lock:
            query_count = self._snapshot.query_count
            total_query_ms = self._snapshot.total_query_ms
            slow_query_count = self._snapshot.slow_query_count

        return {
            "query_count": query_count,
            "total_query_ms": round(total_query_ms, 3),
            "average_query_ms": round(total_query_ms / query_count, 3) if query_count else 0,
            "slow_query_count": slow_query_count,
        }


database_metrics_store = DatabaseMetricsStore()
