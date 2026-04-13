import asyncio
import mimetypes
import uuid
from datetime import datetime, timezone

import bleach
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.core.config import settings
from app.core.database import get_db
from app.core.storage import download_book, get_presigned_url, upload_binary, upload_book_bytes
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.character import Character
from app.models.intelligence import CharacterRelationship, QuoteEntry
from app.models.progress import ReadingProgress
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.entity_filters import is_displayable_character_entity
from app.engine.character.profile_builder import build_description
from app.api.deps.auth import get_current_user
from app.api.deps.subscription import check_upload_limit
from app.core.security import create_asset_token, decode_token
from app.workers.tasks.extraction_tasks import process_book_task
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    author: str | None
    genre: str | None
    format: str
    status: str
    cover_url: str | None = None
    total_chapters: int | None
    total_tokens: int | None
    is_truncated: bool
    primary_series_id: uuid.UUID | None = None
    series_name: str | None
    series_order: int | None
    is_public: bool
    public_description: str | None
    copyright_warning: bool
    archived_at: datetime | None
    hidden_at: datetime | None
    created_at: datetime
    progress_pct: float | None = None
    chapters_read_count: int | None = None
    chapters_left: int | None = None
    marked_complete_in_series: bool | None = None


class SeriesOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    books: list[BookOut]


class SeriesBody(BaseModel):
    series_name: str | None = None
    series_order: int | None = None


class SeriesCreateBody(BaseModel):
    name: str
    description: str | None = None


class SeriesMembershipBody(BaseModel):
    position: int | None = None


class SeriesBookStatusBody(BaseModel):
    marked_complete: bool = True


class PublicUserStats(BaseModel):
    total_books_read: int
    total_words_read: int


class PrivateUserStats(BaseModel):
    total_uploads: int
    total_token_consumption: int
    total_chapters_tracked: int
    saved_quotes: int


class UserStatsOut(BaseModel):
    public: PublicUserStats
    private: PrivateUserStats


