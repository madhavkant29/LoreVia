import uuid

import pytest

from scripts import plan_narrator_profile_review


def test_narrator_profile_budget_rejects_excessive_calls_and_prompt_size():
    short = {"prompt": "I crossed the road."}
    with pytest.raises(ValueError, match="call_limit"):
        plan_narrator_profile_review.review_budget([short] * 7)
    with pytest.raises(ValueError, match="prompt_limit"):
        plan_narrator_profile_review.review_budget([{"prompt": "word " * 5_000}])


def test_narrator_profile_budget_reports_small_bounded_plan():
    budget = plan_narrator_profile_review.review_budget(
        [{"prompt": "I walked away."}, {"prompt": "My hands shook."}]
    )
    assert budget["calls"] == 2
    assert budget["estimated_total_tokens"] <= plan_narrator_profile_review.MAX_TOTAL_TOKENS
    assert float(budget["estimated_cost_usd"]) <= float(plan_narrator_profile_review.MAX_COST_USD)


@pytest.mark.asyncio
async def test_narrator_profile_apply_refuses_stale_plan_before_ai(monkeypatch):
    calls = 0

    async def fake_plan(*_args):
        return {"active_generation_id": str(uuid.uuid4()), "plan_sha256": "new"}

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        return "{}"

    monkeypatch.setattr(plan_narrator_profile_review, "build_plan", fake_plan)
    monkeypatch.setattr(plan_narrator_profile_review, "complete_with_fallback", fake_completion)

    with pytest.raises(ValueError, match="plan_changed"):
        await plan_narrator_profile_review.apply_plan(
            uuid.uuid4(),
            uuid.uuid4(),
            [1],
            expected_generation_id=uuid.uuid4(),
            expected_plan_sha256="old",
        )
    assert calls == 0
