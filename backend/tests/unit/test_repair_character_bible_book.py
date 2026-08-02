import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.book import Book
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
)
from app.models.user import User
from scripts import backfill_character_bible_noise, repair_character_bible_book


def _character(**overrides):
    payload = {
        "id": uuid.uuid4(),
        "name": "Aikawa",
        "aliases": [],
        "trait_state": {},
        "analysis_metadata": {},
        "is_manual": False,
        "mention_count": 1,
        "states": [],
        "voice_profile": None,
        "role": None,
        "personality_tags": [],
        "motivations": [],
        "fears": [],
        "archetype": None,
        "arc_summary": None,
        "goal": None,
        "lie_they_believe": None,
        "backstory_wound": None,
        "arc_type": None,
        "relationships_as_a": [],
        "relationships_as_b": [],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_is_protected_character_marks_manual_characters_as_untouchable():
    character = _character(is_manual=True)

    assert repair_character_bible_book._is_protected_character(character) is True


def test_is_protected_character_marks_manual_description_edits_as_untouchable():
    character = _character(
        trait_state={
            "manual_description": {
                "value": "User wrote a custom profile here.",
                "confidence": 1.0,
                "type": "abstract",
            }
        }
    )

    assert repair_character_bible_book._is_protected_character(character) is True


def test_auto_mergeable_skips_pairs_that_touch_protected_characters():
    suggestion = SimpleNamespace(
        status="pending",
        confidence=96,
        reasons=["Exact name match"],
    )
    primary = _character(is_manual=True)
    secondary = _character()

    assert (
        repair_character_bible_book._auto_mergeable(
            suggestion, primary=primary, secondary=secondary
        )
        is False
    )


def test_auto_mergeable_keeps_unprotected_high_confidence_duplicates():
    suggestion = SimpleNamespace(
        status="pending",
        confidence=96,
        reasons=["Exact name match"],
    )
    primary = _character(name="Aikawa", mention_count=1)
    secondary = _character(name="Aikawa", mention_count=1)

    assert (
        repair_character_bible_book._auto_mergeable(
            suggestion, primary=primary, secondary=secondary
        )
        is True
    )


def test_is_protected_character_respects_curated_metadata_flags():
    character = _character(analysis_metadata={"user_curated": True})

    assert repair_character_bible_book._is_protected_character(character) is True


def test_parse_args_keeps_dry_run_default(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["repair_character_bible_book.py", "--book-id", "00000000-0000-0000-0000-000000000001"],
    )

    args = repair_character_bible_book._parse_args()

    assert args.apply is False
    assert args.allow_merge_safe_pairs is False
    assert args.allow_demote_obvious_noise is False


@pytest.mark.asyncio
async def test_repair_session_reuses_injected_db():
    db = object()

    async with repair_character_bible_book._repair_session(db) as session:
        assert session is db


@pytest.mark.asyncio
async def test_apply_repair_plan_demotes_characters_rejected_by_repair_verifier(db, monkeypatch):
    user = User(
        email="repair-verifier@lorevia.app", username="repair-verifier", password_hash="hash"
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Repair Verifier",
        format="pdf",
        s3_key="books/repair-verifier.pdf",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    character = Character(
        book_id=book.id,
        name="Help",
        aliases=[],
        first_chapter=1,
        last_seen_chapter=1,
        mention_count=1,
    )
    db.add(character)
    await db.flush()

    mention = CharacterMention(
        book_id=book.id,
        chapter_number=1,
        raw_name="Help",
        normalized_name="help",
        mention_text="Help, he shouted toward the pier.",
        matched_character_id=character.id,
        resolver_status="promoted",
    )
    db.add(mention)
    await db.commit()

    async def _fake_verify(*_args, **_kwargs):
        return {
            "local": {"confidence_band": "reject", "reasons": ["interjection_like_usage"]},
            "llm": {
                "used": False,
                "is_person_like": None,
                "confidence": None,
                "canonical_name": None,
                "reason": None,
            },
            "final": {
                "confidence_band": "reject",
                "is_person_like": False,
                "reasons": ["interjection_like_usage"],
            },
        }

    monkeypatch.setattr(
        repair_character_bible_book, "verify_character_candidate_personhood", _fake_verify
    )
    monkeypatch.setattr(
        repair_character_bible_book,
        "_is_obvious_noise_character",
        lambda *_args, **_kwargs: (False, []),
    )

    result = await repair_character_bible_book.apply_repair_plan(
        book.id,
        allow_merge_safe_pairs=False,
        allow_demote_obvious_noise=True,
        db=db,
    )

    persisted_character = await db.get(Character, character.id)
    candidate_rows = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )

    assert persisted_character is not None
    assert persisted_character.visibility_state == "noise"
    assert persisted_character.approval_state == "rejected"
    assert result["demoted_character_ids"] == [str(character.id)]
    assert result["character_labels"][str(character.id)] == "Help"
    assert len(candidate_rows) == 1
    assert candidate_rows[0].matched_character_id == character.id
    assert candidate_rows[0].status == "suppressed"
    assert candidate_rows[0].reason_codes[0] == "repair_demoted_noise"
    assert candidate_rows[0].evidence["verifier"]["final"]["confidence_band"] == "reject"


@pytest.mark.asyncio
async def test_apply_repair_plan_suppresses_pending_candidate_noise(db, monkeypatch):
    user = User(
        email="repair-candidates@lorevia.app", username="repair-candidates", password_hash="hash"
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Repair Candidates",
        format="pdf",
        s3_key="books/repair-candidates.pdf",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    character_candidate = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Texte",
        proposed_name="Texte",
        normalized_name="texte",
        status="pending",
        confidence=0,
        reason_codes=["mention_verifier_review"],
        evidence={
            "verifier": {
                "final": {
                    "confidence_band": "review",
                    "reasons": ["sentence_start_capitalization_only"],
                }
            }
        },
    )
    relationship_candidate = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Gregor",
        raw_character_b="Texte",
        status="pending",
        reason_codes=["relationship_unresolved", "character_b_missing"],
        evidence={},
    )
    db.add_all([character_candidate, relationship_candidate])
    await db.commit()

    async def _empty_chapter_rows(*_args, **_kwargs):
        return []

    monkeypatch.setattr(repair_character_bible_book, "_load_chapter_rows", _empty_chapter_rows)

    result = await repair_character_bible_book.apply_repair_plan(
        book.id,
        allow_merge_safe_pairs=False,
        allow_demote_obvious_noise=True,
        db=db,
    )

    await db.refresh(character_candidate)
    await db.refresh(relationship_candidate)

    assert character_candidate.status == "suppressed"
    assert relationship_candidate.status == "suppressed"
    assert result["pending_character_candidates_suppressed"] == 1
    assert result["pending_relationship_candidates_suppressed"] == 1


