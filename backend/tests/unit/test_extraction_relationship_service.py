import uuid
from types import SimpleNamespace

import pytest

from app.services.extraction_relationship_service import (
    _relationship_signature,
    load_persisted_relationship_signatures,
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
