import json
import uuid

import fitz
import pytest
from httpx import Request
from openai import APIConnectionError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.book import Book, Chapter
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterRelationshipCandidate,
    CharacterState,
)
from app.models.intelligence import BookChunk, CharacterRelationship, Notification
from app.models.operations import TaskExecution
from app.models.user import User
from app.services.extraction_character_profile_service import enrich_chapter_character_profiles
from app.services.extraction_processing_flow_service import _claim_book_completion
from app.workers.consumers import extraction_consumer
from app.workers.consumers.extraction_consumer import (
    _process_chapter,
    process_book,
)


def _embedding_for(text_count: int) -> list[list[float]]:
    return [[0.01] * 1536 for _ in range(text_count)]


def _pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    raw = document.write()
    document.close()
    return raw


VALID_PDF_BYTES = _pdf_bytes("Ingestion test manuscript")


@pytest.fixture(autouse=True)
async def _allow_ingestion_tests_to_dispatch_all_fixture_chapters(monkeypatch, db):
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.EXTRACTION_WORKER_CONCURRENCY", 20
    )
    await db.execute(
        update(TaskExecution)
        .where(TaskExecution.status.in_(("pending_dispatch", "queued", "running")))
        .values(status="succeeded")
    )
    await db.commit()


@pytest.fixture(autouse=True)
def _isolate_existing_ingestion_tests_from_profile_model(monkeypatch):
    async def _passthrough_profiles(entities, **_kwargs):
        return entities

    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.enrich_chapter_character_profiles",
        _passthrough_profiles,
    )


def _bind_worker_session(monkeypatch, db) -> None:
    worker_session_factory = async_sessionmaker(
        db.bind, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(extraction_consumer, "AsyncSessionLocal", worker_session_factory)
    monkeypatch.setitem(process_book.__globals__, "AsyncSessionLocal", worker_session_factory)


def _patch_embedding_batches(monkeypatch, embed_batch) -> None:
    monkeypatch.setattr(
        "app.services.extraction_chapter_embedding_service.embed_batch", embed_batch
    )
    monkeypatch.setattr(
        "app.services.extraction_character_reporting_service.embed_batch", embed_batch
    )


@pytest.mark.asyncio
async def test_claim_book_completion_skips_already_ready_book(db):
    user = User(
        email="completion-claim@lorevia.app", username="completion-claim", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Completion Claim",
        format="pdf",
        s3_key="books/completion-claim.pdf",
        status="processing",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="Chapter 1",
            s3_key="books/completion-claim/chapter-1.txt",
            processed=True,
        )
    )
    await db.flush()

    assert await _claim_book_completion(db, book.id) is True

    book.status = "ready"
    await db.flush()

    assert await _claim_book_completion(db, book.id) is False


@pytest.mark.asyncio
async def test_process_chapter_clears_stale_pending_and_suppressed_candidates_only(db, monkeypatch):
    user = User(
        email="stale-candidates@lorevia.app", username="stale-candidates", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Stale Candidates",
        format="pdf",
        s3_key="books/stale-candidates.pdf",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    accepted = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Mira",
        proposed_name="Mira",
        normalized_name="mira",
        status="accepted",
        confidence=90,
    )
    stale_pending = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Chapitre",
        proposed_name="Chapitre",
        normalized_name="chapitre",
        status="pending",
        confidence=0,
    )
    stale_suppressed = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Texte",
        proposed_name="Texte",
        normalized_name="texte",
        status="suppressed",
        confidence=0,
    )
    accepted_relationship = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Mira",
        raw_character_b="Sol",
        status="accepted",
    )
    stale_relationship = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Mira",
        raw_character_b="Texte",
        status="suppressed",
    )
    db.add_all(
        [accepted, stale_pending, stale_suppressed, accepted_relationship, stale_relationship]
    )
    await db.commit()

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        assert _kwargs["usage_db"] is None
        return {"characters": [], "relationships": [], "rejected_characters": []}

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        assert _kwargs["db"] is None
        return _embedding_for(len(texts))

    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    await _process_chapter(
        db, book, {"number": 1, "title": "One", "text": "Nothing relevant."}, queue_wait_ms=1
    )

    character_candidates = (
        (
            await db.execute(
                select(CharacterCandidate)
                .where(CharacterCandidate.book_id == book.id)
                .order_by(CharacterCandidate.proposed_name)
            )
        )
        .scalars()
        .all()
    )
    relationship_candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate)
                .where(CharacterRelationshipCandidate.book_id == book.id)
                .order_by(CharacterRelationshipCandidate.raw_character_b)
            )
        )
        .scalars()
        .all()
    )

    assert [(candidate.proposed_name, candidate.status) for candidate in character_candidates] == [
        ("Mira", "accepted")
    ]
    assert [
        (candidate.raw_character_b, candidate.status) for candidate in relationship_candidates
    ] == [("Sol", "accepted")]


