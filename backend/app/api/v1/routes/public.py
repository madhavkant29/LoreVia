import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_admin, get_current_user, get_optional_current_user
from app.core.database import get_db
from app.core.redis import (
    cache_del,
    cache_get,
    cache_get_int,
    cache_set,
    key_public_book_detail,
    key_public_books,
    key_public_chapter,
    key_public_forum_cache_version,
    key_public_forum_post_detail,
    key_public_forum_posts,
)
from app.core.storage import download_book, get_presigned_url, upload_text
from app.models.book import Book, Chapter
from app.models.user import User
from app.parsers.chunker import count_tokens
from app.schemas.public import (
    PublicBookCreateOut,
    PublicBookDetailOut,
    PublicBookManualIn,
    PublicBookOut,
    PublicBookShareBody,
    PublicChapterAppendOut,
    PublicChapterOut,
    PublicChapterIn,
    PublicForumInterestCreateBody,
    PublicForumInterestListOut,
    PublicForumInterestOut,
    PublicForumCommentCreateBody,
    PublicForumCommentListOut,
    PublicForumCommentOut,
    PublicForumCommentReactionBody,
    PublicForumPostCreateBody,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumPostUpdateBody,
    PublicUserProfileOut,
)
from app.utils.book_utils import deserialize_manuscript_content
from app.utils.public_utils import (
    DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    MAX_PUBLIC_FORUM_PAGE_SIZE,
    PUBLIC_DEMO_SOURCE_KIND,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    USER_PUBLIC_SHARE_SOURCE_KIND,
    create_public_forum_interest,
    create_public_forum_comment,
    create_public_forum_post,
    ensure_public_forum_read_enabled,
    ensure_public_forum_write_enabled,
    ensure_public_mode_enabled,
    get_public_forum_post_detail,
    get_public_share_status,
    ensure_public_authoring_access,
    get_public_user_profile,
    is_approved_user_public_share_book,
    is_public_demo_book,
    is_user_public_share_book,
    list_author_public_forum_posts,
    list_public_forum_interests_for_author,
    list_public_forum_comments,
    list_public_forum_posts,
    react_to_public_forum_comment,
    update_public_forum_post,
)
router = APIRouter()


def _public_book_payload(book: Book, author_username: str | None) -> dict[str, object]:
    return {
        "id": str(book.id),
        "public_kind": PUBLIC_DEMO_SOURCE_KIND if is_public_demo_book(book) else USER_PUBLIC_SHARE_SOURCE_KIND,
        "title": book.title,
        "author": book.author,
        "author_username": author_username,
        "genre": book.genre,
        "description": book.public_description,
        "format": book.format,
        "work_type": book.work_type,
        "status": book.status,
        "total_chapters": book.total_chapters,
        "copyright_warning": book.copyright_warning,
        "created_at": book.created_at,
    }


def _is_catalog_visible_public_book(book: Book | None) -> bool:
    if (
        book is None
        or book.hidden_at is not None
        or book.archived_at is not None
    ):
        return False
    return is_public_demo_book(book) or is_approved_user_public_share_book(book)


