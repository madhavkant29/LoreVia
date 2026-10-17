from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PRICING_VERSION = "2026-09-07"


class UnsupportedLlmPricingError(ValueError):
    """Raised before a provider call when LoreVia cannot price the request."""


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal


MODEL_PRICES = {
    "gpt-4o-mini": ModelPrice(Decimal("0.15"), Decimal("0.60"), Decimal("0.075")),
    "text-embedding-3-small": ModelPrice(Decimal("0.02"), Decimal("0"), Decimal("0.02")),
}
GOOGLE_MODEL_PRICES = {
    "gemini-2.5-flash": ModelPrice(Decimal("0.30"), Decimal("2.50"), Decimal("0.03")),
}


def model_price(model: str, *, provider: str = "openai") -> ModelPrice:
    prices = {
        "openai": MODEL_PRICES,
        "google": GOOGLE_MODEL_PRICES,
    }.get(provider)
    if prices is None:
        raise UnsupportedLlmPricingError(f"Unsupported LLM provider pricing: {provider}")
    price = prices.get(model)
    if price is None:
        raise UnsupportedLlmPricingError(f"Unsupported LLM model pricing: {model}")
    return price


def calculate_llm_reservation_cost(
    model: str,
    *,
    estimated_prompt_tokens: int,
    estimated_completion_tokens: int,
    provider: str = "openai",
) -> tuple[Decimal, Decimal, Decimal, str]:
    """Price a request at its uncached input and maximum output bounds."""

    price = model_price(model, provider=provider)
    input_cost = (
        Decimal(max(estimated_prompt_tokens, 0)) * price.input_per_million / Decimal(1_000_000)
    )
    output_cost = (
        Decimal(max(estimated_completion_tokens, 0)) * price.output_per_million / Decimal(1_000_000)
    )
    return input_cost, output_cost, input_cost + output_cost, PRICING_VERSION


def calculate_llm_cost(
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cached_prompt_tokens: int = 0,
    provider: str = "openai",
) -> tuple[Decimal | None, Decimal | None, Decimal | None, str | None]:
    prices = {"openai": MODEL_PRICES, "google": GOOGLE_MODEL_PRICES}.get(provider, {})
    price = prices.get(model)
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
