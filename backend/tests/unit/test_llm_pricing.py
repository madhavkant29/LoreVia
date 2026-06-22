from decimal import Decimal

from app.utils.llm_pricing import PRICING_VERSION, calculate_llm_cost


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
    assert calculate_llm_cost(
        "unknown", prompt_tokens=1, completion_tokens=1
    ) == (None, None, None, None)
