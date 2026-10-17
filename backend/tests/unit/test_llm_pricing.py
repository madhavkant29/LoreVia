from decimal import Decimal

import pytest

from app.utils.llm_pricing import (
    PRICING_VERSION,
    UnsupportedLlmPricingError,
    calculate_llm_cost,
    calculate_llm_reservation_cost,
)


def test_chat_cost_accounts_for_cached_prompt_tokens():
    input_cost, output_cost, total, version = calculate_llm_cost(
        "gpt-4o-mini",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        cached_prompt_tokens=500_000,
    )
    assert input_cost == Decimal("0.1125")
    assert output_cost == Decimal("0.60")
    assert total == Decimal("0.7125")
    assert version == PRICING_VERSION


def test_unknown_model_returns_incomplete_cost():
    assert calculate_llm_cost("unknown", prompt_tokens=1, completion_tokens=1) == (
        None,
        None,
        None,
        None,
    )


def test_gemini_flash_cost_uses_google_pricing():
    input_cost, output_cost, total, version = calculate_llm_cost(
        "gemini-2.5-flash",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        provider="google",
    )

    assert input_cost == Decimal("0.30")
    assert output_cost == Decimal("2.50")
    assert total == Decimal("2.80")
    assert version == PRICING_VERSION


def test_reservation_cost_uses_uncached_prompt_and_full_maximum_output():
    input_cost, output_cost, total, version = calculate_llm_reservation_cost(
        "gpt-4o-mini",
        estimated_prompt_tokens=1_000_000,
        estimated_completion_tokens=500_000,
    )

    assert input_cost == Decimal("0.15")
    assert output_cost == Decimal("0.30")
    assert total == Decimal("0.45")
    assert version == PRICING_VERSION


@pytest.mark.parametrize(
    ("provider", "model"),
    [("unknown", "gpt-4o-mini"), ("openai", "unknown-model")],
)
def test_reservation_cost_fails_closed_for_unknown_pricing(provider, model):
    with pytest.raises(UnsupportedLlmPricingError):
        calculate_llm_reservation_cost(
            model,
            provider=provider,
            estimated_prompt_tokens=1,
            estimated_completion_tokens=1,
        )
