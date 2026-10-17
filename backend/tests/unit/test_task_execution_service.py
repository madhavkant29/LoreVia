import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import func, select, update

from app.models.book import Book, Chapter
from app.models.operations import BookProcessingRun, TaskDispatchOutbox, TaskExecution
from app.models.user import ProcessingUsageEvent, User
from app.services import task_execution_service
from app.services.task_execution_service import (
    claim_task_execution,
    complete_task_execution,
    dispatch_pending_analysis_tasks,
    dispatch_pending_embedding_tasks,
    dispatch_pending_extraction_tasks,
    enqueue_chapter_repair_execution,
    enqueue_extraction_execution,
    enqueue_extraction_execution_batch,
    ensure_task_execution,
    fail_task_execution,
    get_or_create_processing_run,
    pause_task_execution,
    reconcile_stale_task_dispatch_outbox,
    release_stale_task_leases,
    resume_temporary_capacity_pauses,
    sanitize_task_arguments,
    task_identity,
)


async def _clear_dispatchable_executions(db, task_name: str) -> None:
    await db.execute(
        update(TaskDispatchOutbox)
        .where(TaskDispatchOutbox.task_name == task_name)
        .values(status="cancelled", lease_until=None)
    )
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
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id, chapters_total=2)
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


async def test_processing_run_reuse_requires_matching_rebuild_run_id(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    stale_run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="initial_ingestion",
        chapters_total=1,
    )
    stale_run.status = "paused"
    rebuild_run_id = uuid.uuid4().hex
    await db.commit()

    rebuild_run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        rebuild_run_id=rebuild_run_id,
        chapters_total=2,
    )
    same_rebuild_run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="analysis_recovery",
        rebuild_run_id=rebuild_run_id,
        chapters_total=3,
    )

    assert rebuild_run.id != stale_run.id
    assert rebuild_run.rebuild_run_id == rebuild_run_id
    assert same_rebuild_run.id == rebuild_run.id
    assert same_rebuild_run.chapters_total == 3


async def test_enqueue_links_processing_reservation_before_dispatch(db, monkeypatch):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{uuid.uuid4().hex}:chapter",
        word_count=25,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    observed_task_ids: list[str | None] = []

    async def observe_link(session):
        await session.refresh(reservation)
        observed_task_ids.append(reservation.task_id)
        return 0

    monkeypatch.setattr(
        task_execution_service,
        "dispatch_pending_extraction_tasks",
        observe_link,
    )

    execution = await enqueue_extraction_execution(
        db,
        book_id=book.id,
        user_id=user.id,
        chapter_id=None,
        chapter_number=1,
        chapters_total=1,
        processing_reservation_id=reservation.id,
        run_kind="manual_reprocess",
        identity_suffix=reservation.id,
    )

    assert observed_task_ids == [str(execution.id)]
    await db.refresh(reservation)
    assert reservation.task_id == str(execution.id)


async def test_enqueue_extraction_execution_batch_commits_and_dispatches_once(db, monkeypatch):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    chapters = [
        Chapter(
            book_id=book.id,
            number=1,
            title="One",
            s3_key=f"chapters/{book.id}/1.txt",
            word_count=10,
        ),
        Chapter(
            book_id=book.id,
            number=2,
            title="Two",
            s3_key=f"chapters/{book.id}/2.txt",
            word_count=20,
        ),
    ]
    db.add_all(chapters)
    await db.flush()
    dispatch_calls = 0

    async def observe_dispatch(session):
        nonlocal dispatch_calls
        dispatch_calls += 1
        result = await session.execute(
            select(TaskExecution).where(TaskExecution.book_id == book.id)
        )
        return len(result.scalars().all())

    monkeypatch.setattr(
        task_execution_service,
        "dispatch_pending_extraction_tasks",
        observe_dispatch,
    )

    executions = await enqueue_extraction_execution_batch(
        db,
        book_id=book.id,
        user_id=user.id,
        chapters=[(chapter.id, chapter.number) for chapter in chapters],
        chapters_total=len(chapters),
        run_kind="manuscript_import",
    )

    assert dispatch_calls == 1
    assert [execution.chapter_number for execution in executions] == [1, 2]
    assert len({execution.processing_run_id for execution in executions}) == 1
    run = await db.get(BookProcessingRun, executions[0].processing_run_id)
    assert run is not None
    assert run.run_kind == "manuscript_import"
    assert run.chapters_total == 2


