from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.book import Book
from app.models.character import Character, CharacterRelationshipCandidate
from app.models.intelligence import CharacterRelationship
from app.models.user import User
from app.utils.relationship_utils import (
    canonical_relationship_pair_ids,
    canonicalize_relationship_book_rows,
    canonicalize_relationship_rows,
    normalize_relationship_labels,
    reconcile_extracted_relationships,
    relationship_label_display,
    upsert_relationship_timeline_state,
)


def _relationship(
    *,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    rel_type: str,
    from_chapter: int,
    book_id: uuid.UUID | None = None,
    to_chapter: int | None = None,
    description: str | None = None,
    sentiment: float | None = None,
    shared_labels: list[str] | None = None,
    character_a_to_b_labels: list[str] | None = None,
    character_b_to_a_labels: list[str] | None = None,
) -> CharacterRelationship:
    return CharacterRelationship(
        book_id=book_id or uuid.uuid4(),
        character_a_id=character_a_id,
        character_b_id=character_b_id,
        rel_type=rel_type,
        sentiment=sentiment,
        description=description,
        from_chapter=from_chapter,
        to_chapter=to_chapter,
        shared_labels=shared_labels or [],
        character_a_to_b_labels=character_a_to_b_labels or [],
        character_b_to_a_labels=character_b_to_a_labels or [],
    )


def test_canonical_relationship_pair_ids_treats_reversed_pairs_as_identical():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()

    assert canonical_relationship_pair_ids(left_id, right_id) == canonical_relationship_pair_ids(
        right_id, left_id
    )


def test_normalize_relationship_labels_handles_aliases_and_supersession():
    labels = normalize_relationship_labels(["freind", "friend(toxic)", "sister", "half-sister"])

    assert labels == ["friend_toxic", "half_sister"]
    assert relationship_label_display("pawn") == "pawn (tool)"
    assert relationship_label_display("grandmother maternal") == "grandmother (maternal)"


def test_canonicalize_relationship_rows_merges_same_state_later_batch():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    first = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="ally",
        sentiment=0.7,
        description="Trust each other",
        from_chapter=2,
    )
    duplicate = _relationship(
        character_a_id=right_id,
        character_b_id=left_id,
        rel_type="ally",
        sentiment=0.7,
        description="Trust each other",
        from_chapter=5,
    )

    kept, removed = canonicalize_relationship_rows([first, duplicate])

    assert kept == [first]
    assert removed == [duplicate]
    assert first.to_chapter is None
    assert (first.character_a_id, first.character_b_id) == canonical_relationship_pair_ids(
        left_id, right_id
    )


def test_canonicalize_relationship_rows_closes_previous_state_on_transition():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    hostile = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="enemy",
        sentiment=-0.8,
        description="Openly hostile",
        from_chapter=4,
    )
    ally = _relationship(
        character_a_id=right_id,
        character_b_id=left_id,
        rel_type="ally",
        sentiment=0.8,
        description="Learn to trust each other",
        from_chapter=5,
    )

    kept, removed = canonicalize_relationship_rows([hostile, ally])

    assert removed == []
    assert kept == [hostile, ally]
    assert hostile.to_chapter == 4
    assert ally.to_chapter is None


def test_canonicalize_relationship_rows_tracks_label_revelation_as_transition():
    left_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    right_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    sister = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="family",
        from_chapter=1,
        character_a_to_b_labels=["sister"],
        character_b_to_a_labels=["brother"],
    )
    half_sister = _relationship(
        character_a_id=right_id,
        character_b_id=left_id,
        rel_type="family",
        from_chapter=7,
        character_a_to_b_labels=["half_brother"],
        character_b_to_a_labels=["half_sister"],
    )

    kept, removed = canonicalize_relationship_rows([sister, half_sister])

    assert removed == []
    assert [(row.rel_type, row.from_chapter, row.to_chapter) for row in kept] == [
        ("sister", 1, 6),
        ("half_sister", 7, None),
    ]
    assert kept[1].character_a_to_b_labels == ["half_sister"]
    assert kept[1].character_b_to_a_labels == ["half_brother"]


def test_canonicalize_relationship_rows_splits_overlapping_manual_window():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    original = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="ally",
        sentiment=0.6,
        description="Steady allies",
        from_chapter=1,
        to_chapter=10,
    )
    inserted = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="rival",
        sentiment=-0.3,
        description="Fall into conflict",
        from_chapter=5,
        to_chapter=8,
    )

    kept, removed = canonicalize_relationship_rows(
        [original, inserted], preferred_relationship_id=inserted.id
    )

    assert removed == []
    assert len(kept) == 3
    assert [(row.rel_type, row.from_chapter, row.to_chapter) for row in kept] == [
        ("ally", 1, 4),
        ("rival", 5, 8),
        ("ally", 9, 10),
    ]


