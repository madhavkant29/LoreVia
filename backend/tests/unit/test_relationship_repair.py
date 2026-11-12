import json
import uuid
from types import SimpleNamespace

import pytest

from app.utils.characters.relationship_repair import (
    relationship_evidence_windows,
    verified_relationship_evidence_proposal,
)
from app.utils.llm_usage_utils import LLMIncompleteResponseError
from scripts import plan_relationship_evidence_review
from scripts.plan_relationship_evidence_review import (
    evidence_plan_hash,
    review_budget,
    review_prompt,
)


def test_relationship_evidence_windows_require_both_named_people():
    source = 'Mara crossed the market. "Wait," Lina said. ' + "x " * 2000 + "Mara returned."
    windows = relationship_evidence_windows(source, ["Mara"], ["Lina"])
    assert len(windows) == 1
    assert "Mara crossed" in windows[0][2]
    assert relationship_evidence_windows(source, ["Mara"], ["Jonas"]) == []
    assert relationship_evidence_windows("", ["Mara"], ["Lina"]) == []


def test_relationship_evidence_windows_prioritize_saved_quote():
    source = (
        "Mara and Lina waited at the gate. "
        + "x " * 1700
        + "Mara and Lina signed the pact together."
    )
    windows = relationship_evidence_windows(
        source,
        ["Mara"],
        ["Lina"],
        preferred_quote="Mara and Lina signed the pact together.",
    )
    assert len(windows) == 2
    assert "signed the pact" in windows[0][2]
    with pytest.raises(ValueError, match="window_limit"):
        relationship_evidence_windows(source, ["Mara"], ["Lina"], max_windows=0)


def test_relationship_evidence_windows_prioritize_close_named_pair_without_saved_quote():
    source = (
        "Mara watched from the hill. "
        + "x " * 1000
        + "Lina crossed the valley. "
        + "x " * 1600
        + "Mara and Lina signed the pact together."
    )
    windows = relationship_evidence_windows(source, ["Mara"], ["Lina"], max_windows=1)

    assert len(windows) == 1
    assert "signed the pact" in windows[0][2]


def test_verified_relationship_evidence_proposal_requires_exact_source_quote():
    source = "Mara and Lina signed the pact together."
    windows = [(100, 100 + len(source), source)]
    raw = json.dumps(
        {
            "supported": True,
            "relationship_type": "allies",
            "quote": "Mara and Lina signed the pact together.",
        }
    )
    assert verified_relationship_evidence_proposal(
        raw, windows=windows, left_name="Mara", right_name="Lina"
    ) == {
        "relationship_type": "allies",
        "quote": source,
        "source_start": 100,
        "source_end": 100 + len(source),
        "participants_anchored": True,
    }
    assert (
        verified_relationship_evidence_proposal(
            raw.replace("signed", "invented"),
            windows=windows,
            left_name="Mara",
            right_name="Lina",
        )
        is None
    )
    assert (
        verified_relationship_evidence_proposal(
            "not json", windows=windows, left_name="Mara", right_name="Lina"
        )
        is None
    )


def test_verified_relationship_evidence_proposal_marks_single_name_quote_for_review():
    source = "Mara met Lina beside the gate. Lina waved."
    raw = json.dumps(
        {"supported": True, "relationship_type": "acquaintance", "quote": "Lina waved."}
    )
    proposal = verified_relationship_evidence_proposal(
        raw,
        windows=[(0, len(source), source)],
        left_name="Mara",
        right_name="Lina",
    )
    assert proposal is not None
    assert proposal["participants_anchored"] is False


def test_relationship_review_budget_caps_calls_and_prompt_tokens(monkeypatch):
    rows = [
        {"prompt": review_prompt("Mara", "Lina", "friends", [(0, 21, "Mara met Lina at dawn.")])}
    ]
    budget = review_budget(rows)
    assert budget["calls"] == 1
    assert budget["max_retry_calls"] == 1
    assert budget["max_provider_calls"] == 2
    assert budget["max_total_tokens"] == (budget["max_prompt_tokens"] + budget["max_output_tokens"])
    assert budget["max_output_tokens"] == 1024 + 1536
    assert float(budget["max_cost_usd"]) <= 0.02
    with pytest.raises(ValueError, match="call_limit"):
        review_budget(rows * 13)
    monkeypatch.setattr(
        "scripts.plan_relationship_evidence_review.count_tokens", lambda _text: 2200
    )
    with pytest.raises(ValueError, match="prompt_limit"):
        review_budget(rows)


