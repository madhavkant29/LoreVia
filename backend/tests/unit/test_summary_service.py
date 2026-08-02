import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.user import User
from app.services.summary_service import get_or_generate_summary


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
