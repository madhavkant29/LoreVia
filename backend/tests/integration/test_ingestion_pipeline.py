import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.workers.consumers.extraction_consumer import _process_chapter, process_book


def _embedding_for(text_count: int) -> list[list[float]]:
    return [[0.01] * 1536 for _ in range(text_count)]


@pytest.mark.asyncio
async def test_upload_pipeline_stages_and_processes_multiple_chapters(client, db, auth_headers, monkeypatch):
    captured_book_tasks: list[dict] = []
    captured_chapter_tasks: list[dict] = []
    captured_analysis_tasks: list[dict] = []

    class _ProcessBookTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_book_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    class _ChapterTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_chapter_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    class _AnalysisTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_analysis_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    chapters = [
        {"number": 1, "title": "One", "text": "Aoi enters the archive and meets Ren."},
        {"number": 2, "title": "Two", "text": "Ren reveals the ledger and the hidden room."},
        {"number": 3, "title": "Three", "text": "They form a pact and leave before dawn."},
    ]

    async def _fake_extract(_text: str) -> dict:
        return {"characters": [], "relationships": []}

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _AnalysisTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: b"%PDF-1.4 mock")
    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf", lambda raw: chapters)
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.extract_characters_and_relationships", _fake_extract)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_batch", _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Throughput Test", "mode": "reader"},
        files={"file": ("throughput.pdf", b"%PDF-1.4 mock", "application/pdf")},
    )

    assert response.status_code == 202
    assert len(captured_book_tasks) == 1

    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))
    result = await process_book(str(book_id), queue_wait_ms=12)

    assert result == {"book_id": str(book_id), "chapters": 3}
    assert [item["args"][1] for item in captured_chapter_tasks] == [1, 2, 3]
    assert [item["kwargs"].get("countdown", 0) for item in captured_chapter_tasks] == [0, 2, 2]

    staged_chapters = (
        await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number))
    ).scalars().all()
    assert [chapter.s3_key for chapter in staged_chapters] == [
        f"chapters/{book_id}/1.txt",
        f"chapters/{book_id}/2.txt",
        f"chapters/{book_id}/3.txt",
    ]
    assert all(chapter.processed is False for chapter in staged_chapters)

    book = await db.get(Book, book_id)
    for chapter_data in chapters:
        await _process_chapter(db, book, chapter_data, queue_wait_ms=4)

    await db.refresh(book)
    processed_chapters = (
        await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number))
    ).scalars().all()

    assert book.status == "ready"
    assert all(chapter.processed is True for chapter in processed_chapters)
    assert captured_analysis_tasks
    assert captured_analysis_tasks[0]["args"][2] == "One"
