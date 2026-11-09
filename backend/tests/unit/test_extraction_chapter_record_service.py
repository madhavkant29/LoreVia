import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
)
from app.models.intelligence import CharacterRelationship
from app.models.user import User
from app.services import extraction_chapter_record_service
from app.services.extraction_chapter_record_service import (
    replace_chapter_extraction_records,
    stage_chapter_for_extraction,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeDb:
    def __init__(self, chapter):
        self.chapter = chapter
        self.execute_calls = 0
        self.flush_calls = 0
        self.added = []

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _ScalarResult(self.chapter)
        return _ScalarResult(None)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_calls += 1


@pytest.mark.asyncio
async def test_stage_chapter_for_extraction_updates_existing_chapter_without_purging_generated_rows(
    monkeypatch,
):
    synced = []

    async def fake_sync_chapter_media(db, book, chapter, ch_data):
        synced.append((db, book, chapter, ch_data))

    monkeypatch.setattr(
        extraction_chapter_record_service,
        "_sync_chapter_media",
        fake_sync_chapter_media,
    )

    book = SimpleNamespace(id=uuid.uuid4())
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=book.id,
        number=3,
        s3_key="chapter-key",
        title="Old",
        description="Old description",
        chapter_kind="chapter",
        processed=True,
        word_count=1,
        content_version=1,
        analysis_state={"status": "done"},
    )
    db = _FakeDb(chapter)

    result = await stage_chapter_for_extraction(
        db,
        book,
        {
            "number": 3,
            "title": "New",
            "description": "New description",
            "chapter_kind": "prologue",
            "content_version": 2,
            "text": "One two [[IMAGE:map]]",
            "images": [{"marker": "[[IMAGE:map]]"}],
        },
        3,
    )

    assert result is chapter
    assert chapter.title == "New"
    assert chapter.description == "New description"
    assert chapter.chapter_kind == "prologue"
    assert chapter.processed is False
    assert chapter.word_count == 2
    assert chapter.content_version == 2
    assert chapter.analysis_state["status"] == "pending"
    assert chapter.analysis_state["source_integrity"]["media_marker_count"] == 1
    assert chapter.analysis_state["source_integrity"]["stored_media_count"] == 1
    assert db.flush_calls == 2
    assert db.execute_calls == 1
    assert synced and synced[0][2] is chapter


@pytest.mark.asyncio
async def test_replace_chapter_extraction_records_preserves_curated_rows(db):
    user = User(email="chapter-replace@example.com", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Safe replacement",
        format="pdf",
        s3_key="books/safe-replacement.pdf",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=2,
        title="Two",
        s3_key="chapters/safe-replacement/2.txt",
    )
    left = Character(book_id=book.id, name="Mara", first_chapter=1, mention_count=2)
    right = Character(book_id=book.id, name="Sol", first_chapter=1, mention_count=2)
    db.add_all([chapter, left, right])
    await db.flush()
    db.add_all(
        [
            CharacterMention(
                book_id=book.id,
                chapter_number=2,
                raw_name="Mara",
                normalized_name="mara",
            ),
            CharacterCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_name="Mara",
                proposed_name="Mara",
                normalized_name="mara",
                status="accepted",
                confidence=95,
            ),
            CharacterCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_name="Noise",
                proposed_name="Noise",
                normalized_name="noise",
                status="pending",
                confidence=10,
            ),
            CharacterCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_name="Sol",
                proposed_name="Sol",
                normalized_name="sol",
                status="pending",
                source_batch_key=f"manual-demote:{book.id}:{right.id}",
                reason_codes=["manual_demoted_for_review"],
                confidence=90,
            ),
            CharacterCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_name="Old Pier",
                proposed_name="Old Pier",
                normalized_name="old pier",
                status="suppressed",
                rejection_reason="author_marked_place",
                confidence=95,
            ),
            CharacterRelationshipCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_character_a="Mara",
                raw_character_b="Sol",
                status="accepted",
            ),
            CharacterRelationshipCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_character_a="Mara",
                raw_character_b="Noise",
                status="suppressed",
            ),
            CharacterRelationshipCandidate(
                book_id=book.id,
                chapter_number=2,
                raw_character_a="Mara",
                raw_character_b="Iris",
                status="pending",
                reason_codes=["author_attached_endpoint"],
            ),
            CharacterRelationship(
                book_id=book.id,
                character_a_id=left.id,
                character_b_id=right.id,
                rel_type="friend",
                from_chapter=2,
                edited_by_author=True,
            ),
            CharacterRelationship(
                book_id=book.id,
                character_a_id=left.id,
                character_b_id=right.id,
                rel_type="ally",
                from_chapter=2,
                edited_by_author=False,
            ),
            CharacterState(character_id=left.id, at_chapter=2, trait_snapshot={"calm": True}),
        ]
    )
    await db.commit()

    await replace_chapter_extraction_records(
        db,
        book_id=book.id,
        chapter_number=2,
        replace_generated_intelligence=True,
    )
    await db.commit()

    assert (
        await db.scalar(select(CharacterMention).where(CharacterMention.book_id == book.id)) is None
    )
    candidates = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )
    relationship_candidates = (
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
    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    assert {(row.proposed_name, row.status) for row in candidates} == {
        ("Mara", "accepted"),
        ("Sol", "pending"),
        ("Old Pier", "suppressed"),
    }
    assert {(row.raw_character_b, row.status) for row in relationship_candidates} == {
        ("Sol", "accepted"),
        ("Iris", "pending"),
    }
    assert [(row.rel_type, row.edited_by_author) for row in relationships] == [("friend", True)]
    assert (
        await db.scalar(select(CharacterState).where(CharacterState.character_id == left.id))
        is None
    )
