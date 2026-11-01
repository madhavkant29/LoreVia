import json
import uuid

import pytest
from fastapi import HTTPException
from httpx import Request, Response
from openai import APIStatusError
from sqlalchemy.dialects import postgresql

from app.services.voice_consistency_review_service import (
    VoiceBaselineSourceError,
    apply_voice_review_decisions,
    load_voice_baseline_samples,
    load_voice_review_characters,
    personalize_voice_review_payload,
    review_voice_sections,
    save_voice_review_decision,
)
from app.utils.ingestion_utils import build_chapter_storage_key
from app.utils.llm_usage_utils import LLMIncompleteResponseError
from app.utils.voice_review_utils import (
    VoiceReviewFormatError,
    attributed_voice_samples,
    first_person_narration_samples,
    voice_baseline_sufficient,
    voice_ranges_cover_text,
)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _DB:
    def __init__(self, rows, source_rows=None):
        self.rows = rows
        self.source_rows = source_rows
        self.statement = None
        self.committed = False

    async def execute(self, statement):
        self.statement = statement
        return _Result(
            self.source_rows
            if self.source_rows is not None
            else [(chapter_number, source) for source, chapter_number in self.rows]
        )

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_voice_cast_query_excludes_large_unused_character_columns():
    class CastDB:
        statement = None

        async def scalars(self, statement):
            self.statement = statement
            return _Result([])

    db = CastDB()
    assert await load_voice_review_characters(db, book_id=uuid.uuid4()) == []
    sql = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "characters.aliases" in sql
    assert "characters.analysis_metadata" in sql
    assert "characters.embedding" not in sql
    assert "characters.growth_events" in sql


SHORT_NARRATOR_SOURCE = "\n\n".join(
    f"I {['counted', 'folded', 'followed', 'watched', 'marked', 'opened'][number % 6]} "
    f"{['lamps', 'letters', 'footsteps', 'clouds', 'boats', 'windows'][number % 6]} "
    f"near {['station', 'harbor', 'market', 'bridge', 'courtyard'][number % 5]} today."
    for number in range(24)
)


@pytest.fixture(autouse=True)
def stored_manuscript_sources(monkeypatch):
    monkeypatch.setattr(
        "app.services.voice_consistency_review_service.download_book",
        lambda source: source.encode(),
    )


def test_saved_voice_decision_suppresses_only_matching_finding_without_mutating_cached_payload():
    matched = {"finding_key": "a" * 64, "title": "Register shift"}
    other = {"finding_key": "b" * 64, "title": "Pacing shift"}
    payload = {
        "review": {
            "issues": [matched, other],
            "overall_verdict": "Register shift is concerning.",
        },
        "coverage": {"total_characters": 60},
    }

    personalized = apply_voice_review_decisions(
        payload,
        {matched["finding_key"]: {"decision": "intentional", "note": "Deliberate"}},
    )

    assert personalized["review"]["issues"] == [other]
    assert personalized["review"]["overall_verdict"] == (
        "New voice findings to review: 1. Previously reviewed findings shown below: 1."
    )
    assert personalized["suppressed_findings"] == [{**matched, "decision": "intentional"}]
    assert personalized["coverage"] == payload["coverage"]
    assert payload["review"]["issues"] == [matched, other]
    assert payload["review"]["overall_verdict"] == "Register shift is concerning."


def test_saved_voice_decisions_do_not_repeat_dismissed_claims_in_headline():
    issue = {"finding_key": "a" * 64, "title": "Register shift"}
    payload = {
        "review": {
            "status": "complete",
            "issues": [issue],
            "overall_verdict": "Mara's dialogue is inconsistent.",
        }
    }

    personalized = apply_voice_review_decisions(
        payload, {issue["finding_key"]: {"decision": "intentional", "note": None}}
    )

    assert personalized["review"]["issues"] == []
    assert "inconsistent" not in personalized["review"]["overall_verdict"]
    assert personalized["suppressed_findings"][0]["decision"] == "intentional"


def test_saved_voice_decisions_keep_partial_evidence_limitations_visible():
    issue = {"finding_key": "a" * 64, "title": "Possible shift"}
    payload = {
        "review": {
            "status": "partial_evidence",
            "issues": [issue],
            "overall_verdict": "A possible shift was found.",
        }
    }

    personalized = apply_voice_review_decisions(
        payload, {issue["finding_key"]: {"decision": "resolved", "note": None}}
    )

    assert personalized["review"]["issues"] == []
    assert "listed separately" in personalized["review"]["overall_verdict"]
    assert "limited by the available evidence" in personalized["review"]["overall_verdict"]


