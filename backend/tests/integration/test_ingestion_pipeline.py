import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import Notification
from app.workers.consumers.extraction_consumer import _process_chapter, process_book


def _embedding_for(text_count: int) -> list[list[float]]:
    return [[0.01] * 1536 for _ in range(text_count)]


VALID_PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


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

    async def _fake_extract(_text: str, **_kwargs) -> dict:
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

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    async def _fake_send_processing_complete_with_stats(email: str, **payload):
        sent_ready_emails.append({"email": email, **payload})

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _AnalysisTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, {"source": "pdf", "chapter_count": len(chapters)}),
    )
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
        files={"file": ("throughput.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    assert len(captured_book_tasks) == 1

    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))
    result = await process_book(str(book_id), queue_wait_ms=12)

    assert result == {"book_id": str(book_id), "chapters": 3}
    assert [item["args"][1] for item in captured_chapter_tasks] == [1, 2, 3]
    assert [item["kwargs"].get("countdown", 0) for item in captured_chapter_tasks] == [0, 0, 1]

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
    await db.refresh(book)
    processing_state = (book.writer_workspace or {}).get("processing", {})
    assert book.status == "processing"
    assert processing_state["stage"] == "parsed"
    assert processing_state["chapters_total"] == 3
    assert processing_state["chapters_completed"] == 0
    assert processing_state["progress_pct"] == 0.0
    assert processing_state["parser_diagnostics"]["source"] == "pdf"
    pipeline = processing_state.get("pipeline") if isinstance(processing_state.get("pipeline"), dict) else {}
    extraction_pipeline = pipeline.get("extraction") if isinstance(pipeline.get("extraction"), dict) else None
    if extraction_pipeline is not None:
        assert extraction_pipeline["status"] == "running"
    assert processing_state.get("is_fully_ready", False) is False

    for chapter_data in chapters:
        await _process_chapter(db, book, chapter_data, queue_wait_ms=4)

    await db.refresh(book)
    processed_chapters = (
        await db.execute(select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number))
    ).scalars().all()

    assert book.status == "ready"
    final_processing_state = (book.writer_workspace or {}).get("processing", {})
    assert final_processing_state["stage"] == "complete"
    assert final_processing_state["chapters_completed"] == 3
    assert final_processing_state["chapters_total"] == 3
    assert final_processing_state["progress_pct"] == 100.0
    assert final_processing_state["eta_seconds"] == 0
    assert final_processing_state["parser_diagnostics"]["chapter_count"] == 3
    final_pipeline = final_processing_state.get("pipeline") if isinstance(final_processing_state.get("pipeline"), dict) else {}
    final_extraction = final_pipeline.get("extraction") if isinstance(final_pipeline.get("extraction"), dict) else None
    if final_extraction is not None:
        assert final_extraction["status"] == "succeeded"
    assert all(chapter.processed is True for chapter in processed_chapters)
    assert all((chapter.analysis_state or {}).get("source_integrity", {}).get("recovery_status") == "ok" for chapter in processed_chapters)
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
    assert ready_notification.data["analysis_complete"] is False
    assert "plot_thread_count" not in ready_notification.data
    assert "continuity_issue_count" not in ready_notification.data
    assert "analysis is still running" in ready_notification.body
    assert sent_ready_emails == []


