import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import create_access_token
from app.models.operations import TaskExecution

_STORED_TEST_CHAPTERS: dict[tuple[uuid.UUID, int], str] = {}


@pytest.fixture(autouse=True)
def _mock_reprocess_stored_chapters(monkeypatch):
    _STORED_TEST_CHAPTERS.clear()

    async def load_saved_source(book_id, chapter_number, **_kwargs):
        text = _STORED_TEST_CHAPTERS.get((book_id, chapter_number))
        return {"text": text, "html": None} if text else None

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.load_processing_chapter_payload",
        load_saved_source,
    )
    yield
    _STORED_TEST_CHAPTERS.clear()


@pytest.fixture(autouse=True)
async def _isolate_durable_dispatch_capacity(db):
    await db.execute(
        update(TaskExecution)
        .where(TaskExecution.status.in_(("pending_dispatch", "queued", "running")))
        .values(status="succeeded")
    )
    await db.commit()


async def _register_author(client, db, email: str, monkeypatch) -> tuple[dict[str, str], uuid.UUID]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:24],
            "password": "StrongPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.require_author_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.require_author_access",
        lambda *_args, **_kwargs: None,
    )

    return headers, user_id


async def _create_editor_project(client, headers, title="Test Project") -> str:
    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": title},
    )
    assert response.status_code == 200
    return response.json()["book_id"]


async def _add_chapter(db, book_id: uuid.UUID, number: int = 1, text: str = "Some story content."):
    from app.models.book import Chapter

    chapter = Chapter(
        book_id=book_id,
        number=number,
        title=f"Chapter {number}",
        s3_key=f"chapters/{book_id}/{number}.txt",
        word_count=len(text.split()),
    )
    db.add(chapter)
    await db.commit()
    _STORED_TEST_CHAPTERS[(book_id, number)] = text
    return chapter


async def _chapter_executions(db, book_id: uuid.UUID) -> list[TaskExecution]:
    return (
        (
            await db.execute(
                select(TaskExecution)
                .where(
                    TaskExecution.book_id == book_id,
                    TaskExecution.task_name == "extraction_tasks.process_chapter",
                )
                .order_by(TaskExecution.chapter_number)
            )
        )
        .scalars()
        .all()
    )


async def _ready_reprocess_fingerprint(client, url: str, headers: dict[str, str]) -> str:
    preview = await client.get(f"{url}/preflight", headers=headers)
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["ready"] is True
    assert payload["preview_fingerprint"]
    return payload["preview_fingerprint"]


