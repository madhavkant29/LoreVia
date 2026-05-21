import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
from app.models.book import Book, BookForumPost, Chapter
from app.models.user import User
from app.parsers.chunker import count_tokens
from app.schemas.public import (
    PublicBookAnalyticsOut,
    PublicBookAnalyticsViewBody,
    PublicBookCreateOut,
    PublicBookDetailOut,
    PublicBookListOut,
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
    PublicForumPostReactionBody,
    PublicForumCommentReactionBody,
    PublicForumPostCreateBody,
    PublicForumPostListOut,
    PublicForumPostOut,
    PublicForumPostUpdateBody,
    PublicUploadsOverviewOut,
    PublicUserProfileOut,
)
from app.utils.book_utils import deserialize_manuscript_content
from app.utils.compliance.copyright_check import evaluate_document_copyright
from app.utils.public_utils import (
    CONTENT_SOURCE_TYPE_ADMIN_SEEDED,
    CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
    DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    FORUM_POST_OPEN,
    FORUM_THREAD_TYPE_NOVEL,
    MAX_PUBLIC_FORUM_PAGE_SIZE,
    PUBLIC_STATUS_PUBLISHED,
    PUBLIC_DEMO_SOURCE_KIND,
    PUBLIC_SHARE_STATUS_APPROVED,
    PUBLIC_SHARE_STATUS_NOT_REQUESTED,
    PUBLIC_SHARE_STATUS_PENDING,
    build_public_book_out,
    build_public_book_analytics,
    build_public_book_analytics_map,
    build_public_uploads_overview,
    USER_PUBLIC_SHARE_SOURCE_KIND,
    can_owner_or_admin_view_hidden_book,
    can_view_public_book,
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
    is_admin_user,
    is_public_demo_book,
    is_user_public_share_book,
    list_author_public_forum_posts,
    list_visible_creator_public_book_outs,
    list_public_forum_interests_for_author,
    list_public_forum_comments,
    list_public_forum_posts,
    normalize_public_slug,
    public_visibility_notice,
    record_public_book_analytics_event,
    react_to_public_forum_post,
    react_to_public_forum_comment,
    resolve_optional_user,
    update_public_forum_post,
)
router = APIRouter()

def _public_book_payload(
    book: Book,
    author_username: str | None,
    *,
    active_forum_post_id: str | None = None,
    analytics: PublicBookAnalyticsOut | None = None,
) -> dict[str, object]:
    return build_public_book_out(
        book,
        author_username=author_username,
        active_forum_post_id=active_forum_post_id,
        analytics=analytics,
    ).model_dump(mode="json")


def _is_catalog_visible_public_book(book: Book | None) -> bool:
    return can_view_public_book(book)


async def _active_forum_post_map(db: AsyncSession, *, book_ids: list[uuid.UUID]) -> dict[str, str]:
    if not book_ids:
        return {}
    rows = (
        await db.execute(
            select(BookForumPost.book_id, BookForumPost.id)
            .where(
                BookForumPost.book_id.in_(book_ids),
                BookForumPost.thread_type == FORUM_THREAD_TYPE_NOVEL,
                BookForumPost.status == FORUM_POST_OPEN,
            )
            .order_by(BookForumPost.updated_at.desc(), BookForumPost.created_at.desc())
        )
    ).all()
    mapping: dict[str, str] = {}
    for book_id, post_id in rows:
        key = str(book_id)
        if key not in mapping:
            mapping[key] = str(post_id)
    return mapping


async def _get_public_book_by_slug_or_id(db: AsyncSession, book_slug: str) -> Book | None:
    if isinstance(book_slug, uuid.UUID):
        return await db.get(Book, book_slug)
    raw_value = str(book_slug or "").strip()
    try:
        return await db.get(Book, uuid.UUID(raw_value))
    except ValueError:
        pass
    try:
        normalized_slug = normalize_public_slug(raw_value)
    except HTTPException:
        return None
    return (
        await db.execute(
            select(Book).where(Book.public_slug == normalized_slug)
        )
    ).scalar_one_or_none()


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


