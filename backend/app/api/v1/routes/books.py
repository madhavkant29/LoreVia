from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.storage import upload_book
from app.models.book import Book
from app.models.character import Character
from app.api.deps.auth import get_current_user
from app.api.deps.subscription import check_upload_limit
from app.utils.external.isbn_lookup import extract_isbn_from_pdf
from app.utils.compliance.copyright_check import check_isbn
from app.workers.tasks.extraction_tasks import process_book_task
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid

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
    result = await db.execute(select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter))
    return result.scalars().all()


@router.delete("/{book_id}", status_code=204)
async def delete_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    await db.delete(book)
    await db.commit()
