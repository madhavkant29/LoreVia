import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.models.book import Book, BookUploadCharge, Chapter, NovelScene
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterMention,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.generation import BookDataGeneration
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    WikiEntry,
    WorldElement,
    WorldGapAnalysis,
)
from app.models.operations import TaskDispatchOutbox, TaskExecution
from app.models.tag import CustomTag
from app.models.user import ProcessingUsageEvent, User


async def _create_user(db) -> uuid.UUID:
    user = User(
        email=f"test-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"test{uuid.uuid4().hex[:8]}",
        password_hash="fake",
    )
    db.add(user)
    await db.flush()
    return user.id


@pytest.mark.asyncio
async def test_purge_chapter_derived_content_is_book_scoped(db):
    user_id = await _create_user(db)
    book1 = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Book 1",
        format="manual",
        s3_key="b1.txt",
        status="ready",
    )
    book2 = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Book 2",
        format="manual",
        s3_key="b2.txt",
        status="ready",
    )
    db.add_all([book1, book2])
    await db.flush()

    char1 = Character(id=uuid.uuid4(), book_id=book1.id, name="Alice", first_chapter=1)
    char2 = Character(id=uuid.uuid4(), book_id=book2.id, name="Bob", first_chapter=1)
    db.add_all([char1, char2])
    await db.flush()

    state1 = CharacterState(
        id=uuid.uuid4(), character_id=char1.id, at_chapter=1, trait_snapshot={"role": "hero"}
    )
    state2 = CharacterState(
        id=uuid.uuid4(), character_id=char2.id, at_chapter=1, trait_snapshot={"role": "villain"}
    )
    db.add_all([state1, state2])
    await db.commit()

    from app.utils.books.chapter_versions import purge_chapter_derived_content

    await purge_chapter_derived_content(db, book_id=book1.id, chapter_number=1)

    states_after = (await db.execute(select(CharacterState))).scalars().all()
    state_ids = {s.id for s in states_after}
    assert state1.id not in state_ids, "Book 1's CharacterState should be deleted"
    assert state2.id in state_ids, "Book 2's CharacterState should survive"


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_curated_relationships(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        format="manual",
        s3_key="t.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()

    char_a = Character(id=uuid.uuid4(), book_id=book.id, name="Alice", first_chapter=1)
    char_b = Character(id=uuid.uuid4(), book_id=book.id, name="Bob", first_chapter=1)
    db.add_all([char_a, char_b])
    await db.commit()

    curated_rel = CharacterRelationship(
        id=uuid.uuid4(),
        book_id=book.id,
        character_a_id=char_a.id,
        character_b_id=char_b.id,
        rel_type="ally",
        from_chapter=1,
        edited_by_author=True,
    )
    generated_rel = CharacterRelationship(
        id=uuid.uuid4(),
        book_id=book.id,
        character_a_id=char_a.id,
        character_b_id=char_b.id,
        rel_type="rival",
        from_chapter=2,
        edited_by_author=False,
    )
    db.add_all([curated_rel, generated_rel])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    remaining = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    remaining_ids = {r.id for r in remaining}
    assert curated_rel.id in remaining_ids, "Curated relationship should survive"
    assert generated_rel.id not in remaining_ids, "Generated relationship should be deleted"


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_anchor_characters(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        format="manual",
        s3_key="t.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()

    manual_char = Character(
        id=uuid.uuid4(), book_id=book.id, name="Manual", first_chapter=1, is_manual=True
    )
    tagged_char = Character(
        id=uuid.uuid4(), book_id=book.id, name="Tagged", first_chapter=1, is_manual=False
    )
    curated_char = Character(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Curated",
        first_chapter=1,
        analysis_metadata={"user_curated": True},
    )
    reviewed_char = Character(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Reviewed",
        first_chapter=1,
        approval_source="manual_review",
    )
    generated_char = Character(
        id=uuid.uuid4(), book_id=book.id, name="Generated", first_chapter=1, is_manual=False
    )
    db.add_all([manual_char, tagged_char, curated_char, reviewed_char, generated_char])
    await db.flush()

    tag = CustomTag(
        id=uuid.uuid4(),
        book_id=book.id,
        entity_type="character",
        entity_id=tagged_char.id,
        tag_name="important",
    )
    db.add(tag)
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    counts = await reset_generated_data(db, book)
    remaining = (
        (await db.execute(select(Character).where(Character.book_id == book.id))).scalars().all()
    )
    remaining_ids = {c.id for c in remaining}
    assert manual_char.id in remaining_ids, "Manual character should survive"
    assert tagged_char.id in remaining_ids, "Tagged character should survive"
    assert curated_char.id in remaining_ids, "Metadata-curated character should survive"
    assert reviewed_char.id in remaining_ids, "Manually reviewed character should survive"
    assert generated_char.id not in remaining_ids, "Generated character should be deleted"
    assert counts["characters_deleted"] == 1
    assert counts["characters_preserved"] == 4


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_curated_plot_threads(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        format="manual",
        s3_key="t.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()

    curated_pt = PlotThread(
        id=uuid.uuid4(), book_id=book.id, title="Curated Thread", edited_by_author=True
    )
    generated_pt = PlotThread(
        id=uuid.uuid4(), book_id=book.id, title="Generated Thread", edited_by_author=False
    )
    db.add_all([curated_pt, generated_pt])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    remaining = (
        (await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))).scalars().all()
    )
    remaining_ids = {p.id for p in remaining}
    assert curated_pt.id in remaining_ids, "Curated plot thread should survive"
    assert generated_pt.id not in remaining_ids, "Generated plot thread should be deleted"


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_curated_world_elements(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        format="manual",
        s3_key="t.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()

    curated_we = WorldElement(
        id=uuid.uuid4(),
        book_id=book.id,
        element_type="location",
        name="Curated City",
        edited_by_author=True,
    )
    generated_we = WorldElement(
        id=uuid.uuid4(),
        book_id=book.id,
        element_type="location",
        name="Generated City",
        edited_by_author=False,
    )
    db.add_all([curated_we, generated_we])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    remaining = (
        (await db.execute(select(WorldElement).where(WorldElement.book_id == book.id)))
        .scalars()
        .all()
    )
    remaining_ids = {w.id for w in remaining}
    assert curated_we.id in remaining_ids, "Curated world element should survive"
    assert generated_we.id not in remaining_ids, "Generated world element should be deleted"


@pytest.mark.asyncio
async def test_reset_generated_data_clears_generated_intelligence(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        format="manual",
        s3_key="t.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1.txt", word_count=10)
    db.add(chapter)
    await db.flush()

    char_primary = Character(id=uuid.uuid4(), book_id=book.id, name="Primary", first_chapter=1)
    char_secondary = Character(id=uuid.uuid4(), book_id=book.id, name="Secondary", first_chapter=1)
    db.add_all([char_primary, char_secondary])
    await db.flush()

    chunk = BookChunk(
        id=uuid.uuid4(),
        book_id=book.id,
        chapter_id=chapter.id,
        chunk_index=0,
        text="chunk",
        token_count=1,
    )
    summary = ChapterSummary(
        id=uuid.uuid4(), chapter_id=chapter.id, mode="short", content="summary"
    )
    wiki = WikiEntry(id=uuid.uuid4(), book_id=book.id, entry_type="location", name="Wiki")
    gap = WorldGapAnalysis(id=uuid.uuid4(), book_id=book.id, analysis_mode="gap")
    candidate = CharacterCandidate(
        id=uuid.uuid4(),
        book_id=book.id,
        chapter_number=1,
        raw_name="C",
        proposed_name="C",
        normalized_name="c",
        status="pending",
    )
    mention = CharacterMention(
        id=uuid.uuid4(),
        book_id=book.id,
        chapter_number=1,
        raw_name="M",
        normalized_name="m",
        resolver_status="unresolved",
    )
    dup = CharacterDuplicateSuggestion(
        id=uuid.uuid4(),
        book_id=book.id,
        primary_character_id=char_primary.id,
        secondary_character_id=char_secondary.id,
        status="pending",
    )
    vp = CharacterVoiceProfile(id=uuid.uuid4(), book_id=book.id, character_id=char_primary.id)
    db.add_all([chunk, summary, wiki, gap, candidate, mention, dup, vp])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    counts = await reset_generated_data(db, book)
    assert counts["book_chunks"] >= 1
    assert counts["chapter_summaries"] >= 1
    assert counts["wiki_entries"] >= 1
    assert counts["world_gap_analyses"] >= 1
    assert counts["character_candidates"] >= 1
    assert counts["character_mentions"] >= 1
    assert counts["duplicate_suggestions"] >= 1
    assert counts["voice_profiles"] >= 1


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_chapters_and_scenes(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Test",
        format="manual",
        s3_key="t.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1.txt", word_count=10)
    scene = NovelScene(
        id=uuid.uuid4(),
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=1,
        title="Scene",
        body="Body",
        path="/s/1",
        sort_order=1,
    )
    db.add_all([chapter, scene])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    chapters_after = (
        (await db.execute(select(Chapter).where(Chapter.book_id == book.id))).scalars().all()
    )
    scenes_after = (
        (await db.execute(select(NovelScene).where(NovelScene.book_id == book.id))).scalars().all()
    )
    assert len(chapters_after) == 1, "Chapters should survive"
    assert len(scenes_after) == 1, "NovelScenes should survive"


@pytest.mark.asyncio
async def test_maybe_auto_reprocess_editor_project_waits_for_threshold(db, monkeypatch):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, s3_key="ch1.txt", word_count=1999))
    await db.commit()

    from app.services.editor_project_service import maybe_auto_reprocess_editor_project

    triggered, chapters_queued, total_words = await maybe_auto_reprocess_editor_project(db, book)

    assert triggered is False
    assert chapters_queued == 0
    assert total_words == 1999