@router.put("/forum/posts/{post_id}/reaction", response_model=PublicForumPostOut)
async def react_to_public_beta_forum_post(
    post_id: uuid.UUID,
    body: PublicForumPostReactionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ensure_public_forum_write_enabled()
    return await react_to_public_forum_post(
        db,
        post_id=post_id,
        current_user=current_user,
        reaction=body.reaction,
    )


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
async def list_public_books(
    content_source_type: str | None = None,
    catalog: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 24,
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    normalized_source = str(content_source_type or "").strip().lower()
    normalized_catalog = str(catalog or "").strip().lower()
    normalized_search = " ".join((search or "").split()).strip().lower()
    creator_only = normalized_catalog in {"creator_uploads", "creator-only", "creator_only"}
    use_cache = not creator_only and not normalized_source and not normalized_search and page == 1 and limit == 24
    if use_cache:
        cached = await cache_get(key_public_books())
        if cached:
            return cached
    if creator_only:
        items = [book.model_dump(mode="json") for book in await list_visible_creator_public_book_outs(db)]
    else:
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
        visible_rows = [(book, username) for book, username in rows if _is_catalog_visible_public_book(book)]
        active_forum_post_ids = await _active_forum_post_map(db, book_ids=[book.id for book, _username in visible_rows])
        analytics_map = await build_public_book_analytics_map(db, book_ids=[book.id for book, _username in visible_rows])
        items = [
            _public_book_payload(
                book,
                username,
                active_forum_post_id=active_forum_post_ids.get(str(book.id)),
                analytics=analytics_map.get(book.id),
            )
            for book, username in visible_rows
        ]
    if normalized_source:
        items = [item for item in items if str(item.get("content_source_type") or "").strip().lower() == normalized_source]
    if normalized_search:
        items = [
            item for item in items
            if normalized_search in " ".join(
                str(item.get(field) or "")
                for field in ("title", "author", "author_username", "genre", "description", "source_title", "source_author")
            ).lower()
        ]
    start = (page - 1) * limit
    payload = items[start:start + limit]
    if use_cache:
        await cache_set(key_public_books(), payload, 300)
    return payload


@router.get("/uploads", response_model=list[PublicBookOut])
async def list_creator_public_uploads(
    search: str | None = None,
    page: int = 1,
    limit: int = 24,
    db: AsyncSession = Depends(get_db),
):
    return await list_public_books(
        catalog="creator_uploads",
        search=search,
        page=page,
        limit=limit,
        db=db,
    )


@router.get("/analytics", response_model=PublicUploadsOverviewOut)
async def get_public_uploads_analytics(
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    return await build_public_uploads_overview(db)


@router.get("/books/{book_slug}", response_model=PublicBookDetailOut)
async def get_public_book(
    book_slug: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_mode_enabled()
    viewer_user = resolve_optional_user(current_user)
    book = await _get_public_book_by_slug_or_id(db, book_slug)
    if not can_view_public_book(book) and not can_owner_or_admin_view_hidden_book(viewer_user, book):
        raise HTTPException(404, "Public book not found")
    should_cache = is_public_demo_book(book)
    analytics = await build_public_book_analytics(db, book=book)

    if should_cache and can_view_public_book(book):
        cached = await cache_get(key_public_book_detail(str(book.id)))
        if cached:
            cached["analytics"] = analytics.model_dump(mode="json")
            return cached

    author_user = await db.get(User, book.user_id)

    chapters = (await db.execute(
        select(Chapter.number, Chapter.title, Chapter.description)
        .where(Chapter.book_id == book.id)
        .order_by(Chapter.number)
    )).all()

    payload = {
        **_public_book_payload(
            book,
            author_user.username if author_user else None,
            active_forum_post_id=(await _active_forum_post_map(db, book_ids=[book.id])).get(str(book.id)),
            analytics=analytics,
        ),
        "chapters": [
            {"number": number, "title": title, "description": description}
            for number, title, description in chapters
        ],
        "visibility_notice": None if can_view_public_book(book) else public_visibility_notice(book),
        "analytics": analytics.model_dump(mode="json"),
    }
    if should_cache and can_view_public_book(book):
        await cache_set(key_public_book_detail(str(book.id)), payload, 300)
    return payload


@router.post("/books/{book_slug}/analytics/view", status_code=204)
async def record_public_book_view(
    book_slug: str,
    body: PublicBookAnalyticsViewBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    book = await _get_public_book_by_slug_or_id(db, book_slug)
    if not can_view_public_book(book):
        raise HTTPException(404, "Public book not found")
    await record_public_book_analytics_event(
        db,
        book=book,
        request=request,
        event_type=body.event_type,
        chapter_number=body.chapter_number,
    )
    await db.commit()


@router.get("/books/{book_slug}/chapter/{chapter_num}", response_model=PublicChapterOut)
async def get_public_chapter(
    book_slug: str,
    chapter_num: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_mode_enabled()
    viewer_user = resolve_optional_user(current_user)
    book = await _get_public_book_by_slug_or_id(db, book_slug)
    if not can_view_public_book(book) and not can_owner_or_admin_view_hidden_book(viewer_user, book):
        raise HTTPException(404, "Public book not found")
    should_cache = is_public_demo_book(book)

    if should_cache and can_view_public_book(book):
        cached = await cache_get(key_public_chapter(str(book.id), chapter_num))
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
    if should_cache and can_view_public_book(book):
        await cache_set(key_public_chapter(str(book.id), chapter_num), payload, 3600)
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
        public_status=PUBLIC_STATUS_PUBLISHED,
        public_slug=normalize_public_slug(body.title),
        published_at=datetime.now(UTC),
        public_visibility="public",
        content_source_type=CONTENT_SOURCE_TYPE_PUBLIC_DOMAIN,
        moderation_status="clean",
        source_title=body.title,
        source_author=body.author,
        source_public_domain_note="Public-domain demo book used to showcase LoreVia features.",
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
    visible_rows = [(book, username) for book, username in rows if is_approved_user_public_share_book(book)]
    active_forum_post_ids = await _active_forum_post_map(db, book_ids=[book.id for book, _username in visible_rows])
    return [
        _public_book_payload(book, username, active_forum_post_id=active_forum_post_ids.get(str(book.id)))
        for book, username in visible_rows
    ]


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
        **_public_book_payload(
            book,
            author_user.username if author_user else None,
            active_forum_post_id=(await _active_forum_post_map(db, book_ids=[book.id])).get(str(book.id)),
        ),
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
    if not (body.rights_confirmation or body.confirm_public_share):
        raise HTTPException(400, "Public sharing requires explicit confirmation.")
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id or book.hidden_at is not None or book.archived_at is not None:
        raise HTTPException(404, "Book not found")
    if book.is_public and not is_user_public_share_book(book):
        raise HTTPException(409, "Public demo books cannot be republished through the user-sharing route.")

    if getattr(book, "s3_key", None) and getattr(book, "format", None) != "manual":
        copyright_info = await evaluate_document_copyright(
            format_name=getattr(book, "format", None),
            raw=await asyncio.to_thread(download_book, book.s3_key),
            existing_isbn=getattr(book, "isbn", None),
        )
        if copyright_info.get("isbn"):
            book.isbn = str(copyright_info["isbn"])
        book.copyright_warning = bool(copyright_info.get("copyright_warning", False))

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