def test_canonicalize_relationship_rows_preserves_tail_when_replacing_same_start_window():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    original = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="ally",
        sentiment=0.6,
        description="Steady allies",
        from_chapter=5,
        to_chapter=10,
    )
    inserted = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="rival",
        sentiment=-0.3,
        description="Fall into conflict",
        from_chapter=5,
        to_chapter=7,
    )

    kept, removed = canonicalize_relationship_rows(
        [original, inserted], preferred_relationship_id=inserted.id
    )

    assert removed == [original]
    assert len(kept) == 2
    assert [(row.rel_type, row.from_chapter, row.to_chapter) for row in kept] == [
        ("rival", 5, 7),
        ("ally", 8, 10),
    ]


def test_canonicalize_relationship_rows_processes_preferred_same_start_row_after_original():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    original = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="ally",
        sentiment=0.6,
        description="Steady allies",
        from_chapter=5,
        to_chapter=10,
    )
    inserted = _relationship(
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="rival",
        sentiment=-0.3,
        description="Fall into conflict",
        from_chapter=5,
        to_chapter=7,
    )
    original.id = uuid.uuid4()
    inserted.id = uuid.uuid4()

    kept, removed = canonicalize_relationship_rows(
        [original, inserted], preferred_relationship_id=inserted.id
    )

    assert removed == [original]
    assert [(row.rel_type, row.from_chapter, row.to_chapter) for row in kept] == [
        ("rival", 5, 7),
        ("ally", 8, 10),
    ]


def test_canonicalize_relationship_book_rows_collapses_reversed_legacy_duplicates():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    book_id = uuid.uuid4()
    primary = _relationship(
        book_id=book_id,
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="mentor",
        from_chapter=2,
        description="Guides them",
    )
    duplicate = _relationship(
        book_id=book_id,
        character_a_id=right_id,
        character_b_id=left_id,
        rel_type="mentor",
        from_chapter=2,
        description="Guides them",
    )

    kept, removed = canonicalize_relationship_book_rows([primary, duplicate])

    assert kept == [primary]
    assert removed == [duplicate]


def test_canonicalize_relationship_book_rows_accepts_sparse_row_objects():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    rel = SimpleNamespace(
        character_a_id=right_id,
        character_b_id=left_id,
        from_chapter=2,
        rel_type="ally",
        description=" Bonds ",
        sentiment=0.4,
    )

    kept, removed = canonicalize_relationship_book_rows([rel])

    assert removed == []
    assert kept == [rel]
    assert (rel.character_a_id, rel.character_b_id) == canonical_relationship_pair_ids(
        left_id, right_id
    )
    assert rel.to_chapter is None
    assert rel.description == "Bonds"


@pytest.mark.asyncio
async def test_upsert_relationship_timeline_state_preserves_omitted_label_facets(db):
    user = User(
        email="relationship-label-preserve@example.com",
        username="relationship-label-preserve",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Relationship Label Preserve",
        format="pdf",
        s3_key="books/relationship-label-preserve.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    left = Character(
        book_id=book.id,
        name="Grete",
        aliases=[],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )
    right = Character(
        book_id=book.id,
        name="Gregor",
        aliases=[],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )
    db.add_all([left, right])
    await db.flush()
    left_id, right_id = canonical_relationship_pair_ids(left.id, right.id)
    relationship = CharacterRelationship(
        book_id=book.id,
        character_a_id=left_id,
        character_b_id=right_id,
        rel_type="family",
        sentiment=0.2,
        description="Known siblings",
        from_chapter=1,
        shared_labels=["forbidden_romance"],
        character_a_to_b_labels=["sister"],
        character_b_to_a_labels=["brother"],
        label_evidence={"quote": "They were raised as siblings."},
    )
    db.add(relationship)
    await db.flush()

    updated, created = await upsert_relationship_timeline_state(
        db,
        book_id=book.id,
        character_a_id=right_id,
        character_b_id=left_id,
        rel_type="family",
        sentiment=0.2,
        description="Known siblings, with a later paternal reveal",
        from_chapter=1,
        relationship_id=relationship.id,
        character_a_to_b_labels=["half_brother"],
    )

    assert created is True
    assert updated.shared_labels == ["forbidden_romance"]
    assert updated.character_a_to_b_labels == ["sister"]
    assert updated.character_b_to_a_labels == ["half_brother"]
    assert updated.label_evidence == {"quote": "They were raised as siblings."}


