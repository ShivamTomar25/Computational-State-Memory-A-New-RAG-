from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict


LOWER_IS_BETTER = {
    "hallucination_rate",
    "unsupported_claim_rate",
    "fabricated_citation_rate",
    "expected_calibration_error",
    "tokens_per_query",
    "p95_latency",
    "provider_generation_latency_ms",
    "retrieval_activation_latency_ms",
    "processing_latency_ms",
    "operational_wall_clock_latency_ms",
    "online_query_cost",
    "offline_csm_update_cost",
    "total_cost",
    "state_recovery_time",
}
CSM_SYSTEMS = {"csm", "csm_v3", "csm_v4"}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stddev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) > 1 else (0.0 if values else None)


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def iqr(values: list[float]) -> float | None:
    if not values:
        return None
    return (percentile(values, 0.75) or 0.0) - (percentile(values, 0.25) or 0.0)


def bootstrap_ci(values: list[float], samples: int = 500) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(20260722)
    means = []
    for _ in range(samples):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    return percentile(means, 0.025), percentile(means, 0.975)


def sign_test_p_value(diffs: list[float]) -> float | None:
    positives = sum(1 for value in diffs if value > 0)
    negatives = sum(1 for value in diffs if value < 0)
    n = positives + negatives
    if n < 2:
        return None
    k = min(positives, negatives)
    p = sum(math.comb(n, i) * (0.5**n) for i in range(k + 1))
    return min(1.0, 2 * p)


def paired_comparisons(observations: list[dict], systems: list[str]) -> list[dict]:
    by_key = {}
    for row in observations:
        if row["applicable"] and row["observation_value"] not in ("", None):
            by_key[(row["system"], row["metric_name"], row["question_id"])] = float(row["observation_value"])
    metrics = sorted({row["metric_name"] for row in observations})
    rows = []
    csm_anchors = [system for system in systems if system in CSM_SYSTEMS]
    for metric in metrics:
        for csm_system in csm_anchors:
            for system in [item for item in systems if item != csm_system]:
                diffs = []
                question_ids = sorted({key[2] for key in by_key if key[0] == csm_system and key[1] == metric})
                for question_id in question_ids:
                    csm = by_key.get((csm_system, metric, question_id))
                    other = by_key.get((system, metric, question_id))
                    if csm is None or other is None:
                        continue
                    diff = csm - other
                    if metric in LOWER_IS_BETTER:
                        diff = -diff
                    diffs.append(diff)
                ci_low, ci_high = bootstrap_ci(diffs)
                rows.append(
                    {
                        "metric_name": metric,
                        "comparison": f"{csm_system}_vs_{system}",
                        "paired_sample_count": len(diffs),
                        "mean_difference": mean(diffs),
                        "median_difference": median(diffs),
                        "effect_size": effect_size(diffs),
                        "raw_p_value": sign_test_p_value(diffs),
                        "adjusted_p_value": None,
                        "ci_low": ci_low,
                        "ci_high": ci_high,
                        "test_result": "N/A" if len(diffs) < 2 else "computed",
                        "reason": None if len(diffs) >= 2 else "insufficient_paired_observations",
                    }
                )
    adjust_p_values(rows)
    return rows


def effect_size(diffs: list[float]) -> float | None:
    sd = stddev(diffs)
    if sd in (None, 0.0):
        return None
    return (mean(diffs) or 0.0) / sd


def adjust_p_values(rows: list[dict]) -> None:
    p_rows = [row for row in rows if row["raw_p_value"] is not None]
    total = len(p_rows)
    for index, row in enumerate(sorted(p_rows, key=lambda item: item["raw_p_value"]), start=1):
        row["adjusted_p_value"] = min(1.0, row["raw_p_value"] * total / index)
