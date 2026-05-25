import uuid
from typing import cast

import numpy as np
import pytest
from sqlalchemy import select

from app.models.book import Book
from app.models.character import Character, CharacterCandidate, CharacterDuplicateSuggestion, CharacterMention, CharacterRelationshipCandidate
from app.models.user import User
from app.utils.character_utils import (
    CHARACTER_CANDIDATE_PENDING,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    build_character_roster_snapshot,
    build_character_review_payload,
    record_character_candidate,
    record_character_mention,
    record_relationship_candidate,
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


def test_score_duplicate_characters_boosts_shared_grounded_cluster_evidence():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Grete",
        aliases=[],
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=5,
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
        book_id=primary.book_id,
        name="Gregor's sister",
        aliases=[],
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=2,
    )

    suggestion = score_duplicate_characters(
        primary,
        secondary,
        left_evidence={"cluster_keys": {"grete"}, "chapter_numbers": {1, 2}},
        right_evidence={"cluster_keys": {"grete"}, "chapter_numbers": {1, 2}},
    )

    assert suggestion is not None
    assert "Shared mention clusters" in suggestion["reasons"]
    assert suggestion["shared_evidence"]["shared_cluster_keys"] == ["grete"]


def test_score_duplicate_characters_uses_embedding_similarity_signal():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000021"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Anna Sergeyevna",
        aliases=["Anna"],
        role="sc",
        first_chapter=2,
        mention_count=4,
        embedding=[0.8, 0.1, 0.2],
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000022"),
        book_id=primary.book_id,
        name="Anna",
        aliases=["Anna Sergeyevna"],
        role="sc",
        first_chapter=2,
        mention_count=2,
        embedding=[0.79, 0.11, 0.19],
    )

    suggestion = score_duplicate_characters(primary, secondary)

    assert suggestion is not None
    assert any(reason in suggestion["reasons"] for reason in ["High embedding similarity", "Related embedding similarity"])
    assert suggestion["shared_evidence"]["embedding_similarity"] is not None


def test_score_duplicate_characters_accepts_numpy_embeddings():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000031"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Anna Sergeyevna",
        aliases=["Anna"],
        role="sc",
        first_chapter=2,
        mention_count=4,
        embedding=np.array([0.8, 0.1, 0.2]),
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000032"),
        book_id=primary.book_id,
        name="Anna",
        aliases=["Anna Sergeyevna"],
        role="sc",
        first_chapter=2,
        mention_count=2,
        embedding=np.array([0.79, 0.11, 0.19]),
    )

    suggestion = score_duplicate_characters(primary, secondary)

    assert suggestion is not None
    assert suggestion["shared_evidence"]["embedding_similarity"] is not None


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


@pytest.mark.asyncio
async def test_record_character_mention_keeps_distinct_passages_in_same_cluster(db):
    user = User(email="mention-review@lorevia.app", username="mention-review", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Mention Review",
        format="pdf",
        s3_key="books/mention-review.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    await record_character_mention(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Grete",
        normalized_name="grete",
        source_batch_key="book:2:1",
        cluster_key="grete",
        mention_text="Grete opened the door.",
        resolver_status="matched_existing",
        resolver_reasons=["matched_existing_character"],
        evidence={"mention_count": 1},
    )
    await record_character_mention(
        db,
        book_id=book.id,
        chapter_number=2,
        raw_name="Grete",
        normalized_name="grete",
        source_batch_key="book:2:1",
        cluster_key="grete",
        mention_text="Grete carried food into the room.",
        resolver_status="matched_existing",
        resolver_reasons=["matched_existing_character"],
        evidence={"mention_count": 1},
    )
    await db.commit()

    rows = (
        await db.execute(select(CharacterMention).where(CharacterMention.book_id == book.id))
    ).scalars().all()

    assert len(rows) == 2
    assert {row.mention_text for row in rows} == {
        "Grete opened the door.",
        "Grete carried food into the room.",
    }