@pytest.mark.asyncio
async def test_process_book_persists_isbn_and_copyright_warning(client, db, auth_headers, monkeypatch):
    captured_book_tasks: list[dict] = []

    class _ProcessBookTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_book_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    chapters = [{"number": 1, "title": "One", "text": "A single clean chapter."}]

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, {"source": "pdf", "chapter_count": 1}),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)

    async def _fake_evaluate_document_copyright(*, format_name, raw, existing_isbn=None):
        assert format_name == "pdf"
        assert raw == VALID_PDF_BYTES
        assert existing_isbn is None
        return {"isbn": "9780306406157", "copyright_warning": True}

    monkeypatch.setattr(
        "app.workers.consumers.extraction_consumer.evaluate_document_copyright",
        _fake_evaluate_document_copyright,
    )

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Compliance Test", "mode": "reader"},
        files={"file": ("compliance.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))

    result = await process_book(str(book_id), queue_wait_ms=8)

    assert result == {"book_id": str(book_id), "chapters": 1}
    book = await db.get(Book, book_id)
    assert book is not None
    assert book.isbn == "9780306406157"
    assert book.copyright_warning is True


@pytest.mark.asyncio
async def test_upload_pipeline_rejects_noise_characters_and_records_diagnostics(client, db, auth_headers, monkeypatch):
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

    chapters = [
        {"number": 1, "title": "One", "text": "Well, Gregor watched the room while Grete spoke softly."},
    ]

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Well",
                    "entity_type": "unknown",
                    "confidence": 0.96,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "is a character",
                    "evidence": {
                        "mention_count": 1,
                        "strong_mention_count": 0,
                        "has_dialogue_or_action": False,
                        "has_physical_description": False,
                        "appears_multiple_times": False,
                    },
                },
                {
                    "name": "Gregor",
                    "entity_type": "person",
                    "confidence": 0.95,
                    "traits": {},
                    "personality_tags": ["anxious"],
                    "motivations": ["protect his family"],
                    "fears": ["losing control"],
                    "arc_summary": "A grounded central character.",
                    "evidence": {
                        "mention_count": 2,
                        "strong_mention_count": 1,
                        "has_dialogue_or_action": True,
                        "has_physical_description": True,
                        "appears_multiple_times": True,
                    },
                },
            ],
            "relationships": [],
        }

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, {"source": "pdf", "chapter_count": len(chapters)}),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.extract_characters_and_relationships", _fake_extract)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_batch", _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Noise Filter Test", "mode": "reader"},
        files={"file": ("noise-filter.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    assert len(captured_book_tasks) == 1

    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))
    result = await process_book(str(book_id), queue_wait_ms=7)
    assert result == {"book_id": str(book_id), "chapters": 1}
    assert [item["args"][1] for item in captured_chapter_tasks] == [1]

    book = await db.get(Book, book_id)
    assert book is not None
    await _process_chapter(db, book, chapters[0], queue_wait_ms=4)
    await db.refresh(book)

    persisted_characters = (
        await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.name.asc()))
    ).scalars().all()
    assert [character.name for character in persisted_characters] == ["Gregor"]

    processing = (book.writer_workspace or {}).get("processing", {})
    extraction_diagnostics = (processing.get("parser_diagnostics") or {}).get("character_extraction") or {}
    rejected = extraction_diagnostics.get("rejected_characters") or []
    assert any(
        item["name"] == "Well"
        and item["stage"] in {"candidate_augmentation", "llm_clean"}
        and "save_gate" in str(item.get("reason") or "")
        for item in rejected
    )
    assert persisted_characters[0].analysis_metadata["confidence_band"] in {"high", "medium"}


@pytest.mark.asyncio
async def test_upload_pipeline_continues_when_cover_upload_fails(client, db, auth_headers, monkeypatch):
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

    chapters = [
        {"number": 1, "title": "One", "text": "Aoi enters the archive and meets Ren."},
        {"number": 2, "title": "Two", "text": "Ren reveals the ledger and the hidden room."},
    ]

    async def _fake_extract(_text: str) -> dict:
        return {"characters": [], "relationships": []}

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    def _raise_permission_error(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, {"source": "pdf", "chapter_count": len(chapters)}),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: (b"cover-bytes", "image/png"))
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.upload_binary", _raise_permission_error)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.extract_characters_and_relationships", _fake_extract)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_batch", _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Cover Failure Test", "mode": "reader"},
        files={"file": ("cover-failure.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    assert len(captured_book_tasks) == 1

    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))
    result = await process_book(str(book_id), queue_wait_ms=9)

    assert result == {"book_id": str(book_id), "chapters": 2}
    assert [item["args"][1] for item in captured_chapter_tasks] == [1, 2]

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.status == "processing"
    assert book.cover_s3_key is None
    assert book.total_chapters == 2
    assert book.writer_workspace["processing"]["stage"] == "parsed"


