from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.core.database import get_db
from app.core.storage import upload_book_bytes
from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import CharacterRelationship, QuoteEntry
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.profile_builder import build_description
from app.api.deps.auth import get_current_user
from app.api.deps.subscription import check_upload_limit
from app.workers.tasks.extraction_tasks import process_book_task
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone
import uuid
import bleach

router = APIRouter()


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    author: str | None
    genre: str | None
    format: str
    status: str
    total_chapters: int | None
    total_tokens: int | None
    is_truncated: bool
    series_name: str | None
    series_order: int | None
    is_public: bool
    public_description: str | None
    copyright_warning: bool
    archived_at: datetime | None
    hidden_at: datetime | None
    created_at: datetime


class SeriesBody(BaseModel):
    series_name: str | None = None
    series_order: int | None = None


@router.post("/upload", status_code=202)
async def upload_book_endpoint(
    file: UploadFile = File(...),
    title: str = Form(...),
    genre: str | None = Form(None),
    author: str | None = Form(None),
    visibility: str = Form("private"),
    description: str | None = Form(None),
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
    book = Book(user_id=current_user.id, title=title, genre=genre, author=author,
                format=fmt, s3_key=s3_key, status="pending", is_public=is_public, public_description=description)
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

    book.series_name = series_name or None
    book.series_order = body.series_order if series_name else None
    await db.commit()
    await db.refresh(book)
    return book


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
    return result.scalars().all()


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
    return book


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
    return book


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
    return book


@router.get("/{book_id}/characters")
async def get_book_characters(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await consolidate_characters(db, book_id)
    result = await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name))
    characters = result.scalars().all()
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
    return book