@pytest.mark.asyncio
async def test_reprocess_requires_confirmation(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-no-ed-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    book_id = await _create_editor_project(client, headers)
    await _add_chapter(db, uuid.UUID(book_id))

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
    )

    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_preflight_checks_stored_sources_and_rejects_stale_snapshot(
    client, db, monkeypatch
):
    headers, user_id = await _register_author(
        client, db, f"repr-preview-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    from app.models.book import Book
    from app.models.character import (
        Character,
        CharacterCandidate,
        CharacterIdentityConstraint,
        CharacterRelationshipCandidate,
        VoiceReviewDecision,
    )
    from app.models.user import ProcessingUsageEvent

    book = Book(
        user_id=user_id,
        title="Saved source preflight",
        format="txt",
        s3_key="saved-source.txt",
        status="ready",
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id, 1, "The first stored chapter has four words.")
    db.add_all(
        [
            Character(
                book_id=book.id,
                name="Reviewed Mara",
                first_chapter=1,
                analysis_metadata={"user_reviewed": True},
            ),
            Character(book_id=book.id, name="Generated Milo", first_chapter=1),
        ]
    )
    await db.commit()
    stored_text = "The first stored chapter has four words."

    async def fake_load(*_args, **_kwargs):
        return {"text": stored_text}

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.load_processing_chapter_payload", fake_load
    )
    url = f"/api/v1/books/{book.id}/manuscript/reprocess"
    preview = await client.get(f"{url}/preflight", headers=headers)
    assert preview.status_code == 200
    snapshot = preview.json()
    assert snapshot["ready"] is True
    assert snapshot["chapters_total"] == 1
    assert snapshot["protected_characters"] == 1
    assert snapshot["replaceable_characters"] == 1
    assert snapshot["missing_source_chapters"] == []
    assert snapshot["preview_fingerprint"]
    assert "The first stored chapter" not in str(snapshot)
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ProcessingUsageEvent)
            .where(ProcessingUsageEvent.book_id == book.id)
        )
    ) == 0

    without_preview = await client.post(
        url, headers=headers, json={"confirm_processing_words": True}
    )
    assert without_preview.status_code == 409
    assert "preview" in without_preview.json()["detail"].lower()
    assert await _chapter_executions(db, book.id) == []

    review_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    reviewed_character = await db.scalar(
        select(Character).where(Character.book_id == book.id, Character.name == "Reviewed Mara")
    )
    reviewed_character.analysis_metadata = {
        **reviewed_character.analysis_metadata,
        "review_note": "Keep the author's correction to Mara's profile.",
    }
    await db.commit()
    stale_review = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": review_preview["preview_fingerprint"],
        },
    )
    assert stale_review.status_code == 409

    decision_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    db.add(
        VoiceReviewDecision(
            book_id=book.id,
            user_id=user_id,
            finding_key="a" * 64,
            decision="intentional",
            note="Deliberate change in this scene.",
        )
    )
    await db.commit()
    stale_decision = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": decision_preview["preview_fingerprint"],
        },
    )
    assert stale_decision.status_code == 409

    candidate_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    candidate = CharacterCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_name="Mara",
        proposed_name="Mara",
        normalized_name="mara",
        status="pending",
    )
    db.add(candidate)
    await db.commit()
    stale_candidate = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": candidate_preview["preview_fingerprint"],
        },
    )
    assert stale_candidate.status_code == 409
    candidate_update_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    candidate.status = "rejected"
    candidate.reason_codes = ["author_rejected_candidate"]
    await db.commit()
    stale_candidate_update = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": candidate_update_preview["preview_fingerprint"],
        },
    )
    assert stale_candidate_update.status_code == 409

    relationship_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    relationship_candidate = CharacterRelationshipCandidate(
        book_id=book.id,
        chapter_number=1,
        raw_character_a="Mara",
        raw_character_b="Milo",
        status="pending",
    )
    db.add(relationship_candidate)
    await db.commit()
    stale_relationship = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": relationship_preview["preview_fingerprint"],
        },
    )
    assert stale_relationship.status_code == 409
    relationship_update_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    relationship_candidate.matched_character_a_id = reviewed_character.id
    relationship_candidate.reason_codes = ["author_attached_endpoint"]
    await db.commit()
    stale_relationship_update = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": relationship_update_preview["preview_fingerprint"],
        },
    )
    assert stale_relationship_update.status_code == 409

    generated_character = await db.scalar(
        select(Character).where(Character.book_id == book.id, Character.name == "Generated Milo")
    )
    generated_character.analysis_metadata = {"user_reviewed": True}
    await db.commit()
    identity_preview = (await client.get(f"{url}/preflight", headers=headers)).json()
    db.add(
        CharacterIdentityConstraint(
            book_id=book.id,
            left_character_id=reviewed_character.id,
            right_character_id=generated_character.id,
            left_text="Mara",
            right_text="Milo",
            constraint_type="not_same_character",
            source="manual",
        )
    )
    await db.commit()
    stale_identity = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": identity_preview["preview_fingerprint"],
        },
    )
    assert stale_identity.status_code == 409
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ProcessingUsageEvent)
            .where(ProcessingUsageEvent.book_id == book.id)
        )
    ) == 0

    stored_text = "The stored chapter changed after the preview was loaded."
    stale = await client.post(
        url,
        headers=headers,
        json={
            "confirm_processing_words": True,
            "preview_fingerprint": snapshot["preview_fingerprint"],
        },
    )
    assert stale.status_code == 409
    assert "Refresh the preflight" in stale.json()["detail"]
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ProcessingUsageEvent)
            .where(ProcessingUsageEvent.book_id == book.id)
        )
    ) == 0