@pytest.mark.asyncio
async def test_repeat_voice_review_loads_saved_decision_for_user(monkeypatch):
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    finding_key = "a" * 64
    captured = {}

    async def fake_load(db, *, book_id, user_id, keys):
        captured.update({"book_id": book_id, "user_id": user_id, "keys": keys})
        return {finding_key: {"decision": "resolved", "note": None}}

    monkeypatch.setattr(
        "app.services.voice_consistency_review_service.load_voice_review_decisions",
        fake_load,
    )
    payload = {"review": {"issues": [{"finding_key": finding_key, "title": "Shift"}]}}

    result = await personalize_voice_review_payload(
        _DB([]), book_id=book_id, user_id=user_id, payload=payload
    )

    assert captured == {"book_id": book_id, "user_id": user_id, "keys": [finding_key]}
    assert result["review"]["issues"] == []
    assert result["suppressed_findings"][0]["decision"] == "resolved"


@pytest.mark.asyncio
async def test_saving_voice_decision_commits_upsert_for_same_finding():
    class DecisionDB(_DB):
        committed = False

        async def commit(self):
            self.committed = True

    db = DecisionDB([])
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    finding_key = "c" * 64

    result = await save_voice_review_decision(
        db,
        book_id=book_id,
        user_id=user_id,
        finding_key=finding_key,
        decision="incorrect",
        note="Wrong speaker",
    )

    assert result == {
        "finding_key": finding_key,
        "decision": "incorrect",
        "note": "Wrong speaker",
    }
    assert db.committed
    assert "ON CONFLICT" in str(db.statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_baseline_retrieval_keeps_exact_quotes_and_excludes_submitted_source():
    submitted = 'Mara said, "No way, dude." ' * 12
    db = _DB(
        [
            ('Mara said, "I shall arrive at dawn." ' * 4, 1),
            (submitted, 2),
            ('A guard replied, "Leave now." Mara whispered, "I can wait."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=None,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall arrive at dawn."),
    ]
    assert samples[0]["source_end"] - samples[0]["source_start"] == len(samples[0]["excerpt"])


@pytest.mark.asyncio
async def test_baseline_retrieval_uses_stored_manuscript_when_embedding_chunks_are_missing(
    monkeypatch,
):
    texts = {
        "chapter-one": b"Unrelated history. " * 300 + b'Mara said, "I shall return before dawn."',
        "chapter-two": b'Mara said, "The gate is open."',
    }
    assert texts["chapter-one"].index(b"Mara said") > 4_000
    monkeypatch.setattr(
        "app.services.voice_consistency_review_service.download_book", texts.__getitem__
    )
    db = _DB([], source_rows=[(1, "chapter-one"), (2, "chapter-two")])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "The gate is open."',
        submitted_chapter=2,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]
    assert db.committed
    assert "chapters.number <" in str(db.statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
@pytest.mark.parametrize("stored_key", [None, "stale-chapter-key"])
async def test_baseline_retrieval_uses_standard_chapter_key_when_recorded_key_is_missing_or_stale(
    monkeypatch, stored_key
):
    book_id = uuid.uuid4()
    fallback_key = build_chapter_storage_key(book_id, 1)
    calls = []

    def load_source(key):
        calls.append(key)
        if key == fallback_key:
            return b'Mara said, "I shall wait by the bridge."'
        raise OSError("recorded key unavailable")

    monkeypatch.setattr("app.utils.ingestion_utils.download_book", load_source)
    monkeypatch.setattr("app.services.voice_consistency_review_service.download_book", load_source)
    db = _DB([], source_rows=[(1, stored_key)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=book_id,
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "The gate is open."',
        submitted_chapter=2,
    )

    assert [sample["excerpt"] for sample in samples] == ["I shall wait by the bridge."]
    assert calls == ([stored_key, fallback_key] if stored_key else [fallback_key])
    assert db.committed


@pytest.mark.asyncio
async def test_missing_immutable_baseline_never_uses_older_standard_chapter(monkeypatch):
    book_id = uuid.uuid4()
    current_key = f"chapters/{book_id}/1/{uuid.uuid4().hex}.txt"
    calls: list[str] = []

    def load(key):
        calls.append(key)
        if key == current_key:
            raise FileNotFoundError(key)
        return b'Mara said, "Old baseline."'

    monkeypatch.setattr("app.services.voice_consistency_review_service.download_book", load)
    monkeypatch.setattr("app.utils.ingestion_utils.download_book", load)
    db = _DB([], source_rows=[(1, current_key)])

    with pytest.raises(VoiceBaselineSourceError, match="voice_baseline_source_unavailable"):
        await load_voice_baseline_samples(
            db,
            book_id=book_id,
            character_name="Mara",
            aliases=[],
            submitted_text='Mara said, "New text."',
            submitted_chapter=2,
        )
    assert calls == [current_key]


@pytest.mark.asyncio
async def test_baseline_retrieval_keeps_earlier_repeated_dialogue_for_known_chapter():
    submitted = 'Mara said, "The gate is open."'
    earlier = submitted + ' Mara said, "I shall wait until dawn by the bridge."'
    db = _DB([(earlier, 1), (submitted, 2)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=2,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "The gate is open."),
        (1, "I shall wait until dawn by the bridge."),
    ]


@pytest.mark.asyncio
async def test_baseline_retrieval_excludes_copied_earlier_passage_despite_selected_chapter():
    copied = (
        'Mara said, "We will cross the northern bridge at dawn." '
        "She folded the map and marked three safe roads through the hills. "
        "The watchtower stood beyond the river near the old mill."
    )
    db = _DB(
        [
            ('Mara said, "The harbor road is open."', 1),
            ("Unrelated opening. " + copied + " A different ending.", 2),
            ('Mara said, "The bell is ringing."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=copied,
        submitted_chapter=3,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "The harbor road is open."),
    ]


@pytest.mark.asyncio
async def test_baseline_retrieval_ignores_stale_derived_quote_and_uses_current_chapter(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.voice_consistency_review_service.download_book",
        lambda _key: b'Mara said, "The current source says wait."',
    )
    db = _DB(
        [('Mara said, "The obsolete draft says leave."', 1)],
        source_rows=[(1, "current-chapter")],
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "I am listening."',
        submitted_chapter=2,
    )

    assert [sample["excerpt"] for sample in samples] == ["The current source says wait."]
    assert "book_chunks" not in str(db.statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_baseline_source_fallback_reuses_download_for_multiple_characters(
    monkeypatch,
):
    calls = []

    def load_source(key):
        calls.append(key)
        return b'Mara said, "I will wait." Lina replied, "I will return."'

    monkeypatch.setattr("app.services.voice_consistency_review_service.download_book", load_source)
    db = _DB([], source_rows=[(1, "shared-chapter")])
    source_cache = {}

    mara = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="A different scene.",
        submitted_chapter=2,
        source_cache=source_cache,
    )
    lina = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Lina",
        aliases=[],
        submitted_text="A different scene.",
        submitted_chapter=2,
        source_cache=source_cache,
    )

    assert calls == ["shared-chapter"]
    assert [item["excerpt"] for item in mara] == ["I will wait."]
    assert [item["excerpt"] for item in lina] == ["I will return."]


@pytest.mark.asyncio
async def test_baseline_retrieval_reports_unavailable_stored_source_instead_of_empty_success(
    monkeypatch,
):
    def missing_source(_key):
        raise OSError("storage temporarily unavailable")

    monkeypatch.setattr(
        "app.services.voice_consistency_review_service.download_book", missing_source
    )
    monkeypatch.setattr("app.utils.ingestion_utils.download_book", missing_source)
    db = _DB([], source_rows=[(1, "missing-chapter")])

    with pytest.raises(VoiceBaselineSourceError, match="voice_baseline_source_unavailable"):
        await load_voice_baseline_samples(
            db,
            book_id=uuid.uuid4(),
            character_name="Mara",
            aliases=[],
            submitted_text='Mara said, "Later."',
            submitted_chapter=2,
        )


@pytest.mark.asyncio
async def test_short_submitted_passage_infers_chapter_and_excludes_current_and_future_voice():
    submitted = 'Mara said, "Stay near."'
    db = _DB(
        [
            ('Mara said, "I shall return before dawn."', 1),
            (submitted + ' Mara said, "The gate is closed."', 2),
            ('Mara said, "We can leave now."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=None,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]


@pytest.mark.asyncio
async def test_exact_short_custom_passage_excludes_current_and_future_chapters():
    submitted = 'Mara said, "Go."'
    db = _DB(
        [
            ('Mara said, "I shall return before dawn."', 1),
            (submitted, 2),
            ('Mara said, "We can leave now."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=None,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]


@pytest.mark.asyncio
async def test_short_attributed_quote_in_longer_chapter_excludes_current_and_future_voice():
    submitted = 'Mara said, "Go."'
    db = _DB(
        [
            ('Mara said, "I shall return before dawn."', 1),
            ("The storm ended. " + submitted + " Lina nodded.", 2),
            ('Mara said, "We can leave now."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=None,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]


@pytest.mark.asyncio
async def test_exact_short_copied_chapter_is_not_used_as_baseline_when_chapter_selected():
    submitted = 'Mara said, "Go."'
    db = _DB(
        [
            ('Mara said, "I shall return before dawn."', 1),
            (submitted, 2),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=3,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]


@pytest.mark.asyncio
async def test_submitted_passage_in_first_chapter_returns_no_future_baseline():
    submitted = 'Mara said, "Stay near."'
    db = _DB(
        [
            (submitted + ' Mara said, "The gate is closed."', 1),
            ('Mara said, "We can leave now."', 2),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=submitted,
        submitted_chapter=None,
    )

    assert samples == []


@pytest.mark.asyncio
async def test_edited_submitted_passage_excludes_current_and_future_chapters():
    source = 'Mara said, "Stay near." ' + " ".join(f"detail{index}" for index in range(40))
    edited = source.replace("detail18", "revision18")
    db = _DB(
        [
            ('Mara said, "I shall return before dawn."', 1),
            (source, 2),
            ('Mara said, "We can leave now."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=edited,
        submitted_chapter=None,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]


@pytest.mark.asyncio
async def test_short_edited_custom_passage_does_not_become_its_own_voice_baseline():
    passage = (
        'Mara said, "Stay near the gate until the storm breaks and the watch changes '
        'at dawn." The lantern shook in her hand.'
    )
    source = "Rain swept through the empty square. " + passage + " The watch crossed the bridge."
    edited = passage.replace("the watch changes", "the patrol changes")
    db = _DB(
        [
            ('Mara said, "I shall return before dawn."', 1),
            (source, 2),
            ('Mara said, "We can leave now."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text=edited,
        submitted_chapter=None,
    )

    assert [(sample["chapter_number"], sample["excerpt"]) for sample in samples] == [
        (1, "I shall return before dawn."),
    ]


@pytest.mark.asyncio
async def test_baseline_retrieval_considers_late_source_after_many_earlier_chapters():
    db = _DB(
        [("The bridge stood empty.", chapter) for chapter in range(1, 251)]
        + [('Mara said, "I shall return at dawn."', 251)]
    )
    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "Later."',
        submitted_chapter=252,
    )

    assert db.committed
    assert [
        (sample["character_name"], sample["chapter_number"], sample["excerpt"])
        for sample in samples
    ] == [("Mara", 251, "I shall return at dawn.")]
    assert samples[0]["source_end"] - samples[0]["source_start"] == len(samples[0]["excerpt"])


@pytest.mark.asyncio
async def test_baseline_retrieval_considers_late_chapters_after_first_sixteen_quotes():
    rows = [
        (f'Mara said, "Routine words from chapter {chapter}."', chapter) for chapter in range(1, 21)
    ]
    rows[-1] = ('Mara said, "The copper compass points to the old bridge."', 20)
    db = _DB(rows)

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="Opening narration. " * 300
        + 'Mara said, "The copper compass points north."',
        submitted_chapter=21,
        max_samples=6,
    )

    assert len(samples) == 6
    assert any(sample["chapter_number"] == 20 for sample in samples)


@pytest.mark.asyncio
async def test_dialogue_baseline_expands_short_quotes_until_word_threshold_is_met():
    source = " ".join(f'Mara said, "Guard sector{index} now."' for index in range(28))
    db = _DB([(source, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "Wait beside the gate."',
        submitted_chapter=2,
    )

    assert 20 <= len(samples) <= 28
    assert voice_baseline_sufficient(samples, min_words=60)
    assert sum(len(item["excerpt"]) for item in samples) <= 12_000
    assert all(item["chapter_number"] == 1 for item in samples)


@pytest.mark.asyncio
async def test_dialogue_baseline_can_reach_word_floor_from_many_one_word_quotes():
    source = " ".join(f'Mara said, "Sector{index}!"' for index in range(80))
    db = _DB([(source, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "Wait here."',
        submitted_chapter=2,
    )

    assert 60 <= len(samples) < 80
    assert voice_baseline_sufficient(samples, min_words=60)
    assert (
        sum(len(f"Chapter {item['chapter_number']}: {item['excerpt']}") for item in samples)
        <= 12_000
    )


@pytest.mark.asyncio
async def test_dialogue_baseline_respects_explicit_sample_cap_when_evidence_is_short():
    source = " ".join(f'Mara said, "Guard sector{index} now."' for index in range(28))
    db = _DB([(source, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "Wait beside the gate."',
        submitted_chapter=2,
        max_samples=16,
    )

    assert len(samples) == 16
    assert not voice_baseline_sufficient(samples, min_words=60)


@pytest.mark.asyncio
async def test_baseline_retrieval_never_uses_future_chapter_as_established_voice():
    db = _DB(
        [
            ('Mara said, "I shall wait."', 1),
            ('Mara said, "I use slang now."', 3),
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text='Mara said, "Wait for me."',
        submitted_chapter=2,
    )

    assert [sample["chapter_number"] for sample in samples] == [1]
    compiled = str(db.statement.compile(dialect=postgresql.dialect()))
    assert "chapters.number <" in compiled


@pytest.mark.asyncio
async def test_baseline_retrieval_includes_verified_narrator_tagged_dialogue():
    db = _DB([('I am Mara Vale. I said, "Keep the lamps low."', 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara Vale",
        aliases=[],
        submitted_text='Mara Vale said, "Wait until morning."',
        submitted_chapter=2,
        known_character_names=["Mara Vale", "Lina Moss"],
    )

    assert [sample["excerpt"] for sample in samples] == ["Keep the lamps low."]


@pytest.mark.asyncio
async def test_baseline_retrieval_omits_ambiguous_first_person_dialogue():
    db = _DB(
        [
            (
                'I am Mara Vale. I said, "Keep the lamps low." '
                'I am Lina Moss. I said, "Open the gate."',
                1,
            )
        ]
    )

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara Vale",
        aliases=[],
        submitted_text='Mara Vale said, "Wait until morning."',
        submitted_chapter=2,
        known_character_names=["Mara Vale", "Lina Moss"],
    )

    assert samples == []


@pytest.mark.asyncio
async def test_baseline_retrieval_with_zero_sample_limit_skips_database():
    db = _DB([])
    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="A passage",
        submitted_chapter=None,
        max_samples=0,
    )
    assert samples == []
    assert db.statement is None


@pytest.mark.asyncio
async def test_narrator_baseline_uses_first_person_prose_outside_submitted_chapter():
    prose = (
        "I walked back across the square and wondered whether the lamps would stay lit "
        "until morning. My coat was damp from the rain, and I thought of the long road "
        "we had crossed yesterday before the train arrived."
    )
    db = _DB([(prose, 1), (prose, 2)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Narrator",
        aliases=[],
        submitted_text="A different first-person scene.",
        submitted_chapter=2,
        voice_mode="first_person_narration",
    )

    assert len(samples) == 1
    assert samples[0]["chapter_number"] == 1
    assert samples[0]["excerpt"] == prose


@pytest.mark.asyncio
async def test_narrator_baseline_expands_short_paragraphs_only_until_sufficient():
    db = _DB([(SHORT_NARRATOR_SOURCE, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="I waited by the gate after dusk.",
        submitted_chapter=2,
        voice_mode="first_person_narration",
    )

    assert 20 <= len(samples) <= 24
    assert voice_baseline_sufficient(samples, min_words=120)
    assert sum(len(item["excerpt"]) for item in samples) <= 12_000
    assert all(item["chapter_number"] == 1 for item in samples)


@pytest.mark.asyncio
async def test_narrator_baseline_respects_explicit_sample_cap():
    db = _DB([(SHORT_NARRATOR_SOURCE, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="I waited by the gate after dusk.",
        submitted_chapter=2,
        voice_mode="first_person_narration",
        max_samples=8,
    )

    assert len(samples) == 8
    assert not voice_baseline_sufficient(samples, min_words=120)


@pytest.mark.asyncio
async def test_narrator_baseline_excludes_explicitly_different_point_of_view():
    mara_prose = (
        "I am Mara. I crossed the market at dawn while the shutters were still closed. "
        "My coat held the rain, and I counted the lamps along the road as I walked "
        "toward the bridge to meet the watch captain before breakfast."
    )
    lina_prose = (
        "I am Lina. I took the northern path after the watch had changed. My hands "
        "were cold, and I could hear the river below me while I searched for the "
        "missing papers that Mara had left inside the old station."
    )
    db = _DB([(mara_prose, 1), (lina_prose, 2)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="I crossed the square again and remembered the old station.",
        submitted_chapter=3,
        voice_mode="first_person_narration",
        known_character_names=["Mara", "Lina"],
    )

    assert [sample["chapter_number"] for sample in samples] == [1]
    assert samples[0]["attribution_confidence"] == "explicit"


@pytest.mark.asyncio
async def test_narrator_baseline_without_identity_evidence_is_marked_unverified():
    prose = (
        "I walked beside the river before sunrise and waited for the station doors "
        "to open. My coat was damp from the rain, and I thought about the promise "
        "I had made to the watch captain late the previous evening."
    )
    db = _DB([(prose, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Mara",
        aliases=[],
        submitted_text="I returned to the square after lunch.",
        submitted_chapter=2,
        voice_mode="first_person_narration",
        known_character_names=["Mara", "Lina"],
    )

    assert len(samples) == 1
    assert samples[0]["attribution_confidence"] == "unverified_narrator"


@pytest.mark.asyncio
async def test_narrator_baseline_with_direct_address_remains_tentative():
    prose = (
        'The clerk said, "I will leave you here, Monsieur Vale." I thanked him. '
        "I walked along the river before sunrise and waited for the station doors "
        "to open. My coat was damp from the rain, and I thought about the promise "
        "I had made to the watch captain late the previous evening."
    )
    db = _DB([(prose, 1)])

    samples = await load_voice_baseline_samples(
        db,
        book_id=uuid.uuid4(),
        character_name="Monsieur Vale",
        aliases=[],
        submitted_text="I returned to the square after lunch.",
        submitted_chapter=2,
        voice_mode="first_person_narration",
        known_character_names=["Monsieur Vale", "Madame Vale"],
    )

    assert samples
    assert all(sample["attribution_confidence"] == "contextual" for sample in samples)


@pytest.mark.asyncio
async def test_twelve_thousand_character_review_processes_tail_and_returns_verified_coverage():
    tail = 'Mara said, "No way, dude."'
    passage = ("Opening narration. " * 700)[: 12_000 - len(tail)] + tail
    baseline = [{"chapter_number": 1, "excerpt": "I shall arrive at dawn."}]
    seen_ranges = []

    async def model_call(section):
        seen_ranges.append((section["start"], section["end"]))
        issues = []
        if "No way, dude." in section["text"]:
            issues.append(
                {
                    "character_name": "Mara",
                    "classification": "possible",
                    "severity": "moderate",
                    "title": "Register shift",
                    "description": "The register changed.",
                    "submitted_excerpt": "No way, dude.",
                    "baseline_excerpt": "I shall arrive at dawn.",
                    "baseline_chapter_number": 1,
                    "confidence": 0.7,
                    "revision_direction": "Check the register.",
                    "intentionality_prompt": "Is this intentional?",
                }
            )
        return json.dumps(
            {"issues": issues, "overall_verdict": "Review completed for this section."}
        )

    result = await review_voice_sections(
        passage,
        character_name="Mara",
        baseline_samples=baseline,
        submitted_samples=[{"excerpt": "No way, dude."}],
        model_call=model_call,
    )

    assert len(passage) == 12_000
    assert len(seen_ranges) == 1
    assert result["issues"][0]["submitted_excerpt"] == "No way, dude."
    assert result["coverage"]["total_characters"] == len(passage)
    assert result["coverage"]["processed_ranges"][-1]["end"] == len(passage)
    assert result["coverage"]["unattributed_ranges"]
    assert result["coverage"]["compared_ranges"] == [
        {
            "start": passage.index("No way, dude."),
            "end": passage.index("No way, dude.") + len("No way, dude."),
        }
    ]
    assert result["coverage"]["not_compared_ranges"][-1] == {
        "start": len(passage) - 1,
        "end": len(passage),
    }
    assert voice_ranges_cover_text(
        [
            *result["coverage"]["processed_ranges"],
            *result["coverage"]["unattributed_ranges"],
        ],
        len(passage),
    )


@pytest.mark.asyncio
async def test_first_person_review_accepts_grounded_finding_after_character_4000():
    phrase = "I could no longer recognize my own words."
    passage = (
        "I crossed the empty square. "
        + "The rain had stopped, but the street stayed silent. " * 210
        + phrase
    )
    baseline = [{"chapter_number": 1, "excerpt": "I kept every promise I made."}]
    submitted = first_person_narration_samples(passage, chapter_number=2)
    assert passage.index(phrase) > 4_000

    async def model_call(section):
        issues = []
        if phrase in section["text"]:
            issues.append(
                {
                    "character_name": "Narrator",
                    "classification": "possible",
                    "severity": "moderate",
                    "title": "Shift in self-description",
                    "description": "The narrator's confidence changes.",
                    "submitted_excerpt": phrase,
                    "baseline_excerpt": baseline[0]["excerpt"],
                    "baseline_chapter_number": 1,
                    "confidence": 0.6,
                    "revision_direction": "Keep the doubt but show its source.",
                    "intentionality_prompt": "Is this change intentional?",
                }
            )
        return json.dumps({"issues": issues, "overall_verdict": "Section reviewed."})

    result = await review_voice_sections(
        passage,
        character_name="Narrator",
        baseline_samples=baseline,
        submitted_samples=submitted,
        model_call=model_call,
    )

    assert result["issues"][0]["submitted_excerpt"] == phrase
    assert result["coverage"]["processed_ranges"][-1]["end"] == len(passage)
    assert result["coverage"]["compared_ranges"][-1]["end"] == len(passage)


@pytest.mark.asyncio
async def test_finding_decision_key_survives_unrelated_edits_but_isolated_by_chapter():
    baseline = [{"chapter_number": 1, "excerpt": "I shall return before dawn."}]
    issue = {
        "character_name": "Mara",
        "classification": "possible",
        "severity": "moderate",
        "title": "Register shift",
        "description": "The register changed.",
        "submitted_excerpt": "No way, dude.",
        "baseline_excerpt": "I shall return before dawn.",
        "baseline_chapter_number": 1,
        "confidence": 0.7,
        "revision_direction": "Check the register.",
        "intentionality_prompt": "Is this intentional?",
    }

    async def model_call(_section):
        return json.dumps({"issues": [issue], "overall_verdict": "Possible shift."})

    async def review(passage, chapter):
        result = await review_voice_sections(
            passage,
            character_name="Mara",
            baseline_samples=baseline,
            submitted_samples=[{"excerpt": "No way, dude."}],
            model_call=model_call,
            source_chapter=chapter,
        )
        return result["issues"][0]["finding_key"]

    first = await review('Mara said, "No way, dude." The door opened.', 2)
    assert first == await review('Mara said, "No way, dude." The door opened.', 2)
    assert first == await review('Mara said, "No way, dude." The door closed.', 2)
    assert first != await review('Mara said, "No way, dude." The door opened.', 3)


@pytest.mark.asyncio
async def test_repeated_quote_in_distant_sections_keeps_two_distinct_findings():
    quote = "No way, dude."
    passage = f'Mara said, "{quote}".' + (" The corridor was quiet." * 220)
    passage += f' Mara said, "{quote}".'
    baseline = [{"chapter_number": 1, "excerpt": "I shall return before dawn."}]

    async def model_call(section):
        issue = {
            "character_name": "Mara",
            "classification": "possible",
            "severity": "moderate",
            "title": "Register shift",
            "description": "The register changed.",
            "submitted_excerpt": quote,
            "baseline_excerpt": baseline[0]["excerpt"],
            "baseline_chapter_number": 1,
            "confidence": 0.7,
            "revision_direction": "Check the register.",
            "intentionality_prompt": "Is this intentional?",
        }
        return json.dumps(
            {
                "issues": [issue] if quote in section["text"] else [],
                "overall_verdict": "Section reviewed.",
            }
        )

    async def finding_keys(text):
        submitted = attributed_voice_samples(
            text, character_name="Mara", chapter_number=2, include_offsets=True
        )
        result = await review_voice_sections(
            text,
            character_name="Mara",
            baseline_samples=baseline,
            submitted_samples=submitted,
            model_call=model_call,
            source_chapter=2,
        )
        return [issue["finding_key"] for issue in result["issues"]]

    original_keys = await finding_keys(passage)
    assert len(original_keys) == 2
    assert original_keys[0] != original_keys[1]
    assert await finding_keys("The morning was still. " + passage) == original_keys


@pytest.mark.asyncio
async def test_voice_review_decision_key_changes_when_cited_evidence_changes():
    baseline = [
        {"chapter_number": 1, "excerpt": "I shall return before dawn."},
        {"chapter_number": 1, "excerpt": "I may return before dawn."},
    ]

    async def review(baseline_excerpt):
        async def model_call(_section):
            return json.dumps(
                {
                    "issues": [
                        {
                            "character_name": "Mara",
                            "classification": "possible",
                            "severity": "moderate",
                            "title": "Register shift",
                            "description": "The register changed.",
                            "submitted_excerpt": "No way, dude.",
                            "baseline_excerpt": baseline_excerpt,
                            "baseline_chapter_number": 1,
                            "confidence": 0.7,
                            "revision_direction": "Check the register.",
                            "intentionality_prompt": "Is this intentional?",
                        }
                    ],
                    "overall_verdict": "Possible shift.",
                }
            )

        result = await review_voice_sections(
            'Mara said, "No way, dude."',
            character_name="Mara",
            baseline_samples=baseline,
            submitted_samples=[{"excerpt": "No way, dude."}],
            model_call=model_call,
            source_chapter=2,
        )
        return result["issues"][0]["finding_key"]

    assert await review("I shall return before dawn.") != await review("I may return before dawn.")


@pytest.mark.asyncio
async def test_invalid_section_is_not_cached_as_empty_success():
    calls = 0

    async def model_call(_section):
        nonlocal calls
        calls += 1
        return "not json"

    with pytest.raises(VoiceReviewFormatError):
        await review_voice_sections(
            "Mara speaks.",
            character_name="Mara",
            baseline_samples=[],
            submitted_samples=[{"excerpt": "Mara speaks."}],
            model_call=model_call,
        )
    assert calls == 2


@pytest.mark.asyncio
async def test_unattributed_sections_do_not_invoke_model_or_claim_voice_review():
    calls = 0

    async def model_call(_section):
        nonlocal calls
        calls += 1
        return json.dumps({"issues": [], "overall_verdict": "No supported shift."})

    with pytest.raises(VoiceReviewFormatError, match="voice_review_no_attributable_sections"):
        await review_voice_sections(
            "Narration without attributed speech.",
            character_name="Mara",
            baseline_samples=[{"chapter_number": 1, "excerpt": "I shall return."}],
            submitted_samples=[],
            model_call=model_call,
        )
    assert calls == 0


@pytest.mark.asyncio
async def test_truncated_voice_model_output_retries_then_fails_without_coverage():
    calls = 0

    async def model_call(_section):
        nonlocal calls
        calls += 1
        raise LLMIncompleteResponseError("llm_response_incomplete")

    with pytest.raises(VoiceReviewFormatError, match="voice_review_incomplete_model_output"):
        await review_voice_sections(
            "Mara speaks.",
            character_name="Mara",
            baseline_samples=[],
            submitted_samples=[{"excerpt": "Mara speaks."}],
            model_call=model_call,
        )
    assert calls == 2


@pytest.mark.asyncio
async def test_transient_voice_capacity_failure_is_retried_once(monkeypatch):
    calls = 0

    async def no_delay(_seconds):
        return None

    async def model_call(_section):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary model timeout")
        return json.dumps({"issues": [], "overall_verdict": "No supported shift in this section."})

    monkeypatch.setattr("app.services.voice_consistency_review_service.asyncio.sleep", no_delay)
    result = await review_voice_sections(
        "Mara said hello.",
        character_name="Mara",
        baseline_samples=[],
        submitted_samples=[{"excerpt": "Mara said hello."}],
        model_call=model_call,
    )

    assert calls == 2
    assert result["coverage"]["processed_ranges"] == [{"start": 0, "end": 16}]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 503])
async def test_voice_coordination_retry_after_is_retried_once(monkeypatch, status_code):
    calls = 0
    delays = []

    async def no_delay(seconds):
        delays.append(seconds)

    async def model_call(_section):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(
                status_code,
                "LLM capacity is temporarily busy. Retry shortly.",
                headers={"Retry-After": "5"},
            )
        return json.dumps({"issues": [], "overall_verdict": "No supported shift."})

    monkeypatch.setattr("app.services.voice_consistency_review_service.asyncio.sleep", no_delay)
    result = await review_voice_sections(
        "Mara said hello.",
        character_name="Mara",
        baseline_samples=[],
        submitted_samples=[{"excerpt": "Mara said hello."}],
        model_call=model_call,
    )

    assert calls == 2
    assert delays == [5]
    assert result["coverage"]["processed_ranges"] == [{"start": 0, "end": 16}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (
            429,
            {"kind": "llm_budget", "message": "Monthly AI capacity has been reached."},
        ),
        (
            503,
            {
                "kind": "llm_configuration",
                "message": "AI configuration is unavailable.",
            },
        ),
    ],
)
async def test_voice_non_transient_control_error_does_not_retry(status_code, detail):
    calls = 0

    async def model_call(_section):
        nonlocal calls
        calls += 1
        raise HTTPException(status_code, detail)

    with pytest.raises(HTTPException) as raised:
        await review_voice_sections(
            "Mara said hello.",
            character_name="Mara",
            baseline_samples=[],
            submitted_samples=[{"excerpt": "Mara said hello."}],
            model_call=model_call,
        )

    assert raised.value.detail == detail
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 409, 503])
async def test_provider_status_error_retries_once_then_fails_without_successful_coverage(
    monkeypatch, status_code
):
    calls = 0

    async def no_delay(_seconds):
        return None

    async def model_call(_section):
        nonlocal calls
        calls += 1
        request = Request("POST", "https://api.openai.com/v1/chat/completions")
        raise APIStatusError(
            "provider busy", response=Response(status_code, request=request), body=None
        )

    monkeypatch.setattr("app.services.voice_consistency_review_service.asyncio.sleep", no_delay)
    with pytest.raises(APIStatusError):
        await review_voice_sections(
            "Mara said hello.",
            character_name="Mara",
            baseline_samples=[],
            submitted_samples=[{"excerpt": "Mara said hello."}],
            model_call=model_call,
        )
    assert calls == 2
