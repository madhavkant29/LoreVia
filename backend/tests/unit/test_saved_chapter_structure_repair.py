"""Safe mapping of saved reader progress across corrected PDF chapters."""

import hashlib
import uuid

import pytest
from sqlalchemy import func, select

from app.models.book import Book, BookSection, Chapter, ChapterVersion
from app.models.generation import BookDataGeneration
from app.models.progress import ReadingProgress
from app.models.user import User
from app.utils.books.structure_plan import build_structure_plan, materialize_structure_plan
from app.utils.books.structure_repair import chapter_number_map, map_reading_position
from scripts import apply_saved_chapter_structure as repair
from scripts.apply_saved_chapter_structure import _check_locked_state
from tests import conftest


def _chapters():
    first = " ".join(["One"] * 12)
    second = " ".join(["Two"] * 12)
    saved = [
        {"number": 1, "title": "Opening material", "text": "A preface."},
        {
            "number": 2,
            "title": "Part One — opening",
            "text": f"I\n\n{first}.\n\nII\n\n{second}.",
        },
    ]
    proposed = [
        {"text": "A preface."},
        {"text": f"{first}."},
        {"text": f"{second}."},
    ]
    return saved, proposed


def test_part_progress_maps_by_word_offset_and_expands_read_chapters():
    saved, proposed = _chapters()
    mapping = chapter_number_map(saved, proposed)
    assert mapping == {1: [1], 2: [2, 3]}
    assert map_reading_position(
        mapping,
        proposed,
        current_chapter=2,
        scroll_pct=0.75,
        chapters_read=[1, 2],
    ) == {"current_chapter": 3, "scroll_pct": 0.5, "chapters_read": [1, 2, 3]}


def test_end_of_part_maps_to_end_of_last_new_chapter():
    saved, proposed = _chapters()
    assert map_reading_position(
        chapter_number_map(saved, proposed),
        proposed,
        current_chapter=2,
        scroll_pct=1.0,
        chapters_read=None,
    ) == {"current_chapter": 3, "scroll_pct": 1.0, "chapters_read": []}


def test_mapping_rejects_missing_chapters_and_positions():
    saved, proposed = _chapters()
    with pytest.raises(ValueError, match="mapping_mismatch"):
        chapter_number_map(saved, proposed[:-1])
    with pytest.raises(ValueError, match="unmapped"):
        map_reading_position({1: [1]}, proposed, current_chapter=2, scroll_pct=0, chapters_read=[])


@pytest.mark.asyncio
async def test_locked_repair_state_rejects_progress_changed_since_plan(db):
    user = User(email="structure-repair@example.test", password_hash="unused")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Synthetic harbor",
        format="pdf",
        s3_key="books/source.pdf",
        import_structure={"source_sha256": "source-hash"},
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Opening material",
        s3_key="chapters/original.txt",
        content_version=1,
    )
    generation = BookDataGeneration(
        book_id=book.id,
        rebuild_run_id="synthetic-repair-run",
        status="active",
        reason="test",
    )
    db.add_all([chapter, generation])
    await db.flush()
    progress = ReadingProgress(
        user_id=user.id,
        book_id=book.id,
        current_chapter=1,
        scroll_pct=0.5,
        chapters_read=[],
    )
    db.add(progress)
    await db.flush()
    plan = {
        "_identity": {
            "source_key": book.s3_key,
            "source_sha256": "source-hash",
            "generation_id": str(generation.id),
            "saved_chapters": [
                {
                    "number": 1,
                    "id": str(chapter.id),
                    "content_version": 1,
                    "title": chapter.title,
                    "s3_key": chapter.s3_key,
                }
            ],
            "record_counts": {
                "saved_scenes": 0,
                "chapter_versions": 0,
                "manuscript_annotations": 0,
                "book_sections": 0,
                "chapter_media": 0,
                "reading_sessions": 0,
                "chapter_notes": 0,
                "reading_progress": 1,
            },
            "section_ids": [],
            "reading_progress": [
                {
                    "id": str(progress.id),
                    "current_chapter": 1,
                    "scroll_pct": 0.5,
                    "chapters_read": [],
                }
            ],
        }
    }
    rows, positions = await _check_locked_state(db, book, plan)
    assert rows == [chapter]
    assert positions == [progress]
    progress.scroll_pct = 0.6
    await db.flush()
    with pytest.raises(ValueError, match="reading_progress_changed"):
        await _check_locked_state(db, book, plan)
    assert (
        await db.execute(select(ChapterVersion).where(ChapterVersion.book_id == book.id))
    ).first() is None
    assert (
        await db.execute(select(BookSection).where(BookSection.book_id == book.id))
    ).first() is None


