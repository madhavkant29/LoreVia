"""Evidence and coverage checks for chapter-level editorial reviews."""

import json

import pytest

from app.engine.analysis import summariser
from app.engine.analysis.summariser import (
    _merge_detailed_summary_payloads,
    _normalize_revision_question,
    _normalize_summary_payload,
)
from app.utils.books.continuity import parse_chapter_editorial_note


def test_editorial_concern_requires_an_exact_excerpt_from_the_passage():
    passage = "Mara heard the bell. She turned the key without warning."
    payload = _normalize_summary_payload(
        {
            "summary": "Mara opens the gate.",
            "editorial_concerns": [
                {
                    "issue": "The decision happens before its motivation is clear.",
                    "evidence": "She turned the key without warning.",
                    "suggestion": "Add the thought that makes her choose now.",
                },
                {
                    "issue": "Invented concern.",
                    "evidence": "She changed her mind because Jon arrived.",
                    "suggestion": "Invented direction.",
                },
            ],
        },
        fallback="",
        source_text=passage,
    )

    assert payload["editorial_concerns"] == [
        {
            "issue": "The decision happens before its motivation is clear.",
            "evidence": "She turned the key without warning.",
            "suggestion": "Add the thought that makes her choose now.",
        }
    ]


def test_editorial_concerns_are_empty_for_malformed_or_unsubstantiated_input():
    for concerns in (None, "not a list", [{"issue": "Vague", "evidence": ""}], [{"issue": "Wrong", "evidence": "Not in the passage"}]):
        payload = _normalize_summary_payload(
            {"summary": "A bell rings.", "editorial_concerns": concerns},
            fallback="",
            source_text="A bell rings.",
        )
        assert payload["editorial_concerns"] == []


def test_editorial_concerns_from_multiple_passages_are_deduplicated():
    concern = {"issue": "The turn is abrupt.", "evidence": "The door opened.", "suggestion": "Show the cause."}
    merged = _merge_detailed_summary_payloads([
        {"content": "First part.", "editorial_concerns": [concern]},
        {"content": "Second part.", "editorial_concerns": [concern]},
    ])
    assert merged["editorial_concerns"] == [concern]


def test_persisted_editorial_concerns_reject_malformed_notes():
    assert parse_chapter_editorial_note(None) == (None, None)
    assert parse_chapter_editorial_note("not json") == (None, None)
    assert parse_chapter_editorial_note(json.dumps({"issue": "not a list"})) == (None, None)
    assert parse_chapter_editorial_note("[]") == ([], None)
    assert parse_chapter_editorial_note(json.dumps([{"issue": "Missing evidence"}])) == ([], None)
    concerns, question = parse_chapter_editorial_note(json.dumps([{
        "issue": "The exit is abrupt.",
        "evidence": "Mara left.",
        "suggestion": "Give the choice a beat.",
    }]))
    assert [(concern.issue, concern.evidence) for concern in concerns] == [("The exit is abrupt.", "Mara left.")]
    assert question is None


def test_revision_question_requires_a_quoted_passage_and_question_form():
    passage = "Mara left the harbor at dawn."
    assert _normalize_revision_question(
        {"question": "What does Mara hope to gain by leaving now?", "evidence": passage},
        passage,
    ) == {"question": "What does Mara hope to gain by leaving now?", "evidence": passage}
    assert _normalize_revision_question(
        {"question": "Mara leaves without a reason.", "evidence": passage}, passage
    ) is None
    assert _normalize_revision_question(
        {"question": "Why does she leave?", "evidence": "A passage not in the text."}, passage
    ) is None


def test_persisted_revision_question_is_separate_from_concerns():
    concerns, question = parse_chapter_editorial_note(json.dumps({
        "concerns": [],
        "revision_question": {
            "question": "Does the departure need another beat?",
            "evidence": "Mara left the harbor at dawn.",
        },
    }))
    assert concerns == []
    assert question is not None
    assert question.question == "Does the departure need another beat?"