async def test_terminal_failure_uses_execution_rebuild_id_for_settlement(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    rebuild_run_id = uuid.uuid4().hex
    book.writer_workspace = {
        "processing": {"status": "processing", "rebuild_run_id": rebuild_run_id},
    }
    mismatched_run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="initial_ingestion",
        chapters_total=1,
    )
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{rebuild_run_id}:chapter-1",
        word_count=25,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=mismatched_run,
        chapter_number=1,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
            "manual_reprocess": True,
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    execution.status = "running"
    await db.commit()

    await fail_task_execution(
        db,
        str(execution.id),
        error=RuntimeError("chapter failed"),
        terminal=True,
        category="processing",
    )

    await db.refresh(book)
    await db.refresh(mismatched_run)
    await db.refresh(reservation)
    assert reservation.status == "released"
    assert book.writer_workspace["processing"].get("rebuild_run_id") is None
    assert mismatched_run.status == "failed_terminal"


async def test_fair_dispatch_selects_one_task_per_waiting_user(db, monkeypatch):
    dispatched: list[tuple[str, str]] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append((args[0], queue))
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        fake_apply_async,
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


async def test_extraction_dispatch_serializes_chapters_within_one_book(db, monkeypatch):
    dispatched: list[int] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append(int(args[1]))
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        fake_apply_async,
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.EXTRACTION_WORKER_CONCURRENCY", 4
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id, chapters_total=3)
    for chapter_number in (1, 2, 3):
        await ensure_task_execution(
            db,
            task_name="extraction_tasks.process_chapter",
            processing_run=run,
            chapter_number=chapter_number,
            arguments={"book_id": str(book.id), "chapter_number": chapter_number},
        )
    await db.commit()

    count = await dispatch_pending_extraction_tasks(db)

    assert count == 1
    assert dispatched == [1]


async def test_extraction_dispatch_uses_chapter_order_even_when_enqueued_out_of_order(
    db, monkeypatch
):
    dispatched: list[int] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append(int(args[1]))
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        fake_apply_async,
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.EXTRACTION_WORKER_CONCURRENCY", 4
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id, chapters_total=3)
    for chapter_number in (3, 1, 2):
        await ensure_task_execution(
            db,
            task_name="extraction_tasks.process_chapter",
            processing_run=run,
            chapter_number=chapter_number,
            arguments={"book_id": str(book.id), "chapter_number": chapter_number},
        )
    await db.commit()

    assert await dispatch_pending_extraction_tasks(db) == 1
    assert dispatched == [1]


async def test_empty_extraction_dispatch_releases_advisory_transaction(db):
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    assert await dispatch_pending_extraction_tasks(db) == 0
    assert db.in_transaction() is False


async def test_fair_dispatch_never_exceeds_global_worker_capacity(db, monkeypatch):
    dispatched: list[str] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append(task_id)
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        fake_apply_async,
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
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id, chapters_total=2)
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
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id, chapters_total=2)
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


async def test_claim_rejects_duplicate_delivery_with_same_celery_task_id(db, monkeypatch):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    execution.status = "queued"
    await db.commit()

    async def cache_lease_created(*_args, **_kwargs):
        return True

    monkeypatch.setattr(task_execution_service, "cache_set_if_absent", cache_lease_created)

    task_id = str(execution.id)
    assert await claim_task_execution(db, str(execution.id), task_id) is True
    assert await claim_task_execution(db, str(execution.id), task_id) is False
    await db.refresh(execution)
    assert execution.attempt_count == 1


