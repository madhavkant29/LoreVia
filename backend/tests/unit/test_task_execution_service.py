import uuid
from types import SimpleNamespace

from sqlalchemy import update

from app.models.book import Book
from app.models.operations import TaskExecution
from app.models.user import ProcessingUsageEvent, User
from app.services.task_execution_service import (
    claim_task_execution,
    complete_task_execution,
    dispatch_pending_analysis_tasks,
    dispatch_pending_embedding_tasks,
    dispatch_pending_extraction_tasks,
    ensure_task_execution,
    fail_task_execution,
    get_or_create_processing_run,
    sanitize_task_arguments,
    task_identity,
)


async def _clear_dispatchable_executions(db, task_name: str) -> None:
    await db.execute(
        update(TaskExecution)
        .where(
            TaskExecution.task_name == task_name,
            TaskExecution.status.in_(("pending_dispatch", "queued", "running")),
        )
        .values(status="succeeded")
    )
    await db.commit()


def test_task_identity_is_stable_and_changes_with_chapter_version():
    run_id = uuid.uuid4()
    book_id = uuid.uuid4()
    kwargs = {
        "task_name": "extraction_tasks.process_chapter",
        "processing_run_id": run_id,
        "book_id": book_id,
        "chapter_number": 2,
        "pipeline_version": "p1",
    }
    first = task_identity(**kwargs, chapter_version_id="v1")
    same = task_identity(**kwargs, chapter_version_id="v1")
    changed = task_identity(**kwargs, chapter_version_id="v2")
    assert first == same
    assert first != changed


def test_task_identity_changes_with_embedding_entity():
    kwargs = {
        "task_name": "embedding_tasks.update_character_embedding",
        "processing_run_id": uuid.uuid4(),
        "book_id": uuid.uuid4(),
    }
    assert task_identity(**kwargs, entity_id="character-1") != task_identity(
        **kwargs, entity_id="character-2"
    )


def test_sanitize_task_arguments_removes_manuscript_content():
    result = sanitize_task_arguments(
        {"book_id": "book", "chapter_number": 3, "chapter_text": "private manuscript"}
    )
    assert result == {"book_id": "book", "chapter_number": 3}


async def _processing_user_and_book(db, suffix: str):
    user = User(
        email=f"task-{suffix}@lorevia.app",
        username=f"task{suffix}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title=f"Task {suffix}",
        format="txt",
        s3_key=f"books/{suffix}.txt",
        status="processing",
    )
    db.add(book)
    await db.flush()
    return user, book


async def test_processing_run_and_task_execution_are_idempotent(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(
        db, user_id=user.id, book_id=book.id, chapters_total=2
    )
    first = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_number": 1},
    )
    duplicate = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_number": 1},
    )
    assert duplicate.id == first.id


async def test_fair_dispatch_selects_one_task_per_waiting_user(db, monkeypatch):
    dispatched: list[tuple[str, str]] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append((args[0], queue))
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async", fake_apply_async
    )
    for suffix in (uuid.uuid4().hex[:8], uuid.uuid4().hex[:8]):
        user, book = await _processing_user_and_book(db, suffix)
        run = await get_or_create_processing_run(
            db, user_id=user.id, book_id=book.id, chapters_total=2
        )
        for chapter_number in (1, 2):
            await ensure_task_execution(
                db,
                task_name="extraction_tasks.process_chapter",
                processing_run=run,
                chapter_number=chapter_number,
                arguments={"book_id": str(book.id), "chapter_number": chapter_number},
            )
    await db.commit()

    count = await dispatch_pending_extraction_tasks(db)

    assert count == 2
    assert len({book_id for book_id, _queue in dispatched}) == 2


async def test_fair_dispatch_never_exceeds_global_worker_capacity(db, monkeypatch):
    dispatched: list[str] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append(task_id)
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async", fake_apply_async
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.EXTRACTION_WORKER_CONCURRENCY", 2
    )
    for index in range(3):
        suffix = uuid.uuid4().hex[:8]
        user, book = await _processing_user_and_book(db, suffix)
        run = await get_or_create_processing_run(
            db, user_id=user.id, book_id=book.id, chapters_total=1
        )
        execution = await ensure_task_execution(
            db,
            task_name="extraction_tasks.process_chapter",
            processing_run=run,
            chapter_number=1,
            arguments={"book_id": str(book.id), "chapter_number": 1},
        )
        if index == 0:
            execution.status = "queued"
    await db.commit()

    count = await dispatch_pending_extraction_tasks(db)

    assert count == 1
    assert len(dispatched) == 1