def test_backfill_marks_book_state_with_version_and_summary():
    book = SimpleNamespace(writer_workspace={})

    backfill_character_bible_noise._mark_backfill_state(
        book,
        status="applied",
        payload={"demoted_character_ids": ["a"]},
    )

    state = book.writer_workspace["character_noise_backfill"]
    assert state["version"] == backfill_character_bible_noise.BACKFILL_VERSION
    assert state["status"] == "applied"
    assert state["summary"] == {"demoted_character_ids": ["a"]}


@pytest.mark.asyncio
async def test_backfill_targets_books_with_only_pending_candidate_noise(db, monkeypatch):
    user = User(
        email="candidate-only-backfill@lorevia.app",
        username="candidate-only-backfill",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Candidate Only Backfill",
        format="pdf",
        s3_key="books/candidate-only-backfill.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    db.add(
        CharacterCandidate(
            book_id=book.id,
            chapter_number=1,
            raw_name="Chapitre",
            proposed_name="Chapitre",
            normalized_name="chapitre",
            status="pending",
            confidence=0,
        )
    )
    await db.commit()

    session_factory = async_sessionmaker(db.bind, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(backfill_character_bible_noise, "AsyncSessionLocal", session_factory)

    targets = await backfill_character_bible_noise._iter_target_books(
        book_id=book.id, limit=0, force=True
    )

    assert [item.id for item in targets] == [book.id]
