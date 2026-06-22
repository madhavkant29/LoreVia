import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.core.redis import mark_reader_progress_cache_dirty
from app.models.progress import ReadingProgress
from app.utils.beta_read_utils import sync_beta_assignments_for_reader_book
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.reader_utils import (
    build_reading_progress_payload,
)

router = APIRouter()


@router.get("/{book_id}/progress")
async def get_progress(
    book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    return await build_reading_progress_payload(
        db,
        book=book,
        current_user=current_user,
        collaborator=collaborator,
    )


@router.put("/{book_id}/progress")
async def update_progress(
    book_id: uuid.UUID,
    current_chapter: int,
    scroll_pct: float,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, current_chapter):
        raise HTTPException(403, "This share does not include that chapter.")

    p = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
            )
        )
    ).scalar()
    if p:
        read_set = set(p.chapters_read or [])
        read_set.add(current_chapter)
        p.current_chapter = current_chapter
        p.scroll_pct = scroll_pct
        p.chapters_read = sorted(read_set)
        p.last_read = datetime.now(UTC)
    else:
        db.add(
            ReadingProgress(
                user_id=current_user.id,
                book_id=book_id,
                current_chapter=current_chapter,
                scroll_pct=scroll_pct,
                chapters_read=[current_chapter],
            )
        )
    await db.commit()
    await mark_reader_progress_cache_dirty(str(book_id), str(current_user.id))
    await sync_beta_assignments_for_reader_book(db, book_id=book_id, current_user=current_user)
    return {"ok": True}


@router.put("/{book_id}/progress/mark-book-read")
async def mark_book_read(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)

    total = book.total_chapters or 0
    if total <= 0:
        raise HTTPException(400, "Book has no chapters to mark as read")

    chapters_read = [
        number
        for number in range(1, total + 1)
        if collaboration_allows_chapter(collaborator, number)
    ]
    if not chapters_read:
        raise HTTPException(403, "This share does not include any chapters.")
    progress = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
            )
        )
    ).scalar()

    if progress is None:
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book_id,
            current_chapter=max(chapters_read),
            scroll_pct=1.0,
            chapters_read=chapters_read,
        )
        db.add(progress)
    else:
        progress.current_chapter = max(chapters_read)
        progress.scroll_pct = 1.0
        progress.chapters_read = chapters_read
        progress.last_read = datetime.now(UTC)

    await db.commit()
    await mark_reader_progress_cache_dirty(str(book_id), str(current_user.id))
    await sync_beta_assignments_for_reader_book(db, book_id=book_id, current_user=current_user)
    return {
        "ok": True,
        "current_chapter": max(chapters_read),
        "chapters_read_count": len(chapters_read),
        "percent_complete": 100.0,
        "chapters_left": 0,
    }


@router.put("/{book_id}/progress/chapter-status")
async def update_chapter_read_status(
    book_id: uuid.UUID,
    chapter: int,
    read: bool,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")

    progress = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
            )
        )
    ).scalar()

    if progress is None:
        chapters_read = [chapter] if read else []
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=book_id,
            current_chapter=max(chapter, 1),
            scroll_pct=0.0,
            chapters_read=chapters_read,
        )
        db.add(progress)
    else:
        read_set = set(progress.chapters_read or [])
        if read:
            read_set.add(chapter)
            progress.current_chapter = max(progress.current_chapter, chapter)
        else:
            read_set.discard(chapter)
        progress.chapters_read = sorted(read_set)
        progress.last_read = datetime.now(UTC)

    await db.commit()
    await mark_reader_progress_cache_dirty(str(book_id), str(current_user.id))
    await sync_beta_assignments_for_reader_book(db, book_id=book_id, current_user=current_user)
    return {"ok": True, "chapter": chapter, "read": read}
