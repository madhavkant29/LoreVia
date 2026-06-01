import uuid
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_book, upload_text
from app.models.book import Book

from app.utils.book_utils import normalize_writer_workspace


async def create_book(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    genre: str | None,
    author: str | None,
    fmt: str,
    file: BinaryIO,
    filename: str,
    isbn: str | None = None,
) -> Book:
    s3_key = upload_book(file, str(user_id), filename)
    book = Book(
        user_id=user_id, title=title, genre=genre, author=author,
        format=fmt, s3_key=s3_key, isbn=isbn, status="pending",
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def create_editor_project(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    book_id: uuid.UUID,
    title: str,
    genre: str | None,
    author: str | None,
    work_type: str,
) -> Book:
    s3_key = _editor_project_s3_key(user_id, book_id)
    upload_text(s3_key, "")

    workspace = normalize_writer_workspace(None)
    workspace["processing"] = {"is_fully_ready": True}

    book = Book(
        id=book_id,
        user_id=user_id,
        title=title,
        genre=genre,
        author=author,
        format="manual",
        work_type=work_type,
        s3_key=s3_key,
        status="ready",
        mode="author",
        source_kind="manual",
        is_editor_project=True,
        writer_workspace=workspace,
    )
    db.add(book)
    await db.flush()
    return book


def _editor_project_s3_key(user_id: uuid.UUID, book_id: uuid.UUID) -> str:
    return f"books/{user_id}/{book_id}/empty.txt"


async def get_user_book(db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> Book | None:
    result = await db.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
    return result.scalar()


async def count_user_books(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(select(func.count()).select_from(Book).where(Book.user_id == user_id))
    return result.scalar() or 0
