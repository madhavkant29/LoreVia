import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.v1.routes.public_catalog import _public_book_payload
from app.core.database import get_db
from app.core.redis import (
    cache_del,
    key_public_book_detail,
    key_public_books,
    mark_public_profile_cache_dirty,
)
from app.core.storage import download_book, get_presigned_url
from app.models.book import Book, Chapter
from app.models.user import User
from app.schemas.public import (
    PublicBookCreateOut,
    PublicBookDetailOut,
    PublicBookOut,
    PublicBookShareBody,
    PublicChapterOut,
)
from app.services.public_publish_service import submit_public_share
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
)
from app.utils.public.catalog import (
    _active_forum_post_map,
)
from app.utils.public.serialization import (
    ensure_public_authoring_access,
    ensure_public_mode_enabled,
    get_public_share_status,
    is_approved_user_public_share_book,
    is_user_public_share_book,
)
from app.utils.public_utils import (
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    USER_PUBLIC_SHARE_SOURCE_KIND,
)

router = APIRouter()


@router.get("/shared-books", response_model=list[PublicBookOut])
async def list_user_shared_books(db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    rows = (
        await db.execute(
            select(Book, User.username)
            .join(User, User.id == Book.user_id)
            .where(
                Book.is_public.is_(True),
                Book.hidden_at.is_(None),
                Book.archived_at.is_(None),
                Book.status.in_(["ready", "processing", "pending"]),
            )
            .order_by(Book.created_at.desc())
        )
    ).all()
    visible_rows = [
        (book, username) for book, username in rows if is_approved_user_public_share_book(book)
    ]
    active_forum_post_ids = await _active_forum_post_map(
        db, book_ids=[book.id for book, _username in visible_rows]
    )
    return [
        _public_book_payload(
            book, username, active_forum_post_id=active_forum_post_ids.get(str(book.id))
        )
        for book, username in visible_rows
    ]


@router.get("/shared-books/{book_id}", response_model=PublicBookDetailOut)
async def get_user_shared_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if (
        not book
        or not is_approved_user_public_share_book(book)
        or book.hidden_at is not None
        or book.archived_at is not None
    ):
        raise HTTPException(404, "Shared book not found")
    author_user = await db.get(User, book.user_id)
    chapters = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.description)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )
    ).all()
    return {
        **_public_book_payload(
            book,
            author_user.username if author_user else None,
            active_forum_post_id=(await _active_forum_post_map(db, book_ids=[book.id])).get(
                str(book.id)
            ),
        ),
        "chapters": [
            {"number": number, "title": title, "description": description}
            for number, title, description in chapters
        ],
    }


@router.get("/shared-books/{book_id}/chapter/{chapter_num}", response_model=PublicChapterOut)
async def get_user_shared_chapter(
    book_id: uuid.UUID, chapter_num: int, db: AsyncSession = Depends(get_db)
):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if (
        not book
        or not is_approved_user_public_share_book(book)
        or book.hidden_at is not None
        or book.archived_at is not None
    ):
        raise HTTPException(404, "Shared book not found")
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
        )
    ).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    stored_payload = (
        deserialize_manuscript_content(download_book(chapter.s3_key))
        if chapter.s3_key
        else {"text": None, "html": None}
    )
    return {
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": chapter.number,
        "chapter_title": chapter.title,
        "chapter_description": chapter.description,
        "total_chapters": book.total_chapters,
        "text_url": get_presigned_url(chapter.s3_key) if chapter.s3_key else None,
        "text_content": stored_payload.get("text"),
        "html_content": stored_payload.get("html"),
    }


@router.post("/shared-books/{book_id}/publish", response_model=PublicBookCreateOut)
async def publish_user_shared_book(
    book_id: uuid.UUID,
    body: PublicBookShareBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    ensure_public_authoring_access(current_user, action_label="Submitting a public sample")
    book = await db.get(Book, book_id)
    if (
        not book
        or book.user_id != current_user.id
        or book.hidden_at is not None
        or book.archived_at is not None
    ):
        raise HTTPException(404, "Book not found")
    if book.is_public and not is_user_public_share_book(book):
        raise HTTPException(
            409, "Public demo books cannot be republished through the user-sharing route."
        )

    return await submit_public_share(
        db,
        book=book,
        user=current_user,
        body=body,
        request_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/shared-books/{book_id}/unpublish", response_model=PublicBookCreateOut)
async def unpublish_user_shared_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Shared book not found")
    share_status = get_public_share_status(book)
    if (
        str(getattr(book, "source_kind", "") or "").strip().lower() != USER_PUBLIC_SHARE_SOURCE_KIND
        and share_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED
    ):
        raise HTTPException(404, "Shared book not found")
    book.is_public = False
    book.source_kind = USER_PUBLIC_SHARE_SOURCE_KIND
    book.public_share_status = PUBLIC_SHARE_STATUS_NOT_REQUESTED
    book.public_share_requested_at = None
    book.public_share_approved_at = None
    book.public_share_approved_by_user_id = None
    await db.commit()
    await cache_del(key_public_books())
    await cache_del(key_public_book_detail(str(book.id)))
    await mark_public_profile_cache_dirty(str(book.user_id))
    return {
        "book_id": str(book.id),
        "status": book.status,
        "visibility": "private",
        "public_kind": USER_PUBLIC_SHARE_SOURCE_KIND,
        "approval_status": get_public_share_status(book),
        "message": "Public sample is no longer visible.",
    }
