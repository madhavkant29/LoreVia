import json
import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.intelligence import ChapterSummary
from app.models.user import User
from app.services.summary_service import (
    get_or_generate_summary,
    persist_chapter_summary_payloads,
    summary_modes_to_generate,
)


def test_summary_modes_to_generate_can_force_refresh_existing_modes():
    assert summary_modes_to_generate({"detailed"}) == ["short", "key_points", "detailed"]
    assert summary_modes_to_generate({"short", "detailed", "key_points"}) == ["detailed"]
    assert summary_modes_to_generate({"short", "detailed", "key_points", "editorial_note"}) == []
    assert summary_modes_to_generate(
        {"short", "detailed", "key_points"},
        force_regenerate=True,
    ) == ["short", "detailed", "key_points"]


@pytest.mark.asyncio
async def test_get_or_generate_summary_returns_pending_without_request_time_generation(
    db, monkeypatch
):
    user = User(
        id=uuid.uuid4(),
        email="summary-test@example.com",
        password_hash="hashed",
    )
    book = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Atlas",
        format="pdf",
        work_type="novel",
        s3_key="books/atlas.pdf",
        status="ready",
        mode="reader",
        source_kind="single_upload",
    )
    chapter = Chapter(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="One",
        s3_key="chapters/atlas/1.txt",
        processed=True,
        analysis_state={"status": "queued", "generated_modes": [], "attempt_count": 1},
    )
    db.add(user)
    db.add(book)
    db.add(chapter)
    await db.commit()

    called = {"generate": False}

    async def _unexpected_generate(*_args, **_kwargs):
        called["generate"] = True
        return {}

    monkeypatch.setattr("app.engine.analysis.summariser.generate_summary", _unexpected_generate)

    payload = await get_or_generate_summary(db, book.id, 1, "short")

    assert payload is not None
    assert payload["status"] == "pending"
    assert payload["content"] is None
    assert called["generate"] is False


@pytest.mark.asyncio
async def test_get_or_generate_summary_masks_legacy_analysis_error(db):
    user = User(id=uuid.uuid4(), email="summary-error@example.com", password_hash="hashed")
    book = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Atlas",
        format="pdf",
        work_type="novel",
        s3_key="books/atlas-error.pdf",
        status="ready",
        mode="reader",
        source_kind="single_upload",
    )
    chapter = Chapter(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="One",
        s3_key="chapters/atlas-error/1.txt",
        processed=True,
        analysis_state={
            "status": "failed",
            "last_error": "SQL parameters: private manuscript text",
        },
    )
    db.add_all([user, book, chapter])
    await db.commit()

    payload = await get_or_generate_summary(db, book.id, 1, "short")

    assert payload["status"] == "failed"
    assert "private manuscript text" not in str(payload)


@pytest.mark.asyncio
async def test_persist_chapter_summary_payloads_updates_existing_and_inserts_missing(db):
    user = User(
        id=uuid.uuid4(),
        email="summary-persist@example.com",
        password_hash="hashed",
    )
    book = Book(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Summary persistence",
        format="pdf",
        work_type="novel",
        s3_key="books/summary-persistence.pdf",
        status="ready",
        mode="reader",
        source_kind="single_upload",
    )
    chapter = Chapter(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="One",
        s3_key="chapters/summary-persistence/1.txt",
    )
    existing = ChapterSummary(
        chapter_id=chapter.id,
        mode="detailed",
        content="Last known good summary",
    )
    db.add_all([user, book, chapter, existing])
    await db.commit()

    persisted = await persist_chapter_summary_payloads(
        db,
        chapter_id=chapter.id,
        payloads={
            "detailed": {
                "content": "Replacement summary",
                "key_events": [{"event_title": "Arrival"}],
                "themes": [{"theme": "trust"}],
            },
            "short": {"content": "Replacement short summary"},
            "editorial_note": {
                "content": json.dumps(
                    [
                        {
                            "issue": "The gate opens without a choice.",
                            "evidence": "The gate opened.",
                            "suggestion": "Show the choice.",
                        }
                    ]
                )
            },
        },
    )
    await db.commit()

    rows = (
        (
            await db.execute(
                select(ChapterSummary)
                .where(ChapterSummary.chapter_id == chapter.id)
                .order_by(ChapterSummary.mode)
            )
        )
        .scalars()
        .all()
    )
    assert persisted == ["short", "detailed", "editorial_note"]
    assert [(row.mode, row.content) for row in rows] == [
        ("detailed", "Replacement summary"),
        (
            "editorial_note",
            json.dumps(
                [
                    {
                        "issue": "The gate opens without a choice.",
                        "evidence": "The gate opened.",
                        "suggestion": "Show the choice.",
                    }
                ]
            ),
        ),
        ("short", "Replacement short summary"),
    ]
    assert rows[0].id == existing.id
    assert rows[0].key_events == [{"event_title": "Arrival"}]