@pytest.mark.asyncio
async def test_maybe_auto_reprocess_editor_project_starts_once_at_threshold(db, monkeypatch):
    await db.execute(
        update(TaskExecution)
        .where(TaskExecution.status.in_(("pending_dispatch", "queued", "running")))
        .values(status="succeeded")
    )
    await db.commit()
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="ready",
        is_editor_project=True,
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, s3_key="ch1.txt", word_count=2000))
    await db.commit()

    dispatched: list[dict] = []

    def _fake_apply_async(*args, **kwargs):
        dispatched.append({"args": args, "kwargs": kwargs})
        return type("Result", (), {"id": "task-1"})()

    monkeypatch.setattr(
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _fake_apply_async,
    )

    from app.services.editor_project_service import maybe_auto_reprocess_editor_project

    triggered, chapters_queued, total_words = await maybe_auto_reprocess_editor_project(db, book)
    await db.refresh(book)
    triggered_again, chapters_queued_again, _ = await maybe_auto_reprocess_editor_project(db, book)

    assert triggered is True
    assert chapters_queued == 1
    assert total_words == 2000
    execution = await db.scalar(
        select(TaskExecution).where(
            TaskExecution.book_id == book.id,
            TaskExecution.task_name == "extraction_tasks.process_chapter",
        )
    )
    assert execution is not None
    reservation = await db.scalar(
        select(ProcessingUsageEvent).where(
            ProcessingUsageEvent.book_id == book.id,
            ProcessingUsageEvent.usage_kind == "auto_first_reprocess",
        )
    )
    assert reservation is not None
    assert reservation.source_id.startswith(
        f"auto-first:{book.writer_workspace['processing']['rebuild_run_id']}:"
    )
    assert reservation.status == "reserved"
    assert reservation.task_id == str(execution.id)
    assert book.writer_workspace["reprocess"]["auto_first_started_at"]
    assert book.writer_workspace["reprocess"]["last_reason"] == "auto_first_2000_words"
    charge_count = await db.scalar(
        select(func.count())
        .select_from(BookUploadCharge)
        .where(BookUploadCharge.book_id == book.id)
    )
    assert charge_count == 0
    assert triggered_again is False
    assert chapters_queued_again == 0