def test_relationship_review_budget_includes_single_retry_exposure(monkeypatch):
    rows = [{"prompt": "source"}] * 11
    monkeypatch.setattr(plan_relationship_evidence_review, "count_tokens", lambda _text: 1500)
    budget = review_budget(rows)
    assert budget["max_provider_calls"] == 12
    assert budget["max_output_tokens"] == 11 * 1024 + 1536
    assert budget["max_total_tokens"] <= 36_000
    assert float(budget["max_cost_usd"]) <= 0.02

    monkeypatch.setattr(plan_relationship_evidence_review, "count_tokens", lambda _text: 1900)
    with pytest.raises(ValueError, match="token_limit"):
        review_budget(rows + rows[:1])


def test_evidence_plan_hash_changes_with_source_prompt_and_review_policy(monkeypatch):
    rows = [{"relationship_id": "tie-1", "prompt": "Mara met Lina."}]
    original = evidence_plan_hash("repair-1", {2: "Mara met Lina."}, rows)
    assert original == evidence_plan_hash("repair-1", {2: "Mara met Lina."}, rows)
    assert original != evidence_plan_hash("repair-1", {2: "Mara missed Lina."}, rows)
    assert original != evidence_plan_hash("repair-2", {2: "Mara met Lina."}, rows)
    assert original != evidence_plan_hash(
        "repair-1", {2: "Mara met Lina."}, [{**rows[0], "prompt": "Different"}]
    )
    monkeypatch.setattr(plan_relationship_evidence_review, "RETRY_OUTPUT_TOKENS", 2048)
    assert original != evidence_plan_hash("repair-1", {2: "Mara met Lina."}, rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcomes", "expected_caps", "should_apply"),
    [
        (["complete"], [1024], True),
        (["length", "complete"], [1024, 1536], True),
        (["length", "length"], [1024, 1536], False),
        (["content_filter"], [1024], False),
    ],
)
async def test_relationship_review_retries_only_one_length_response_and_applies_atomically(
    monkeypatch, outcomes, expected_caps, should_apply
):
    generation_id = uuid.uuid4()
    book_id = uuid.uuid4()
    plan = {
        "active_generation_id": str(generation_id),
        "evidence_plan_sha256": "plan",
        "repair_plan_sha256": "repair",
        "budget": {"calls": 1},
        "_eligible": [
            {
                "relationship_id": "tie-1",
                "prompt": "Mara met Lina.",
                "windows": [(0, 14, "Mara met Lina.")],
                "character_a": "Mara",
                "character_b": "Lina",
            }
        ],
    }
    calls = []
    applied = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def begin(self):
            return self

        async def execute(self, *_args):
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))

        async def get(self, *_args):
            return SimpleNamespace(mode="author", user_id=uuid.uuid4())

    async def build_plan(*_args):
        return plan

    async def paid_call(**kwargs):
        calls.append(kwargs["max_tokens"])
        outcome = outcomes[len(calls) - 1]
        if outcome != "complete":
            raise LLMIncompleteResponseError("llm_response_incomplete", finish_reason=outcome)
        return '{"supported":false}'

    async def apply_plan(*_args, **_kwargs):
        applied.append(True)
        return {"review_count": 0}

    monkeypatch.setattr(plan_relationship_evidence_review, "AsyncSessionLocal", Session)
    monkeypatch.setattr(plan_relationship_evidence_review, "build_evidence_review_plan", build_plan)
    monkeypatch.setattr(plan_relationship_evidence_review, "complete_with_fallback", paid_call)
    monkeypatch.setattr(plan_relationship_evidence_review, "apply_plan", apply_plan)

    if should_apply:
        result = await plan_relationship_evidence_review.apply_evidence_review_plan(
            book_id=book_id,
            expected_generation_id=generation_id,
            expected_plan_sha256="plan",
        )
        assert result["ai_calls"] == len(expected_caps)
    else:
        with pytest.raises(LLMIncompleteResponseError):
            await plan_relationship_evidence_review.apply_evidence_review_plan(
                book_id=book_id,
                expected_generation_id=generation_id,
                expected_plan_sha256="plan",
            )
    assert calls == expected_caps
    assert bool(applied) is should_apply


