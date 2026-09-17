from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.performance.caching.memory_cache import MemoryTTLCache
from app.performance.database.connection_pool import connection_pool_settings
from app.performance.middleware.request_id import RequestIdMiddleware
from app.performance.middleware.request_timing import RequestTimingMiddleware


class PerformanceInstrumentationTests(TestCase):
    def test_server_timing_and_request_id_headers_are_added(self):
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)
        app.add_middleware(RequestIdMiddleware)

        @app.get("/")
        def home():
            return {"ok": True}

        with TestClient(app) as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Server-Timing", response.headers)
        self.assertIn("X-Request-ID", response.headers)
        self.assertIn("X-Response-Time-ms", response.headers)

    def test_memory_cache_tracks_hits_and_misses(self):
        cache = MemoryTTLCache(max_entries=2, default_ttl_seconds=30)
        cache.set("a", {"value": 1})

        self.assertEqual(cache.get("a"), {"value": 1})
        self.assertIsNone(cache.get("missing"))

        stats = cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

    def test_connection_pool_settings_are_explicit(self):
        settings = connection_pool_settings()

        self.assertGreater(settings["pool_size"], 0)
        self.assertGreaterEqual(settings["max_overflow"], 0)
        self.assertTrue(settings["pool_pre_ping"])
