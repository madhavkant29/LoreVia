import hashlib
import uuid
from types import SimpleNamespace

import pytest

from scripts import plan_character_profile_review


def test_narrator_profile_budget_rejects_excessive_calls_and_prompt_size():
    short = {"prompt": "I crossed the road."}
    with pytest.raises(ValueError, match="call_limit"):
        plan_character_profile_review.review_budget([short] * 7)
    with pytest.raises(ValueError, match="prompt_limit"):
        plan_character_profile_review.review_budget([{"prompt": "word " * 5_000}])


def test_narrator_profile_budget_reports_small_bounded_plan():
    budget = plan_character_profile_review.review_budget(
        [{"prompt": "I walked away."}, {"prompt": "My hands shook."}]
    )
    assert budget["calls"] == 2
    assert budget["estimated_total_tokens"] <= plan_character_profile_review.MAX_TOTAL_TOKENS
    assert float(budget["estimated_cost_usd"]) <= float(plan_character_profile_review.MAX_COST_USD)


@pytest.mark.asyncio
async def test_narrator_profile_apply_refuses_stale_plan_before_ai(monkeypatch):
    calls = 0

    async def fake_plan(*_args, **_kwargs):
        return {"active_generation_id": str(uuid.uuid4()), "plan_sha256": "new"}

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        return "{}"

    monkeypatch.setattr(plan_character_profile_review, "build_plan", fake_plan)
    monkeypatch.setattr(plan_character_profile_review, "complete_with_fallback", fake_completion)

    with pytest.raises(ValueError, match="plan_changed"):
        await plan_character_profile_review.apply_plan(
            uuid.uuid4(),
            uuid.uuid4(),
            [1],
            expected_generation_id=uuid.uuid4(),
            expected_plan_sha256="old",
        )
    assert calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject_mode", "review_mode"),
    [("narrator", "confirmed_narrator"), ("named", "named_person")],
)
async def test_profile_review_does_not_repeat_ai_calls_for_completed_plan(
    monkeypatch, subject_mode, review_mode
):
    book_id = uuid.uuid4()
    character_id = uuid.uuid4()
    generation_id = uuid.uuid4()
    plan_hash = "reviewed-plan"
    book = SimpleNamespace(mode="author", user_id=uuid.uuid4())
    character = SimpleNamespace(
        generation_id=generation_id,
        analysis_metadata={
            "character_profile_review": {
                "plan_sha256": plan_hash,
                "generation_id": str(generation_id),
                "subject_mode": review_mode,
                "proposals": [{"status": "accepted"}],
            }
        },
    )

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, _statement):
            return None

        async def get(self, model, _id):
            return book if model is plan_character_profile_review.Book else character

    async def fake_plan(*_args, **_kwargs):
        return {
            "active_generation_id": str(generation_id),
            "plan_sha256": plan_hash,
            "character_name": "Mara",
            "budget": {"calls": 2},
        }

    async def unexpected_completion(**_kwargs):
        raise AssertionError("A completed review must not spend AI tokens again")

    monkeypatch.setattr(plan_character_profile_review, "AsyncSessionLocal", Session)
    monkeypatch.setattr(plan_character_profile_review, "build_plan", fake_plan)
    monkeypatch.setattr(
        plan_character_profile_review, "complete_with_fallback", unexpected_completion
    )

    result = await plan_character_profile_review.apply_plan(
        book_id,
        character_id,
        [2],
        expected_generation_id=generation_id,
        expected_plan_sha256=plan_hash,
        subject_mode=subject_mode,
    )

    assert result["ai_calls"] == 0
    assert result["source_checked_claims_for_review"] == 1
    assert result["already_reviewed"] is True


def test_named_profile_review_budget_uses_named_person_prompt():
    budget = plan_character_profile_review.review_budget(
        [{"prompt": "Mara lifted the gate."}], subject_mode="named"
    )
    assert budget["calls"] == 1
    with pytest.raises(ValueError, match="invalid_subject_mode"):
        plan_character_profile_review.review_budget([], subject_mode="unknown")


def test_named_profile_review_targets_only_incomplete_matched_chapters():
    rows = [
        SimpleNamespace(
            chapter_number=2, evidence={"profile_enrichment_status": "partial_invalid_response"}
        ),
        SimpleNamespace(chapter_number=3, evidence={"profile_enrichment_status": "complete"}),
        SimpleNamespace(chapter_number=4, evidence=None),
    ]
    assert plan_character_profile_review.incomplete_profile_chapters(rows) == {2}


def test_named_profile_windows_sample_separate_mentions_and_aliases():
    source = (
        "Mara opened the gate. "
        + "noise " * 400
        + "Mara waited. "
        + "noise " * 400
        + "Lark returned."
    )
    windows = plan_character_profile_review.profile_review_windows(
        source, name="Mara", aliases=["Lark"], subject_mode="named"
    )
    assert len(windows) == 2
    assert "Mara opened" in windows[0][2]
    assert "Lark returned" in windows[1][2]
    assert all(end - start <= 1_600 for start, end, _passage in windows)
    assert (
        plan_character_profile_review.profile_review_windows(
            "Nobody is named.", name="Mara", aliases=[], subject_mode="named"
        )
        == []
    )
    with pytest.raises(ValueError, match="invalid_subject_mode"):
        plan_character_profile_review.profile_review_windows(
            source, name="Mara", aliases=[], subject_mode="unknown"
        )


@pytest.mark.asyncio
async def test_named_plan_requires_recorded_incomplete_chapter_before_source_download(monkeypatch):
    book_id = uuid.uuid4()
    character_id = uuid.uuid4()
    generation_id = uuid.uuid4()
    character = SimpleNamespace(
        id=character_id,
        book_id=book_id,
        generation_id=generation_id,
        name="Mara",
        aliases=["Lark"],
    )
    chapter = SimpleNamespace(number=2, s3_key="chapter-2")
    candidate = SimpleNamespace(
        chapter_number=2, evidence={"profile_enrichment_status": "complete"}
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return self.value

    class Session:
        def __init__(self):
            self.results = iter(
                [Result(SimpleNamespace(id=generation_id)), Result([chapter]), Result([candidate])]
            )

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, statement):
            if str(statement).startswith("SET TRANSACTION"):
                return None
            return next(self.results, None)

        async def get(self, _model, _id):
            return character

    downloads = []
    monkeypatch.setattr(plan_character_profile_review, "AsyncSessionLocal", Session)
    monkeypatch.setattr(
        plan_character_profile_review,
        "download_book",
        lambda key: downloads.append(key) or b"Mara opened the gate.",
    )
    with pytest.raises(ValueError, match="chapters_not_incomplete"):
        await plan_character_profile_review.build_plan(
            book_id, character_id, [2], subject_mode="named"
        )
    assert downloads == []

    candidate.evidence = {"profile_enrichment_status": "partial_invalid_response"}
    monkeypatch.setattr(
        plan_character_profile_review,
        "deserialize_manuscript_content",
        lambda _raw: {"text": "Mara opened the gate."},
    )
    plan = await plan_character_profile_review.build_plan(
        book_id, character_id, [2], subject_mode="named"
    )
    assert plan["subject_mode"] == "named"
    assert plan["source_windows"] == 1
    assert plan["budget"]["calls"] == 1
    assert plan["_source_hashes"][2] == hashlib.sha256(b"Mara opened the gate.").hexdigest()
    assert downloads == ["chapter-2"]
