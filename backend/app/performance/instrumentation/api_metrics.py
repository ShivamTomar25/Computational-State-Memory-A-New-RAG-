from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Optional


@dataclass(frozen=True)
class RequestMeasurement:
    method: str
    path: str
    status_code: int
    duration_ms: float
    query_count: int
    query_duration_ms: float
    cache_hits: int
    cache_misses: int


class ApiMetricsStore:
    def __init__(self, max_samples_per_route: int = 200) -> None:
        self._max_samples_per_route = max_samples_per_route
        self._samples = defaultdict(lambda: deque(maxlen=max_samples_per_route))
        self._lock = Lock()

    def record(self, measurement: RequestMeasurement) -> None:
        key = f"{measurement.method} {measurement.path}"

        with self._lock:
            self._samples[key].append(measurement)

    def summary(self) -> dict:
        with self._lock:
            route_summaries = {
                key: summarize_samples(list(samples))
                for key, samples in self._samples.items()
            }

        total_samples = sum(route["count"] for route in route_summaries.values())
        return {
            "sample_count": total_samples,
            "routes": route_summaries,
        }

    def routes(self) -> dict:
        return self.summary()["routes"]


api_metrics_store = ApiMetricsStore()


def summarize_samples(samples: list[RequestMeasurement]) -> dict:
    durations = [sample.duration_ms for sample in samples]
    query_counts = [sample.query_count for sample in samples]
    query_durations = [sample.query_duration_ms for sample in samples]
    cache_hits = sum(sample.cache_hits for sample in samples)
    cache_misses = sum(sample.cache_misses for sample in samples)

    return {
        "count": len(samples),
        "p50_ms": percentile(durations, 0.50),
        "p95_ms": percentile(durations, 0.95),
        "max_ms": max(durations) if durations else None,
        "avg_query_count": sum(query_counts) / len(query_counts) if query_counts else 0,
        "p95_query_ms": percentile(query_durations, 0.95),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }


def percentile(values: list[float], percentile_value: float) -> Optional[float]:
    if not values:
        return None

    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile_value
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return round(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction, 3)
