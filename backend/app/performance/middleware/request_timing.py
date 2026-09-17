from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.performance.caching.memory_cache import request_cache_stats
from app.performance.database.query_profiler import finish_request_query_stats, start_request_query_stats
from app.performance.instrumentation.api_metrics import RequestMeasurement, api_metrics_store
from app.performance.middleware.server_timing import server_timing_header


logger = logging.getLogger("sustha.performance.request")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not settings.performance_monitoring_enabled:
            return await call_next(request)

        started_at = time.perf_counter()
        query_token = start_request_query_stats()
        cache_token = request_cache_stats.set({"hits": 0, "misses": 0})
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            query_stats = finish_request_query_stats(query_token)
            cache_stats = request_cache_stats.get() or {"hits": 0, "misses": 0}
            request_cache_stats.reset(cache_token)
            route_path = get_route_path(request)
            measurement = RequestMeasurement(
                method=request.method,
                path=route_path,
                status_code=status_code,
                duration_ms=duration_ms,
                query_count=query_stats.count,
                query_duration_ms=query_stats.total_ms,
                cache_hits=cache_stats["hits"],
                cache_misses=cache_stats["misses"],
            )
            api_metrics_store.record(measurement)

            if "response" in locals() and settings.performance_server_timing_enabled:
                response.headers["Server-Timing"] = server_timing_header(
                    total_ms=duration_ms,
                    query_count=query_stats.count,
                    query_ms=query_stats.total_ms,
                    cache_hits=cache_stats["hits"],
                    cache_misses=cache_stats["misses"],
                )
                response.headers["X-Response-Time-ms"] = f"{duration_ms:.2f}"

            if duration_ms >= settings.performance_slow_request_ms:
                logger.warning(
                    "slow_request method=%s path=%s status=%s duration_ms=%.2f query_count=%s cache_hits=%s cache_misses=%s",
                    request.method,
                    route_path,
                    status_code,
                    duration_ms,
                    query_stats.count,
                    cache_stats["hits"],
                    cache_stats["misses"],
                )


def get_route_path(request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)