@pytest.mark.asyncio
async def test_process_chapter_persists_cited_profile_from_separate_model_stage(db, monkeypatch):
    user = User(email="profile-stage@lorevia.app", username="profile-stage", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Evidence Stage",
        format="pdf",
        s3_key="books/evidence-stage.pdf",
        status="processing",
        total_chapters=1,
    )
    db.add(book)
    await db.commit()
    source = "Mara Vale promised to protect the gate. Mara Vale stood watch until morning."

    async def fake_discover(_text: str, **kwargs) -> dict:
        assert kwargs["discovery_only"] is True
        return {
            "characters": [
                {
                    "name": "Mara Vale",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.95,
                    "evidence": {
                        "has_dialogue_or_action": True,
                        "appears_multiple_times": True,
                        "mention_count": 2,
                        "strong_mention_count": 2,
                    },
                }
            ],
            "relationships": [],
        }

    async def fake_profile(**kwargs) -> str:
        assert source in kwargs["user"]
        return json.dumps(
            {
                "profile": {
                    "goal": "protect the gate",
                    "claim_evidence": {"goal": "Mara Vale promised to protect the gate."},
                }
            }
        )

    async def fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.enrich_chapter_character_profiles",
        enrich_chapter_character_profiles,
    )
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        fake_discover,
    )
    monkeypatch.setattr(
        "app.services.extraction_character_profile_service.complete_with_fallback",
        fake_profile,
    )
    _patch_embedding_batches(monkeypatch, fake_embed)

    await _process_chapter(
        db,
        book,
        {"number": 1, "title": "One", "text": source},
        queue_wait_ms=1,
    )
    await _process_chapter(
        db,
        book,
        {"number": 1, "title": "One", "text": source},
        queue_wait_ms=1,
    )

    characters = (
        (await db.execute(select(Character).where(Character.book_id == book.id))).scalars().all()
    )
    candidates = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )
    assert len(characters) == 1, [
        (candidate.proposed_name, candidate.status, candidate.reason_codes)
        for candidate in candidates
    ]
    character = characters[0]
    assert character.mention_count == 2
    assert character.analysis_metadata["mention_count_basis"] == "source_positions"
    assert character.goal == "protect the gate"
    assert character.analysis_metadata["profile_claims"] == [
        {
            "field": "goal",
            "value": "protect the gate",
            "quote": "Mara Vale promised to protect the gate.",
            "chapter_number": 1,
            "source_batch_key": f"{book.id}:1:1",
            "start": 0,
            "end": 39,
        }
    ]


@pytest.mark.asyncio
async def test_process_chapter_keeps_discovery_when_profile_response_is_unsupported(
    db, monkeypatch
):
    user = User(
        email="profile-partial@lorevia.app", username="profile-partial", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Partial Evidence Stage",
        format="pdf",
        s3_key="books/profile-partial.pdf",
        status="processing",
        total_chapters=1,
    )
    db.add(book)
    await db.commit()
    source = "Mara Vale walked to the gate. Mara Vale stood watch until morning."

    async def fake_discover(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Mara Vale",
                    "entity_type": "person",
                    "confidence": 0.95,
                    "evidence": {"has_dialogue_or_action": True, "mention_count": 2},
                }
            ],
            "relationships": [],
        }

    async def invalid_profile(**_kwargs) -> str:
        return '{"profile":{"goal":"invent a kingdom","claim_evidence":{}}}'

    async def fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.enrich_chapter_character_profiles",
        enrich_chapter_character_profiles,
    )
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        fake_discover,
    )
    monkeypatch.setattr(
        "app.services.extraction_character_profile_service.complete_with_fallback",
        invalid_profile,
    )
    _patch_embedding_batches(monkeypatch, fake_embed)

    assert await _process_chapter(
        db, book, {"number": 1, "title": "One", "text": source}, queue_wait_ms=1
    )

    chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))
    ).scalar_one()
    coverage = chapter.analysis_state["source_integrity"]["extraction_coverage"]
    assert chapter.processed is True
    assert coverage["complete"] is True
    assert coverage["profile_enrichment"]["status"] == "partial"
    assert coverage["profile_enrichment"]["invalid_response_batches"] == 1
    characters = (await db.execute(select(Character).where(Character.book_id == book.id))).scalars()
    assert all(character.goal != "invent a kingdom" for character in characters)