@pytest.mark.asyncio
async def test_relationship_ai_review_refuses_stale_source_plan_before_calls(monkeypatch):
    calls = 0

    class ReadSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, *_args):
            return None

        async def get(self, *_args):
            return SimpleNamespace(mode="author", user_id=uuid.uuid4())

    async def changed_plan(*_args):
        return {"active_generation_id": str(uuid.uuid4()), "evidence_plan_sha256": "new"}

    async def paid_call(**_kwargs):
        nonlocal calls
        calls += 1
        return "{}"

    monkeypatch.setattr(plan_relationship_evidence_review, "AsyncSessionLocal", ReadSession)
    monkeypatch.setattr(
        plan_relationship_evidence_review, "build_evidence_review_plan", changed_plan
    )
    monkeypatch.setattr(plan_relationship_evidence_review, "complete_with_fallback", paid_call)

    with pytest.raises(ValueError, match="plan_changed"):
        await plan_relationship_evidence_review.apply_evidence_review_plan(
            book_id=uuid.uuid4(),
            expected_generation_id=uuid.uuid4(),
            expected_plan_sha256="old",
        )
    assert calls == 0


@pytest.mark.asyncio
async def test_relationship_ai_review_rechecks_source_after_provider_call(monkeypatch):
    generation_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    plans = iter(
        [
            {
                "active_generation_id": str(generation_id),
                "evidence_plan_sha256": "original",
                "repair_plan_sha256": "repair-1",
                "_eligible": [
                    {
                        "relationship_id": "tie-1",
                        "prompt": "Mara met Lina.",
                        "windows": [(0, 14, "Mara met Lina.")],
                        "character_a": "Mara",
                        "character_b": "Lina",
                    }
                ],
            },
            {"evidence_plan_sha256": "source-changed"},
        ]
    )
    paid_calls = 0

    class ReadSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, *_args):
            return None

        async def get(self, *_args):
            return SimpleNamespace(mode="author", user_id=uuid.uuid4())

    async def next_plan(*_args):
        return next(plans)

    async def paid_call(**_kwargs):
        nonlocal paid_calls
        paid_calls += 1
        return '{"supported":false}'

    async def forbidden_apply(*_args, **_kwargs):
        raise AssertionError("stale source must not be applied")

    monkeypatch.setattr(plan_relationship_evidence_review, "AsyncSessionLocal", ReadSession)
    monkeypatch.setattr(plan_relationship_evidence_review, "build_evidence_review_plan", next_plan)
    monkeypatch.setattr(plan_relationship_evidence_review, "complete_with_fallback", paid_call)
    monkeypatch.setattr(plan_relationship_evidence_review, "apply_plan", forbidden_apply)

    with pytest.raises(ValueError, match="plan_changed_after_ai"):
        await plan_relationship_evidence_review.apply_evidence_review_plan(
            book_id=uuid.uuid4(),
            expected_generation_id=generation_id,
            expected_plan_sha256="original",
        )
    assert paid_calls == 1


@pytest.mark.asyncio
async def test_relationship_ai_review_rejects_reader_book_before_paid_calls(monkeypatch):
    generation_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    calls = 0

    class ReadSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, *_args):
            return None

        async def get(self, *_args):
            return SimpleNamespace(mode="reader", user_id=uuid.uuid4())

    async def unchanged_plan(*_args):
        return {"active_generation_id": str(generation_id), "evidence_plan_sha256": "plan"}

    async def paid_call(**_kwargs):
        nonlocal calls
        calls += 1
        return "{}"

    monkeypatch.setattr(plan_relationship_evidence_review, "AsyncSessionLocal", ReadSession)
    monkeypatch.setattr(
        plan_relationship_evidence_review, "build_evidence_review_plan", unchanged_plan
    )
    monkeypatch.setattr(plan_relationship_evidence_review, "complete_with_fallback", paid_call)

    with pytest.raises(ValueError, match="author_book_required"):
        await plan_relationship_evidence_review.apply_evidence_review_plan(
            book_id=uuid.uuid4(),
            expected_generation_id=generation_id,
            expected_plan_sha256="plan",
        )
    assert calls == 0