@pytest.mark.asyncio
async def test_maybe_auto_reprocess_editor_project_does_not_start_after_manual_reprocess(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="ready",
        is_editor_project=True,
        writer_workspace={"reprocess": {"manual_started_at": "2026-06-02T00:00:00+00:00"}},
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, s3_key="ch1.txt", word_count=2000))
    await db.commit()

    from app.services.editor_project_service import maybe_auto_reprocess_editor_project

    triggered, chapters_queued, total_words = await maybe_auto_reprocess_editor_project(db, book)

    assert triggered is False
    assert chapters_queued == 0
    assert total_words == 0


@pytest.mark.asyncio
async def test_complete_rebuild_if_ready_clears_active_run_id(db):
    user_id = await _create_user(db)
    rebuild_run_id = uuid.uuid4().hex
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "analysis",
                "rebuild_run_id": rebuild_run_id,
                "is_fully_ready": True,
            },
            "reprocess": {"last_started_at": "2026-06-02T00:00:00+00:00"},
        },
    )
    db.add(book)
    db.add(
        BookDataGeneration(
            id=uuid.UUID(rebuild_run_id),
            book_id=book.id,
            rebuild_run_id=rebuild_run_id,
            status="staging",
            reason="test",
        )
    )
    await db.commit()

    from app.services.editor_project_service import complete_rebuild_if_ready

    completed = await complete_rebuild_if_ready(db, book)
    await db.commit()
    await db.refresh(book)

    assert completed is True
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["reprocess"]["last_completed_rebuild_run_id"] == rebuild_run_id
    assert book.status == "ready"