async def test_claim_succeeds_when_redis_lease_marker_is_unavailable(db, monkeypatch):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    execution.status = "queued"
    await db.commit()

    async def redis_unavailable(*_args, **_kwargs):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(task_execution_service, "cache_set_if_absent", redis_unavailable)

    assert await claim_task_execution(db, str(execution.id), str(execution.id)) is True
    await db.refresh(execution)
    assert execution.status == "running"


async def test_completion_survives_redis_cleanup_failure_and_late_failure(db, monkeypatch):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    execution.status = "running"
    await db.commit()

    async def redis_unavailable(*_args, **_kwargs):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(task_execution_service, "cache_del", redis_unavailable)

    await complete_task_execution(db, str(execution.id))
    await fail_task_execution(
        db,
        str(execution.id),
        error=RuntimeError("late wrapper failure"),
        terminal=False,
    )

    await db.refresh(execution)
    assert execution.status == "succeeded"
    assert execution.error_detail is None


async def test_temporary_capacity_pause_returns_to_durable_dispatch_after_cooldown(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_number=2,
        arguments={"book_id": str(book.id), "chapter_id": str(uuid.uuid4())},
    )
    execution.status = "paused"
    execution.error_category = "llm_capacity"
    execution.error_detail = "temporary capacity"
    execution.attempt_count = 1
    execution.updated_at = datetime.now(UTC) - timedelta(minutes=2)
    run.status = "paused"
    run.pause_reason = "llm_capacity"
    run.resume_blockers = [{"kind": "llm_capacity"}]
    run.paused_at = datetime.now(UTC) - timedelta(minutes=2)
    await db.commit()

    resumed = await resume_temporary_capacity_pauses(db, min_age_seconds=60)

    assert resumed == 1
    await db.refresh(execution)
    await db.refresh(run)
    assert execution.status == "pending_dispatch"
    assert execution.error_category is None
    assert run.status == "queued"
    assert run.resume_blockers == []


async def test_usage_limit_pause_is_not_automatically_resumed(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_number=2,
        arguments={"book_id": str(book.id), "chapter_id": str(uuid.uuid4())},
    )
    execution.status = "paused"
    execution.error_category = "llm_usage_limit"
    execution.updated_at = datetime.now(UTC) - timedelta(minutes=2)
    await db.commit()

    assert await resume_temporary_capacity_pauses(db, min_age_seconds=60) == 0
    await db.refresh(execution)
    assert execution.status == "paused"


async def test_token_limit_pause_resumes_at_scheduled_time_without_new_reservation(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{uuid.uuid4().hex}:chapter",
        word_count=120,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=2,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 2,
            "processing_reservation_id": str(reservation.id),
            "manual_reprocess": True,
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    execution.status = "running"
    execution.attempt_count = 1
    resume_at = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=5)
    blocker = {
        "kind": "llm_tokens",
        "detail": "Token limit reached.",
        "next_resume_at": resume_at.isoformat(),
        "auto_resume": True,
    }
    await db.commit()

    await pause_task_execution(
        db,
        str(execution.id),
        reason="llm_token_limit",
        blocker=blocker,
    )
    await db.refresh(book)
    assert book.writer_workspace["processing"]["auto_resume"] is True
    assert book.writer_workspace["processing"]["resume_available"] is False
    assert book.writer_workspace["processing"]["next_resume_at"] == resume_at.isoformat()

    assert await resume_temporary_capacity_pauses(db, now=resume_at - timedelta(seconds=1)) == 0
    assert await resume_temporary_capacity_pauses(db, now=resume_at) == 1

    await db.refresh(execution)
    await db.refresh(reservation)
    await db.refresh(book)
    assert execution.status == "pending_dispatch"
    assert reservation.status == "reserved"
    assert book.writer_workspace["processing"]["auto_resume"] is False
    reservation_count = await db.scalar(
        select(func.count(ProcessingUsageEvent.id)).where(
            ProcessingUsageEvent.source_id == reservation.source_id
        )
    )
    assert reservation_count == 1