@pytest.mark.asyncio
async def test_process_chapter_remains_incomplete_when_embedding_provider_disconnects(
    db,
    monkeypatch,
):
    user = User(
        email="embedding-disconnect@lorevia.app",
        username="embedding-disconnect",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Interrupted Extraction",
        format="pdf",
        s3_key="books/interrupted-extraction.pdf",
        status="processing",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key="books/interrupted-extraction/chapter-1.txt",
        processed=True,
    )
    db.add(chapter)
    await db.flush()
    old_chunk = BookChunk(
        book_id=book.id,
        chapter_id=chapter.id,
        chunk_index=0,
        text="Last known good chunk",
        embedding=_embedding_for(1)[0],
        token_count=4,
    )
    db.add(old_chunk)
    await db.commit()

    async def _raise_connection_error(*args, **kwargs):
        raise APIConnectionError(request=Request("POST", "https://api.openai.com/v1/embeddings"))

    _patch_embedding_batches(monkeypatch, _raise_connection_error)

    with pytest.raises(APIConnectionError):
        await _process_chapter(
            db,
            book,
            {
                "number": 1,
                "title": "Chapter 1",
                "text": "Mara crosses the bridge before dawn.",
            },
        )

    await db.refresh(chapter)
    assert chapter.processed is False
    persisted_chunks = (
        (await db.execute(select(BookChunk).where(BookChunk.chapter_id == chapter.id)))
        .scalars()
        .all()
    )
    assert [(chunk.id, chunk.text) for chunk in persisted_chunks] == [
        (old_chunk.id, "Last known good chunk")
    ]


@pytest.mark.asyncio
async def test_upload_pipeline_stages_and_processes_multiple_chapters(
    client, db, auth_headers, monkeypatch
):
    captured_book_tasks: list[dict] = []
    captured_chapter_tasks: list[dict] = []
    captured_analysis_tasks: list[dict] = []
    captured_embed_inputs: list[list[str]] = []
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
        {"number": 1, "title": "One", "text": "Aoi Tanaka enters the archive and meets Ren Sato."},
        {"number": 2, "title": "Two", "text": "Ren Sato reveals the ledger and the hidden room."},
        {"number": 3, "title": "Three", "text": "They form a pact and leave before dawn."},
    ]

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Aoi Tanaka",
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
                    "name": "Ren Sato",
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
                    "character_a": "Aoi Tanaka",
                    "character_b": "Ren Sato",
                    "type": "ally",
                    "sentiment": 0.6,
                    "description": "They decide to work together.",
                    "label_evidence": {
                        "quote": "Aoi Tanaka enters the archive and meets Ren Sato."
                    },
                }
            ],
        }

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        captured_embed_inputs.append(list(texts))
        return _embedding_for(len(texts))

    async def _fake_send_processing_complete_with_stats(email: str, **payload):
        sent_ready_emails.append({"email": email, **payload})

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr("app.workers.tasks.analysis_tasks.analyse_chapter_task", _AnalysisTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)
    monkeypatch.setattr(
        "app.services.extraction_processing_flow_service.send_processing_complete_with_stats",
        _fake_send_processing_complete_with_stats,
    )

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Throughput Test", "mode": "reader"},
        files={"file": ("throughput.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202

    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=12)

    assert result == {"book_id": str(book_id), "chapters": 3}
    assert [item["args"][1] for item in captured_chapter_tasks] == [1]
    assert [item["kwargs"].get("countdown", 0) for item in captured_chapter_tasks] == [0]

    staged_chapters = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )
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
    pipeline = (
        processing_state.get("pipeline")
        if isinstance(processing_state.get("pipeline"), dict)
        else {}
    )
    extraction_pipeline = (
        pipeline.get("extraction") if isinstance(pipeline.get("extraction"), dict) else None
    )
    if extraction_pipeline is not None:
        assert extraction_pipeline["status"] == "running"
    assert processing_state.get("is_fully_ready", False) is False

    for chapter_data in chapters:
        await _process_chapter(db, book, chapter_data, queue_wait_ms=4)

    await db.refresh(book)
    processed_chapters = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )

    assert book.status == "processing"
    final_processing_state = (book.writer_workspace or {}).get("processing", {})
    assert final_processing_state["stage"] == "analysis"
    assert final_processing_state["chapters_completed"] == 3
    assert final_processing_state["chapters_total"] == 3
    assert final_processing_state["progress_pct"] == 100.0
    assert final_processing_state["eta_seconds"] == 0
    assert final_processing_state["parser_diagnostics"]["chapter_count"] == 3
    final_pipeline = (
        final_processing_state.get("pipeline")
        if isinstance(final_processing_state.get("pipeline"), dict)
        else {}
    )
    final_extraction = (
        final_pipeline.get("extraction")
        if isinstance(final_pipeline.get("extraction"), dict)
        else None
    )
    if final_extraction is not None:
        assert final_extraction["status"] == "succeeded"
    assert all(chapter.processed is True for chapter in processed_chapters)
    assert all(
        (chapter.analysis_state or {}).get("source_integrity", {}).get("recovery_status") == "ok"
        for chapter in processed_chapters
    )
    analysis_executions = (
        (
            await db.execute(
                select(TaskExecution)
                .where(
                    TaskExecution.book_id == book_id,
                    TaskExecution.task_name == "analysis_tasks.analyse_chapter",
                )
                .order_by(TaskExecution.chapter_number)
            )
        )
        .scalars()
        .all()
    )
    assert [execution.chapter_number for execution in analysis_executions] == [1, 2, 3]
    assert all(
        execution.status in {"pending_dispatch", "queued"} for execution in analysis_executions
    )
    assert any(
        batch and batch[0].startswith("Chapter 1: One\n\nAoi Tanaka enters the archive")
        for batch in captured_embed_inputs
    )
    ready_notification = (
        await db.execute(
            select(Notification).where(
                Notification.book_id == book_id, Notification.kind == "book_ready"
            )
        )
    ).scalar()
    assert ready_notification is not None
    assert ready_notification.data is not None
    assert ready_notification.data["analysis_complete"] is False
    assert "plot_thread_count" not in ready_notification.data
    assert "continuity_issue_count" not in ready_notification.data
    assert "story analysis is still running" in ready_notification.body
    assert sent_ready_emails == []