@pytest.mark.asyncio
async def test_reconcile_extracted_relationships_repairs_generated_rows_and_preserves_manual_rows(
    db,
):
    user = User(
        email="relationship-reconcile@example.com",
        username="relationship-reconcile",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Relationship Reconcile",
        format="pdf",
        s3_key="books/relationship-reconcile.pdf",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    gregor = Character(
        book_id=book.id,
        name="Gregor Samsa",
        aliases=["Gregor", "Grete"],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )
    grete = Character(
        book_id=book.id,
        name="Grete",
        aliases=[],
        first_chapter=1,
        visibility_state="visible",
        approval_state="approved",
    )
    hidden = Character(
        book_id=book.id,
        name="Mr. Samsa",
        aliases=[],
        first_chapter=1,
        visibility_state="noise",
        approval_state="rejected",
    )
    db.add_all([gregor, grete, hidden])
    await db.flush()
    generated_hidden = _relationship(
        book_id=book.id,
        character_a_id=gregor.id,
        character_b_id=hidden.id,
        rel_type="family",
        from_chapter=1,
        description="Incorrect generated endpoint",
    )
    curated_hidden = _relationship(
        book_id=book.id,
        character_a_id=gregor.id,
        character_b_id=hidden.id,
        rel_type="family",
        from_chapter=2,
        description="Author-preserved endpoint",
    )
    curated_hidden.edited_by_author = True
    curated_visible = _relationship(
        book_id=book.id,
        character_a_id=gregor.id,
        character_b_id=grete.id,
        rel_type="family",
        from_chapter=1,
        description="Author-preserved visible endpoint",
    )
    curated_visible.edited_by_author = True
    candidate = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Gregor",
        raw_character_b="Grete",
        rel_type="family",
        sentiment=0.4,
        description="Gregor cares for his sister.",
        status="suppressed",
        reason_codes=["character_b_missing"],
        evidence={
            "source_quote_verified": True,
            "relationship": {"label_evidence": {"quote": "Gregor helped Grete escape."}},
        },
    )
    unverified_candidate = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Gregor",
        raw_character_b="Grete",
        rel_type="rival",
        status="suppressed",
        reason_codes=["relationship_source_quote_unverified"],
        evidence={"source_quote_verified": False, "relationship": {"label_evidence": {}}},
    )
    invalid_auto_candidate = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Gregor's mother",
        raw_character_b="Grete",
        matched_character_a_id=gregor.id,
        matched_character_b_id=grete.id,
        rel_type="family",
        sentiment=-0.3,
        description="Gregor's mother cares for him but struggles with the changes in their relationship.",
        status="accepted",
        reason_codes=["relationship_auto_reconciled"],
        evidence={"relationship_auto_reconciled": True},
    )
    db.add_all(
        [
            generated_hidden,
            curated_hidden,
            curated_visible,
            candidate,
            unverified_candidate,
            invalid_auto_candidate,
        ]
    )
    await db.flush()

    result = await reconcile_extracted_relationships(db, book_id=book.id)
    await db.flush()

    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    relationship_ids = {relationship.id for relationship in relationships}
    visible_pair = canonical_relationship_pair_ids(gregor.id, grete.id)

    assert result["aliases_sanitized"] == 1
    assert result["hidden_relationships_removed"] == 1
    assert result["relationship_candidates_reconciled"] == 1
    assert result["relationship_candidates_demoted"] == 1
    assert gregor.aliases == ["Gregor"]
    assert generated_hidden.id not in relationship_ids
    assert curated_hidden.id in relationship_ids
    assert curated_visible.id in relationship_ids
    assert any(
        (relationship.character_a_id, relationship.character_b_id) == visible_pair
        for relationship in relationships
    )
    assert candidate.status == "accepted"
    assert (candidate.matched_character_a_id, candidate.matched_character_b_id) == visible_pair
    assert candidate.reason_codes == ["relationship_auto_reconciled"]
    assert unverified_candidate.status == "suppressed"
    assert not any(relationship.rel_type == "rival" for relationship in relationships)
    assert invalid_auto_candidate.status == "pending"
    assert invalid_auto_candidate.reason_codes == ["relationship_source_quote_unverified"]