@pytest.mark.asyncio
async def test_record_relationship_candidate_upserts_by_source_key(db):
    user = User(email="relationship-review@lorevia.app", username="relationship-review", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Relationship Review",
        format="pdf",
        s3_key="books/relationship-review.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    await record_relationship_candidate(
        db,
        book_id=book.id,
        chapter_number=4,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        rel_type="family",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
        reason_codes=["relationship_unresolved"],
        evidence={"marker": "first"},
        source_batch_key="book:4:relationship",
    )
    await record_relationship_candidate(
        db,
        book_id=book.id,
        chapter_number=4,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        rel_type="family",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
        reason_codes=["relationship_unresolved", "character_b_missing"],
        evidence={"marker": "second"},
        source_batch_key="book:4:relationship",
    )
    await db.commit()

    rows = (
        await db.execute(
            select(CharacterRelationshipCandidate).where(CharacterRelationshipCandidate.book_id == book.id)
        )
    ).scalars().all()

    assert len(rows) == 1
    assert rows[0].reason_codes == ["relationship_unresolved", "character_b_missing"]
    assert rows[0].evidence["marker"] == "second"


def test_build_character_review_payload_includes_relationship_candidates():
    relationship_candidate = CharacterRelationshipCandidate(
        id=uuid.UUID("00000000-0000-0000-0000-000000000111"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        chapter_number=3,
        raw_character_a="Grete",
        raw_character_b="Gregor's father",
        rel_type="family",
        status=CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
        reason_codes=["relationship_unresolved"],
        evidence={"sample": True},
    )

    payload = build_character_review_payload([], [], [relationship_candidate])

    assert payload["counts"]["pending_relationship_candidates"] == 1
    assert payload["relationship_candidates"][0]["raw_character_a"] == "Grete"


def test_build_character_review_payload_surfaces_structured_candidate_and_duplicate_evidence():
    primary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000201"),
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
        name="Grete",
        aliases=["Gregor's sister"],
        role="sc",
        first_chapter=1,
        analysis_metadata={"protected_from_repair": True},
    )
    secondary = Character(
        id=uuid.UUID("00000000-0000-0000-0000-000000000202"),
        book_id=primary.book_id,
        name="Gregor's sister",
        aliases=[],
        role="sc",
        first_chapter=1,
    )
    candidate = CharacterCandidate(
        id=uuid.UUID("00000000-0000-0000-0000-000000000203"),
        book_id=primary.book_id,
        chapter_number=1,
        raw_name="Gregor's sister",
        proposed_name="Gregor's sister",
        normalized_name="gregor sister",
        aliases=["Grete"],
        status=CHARACTER_CANDIDATE_PENDING,
        confidence=58,
        reason_codes=["role_only_reference"],
        evidence={
            "cluster_names": ["Grete", "Gregor's sister"],
            "cluster_size": 2,
            "cluster_mention_count": 3,
            "resolver_status": "held_for_review",
            "resolver_reasons": ["role_only_reference", "competing_proper_name"],
            "canonical_confidence": 0.58,
            "grounding_coverage": 0.75,
            "snippets": ["Grete brings food to Gregor."],
        },
    )
    suggestion = score_duplicate_characters(primary, secondary)
    duplicate = CharacterDuplicateSuggestion(
        id=uuid.UUID("00000000-0000-0000-0000-000000000204"),
        book_id=primary.book_id,
        primary_character_id=primary.id,
        secondary_character_id=secondary.id,
        confidence=cast(dict, suggestion)["confidence"],
        reasons=cast(dict, suggestion)["reasons"],
        shared_evidence=cast(dict, suggestion)["shared_evidence"],
        status="pending",
    )

    payload = build_character_review_payload(
        [candidate],
        [duplicate],
        [],
        character_map={primary.id: primary, secondary.id: secondary},
    )

    assert payload["candidates"][0]["cluster_names"] == ["Grete", "Gregor's sister"]
    assert payload["candidates"][0]["resolver_status"] == "held_for_review"
    assert payload["candidates"][0]["snippets"] == ["Grete brings food to Gregor."]
    assert payload["duplicate_suggestions"][0]["primary_is_protected"] is True
    assert isinstance(payload["duplicate_suggestions"][0]["shared_chapters"], list)
