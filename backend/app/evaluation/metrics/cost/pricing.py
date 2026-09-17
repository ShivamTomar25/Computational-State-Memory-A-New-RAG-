from __future__ import annotations

from datetime import date


GROQ_PRICING_SOURCE = "https://groq.com/pricing"
GROQ_PRICING_EFFECTIVE_DATE = date(2026, 7, 20)

GROQ_MODEL_PRICING = [
    {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "input_price_per_million_tokens": 0.15,
        "output_price_per_million_tokens": 0.60,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
        "currency": "USD",
        "active": True,
    },
    {
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "input_price_per_million_tokens": 0.075,
        "output_price_per_million_tokens": 0.30,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
        "currency": "USD",
        "active": True,
    },
    {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "input_price_per_million_tokens": 0.59,
        "output_price_per_million_tokens": 0.79,
        "effective_date": GROQ_PRICING_EFFECTIVE_DATE,
        "source": GROQ_PRICING_SOURCE,
        "currency": "USD",
        "active": True,
    },
]


def estimate_token_cost(*, provider: str, model: str, input_tokens: int, output_tokens: int) -> dict:
    pricing = next(
        (
            item
            for item in GROQ_MODEL_PRICING
            if item["provider"] == provider and item["model"] == model and item["active"]
        ),
        None,
    )

    if pricing is None:
        return {
            "available": False,
            "reason": "pricing_not_configured",
            "total_cost": None,
        }

    input_cost = input_tokens / 1_000_000 * pricing["input_price_per_million_tokens"]
    output_cost = output_tokens / 1_000_000 * pricing["output_price_per_million_tokens"]

    return {
        "available": True,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + output_cost,
        "currency": pricing["currency"],
        "source": pricing["source"],
        "effective_date": pricing["effective_date"].isoformat(),
    }
