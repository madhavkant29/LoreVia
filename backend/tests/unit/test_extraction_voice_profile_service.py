import uuid
from types import SimpleNamespace

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
@pytest.mark.parametrize("generation_id", [None, uuid.uuid4()])
async def test_refresh_chapter_voice_profiles_creates_new_profile_in_character_generation(
    monkeypatch, generation_id
):
    book = SimpleNamespace(id=uuid.uuid4())
    character = SimpleNamespace(
        id=uuid.uuid4(), name="Ada", aliases=["A"], generation_id=generation_id
    )
    db = _FakeDb()

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
        chapter_text='Ada said, "I can\'t stop now."',
        existing_characters=[character],
    )

    assert refreshed == 1
    assert db.executed == 1
    assert len(db.added) == 1
    assert db.added[0].book_id == book.id
    assert db.added[0].character_id == character.id
    assert db.added[0].generation_id == generation_id
    assert db.added[0].sample_word_count == 4


@pytest.mark.asyncio
async def test_refresh_chapter_voice_profiles_updates_existing_profile(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    generation_id = uuid.uuid4()
    character = SimpleNamespace(
        id=uuid.uuid4(), name="Ada", aliases=[], generation_id=generation_id
    )
    existing_profile = SimpleNamespace(
        character_id=character.id,
        generation_id=generation_id,
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
        chapter_text='Ada said, "Stop." Ada replied, "Go."',
        existing_characters=[character],
    )

    assert refreshed == 1
    assert db.added == []
    assert snapshots[0]["sample_dialogue_count"] == 2
    assert snapshots[0]["dominant_markers"] == {"old": 1}
    assert existing_profile.sample_dialogue_count == 4
    assert existing_profile.sample_word_count == 12
    assert existing_profile.generation_id == generation_id


@pytest.mark.asyncio
async def test_curated_character_reuses_legacy_generation_voice_profile(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    character = SimpleNamespace(id=uuid.uuid4(), name="Ada", aliases=[], generation_id=None)
    old_generation_id = uuid.uuid4()
    profile = SimpleNamespace(
        character_id=character.id,
        generation_id=old_generation_id,
        dominant_markers={},
        signature_phrases=[],
    )
    db = _FakeDb([profile])
    monkeypatch.setattr(
        extraction_voice_profile_service,
        "compute_voice_metrics",
        lambda _samples: {"sample_dialogue_count": 1},
    )
    monkeypatch.setattr(
        extraction_voice_profile_service,
        "merge_voice_profile_metrics",
        lambda _current, _metrics: {"sample_dialogue_count": 2},
    )

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=book,
        chapter_text='Ada said, "I can wait."',
        existing_characters=[character],
    )

    assert refreshed == 1
    assert db.added == []
    assert profile.generation_id is None
    assert profile.sample_dialogue_count == 2


@pytest.mark.asyncio
async def test_ambiguous_legacy_voice_profiles_are_not_mutated_or_duplicated(monkeypatch):
    character = SimpleNamespace(id=uuid.uuid4(), name="Ada", aliases=[], generation_id=None)
    profiles = [
        SimpleNamespace(character_id=character.id, generation_id=uuid.uuid4()) for _ in range(2)
    ]
    db = _FakeDb(profiles)

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text='Ada said, "I can wait."',
        existing_characters=[character],
    )

    assert refreshed == 0
    assert db.added == []
    assert all(profile.generation_id is not None for profile in profiles)


@pytest.mark.asyncio
async def test_refresh_chapter_voice_profiles_skips_database_when_no_samples():
    db = _FakeDb()

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text="No dialogue.",
        existing_characters=[],
    )

    assert refreshed == 0
    assert db.executed == 0
    assert db.added == []


@pytest.mark.asyncio
async def test_voice_profile_uses_speaker_attribution_not_nearest_character_name():
    mara = SimpleNamespace(id=uuid.uuid4(), name="Mara", aliases=[], generation_id=None)
    lina = SimpleNamespace(id=uuid.uuid4(), name="Lina", aliases=[], generation_id=None)
    db = _FakeDb()

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text='Mara watched the door. "The gate is open," Lina said.',
        existing_characters=[mara, lina],
    )

    assert refreshed == 1
    assert [profile.character_id for profile in db.added] == [lina.id]
    assert db.added[0].sample_dialogue_count == 1


@pytest.mark.asyncio
async def test_tentative_pronoun_speech_does_not_become_established_voice_profile():
    mara = SimpleNamespace(id=uuid.uuid4(), name="Mara", aliases=[], generation_id=None)
    db = _FakeDb()

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text='Mara closed the door. She said, "Go now."',
        existing_characters=[mara],
    )

    assert refreshed == 0
    assert db.executed == 0


@pytest.mark.asyncio
async def test_shared_surname_alias_does_not_assign_dialogue_to_two_profiles():
    madame = SimpleNamespace(
        id=uuid.uuid4(), name="Madame Arlen", aliases=["Arlen"], generation_id=None
    )
    monsieur = SimpleNamespace(
        id=uuid.uuid4(), name="Monsieur Arlen", aliases=["Arlen"], generation_id=None
    )
    db = _FakeDb()

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text='Arlen said, "Wait." Madame Arlen replied, "Please stay."',
        existing_characters=[madame, monsieur],
    )

    assert refreshed == 1
    assert [profile.character_id for profile in db.added] == [madame.id]
    assert db.added[0].sample_dialogue_count == 1


@pytest.mark.asyncio
async def test_long_quote_overlap_counts_as_one_independent_voice_sample():
    mara = SimpleNamespace(id=uuid.uuid4(), name="Mara", aliases=[], generation_id=None)
    db = _FakeDb()
    long_quote = " ".join(f"word{index}" for index in range(180))

    refreshed = await refresh_chapter_voice_profiles(
        db,
        book=SimpleNamespace(id=uuid.uuid4()),
        chapter_text=f'Mara said, "{long_quote}"',
        existing_characters=[mara],
    )

    assert refreshed == 1
    assert db.added[0].sample_dialogue_count == 1
    assert db.added[0].sample_word_count == 180
