from __future__ import annotations


def server_timing_header(*, total_ms: float, query_count: int, query_ms: float, cache_hits: int, cache_misses: int) -> str:
    return (
        f"total;dur={total_ms:.2f}, "
        f"db;dur={query_ms:.2f};desc=\"{query_count} queries\", "
        f"cache;desc=\"{cache_hits} hits {cache_misses} misses\""
    )
