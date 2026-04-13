from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api.deps.auth import get_current_user
from app.core.database import get_db
from app.core.redis import cache_del, cache_get, cache_set, key_public_book_detail, key_public_books, key_public_chapter
from app.core.storage import download_book, get_presigned_url, upload_text
from app.models.book import Book, Chapter
from app.parsers.chunker import count_tokens

router = APIRouter()
PUBLIC_MODE_ENABLED = False


def _ensure_public_mode_enabled() -> None:
    if not PUBLIC_MODE_ENABLED:
        raise HTTPException(503, "Public mode is temporarily disabled")


class PublicChapterIn(BaseModel):
    title: str
    text: str
    description: str | None = None


class PublicBookManualIn(BaseModel):
    title: str
    author: str | None = None
    genre: str | None = None
    description: str | None = None
    chapters: list[PublicChapterIn]


@router.get("/books")
async def list_public_books(db: AsyncSession = Depends(get_db)):
    _ensure_public_mode_enabled()
    cached = await cache_get(key_public_books())
    if cached:
        return cached

    rows = (await db.execute(
        select(Book)
        .where(Book.is_public.is_(True), Book.hidden_at.is_(None), Book.status.in_(["ready", "processing", "pending"]))
        .order_by(Book.created_at.desc())
    )).scalars().all()
    payload = [
        {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "genre": book.genre,
            "description": book.public_description,
            "format": book.format,
            "status": book.status,
            "total_chapters": book.total_chapters,
            "copyright_warning": book.copyright_warning,
            "created_at": book.created_at,
        }
        for book in rows
    ]
    await cache_set(key_public_books(), payload, 300)
    return payload


@router.get("/books/{book_id}")
async def get_public_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    _ensure_public_mode_enabled()
    cached = await cache_get(key_public_book_detail(str(book_id)))
    if cached:
        return cached

    book = await db.get(Book, book_id)
    if not book or not book.is_public or book.hidden_at is not None:
        raise HTTPException(404, "Public book not found")

    chapters = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.description)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number)
    )).all()

    payload = {
        "id": str(book.id),
        "title": book.title,
        "author": book.author,
        "genre": book.genre,
        "description": book.public_description,
        "format": book.format,
        "status": book.status,
        "total_chapters": book.total_chapters,
        "copyright_warning": book.copyright_warning,
        "chapters": [
            {"number": number, "title": title, "description": description}
            for number, title, description in chapters
        ],
    }
    await cache_set(key_public_book_detail(str(book_id)), payload, 300)
    return payload


@router.get("/books/{book_id}/chapter/{chapter_num}")
async def get_public_chapter(book_id: uuid.UUID, chapter_num: int, db: AsyncSession = Depends(get_db)):
    _ensure_public_mode_enabled()
    cached = await cache_get(key_public_chapter(str(book_id), chapter_num))
    if cached:
        return cached

    book = await db.get(Book, book_id)
    if not book or not book.is_public or book.hidden_at is not None:
        raise HTTPException(404, "Public book not found")

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    payload = {
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": chapter.number,
        "chapter_title": chapter.title,
        "chapter_description": chapter.description,
        "total_chapters": book.total_chapters,
        "text_url": get_presigned_url(chapter.s3_key) if chapter.s3_key else None,
        "text_content": download_book(chapter.s3_key).decode("utf-8", errors="ignore") if chapter.s3_key and not get_presigned_url(chapter.s3_key) else None,
    }
    await cache_set(key_public_chapter(str(book_id), chapter_num), payload, 3600)
    return payload


@router.post("/books/manual")
async def create_public_book_manual(
    body: PublicBookManualIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ensure_public_mode_enabled()
    if not body.chapters:
        raise HTTPException(400, "At least one chapter is required")

    book = Book(
        user_id=current_user.id,
        title=body.title,
        author=body.author,
        genre=body.genre,
        format="manual",
        s3_key=f"public/manual/{current_user.id}/{body.title}".replace(" ", "-").lower(),
        status="ready",
        is_public=True,
        public_description=body.description,
    )
    db.add(book)
    await db.flush()

    total_tokens = 0
    for index, chapter_in in enumerate(body.chapters, start=1):
        chapter_key = f"public_chapters/{book.id}/{index}.txt"
        upload_text(chapter_key, chapter_in.text)
        total_tokens += count_tokens(chapter_in.text)
        db.add(
            Chapter(
                book_id=book.id,
                number=index,
                title=chapter_in.title,
                description=chapter_in.description,
                s3_key=chapter_key,
                token_count=count_tokens(chapter_in.text),
                processed=False,
            )
        )

    book.total_chapters = len(body.chapters)
    book.total_tokens = total_tokens
    await db.commit()
    await db.refresh(book)
    await cache_del(key_public_books())
    return {"book_id": str(book.id), "status": "ready", "visibility": "public"}


@router.post("/books/{book_id}/chapters")
async def append_public_chapter(
    book_id: uuid.UUID,
    body: PublicChapterIn,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id or not book.is_public:
        raise HTTPException(404, "Public book not found")

    next_number = (await db.execute(
        select(func.coalesce(func.max(Chapter.number), 0) + 1).where(Chapter.book_id == book.id)
    )).scalar_one()
    chapter_key = f"public_chapters/{book.id}/{next_number}.txt"
    upload_text(chapter_key, body.text)
    token_count = count_tokens(body.text)
    db.add(
        Chapter(
            book_id=book.id,
            number=next_number,
            title=body.title,
            description=body.description,
            s3_key=chapter_key,
            token_count=token_count,
            processed=False,
        )
    )
    book.total_chapters = next_number
    book.total_tokens = (book.total_tokens or 0) + token_count
    await db.commit()
    await cache_del(key_public_book_detail(str(book.id)))
    await cache_del(key_public_chapter(str(book.id), next_number))
    await cache_del(key_public_books())
    return {"book_id": str(book.id), "chapter_number": next_number, "saved": True}