@pytest.mark.asyncio
async def test_process_book_persists_isbn_and_copyright_warning(
    client, db, auth_headers, monkeypatch
):
    captured_book_tasks: list[dict] = []

    class _ProcessBookTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_book_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    chapters = [{"number": 1, "title": "One", "text": "A single clean chapter."}]

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": 1},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)

    async def _fake_evaluate_document_copyright(*, format_name, raw, existing_isbn=None):
        assert format_name == "pdf"
        assert raw == VALID_PDF_BYTES
        assert existing_isbn is None
        return {"isbn": "9780306406157", "copyright_warning": True}

    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.evaluate_document_copyright",
        _fake_evaluate_document_copyright,
    )

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Compliance Test", "mode": "reader"},
        files={"file": ("compliance.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(response.json()["book_id"])

    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=8)

    assert result == {"book_id": str(book_id), "chapters": 1}
    book = await db.get(Book, book_id)
    assert book is not None
    assert book.isbn == "9780306406157"
    assert book.copyright_warning is True


@pytest.mark.asyncio
async def test_upload_pipeline_rejects_noise_characters_and_records_diagnostics(
    client, db, auth_headers, monkeypatch
):
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
            "text": "Well, Gregor watched the room while Grete spoke softly. Help, he shouted toward the pier. Gregor returned to the room.",
        },
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
                    "name": "Help",
                    "entity_type": "unknown",
                    "confidence": 0.95,
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

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Noise Filter Test", "mode": "reader"},
        files={"file": ("noise-filter.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202

    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=7)
    assert result == {"book_id": str(book_id), "chapters": 1}

    book = await db.get(Book, book_id)
    assert book is not None
    await _process_chapter(db, book, chapters[0], queue_wait_ms=4)
    await db.refresh(book)

    persisted_characters = (
        (
            await db.execute(
                select(Character).where(Character.book_id == book_id).order_by(Character.name.asc())
            )
        )
        .scalars()
        .all()
    )
    assert persisted_characters == []

    processing = (book.writer_workspace or {}).get("processing", {})
    extraction_diagnostics = (processing.get("parser_diagnostics") or {}).get(
        "character_extraction"
    ) or {}
    rejected = extraction_diagnostics.get("rejected_characters") or []
    rejected_reported = any(
        item["name"] in {"Well", "Help"}
        and item["stage"] in {"candidate_augmentation", "llm_clean", "mention_verifier"}
        and any(
            reason in str(item.get("reason") or "")
            for reason in {
                "save_gate",
                "visibility_score_below_threshold",
                "single_token_lacks_profile_evidence",
                "interjection_like_usage",
                "sentence_start_capitalization_only",
            }
        )
        for item in rejected
    )
    candidate_rows = (
        (
            await db.execute(
                select(CharacterCandidate).where(
                    CharacterCandidate.book_id == book_id,
                    CharacterCandidate.raw_name == "Well",
                )
            )
        )
        .scalars()
        .all()
    )
    gregor_candidate = (
        await db.execute(
            select(CharacterCandidate).where(
                CharacterCandidate.book_id == book_id,
                CharacterCandidate.proposed_name == "Gregor",
            )
        )
    ).scalar_one()
    assert rejected_reported or candidate_rows
    assert gregor_candidate.status == "pending"
    assert "candidate_dossier_needs_review" in (gregor_candidate.reason_codes or [])
    assert "insufficient_cross_chapter_support" in (gregor_candidate.reason_codes or [])


@pytest.mark.asyncio
async def test_upload_pipeline_routes_low_confidence_new_character_into_review_queue(
    client, db, auth_headers, monkeypatch
):
    captured_book_tasks: list[dict] = []

    class _ProcessBookTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_book_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    chapters = [
        {
            "number": 1,
            "title": "One",
            "text": "Anna looked up once. Gregor kept moving toward the door. Gregor paused at the threshold.",
        },
    ]

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Anna",
                    "entity_type": "person",
                    "confidence": 0.32,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "background character",
                    "evidence": {
                        "mention_count": 1,
                        "strong_mention_count": 1,
                        "has_dialogue_or_action": True,
                        "has_physical_description": False,
                        "appears_multiple_times": False,
                    },
                },
                {
                    "name": "Gregor",
                    "entity_type": "person",
                    "confidence": 0.94,
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

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Low Confidence Review Test", "mode": "reader"},
        files={"file": ("low-confidence-review.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    await process_book(str(book_id), queue_wait_ms=6)

    book = await db.get(Book, book_id)
    assert book is not None
    await _process_chapter(db, book, chapters[0], queue_wait_ms=2)

    persisted_characters = (
        (
            await db.execute(
                select(Character).where(Character.book_id == book_id).order_by(Character.name.asc())
            )
        )
        .scalars()
        .all()
    )
    candidate_rows = (
        (
            await db.execute(
                select(CharacterCandidate)
                .where(CharacterCandidate.book_id == book_id)
                .order_by(CharacterCandidate.proposed_name.asc())
            )
        )
        .scalars()
        .all()
    )

    assert persisted_characters == []
    assert [candidate.proposed_name for candidate in candidate_rows] == ["Anna", "Gregor"]
    anna_candidate = next(
        candidate for candidate in candidate_rows if candidate.proposed_name == "Anna"
    )
    gregor_candidate = next(
        candidate for candidate in candidate_rows if candidate.proposed_name == "Gregor"
    )
    assert anna_candidate.status == "suppressed"
    assert "low_confidence_needs_review" in (anna_candidate.reason_codes or [])
    assert gregor_candidate.status == "pending"
    assert "candidate_dossier_needs_review" in (gregor_candidate.reason_codes or [])
    assert "insufficient_cross_chapter_support" in (gregor_candidate.reason_codes or [])


@pytest.mark.asyncio
async def test_upload_pipeline_promotes_grounded_first_pass_full_name(
    client, db, auth_headers, monkeypatch
):
    chapters = [
        {
            "number": 1,
            "title": "One",
            "text": "Anna Sergeyevna stepped through the doorway. Anna Sergeyevna studied the room. Anna Sergeyevna checked the window latch.",
        },
    ]

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Anna Sergeyevna",
                    "canonical_name": "Anna Sergeyevna",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.94,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "A named character entering the scene.",
                    "evidence": {
                        "mention_count": 3,
                        "strong_mention_count": 2,
                        "has_dialogue_or_action": True,
                        "has_physical_description": True,
                        "appears_multiple_times": True,
                        "verifier": {
                            "local": {
                                "person_ner_mentions": 1,
                                "mid_sentence_mentions": 1,
                            },
                            "final": {
                                "confidence_band": "accept",
                                "is_person_like": True,
                                "reasons": [],
                            },
                        },
                    },
                },
            ],
            "relationships": [],
        }

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "First Pass Precision Test", "mode": "reader"},
        files={"file": ("first-pass-precision.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    await process_book(str(book_id), queue_wait_ms=6)

    book = await db.get(Book, book_id)
    assert book is not None
    await _process_chapter(db, book, chapters[0], queue_wait_ms=2)

    persisted_characters = (
        (
            await db.execute(
                select(Character).where(Character.book_id == book_id).order_by(Character.name.asc())
            )
        )
        .scalars()
        .all()
    )
    candidate_rows = (
        (
            await db.execute(
                select(CharacterCandidate)
                .where(CharacterCandidate.book_id == book_id)
                .order_by(CharacterCandidate.proposed_name.asc())
            )
        )
        .scalars()
        .all()
    )

    assert [character.name for character in persisted_characters] == ["Anna Sergeyevna"]
    assert [candidate.proposed_name for candidate in candidate_rows] == ["Anna Sergeyevna"]
    assert candidate_rows[0].status == "promoted"
    assert candidate_rows[0].matched_character_id == persisted_characters[0].id
    baseline_state = (
        await db.execute(
            select(CharacterState).where(
                CharacterState.character_id == persisted_characters[0].id,
                CharacterState.at_chapter == 1,
            )
        )
    ).scalar_one()
    assert baseline_state.trait_snapshot == {}


@pytest.mark.asyncio
async def test_process_chapter_records_ambiguous_roster_match_without_crashing(db, monkeypatch):
    user = User(
        email="ambiguous-roster@getlorevia.com",
        username="ambiguous_roster",
        password_hash="hash",
        tier="author",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Ambiguous Roster",
        format="txt",
        s3_key="ambiguous-roster.txt",
        status="processing",
        mode="author",
        total_chapters=1,
        writer_workspace={},
    )
    db.add(book)
    await db.flush()
    db.add_all(
        [
            Character(book_id=book.id, name="Mina Bell", aliases=["Mimi"], first_chapter=1),
            Character(book_id=book.id, name="Mina Reed", aliases=["Mimi"], first_chapter=1),
        ]
    )
    await db.commit()

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Mimi",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.82,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "A named character with an ambiguous roster match.",
                    "evidence": {
                        "mention_count": 2,
                        "strong_mention_count": 1,
                        "has_dialogue_or_action": True,
                        "appears_multiple_times": True,
                    },
                },
            ],
            "relationships": [],
        }

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    await _process_chapter(
        db,
        book,
        {"number": 1, "title": "One", "text": "Mimi crossed the room. Mimi opened the archive."},
        queue_wait_ms=2,
    )

    candidates = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book.id)))
        .scalars()
        .all()
    )

    assert len(candidates) == 1
    assert candidates[0].proposed_name == "Mimi"
    assert "ambiguous_roster_match" in candidates[0].reason_codes


