"""Persist a new outline without modifying chapters already in a project."""

import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, BookSection, Chapter
from app.models.generation import BookDataGeneration
from app.models.intelligence import ChapterSummary
from app.models.user import User
from app.services.book_section_service import (
    append_import_structure_plans,
    filter_analysis_eligible_chapters,
    persist_book_sections,
)
from app.utils.books.structure_plan import build_structure_plan, materialize_structure_plan
from app.utils.reader_utils import build_chapter_list_payload


def test_appending_later_import_plan_keeps_existing_structure():
    book = Book(
        title="Harbor",
        format="txt",
        s3_key="books/test.txt",
        import_structure={"source_sha256": "old"},
    )
    batch = {"scope": "later", "plan": {"parser_version": "prose-structure-3", "sections": []}}
    append_import_structure_plans(book, [batch, batch])
    assert book.import_structure["source_sha256"] == "old"
    assert book.import_structure["additional_imports"] == [
        {"scope": "later", "plan": batch["plan"]}
    ]


@pytest.mark.asyncio
async def test_part_and_chapter_links_are_stable_without_touching_old_chapters(db):
    user = User(
        email=f"outline-{uuid.uuid4().hex[:8]}@lorevia.test",
        username=f"outline{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id, title="Harbor", format="txt", s3_key="books/harbor.txt", status="ready"
    )
    db.add(book)
    await db.flush()
    old_chapter = Chapter(book_id=book.id, number=1, title="Existing", s3_key="chapters/old.txt")
    new_chapter = Chapter(book_id=book.id, number=2, title="Chapter 1", s3_key="chapters/new.txt")
    db.add_all([old_chapter, new_chapter])
    await db.flush()
    plan = build_structure_plan(
        b"new source",
        [
            {"title": "Part I", "section_type": "part", "text": ""},
            {
                "title": "Chapter 1",
                "section_type": "chapter",
                "source_number": 1,
                "text": "Mara crossed the bridge.",
            },
        ],
    )
    chapters = materialize_structure_plan(plan)
    chapters[0]["number"] = 2
    await persist_book_sections(
        db,
        book=book,
        plan=plan,
        chapter_rows=[old_chapter, new_chapter],
        chapters=chapters,
        import_scope="later-upload",
    )
    await db.flush()
    rows = (
        (
            await db.execute(
                select(BookSection)
                .where(BookSection.book_id == book.id)
                .order_by(BookSection.display_order)
            )
        )
        .scalars()
        .all()
    )
    assert [row.kind for row in rows] == ["part", "chapter"]
    assert rows[1].parent_id == rows[0].id
    assert rows[1].chapter_id == new_chapter.id
    assert old_chapter.title == "Existing"

    await persist_book_sections(
        db,
        book=book,
        plan=plan,
        chapter_rows=[old_chapter, new_chapter],
        chapters=chapters,
        import_scope="later-upload",
    )
    assert (
        len(
            (await db.execute(select(BookSection).where(BookSection.book_id == book.id)))
            .scalars()
            .all()
        )
        == 2
    )


@pytest.mark.asyncio
async def test_rebuild_filter_keeps_legacy_chapters_but_excludes_imported_notes(db):
    user = User(
        email=f"outline-{uuid.uuid4().hex[:8]}@lorevia.test",
        username=f"outline{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id, title="Harbor", format="txt", s3_key="books/harbor.txt", status="ready"
    )
    db.add(book)
    await db.flush()
    chapters = [
        Chapter(book_id=book.id, number=1, title="Existing", s3_key="chapters/old.txt"),
        Chapter(book_id=book.id, number=2, title="Author's Note", s3_key="chapters/note.txt"),
        Chapter(book_id=book.id, number=3, title="Chapter 1", s3_key="chapters/new.txt"),
    ]
    db.add_all(chapters)
    await db.flush()
    plan = build_structure_plan(
        b"new source",
        [
            {
                "title": "Author's Note",
                "section_type": "notes",
                "text": "This story began near the harbor.",
            },
            {"title": "Chapter 1", "section_type": "chapter", "text": "Mara crossed the bridge."},
        ],
    )
    imported = materialize_structure_plan(plan)
    for number, item in enumerate(imported, start=2):
        item["number"] = number
    await persist_book_sections(
        db,
        book=book,
        plan=plan,
        chapter_rows=chapters[1:],
        chapters=imported,
        import_scope="later-upload",
    )
    eligible = await filter_analysis_eligible_chapters(db, book.id, chapters)
    assert [chapter.number for chapter in eligible] == [1, 3]


@pytest.mark.asyncio
async def test_chapter_list_suggests_titles_from_active_summary_without_changing_source_heading(db):
    user = User(
        email=f"titles-{uuid.uuid4().hex[:8]}@lorevia.test",
        username=f"titles{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Harbor",
        mode="author",
        format="pdf",
        s3_key="books/harbor.pdf",
        status="ready",
        import_structure={"parser_version": "test"},
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="I",
        s3_key="chapters/harbor.txt",
        processed=True,
        analysis_state={"status": "succeeded", "generated_modes": ["detailed"]},
    )
    db.add(chapter)
    await db.flush()
    db.add(
        BookSection(
            book_id=book.id,
            chapter_id=chapter.id,
            source_section_id="harbor-I",
            kind="chapter",
            title="I",
            source_label="I",
            display_order=1,
            start_block=0,
            end_block=3,
            include_in_analysis=True,
        )
    )
    stale = BookDataGeneration(
        book_id=book.id,
        rebuild_run_id=uuid.uuid4().hex,
        status="retired",
        reason="test",
    )
    active = BookDataGeneration(
        book_id=book.id,
        rebuild_run_id=uuid.uuid4().hex,
        status="active",
        reason="test",
    )
    db.add_all([stale, active])
    await db.flush()
    db.add_all(
        [
            ChapterSummary(
                chapter_id=chapter.id,
                generation_id=stale.id,
                mode="detailed",
                content="A storm hits the harbor.",
                key_events=[{"event_title": "The Storm Arrives"}],
            ),
            ChapterSummary(
                chapter_id=chapter.id,
                generation_id=active.id,
                mode="detailed",
                content="The harbor gate closes at dusk.",
                key_events=[{"event_title": "The Harbor Gate Closes"}],
            ),
        ]
    )
    await db.flush()

    payload = await build_chapter_list_payload(
        db, book=book, current_user=user, intelligence_map={}
    )
    assert payload["chapters"][0]["title"] == "I"
    assert payload["chapters"][0]["printed_label"] == "I"
    assert payload["chapters"][0]["title_suggestion"] == "The Harbor Gate Closes"

    chapter.processed = False
    payload = await build_chapter_list_payload(
        db, book=book, current_user=user, intelligence_map={}
    )
    assert payload["chapters"][0]["title_suggestion"] is None
