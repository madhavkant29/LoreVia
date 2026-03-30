from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.storage import upload_book
from app.models.book import Book
from app.models.character import Character
from app.models.intelligence import CharacterRelationship
from app.engine.character.consolidator import consolidate_characters
from app.engine.character.profile_builder import build_description
from app.api.deps.auth import get_current_user
from app.api.deps.subscription import check_upload_limit
from app.utils.external.isbn_lookup import extract_isbn_from_pdf
from app.utils.compliance.copyright_check import check_isbn
from app.workers.tasks.extraction_tasks import process_book_task
from pydantic import BaseModel, ConfigDict
from datetime import datetime
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
    created_at: datetime


@router.post("/upload", status_code=202)
async def upload_book_endpoint(
    file: UploadFile = File(...),
    title: str = Form(...),
    genre: str | None = Form(None),
    author: str | None = Form(None),
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
    if not file.filename:
        raise HTTPException(400, "No file")
    fmt = "pdf" if file.filename.endswith(".pdf") else "epub"
    raw = await file.read()
    isbn = extract_isbn_from_pdf(raw) if fmt == "pdf" else None
    copyright_info = await check_isbn(isbn) if isbn else {"found": False}

    import io
    s3_key = upload_book(io.BytesIO(raw), str(current_user.id), file.filename)
    book = Book(user_id=current_user.id, title=title, genre=genre, author=author,
                format=fmt, s3_key=s3_key, isbn=isbn, status="pending")
    db.add(book)
    await db.commit()
    await db.refresh(book)

    process_book_task.apply_async(args=[str(book.id)], queue="extraction")
    return {"book_id": str(book.id), "status": "processing",
            "copyright_warning": copyright_info.get("found", False)}


@router.get("", response_model=list[BookOut])
async def list_books(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    result = await db.execute(
        select(Book).where(Book.user_id == current_user.id).order_by(Book.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
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

    for rel in relationships:
        a = char_by_id.get(rel.character_a_id)
        b = char_by_id.get(rel.character_b_id)
        if not a or not b:
            continue

        summary = _relationship_summary(rel.description, rel.rel_type, a.name, b.name)
        if summary:
            rel_summaries.setdefault(str(a.id), []).append(summary)
            rel_summaries.setdefault(str(b.id), []).append(summary)

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


@router.delete("/{book_id}", status_code=204)
async def delete_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await db.delete(book)
    await db.commit()