@pytest.mark.asyncio
async def test_upload_pipeline_collapses_same_batch_full_name_and_short_name_duplicates(
    client, db, auth_headers, monkeypatch
):
    captured_book_tasks: list[dict] = []

    class _ProcessBookTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_book_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    chapters = [
        {
            "number": 1,
            "title": "One",
            "text": "Gregor Samsa woke before dawn. Gregor warned Grete to stay back.",
        },
    ]

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Gregor Samsa",
                    "canonical_name": "Gregor Samsa",
                    "aliases": [],
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
                {
                    "name": "Gregor",
                    "canonical_name": "Gregor",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.93,
                    "traits": {},
                    "personality_tags": ["anxious"],
                    "motivations": ["protect his sister"],
                    "fears": ["losing control"],
                    "arc_summary": "The same grounded central character under a shorter mention.",
                    "evidence": {
                        "mention_count": 1,
                        "strong_mention_count": 1,
                        "has_dialogue_or_action": True,
                        "has_physical_description": False,
                        "appears_multiple_times": False,
                    },
                },
                {
                    "name": "Grete",
                    "canonical_name": "Grete",
                    "aliases": [],
                    "entity_type": "person",
                    "confidence": 0.94,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": ["protect Gregor"],
                    "fears": [],
                    "arc_summary": "A grounded supporting character.",
                    "evidence": {
                        "mention_count": 1,
                        "strong_mention_count": 1,
                        "has_dialogue_or_action": True,
                        "has_physical_description": False,
                        "appears_multiple_times": False,
                    },
                },
            ],
            "relationships": [
                {
                    "character_a": "Gregor",
                    "character_b": "Grete",
                    "type": "family",
                    "sentiment": 0.7,
                    "description": "Gregor warns Grete to stay back.",
                    "label_evidence": {"quote": "Gregor warned Grete to stay back."},
                }
            ],
        }

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Same Batch Dedup Test", "mode": "reader"},
        files={"file": ("same-batch-dedup.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    await process_book(str(book_id), queue_wait_ms=6)

    book = await db.get(Book, book_id)
    assert book is not None
    await _process_chapter(db, book, chapters[0], queue_wait_ms=2)

    persisted_characters = (
        (
            await db.execute(
                select(Character).where(Character.book_id == book_id).order_by(Character.name.asc())
            )
        )
        .scalars()
        .all()
    )
    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
            )
        )
        .scalars()
        .all()
    )
    relationship_candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book_id
                )
            )
        )
        .scalars()
        .all()
    )
    candidate_rows = (
        (
            await db.execute(
                select(CharacterCandidate)
                .where(CharacterCandidate.book_id == book_id)
                .order_by(CharacterCandidate.proposed_name.asc())
            )
        )
        .scalars()
        .all()
    )

    assert [character.name for character in persisted_characters] == ["Gregor Samsa"]
    assert persisted_characters[0].aliases == ["Gregor"]
    assert relationships == []
    assert [candidate.proposed_name for candidate in candidate_rows] == [
        "Gregor",
        "Gregor Samsa",
        "Grete",
    ]
    candidate_statuses = {candidate.proposed_name: candidate.status for candidate in candidate_rows}
    assert candidate_statuses == {
        "Gregor": "accepted",
        "Gregor Samsa": "promoted",
        "Grete": "suppressed",
    }
    gregor_samsa_candidate = next(
        candidate for candidate in candidate_rows if candidate.proposed_name == "Gregor Samsa"
    )
    assert gregor_samsa_candidate.matched_character_id == persisted_characters[0].id
    gregor_candidate = next(
        candidate for candidate in candidate_rows if candidate.proposed_name == "Gregor"
    )
    assert gregor_candidate.matched_character_id == persisted_characters[0].id
    grete_candidate = next(
        candidate for candidate in candidate_rows if candidate.proposed_name == "Grete"
    )
    assert "weak_single_token_suppressed" in (grete_candidate.reason_codes or [])
    assert len(relationship_candidates) == 1
    assert relationship_candidates[0].raw_character_a == "Gregor"
    assert relationship_candidates[0].raw_character_b == "Grete"
    assert relationship_candidates[0].status == "suppressed"