@pytest.mark.asyncio
async def test_upload_pipeline_recovers_named_characters_when_llm_extraction_fails(client, db, auth_headers, monkeypatch):
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

    chapters = [
        {
            "number": 1,
            "title": "One",
            "text": "Gregor Samsa woke before dawn. Gregor paced the room while his sister Grete called to him twice.",
        },
    ]

    async def _raise_extract(*_args, **_kwargs):
        raise RuntimeError("extractor offline")

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    async def _fake_embed_for_dedup(_name: str, _traits: dict) -> list[float]:
        return [0.01] * 1536

    async def _never_find_similar(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, {"source": "pdf", "chapter_count": len(chapters)}),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.extract_characters_and_relationships", _raise_extract)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_batch", _fake_embed)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.embed_for_dedup", _fake_embed_for_dedup)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.find_similar", _never_find_similar)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Metamorphosis", "mode": "reader"},
        files={"file": ("metamorphosis.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    assert len(captured_book_tasks) == 1

    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))
    await process_book(str(book_id), queue_wait_ms=5)

    book = await db.get(Book, book_id)
    assert book is not None

    for chapter_data in chapters:
        await _process_chapter(db, book, chapter_data, queue_wait_ms=3)

    ready_notification = (
        await db.execute(
            select(Notification).where(Notification.book_id == book_id, Notification.kind == "book_ready")
        )
    ).scalar_one()

    assert ready_notification.data is not None
    assert ready_notification.data["character_count"] >= 2
    assert "character extraction hit an internal issue" not in ready_notification.body

    refreshed_book = await db.get(Book, book_id)
    processing = (refreshed_book.writer_workspace or {}).get("processing", {})
    extraction_diagnostics = (processing.get("parser_diagnostics") or {}).get("character_extraction") or {}
    assert extraction_diagnostics["failed_batches"] == 1
    assert extraction_diagnostics["fallback_batches"] == 1
    assert extraction_diagnostics["fallback_character_count"] >= 2


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
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)

    def _fake_parse_pdf(raw: bytes, *, split_large_chapters: bool = True):
        parse_calls.append(split_large_chapters)
        return parsed_chapters, {"source": "pdf", "chapter_count": len(parsed_chapters)}

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf_with_diagnostics", _fake_parse_pdf)
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={
            "title": "Preserved Numbers",
            "mode": "reader",
            "preserve_chapter_numbers": "true",
        },
        files={"file": ("preserved.pdf", VALID_PDF_BYTES, "application/pdf")},
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


@pytest.mark.asyncio
async def test_upload_pipeline_preserves_source_chapters_exactly_when_requested(client, db, auth_headers, monkeypatch):
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
        {"number": 1, "source_number": 1, "title": "Chapter 1", "text": "Very long intact opening text."},
        {"number": 2, "source_number": 2, "title": "Chapter 2", "text": "Very long intact middle text."},
    ]
    parse_calls: list[bool] = []

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)

    def _fake_parse_pdf(raw: bytes, *, split_large_chapters: bool = True):
        parse_calls.append(split_large_chapters)
        return parsed_chapters, {"source": "pdf", "chapter_count": len(parsed_chapters)}

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf_with_diagnostics", _fake_parse_pdf)
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={
            "title": "Exact Source",
            "mode": "reader",
            "preserve_source_chapters": "true",
        },
        files={"file": ("exact-source.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))

    result = await process_book(str(book_id), queue_wait_ms=8)

    assert result == {"book_id": str(book_id), "chapters": 2}
    assert parse_calls == [False]
    assert [item["args"][1] for item in captured_chapter_tasks] == [1, 2]

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.preserve_source_chapters is True


@pytest.mark.asyncio
async def test_upload_pipeline_stops_when_book_is_hidden_mid_processing(client, db, auth_headers, monkeypatch):
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

    chapters = [
        {"number": 1, "title": "One", "text": "Aoi enters the archive and meets Ren."},
        {"number": 2, "title": "Two", "text": "Ren reveals the ledger and the hidden room."},
    ]

    async def _fake_is_book_hidden(*args, **kwargs):
        return True

    monkeypatch.setattr("app.api.v1.routes.books.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.download_book", lambda key: VALID_PDF_BYTES)
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, {"source": "pdf", "chapter_count": len(chapters)}),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr("app.workers.consumers.extraction_consumer.is_book_hidden", _fake_is_book_hidden)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Cancelled Pipeline", "mode": "reader"},
        files={"file": ("cancelled.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    assert len(captured_book_tasks) == 1

    book_id = uuid.UUID(str(captured_book_tasks[0]["args"][0]))
    result = await process_book(str(book_id), queue_wait_ms=12)

    assert result == {"skipped": "book_hidden"}
    assert captured_chapter_tasks == []

    book = await db.get(Book, book_id)
    assert book is not None
    await db.refresh(book)
    assert book.status == "failed"
    processing_state = (book.writer_workspace or {}).get("processing", {})
    assert processing_state["stage"] == "cancelled"
    assert processing_state["status"] == "failed"
