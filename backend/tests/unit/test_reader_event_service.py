from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, ReaderEvent
from app.models.user import User
from app.services.data_generation_service import create_staging_generation, generation_scope
from app.services.reader_event_service import (
    InvalidReaderEventCursor,
    backfill_reader_events_for_book,
    list_reader_event_page,
    sync_reader_events_for_chapter,
)


@pytest.mark.asyncio
async def test_reader_event_pages_use_a_stable_keyset_cursor_with_tied_labels(db):
    user = User(email="reader-event-pages@example.com", password_hash="hashed")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Cursor Atlas",
        format="pdf",
        s3_key="books/cursor-atlas.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    first_chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Arrival",
        s3_key="chapters/cursor-atlas/1.json",
    )
    second_chapter = Chapter(
        book_id=book.id,
        number=2,
        title="Departure",
        s3_key="chapters/cursor-atlas/2.json",
    )
    db.add_all([first_chapter, second_chapter])
    await db.flush()

    await sync_reader_events_for_chapter(
        db,
        chapter=first_chapter,
        major_events=[
            {"event_title": "Arrival", "description": "The gate opens."},
            {"event_title": "Arrival", "description": "The city answers."},
        ],
        character_events=[
            {
                "character_id": "legacy-character",
                "character_name": "Mira",
                "event_title": "Chooses the road",
                "description": "Mira leaves the city.",
            }
        ],
    )
    await sync_reader_events_for_chapter(
        db,
        chapter=second_chapter,
        major_events=[{"event_title": "Departure", "description": "The caravan leaves."}],
        character_events=[],
    )

    first_page = await list_reader_event_page(
        db,
        book_id=book.id,
        max_visible_chapter=2,
        limit=2,
        cursor=None,
    )
    second_page = await list_reader_event_page(
        db,
        book_id=book.id,
        max_visible_chapter=2,
        limit=2,
        cursor=first_page["next_cursor"],
    )

    page_ids = [item["id"] for item in first_page["items"] + second_page["items"]]
    assert first_page["has_more"] is True
    assert second_page["has_more"] is False
    assert len(page_ids) == 4
    assert len(set(page_ids)) == 4
    assert [item["chapter_number"] for item in first_page["items"] + second_page["items"]] == [
        1,
        1,
        1,
        2,
    ]

    with pytest.raises(InvalidReaderEventCursor):
        await list_reader_event_page(
            db,
            book_id=book.id,
            max_visible_chapter=1,
            limit=2,
            cursor=first_page["next_cursor"],
        )


@pytest.mark.asyncio
async def test_reader_event_sync_replaces_only_the_changed_chapter_materialization(db):
    user = User(email="reader-event-sync@example.com", password_hash="hashed")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Replacement Atlas",
        format="pdf",
        s3_key="books/replacement-atlas.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="One",
        s3_key="chapters/replacement-atlas/1.json",
    )
    db.add(chapter)
    await db.flush()

    await sync_reader_events_for_chapter(
        db,
        chapter=chapter,
        major_events=[{"event_title": "Old beat", "description": "Old detail"}],
        character_events=[],
    )
    await sync_reader_events_for_chapter(
        db,
        chapter=chapter,
        major_events=[{"event_title": "New beat", "description": "New detail"}],
        character_events=[],
    )

    rows = (
        (await db.execute(select(ReaderEvent).where(ReaderEvent.chapter_id == chapter.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].payload["event_title"] == "New beat"


@pytest.mark.asyncio
async def test_reader_event_backfill_is_bounded_and_resumable(db):
    user = User(email="reader-event-backfill@example.com", password_hash="hashed")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Backfill Atlas",
        format="pdf",
        s3_key="books/backfill-atlas.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    first_chapter = Chapter(
        book_id=book.id,
        number=1,
        title="First",
        s3_key="chapters/backfill-atlas/1.json",
    )
    second_chapter = Chapter(
        book_id=book.id,
        number=2,
        title="Second",
        s3_key="chapters/backfill-atlas/2.json",
    )
    character = Character(
        book_id=book.id,
        name="Mira",
        first_chapter=1,
        growth_events=[
            {
                "chapter_number": 2,
                "event_title": "Mira changes course",
                "description": "She accepts the map.",
            }
        ],
    )
    db.add_all([first_chapter, second_chapter, character])
    await db.flush()
    db.add_all(
        [
            ChapterSummary(
                chapter_id=first_chapter.id,
                mode="detailed",
                content="First summary",
                key_events=[{"event_title": "The map appears"}],
            ),
            ChapterSummary(
                chapter_id=second_chapter.id,
                mode="detailed",
                content="Second summary",
                key_events=[{"event_title": "The journey begins"}],
            ),
        ]
    )
    await db.flush()

    first_batch = await backfill_reader_events_for_book(db, book_id=book.id, limit=1)

    assert first_batch["processed_chapters"] == 1
    assert first_batch["materialized_events"] == 1
    assert first_batch["has_more"] is True
    assert first_batch["next_cursor"] is not None
    first_rows = (
        (await db.execute(select(ReaderEvent).where(ReaderEvent.book_id == book.id)))
        .scalars()
        .all()
    )
    assert [row.chapter_number for row in first_rows] == [1]

    cursor = first_batch["next_cursor"]
    second_batch = await backfill_reader_events_for_book(
        db,
        book_id=book.id,
        after_chapter_number=cursor["chapter_number"],
        after_chapter_id=uuid.UUID(cursor["chapter_id"]),
        limit=1,
    )

    assert second_batch["processed_chapters"] == 1
    assert second_batch["materialized_events"] == 2
    assert second_batch["has_more"] is False
    assert second_batch["next_cursor"] is None
    rows = (
        (
            await db.execute(
                select(ReaderEvent)
                .where(ReaderEvent.book_id == book.id)
                .order_by(ReaderEvent.chapter_number, ReaderEvent.sort_order)
            )
        )
        .scalars()
        .all()
    )
    assert [(row.chapter_number, row.event_type) for row in rows] == [
        (1, "major"),
        (2, "major"),
        (2, "character"),
    ]


@pytest.mark.asyncio
async def test_reader_event_sync_uses_the_active_generation_scope(db):
    user = User(email="reader-event-generation@example.com", password_hash="hashed")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Generation Atlas",
        format="pdf",
        s3_key="books/generation-atlas.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="One",
        s3_key="chapters/generation-atlas/1.json",
    )
    db.add(chapter)
    await db.flush()
    rebuild_run_id = uuid.uuid4().hex
    generation_id = await create_staging_generation(
        db,
        book_id=book.id,
        rebuild_run_id=rebuild_run_id,
        reason="test",
    )

    with generation_scope(rebuild_run_id):
        await sync_reader_events_for_chapter(
            db,
            chapter=chapter,
            major_events=[{"event_title": "Generated beat"}],
            character_events=[],
        )
        await sync_reader_events_for_chapter(
            db,
            chapter=chapter,
            major_events=[{"event_title": "Generated beat"}],
            character_events=[],
        )

    rows = (
        (
            await db.execute(
                select(ReaderEvent)
                .where(ReaderEvent.chapter_id == chapter.id)
                .execution_options(include_all_generations=True)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].generation_id == generation_id