async def test_late_token_pause_cannot_resurrect_cancelled_rebuild(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    stale_rebuild_run_id = uuid.uuid4().hex
    book.status = "ready"
    book.writer_workspace = {"processing": {"status": "ready", "stage": "ready"}}
    run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        rebuild_run_id=stale_rebuild_run_id,
        chapters_total=1,
    )
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{stale_rebuild_run_id}:chapter-1",
        word_count=50,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=1,
        rebuild_run_id=stale_rebuild_run_id,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
            "manual_reprocess": True,
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    execution.status = "running"
    await db.commit()

    await pause_task_execution(
        db,
        str(execution.id),
        reason="llm_token_limit",
        blocker={
            "kind": "llm_tokens",
            "auto_resume": True,
            "next_resume_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )

    await db.refresh(execution)
    await db.refresh(reservation)
    await db.refresh(book)
    assert execution.status == "dismissed"
    assert reservation.status == "released"
    assert book.status == "ready"
    assert book.writer_workspace["processing"]["stage"] == "ready"


async def test_stale_chapter_completion_releases_reservation_without_charging(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    rebuild_run_id = uuid.uuid4().hex
    book.status = "ready"
    book.writer_workspace = {"processing": {"status": "ready", "stage": "ready"}}
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Processed before cancellation",
        s3_key=f"chapters/{book.id}/1.txt",
        word_count=20,
        processed=True,
    )
    db.add(chapter)
    run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        rebuild_run_id=rebuild_run_id,
        chapters_total=1,
    )
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{rebuild_run_id}:chapter-1",
        word_count=20,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_id=chapter.id,
        chapter_number=1,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    execution.status = "running"
    await db.commit()

    await complete_task_execution(db, str(execution.id))

    await db.refresh(execution)
    await db.refresh(reservation)
    assert execution.status == "dismissed"
    assert execution.error_category == "stale_rebuild"
    assert reservation.status == "released"


async def test_incomplete_chapter_completion_fails_rebuild_and_releases_reservation(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    rebuild_run_id = uuid.uuid4().hex
    book.status = "processing"
    book.writer_workspace = {
        "processing": {"status": "processing", "rebuild_run_id": rebuild_run_id}
    }
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Incomplete extraction",
        s3_key=f"chapters/{book.id}/1.txt",
        word_count=20,
        processed=False,
    )
    db.add(chapter)
    run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        rebuild_run_id=rebuild_run_id,
        chapters_total=1,
    )
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{rebuild_run_id}:chapter-1",
        word_count=20,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_id=chapter.id,
        chapter_number=1,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    execution.status = "running"
    await db.commit()

    await complete_task_execution(db, str(execution.id))

    await db.refresh(execution)
    await db.refresh(reservation)
    await db.refresh(book)
    assert execution.status == "failed_terminal"
    assert execution.error_category == "extraction_incomplete"
    assert reservation.status == "released"
    assert book.writer_workspace["processing"].get("rebuild_run_id") is None


async def test_budget_pause_stays_paused_until_reset_and_provider_recovers(db, monkeypatch):
    _user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=book.user_id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_id": str(uuid.uuid4())},
    )
    execution.status = "running"
    execution.attempt_count = 1
    reset_at = datetime.now(UTC).replace(microsecond=0) + timedelta(days=2)
    await db.commit()
    await pause_task_execution(
        db,
        str(execution.id),
        reason="llm_budget",
        blocker={
            "kind": "llm_budget",
            "detail": "Monthly AI capacity reached.",
            "next_resume_at": reset_at.isoformat(),
            "auto_resume": True,
        },
    )

    circuit_open = [True]

    async def _circuit_status(**_kwargs):
        return circuit_open[0]

    monkeypatch.setattr(
        "app.services.llm_circuit_breaker_service.provider_circuit_is_open",
        _circuit_status,
    )

    assert await resume_temporary_capacity_pauses(db, now=reset_at - timedelta(seconds=1)) == 0
    await db.refresh(execution)
    assert execution.status == "paused"

    assert await resume_temporary_capacity_pauses(db, now=reset_at) == 0
    circuit_open[0] = False
    assert await resume_temporary_capacity_pauses(db, now=reset_at) == 1
    await db.refresh(execution)
    assert execution.status == "pending_dispatch"


