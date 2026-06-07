from app.workers.celery_app import celery_app
from app.workers.consumers.extraction_consumer import _process_chapter, process_book
from app.services.chapter_recovery_service import repair_chapter_payload_from_source
from app.utils.ingestion_utils import (
    LLM_USAGE_LIMIT_MAX_RETRIES,
    LLM_USAGE_LIMIT_RETRY_SECONDS,
    extract_queue_wait_ms,
    get_processing_started_at,
    is_book_hidden,
    is_llm_usage_limit_error,
    is_retryable_processing_error,
    load_processing_chapter_payload,
    update_book_processing_state,
)
from app.utils.worker_async_utils import run_worker_coro


@celery_app.task(bind=True, name="extraction_tasks.process_book",
                 queue="extraction", max_retries=3, ignore_result=True)
def process_book_task(self, book_id: str):
    try:
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        return run_worker_coro(process_book(book_id, queue_wait_ms=queue_wait_ms, task_id=self.request.id))
    except Exception as exc:
        if not is_retryable_processing_error(exc):
            raise
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="extraction_tasks.process_chapter",
                 queue="extraction", max_retries=3, ignore_result=True)
def process_chapter_task(
    self,
    book_id: str,
    chapter_num: int,
    chapter_version_id: str | None = None,
    rebuild_run_id: str | None = None,
    manual_reprocess: bool = False,
):
    async def _run():
        import uuid
        from datetime import UTC, datetime

        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.core.redis import get_redis
        from app.models.book import Book, Chapter

        r = await get_redis()
        if await r.exists(f"chapter_reprocess:{book_id}:{chapter_num}"):
            return

        try:
            from app.models.book import ChapterVersion
        except ImportError:
            ChapterVersion = None

        version_uuid = uuid.UUID(chapter_version_id) if chapter_version_id else None
        queue_wait_ms = extract_queue_wait_ms(getattr(self.request, "headers", None))
        async with AsyncSessionLocal() as db:
            book = None
            chapter_payload = None
            try:
                if version_uuid is not None and ChapterVersion is not None:
                    version = await db.get(ChapterVersion, version_uuid)
                    if version is not None:
                        version.restore_status = "processing"
                        version.restore_error = None
                        version.restore_task_id = self.request.id
                        version.restore_started_at = version.restore_started_at or datetime.now(UTC)
                        version.restore_completed_at = None
                        await db.commit()

                book = await db.get(Book, uuid.UUID(book_id))
                if not book:
                    if version_uuid is not None and ChapterVersion is not None:
                        version = await db.get(ChapterVersion, version_uuid)
                        if version is not None:
                            version.restore_status = "failed"
                            version.restore_error = "Book not found."
                            version.restore_completed_at = datetime.now(UTC)
                            await db.commit()
                    return
                if rebuild_run_id is not None:
                    from app.services.editor_project_service import get_rebuild_run_id

                    if get_rebuild_run_id(book) != rebuild_run_id:
                        return

                chapter_row = (
                    await db.execute(
                        select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
                    )
                ).scalar()

                if await is_book_hidden(db, book.id):
                    if version_uuid is not None and ChapterVersion is not None:
                        version = await db.get(ChapterVersion, version_uuid)
                        if version is not None:
                            version.restore_status = "failed"
                            version.restore_error = "Book was removed while processing."
                            version.restore_completed_at = datetime.now(UTC)
                            await db.commit()
                    return

                chapter_payload = await load_processing_chapter_payload(
                    book.id,
                    chapter_num,
                    chapter_s3_key=chapter_row.s3_key if chapter_row is not None else None,
                    chapter_title=chapter_row.title if chapter_row is not None else None,
                )
                if chapter_payload is None:
                    raise ValueError(f"missing_chapter_payload:{book.id}:{chapter_num}")

                await _process_chapter(
                    db,
                    book,
                    chapter_payload,
                    queue_wait_ms=queue_wait_ms,
                    rebuild_run_id=rebuild_run_id,
                    manual_reprocess=manual_reprocess,
                )
                await r.set(f"chapter_reprocess:{book_id}:{chapter_num}", "1", ex=30)

                if version_uuid is not None and book.work_type != "screenplay":
                    from app.utils.book_utils import (
                        extract_novel_scene_candidates,
                        replace_chapter_novel_scenes,
                        sync_chapter_content_from_novel_scenes,
                    )

                    extracted_scenes = extract_novel_scene_candidates(
                        text=str(chapter_payload.get("text") or ""),
                        chapter_number=chapter_num,
                        source="chapter_sync",
                    )
                    await replace_chapter_novel_scenes(
                        db,
                        book=book,
                        chapter_number=chapter_num,
                        scenes=extracted_scenes,
                    )
                    await sync_chapter_content_from_novel_scenes(
                        db,
                        book=book,
                        chapter_number=chapter_num,
                    )
                    await db.commit()

                if version_uuid is not None and ChapterVersion is not None:
                    version = await db.get(ChapterVersion, version_uuid)
                    if version is not None:
                        version.restore_status = "restored"
                        version.restore_error = None
                        version.restore_completed_at = datetime.now(UTC)
                        await db.commit()
            except Exception as exc:
                if is_llm_usage_limit_error(exc) and book is not None:
                    await db.rollback()
                    book = await db.get(Book, uuid.UUID(book_id))
                    if book is None:
                        raise
                    processing = book.writer_workspace.get("processing") if isinstance(book.writer_workspace, dict) else {}
                    completed_value = processing.get("chapters_completed") if isinstance(processing, dict) else None
                    total_value = processing.get("chapters_total") if isinstance(processing, dict) else None
                    completed_chapters = (
                        int(completed_value)
                        if isinstance(completed_value, (int, float)) and int(completed_value) >= 0
                        else max(int(chapter_num) - 1, 0)
                    )
                    total_chapters = (
                        int(total_value)
                        if isinstance(total_value, (int, float)) and int(total_value) > 0
                        else book.total_chapters
                    )
                    book.status = "processing"
                    book.writer_workspace = update_book_processing_state(
                        book,
                        status="processing",
                        stage="usage_limited",
                        total_chapters=total_chapters,
                        completed_chapters=completed_chapters,
                        started_at=get_processing_started_at(book),
                        queue_wait_ms=queue_wait_ms,
                        chapter_number=chapter_num,
                        chapter_title=chapter_payload.get("title") if isinstance(chapter_payload, dict) else None,
                        last_error=str(getattr(exc, "detail", None) or exc),
                    )
                    await db.commit()
                    raise
                if version_uuid is not None and ChapterVersion is not None:
                    await db.rollback()
                    version = await db.get(ChapterVersion, version_uuid)
                    if version is not None:
                        version.restore_status = "failed"
                        version.restore_error = str(exc)[:2000]
                        version.restore_completed_at = datetime.now(UTC)
                        await db.commit()
                raise
    try:
        run_worker_coro(_run())
    except Exception as exc:
        if is_llm_usage_limit_error(exc):
            retries = int(getattr(self.request, "retries", 0) or 0)
            if retries >= LLM_USAGE_LIMIT_MAX_RETRIES:
                return {"paused": "llm_usage_limit"}
            raise self.retry(
                exc=exc,
                countdown=LLM_USAGE_LIMIT_RETRY_SECONDS,
                max_retries=LLM_USAGE_LIMIT_MAX_RETRIES,
            )
        retryable = is_retryable_processing_error(exc)
        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = self.max_retries if isinstance(self.max_retries, int) else 3
        if rebuild_run_id is not None and (not retryable or retries >= max_retries):
            async def _fail_terminal_rebuild() -> None:
                import uuid

                from app.core.database import AsyncSessionLocal
                from app.services.editor_project_service import fail_rebuild_run

                async with AsyncSessionLocal() as db:
                    await fail_rebuild_run(
                        db,
                        uuid.UUID(book_id),
                        expected_rebuild_run_id=rebuild_run_id,
                        error=str(exc),
                    )
                    await db.commit()

            run_worker_coro(_fail_terminal_rebuild())
            raise
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="extraction_tasks.repair_chapter_payload",
                 queue="extraction", max_retries=3, ignore_result=True)
def repair_chapter_payload_task(self, book_id: str, chapter_num: int):
    async def _run():
        import uuid

        from sqlalchemy import select

        from app.core.database import AsyncSessionLocal
        from app.models.book import Book, Chapter

        async with AsyncSessionLocal() as db:
            book = await db.get(Book, uuid.UUID(book_id))
            if not book:
                return
            chapter = (
                await db.execute(
                    select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
                )
            ).scalar()
            if chapter is None:
                return
            if await is_book_hidden(db, book.id):
                return
            await repair_chapter_payload_from_source(db, book=book, chapter=chapter)
    try:
        run_worker_coro(_run())
    except Exception as exc:
        if not is_retryable_processing_error(exc):
            raise
        raise self.retry(exc=exc)
