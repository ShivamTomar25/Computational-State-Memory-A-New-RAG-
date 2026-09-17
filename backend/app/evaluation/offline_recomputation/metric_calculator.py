from __future__ import annotations

from collections import defaultdict

from app.evaluation.offline_recomputation.scope_loader import ALL_SYSTEMS, SYSTEMS
from app.evaluation.offline_recomputation.statistics import LOWER_IS_BETTER, bootstrap_ci, iqr, mean, median, stddev


METRICS = [
    "state_accuracy",
    "temporal_consistency",
    "decision_f1",
    "answer_accuracy",
    "hallucination_rate",
    "evidence_support_rate",
    "unsupported_claim_rate",
    "fabricated_citation_rate",
    "faithfulness",
    "groundedness",
    "expected_calibration_error",
    "lineage_citation_f1",
    "contradiction_handling",
    "correction_recovery",
    "retrieval_precision",
    "retrieval_recall",
    "activation_precision",
    "activation_recall",
    "tokens_per_query",
    "p95_latency",
    "provider_generation_latency_ms",
    "retrieval_activation_latency_ms",
    "processing_latency_ms",
    "operational_wall_clock_latency_ms",
    "online_query_cost",
    "offline_csm_update_cost",
    "total_cost",
    "memory_update_accuracy",
    "state_recovery_time",
]


def aggregate_observations(observations: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in observations:
        grouped[(row["system"], row["metric_name"])].append(row)
    matrix = []
    systems = systems_for_observations(observations)
    metadata = matrix_metadata(observations, systems)
    for system in systems:
        for metric in METRICS:
            rows = grouped.get((system, metric), [])
            values = [float(row["observation_value"]) for row in rows if row["applicable"] and row["observation_value"] not in ("", None)]
            ci_low, ci_high = bootstrap_ci(values)
            matrix.append(
                {
                    "patient": metadata["patient"],
                    "questions": metadata["questions"],
                    "systems": len(systems),
                    "repetitions": metadata["repetitions"],
                    "completed_turns": metadata["completed_turns"],
                    "system": system,
                    "metric_name": metric,
                    "value": aggregate_value(metric, values),
                    "observation_count": len(values),
                    "total_rows": len(rows),
                    "mean": mean(values),
                    "stddev": stddev(values),
                    "median": median(values),
                    "iqr": iqr(values),
                    "min": min(values) if values else None,
                    "max": max(values) if values else None,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "direction": "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better",
                    "reason_not_applicable": "; ".join(sorted({row["reason_not_applicable"] for row in rows if row["reason_not_applicable"]})) if not values else None,
                }
            )
    return matrix


def systems_for_observations(observations: list[dict]) -> list[str]:
    observed = {row["system"] for row in observations}
    ordered = [system for system in ALL_SYSTEMS if system in observed]
    if ordered in (["csm_v3"], ["csm_v4"]):
        return ordered
    if "csm_v3" in observed or "csm_v4" in observed:
        return [system for system in ALL_SYSTEMS if system in observed or system in SYSTEMS]
    return [system for system in SYSTEMS if system in observed or not observed]


def matrix_metadata(observations: list[dict], systems: list[str]) -> dict:
    patients = sorted({str(row.get("patient")) for row in observations if row.get("patient")})
    questions = {str(row.get("question_id")) for row in observations if row.get("question_id")}
    turns = {(str(row.get("system")), str(row.get("turn_id"))) for row in observations if row.get("system") and row.get("turn_id")}
    return {
        "patient": patients[0] if len(patients) == 1 else f"pooled_{len(patients)}_patients" if patients else None,
        "questions": len(questions) if questions else 0,
        "repetitions": 1,
        "completed_turns": len(turns) if turns else 0,
    }


def aggregate_value(metric: str, values: list[float]) -> float | None:
    if not values:
        return None
    if metric == "total_cost":
        return sum(values)
    if metric == "p95_latency":
        ordered = sorted(values)
        index = int(round((len(ordered) - 1) * 0.95))
        return ordered[index]
    return mean(values)


def rankings(matrix: list[dict]) -> list[dict]:
    rows = []
    for metric in METRICS:
        metric_rows = [row for row in matrix if row["metric_name"] == metric and row["value"] is not None]
        metric_rows.sort(key=lambda row: row["value"], reverse=metric not in LOWER_IS_BETTER)
        last = object()
        rank = 0
        for index, row in enumerate(metric_rows, start=1):
            if row["value"] != last:
                rank = index
                last = row["value"]
            rows.append({"metric_name": metric, "rank": rank, "system": row["system"], "value": row["value"], "observation_count": row["observation_count"]})
    return rows
