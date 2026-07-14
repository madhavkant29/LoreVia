from types import SimpleNamespace
import uuid

import pytest

from app.services import extraction_voice_profile_service
from app.services.extraction_voice_profile_service import refresh_chapter_voice_profiles


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeDb:
    def __init__(self, profiles=None):
        self.profiles = profiles or []
        self.added = []
        self.executed = 0

    async def execute(self, _statement):
        self.executed += 1
        return _FakeResult(self.profiles)

    def add(self, value):
        self.added.append(value)


@pytest.mark.asyncio
async def test_refresh_chapter_voice_profiles_creates_new_profile(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    character = SimpleNamespace(id=uuid.uuid4(), name="Ada", aliases=["A"])
    db = _FakeDb()

    monkeypatch.setattr(
        extraction_voice_profile_service,
        "extract_dialogue_samples_by_character",
        lambda text, roster: {"Ada": ["I can't stop now."]},
    )
    monkeypatch.setattr(
        extraction_voice_profile_service,
        "compute_voice_metrics",
        lambda samples: {"sample_dialogue_count": len(samples), "sample_word_count": 4},
    )
    monkeypatch.setattr(
        extraction_voice_profile_service,
        "merge_voice_profile_metrics",
        lambda current, metrics: {
            "sample_dialogue_count": metrics["sample_dialogue_count"],
            "sample_word_count": metrics["sample_word_count"],
        },
    )

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=book,
        chapter_text="Ada said something.",
        existing_characters=[character],
    )

    assert refreshed == 1
    assert db.executed == 1
    assert len(db.added) == 1
    assert db.added[0].book_id == book.id
    assert db.added[0].character_id == character.id
    assert db.added[0].sample_word_count == 4


@pytest.mark.asyncio
async def test_refresh_chapter_voice_profiles_updates_existing_profile(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    character = SimpleNamespace(id=uuid.uuid4(), name="Ada", aliases=[])
    existing_profile = SimpleNamespace(
        character_id=character.id,
        sample_dialogue_count=2,
        sample_word_count=10,
        avg_sentence_length=5,
        avg_word_length_x100=400,
        contraction_rate_x1000=0,
        question_rate_x1000=0,
        exclamation_rate_x1000=0,
        ellipsis_rate_x1000=0,
        dash_rate_x1000=0,
        uppercase_rate_x1000=0,
        formality_score_x1000=0,
        lexical_complexity_x1000=0,
        emotional_intensity_x1000=0,
        dominant_markers={"old": 1},
        signature_phrases=["old phrase"],
    )
    db = _FakeDb([existing_profile])
    snapshots = []

    monkeypatch.setattr(
        extraction_voice_profile_service,
        "extract_dialogue_samples_by_character",
        lambda text, roster: {"Ada": ["Stop.", "Go."]},
    )
    monkeypatch.setattr(
        extraction_voice_profile_service,
        "compute_voice_metrics",
        lambda samples: {"sample_dialogue_count": len(samples), "sample_word_count": 2},
    )

    def fake_merge(current, metrics):
        snapshots.append(current)
        return {"sample_dialogue_count": 4, "sample_word_count": 12}

    monkeypatch.setattr(
        extraction_voice_profile_service,
        "merge_voice_profile_metrics",
        fake_merge,
    )

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=book,
        chapter_text="Ada speaks.",
        existing_characters=[character],
    )

    assert refreshed == 1
    assert db.added == []
    assert snapshots[0]["sample_dialogue_count"] == 2
    assert snapshots[0]["dominant_markers"] == {"old": 1}
    assert existing_profile.sample_dialogue_count == 4
    assert existing_profile.sample_word_count == 12


@pytest.mark.asyncio
async def test_refresh_chapter_voice_profiles_skips_database_when_no_samples(monkeypatch):
    db = _FakeDb()
    monkeypatch.setattr(
        extraction_voice_profile_service,
        "extract_dialogue_samples_by_character",
        lambda text, roster: {},
    )

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text="No dialogue.",
        existing_characters=[],
    )

    assert refreshed == 0
    assert db.executed == 0
    assert db.added == []