@pytest.mark.asyncio
async def test_unresolved_relationships_become_relationship_review_records(
    client, db, auth_headers, monkeypatch
):
    captured_book_tasks: list[dict] = []

    class _ProcessBookTask:
        @staticmethod
        def apply_async(*, args, queue, **kwargs):
            captured_book_tasks.append({"args": args, "queue": queue, "kwargs": kwargs})
            return None

    chapters = [
        {"number": 1, "title": "One", "text": "Gregor argued with the Doctor in the hall."},
    ]

    async def _fake_extract(_text: str, **_kwargs) -> dict:
        return {
            "characters": [
                {
                    "name": "Gregor",
                    "entity_type": "person",
                    "confidence": 0.95,
                    "traits": {},
                    "personality_tags": [],
                    "motivations": [],
                    "fears": [],
                    "arc_summary": "Grounded lead.",
                    "evidence": {
                        "mention_count": 2,
                        "strong_mention_count": 1,
                        "has_dialogue_or_action": True,
                        "has_physical_description": True,
                        "appears_multiple_times": True,
                    },
                },
            ],
            "relationships": [
                {
                    "character_a": "Gregor",
                    "character_b": "Doctor",
                    "type": "hostile",
                    "sentiment": -0.5,
                    "description": "A tense confrontation.",
                    "label_evidence": {"quote": "Gregor argued with the Doctor in the hall."},
                }
            ],
        }

    async def _fake_embed(texts: list[str], **_kwargs) -> list[list[float]]:
        return _embedding_for(len(texts))

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Relationship Review Test", "mode": "reader"},
        files={"file": ("relationship-review.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202
    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    await process_book(str(book_id), queue_wait_ms=6)

    book = await db.get(Book, book_id)
    assert book is not None
    await _process_chapter(db, book, chapters[0], queue_wait_ms=2)
    await db.refresh(book)

    relationship_candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book_id
                )
            )
        )
        .scalars()
        .all()
    )
    character_candidates = (
        (await db.execute(select(CharacterCandidate).where(CharacterCandidate.book_id == book_id)))
        .scalars()
        .all()
    )

    assert len(relationship_candidates) == 1
    assert relationship_candidates[0].raw_character_a == "Gregor"
    assert relationship_candidates[0].raw_character_b == "Doctor"
    assert relationship_candidates[0].status == "suppressed"
    assert all(
        "relationship_unresolved" not in (candidate.reason_codes or [])
        for candidate in character_candidates
    )