@pytest.mark.asyncio
async def test_full_rebuild_keeps_active_chunks_until_atomic_promotion(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Generation test",
        format="manual",
        s3_key="generation-test.txt",
        status="ready",
        is_editor_project=True,
        total_chapters=1,
    )
    chapter = Chapter(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        s3_key="generation-ch1.txt",
        word_count=100,
        processed=True,
    )
    db.add_all([book, chapter])
    await db.flush()
    db.add(
        BookChunk(
            book_id=book.id,
            chapter_id=chapter.id,
            chunk_index=0,
            text="old active text",
        )
    )
    await db.commit()

    from app.services.data_generation_service import generation_scope
    from app.services.editor_project_service import complete_rebuild_if_ready, prepare_rebuild

    rebuild_run_id = await prepare_rebuild(db, book)
    active_texts = list(
        (await db.execute(select(BookChunk.text).where(BookChunk.book_id == book.id)))
        .scalars()
        .all()
    )
    assert active_texts == ["old active text"]

    with generation_scope(rebuild_run_id):
        staged_before = list(
            (await db.execute(select(BookChunk.text).where(BookChunk.book_id == book.id)))
            .scalars()
            .all()
        )
        assert staged_before == []
        db.add(
            BookChunk(
                book_id=book.id,
                chapter_id=chapter.id,
                chunk_index=0,
                text="new staged text",
            )
        )
        db.add(
            ChapterSummary(
                chapter_id=chapter.id,
                mode="detailed",
                content="new staged summary",
            )
        )
        chapter.processed = True
        await db.commit()
        assert await complete_rebuild_if_ready(db, book) is True
        await db.commit()

    promoted_texts = list(
        (await db.execute(select(BookChunk.text).where(BookChunk.book_id == book.id)))
        .scalars()
        .all()
    )
    assert promoted_texts == ["new staged text"]


