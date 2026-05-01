import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.intelligence import Notification
from app.workers.consumers.extraction_consumer import _process_chapter, process_book


def _embedding_for(text_count: int) -> list[list[float]]:
    return [[0.01] * 1536 for _ in range(text_count)]


@pytest.mark.asyncio
async def test_upload_pipeline_stages_and_processes_multiple_chapters(client, db, auth_headers, monkeypatch):
    captured_book_tasks: list[dict] = []
    captured_chapter_tasks: list[dict] = []
    captured_analysis_tasks: list[dict] = []
    sent_ready_emails: list[dict] = []

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
        return {
            "characters": [
                {
                    "name": "Aoi",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.95,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "Keeps pushing deeper into the mystery.",
                    "archetype": "hero",
                    "evidence": {
                        "has_dialogue_or_action": True,
                        "appears_multiple_times": True,
                        "mention_count": 2,
                    },
                },
                {
                    "name": "Ren",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.95,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "Guards the archive's secrets.",
                    "archetype": "ally",
                    "evidence": {
                        "has_dialogue_or_action": True,
                        "appears_multiple_times": True,
                        "mention_count": 2,
                    },
                },
            ],
            "relationships": [
                {
                    "character_a": "Aoi",
                    "character_b": "Ren",
                    "type": "ally",
                    "sentiment": 0.6,
                    "description": "They decide to work together.",
                }
            ],
        }

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        return _embedding_for(len(texts))

    async def _fake_send_processing_complete_with_stats(email: str, **payload):
        sent_ready_emails.append({"email": email, **payload})

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _AnalysisTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: b"%PDF-1.4 mock")
    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf", lambda raw, *, split_large_chapters=True: chapters)
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.extract_characters_and_relationships", _fake_extract)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_batch", _fake_embed)
    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.send_processing_complete_with_stats",
        _fake_send_processing_complete_with_stats,
    )

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
    ready_notification = (
        await db.execute(
            select(Notification).where(Notification.book_id == book_id, Notification.kind == "book_ready")
        )
    ).scalar()
    assert ready_notification is not None
    assert ready_notification.data is not None
    assert ready_notification.data["character_count"] == 2
    assert ready_notification.data["relationship_count"] >= 1
    assert sent_ready_emails
    assert sent_ready_emails[0]["book_title"] == "Throughput Test"


@pytest.mark.asyncio
async def test_upload_pipeline_preserves_chapter_numbers_when_requested(client, db, auth_headers, monkeypatch):
    captured_book_tasks: list[dict] = []
    captured_chapter_tasks: list[dict] = []

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

    parsed_chapters = [
        {"number": 1, "source_number": 1, "title": "Chapter 1", "text": "Opening text."},
        {"number": 2, "source_number": 2, "title": "Chapter 2", "text": "Middle text."},
        {"number": 3, "source_number": 3, "title": "Chapter 3", "text": "Ending text."},
    ]
    parse_calls: list[bool] = []

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: b"%PDF-1.4 mock")

    def _fake_parse_pdf(raw: bytes, *, split_large_chapters: bool = True):
        parse_calls.append(split_large_chapters)
        return parsed_chapters

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf", _fake_parse_pdf)
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={
            "title": "Preserved Numbers",
            "mode": "reader",
            "preserve_chapter_numbers": "true",
        },
        files={"file": ("preserved.pdf", b"%PDF-1.4 mock", "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))

    result = await process_book(str(book_id), queue_wait_ms=8)

    assert result == {"book_id": str(book_id), "chapters": 3}
    assert parse_calls == [False]
    assert [item["args"][1] for item in captured_chapter_tasks] == [1, 2, 3]

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.preserve_chapter_numbers is True
