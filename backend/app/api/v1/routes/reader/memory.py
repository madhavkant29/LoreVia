import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_recall
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import cache_get, cache_set, key_memory_recall
from app.engine.analysis.recall import generate_recall
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import ChapterSummary, PlotThread
from app.models.progress import ReadingProgress
from app.schemas.reader import PlotThreadOut, UpdatePlotThreadBody
from app.utils.billing_utils import require_author_access
from app.utils.plot_thread_utils import derive_plot_thread_status
from app.utils.reader_utils import list_plot_threads, update_plot_thread_note

router = APIRouter()


@router.get("/{book_id}/plot-threads", response_model=list[PlotThreadOut])
async def get_plot_threads(
    book_id: uuid.UUID,
    chapter: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)
    return await list_plot_threads(db, book_id, chapter)


@router.put("/{book_id}/plot-threads/{thread_id}", response_model=PlotThreadOut)
async def save_plot_thread_note(
    book_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: UpdatePlotThreadBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)

    thread = await update_plot_thread_note(db, book_id, thread_id, body.note, body.status)
    if thread is None:
        raise HTTPException(404, "Plot thread not found")
    return thread


@router.get("/{book_id}/recall")
async def memory_recall(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_recall),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)
    book_title = book.title

    cache_key = key_memory_recall(str(current_user.id), str(book_id))
    cached = await cache_get(cache_key)
    if cached:
        return {"recall": cached, "cached": True}

    progress_result = await db.execute(
        select(ReadingProgress).where(
            ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book_id
        )
    )
    progress = progress_result.scalar()
    if not progress:
        return {"recall": None}

    last_chapter = progress.current_chapter
    chapter_result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.number == last_chapter)
    )
    chapter = chapter_result.scalar()

    recent_summary = ""
    if chapter:
        summ_result = await db.execute(
            select(ChapterSummary).where(
                ChapterSummary.chapter_id == chapter.id, ChapterSummary.mode == "short"
            )
        )
        summ = summ_result.scalar()
        if summ:
            recent_summary = summ.content

    chars_result = await db.execute(
        select(Character.name)
        .where(Character.book_id == book_id, Character.first_chapter <= last_chapter)
        .limit(8)
    )
    chars = chars_result.scalars().all()

    open_threads_result = await db.execute(
        select(
            PlotThread.title,
            PlotThread.status,
            PlotThread.introduced_at,
            PlotThread.last_mentioned_at,
            PlotThread.resolved_at,
        )
        .where(
            PlotThread.book_id == book_id,
            PlotThread.introduced_at <= last_chapter,
        )
        .limit(6)
    )
    open_threads = [
        title
        for title, status, introduced_at, last_mentioned_at, resolved_at in open_threads_result.all()
        if derive_plot_thread_status(
            status,
            introduced_at=introduced_at,
            last_mentioned_at=last_mentioned_at or introduced_at,
            resolved_at=resolved_at,
            current_chapter=last_chapter,
        )
        not in {"resolved", "abandoned"}
    ][:3]

    # Release the request-scoped connection before the external LLM call.
    await db.rollback()

    recall_text = await generate_recall(
        title=book_title,
        last_chapter=last_chapter,
        recent_summary=recent_summary,
        active_characters=list(chars),
        open_threads=list(open_threads),
        user_id=current_user.id,
        book_id=book_id,
        usage_db=None,
    )

    await cache_set(cache_key, recall_text, settings.REDIS_TTL_RECALL)
    return {"recall": recall_text, "last_chapter": last_chapter}