@pytest.mark.asyncio
async def test_detailed_summary_retries_malformed_json_without_dropping_the_passage(monkeypatch):
    responses = iter(["not json", json.dumps({"summary": "Mara keeps the archive key."}), "{}"])
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete)
    result = await summariser.generate_summary("Mara keeps the archive key.", "detailed")

    assert result["content"] == "Mara keeps the archive key."
    assert len(calls) == 3
    assert calls[1]["usage_metadata"]["attempt"] == 2


@pytest.mark.asyncio
async def test_missing_editorial_concern_gets_a_focused_evidence_checked_pass(monkeypatch):
    passage = "Mara turned the key without warning. The gate opened."
    responses = iter([
        json.dumps({"summary": "Mara opens the gate.", "editorial_concerns": []}),
        json.dumps({
            "issue": "The turn lacks a decision beat.",
            "evidence": "Mara turned the key without warning.",
            "suggestion": "Show what makes her act now.",
        }),
    ])
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete)
    result = await summariser.generate_summary(passage, "detailed")

    assert result["editorial_concerns"][0]["issue"] == "The turn lacks a decision beat."
    assert calls[1]["usage_feature"] == "chapter_editorial_review"


@pytest.mark.asyncio
async def test_no_supported_issue_keeps_a_grounded_revision_question(monkeypatch):
    passage = "Mara left the harbor at dawn."
    responses = iter([
        json.dumps({"summary": "Mara departs at dawn.", "editorial_concerns": []}),
        json.dumps({
            "question": "What does Mara hope this departure will change?",
            "evidence": passage,
        }),
    ])

    async def fake_complete(**_kwargs):
        return next(responses)

    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete)

    result = await summariser.generate_summary(passage, "detailed")

    assert result["editorial_concerns"] == []
    assert result["revision_question"] == {
        "question": "What does Mara hope this departure will change?",
        "evidence": passage,
    }


@pytest.mark.asyncio
async def test_focused_review_checks_other_passages_when_first_has_no_supported_issue(monkeypatch):
    responses = iter([
        json.dumps({"summary": "First passage summary.", "editorial_concerns": []}),
        json.dumps({"summary": "Second passage summary.", "editorial_concerns": []}),
        json.dumps({
            "question": "What drives the first passage's quiet opening?",
            "evidence": "The first passage is quiet.",
        }),
        json.dumps({
            "issue": "The key change has no cause on the page.",
            "evidence": "The key changed hands.",
            "suggestion": "Show the transfer before the guard uses the key.",
        }),
    ])
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr(
        summariser,
        "_analysis_passages",
        lambda *_args, **_kwargs: ["The first passage is quiet.", "The key changed hands."],
    )
    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete)

    result = await summariser.generate_summary("Long chapter", "detailed")

    assert result["editorial_concerns"][0]["evidence"] == "The key changed hands."
    assert result["revision_question"] is None
    assert [call["usage_metadata"]["part_index"] for call in calls[2:]] == [1, 2]


@pytest.mark.asyncio
async def test_supported_editorial_concern_does_not_trigger_an_extra_provider_call(monkeypatch):
    calls = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return json.dumps({
            "summary": "Mara opens the gate.",
            "editorial_concerns": [{
                "issue": "The decision is abrupt.",
                "evidence": "Mara turned the key.",
                "suggestion": "Show the choice.",
            }],
        })

    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete)
    result = await summariser.generate_summary("Mara turned the key.", "detailed")

    assert len(result["editorial_concerns"]) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_detailed_summary_rejects_a_partial_long_chapter_after_retry(monkeypatch):
    responses = iter([
        json.dumps({"summary": "The first passage is ready."}),
        "not json",
        json.dumps({"key_events": []}),
    ])

    async def fake_complete(**_kwargs):
        return next(responses)

    monkeypatch.setattr(summariser, "_analysis_passages", lambda *_args, **_kwargs: ["first", "second"])
    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete)

    with pytest.raises(ValueError, match="passage 2 is incomplete"):
        await summariser.generate_summary("first second", "detailed")
