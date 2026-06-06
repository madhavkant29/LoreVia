import uuid

import pytest
from sqlalchemy import func, select

from app.models.book import Book, BookUploadCharge, Chapter, NovelScene
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterDuplicateSuggestion,
    CharacterMention,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    WikiEntry,
    WorldElement,
    WorldGapAnalysis,
)
from app.models.tag import CustomTag
from app.models.user import User


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
    book1 = Book(id=uuid.uuid4(), user_id=user_id, title="Book 1", format="manual", s3_key="b1.txt", status="ready")
    book2 = Book(id=uuid.uuid4(), user_id=user_id, title="Book 2", format="manual", s3_key="b2.txt", status="ready")
    db.add_all([book1, book2])
    await db.flush()

    char1 = Character(id=uuid.uuid4(), book_id=book1.id, name="Alice", first_chapter=1)
    char2 = Character(id=uuid.uuid4(), book_id=book2.id, name="Bob", first_chapter=1)
    db.add_all([char1, char2])
    await db.flush()

    state1 = CharacterState(id=uuid.uuid4(), character_id=char1.id, at_chapter=1, trait_snapshot={"role": "hero"})
    state2 = CharacterState(id=uuid.uuid4(), character_id=char2.id, at_chapter=1, trait_snapshot={"role": "villain"})
    db.add_all([state1, state2])
    await db.commit()

    from app.utils.book_utils import purge_chapter_derived_content

    await purge_chapter_derived_content(db, book_id=book1.id, chapter_number=1)

    states_after = (await db.execute(select(CharacterState))).scalars().all()
    state_ids = {s.id for s in states_after}
    assert state1.id not in state_ids, "Book 1's CharacterState should be deleted"
    assert state2.id in state_ids, "Book 2's CharacterState should survive"


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_curated_relationships(db):
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Test", format="manual", s3_key="t.txt", status="ready", is_editor_project=True)
    db.add(book)
    await db.flush()

    char_a = Character(id=uuid.uuid4(), book_id=book.id, name="Alice", first_chapter=1)
    char_b = Character(id=uuid.uuid4(), book_id=book.id, name="Bob", first_chapter=1)
    db.add_all([char_a, char_b])
    await db.commit()

    curated_rel = CharacterRelationship(id=uuid.uuid4(), book_id=book.id, character_a_id=char_a.id, character_b_id=char_b.id, rel_type="ally", from_chapter=1, edited_by_author=True)
    generated_rel = CharacterRelationship(id=uuid.uuid4(), book_id=book.id, character_a_id=char_a.id, character_b_id=char_b.id, rel_type="rival", from_chapter=2, edited_by_author=False)
    db.add_all([curated_rel, generated_rel])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    remaining = (await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book.id))).scalars().all()
    remaining_ids = {r.id for r in remaining}
    assert curated_rel.id in remaining_ids, "Curated relationship should survive"
    assert generated_rel.id not in remaining_ids, "Generated relationship should be deleted"


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_anchor_characters(db):
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Test", format="manual", s3_key="t.txt", status="ready", is_editor_project=True)
    db.add(book)
    await db.flush()

    manual_char = Character(id=uuid.uuid4(), book_id=book.id, name="Manual", first_chapter=1, is_manual=True)
    tagged_char = Character(id=uuid.uuid4(), book_id=book.id, name="Tagged", first_chapter=1, is_manual=False)
    generated_char = Character(id=uuid.uuid4(), book_id=book.id, name="Generated", first_chapter=1, is_manual=False)
    db.add_all([manual_char, tagged_char, generated_char])
    await db.flush()

    tag = CustomTag(id=uuid.uuid4(), book_id=book.id, entity_type="character", entity_id=tagged_char.id, tag_name="important")
    db.add(tag)
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    counts = await reset_generated_data(db, book)
    remaining = (await db.execute(select(Character).where(Character.book_id == book.id))).scalars().all()
    remaining_ids = {c.id for c in remaining}
    assert manual_char.id in remaining_ids, "Manual character should survive"
    assert tagged_char.id in remaining_ids, "Tagged character should survive"
    assert generated_char.id not in remaining_ids, "Generated character should be deleted"
    assert counts["characters_deleted"] == 1
    assert counts["characters_preserved"] == 2


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_curated_plot_threads(db):
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Test", format="manual", s3_key="t.txt", status="ready", is_editor_project=True)
    db.add(book)
    await db.flush()

    curated_pt = PlotThread(id=uuid.uuid4(), book_id=book.id, title="Curated Thread", edited_by_author=True)
    generated_pt = PlotThread(id=uuid.uuid4(), book_id=book.id, title="Generated Thread", edited_by_author=False)
    db.add_all([curated_pt, generated_pt])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    remaining = (await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))).scalars().all()
    remaining_ids = {p.id for p in remaining}
    assert curated_pt.id in remaining_ids, "Curated plot thread should survive"
    assert generated_pt.id not in remaining_ids, "Generated plot thread should be deleted"


@pytest.mark.asyncio
async def test_reset_generated_data_preserves_curated_world_elements(db):
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Test", format="manual", s3_key="t.txt", status="ready", is_editor_project=True)
    db.add(book)
    await db.flush()

    curated_we = WorldElement(id=uuid.uuid4(), book_id=book.id, element_type="location", name="Curated City", edited_by_author=True)
    generated_we = WorldElement(id=uuid.uuid4(), book_id=book.id, element_type="location", name="Generated City", edited_by_author=False)
    db.add_all([curated_we, generated_we])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    remaining = (await db.execute(select(WorldElement).where(WorldElement.book_id == book.id))).scalars().all()
    remaining_ids = {w.id for w in remaining}
    assert curated_we.id in remaining_ids, "Curated world element should survive"
    assert generated_we.id not in remaining_ids, "Generated world element should be deleted"


