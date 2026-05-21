import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book
from app.models.character import Character, CharacterCandidate
from app.models.user import User
from app.utils.character_utils import (
    CHARACTER_CANDIDATE_PENDING,
    build_character_roster_snapshot,
    record_character_candidate,
    score_duplicate_characters,
)


def test_build_character_roster_snapshot_marks_manual_anchors():
    character = Character(
        id=None,
        book_id=None,
        name="Hitagi Senjogahara",
        aliases=["Hitagi", "Senjogahara"],
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=4,
        personality_tags=["sharp"],
        motivations=["protect Araragi"],
        arc_summary="Guarded but emotionally precise.",
        is_manual=True,
    )

    snapshot = build_character_roster_snapshot([character])

    assert snapshot[0]["name"] == "Hitagi Senjogahara"
    assert snapshot[0]["aliases"] == ["Hitagi", "Senjogahara"]
    assert snapshot[0]["is_manual"] is True


def test_score_duplicate_characters_returns_backend_review_signal():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Tsubasa Hanekawa",
        aliases=["Hanekawa"],
        role="sc",
        first_chapter=1,
        mention_count=5,
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Tsubasa",
        aliases=["Hanekawa", "Tsubasa Hanekawa"],
        role="sc",
        first_chapter=1,
        mention_count=2,
    )

    suggestion = score_duplicate_characters(primary, secondary)

    assert suggestion is not None
    assert suggestion["primary"].name == "Tsubasa Hanekawa"
    assert suggestion["secondary"].name == "Tsubasa"
    assert suggestion["confidence"] >= 34
    assert "Primary name appears in alias list" in suggestion["reasons"]


@pytest.mark.asyncio
async def test_record_character_candidate_upserts_by_source_key(db):
    user = User(email="candidate-review@lorevia.app", username="candidate-review", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Candidate Review",
        format="pdf",
        s3_key="books/candidate-review.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=3,
        raw_name="Hitagi",
        proposed_name="Hitagi",
        aliases=["Senjogahara"],
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=0.62,
        reason_codes=["ambiguous_roster_match"],
        evidence={"mention_count": 1},
        source_batch_key="book:3:1",
    )
    await record_character_candidate(
        db,
        book_id=book.id,
        chapter_number=3,
        raw_name="Hitagi",
        proposed_name="Hitagi",
        aliases=["Senjogahara"],
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=0.68,
        reason_codes=["ambiguous_roster_match", "single_token_needs_stronger_support"],
        evidence={"strong_mention_count": 1},
        source_batch_key="book:3:1",
    )
    await db.commit()

    rows = (
        await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id))
    ).scalars().all()

    assert len(rows) == 1
    assert rows[0].confidence == 68
    assert rows[0].reason_codes == ["ambiguous_roster_match", "single_token_needs_stronger_support"]
    assert rows[0].evidence["mention_count"] == 1
    assert rows[0].evidence["strong_mention_count"] == 1
