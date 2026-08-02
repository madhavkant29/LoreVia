from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_optional_current_user
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_set,
    key_public_book_detail,
    key_public_books,
    key_public_chapter,
    mark_public_profile_cache_dirty,
)
from app.core.storage import download_book, get_presigned_url
from app.models.book import Book, Chapter
from app.models.user import User
from app.schemas.public import (
    PublicBookAnalyticsOut,
    PublicBookAnalyticsViewBody,
    PublicBookDetailOut,
    PublicBookOut,
    PublicChapterOut,
    PublicForumPostListOut,
    PublicRankedBookListOut,
    PublicUploadsOverviewOut,
    PublicUserProfileOut,
)
from app.utils.books.manuscript import (
    deserialize_manuscript_content,
)
from app.utils.public.analytics import (
    build_public_book_analytics,
    build_public_book_analytics_map,
    build_public_uploads_overview,
    list_visible_creator_public_book_outs,
    record_public_book_analytics_event,
)
from app.utils.public.catalog import (
    _active_forum_post_map,
    _get_public_book_by_slug_or_id,
    filter_public_books_catalog,
    is_catalog_visible_public_book,
)
from app.utils.public.forum_foundation import ensure_public_forum_read_enabled
from app.utils.public.profiles import get_public_user_profile
from app.utils.public.ranking_core import (
    normalize_public_ranking_key,
    normalize_public_ranking_window,
)
from app.utils.public.ranking_service import (
    list_ranked_public_beta_novels,
    list_ranked_public_uploads,
)
from app.utils.public.serialization import (
    build_public_book_out,
    can_owner_or_admin_view_hidden_book,
    can_view_public_book,
    ensure_public_mode_enabled,
    is_public_demo_book,
    public_visibility_notice,
    resolve_optional_user,
)
from app.utils.public_utils import (
    DEFAULT_PUBLIC_FORUM_PAGE_SIZE,
    MAX_PUBLIC_FORUM_PAGE_SIZE,
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
    use_cache = (
        not creator_only
        and not normalized_source
        and not normalized_search
        and page == 1
        and limit == 24
    )
    if use_cache:
        cached = await cache_get(key_public_books())
        if cached:
            return cached
    if creator_only:
        items = [
            book.model_dump(mode="json") for book in await list_visible_creator_public_book_outs(db)
        ]
    else:
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
            (book, username) for book, username in rows if is_catalog_visible_public_book(book)
        ]
        active_forum_post_ids = await _active_forum_post_map(
            db, book_ids=[book.id for book, _username in visible_rows]
        )
        analytics_map = await build_public_book_analytics_map(
            db, book_ids=[book.id for book, _username in visible_rows]
        )
        items = [
            _public_book_payload(
                book,
                username,
                active_forum_post_id=active_forum_post_ids.get(str(book.id)),
                analytics=analytics_map.get(book.id),
            )
            for book, username in visible_rows
        ]
    items = filter_public_books_catalog(
        items, normalized_source, normalized_catalog, normalized_search
    )
    start = (page - 1) * limit
    payload = items[start : start + limit]
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


@router.get("/rankings/uploads", response_model=PublicRankedBookListOut)
async def list_ranked_creator_public_uploads(
    ranking: str = Query(default="most_popular"),
    time_window: str = Query(default="monthly"),
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    return await list_ranked_public_uploads(
        db,
        ranking_key=normalize_public_ranking_key(ranking),
        time_window=normalize_public_ranking_window(time_window),
        search=search,
        page=page,
        limit=limit,
    )


@router.get("/rankings/beta-novels", response_model=PublicForumPostListOut)
async def list_ranked_public_beta_novels_endpoint(
    ranking: str = Query(default="most_popular"),
    time_window: str = Query(default="monthly"),
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=DEFAULT_PUBLIC_FORUM_PAGE_SIZE, ge=1, le=MAX_PUBLIC_FORUM_PAGE_SIZE
    ),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    ensure_public_forum_read_enabled()
    return await list_ranked_public_beta_novels(
        db,
        ranking_key=normalize_public_ranking_key(ranking),
        time_window=normalize_public_ranking_window(time_window),
        q=q,
        page=page,
        page_size=page_size,
        current_user=current_user,
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
    if not can_view_public_book(book) and not can_owner_or_admin_view_hidden_book(
        viewer_user, book
    ):
        raise HTTPException(404, "Public book not found")
    should_cache = is_public_demo_book(book)
    analytics = await build_public_book_analytics(db, book=book)

    if should_cache and can_view_public_book(book):
        cached = await cache_get(key_public_book_detail(str(book.id)))
        if cached:
            cached["analytics"] = analytics.model_dump(mode="json")
            return cached

    author_user = await db.get(User, book.user_id)

    chapters = (
        await db.execute(
            select(Chapter.number, Chapter.title, Chapter.description)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )
    ).all()

    payload = {
        **_public_book_payload(
            book,
            author_user.username if author_user else None,
            active_forum_post_id=(await _active_forum_post_map(db, book_ids=[book.id])).get(
                str(book.id)
            ),
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
    await mark_public_profile_cache_dirty(str(book.user_id))


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
    if not can_view_public_book(book) and not can_owner_or_admin_view_hidden_book(
        viewer_user, book
    ):
        raise HTTPException(404, "Public book not found")
    should_cache = is_public_demo_book(book)

    if should_cache and can_view_public_book(book):
        cached = await cache_get(key_public_chapter(str(book.id), chapter_num))
        if cached:
            return cached

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
