# Sustha Performance Pass

This folder stores machine-readable and human-readable performance reports.

Run:

```bash
python scripts/performance_baseline.py
```

The script uses synthetic data, records measured endpoint timings, reads frontend production bundle sizes from `frontend/dist`, and writes `app/performance/reports/latest_api_baseline.json`.

Targets are budgets, not guarantees:

- Click feedback under 50 ms.
- Cached route render under 100 ms.
- Normal local read API p95 under 250 ms.
- Heavy operations return an accepted job/run ID quickly.

Do not report fabricated performance numbers. If an operation is not measured by the script, mark it unmeasured.