async def test_capacity_resume_checks_provider_circuit(db, monkeypatch):
    _user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=book.user_id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_id": str(uuid.uuid4())},
    )
    execution.status = "paused"
    execution.error_category = "llm_capacity"
    execution.error_detail = "temporary capacity"
    execution.attempt_count = 1
    execution.updated_at = datetime.now(UTC) - timedelta(minutes=10)
    await db.commit()

    async def _open(**_kwargs):
        return True

    monkeypatch.setattr("app.services.llm_circuit_breaker_service.provider_circuit_is_open", _open)

    assert await resume_temporary_capacity_pauses(db) == 0
    await db.refresh(execution)
    assert execution.status == "paused"


async def test_capacity_resume_is_fair_at_one_execution_per_user(db):
    await db.execute(
        update(TaskExecution)
        .where(
            TaskExecution.status == "paused",
            TaskExecution.error_category == "llm_capacity",
        )
        .values(status="succeeded")
    )
    await db.commit()
    first_user, first_book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    second_user, second_book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    rows = []
    for user, book, chapters in (
        (first_user, first_book, (1, 2)),
        (second_user, second_book, (1,)),
    ):
        run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
        for chapter_number in chapters:
            execution = await ensure_task_execution(
                db,
                task_name="analysis_tasks.analyse_chapter",
                processing_run=run,
                chapter_number=chapter_number,
                arguments={
                    "book_id": str(book.id),
                    "chapter_id": str(uuid.uuid4()),
                },
            )
            execution.status = "paused"
            execution.error_category = "llm_capacity"
            execution.error_detail = "temporary capacity"
            execution.attempt_count = 1
            execution.updated_at = datetime.now(UTC) - timedelta(minutes=10)
            rows.append(execution)
    await db.commit()

    assert await resume_temporary_capacity_pauses(db, limit=20) == 2
    statuses_by_user: dict[uuid.UUID, list[str]] = {}
    for execution in rows:
        await db.refresh(execution)
        statuses_by_user.setdefault(execution.user_id, []).append(execution.status)
    assert sorted(statuses_by_user[first_user.id]) == ["paused", "pending_dispatch"]
    assert statuses_by_user[second_user.id] == ["pending_dispatch"]


async def test_dispatch_failure_returns_execution_to_pending(db, monkeypatch):
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")
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


async def test_dispatch_creates_published_outbox_with_sanitized_payload(db, monkeypatch):
    dispatched: list[dict] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append({"args": args, "kwargs": kwargs, "queue": queue, "task_id": task_id})
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        fake_apply_async,
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=7,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 7,
            "chapter_text": "private manuscript content",
        },
    )
    await db.commit()

    assert await dispatch_pending_extraction_tasks(db) == 1

    outbox = (
        await db.execute(
            select(TaskDispatchOutbox).where(TaskDispatchOutbox.execution_id == execution.id)
        )
    ).scalar_one()
    assert outbox.status == "published"
    assert outbox.published_at is not None
    assert outbox.payload_json["execution_id"] == str(execution.id)
    assert outbox.payload_json["book_id"] == str(book.id)
    assert "chapter_text" not in outbox.payload_json
    assert dispatched[0]["task_id"] == str(execution.id)