@pytest.mark.asyncio
async def test_repair_stale_editor_processing_state_marks_ready_without_active_run(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="processing",
        is_editor_project=True,
        total_chapters=1,
        writer_workspace={
            "processing": {
                "status": "processing",
                "stage": "analysis",
                "chapters_completed": 1,
                "chapters_total": 1,
                "progress_pct": 100,
            },
            "reprocess": {"last_started_at": "2026-06-02T00:00:00+00:00"},
        },
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(
        id=uuid.uuid4(),
        book_id=book.id,
        number=1,
        title="Chapter 1",
        s3_key="ch1.txt",
        word_count=250,
        processed=True,
    )
    db.add(chapter)
    await db.flush()

    db.add(
        ChapterSummary(
            id=uuid.uuid4(),
            chapter_id=chapter.id,
            mode="detailed",
            content="Done",
        )
    )
    await db.commit()

    from app.services.editor_project_service import repair_stale_editor_processing_state

    repaired = await repair_stale_editor_processing_state(db, book)
    await db.refresh(book)

    assert repaired is True
    assert book.status == "ready"
    assert book.writer_workspace["processing"]["status"] == "ready"
    assert book.writer_workspace["processing"]["stage"] == "complete"
    assert book.writer_workspace["reprocess"]["last_completed_at"]


@pytest.mark.asyncio
async def test_fail_rebuild_if_active_clears_only_matching_run(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={"processing": {"rebuild_run_id": "run-current", "status": "processing"}},
    )
    db.add(book)
    reservation = ProcessingUsageEvent(
        user_id=user_id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="manual:run-current:chapter-1:1",
        word_count=100,
        status="reserved",
    )
    db.add(reservation)
    await db.commit()

    from app.services.editor_project_service import fail_rebuild_if_active

    stale_failed = await fail_rebuild_if_active(
        db, book, expected_rebuild_run_id="run-stale", error="stale"
    )
    assert reservation.status == "reserved"
    active_failed = await fail_rebuild_if_active(
        db, book, expected_rebuild_run_id="run-current", error="queue unavailable"
    )
    await db.commit()
    await db.refresh(book)

    assert stale_failed is False
    assert active_failed is True
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["processing"]["status"] == "failed"
    assert book.writer_workspace["reprocess"]["last_failed_rebuild_run_id"] == "run-current"
    assert book.status == "failed"
    assert reservation.status == "released"


@pytest.mark.asyncio
async def test_cancel_rebuild_releases_unfinished_manual_reservations(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Cancelled draft",
        format="manual",
        s3_key="cancelled-draft.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={"processing": {"rebuild_run_id": "run-cancel", "status": "processing"}},
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, s3_key="cancel-ch1.txt", word_count=100))
    reservation = ProcessingUsageEvent(
        user_id=user_id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="manual:run-cancel:chapter-1:1",
        word_count=100,
        status="reserved",
    )
    db.add(reservation)
    await db.commit()

    from app.services.editor_project_service import cancel_rebuild_for_manual_edit

    assert await cancel_rebuild_for_manual_edit(
        db,
        book,
        reason="The manuscript changed during reprocessing.",
    )
    await db.commit()
    await db.refresh(reservation)

    assert reservation.status == "released"
    assert book.writer_workspace["processing"]["status"] == "failed"


@pytest.mark.asyncio
async def test_dispatch_rebuild_broker_failure_keeps_durable_work_pending(db, monkeypatch):
    await db.execute(
        update(TaskExecution)
        .where(TaskExecution.status.in_(("pending_dispatch", "queued", "running")))
        .values(status="succeeded")
    )
    await db.commit()
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={"processing": {"rebuild_run_id": "run-dispatch", "status": "processing"}},
    )
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=1, s3_key="ch1.txt", word_count=2000))
    await db.commit()

    def _raise_dispatch(*_args, **_kwargs):
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(
        "app.services.task_execution_service._publish_outbox_task",
        _raise_dispatch,
    )

    from app.services.editor_project_service import dispatch_rebuild

    chapters_queued, _ = await dispatch_rebuild(db, book)
    await db.refresh(book)
    execution = await db.scalar(
        select(TaskExecution).where(
            TaskExecution.book_id == book.id,
            TaskExecution.task_name == "extraction_tasks.process_chapter",
        )
    )
    assert execution is not None
    outbox = await db.scalar(
        select(TaskDispatchOutbox).where(TaskDispatchOutbox.execution_id == execution.id)
    )
    assert outbox is not None
    await db.execute(
        update(TaskDispatchOutbox)
        .where(
            TaskDispatchOutbox.id != outbox.id,
            TaskDispatchOutbox.status.in_(("pending", "publish_failed")),
        )
        .values(status="cancelled")
    )
    outbox.status = "pending"
    outbox.available_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()

    from app.services.task_execution_service import publish_task_dispatch_outbox

    await publish_task_dispatch_outbox(
        db,
        queues=("extraction", "extraction_priority"),
        limit=1,
    )
    await db.refresh(execution)

    assert chapters_queued == 1
    assert execution.status == "pending_dispatch"
    assert execution.error_category == "dispatch"
    assert book.writer_workspace["processing"]["rebuild_run_id"] == "run-dispatch"
    assert book.status == "processing"


