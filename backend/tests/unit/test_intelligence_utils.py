"""Unit tests for grounded intelligence and voice fingerprint helpers."""

import uuid
from types import SimpleNamespace

import pytest

from app.utils import intelligence_utils
from app.utils.intelligence_utils import (
    book_series_snapshot,
    build_grounded_citation,
    build_grounded_qa_context,
    build_prior_series_context,
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    score_voice_match,
)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class _FakeDB:
    def __init__(self, *rows):
        self.rows = list(rows)

    async def execute(self, _statement):
        return _Rows(self.rows.pop(0))


def test_grounded_citation_normalizes_excerpt_and_relevance():
    assert build_grounded_citation(2, None, "  Gate opens.  ", "passage", 0.87654) == {
        "chapter_num": 2,
        "chapter_title": None,
        "excerpt": "Gate opens.",
        "source_type": "passage",
        "relevance": 0.877,
    }


@pytest.mark.asyncio
async def test_build_grounded_context_combines_series_summaries_and_ranked_passages(monkeypatch):
    db = _FakeDB(
        [
            (3, "Third", "A repeated summary."),
            (2, None, "  The key changes hands.  "),
            (1, "First", ""),
        ]
    )
    book = SimpleNamespace(id=uuid.uuid4())
    user_id = uuid.uuid4()

    async def search(*_args, **_kwargs):
        return [
            {
                "chapter_num": 2,
                "chapter_title": "Key",
                "text": "The brass key glows.",
                "relevance": 0.92,
            },
            {"chapter_num": 3, "chapter_title": None, "text": "A weaker clue.", "relevance": 0.4},
            {"chapter_num": 4, "chapter_title": "Empty", "text": "   ", "relevance": 1.0},
        ]

    async def series(*_args, **_kwargs):
        return ["Previous volume context: Atlas I"]

    monkeypatch.setattr(intelligence_utils, "semantic_search", search)
    monkeypatch.setattr(intelligence_utils, "build_prior_series_context", series)
    blocks, citations = await build_grounded_qa_context(db, book, user_id, "What changed?", 3)

    assert blocks[0] == "Previous volume context: Atlas I"
    assert any("Chapter 2: Untitled" in block for block in blocks)
    assert any("Passage from Chapter 2: Key" in block for block in blocks)
    assert [citation["source_type"] for citation in citations[:2]] == ["passage", "passage"]
    assert citations[0]["relevance"] == 0.92
    assert citations[-1]["source_type"] == "summary"


@pytest.mark.asyncio
async def test_prior_series_context_uses_only_three_preceding_volumes(monkeypatch):
    current = SimpleNamespace(id=uuid.uuid4(), primary_series_id=uuid.uuid4())
    prior = [SimpleNamespace(id=uuid.uuid4(), title=f"Volume {index}") for index in range(5)]
    db = _FakeDB([(item, index) for index, item in enumerate([*prior, current])])
    calls = []

    async def snapshot(_db, book_id, title):
        calls.append((book_id, title))
        return None if title == "Volume 3" else f"Context: {title}"

    monkeypatch.setattr(intelligence_utils, "book_series_snapshot", snapshot)
    result = await build_prior_series_context(db, current, uuid.uuid4())
    assert calls == [
        (prior[2].id, "Volume 2"),
        (prior[3].id, "Volume 3"),
        (prior[4].id, "Volume 4"),
    ]
    assert result == ["Context: Volume 2", "Context: Volume 4"]

    assert (
        await build_prior_series_context(
            _FakeDB(), SimpleNamespace(primary_series_id=None), uuid.uuid4()
        )
        == []
    )
    missing = SimpleNamespace(id=uuid.uuid4(), primary_series_id=uuid.uuid4())
    assert await build_prior_series_context(_FakeDB([]), missing, uuid.uuid4()) == []


@pytest.mark.asyncio
async def test_book_series_snapshot_formats_all_context_sections_and_empty_state():
    db = _FakeDB(
        [
            (2, None, "Second summary", {"turns": ["Gate opens", "Key breaks"]}),
            (1, "Opening", "First summary", ["Arrival"]),
        ],
        [("Mara", "lead", "Learns trust"), ("Theo", None, None), (None, "extra", "ignored")],
        [("ally", "Mara protects Theo"), ("enemy", None)],
        [("Gate law", "Who controls it?", "open"), ("Lost key", None, None)],
    )
    result = await book_series_snapshot(db, uuid.uuid4(), "Atlas I")
    assert result is not None
    assert "Previous volume context: Atlas I" in result
    assert "Chapter 1 (Opening): First summary" in result
    assert "Key events: Arrival" in result
    assert "Mara (lead): Learns trust" in result
    assert "Theo: role in progress" in result
    assert "Mara protects Theo" in result and "enemy" in result
    assert "Lost key [unknown]: No detail yet." in result

    assert await book_series_snapshot(_FakeDB([], [], [], []), uuid.uuid4(), "Empty") is None


def test_extract_dialogue_samples_by_character_matches_nearby_names():
    text = 'Kael muttered, "Keep moving." Elder Mira replied, "We proceed with care."'

    samples = extract_dialogue_samples_by_character(
        text,
        [
            {"name": "Kael", "aliases": []},
            {"name": "Elder Mira", "aliases": ["Mira"]},
        ],
    )

    assert samples["Kael"] == ["Keep moving."]
    assert samples["Elder Mira"] == ["We proceed with care."]


def test_compute_voice_metrics_tracks_formality_and_punctuation():
    metrics = compute_voice_metrics(
        [
            "We shall proceed with caution, therefore remain alert.",
            "Do you understand? Excellent!",
        ]
    )

    assert metrics["sample_dialogue_count"] == 2
    assert metrics["sample_word_count"] > 5
    assert metrics["formality_score_x1000"] > 0
    assert metrics["question_rate_x1000"] > 0
    assert metrics["exclamation_rate_x1000"] > 0


def test_score_voice_match_penalizes_drift_and_explains_signals():
    profile = compute_voice_metrics(
        [
            "No. Move.",
            "Keep low. Stay sharp.",
        ]
    )
    sample = compute_voice_metrics(
        [
            "We should, perhaps, proceed with greater delicacy and caution.",
            "Do you agree with this approach?",
        ]
    )

    score, signals = score_voice_match(profile, sample)

    assert score < 70
    assert signals
