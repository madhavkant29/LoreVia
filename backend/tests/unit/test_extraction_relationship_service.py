import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.engine.character.deduplicator import character_name_keys
from app.models.book import Book
from app.models.character import Character, CharacterRelationshipCandidate
from app.models.intelligence import CharacterRelationship
from app.models.user import User
from app.services.extraction_relationship_service import (
    _persist_relationship_records,
    _relationship_signature,
    load_persisted_relationship_signatures,
)


@pytest.mark.asyncio
async def test_unverified_relationship_quote_creates_review_candidate_not_canon(db):
    user = User(email="relationship-proof@lorevia.app", username="relproof", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(user_id=user.id, title="Source proof", format="manual", s3_key="books/proof.txt")
    db.add(book)
    await db.flush()
    mara = Character(book_id=book.id, name="Mara Vale", first_chapter=1)
    ilya = Character(book_id=book.id, name="Ilya Ren", first_chapter=1)
    db.add_all([mara, ilya])
    await db.flush()

    persisted, unresolved, review_count = await _persist_relationship_records(
        db,
        book_id=book.id,
        chapter_number=1,
        existing_characters=[mara, ilya],
        relationships=[
            {
                "character_a": "Mara Vale",
                "character_b": "Ilya Ren",
                "type": "sibling",
                "description": "They are siblings.",
                "label_evidence": {},
                "source_quote_verified": False,
                "source_batch_key": "book:1:1",
            },
            {
                "character_a": "Mara Vale",
                "character_b": "Ilya Ren",
                "type": "friend",
                "description": "They are friends.",
                "label_evidence": {"quote": "They are friends."},
                "source_quote_verified": True,
                "source_batch_key": "book:1:2",
            },
        ],
        key_cache={
            mara.id: character_name_keys(mara.name, []),
            ilya.id: character_name_keys(ilya.name, []),
        },
        persisted_signatures=set(),
    )
    await db.flush()

    assert persisted == 0
    assert review_count == 2
    assert unresolved[0]["source_quote_verified"] is False
    assert unresolved[1]["relationship_participants_anchored"] is False
    relationship_rows = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert relationship_rows == []
    assert len(candidates) == 2
    assert all(candidate.status == "pending" for candidate in candidates)
    assert any(
        "relationship_source_quote_unverified" in candidate.reason_codes for candidate in candidates
    )
    assert any(
        "relationship_participants_unanchored" in candidate.reason_codes for candidate in candidates
    )


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _FakeResult(self.rows)


def test_relationship_signature_canonicalizes_pair_and_state():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()

    first = _relationship_signature(
        left_id,
        right_id,
        "Ally",
        0.8,
        4,
        "  Trusts her. ",
        ["friend", "ally"],
        [],
        [],
    )
    reversed_pair = _relationship_signature(
        right_id,
        left_id,
        "Ally",
        0.8,
        4,
        "Trusts her.",
        ["friend", "ally"],
        [],
        [],
    )

    assert first == reversed_pair
    assert first[-1] == 4


@pytest.mark.asyncio
async def test_load_persisted_relationship_signatures_returns_signature_set():
    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    rows = [
        SimpleNamespace(
            character_a_id=left_id,
            character_b_id=right_id,
            rel_type="mentor",
            sentiment=0.7,
            from_chapter=3,
            description="Trains him",
            shared_labels=["teacher"],
            character_a_to_b_labels=["guide"],
            character_b_to_a_labels=["student"],
        )
    ]
    db = _FakeDb(rows)

    signatures = await load_persisted_relationship_signatures(
        db,
        book_id=uuid.uuid4(),
        chapter_number=3,
    )

    assert db.statements
    assert signatures == {
        _relationship_signature(
            left_id,
            right_id,
            "mentor",
            0.7,
            3,
            "Trains him",
            ["teacher"],
            ["guide"],
            ["student"],
        )
    }
