"""Focused book chapter versions workflows."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, move_object, upload_binary
from app.models.beta_read import BetaReadFeedbackItem
from app.models.book import (
    Book,
    BookNote,
    Chapter,
    ChapterMedia,
    ChapterVersion,
    ManuscriptAnnotation,
    NovelScene,
    PublicBookAnalyticsEvent,
    SceneVersion,
)
from app.models.character import (
    Character,
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterSuppression,
)
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    QuoteEntry,
    WorldNote,
)
from app.models.progress import ReadingProgress
from app.models.tag import CustomTag
from app.models.user import UserWritingActivity
from app.utils.books import (
    manuscript,
    writer_workspace,
)
from app.utils.books.chapter_titles import (
    _count_words,
)
from app.utils.books.scene_sync import (
    _chapter_storage_key,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.tag_utils import (
    ENTITY_TYPE_CHAPTER,
)

RESTORE_FAILED_MESSAGE = "The restore stopped before it finished. Try again."


def public_restore_error(version: ChapterVersion) -> str | None:
    """Hide exception text saved by older restore tasks from chapter history APIs."""
    if version.restore_status == "failed":
        return RESTORE_FAILED_MESSAGE
    return version.restore_error


async def snapshot_chapter_version(
    db: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    note: str,
    snapshot_kind: str = "manual",
    restored_from_version_id: uuid.UUID | None = None,
) -> ChapterVersion | None:
    if not chapter.s3_key:
        return None
    try:
        raw = await asyncio.to_thread(download_book, chapter.s3_key)
    except STORAGE_IO_EXCEPTIONS:
        return None

    version_key = await asyncio.to_thread(
        upload_binary,
        f"versions/{book.user_id}/{book.id}/{chapter.number}/{uuid.uuid4()}.txt",
        raw,
        "text/plain; charset=utf-8",
    )
    version = ChapterVersion(
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        title=chapter.title,
        s3_key=version_key,
        word_count=chapter.word_count,
        note=note,
        snapshot_kind=snapshot_kind,
        restored_from_version_id=restored_from_version_id,
    )
    db.add(version)
    await db.flush()
    return version


async def snapshot_chapter_version_reference(
    db: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    note: str,
    snapshot_kind: str = "manual",
    restored_from_version_id: uuid.UUID | None = None,
) -> ChapterVersion | None:
    """Record a version by retaining an immutable chapter storage key."""
    if not chapter.s3_key:
        return None
    version = ChapterVersion(
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        title=chapter.title,
        s3_key=chapter.s3_key,
        word_count=chapter.word_count,
        note=note,
        snapshot_kind=snapshot_kind,
        restored_from_version_id=restored_from_version_id,
    )
    db.add(version)
    await db.flush()
    return version


async def get_chapter_version_content(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(ChapterVersion).where(
                ChapterVersion.book_id == book.id, ChapterVersion.id == version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Chapter version not found")
    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = manuscript.deserialize_manuscript_content(raw)
    return {
        "id": str(version.id),
        "chapter_number": version.chapter_number,
        "title": version.title,
        "word_count": version.word_count,
        "note": version.note,
        "snapshot_kind": version.snapshot_kind,
        "restore_status": version.restore_status,
        "restore_error": public_restore_error(version),
        "restore_task_id": version.restore_task_id,
        "restore_started_at": version.restore_started_at,
        "restore_completed_at": version.restore_completed_at,
        "created_at": version.created_at,
        "text": str(stored.get("text") or ""),
        "html": cast(str | None, stored.get("html")),
    }


async def purge_chapter_derived_content(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    chapter_id: uuid.UUID | None = None,
) -> None:
    from app.models.character import Character, CharacterState
    from app.models.intelligence import BookChunk, CharacterRelationship

    if chapter_id is not None:
        await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter_id))
        await db.execute(delete(ChapterSummary).where(ChapterSummary.chapter_id == chapter_id))
    await db.execute(
        delete(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterState).where(
            CharacterState.character_id.in_(
                select(Character.id).where(Character.book_id == book_id)
            ),
            CharacterState.at_chapter == chapter_number,
        )
    )
    await db.execute(
        delete(NovelScene).where(
            NovelScene.book_id == book_id,
            NovelScene.chapter_number == chapter_number,
        )
    )


async def _recompute_character_chapter_aggregates(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    character_ids: set[uuid.UUID],
) -> None:
    if not character_ids:
        return

    characters = (
        (
            await db.execute(
                select(Character).where(
                    Character.book_id == book_id,
                    Character.id.in_(character_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    for character in characters:
        rows = (
            await db.execute(
                select(
                    func.min(CharacterMention.chapter_number),
                    func.max(CharacterMention.chapter_number),
                    func.count(CharacterMention.id),
                ).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.matched_character_id == character.id,
                )
            )
        ).one()
        first_chapter, last_seen_chapter, mention_count = rows
        character.mention_count = int(mention_count or 0)
        if first_chapter is not None:
            character.first_chapter = int(first_chapter)
            character.last_seen_chapter = (
                int(last_seen_chapter) if last_seen_chapter is not None else None
            )
        elif character.last_seen_chapter == character.first_chapter:
            character.last_seen_chapter = None


async def _repair_progress_after_chapter_delete(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    remaining_numbers: list[int],
) -> None:
    fallback_chapter = remaining_numbers[-1] if remaining_numbers else 1
    progress_rows = (
        (await db.execute(select(ReadingProgress).where(ReadingProgress.book_id == book_id)))
        .scalars()
        .all()
    )
    remaining_set = set(remaining_numbers)
    for progress in progress_rows:
        progress.chapters_read = [
            number
            for number in sorted(set(progress.chapters_read or []))
            if number in remaining_set and number != chapter_number
        ]
        if not remaining_numbers:
            progress.current_chapter = 1
            progress.scroll_pct = 0.0
        elif progress.current_chapter not in remaining_set:
            previous = [number for number in remaining_numbers if number < chapter_number]
            progress.current_chapter = previous[-1] if previous else fallback_chapter


async def _renumber_chapters_after_delete(
    db: AsyncSession,
    *,
    book: Book,
    deleted_chapter_number: int,
) -> None:
    chapters_to_renumber = (
        (
            await db.execute(
                select(Chapter)
                .where(Chapter.book_id == book.id, Chapter.number > deleted_chapter_number)
                .order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )

    for chapter in chapters_to_renumber:
        old_number = chapter.number
        new_number = old_number - 1

        old_key = chapter.s3_key
        new_key = _chapter_storage_key(book.id, new_number)
        if old_key and old_key != new_key:
            try:
                chapter.s3_key = await asyncio.to_thread(move_object, old_key, new_key)
            except STORAGE_IO_EXCEPTIONS:
                chapter.s3_key = new_key

        chapter.number = new_number

        for table, col in [
            (NovelScene, "chapter_number"),
            (ManuscriptAnnotation, "chapter_number"),
            (BookNote, "chapter_number"),
            (WorldNote, "chapter_number"),
            (QuoteEntry, "chapter_number"),
            (CharacterCandidate, "chapter_number"),
            (CharacterMention, "chapter_number"),
            (CharacterSuppression, "chapter_number"),
            (CharacterRelationshipCandidate, "chapter_number"),
            (BetaReadFeedbackItem, "chapter_number"),
            (UserWritingActivity, "chapter_number"),
            (PublicBookAnalyticsEvent, "chapter_number"),
        ]:
            await db.execute(
                update(table)
                .where(
                    table.book_id == book.id,
                    getattr(table, col) == old_number,
                )
                .values(**{col: new_number})
            )

        await db.execute(
            update(NovelScene)
            .where(
                NovelScene.book_id == book.id,
                NovelScene.origin_chapter_number == old_number,
            )
            .values(origin_chapter_number=new_number)
        )

        await db.execute(
            update(CharacterRelationship)
            .where(
                CharacterRelationship.book_id == book.id,
                CharacterRelationship.from_chapter == old_number,
            )
            .values(from_chapter=new_number)
        )
        await db.execute(
            update(CharacterRelationship)
            .where(
                CharacterRelationship.book_id == book.id,
                CharacterRelationship.to_chapter == old_number,
            )
            .values(to_chapter=new_number)
        )

        character_ids_subq = select(Character.id).where(Character.book_id == book.id)
        await db.execute(
            update(CharacterState)
            .where(
                CharacterState.character_id.in_(character_ids_subq),
                CharacterState.at_chapter == old_number,
            )
            .values(at_chapter=new_number)
        )

    progress_rows = (
        (await db.execute(select(ReadingProgress).where(ReadingProgress.book_id == book.id)))
        .scalars()
        .all()
    )
    for progress in progress_rows:
        progress.chapters_read = [
            n - 1 if n > deleted_chapter_number else n
            for n in sorted(set(progress.chapters_read or []))
        ]
        if progress.current_chapter and progress.current_chapter > deleted_chapter_number:
            progress.current_chapter -= 1

    max_remaining = await db.scalar(
        select(func.max(Chapter.number)).where(Chapter.book_id == book.id)
    )
    book.total_chapters = int(max_remaining) if max_remaining is not None else 0


async def delete_chapter(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
) -> None:
    chapter = (
        await db.execute(
            select(Chapter).where(
                Chapter.book_id == book.id,
                Chapter.number == chapter_number,
            )
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")

    affected_character_rows = (
        (
            await db.execute(
                select(CharacterMention.matched_character_id).where(
                    CharacterMention.book_id == book.id,
                    CharacterMention.chapter_number == chapter_number,
                    CharacterMention.matched_character_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    affected_character_ids = {
        character_id
        for character_id in affected_character_rows
        if isinstance(character_id, uuid.UUID)
    }

    snapshot = await snapshot_chapter_version(
        db,
        book,
        chapter,
        note=f"Auto checkpoint before deleting Chapter {chapter_number}",
        snapshot_kind="pre_delete",
    )
    snapshot_version_id = str(snapshot.id) if snapshot is not None else None
    writer_workspace._append_recent_revision_edit(
        book,
        kind="chapter",
        chapter_number=chapter_number,
        before_text=f"Deleted Chapter {chapter_number}: {chapter.title or ''}".strip(),
        after_text="",
        source_version_id=snapshot_version_id,
    )

    await db.execute(
        update(ChapterVersion)
        .where(ChapterVersion.book_id == book.id, ChapterVersion.chapter_id == chapter.id)
        .values(chapter_id=None)
    )
    scene_ids = (
        (
            await db.execute(
                select(NovelScene.id).where(
                    NovelScene.book_id == book.id,
                    NovelScene.chapter_number == chapter_number,
                )
            )
        )
        .scalars()
        .all()
    )
    if scene_ids:
        await db.execute(
            update(SceneVersion)
            .where(
                SceneVersion.book_id == book.id,
                SceneVersion.scene_id.in_(scene_ids),
            )
            .values(scene_id=None, chapter_id=None)
        )
    await db.execute(
        update(SceneVersion)
        .where(SceneVersion.book_id == book.id, SceneVersion.chapter_id == chapter.id)
        .values(chapter_id=None)
    )
    await db.execute(delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    await purge_chapter_derived_content(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        chapter_id=chapter.id,
    )
    await db.execute(
        delete(ManuscriptAnnotation).where(
            ManuscriptAnnotation.book_id == book.id,
            ManuscriptAnnotation.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(BookNote).where(
            BookNote.book_id == book.id,
            BookNote.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(WorldNote).where(
            WorldNote.book_id == book.id,
            WorldNote.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(QuoteEntry).where(
            QuoteEntry.book_id == book.id,
            QuoteEntry.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterCandidate).where(
            CharacterCandidate.book_id == book.id,
            CharacterCandidate.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterMention).where(
            CharacterMention.book_id == book.id,
            CharacterMention.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterRelationshipCandidate).where(
            CharacterRelationshipCandidate.book_id == book.id,
            CharacterRelationshipCandidate.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterSuppression).where(
            CharacterSuppression.book_id == book.id,
            CharacterSuppression.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CustomTag).where(
            CustomTag.book_id == book.id,
            CustomTag.entity_type == ENTITY_TYPE_CHAPTER,
            CustomTag.entity_id == chapter.id,
        )
    )
    await db.execute(delete(Chapter).where(Chapter.id == chapter.id))
    await db.flush()

    remaining_numbers = (
        (
            await db.execute(
                select(Chapter.number)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )
    book.total_chunks = await db.scalar(
        select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book.id)
    )
    await _repair_progress_after_chapter_delete(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        remaining_numbers=[int(number) for number in remaining_numbers],
    )
    await _renumber_chapters_after_delete(db, book=book, deleted_chapter_number=chapter_number)
    await _recompute_character_chapter_aggregates(
        db,
        book_id=book.id,
        character_ids=affected_character_ids,
    )
    if getattr(book, "is_editor_project", False):
        from app.services.editor_project_service import cancel_rebuild_for_manual_edit

        await cancel_rebuild_for_manual_edit(
            db,
            book,
            reason=f"Chapter {chapter_number} was removed while reprocessing was in progress.",
        )
    writer_workspace.touch_public_book_updated_at(book)
    await db.commit()


async def restore_chapter_version(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(ChapterVersion).where(
                ChapterVersion.book_id == book.id, ChapterVersion.id == version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Chapter version not found")

    chapter = (
        await db.execute(
            select(Chapter).where(
                Chapter.book_id == book.id, Chapter.number == version.chapter_number
            )
        )
    ).scalar_one_or_none()
    if chapter is not None:
        await snapshot_chapter_version(
            db,
            book,
            chapter,
            note=f"Snapshot before restoring Chapter {chapter.number}",
            snapshot_kind="pre_restore",
            restored_from_version_id=version.id,
        )
        await purge_chapter_derived_content(
            db, book_id=book.id, chapter_number=chapter.number, chapter_id=chapter.id
        )
        await db.delete(chapter)
        await db.flush()

    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = manuscript.deserialize_manuscript_content(raw)
    next_text = str(stored.get("text") or "")
    next_html = cast(str | None, stored.get("html"))
    replacement_key = await asyncio.to_thread(
        upload_binary,
        f"books/{book.user_id}/{book.id}/chapters/{version.chapter_number}/{uuid.uuid4()}.txt",
        manuscript.serialize_manuscript_content(next_text, next_html).encode("utf-8"),
        "text/plain; charset=utf-8",
    )
    restored_chapter = Chapter(
        book_id=book.id,
        number=version.chapter_number,
        content_version=(int(chapter.content_version or 1) + 1) if chapter is not None else 1,
        title=version.title,
        s3_key=replacement_key,
        word_count=_count_words(next_text),
        processed=False,
    )
    db.add(restored_chapter)
    writer_workspace.touch_public_book_updated_at(book)
    await db.commit()
    await db.refresh(restored_chapter)
    return {
        "chapter_number": restored_chapter.number,
        "title": restored_chapter.title,
        "text": next_text,
        "html": next_html,
    }


async def list_chapter_versions(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
    limit: int = 12,
) -> list[dict]:
    versions = (
        (
            await db.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.book_id == book.id,
                    ChapterVersion.chapter_number == chapter_number,
                )
                .order_by(ChapterVersion.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(version.id),
            "chapter_number": version.chapter_number,
            "title": version.title,
            "word_count": version.word_count,
            "note": version.note,
            "snapshot_kind": version.snapshot_kind,
            "restore_status": version.restore_status,
            "restore_error": public_restore_error(version),
            "restore_task_id": version.restore_task_id,
            "restore_started_at": version.restore_started_at,
            "restore_completed_at": version.restore_completed_at,
            "created_at": version.created_at,
        }
        for version in versions
    ]