@pytest.mark.asyncio
async def test_reset_generated_data_clears_generated_intelligence(db):
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Test", format="manual", s3_key="t.txt", status="ready", is_editor_project=True)
    db.add(book)
    await db.flush()

    chapter = Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1.txt", word_count=10)
    db.add(chapter)
    await db.flush()

    char_primary = Character(id=uuid.uuid4(), book_id=book.id, name="Primary", first_chapter=1)
    char_secondary = Character(id=uuid.uuid4(), book_id=book.id, name="Secondary", first_chapter=1)
    db.add_all([char_primary, char_secondary])
    await db.flush()

    chunk = BookChunk(id=uuid.uuid4(), book_id=book.id, chapter_id=chapter.id, chunk_index=0, text="chunk", token_count=1)
    summary = ChapterSummary(id=uuid.uuid4(), chapter_id=chapter.id, mode="short", content="summary")
    wiki = WikiEntry(id=uuid.uuid4(), book_id=book.id, entry_type="location", name="Wiki")
    gap = WorldGapAnalysis(id=uuid.uuid4(), book_id=book.id, analysis_mode="gap")
    candidate = CharacterCandidate(id=uuid.uuid4(), book_id=book.id, chapter_number=1, raw_name="C", proposed_name="C", normalized_name="c", status="pending")
    mention = CharacterMention(id=uuid.uuid4(), book_id=book.id, chapter_number=1, raw_name="M", normalized_name="m", resolver_status="unresolved")
    dup = CharacterDuplicateSuggestion(id=uuid.uuid4(), book_id=book.id, primary_character_id=char_primary.id, secondary_character_id=char_secondary.id, status="pending")
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
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Test", format="manual", s3_key="t.txt", status="ready", is_editor_project=True)
    db.add(book)
    await db.flush()

    chapter = Chapter(id=uuid.uuid4(), book_id=book.id, number=1, s3_key="ch1.txt", word_count=10)
    scene = NovelScene(id=uuid.uuid4(), book_id=book.id, chapter_id=chapter.id, chapter_number=1, title="Scene", body="Body", path="/s/1", sort_order=1)
    db.add_all([chapter, scene])
    await db.commit()

    from app.services.editor_project_service import reset_generated_data

    await reset_generated_data(db, book)
    chapters_after = (await db.execute(select(Chapter).where(Chapter.book_id == book.id))).scalars().all()
    scenes_after = (await db.execute(select(NovelScene).where(NovelScene.book_id == book.id))).scalars().all()
    assert len(chapters_after) == 1, "Chapters should survive"
    assert len(scenes_after) == 1, "NovelScenes should survive"


@pytest.mark.asyncio
async def test_maybe_auto_reprocess_editor_project_waits_for_threshold(db, monkeypatch):
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Draft", format="manual", s3_key="draft.txt", status="ready", is_editor_project=True)
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
    user_id = await _create_user(db)
    book = Book(id=uuid.uuid4(), user_id=user_id, title="Draft", format="manual", s3_key="draft.txt", status="ready", is_editor_project=True)
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
    assert dispatched
    assert book.writer_workspace["reprocess"]["auto_first_started_at"]
    assert book.writer_workspace["reprocess"]["last_reason"] == "auto_first_2000_words"
    charge_count = await db.scalar(
        select(func.count()).select_from(BookUploadCharge).where(BookUploadCharge.book_id == book.id)
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
                "rebuild_run_id": "run-ready",
                "is_fully_ready": True,
            },
            "reprocess": {"last_started_at": "2026-06-02T00:00:00+00:00"},
        },
    )
    db.add(book)
    await db.commit()

    from app.services.editor_project_service import complete_rebuild_if_ready

    completed = await complete_rebuild_if_ready(db, book)
    await db.commit()
    await db.refresh(book)

    assert completed is True
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["reprocess"]["last_completed_rebuild_run_id"] == "run-ready"
    assert book.status == "ready"


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
    await db.commit()

    from app.services.editor_project_service import fail_rebuild_if_active

    stale_failed = await fail_rebuild_if_active(db, book, expected_rebuild_run_id="run-stale", error="stale")
    active_failed = await fail_rebuild_if_active(db, book, expected_rebuild_run_id="run-current", error="queue unavailable")
    await db.commit()
    await db.refresh(book)

    assert stale_failed is False
    assert active_failed is True
    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["processing"]["status"] == "failed"
    assert book.writer_workspace["reprocess"]["last_failed_rebuild_run_id"] == "run-current"
    assert book.status == "failed"


@pytest.mark.asyncio
async def test_dispatch_rebuild_failure_clears_active_run(db, monkeypatch):
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
        "app.workers.tasks.extraction_tasks.process_chapter_task.apply_async",
        _raise_dispatch,
    )

    from app.services.editor_project_service import dispatch_rebuild

    with pytest.raises(RuntimeError, match="queue unavailable"):
        await dispatch_rebuild(db, book)
    await db.refresh(book)

    assert "rebuild_run_id" not in book.writer_workspace["processing"]
    assert book.writer_workspace["reprocess"]["last_failed_rebuild_run_id"] == "run-dispatch"
    assert book.status == "failed"


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
