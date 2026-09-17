from __future__ import annotations

from app.evaluation.metrics.calculators.common import measured_value, not_applicable, percentile
from app.evaluation.metrics.calculators.context import EvaluationTurnContext
from app.evaluation.metrics.cost.pricing import estimate_token_cost
from app.evaluation.metrics.interface.base import MetricCalculation


def calculate_efficiency_metric_group(contexts: list[EvaluationTurnContext]) -> dict[str, MetricCalculation]:
    llm_calls = [context.llm_call for context in contexts if context.llm_call is not None]

    return {
        "tokens_per_query": calculate_tokens_per_query(llm_calls),
        "p95_latency": calculate_p95_latency(contexts, llm_calls),
        "total_cost": calculate_total_cost(llm_calls),
    }


def calculate_tokens_per_query(llm_calls: list[object]) -> MetricCalculation:
    completed_calls = [call for call in llm_calls if getattr(call, "request_status", "") == "completed"]

    if not completed_calls:
        return not_applicable("no_completed_llm_calls")

    token_counts = [getattr(call, "input_token_count", 0) + getattr(call, "output_token_count", 0) for call in completed_calls]
    total_tokens = sum(token_counts)
    return measured_value(
        total_tokens / len(completed_calls),
        {"completed_queries": len(completed_calls), "total_online_generation_tokens": total_tokens},
        numerator=total_tokens,
        denominator=len(completed_calls),
    )


def calculate_p95_latency(contexts: list[EvaluationTurnContext], llm_calls: list[object]) -> MetricCalculation:
    durations = [float(getattr(call, "duration_ms", 0)) for call in llm_calls if getattr(call, "duration_ms", 0)]

    if not durations:
        durations = [
            (context.turn.completed_at - context.turn.started_at).total_seconds() * 1000
            for context in contexts
            if getattr(context.turn, "started_at", None) and getattr(context.turn, "completed_at", None)
        ]

    p95 = percentile(durations, 0.95)

    if p95 is None:
        return not_applicable("missing_latency_measurements")

    return measured_value(p95, {"sample_count": len(durations), "latencies_ms": durations})


def calculate_total_cost(llm_calls: list[object]) -> MetricCalculation:
    completed_calls = [call for call in llm_calls if getattr(call, "request_status", "") == "completed"]

    if not completed_calls:
        return not_applicable("no_completed_llm_calls")

    online_generation_cost = 0.0
    offline_maintenance_cost = 0.0
    pricing_details = []
    offline_pricing_details = []

    for call in completed_calls:
        estimate = estimate_token_cost(
            provider=getattr(call, "provider", ""),
            model=getattr(call, "model", ""),
            input_tokens=getattr(call, "input_token_count", 0),
            output_tokens=getattr(call, "output_token_count", 0),
        )

        if not estimate["available"]:
            return not_applicable(
                "pricing_not_configured",
                {
                    "provider": getattr(call, "provider", ""),
                    "model": getattr(call, "model", ""),
                },
            )

        if getattr(call, "ingestion_run_id", None) is not None:
            offline_maintenance_cost += estimate["total_cost"]
            offline_pricing_details.append(estimate)
        else:
            online_generation_cost += estimate["total_cost"]
            pricing_details.append(estimate)

    total_cost = online_generation_cost + offline_maintenance_cost
    return measured_value(
        total_cost,
        {
            "calls": len(completed_calls),
            "online_generation_cost": online_generation_cost,
            "offline_maintenance_cost": offline_maintenance_cost,
            "pricing": pricing_details,
            "offline_maintenance_pricing": offline_pricing_details,
        },
        numerator=total_cost,
    )