async def test_claim_marks_execution_terminal_when_attempt_budget_is_exhausted(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    execution.status = "queued"
    execution.attempt_count = 3
    execution.max_attempts = 3
    await db.commit()

    assert not await claim_task_execution(db, str(execution.id), str(execution.id))
    await db.refresh(execution)
    assert execution.status == "failed_terminal"
    assert execution.error_category == "attempt_exhausted"


async def test_attempt_exhaustion_releases_entire_rebuild_and_dismisses_stale_pauses(
    db,
):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    rebuild_run_id = uuid.uuid4().hex
    book.writer_workspace = {
        "reprocess": {},
        "processing": {
            "status": "processing",
            "rebuild_run_id": rebuild_run_id,
        },
    }
    run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        rebuild_run_id=rebuild_run_id,
        chapters_total=2,
    )
    reservations = [
        ProcessingUsageEvent(
            user_id=user.id,
            book_id=book.id,
            usage_kind="manual_reprocess",
            source_id=f"manual:{rebuild_run_id}:chapter-{number}",
            word_count=50,
            status="reserved",
        )
        for number in (1, 2)
    ]
    db.add_all(reservations)
    await db.flush()
    executions = []
    for number, reservation in enumerate(reservations, start=1):
        execution = await ensure_task_execution(
            db,
            task_name="extraction_tasks.process_chapter",
            processing_run=run,
            chapter_number=number,
            rebuild_run_id=rebuild_run_id,
            arguments={
                "book_id": str(book.id),
                "chapter_number": number,
                "processing_reservation_id": str(reservation.id),
                "manual_reprocess": True,
            },
            identity_suffix=reservation.id,
        )
        reservation.task_id = str(execution.id)
        executions.append(execution)
    executions[0].status = "queued"
    executions[0].attempt_count = executions[0].max_attempts
    executions[1].status = "paused"
    executions[1].error_category = "llm_token_limit"
    executions[
        1
    ].error_detail = (
        '{"kind":"llm_tokens","auto_resume":true,"next_resume_at":"2026-01-01T00:00:00+00:00"}'
    )
    await db.commit()

    assert not await claim_task_execution(db, str(executions[0].id), str(executions[0].id))
    for reservation in reservations:
        await db.refresh(reservation)
        assert reservation.status == "released"
    await db.refresh(book)
    await db.refresh(run)
    assert book.writer_workspace["processing"].get("rebuild_run_id") is None
    assert run.status == "failed_terminal"

    assert (
        await resume_temporary_capacity_pauses(
            db,
            now=datetime(2026, 1, 2, tzinfo=UTC),
        )
        == 0
    )
    await db.refresh(executions[1])
    await db.refresh(run)
    assert executions[1].status == "dismissed"
    assert run.status == "failed_terminal"


async def test_stale_lease_attempt_exhaustion_releases_rebuild_reservation(db):
    await db.execute(
        update(TaskExecution)
        .where(TaskExecution.status == "running")
        .values(status="succeeded", locked_until=None)
    )
    await db.commit()
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    rebuild_run_id = uuid.uuid4().hex
    book.writer_workspace = {
        "processing": {"status": "processing", "rebuild_run_id": rebuild_run_id}
    }
    run = await get_or_create_processing_run(
        db,
        user_id=user.id,
        book_id=book.id,
        run_kind="manual_reprocess",
        rebuild_run_id=rebuild_run_id,
        chapters_total=1,
    )
    reservation = ProcessingUsageEvent(
        user_id=user.id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id=f"manual:{rebuild_run_id}:chapter-1",
        word_count=50,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_chapter",
        processing_run=run,
        chapter_number=1,
        rebuild_run_id=rebuild_run_id,
        arguments={
            "book_id": str(book.id),
            "chapter_number": 1,
            "processing_reservation_id": str(reservation.id),
            "manual_reprocess": True,
        },
        identity_suffix=reservation.id,
    )
    reservation.task_id = str(execution.id)
    execution.status = "running"
    execution.attempt_count = execution.max_attempts
    execution.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    assert await release_stale_task_leases(db) == 1
    await db.commit()
    await db.refresh(execution)
    await db.refresh(reservation)
    await db.refresh(book)
    assert execution.status == "failed_terminal"
    assert reservation.status == "released"
    assert book.writer_workspace["processing"].get("rebuild_run_id") is None