async def test_completed_chapter_does_not_clear_later_allowance_pause(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(
        db, user_id=user.id, book_id=book.id, chapters_total=2
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_number": 1},
    )
    execution.status = "running"
    run.status = "paused"
    run.pause_reason = "monthly_processed_words"
    run.resume_blockers = [{"kind": "monthly_processed_words"}]
    run.next_chapter_number = 2
    await db.commit()

    await complete_task_execution(db, str(execution.id))
    await db.refresh(run)

    assert run.status == "paused"
    assert run.pause_reason == "monthly_processed_words"
    assert run.resume_blockers == [{"kind": "monthly_processed_words"}]
    assert run.next_chapter_number == 2


async def test_completed_chapter_does_not_resurrect_terminal_run(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(
        db, user_id=user.id, book_id=book.id, chapters_total=2
    )
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=2,
        arguments={"book_id": str(book.id), "chapter_number": 2},
    )
    execution.status = "running"
    run.status = "failed_terminal"
    await db.commit()

    await complete_task_execution(db, str(execution.id))
    await db.refresh(run)

    assert run.status == "failed_terminal"


async def test_claim_rejects_paused_and_terminal_executions(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    for status in ("paused", "failed_terminal", "dismissed", "succeeded"):
        execution.status = status
        await db.commit()
        assert not await claim_task_execution(db, str(execution.id), str(execution.id))


async def test_dispatch_failure_returns_execution_to_pending(db, monkeypatch):
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    await db.commit()

    def fail_publish(**_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_book_task.apply_async", fail_publish
    )

    assert await dispatch_pending_extraction_tasks(db) == 0
    await db.refresh(execution)
    assert execution.status == "pending_dispatch"
    assert execution.error_category == "dispatch"
    assert execution.celery_task_id is None


async def test_manual_processing_reservation_reconciles_with_terminal_outcome(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    succeeded_reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="chapter_reprocess",
        source_id=uuid.uuid4().hex,
        word_count=100,
        status="reserved",
    )
    db.add(succeeded_reservation)
    await db.flush()
    succeeded = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(succeeded_reservation.id),
        },
        identity_suffix=succeeded_reservation.id,
    )
    succeeded.status = "running"
    await db.commit()

    await complete_task_execution(db, str(succeeded.id))
    await db.refresh(succeeded_reservation)
    assert succeeded_reservation.status == "consumed"

    failed_reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="chapter_reprocess",
        source_id=uuid.uuid4().hex,
        word_count=80,
        status="reserved",
    )
    db.add(failed_reservation)
    await db.flush()
    failed = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=2,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 2,
            "processing_reservation_id": str(failed_reservation.id),
        },
        identity_suffix=failed_reservation.id,
    )
    failed.status = "running"
    await db.commit()

    await fail_task_execution(
        db,
        str(failed.id),
        error=RuntimeError("invalid source"),
        terminal=True,
        category="processing",
    )
    await db.refresh(failed_reservation)
    assert failed_reservation.status == "released"


async def test_analysis_dispatch_respects_configured_capacity(db, monkeypatch):
    dispatched: list[str] = []
    await _clear_dispatchable_executions(db, "analysis_tasks.analyse_chapter")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append(task_id)
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.analysis_tasks.analyse_chapter_task.apply_async", fake_apply_async
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.ANALYSIS_WORKER_CONCURRENCY", 1
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(
        db, user_id=user.id, book_id=book.id, chapters_total=1
    )
    await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={"book_id": str(book.id)},
    )
    await db.commit()

    assert await dispatch_pending_analysis_tasks(db) == 1
    assert len(dispatched) == 1
    assert await dispatch_pending_analysis_tasks(db) == 0


async def test_embedding_dispatch_respects_configured_capacity(db, monkeypatch):
    dispatched: list[str] = []
    await _clear_dispatchable_executions(db, "embedding_tasks.update_character_embedding")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append(task_id)
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.embedding_tasks.update_character_embedding_task.apply_async",
        fake_apply_async,
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.EMBEDDING_WORKER_CONCURRENCY", 1
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    await ensure_task_execution(
        db,
        task_name="embedding_tasks.update_character_embedding",
        processing_run=run,
        arguments={"character_id": str(uuid.uuid4()), "book_id": str(book.id)},
        feature="embeddings",
    )
    await db.commit()

    assert await dispatch_pending_embedding_tasks(db) == 1
    assert len(dispatched) == 1
    assert await dispatch_pending_embedding_tasks(db) == 0
