from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.models.intelligence import CharacterRelationship
from app.utils.relationship_utils import (
    canonical_relationship_pair_ids,
    canonicalize_relationship_book_rows,
    canonicalize_relationship_rows,
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
    )


def test_canonical_relationship_pair_ids_treats_reversed_pairs_as_identical():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()

    assert canonical_relationship_pair_ids(left_id, right_id) == canonical_relationship_pair_ids(right_id, left_id)


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
    assert (first.character_a_id, first.character_b_id) == canonical_relationship_pair_ids(left_id, right_id)


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

    kept, removed = canonicalize_relationship_rows([original, inserted], preferred_relationship_id=inserted.id)

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

    kept, removed = canonicalize_relationship_rows([original, inserted], preferred_relationship_id=inserted.id)

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

    kept, removed = canonicalize_relationship_rows([original, inserted], preferred_relationship_id=inserted.id)

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
    assert (rel.character_a_id, rel.character_b_id) == canonical_relationship_pair_ids(left_id, right_id)
    assert rel.to_chapter is None
    assert rel.description == "Bonds"