@pytest.mark.asyncio
async def test_partial_rebuild_dispatch_releases_every_unfinished_reservation(db, monkeypatch):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Partial dispatch",
        format="manual",
        s3_key="partial-dispatch.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={"processing": {"rebuild_run_id": "run-partial", "status": "processing"}},
    )
    db.add(book)
    await db.flush()
    chapters = [
        Chapter(book_id=book.id, number=1, s3_key="partial-1.txt", word_count=100),
        Chapter(book_id=book.id, number=2, s3_key="partial-2.txt", word_count=200),
    ]
    db.add_all(chapters)
    await db.flush()
    reservations = [
        ProcessingUsageEvent(
            user_id=user_id,
            book_id=book.id,
            usage_kind="manual_reprocess",
            source_id=f"manual:run-partial:{chapter.id}:1",
            word_count=int(chapter.word_count or 0),
            status="reserved",
        )
        for chapter in chapters
    ]
    db.add_all(reservations)
    await db.commit()
    calls = 0

    async def enqueue(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("dispatch interrupted")
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(
        "app.services.task_execution_service.enqueue_extraction_execution",
        enqueue,
    )
    from app.services.editor_project_service import dispatch_rebuild

    with pytest.raises(RuntimeError, match="dispatch interrupted"):
        await dispatch_rebuild(
            db,
            book,
            reservation_ids_by_chapter_id={
                chapter.id: reservation.id
                for chapter, reservation in zip(chapters, reservations, strict=True)
            },
            manual_reprocess=True,
            run_kind="manual_reprocess",
        )

    for reservation in reservations:
        await db.refresh(reservation)
    await db.refresh(book)
    assert calls == 2
    assert all(reservation.status == "released" for reservation in reservations)
    assert book.status == "failed"


@pytest.mark.asyncio
async def test_dispatch_rebuild_rolls_back_before_cleanup_after_db_failure(db, monkeypatch):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Failed dispatch",
        format="manual",
        s3_key="failed-dispatch.txt",
        status="processing",
        is_editor_project=True,
        writer_workspace={"processing": {"rebuild_run_id": "run-db-fail", "status": "processing"}},
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=1, s3_key="failed-1.txt", word_count=100)
    db.add(chapter)
    await db.flush()
    reservation = ProcessingUsageEvent(
        user_id=user_id,
        book_id=book.id,
        usage_kind="manual_reprocess",
        source_id="manual:run-db-fail:chapter-1:1",
        word_count=100,
        status="reserved",
    )
    db.add(reservation)
    await db.commit()

    async def enqueue(db_arg, *_args, **_kwargs):
        db_arg.add(
            TaskExecution(
                identity_key=f"broken-{uuid.uuid4().hex}",
                task_name="extraction_tasks.process_chapter",
                feature="processing",
                user_id=uuid.uuid4(),
                book_id=book.id,
                chapter_id=chapter.id,
                chapter_number=chapter.number,
                arguments_json={},
            )
        )
        await db_arg.flush()

    monkeypatch.setattr(
        "app.services.task_execution_service.enqueue_extraction_execution",
        enqueue,
    )
    from app.services.editor_project_service import dispatch_rebuild

    with pytest.raises(IntegrityError):
        await dispatch_rebuild(
            db,
            book,
            reservation_ids_by_chapter_id={chapter.id: reservation.id},
            manual_reprocess=True,
            run_kind="manual_reprocess",
        )

    await db.refresh(book)
    await db.refresh(reservation)
    assert book.status == "failed"
    assert book.writer_workspace["processing"]["status"] == "failed"
    assert reservation.status == "released"


@pytest.mark.asyncio
async def test_dispatch_rebuild_requires_active_run_id(db):
    user_id = await _create_user(db)
    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Draft",
        format="manual",
        s3_key="draft.txt",
        status="ready",
        is_editor_project=True,
        writer_workspace={},
    )
    db.add(book)
    await db.commit()

    from app.services.editor_project_service import dispatch_rebuild

    with pytest.raises(RuntimeError, match="active_rebuild_run_required"):
        await dispatch_rebuild(db, book)