@pytest.mark.asyncio
async def test_reprocess_preflight_blocks_missing_stored_source(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-missing-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    from app.models.book import Book
    from app.models.user import ProcessingUsageEvent

    book = Book(
        user_id=user_id,
        title="Missing source",
        format="txt",
        s3_key="missing-source.txt",
        status="ready",
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id, 1, "Saved chapter text.")

    async def missing_load(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.load_processing_chapter_payload",
        missing_load,
    )
    preview = await client.get(
        f"/api/v1/books/{book.id}/manuscript/reprocess/preflight", headers=headers
    )
    assert preview.status_code == 200
    assert preview.json()["ready"] is False
    assert preview.json()["missing_source_chapters"] == [1]
    assert preview.json()["preview_fingerprint"] is None

    start = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_processing_words": True},
    )
    assert start.status_code == 409
    assert "preflight" in start.json()["detail"].lower()
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ProcessingUsageEvent)
            .where(ProcessingUsageEvent.book_id == book.id)
        )
        == 0
    )
    assert await _chapter_executions(db, book.id) == []


@pytest.mark.asyncio
async def test_reprocess_source_loading_runs_outside_database_transaction(client, db, monkeypatch):
    from app.models.book import Book
    from app.models.user import User
    from app.schemas.books import ManuscriptReprocessBody
    from app.services.manuscript_reprocess_service import (
        preview_manual_manuscript_reprocess,
        start_manual_manuscript_reprocess,
    )

    headers, user_id = await _register_author(
        client, db, f"repr-no-open-txn-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = uuid.UUID(await _create_editor_project(client, headers))
    await _add_chapter(db, book_id)
    user = await db.get(User, user_id)
    observed: list[bool] = []

    async def load_without_transaction(*_args, **_kwargs):
        observed.append(db.in_transaction())
        return None

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.load_processing_chapter_payload",
        load_without_transaction,
    )
    preview = await preview_manual_manuscript_reprocess(db=db, current_user=user, book_id=book_id)
    assert preview.ready is False
    with pytest.raises(HTTPException) as exc:
        await start_manual_manuscript_reprocess(
            db=db,
            current_user=user,
            book_id=book_id,
            body=ManuscriptReprocessBody(confirm_processing_words=True),
        )
    assert exc.value.status_code == 409
    assert observed == [False, False]
    assert await db.get(Book, book_id) is not None


@pytest.mark.asyncio
async def test_reprocess_rejects_chapter_change_during_source_loading(client, db, monkeypatch):
    from app.models.book import Book, Chapter
    from app.models.user import ProcessingUsageEvent

    headers, user_id = await _register_author(
        client, db, f"repr-raced-source-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book = Book(
        user_id=user_id,
        title="Source race",
        format="txt",
        s3_key="source-race.txt",
        status="ready",
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id)
    url = f"/api/v1/books/{book.id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def mutate_during_load(*_args, **_kwargs):
        async with sessions() as session:
            await session.execute(
                update(Chapter)
                .where(Chapter.book_id == book.id, Chapter.number == 1)
                .values(title="Edited while loading")
            )
            await session.commit()
        return {"text": _STORED_TEST_CHAPTERS[(book.id, 1)], "html": None}

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.load_processing_chapter_payload",
        mutate_during_load,
    )
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_processing_words": True, "preview_fingerprint": fingerprint},
    )
    assert response.status_code == 409
    assert "changed" in response.json()["detail"].lower()
    assert await _chapter_executions(db, book.id) == []
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ProcessingUsageEvent)
            .where(ProcessingUsageEvent.book_id == book.id)
        )
    ) == 0


@pytest.mark.asyncio
async def test_single_chapter_reprocess_rejects_source_change_before_reservation(
    client, db, monkeypatch
):
    from app.models.book import Chapter
    from app.models.user import ProcessingUsageEvent

    headers, user_id = await _register_author(
        client, db, f"repr-chapter-race-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = uuid.UUID(await _create_editor_project(client, headers))
    await _add_chapter(db, book_id)
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def mutate_during_load(*_args, **_kwargs):
        async with sessions() as session:
            await session.execute(
                update(Chapter)
                .where(Chapter.book_id == book_id, Chapter.number == 1)
                .values(title="Edited before chapter reprocess")
            )
            await session.commit()
        return {"text": _STORED_TEST_CHAPTERS[(book_id, 1)], "html": None}

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.load_processing_chapter_payload",
        mutate_during_load,
    )
    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/chapters/1/reprocess", headers=headers
    )
    assert response.status_code == 409
    assert "changed" in response.json()["detail"].lower()
    assert await _chapter_executions(db, book_id) == []
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ProcessingUsageEvent)
            .where(ProcessingUsageEvent.book_id == book_id)
        )
    ) == 0