@router.post("/upload", status_code=202)
async def upload_book_endpoint(
    file: UploadFile = File(...),
    cover_file: UploadFile | None = File(None),
    title: str = Form(...),
    genre: str | None = Form(None),
    author: str | None = Form(None),
    visibility: str = Form("private"),
    description: str | None = Form(None),
    auto_extract_cover: str = Form("true"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(check_upload_limit),
):
    # Sanitize title, author, genre
    title = bleach.clean(title, tags=[], strip=True) if title else ""
    if author:
        author = bleach.clean(author, tags=[], strip=True)
    if genre:
        genre = bleach.clean(genre, tags=[], strip=True)
    if description:
        description = bleach.clean(description, tags=[], strip=True)
    if not file.filename:
        raise HTTPException(400, "No file")
    if visibility not in {"private", "public"}:
        raise HTTPException(400, "Invalid visibility")
    if not title.strip():
        raise HTTPException(400, "Title is required")

    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        fmt = "pdf"
    elif filename.endswith(".epub"):
        fmt = "epub"
    else:
        raise HTTPException(400, "Only PDF and EPUB files are supported")

    is_public = visibility == "public"
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    s3_key = upload_book_bytes(raw, str(current_user.id), file.filename)
    cover_s3_key = None
    if not _as_bool(auto_extract_cover) and cover_file is not None and cover_file.filename:
        cover_raw = await cover_file.read()
        if cover_raw:
            suffix = cover_file.filename.rsplit(".", 1)[-1].lower() if "." in cover_file.filename else "png"
            content_type = cover_file.content_type or f"image/{suffix}"
            cover_s3_key = upload_binary(
                f"covers/{current_user.id}/{uuid.uuid4()}.{suffix}",
                cover_raw,
                content_type,
            )
    book = Book(user_id=current_user.id, title=title, genre=genre, author=author,
                format=fmt, s3_key=s3_key, cover_s3_key=cover_s3_key, status="pending", is_public=is_public, public_description=description)
    db.add(book)
    await db.commit()
    await db.refresh(book)

    process_book_task.apply_async(args=[str(book.id)], queue="extraction")
    return {"book_id": str(book.id), "status": "processing",
            "copyright_warning": False, "visibility": visibility}


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

    series_name = bleach.clean((body.series_name or "").strip(), tags=[], strip=True)
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
        return await _book_out(db, book)

    series = (
        await db.execute(
            select(Series).where(
                Series.user_id == current_user.id,
                Series.name == series_name,
            )
        )
    ).scalar()
    if not series:
        series = Series(user_id=current_user.id, name=series_name)
        db.add(series)
        await db.flush()

    membership = (
        await db.execute(
            select(SeriesBook).where(
                SeriesBook.series_id == series.id,
                SeriesBook.book_id == book.id,
            )
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
    return await _book_out(db, book)


@router.get("/series", response_model=list[SeriesOut])
async def list_series(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        await db.execute(
            select(Series)
            .where(Series.user_id == current_user.id)
            .order_by(Series.created_at.desc(), Series.name)
        )
    ).scalars().all()
    output: list[SeriesOut] = []
    for series in rows:
        memberships = (
            await db.execute(
                select(SeriesBook, Book)
                .join(Book, Book.id == SeriesBook.book_id)
                .where(
                    SeriesBook.series_id == series.id,
                    Book.user_id == current_user.id,
                )
                .order_by(SeriesBook.position, Book.created_at)
            )
        ).all()
        books = []
        for membership, book in memberships:
            enriched = await _book_out(db, book, current_user.id)
            enriched.marked_complete_in_series = membership.marked_complete
            books.append(enriched)
        output.append(
            SeriesOut(
                id=series.id,
                name=series.name,
                description=series.description,
                created_at=series.created_at,
                books=books,
            )
        )
    return output


@router.post("/series", response_model=SeriesOut, status_code=201)
async def create_series(
    body: SeriesCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    name = bleach.clean(body.name.strip(), tags=[], strip=True)
    description = bleach.clean((body.description or "").strip(), tags=[], strip=True) or None
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
    series = await _get_owned_series(db, series_id, current_user.id)
    book = await _get_owned_book(db, book_id, current_user.id)
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
    return next(item for item in await list_series(db, current_user) if item.id == series.id)


@router.delete("/series/{series_id}/books/{book_id}", response_model=SeriesOut)
async def remove_book_from_series(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await _get_owned_series(db, series_id, current_user.id)
    book = await _get_owned_book(db, book_id, current_user.id)
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
    return next(item for item in await list_series(db, current_user) if item.id == series.id)


@router.put("/series/{series_id}/books/{book_id}/status", response_model=BookOut)
async def set_series_book_status(
    series_id: uuid.UUID,
    book_id: uuid.UUID,
    body: SeriesBookStatusBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await _get_owned_series(db, series_id, current_user.id)
    book = await _get_owned_book(db, book_id, current_user.id)
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
                user_id=current_user.id,
                book_id=book.id,
                current_chapter=total,
                scroll_pct=1.0,
                chapters_read=chapters_read,
            )
            db.add(progress)
        else:
            progress.current_chapter = total
            progress.scroll_pct = 1.0
            progress.chapters_read = chapters_read
            progress.last_read = datetime.now(timezone.utc)
    await db.commit()
    enriched = await _book_out(db, book, current_user.id)
    enriched.marked_complete_in_series = membership.marked_complete
    return enriched


@router.get("", response_model=list[BookOut])
async def list_books(
    include_hidden: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    stmt = select(Book).where(Book.user_id == current_user.id)
    if not include_hidden:
        stmt = stmt.where(Book.hidden_at.is_(None))
    result = await db.execute(stmt.order_by(Book.created_at.desc()))
    books = result.scalars().all()
    return [await _book_out(db, book, current_user.id) for book in books]


@router.get("/stats", response_model=UserStatsOut)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    books = (
        await db.execute(
            select(Book)
            .where(Book.user_id == current_user.id)
            .order_by(Book.created_at.desc())
        )
    ).scalars().all()

    progress_rows = (
        await db.execute(
            select(ReadingProgress)
            .where(ReadingProgress.user_id == current_user.id)
        )
    ).scalars().all()
    progress_by_book = {progress.book_id: progress for progress in progress_rows}

    total_books_read = 0
    total_words_read = 0
    total_chapters_tracked = 0

    for book in books:
        total_chapters_tracked += book.total_chapters or 0
        progress = progress_by_book.get(book.id)
        read_chapters = sorted(set(progress.chapters_read or [])) if progress and progress.chapters_read else []
        if book.total_chapters and len(read_chapters) >= book.total_chapters:
            total_books_read += 1
        total_words_read += await _compute_words_read_for_book(db, book, progress)

    total_uploads = len(books)
    total_token_consumption = int(sum(book.total_tokens or 0 for book in books))
    saved_quotes = int(
        (
            await db.execute(
                select(func.count(QuoteEntry.id)).where(QuoteEntry.user_id == current_user.id)
            )
        ).scalar()
        or 0
    )

    return UserStatsOut(
        public=PublicUserStats(
            total_books_read=total_books_read,
            total_words_read=total_words_read,
        ),
        private=PrivateUserStats(
            total_uploads=total_uploads,
            total_token_consumption=total_token_consumption,
            total_chapters_tracked=total_chapters_tracked,
            saved_quotes=saved_quotes,
        ),
    )


@router.get("/quotes")
async def list_saved_quotes(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    rows = (await db.execute(
        select(QuoteEntry, Book.title, Chapter.title)
        .join(Book, Book.id == QuoteEntry.book_id)
        .outerjoin(
            Chapter,
            and_(
                Chapter.book_id == QuoteEntry.book_id,
                Chapter.number == QuoteEntry.chapter_number,
            ),
        )
        .where(QuoteEntry.user_id == current_user.id)
        .order_by(QuoteEntry.created_at.desc())
    )).all()
    return [
        {
            "id": str(quote.id),
            "book_id": str(quote.book_id),
            "book_title": book_title,
            "chapter_number": quote.chapter_number,
            "chapter_title": chapter_title,
            "character_name": quote.character_name,
            "quote_text": quote.quote_text,
            "note": quote.note,
            "created_at": quote.created_at,
        }
        for quote, book_title, chapter_title in rows
    ]


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    return await _book_out(db, book, current_user.id)


@router.get("/{book_id}/cover")
async def get_book_cover(book_id: uuid.UUID, token: str = Query(...), db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"book-cover:{book.id}"
    ):
        raise HTTPException(401, "Invalid cover token")

    await _ensure_book_cover(db, book)
    if not book.cover_s3_key:
        raise HTTPException(404, "Cover not found")

    raw = await asyncio.to_thread(download_book, book.cover_s3_key)
    media_type = mimetypes.guess_type(book.cover_s3_key)[0] or "image/png"
    return Response(content=raw, media_type=media_type)


@router.put("/{book_id}/archive", response_model=BookOut)
async def archive_book(
    book_id: uuid.UUID,
    archived: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book.archived_at = datetime.now(timezone.utc) if archived else None
    if archived:
        book.hidden_at = None
    await db.commit()
    await db.refresh(book)
    return await _book_out(db, book, current_user.id)


@router.put("/{book_id}/hide", response_model=BookOut)
async def hide_book(
    book_id: uuid.UUID,
    hidden: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book.hidden_at = datetime.now(timezone.utc) if hidden else None
    if hidden:
        book.archived_at = None
    await db.commit()
    await db.refresh(book)
    return await _book_out(db, book, current_user.id)


@router.get("/{book_id}/characters")
async def get_book_characters(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id)
    result = await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name))
    characters = [char for char in result.scalars().all() if _is_displayable_character(char)]
    rel_result = await db.execute(
        select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
    )
    relationships = rel_result.scalars().all()

    char_by_id = {char.id: char for char in characters}
    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}

    for rel in relationships:
        a = char_by_id.get(rel.character_a_id)
        b = char_by_id.get(rel.character_b_id)
        if not a or not b:
            continue

        summary_a = _relationship_summary_for_character(rel, a.name, b.name, a.name)
        summary_b = _relationship_summary_for_character(rel, a.name, b.name, b.name)
        if summary_a:
            _append_unique_summary(rel_summaries, rel_keys, str(a.id), f"{rel.rel_type}:{b.name}".lower(), summary_a)
        if summary_b:
            _append_unique_summary(rel_summaries, rel_keys, str(b.id), f"{rel.rel_type}:{a.name}".lower(), summary_b)

    return [
        {
            "id": str(char.id),
            "book_id": str(char.book_id),
            "name": char.name,
            "aliases": char.aliases or [],
            "role": char.role,
            "first_chapter": char.first_chapter,
            "trait_state": char.trait_state or {},
            "description": _merge_description_with_relationships(
                build_description(char.trait_state or {}, char.archetype),
                _dedupe_preserve_order(rel_summaries.get(str(char.id), [])),
            ),
            "personality_tags": char.personality_tags or [],
            "motivations": char.motivations or [],
            "fears": char.fears or [],
            "archetype": char.archetype,
            "arc_summary": char.arc_summary,
            "relationship_summaries": _dedupe_preserve_order(rel_summaries.get(str(char.id), [])),
        }
        for char in characters
    ]


def _is_displayable_character(char: Character) -> bool:
    name = " ".join((char.name or "").split())
    if not name:
        return False
    return is_displayable_character_entity(
        name,
        role=char.role,
        aliases=char.aliases or [],
        personality_tags=char.personality_tags or [],
        motivations=char.motivations or [],
        fears=char.fears or [],
        archetype=char.archetype or char.arc_summary,
        trait_state=char.trait_state or {},
        relationship_count=0,
    )


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _relationship_summary_for_character(rel: CharacterRelationship, name_a: str, name_b: str, perspective_name: str) -> str | None:
    counterpart = name_b if perspective_name == name_a else name_a
    rel_type = (rel.rel_type or "connection").replace("_", " ").strip()
    if not rel_type:
        rel_type = "connection"
    return f"{rel_type.capitalize()} connection with {counterpart}."


def _append_unique_summary(
    rel_summaries: dict[str, list[str]],
    rel_keys: dict[str, set[str]],
    char_id: str,
    signature: str,
    summary: str,
) -> None:
    bucket = rel_keys.setdefault(char_id, set())
    if signature in bucket:
        return
    bucket.add(signature)
    rel_summaries.setdefault(char_id, []).append(summary)


def _relationship_summary(description: str | None, rel_type: str | None, name_a: str, name_b: str) -> str | None:
    if description:
        cleaned = " ".join(description.split())
        return cleaned
    if rel_type:
        return f"{name_a} has a {rel_type} relationship with {name_b}."
    return None


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _merge_description_with_relationships(description: str, relationship_summaries: list[str]) -> str:
    preview = relationship_summaries[:2]
    if not preview:
        return description
    return f"{description}. {' '.join(preview)}"


@router.delete("/{book_id}", response_model=BookOut)
async def delete_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    book.hidden_at = datetime.now(timezone.utc)
    book.archived_at = None
    await db.commit()
    await db.refresh(book)
    return await _book_out(db, book, current_user.id)


async def _book_out(db: AsyncSession, book: Book, user_id: uuid.UUID) -> BookOut:
    await _ensure_book_cover(db, book)
    progress = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.book_id == book.id,
                ReadingProgress.user_id == user_id,
            )
        )
    ).scalars().first()
    chapters_read_count = len(set(progress.chapters_read or [])) if progress else 0
    total = book.total_chapters or 0
    percent = round((chapters_read_count / total) * 100, 1) if total else 0.0
    chapters_left = max(total - chapters_read_count, 0) if total else None
    cover_url = _cover_url_for_book(book)
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        genre=book.genre,
        format=book.format,
        status=book.status,
        cover_url=cover_url,
        total_chapters=book.total_chapters,
        total_tokens=book.total_tokens,
        is_truncated=book.is_truncated,
        primary_series_id=book.primary_series_id,
        series_name=book.series_name,
        series_order=book.series_order,
        is_public=book.is_public,
        public_description=book.public_description,
        copyright_warning=book.copyright_warning,
        archived_at=book.archived_at,
        hidden_at=book.hidden_at,
        created_at=book.created_at,
        progress_pct=percent,
        chapters_read_count=chapters_read_count,
        chapters_left=chapters_left,
    )


async def _ensure_book_cover(db: AsyncSession, book: Book) -> None:
    if book.cover_s3_key or book.format != "pdf":
        return
    if not book.s3_key:
        return

    from app.parsers.pdf_parser import extract_first_page_cover

    raw = await asyncio.to_thread(download_book, book.s3_key)
    cover = await asyncio.to_thread(extract_first_page_cover, raw)
    if not cover:
        return

    cover_bytes, content_type = cover
    book.cover_s3_key = await asyncio.to_thread(
        upload_binary,
        f"covers/{book.user_id}/{uuid.uuid4()}.png",
        cover_bytes,
        content_type,
    )
    await db.commit()
    await db.refresh(book)


def _cover_url_for_book(book: Book) -> str | None:
    if not book.cover_s3_key:
        return None
    presigned = get_presigned_url(book.cover_s3_key)
    if presigned:
        return presigned
    token = create_asset_token(str(book.user_id), f"book-cover:{book.id}", expires_minutes=120)
    return f"{settings.API_V1_PREFIX}/books/{book.id}/cover?token={token}"


async def _compute_words_read_for_book(db: AsyncSession, book: Book, progress: ReadingProgress | None) -> int:
    if progress is None:
        return 0

    read_chapters = sorted(set(progress.chapters_read or []))
    total_words = 0
    counted_chapters = set(read_chapters)

    for chapter_number in read_chapters:
        total_words += await _chapter_word_count(db, book.id, chapter_number)

    current_chapter = progress.current_chapter or 0
    if current_chapter > 0 and current_chapter not in counted_chapters:
        chapter_words = await _chapter_word_count(db, book.id, current_chapter)
        total_words += int(round(chapter_words * max(0.0, min(progress.scroll_pct or 0.0, 1.0))))

    return total_words


async def _chapter_word_count(db: AsyncSession, book_id: uuid.UUID, chapter_number: int) -> int:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_number)
        )
    ).scalar()
    if chapter is None:
        return 0
    if chapter.word_count:
        return chapter.word_count
    if not chapter.s3_key:
        return 0
    try:
        from app.core.storage import download_book

        text = download_book(chapter.s3_key).decode("utf-8", errors="ignore")
    except Exception:
        return 0
    return len(text.replace("\r", " ").replace("\n", " ").split())


async def _get_owned_book(db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> Book:
    book = await db.get(Book, book_id)
    if not book or book.user_id != user_id:
        raise HTTPException(404, "Book not found")
    return book


async def _get_owned_series(db: AsyncSession, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
    series = await db.get(Series, series_id)
    if not series or series.user_id != user_id:
        raise HTTPException(404, "Series not found")
    return series