@pytest.mark.asyncio
async def test_upload_pipeline_continues_when_cover_upload_fails(
    client, db, auth_headers, monkeypatch
):
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

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.extract_first_page_cover", lambda raw: (b"cover-bytes", "image/png")
    )
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.upload_binary", _raise_permission_error
    )
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _fake_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Cover Failure Test", "mode": "reader"},
        files={"file": ("cover-failure.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202

    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=9)

    assert result == {"book_id": str(book_id), "chapters": 2}

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.status == "processing"
    assert book.cover_s3_key is None
    assert book.total_chapters == 2
    assert book.writer_workspace["processing"]["stage"] == "parsed"


@pytest.mark.asyncio
async def test_upload_pipeline_keeps_chapter_incomplete_when_llm_extraction_fails(
    client, db, auth_headers, monkeypatch
):
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

    async def _fake_embed_for_dedup(_name: str, _traits: dict, **_kwargs) -> list[float]:
        return [0.01] * 1536

    async def _never_find_similar(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_chapter_llm_service.extract_characters_and_relationships",
        _raise_extract,
    )
    _patch_embedding_batches(monkeypatch, _fake_embed)
    monkeypatch.setattr("app.engine.character.deduplicator.embed_for_dedup", _fake_embed_for_dedup)
    monkeypatch.setattr(
        "app.services.extraction_new_character_resolution_service.find_similar", _never_find_similar
    )

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Metamorphosis", "mode": "reader"},
        files={"file": ("metamorphosis.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202

    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    await process_book(str(book_id), queue_wait_ms=5)

    book = await db.get(Book, book_id)
    assert book is not None

    for chapter_data in chapters:
        with pytest.raises(RuntimeError, match="extractor offline"):
            await _process_chapter(db, book, chapter_data, queue_wait_ms=3)

    ready_notifications = (
        (
            await db.execute(
                select(Notification).where(
                    Notification.book_id == book_id, Notification.kind == "book_ready"
                )
            )
        )
        .scalars()
        .all()
    )

    refreshed_book = await db.get(Book, book_id)
    chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book_id, Chapter.number == 1))
    ).scalar_one()
    characters = (
        (
            await db.execute(
                select(Character).where(Character.book_id == book_id).order_by(Character.name.asc())
            )
        )
        .scalars()
        .all()
    )
    candidates = (
        (
            await db.execute(
                select(CharacterCandidate)
                .where(CharacterCandidate.book_id == book_id)
                .order_by(CharacterCandidate.proposed_name.asc())
            )
        )
        .scalars()
        .all()
    )
    assert refreshed_book.status != "ready"
    assert chapter.processed is False
    assert ready_notifications == []
    assert characters == []
    assert candidates == []


