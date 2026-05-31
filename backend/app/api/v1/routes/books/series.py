import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .core import _clean_text, _clean_optional_text
from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.models.book import Book, Series, SeriesBook
from app.models.progress import ReadingProgress
from app.schemas.books import (
    BookOut,
    SeriesBibleOut,
    SeriesBody,
    SeriesBookStatusBody,
    SeriesCreateBody,
    SeriesMembershipBody,
    SeriesOut,
)
from app.utils.book_utils import (
    book_out,
    build_single_series_out,
    build_series_bible_payload,
    build_series_out_list,
    get_owned_book,
    get_owned_series,
)

router = APIRouter()


@router.put("/{book_id}/series", response_model=BookOut)
async def update_book_series(
    book_id: uuid.UUID,
    body: SeriesBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")

    series_name = _clean_text(body.series_name)
    if body.series_order is not None and body.series_order < 1:
        raise HTTPException(400, "Series order must be at least 1")

    if not series_name:
        if book.primary_series_id:
            membership = (
                await db.execute(
                    select(SeriesBook).where(
                        SeriesBook.book_id == book.id,
                        SeriesBook.series_id == book.primary_series_id,
                    )
                )
            ).scalar()
            if membership:
                await db.delete(membership)
        book.primary_series_id = None
        book.series_name = None
        book.series_order = None
        await db.commit()
        await db.refresh(book)
        return await book_out(db, book, current_user.id)

    series = (
        await db.execute(
            select(Series).where(Series.user_id == current_user.id, Series.name == series_name)
        )
    ).scalar()
    if not series:
        series = Series(user_id=current_user.id, name=series_name)
        db.add(series)
        await db.flush()

    membership = (
        await db.execute(
            select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id)
        )
    ).scalar()
    if not membership:
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
    membership.position = body.series_order
    book.primary_series_id = series.id
    book.series_name = series.name
    book.series_order = body.series_order
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.get("/series")
async def list_series(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    total_result = await db.execute(
        select(func.count()).select_from(Series).where(Series.user_id == current_user.id)
    )
    total = total_result.scalar() or 0
    rows_result = await db.execute(
        select(Series)
        .where(Series.user_id == current_user.id)
        .order_by(Series.created_at.desc(), Series.name)
        .limit(limit)
        .offset(offset)
    )
    rows = list(rows_result.scalars().all())
    series_ids = [series.id for series in rows]
    membership_rows = (
        await db.execute(
            select(SeriesBook, Book)
            .join(Book, Book.id == SeriesBook.book_id)
            .where(SeriesBook.series_id.in_(series_ids), Book.user_id == current_user.id)
            .order_by(SeriesBook.series_id, SeriesBook.position, Book.created_at)
        )
    ).all() if series_ids else []
    items = await build_series_out_list(
        db,
        series_rows=rows,
        membership_rows=membership_rows,
        user_id=current_user.id,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


@router.get("/series/{series_id}/bible", response_model=SeriesBibleOut)
async def get_series_bible(
    series_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    return await build_series_bible_payload(db, series=series)


@router.post("/series", response_model=SeriesOut, status_code=201)
async def create_series(
    body: SeriesCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    name = _clean_text(body.name)
    description = _clean_optional_text(body.description)
    if not name:
        raise HTTPException(400, "Series name is required")

    existing = (
        await db.execute(select(Series).where(Series.user_id == current_user.id, Series.name == name))
    ).scalar()
    if existing:
        raise HTTPException(400, "Series already exists")

    series = Series(user_id=current_user.id, name=name, description=description)
    db.add(series)
    await db.commit()
    await db.refresh(series)
    return SeriesOut(id=series.id, name=series.name, description=series.description, created_at=series.created_at, books=[])


@router.post("/series/{series_id}/books/{book_id}", response_model=SeriesOut)
async def add_book_to_series(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    body: SeriesMembershipBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    book = await get_owned_book(db, book_id, current_user.id)
    if body.position is not None and body.position < 1:
        raise HTTPException(400, "Position must be at least 1")

    membership = (
        await db.execute(select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id))
    ).scalar()
    if not membership:
        membership = SeriesBook(series_id=series.id, book_id=book.id)
        db.add(membership)
    membership.position = body.position
    book.primary_series_id = series.id
    book.series_name = series.name
    book.series_order = body.position
    await db.commit()
    return await build_single_series_out(db, series=series, user_id=current_user.id)


@router.delete("/series/{series_id}/books/{book_id}", response_model=SeriesOut)
async def remove_book_from_series(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    book = await get_owned_book(db, book_id, current_user.id)
    membership = (
        await db.execute(select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id))
    ).scalar()
    if not membership:
        raise HTTPException(404, "Series membership not found")

    await db.delete(membership)
    if book.primary_series_id == series.id:
        book.primary_series_id = None
        book.series_name = None
        book.series_order = None
    await db.commit()
    return await build_single_series_out(db, series=series, user_id=current_user.id)


@router.put("/series/{series_id}/books/{book_id}/status", response_model=BookOut)
async def set_series_book_status(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    body: SeriesBookStatusBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await get_owned_series(db, series_id, current_user.id)
    book = await get_owned_book(db, book_id, current_user.id)
    membership = (
        await db.execute(select(SeriesBook).where(SeriesBook.series_id == series.id, SeriesBook.book_id == book.id))
    ).scalar()
    if not membership:
        raise HTTPException(404, "Series membership not found")

    membership.marked_complete = body.marked_complete
    progress = (
        await db.execute(select(ReadingProgress).where(ReadingProgress.user_id == current_user.id, ReadingProgress.book_id == book.id))
    ).scalar()
    total = book.total_chapters or 0
    if body.marked_complete and total > 0:
        chapters_read = list(range(1, total + 1))
        if progress is None:
            progress = ReadingProgress(
                user_id=current_user.id, book_id=book.id,
                current_chapter=total, scroll_pct=1.0, chapters_read=chapters_read,
            )
            db.add(progress)
        else:
            progress.current_chapter = total
            progress.scroll_pct = 1.0
            progress.chapters_read = chapters_read
            progress.last_read = datetime.now(UTC)
    await db.commit()
    enriched = await book_out(db, book, current_user.id)
    enriched.marked_complete_in_series = membership.marked_complete
    return enriched