@pytest.mark.asyncio
async def test_reprocess_uploaded_manuscript_success(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-uploaded-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, Chapter
    from app.models.user import ProcessingUsageEvent

    dispatched: list = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    book = Book(
        user_id=user_id,
        title="Regular Book",
        format="txt",
        s3_key="regular.txt",
        status="ready",
        is_editor_project=False,
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id, 1, "Uploaded manuscript chapter content.")
    await _add_chapter(db, book.id, 2, "A second uploaded manuscript chapter.")

    url = f"/api/v1/books/{book.id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_upload_charge": True, "preview_fingerprint": fingerprint},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["upload_charge_consumed"] is False
    assert body["charge_kind"] is None
    assert body["processed_words_reserved"] == 9
    assert body["chapters_queued"] == 2
    executions = await _chapter_executions(db, book.id)
    assert len(executions) == 2
    assert all(execution.rebuild_run_id for execution in executions)
    usage_events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent)
                .where(ProcessingUsageEvent.book_id == book.id)
                .order_by(ProcessingUsageEvent.source_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(usage_events) == 2
    assert all(event.usage_kind == "manual_reprocess" for event in usage_events)
    assert sum(event.word_count for event in usage_events) == 9
    assert all(event.status == "reserved" for event in usage_events)
    assert all(event.task_id for event in usage_events)
    assert {execution.arguments_json["processing_reservation_id"] for execution in executions} == {
        str(event.id) for event in usage_events
    }
    assert all(execution.arguments_json["manual_reprocess"] is True for execution in executions)
    from app.services.task_execution_service import (
        complete_task_execution,
        fail_task_execution,
    )

    for execution in executions:
        chapter = await db.get(Chapter, execution.chapter_id)
        chapter.processed = True
    executions[0].status = "running"
    executions[1].status = "running"
    await db.commit()
    await complete_task_execution(db, str(executions[0].id))
    await fail_task_execution(
        db,
        str(executions[1].id),
        error=RuntimeError("terminal chapter failure"),
        terminal=True,
        category="processing",
    )
    for event in usage_events:
        await db.refresh(event)
    settled_statuses = {event.status for event in usage_events}
    assert settled_statuses == {"consumed", "released"}
    from app.models.user import User
    from app.utils.billing_utils import calculate_upload_usage_summary

    usage = await calculate_upload_usage_summary(db, await db.get(User, user_id))
    assert usage.manuscript_uploads == 1


@pytest.mark.asyncio
async def test_successful_reprocess_consumes_exact_manuscript_words_once(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-settle-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, Chapter
    from app.models.user import ProcessingUsageEvent
    from app.services.task_execution_service import complete_task_execution

    book = Book(
        user_id=user_id,
        title="Settled Manuscript",
        format="txt",
        s3_key="settled-manuscript.txt",
        status="ready",
        is_editor_project=False,
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id, 1, "one two three four")
    await _add_chapter(db, book.id, 2, "five six seven")

    url = f"/api/v1/books/{book.id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_processing_words": True, "preview_fingerprint": fingerprint},
    )

    assert response.status_code == 200
    assert response.json()["processed_words_reserved"] == 7
    executions = await _chapter_executions(db, book.id)
    assert len(executions) == 2
    for execution in executions:
        chapter = await db.get(Chapter, execution.chapter_id)
        chapter.processed = True
        execution.status = "running"
    await db.commit()
    for execution in executions:
        await complete_task_execution(db, str(execution.id))
    await complete_task_execution(db, str(executions[0].id))

    usage_events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent).where(
                    ProcessingUsageEvent.book_id == book.id,
                    ProcessingUsageEvent.usage_kind == "manual_reprocess",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(usage_events) == 2
    assert all(event.status == "consumed" for event in usage_events)
    assert sum(event.word_count for event in usage_events) == 7


@pytest.mark.asyncio
async def test_reprocess_empty_manuscript(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-empty-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    book_id = await _create_editor_project(client, headers)

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 400
    assert "chapter" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_reprocess_duplicate_run(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-dup-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book_id = uuid.uuid4()

    async def _fake_prepare_rebuild(db, book, **_kwargs):
        book.status = "processing"
        ws = dict(book.writer_workspace) if isinstance(book.writer_workspace, dict) else {}
        ws["processing"] = {"rebuild_run_id": "fake-run-id", "status": "processing"}
        book.writer_workspace = ws
        await db.commit()
        return "fake-run-id"

    monkeypatch.setattr(
        "app.services.editor_project_service.prepare_rebuild",
        _fake_prepare_rebuild,
    )

    book = Book(
        id=book_id,
        user_id=user_id,
        title="Dup Run",
        format="manual",
        s3_key="dup.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    await _add_chapter(db, book_id)

    url = f"/api/v1/books/{book_id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_upload_charge": True, "preview_fingerprint": fingerprint},
    )
    assert response.status_code == 200

    response2 = await client.post(
        url,
        headers=headers,
        json={"confirm_upload_charge": True, "preview_fingerprint": fingerprint},
    )
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_duplicate_reprocess_requests_reserve_only_one_run(db, monkeypatch):
    from app.models.book import Book
    from app.models.user import ProcessingUsageEvent, User
    from app.schemas.books import ManuscriptReprocessBody
    from app.services.manuscript_reprocess_service import (
        _build_manual_reprocess_preflight,
        _load_manual_reprocess_state,
        start_manual_manuscript_reprocess,
    )

    user = User(
        email=f"repr-race-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"reprrace{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Concurrent Reprocess",
        format="manual",
        s3_key="concurrent-reprocess.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id, 1, "one two three")
    await _add_chapter(db, book.id, 2, "four five")
    state = await _load_manual_reprocess_state(db, book)
    await db.commit()
    preflight = await _build_manual_reprocess_preflight(book.id, state)
    assert preflight.ready is True
    assert preflight.preview_fingerprint

    def _fake_apply_async(*_args, **_kwargs):
        return type("Result", (), {"id": uuid.uuid4().hex})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def invoke() -> int:
        async with sessions() as session:
            local_user = await session.get(User, user.id)
            try:
                await start_manual_manuscript_reprocess(
                    db=session,
                    current_user=local_user,
                    book_id=book.id,
                    body=ManuscriptReprocessBody(
                        confirm_processing_words=True,
                        preview_fingerprint=preflight.preview_fingerprint,
                    ),
                )
                return 200
            except HTTPException as exc:
                await session.rollback()
                return exc.status_code

    statuses = await asyncio.gather(invoke(), invoke())

    assert sorted(statuses) == [200, 409]
    usage_events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent).where(
                    ProcessingUsageEvent.book_id == book.id,
                    ProcessingUsageEvent.usage_kind == "manual_reprocess",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(usage_events) == 2
    assert sum(event.word_count for event in usage_events) == 5


@pytest.mark.asyncio
async def test_reprocess_success(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-ok-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, BookUploadCharge

    dispatched: list = []

    class _FakeResult:
        def __init__(self, tid):
            self.id = tid

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return _FakeResult(f"task-{len(dispatched)}")

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    book_id = uuid.uuid4()
    book = Book(
        id=book_id,
        user_id=user_id,
        title="Reprocess OK",
        format="manual",
        s3_key="reprocess.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    await _add_chapter(db, book_id, 1, "First chapter content here.")
    await _add_chapter(db, book_id, 2, "Second chapter content too.")

    url = f"/api/v1/books/{book_id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_upload_charge": True, "preview_fingerprint": fingerprint},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    assert body["chapters_queued"] >= 1
    assert body["total_words"] > 0
    assert len(await _chapter_executions(db, book_id)) >= 1

    book_after = await db.get(Book, book_id)
    assert book_after.status == "processing"
    ws = book_after.writer_workspace or {}
    assert ws.get("processing", {}).get("rebuild_run_id") is not None
    from app.models.user import ProcessingUsageEvent

    usage_events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent).where(ProcessingUsageEvent.book_id == book_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(usage_events) == 2
    assert all(event.usage_kind == "manual_reprocess" for event in usage_events)
    assert all(event.status == "reserved" for event in usage_events)


@pytest.mark.asyncio
async def test_reprocess_charge_failure_invalidates_queued_rebuild(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-charge-fail-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, BookUploadCharge
    from app.services.editor_project_service import get_rebuild_run_id

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    async def _fail_dispatch(*_args, **_kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )
    monkeypatch.setattr(
        "app.services.editor_project_service.dispatch_rebuild",
        _fail_dispatch,
    )

    book = Book(
        user_id=user_id,
        title="Charge Failure",
        format="manual",
        s3_key="charge-failure.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id)

    url = f"/api/v1/books/{book.id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_upload_charge": True, "preview_fingerprint": fingerprint},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Something went wrong. Please try again."
    assert len(await _chapter_executions(db, book.id)) == 0
    await db.refresh(book)
    # Dispatch failure keeps the last active generation usable.
    assert book.status == "ready"
    assert get_rebuild_run_id(book) is None
    from app.models.user import ProcessingUsageEvent

    usage_events = list(
        (
            await db.execute(
                select(ProcessingUsageEvent).where(ProcessingUsageEvent.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(usage_events) == 1
    assert usage_events[0].status == "released"
    charge_count = len(
        (await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id)))
        .scalars()
        .all()
    )
    assert charge_count == 0


@pytest.mark.asyncio
async def test_reprocess_requires_ownership(client, db, monkeypatch):
    headers1, user1 = await _register_author(
        client, db, f"repr-own1-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    headers2, user2 = await _register_author(
        client, db, f"repr-own2-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book = Book(
        user_id=user1,
        title="Owner Book",
        format="manual",
        s3_key="owner.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers2,
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reprocess_requires_author_access(client, db, monkeypatch):
    headers1, user1 = await _register_author(
        client, db, f"repr-auth-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book

    book = Book(
        user_id=user1,
        title="Auth Test Book",
        format="manual",
        s3_key="auth.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.require_author_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(403, "Requires Author plan")
        ),
    )

    response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/reprocess",
        headers=headers1,
        json={"confirm_upload_charge": True},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reprocess_rejects_when_upload_capacity_is_exhausted(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, db, f"repr-quota-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from fastapi import HTTPException

    from app.models.book import Book, BookUploadCharge

    book = Book(
        user_id=user_id,
        title="Quota Test",
        format="txt",
        s3_key="quota.txt",
        status="ready",
    )
    db.add(book)
    await db.commit()
    await _add_chapter(db, book.id)

    async def _reject_processing_allowance(*_args, **_kwargs):
        raise HTTPException(403, "Author tier includes 15 uploads. You have 0 remaining.")

    monkeypatch.setattr(
        "app.services.manuscript_reprocess_service.reserve_processing_word_batch",
        _reject_processing_allowance,
    )

    url = f"/api/v1/books/{book.id}/manuscript/reprocess"
    fingerprint = await _ready_reprocess_fingerprint(client, url, headers)
    response = await client.post(
        url,
        headers=headers,
        json={"confirm_upload_charge": True, "preview_fingerprint": fingerprint},
    )

    assert response.status_code == 403
    assert "0 remaining" in response.json()["detail"]
    charge_count = len(
        (await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id)))
        .scalars()
        .all()
    )
    assert charge_count == 0


@pytest.mark.asyncio
async def test_editor_project_import_auto_reprocesses_once_at_word_threshold_without_charge(
    client, db, monkeypatch
):
    headers, user_id = await _register_author(
        client, db, f"repr-auto-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = await _create_editor_project(client, headers, title="Auto Draft")

    from app.models.book import Book, BookUploadCharge, Chapter

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/import",
        headers=headers,
        data={
            "text": " ".join(["threshold"] * 2000),
            "title": "Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert response.status_code == 200
    book = await db.get(Book, uuid.UUID(book_id))
    chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))
    ).scalar_one()
    charge_count = len(
        (await db.execute(select(BookUploadCharge).where(BookUploadCharge.book_id == book.id)))
        .scalars()
        .all()
    )

    assert chapter.word_count >= 2000
    assert book.status == "processing"
    assert book.writer_workspace["reprocess"]["last_reason"] == "auto_first_2000_words"
    assert book.writer_workspace["reprocess"]["auto_first_threshold_words"] == 2000
    executions = await _chapter_executions(db, book.id)
    assert len(executions) == 1
    assert executions[0].rebuild_run_id
    assert charge_count == 0


@pytest.mark.asyncio
async def test_manual_reprocess_mode_marks_saved_chapter_pending_without_queue(
    client, db, monkeypatch
):
    headers, user_id = await _register_author(
        client, db, f"repr-manual-mode-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = await _create_editor_project(client, headers, title="Manual Mode Draft")

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    workspace_response = await client.put(
        f"/api/v1/books/{book_id}/writer-workspace",
        headers=headers,
        json={"reprocess": {"auto_reprocess_enabled": False}},
    )
    assert workspace_response.status_code == 200

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/import",
        headers=headers,
        data={
            "text": " ".join(["manual"] * 2000),
            "title": "Manual Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert response.status_code == 200
    assert dispatched == []
    workspace = (
        await client.get(f"/api/v1/books/{book_id}/writer-workspace", headers=headers)
    ).json()
    assert workspace["reprocess"]["auto_reprocess_enabled"] is False
    assert workspace["reprocess"]["pending_chapters"] == [1]
    assert workspace["reprocess"]["last_mode_changed_at"]


@pytest.mark.asyncio
async def test_manual_chapter_reprocess_queues_one_chapter_without_upload_charge(
    client, db, monkeypatch
):
    from app.models.book import Book, BookUploadCharge, Chapter
    from app.models.intelligence import BookChunk, ChapterSummary

    headers, user_id = await _register_author(
        client, db, f"repr-one-chapter-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )
    book_id = await _create_editor_project(client, headers, title="One Chapter Draft")

    import_response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/import",
        headers=headers,
        data={
            "text": "Chapter text that needs a targeted reprocess.",
            "title": "Opening",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )
    assert import_response.status_code == 200
    _STORED_TEST_CHAPTERS[(uuid.UUID(book_id), 1)] = "Chapter text that needs a targeted reprocess."
    await client.put(
        f"/api/v1/books/{book_id}/writer-workspace",
        headers=headers,
        json={"reprocess": {"auto_reprocess_enabled": False, "pending_chapters": [1]}},
    )

    chapter = (
        await db.execute(
            select(Chapter).where(
                Chapter.book_id == uuid.UUID(book_id),
                Chapter.number == 1,
            )
        )
    ).scalar_one()
    db.add_all(
        [
            BookChunk(
                book_id=uuid.UUID(book_id),
                chapter_id=chapter.id,
                chunk_index=0,
                text="Last-known-good extracted text.",
                token_count=5,
            ),
            ChapterSummary(
                chapter_id=chapter.id,
                mode="detailed",
                content="Last-known-good summary.",
            ),
        ]
    )
    await db.commit()

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": f"task-{len(dispatched)}"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    response = await client.post(
        f"/api/v1/books/{book_id}/manuscript/chapters/1/reprocess",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["chapters_queued"] == 1
    assert body["upload_charge_consumed"] is False
    executions = await _chapter_executions(db, uuid.UUID(book_id))
    assert len(executions) == 1
    assert executions[0].chapter_number == 1
    assert executions[0].arguments_json["manual_reprocess"] is True
    book = await db.get(Book, uuid.UUID(book_id))
    assert book.writer_workspace["reprocess"]["pending_chapters"] == []
    remaining_chunk_count = await db.scalar(
        select(func.count(BookChunk.id)).where(BookChunk.chapter_id == chapter.id)
    )
    remaining_summary = await db.scalar(
        select(ChapterSummary.content).where(
            ChapterSummary.chapter_id == chapter.id,
            ChapterSummary.mode == "detailed",
        )
    )
    assert remaining_chunk_count == 1
    assert remaining_summary == "Last-known-good summary."
    charge_count = len(
        (
            await db.execute(
                select(BookUploadCharge).where(BookUploadCharge.book_id == uuid.UUID(book_id))
            )
        )
        .scalars()
        .all()
    )
    assert charge_count == 0

    duplicate = await client.post(
        f"/api/v1/books/{book_id}/manuscript/chapters/1/reprocess",
        headers=headers,
    )
    assert duplicate.status_code == 409

    full_reprocess = await client.post(
        f"/api/v1/books/{book_id}/manuscript/reprocess",
        headers=headers,
        json={"confirm_processing_words": True},
    )
    assert full_reprocess.status_code == 409

    from app.models.user import ProcessingUsageEvent

    reservation_count = await db.scalar(
        select(func.count(ProcessingUsageEvent.id)).where(
            ProcessingUsageEvent.book_id == uuid.UUID(book_id),
            ProcessingUsageEvent.status == "reserved",
        )
    )
    assert reservation_count == 1