@pytest.mark.asyncio
async def test_apply_saved_structure_preserves_old_versions_and_maps_progress(db, monkeypatch):
    user = User(email="structure-apply@example.test", password_hash="unused")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Synthetic harbor",
        format="pdf",
        s3_key="books/harbor.pdf",
        import_structure={"source_sha256": "source-hash"},
        status="ready",
    )
    db.add(book)
    await db.flush()
    saved_source, proposed_source = _chapters()
    first, second = saved_source
    chapters = [
        Chapter(
            book_id=book.id,
            number=source["number"],
            title=source["title"],
            s3_key=f"chapters/old-{source['number']}.txt",
            content_version=1,
        )
        for source in (first, second)
    ]
    generation = BookDataGeneration(
        book_id=book.id,
        rebuild_run_id="synthetic-apply-run",
        status="active",
        reason="test",
    )
    db.add_all([*chapters, generation])
    await db.flush()
    progress = ReadingProgress(
        user_id=user.id,
        book_id=book.id,
        current_chapter=2,
        scroll_pct=0.75,
        chapters_read=[1],
    )
    db.add(progress)
    await db.commit()
    source = [
        {"section_type": "unknown", "title": "Opening material", "text": first["text"]},
        {"section_type": "part", "title": "Part One", "text": ""},
        {"section_type": "chapter", "title": "I", "text": proposed_source[1]["text"]},
        {"section_type": "chapter", "title": "II", "text": proposed_source[2]["text"]},
    ]
    structure = build_structure_plan(b"synthetic", source)
    proposed = materialize_structure_plan(structure)
    saved = [
        {
            **source,
            "id": str(chapter.id),
            "content_version": 1,
            "s3_key": chapter.s3_key,
        }
        for source, chapter in zip((first, second), chapters)
    ]
    identity = {
        "source_key": book.s3_key,
        "source_sha256": "source-hash",
        "generation_id": str(generation.id),
        "saved_chapters": [
            {key: row[key] for key in ("number", "id", "title", "content_version", "s3_key")}
            for row in saved
        ],
        "record_counts": {
            "saved_scenes": 0,
            "chapter_versions": 0,
            "manuscript_annotations": 0,
            "book_sections": 0,
            "chapter_media": 0,
            "reading_sessions": 0,
            "chapter_notes": 0,
            "reading_progress": 1,
        },
        "section_ids": [],
        "reading_progress": [
            {
                "id": str(progress.id),
                "current_chapter": 2,
                "scroll_pct": 0.75,
                "chapters_read": [1],
            }
        ],
    }
    plan = {
        "_identity": identity,
        "_reparsed": {"chapters": proposed, "structure_plan": structure},
        "active_generation_id": str(generation.id),
        "plan_sha256": "planned-hash",
        "all_chapter_content_preserved": True,
        "all_chapter_titles_match": True,
        "saved_chapter_count": 2,
        "proposed_chapter_count": 3,
        "reading_progress_mapping": [
            map_reading_position(
                chapter_number_map(saved, proposed),
                proposed,
                current_chapter=2,
                scroll_pct=0.75,
                chapters_read=[1],
            )
        ],
    }

    async def planned(_book_id, *, include_private):
        assert include_private is True
        return plan

    async def staged(_book, *, chapter_number, text, html):
        from app.utils.books.manuscript import StagedEditorChapterContent

        return StagedEditorChapterContent(
            text=text,
            html=html,
            storage_key=f"chapters/new-{chapter_number}-{uuid.uuid4().hex}.txt",
            media=[],
            retained_media_markers=set(),
            should_sync_media=False,
            uploaded_keys=(),
        )

    async def no_cache(*_args, **_kwargs):
        return None

    monkeypatch.setattr(repair, "build_plan", planned)
    monkeypatch.setattr(repair, "AsyncSessionLocal", conftest.TestSession)
    monkeypatch.setattr(repair, "stage_editor_chapter_content", staged)
    monkeypatch.setattr(repair, "invalidate_advisor_caches_for_book", no_cache)
    monkeypatch.setattr(repair, "mark_book_cache_dirty", no_cache)
    monkeypatch.setattr(repair, "mark_user_dashboard_cache_dirty", no_cache)

    result = await repair.apply_plan(book.id, generation.id, "planned-hash")
    assert result["chapters"] == 3
    assert result["ai_calls"] == 0
    await db.refresh(book)
    await db.refresh(progress)
    assert book.total_chapters == 3
    assert book.writer_workspace["reprocess"]["pending_chapters"] == [1, 2, 3]
    assert progress.current_chapter == 3
    assert progress.scroll_pct == 0.5
    assert progress.chapters_read == [1]
    actual = (
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number)
            )
        )
        .scalars()
        .all()
    )
    for row in actual:
        await db.refresh(row)
    assert len(actual) == 3
    assert [chapter.title for chapter in actual] == ["Opening material", "I", "II"]
    assert [chapter.content_version for chapter in actual] == [2, 2, 1]
    assert [chapter.id for chapter in actual[:2]] == [chapter.id for chapter in chapters]
    assert (
        await db.scalar(
            select(func.count()).select_from(BookSection).where(BookSection.book_id == book.id)
        )
    ) == 4
    assert (
        await db.scalar(
            select(func.count())
            .select_from(ChapterVersion)
            .where(ChapterVersion.book_id == book.id)
        )
    ) == 2
