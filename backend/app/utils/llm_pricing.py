from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PRICING_VERSION = "2026-05-24"


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal


MODEL_PRICES = {
    "gpt-4o-mini": ModelPrice(Decimal("0.15"), Decimal("0.60"), Decimal("0.075")),
    "text-embedding-3-small": ModelPrice(Decimal("0.02"), Decimal("0"), Decimal("0.02")),
}


def calculate_llm_cost(
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cached_prompt_tokens: int = 0,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, str | None]:
    price = MODEL_PRICES.get(model)
    if price is None:
        return None, None, None, None
    cached = min(max(cached_prompt_tokens, 0), max(prompt_tokens, 0))
    uncached = max(prompt_tokens - cached, 0)
    input_cost = (
        Decimal(uncached) * price.input_per_million
        + Decimal(cached) * price.cached_input_per_million
    ) / Decimal(1_000_000)
    output_cost = Decimal(max(completion_tokens, 0)) * price.output_per_million / Decimal(1_000_000)
    return input_cost, output_cost, input_cost + output_cost, PRICING_VERSION