async def test_reconcile_stale_outbox_recovers_unconfirmed_publish(db):
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id)
    execution = await ensure_task_execution(
        db,
        task_name="extraction_tasks.process_book",
        processing_run=run,
        arguments={"book_id": str(book.id)},
    )
    execution.status = "queued"
    outbox = TaskDispatchOutbox(
        execution_id=execution.id,
        task_name=execution.task_name,
        queue="extraction",
        payload_json={"execution_id": str(execution.id), "book_id": str(book.id)},
        status="publishing",
        attempts=1,
        available_at=datetime.now(UTC) - timedelta(minutes=10),
        lease_until=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.add(outbox)
    await db.commit()

    assert await reconcile_stale_task_dispatch_outbox(db) == 1
    await db.flush()
    await db.refresh(outbox)
    assert outbox.status == "pending"
    assert outbox.lease_until is None


async def test_chapter_repair_execution_uses_durable_dispatch(db, monkeypatch):
    dispatched: list[dict] = []
    await _clear_dispatchable_executions(db, "extraction_tasks.process_book")
    await _clear_dispatchable_executions(db, "extraction_tasks.process_chapter")
    await _clear_dispatchable_executions(db, "extraction_tasks.repair_chapter_payload")

    def fake_apply_async(*, args, kwargs, queue, task_id):
        dispatched.append({"args": args, "kwargs": kwargs, "queue": queue, "task_id": task_id})
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.repair_chapter_payload_task.apply_async",
        fake_apply_async,
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    execution = await enqueue_chapter_repair_execution(
        db,
        book_id=book.id,
        user_id=user.id,
        chapter_id=None,
        chapter_number=3,
        chapters_total=5,
        reason="source_integrity_mismatch",
    )

    await db.refresh(execution)
    assert execution.task_name == "extraction_tasks.repair_chapter_payload"
    assert execution.status == "queued"
    assert dispatched == [
        {
            "args": [str(book.id), 3],
            "kwargs": {"execution_id": str(execution.id)},
            "queue": "extraction",
            "task_id": str(execution.id),
        }
    ]
    execution.status = "running"
    await db.commit()

    await complete_task_execution(db, str(execution.id))
    run = await db.get(BookProcessingRun, execution.processing_run_id)
    assert run.status == "succeeded"
    assert run.chapters_completed == 1


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
        "app.workers.tasks.analysis_tasks.analyse_chapter_task.apply_async",
        fake_apply_async,
    )
    monkeypatch.setattr(
        "app.services.task_execution_service.settings.ANALYSIS_WORKER_CONCURRENCY", 1
    )
    user, book = await _processing_user_and_book(db, uuid.uuid4().hex[:8])
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Analysis chapter",
        s3_key=f"chapters/{book.id}/1.txt",
        word_count=10,
    )
    db.add(chapter)
    await db.flush()
    run = await get_or_create_processing_run(db, user_id=user.id, book_id=book.id, chapters_total=1)
    await ensure_task_execution(
        db,
        task_name="analysis_tasks.analyse_chapter",
        processing_run=run,
        chapter_id=chapter.id,
        chapter_number=1,
        arguments={"book_id": str(book.id), "chapter_id": str(chapter.id)},
    )
    await db.commit()

    assert await dispatch_pending_analysis_tasks(db) == 1
    assert len(dispatched) == 1
    assert await dispatch_pending_analysis_tasks(db) == 0
    assert db.in_transaction() is False


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
    assert db.in_transaction() is False
