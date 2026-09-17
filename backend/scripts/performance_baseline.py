from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app
from scripts import smoke_all_flows as smoke


REPORT_PATH = Path(__file__).resolve().parents[1] / "app" / "performance" / "reports" / "latest_api_baseline.json"
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "assets"


def main() -> int:
    init_db()
    marker = f"sustha-perf-{int(time.time())}-{uuid4().hex[:8]}"
    email = f"{marker}@susthahealth.dev"
    password = "SmokePass123!"
    context = {"marker": marker, "email": email}
    timings = []

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            measure(timings, "root", lambda: smoke.assert_response(client.get("/"), "root"))
            measure(timings, "health", lambda: smoke.assert_response(client.get("/health/live"), "health"))
            measure(timings, "llm_status", lambda: smoke.assert_response(client.get("/api/llm/status"), "llm status"))
            auth = measure(timings, "doctor_register_login", lambda: smoke.smoke_auth(client, email, password))
            headers = {"Authorization": f"Bearer {auth['access_token']}"}
            context["doctor_id"] = auth["doctor"]["id"]
            patient = measure(timings, "patient_create", lambda: smoke.smoke_patient(client, headers, marker))
            context["patient_id"] = patient["id"]
            measure(timings, "patient_list", lambda: smoke.assert_response(client.get("/api/patients?page=1&page_size=20", headers=headers), "patient list"))
            measure(timings, "patient_detail", lambda: smoke.assert_response(client.get(f"/api/patients/{patient['id']}", headers=headers), "patient detail"))
            measure(timings, "patient_workspace_summary", lambda: smoke.assert_response(client.get(f"/api/patients/{patient['id']}/workspace-summary", headers=headers), "patient workspace summary"))
            measure(timings, "memory_registry_first", lambda: smoke.assert_response(client.get("/api/memory-systems", headers=headers), "memory registry"))
            measure(timings, "memory_registry_cached", lambda: smoke.assert_response(client.get("/api/memory-systems", headers=headers), "memory registry cached"))
            measure(timings, "patient_memory_systems", lambda: smoke.assert_response(client.get(f"/api/patients/{patient['id']}/memory-systems", headers=headers), "patient memory systems"))

            performance_summary = measure(
                timings,
                "performance_summary",
                lambda: smoke.assert_response(client.get("/api/performance/summary", headers=headers), "performance summary"),
            )
    finally:
        cleanup = smoke.cleanup_smoke_data(context)

    report = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api_timings": summarize_timings(timings),
        "bundle_sizes": bundle_sizes(),
        "performance_summary": performance_summary,
        "cleanup": cleanup,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def measure(timings: list[dict], name: str, callback):
    started_at = time.perf_counter()
    result = callback()
    duration_ms = (time.perf_counter() - started_at) * 1000
    timings.append({"name": name, "duration_ms": round(duration_ms, 3)})
    return result


def summarize_timings(timings: list[dict]) -> dict:
    by_name = {}

    for timing in timings:
        by_name.setdefault(timing["name"], []).append(timing["duration_ms"])

    return {
        name: {
            "count": len(values),
            "p50_ms": round(statistics.median(values), 3),
            "p95_ms": percentile(values, 0.95),
            "max_ms": round(max(values), 3),
        }
        for name, values in by_name.items()
    }


def percentile(values: list[float], percentile_value: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile_value
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def bundle_sizes() -> dict:
    if not FRONTEND_DIST.exists():
        return {"status": "frontend_dist_missing"}

    files = []

    for path in sorted(FRONTEND_DIST.glob("*")):
        if path.is_file():
            files.append(
                {
                    "file": path.name,
                    "size_bytes": path.stat().st_size,
                }
            )

    return {
        "asset_count": len(files),
        "total_bytes": sum(item["size_bytes"] for item in files),
        "largest_assets": sorted(files, key=lambda item: item["size_bytes"], reverse=True)[:10],
    }


if __name__ == "__main__":
    raise SystemExit(main())