@router.get("/forum/posts", response_model=PublicForumPostListOut)
async def list_public_beta_forum_posts(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PUBLIC_FORUM_PAGE_SIZE, ge=1, le=MAX_PUBLIC_FORUM_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    normalized_query = " ".join((q or "").split()).strip()
    if current_user is None:
        version = await cache_get_int(key_public_forum_cache_version(), default=1)
        cache_key = key_public_forum_posts(version, normalized_query, page, page_size)
        cached = await cache_get(cache_key)
        if cached:
            return PublicForumPostListOut(**cached)

    payload = await list_public_forum_posts(
        db,
        q=normalized_query,
        page=page,
        page_size=page_size,
        current_user=current_user,
    )
    if current_user is None:
        await cache_set(cache_key, payload.model_dump(mode="json"), 120)
    return payload


@router.get("/forum/my-posts", response_model=list[PublicForumPostOut])
async def list_current_author_public_forum_posts(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_read_enabled()
    return await list_author_public_forum_posts(db, author_user_id=current_user.id)


@router.get("/forum/posts/{post_id}", response_model=PublicForumPostOut)
async def get_public_beta_forum_post(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    if current_user is None:
        version = await cache_get_int(key_public_forum_cache_version(), default=1)
        cache_key = key_public_forum_post_detail(version, str(post_id))
        cached = await cache_get(cache_key)
        if cached:
            return PublicForumPostOut(**cached)

    payload = await get_public_forum_post_detail(
        db,
        post_id=post_id,
        current_user=current_user,
    )
    if current_user is None:
        await cache_set(cache_key, payload.model_dump(mode="json"), 120)
    return payload


@router.post("/forum/posts", response_model=PublicForumPostOut, status_code=201)
async def create_public_beta_forum_post_endpoint(
    body: PublicForumPostCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await create_public_forum_post(db, current_user=current_user, body=body)


@router.put("/forum/posts/{post_id}", response_model=PublicForumPostOut)
async def edit_public_beta_forum_post_endpoint(
    post_id: uuid.UUID,
    body: PublicForumPostUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await update_public_forum_post(db, post_id=post_id, current_user=current_user, body=body)


@router.post("/forum/posts/{post_id}/interests", response_model=PublicForumInterestOut, status_code=201)
async def create_public_beta_forum_interest_endpoint(
    post_id: uuid.UUID,
    body: PublicForumInterestCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await create_public_forum_interest(db, post_id=post_id, current_user=current_user, body=body)


@router.get("/forum/posts/{post_id}/interests", response_model=PublicForumInterestListOut)
async def list_public_beta_forum_interests(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return PublicForumInterestListOut(
        items=await list_public_forum_interests_for_author(
            db,
            post_id=post_id,
            author_user_id=current_user.id,
        )
    )


@router.get("/forum/posts/{post_id}/comments", response_model=PublicForumCommentListOut)
async def list_public_beta_forum_comments(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    return PublicForumCommentListOut(
        items=await list_public_forum_comments(
            db,
            post_id=post_id,
            current_user=current_user,
        )
    )


@router.post("/forum/posts/{post_id}/comments", response_model=PublicForumCommentOut, status_code=201)
async def create_public_beta_forum_comment(
    post_id: uuid.UUID,
    body: PublicForumCommentCreateBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await create_public_forum_comment(db, post_id=post_id, current_user=current_user, body=body)


@router.put("/forum/comments/{comment_id}/reaction", response_model=PublicForumCommentOut)
async def react_to_public_beta_forum_comment(
    comment_id: uuid.UUID,
    body: PublicForumCommentReactionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await react_to_public_forum_comment(
        db,
        comment_id=comment_id,
        current_user=current_user,
        reaction=body.reaction,
    )


@router.get("/users/{username}", response_model=PublicUserProfileOut)
async def get_public_user_profile_endpoint(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    return await get_public_user_profile(db, username=username)


@router.get("/books", response_model=list[PublicBookOut])
async def list_public_books(db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    cached = await cache_get(key_public_books())
    if cached:
        return cached

    rows = (await db.execute(
        select(Book, User.username)
        .join(User, User.id == Book.user_id)
        .where(
            Book.is_public.is_(True),
            Book.hidden_at.is_(None),
            Book.archived_at.is_(None),
            Book.status.in_(["ready", "processing", "pending"]),
        )
        .order_by(Book.created_at.desc())
    )).all()
    payload = [_public_book_payload(book, username) for book, username in rows if _is_catalog_visible_public_book(book)]
    await cache_set(key_public_books(), payload, 300)
    return payload


@router.get("/books/{book_id}", response_model=PublicBookDetailOut)
async def get_public_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not _is_catalog_visible_public_book(book):
        raise HTTPException(404, "Public book not found")
    should_cache = is_public_demo_book(book)

    if should_cache:
        cached = await cache_get(key_public_book_detail(str(book_id)))
        if cached:
            return cached

    author_user = await db.get(User, book.user_id)

    chapters = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.description)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number)
    )).all()

    payload = {
        **_public_book_payload(book, author_user.username if author_user else None),
        "chapters": [
            {"number": number, "title": title, "description": description}
            for number, title, description in chapters
        ],
    }
    if should_cache:
        await cache_set(key_public_book_detail(str(book_id)), payload, 300)
    return payload


@router.get("/books/{book_id}/chapter/{chapter_num}", response_model=PublicChapterOut)
async def get_public_chapter(book_id: uuid.UUID, chapter_num: int, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not _is_catalog_visible_public_book(book):
        raise HTTPException(404, "Public book not found")
    should_cache = is_public_demo_book(book)

    if should_cache:
        cached = await cache_get(key_public_chapter(str(book_id), chapter_num))
        if cached:
            return cached

    chapter = (await db.execute(
        select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
    )).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")

    stored_payload = deserialize_manuscript_content(download_book(chapter.s3_key)) if chapter.s3_key else {"text": None, "html": None}
    payload = {
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
    if should_cache:
        await cache_set(key_public_chapter(str(book_id), chapter_num), payload, 3600)
    return payload


@router.post("/books/manual", response_model=PublicBookCreateOut)
async def create_public_book_manual(
    body: PublicBookManualIn,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    ensure_public_mode_enabled()
    if not body.chapters:
        raise HTTPException(400, "At least one chapter is required")
    book_id = uuid.uuid4()
    book = Book(
        id=book_id,
        user_id=admin_user.id,
        title=body.title,
        author=body.author,
        genre=body.genre,
        format="manual",
        s3_key=f"public/manual/{admin_user.id}/{body.title}".replace(" ", "-").lower(),
        status="ready",
        is_public=True,
        source_kind=PUBLIC_DEMO_SOURCE_KIND,
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
    return {
        "book_id": str(book.id),
        "status": "ready",
        "visibility": "public",
        "public_kind": PUBLIC_DEMO_SOURCE_KIND,
        "approval_status": PUBLIC_SHARE_STATUS_APPROVED,
        "message": "Public demo is live.",
    }


@router.post("/books/{book_id}/chapters", response_model=PublicChapterAppendOut)
async def append_public_chapter(
    book_id: uuid.UUID,
    body: PublicChapterIn,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin),
):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not book or book.user_id != admin_user.id or not is_public_demo_book(book):
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
    return [_public_book_payload(book, username) for book, username in rows if is_approved_user_public_share_book(book)]


@router.get("/shared-books/{book_id}", response_model=PublicBookDetailOut)
async def get_user_shared_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not book or not is_approved_user_public_share_book(book) or book.hidden_at is not None or book.archived_at is not None:
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
        **_public_book_payload(book, author_user.username if author_user else None),
        "chapters": [
            {"number": number, "title": title, "description": description}
            for number, title, description in chapters
        ],
    }


@router.get("/shared-books/{book_id}/chapter/{chapter_num}", response_model=PublicChapterOut)
async def get_user_shared_chapter(book_id: uuid.UUID, chapter_num: int, db: AsyncSession = Depends(get_db)):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    if not book or not is_approved_user_public_share_book(book) or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Shared book not found")
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_num)
        )
    ).scalar()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    stored_payload = deserialize_manuscript_content(download_book(chapter.s3_key)) if chapter.s3_key else {"text": None, "html": None}
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
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_mode_enabled()
    ensure_public_authoring_access(current_user, action_label="Submitting a public sample")
    if not body.confirm_public_share:
        raise HTTPException(400, "Public sharing requires explicit confirmation.")
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Book not found")
    if book.is_public and not is_user_public_share_book(book):
        raise HTTPException(409, "Public demo books cannot be republished through the user-sharing route.")
    book.source_kind = USER_PUBLIC_SHARE_SOURCE_KIND
    if body.description is not None:
        book.public_description = body.description.strip() or None
    book.is_public = False
    book.public_share_status = PUBLIC_SHARE_STATUS_PENDING
    book.public_share_requested_at = datetime.now(UTC)
    book.public_share_approved_at = None
    book.public_share_approved_by_user_id = None
    await db.commit()
    await cache_del(key_public_books())
    await cache_del(key_public_book_detail(str(book.id)))
    approval_status = get_public_share_status(book)
    return {
        "book_id": str(book.id),
        "status": book.status,
        "visibility": "private",
        "public_kind": USER_PUBLIC_SHARE_SOURCE_KIND,
        "approval_status": approval_status,
        "message": "Public sample request submitted for manual approval.",
    }


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
    if str(getattr(book, "source_kind", "") or "").strip().lower() != USER_PUBLIC_SHARE_SOURCE_KIND and share_status == PUBLIC_SHARE_STATUS_NOT_REQUESTED:
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
    return {
        "book_id": str(book.id),
        "status": book.status,
        "visibility": "private",
        "public_kind": USER_PUBLIC_SHARE_SOURCE_KIND,
        "approval_status": get_public_share_status(book),
        "message": "Public sample is no longer visible.",
    }