@pytest.mark.asyncio
async def test_upload_pipeline_preserves_chapter_numbers_when_requested(
    client, db, auth_headers, monkeypatch
):
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
    parse_calls: list[str] = []

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )

    def _fake_parse_pdf(raw: bytes, *, language: str | None = None):
        parse_calls.append("structured")
        return parsed_chapters, {"source": "pdf", "chapter_count": len(parsed_chapters)}

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf_structure", _fake_parse_pdf)
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
    book_id = uuid.UUID(response.json()["book_id"])

    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=8)

    assert result == {"book_id": str(book_id), "chapters": 3}
    assert parse_calls == ["structured", "structured"]

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.preserve_chapter_numbers is True


@pytest.mark.asyncio
async def test_upload_pipeline_preserves_source_chapters_exactly_when_requested(
    client, db, auth_headers, monkeypatch
):
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
        {
            "number": 1,
            "source_number": 1,
            "title": "Chapter 1",
            "text": "Very long intact opening text.",
        },
        {
            "number": 2,
            "source_number": 2,
            "title": "Chapter 2",
            "text": "Very long intact middle text.",
        },
    ]
    parse_calls: list[str] = []

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )

    def _fake_parse_pdf(raw: bytes, *, language: str | None = None):
        parse_calls.append("structured")
        return parsed_chapters, {"source": "pdf", "chapter_count": len(parsed_chapters)}

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf_structure", _fake_parse_pdf)
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
    book_id = uuid.UUID(response.json()["book_id"])

    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=8)

    assert result == {"book_id": str(book_id), "chapters": 2}
    assert parse_calls == ["structured", "structured"]

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.preserve_source_chapters is True


@pytest.mark.asyncio
async def test_upload_pipeline_stops_when_book_is_hidden_mid_processing(
    client, db, auth_headers, monkeypatch
):
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

    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_book_task", _ProcessBookTask())
    monkeypatch.setattr("app.workers.tasks.extraction_tasks.process_chapter_task", _ChapterTask())
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.download_book", lambda key: VALID_PDF_BYTES
    )
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda raw, *, split_large_chapters=True, language=None: (
            chapters,
            {"source": "pdf", "chapter_count": len(chapters)},
        ),
    )
    monkeypatch.setattr("app.parsers.pdf_parser.extract_first_page_cover", lambda raw: None)
    monkeypatch.setattr(
        "app.services.extraction_book_processing_service.is_book_hidden", _fake_is_book_hidden
    )

    response = await client.post(
        "/api/v1/books/upload",
        headers=auth_headers,
        data={"title": "Cancelled Pipeline", "mode": "reader"},
        files={"file": ("cancelled.pdf", VALID_PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 202

    book_id = uuid.UUID(response.json()["book_id"])
    _bind_worker_session(monkeypatch, db)
    result = await process_book(str(book_id), queue_wait_ms=12)

    assert result == {"skipped": "book_unavailable"}
    assert captured_chapter_tasks == []

    book = await db.get(Book, book_id)
    assert book is not None
    await db.refresh(book)
    assert book.status == "pending"
    processing_state = (book.writer_workspace or {}).get("processing", {})
    assert processing_state == {}
