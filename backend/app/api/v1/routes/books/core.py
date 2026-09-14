import logging
import uuid
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

# ─── Upload limits ────────────────────────────────────────────────────────────
MAX_BOOK_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_COVER_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

_COVER_MAGIC: dict[bytes, tuple[str, str]] = {
    b"\xff\xd8\xff": ("jpg", "image/jpeg"),
    b"\x89PNG": ("png", "image/png"),
    b"GIF8": ("gif", "image/gif"),
    b"RIFF": ("webp", "image/webp"),
}

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


from app.api.deps.auth import get_current_user
from app.api.deps.feature_flags import require_cursor_page_apis_enabled
from app.core.database import get_db
from app.core.redis import (
    mark_book_cache_dirty,
    mark_user_dashboard_cache_dirty,
)
from app.models.book import (
    Book,
    BookCollaborator,
    Chapter,
)
from app.models.intelligence import QuoteEntry
from app.schemas.books import (
    BookForumMetadataBody,
    BookModeBody,
    BookNoteOut,
    BookNotePageOut,
    BookOut,
    BookPageOut,
    BookProcessingOut,
    BookSelectorOut,
    SavedQuotePageOut,
    UserStatsOut,
)
from app.services.book_listing_service import list_user_book_selectors, list_user_books_page
from app.services.pipeline_state_service import (
    continue_book_processing,
    enqueue_processing_state_repair_if_needed,
    retry_book_processing,
)
from app.services.saved_content_service import list_saved_notes_page, list_saved_quotes_page
from app.services.user_stats_service import get_user_stats_cached
from app.utils.billing_utils import require_author_access
from app.utils.books.collaboration_access import (
    get_book_with_collaboration_access,
    require_book_owner_access,
)
from app.utils.books.notes import (
    get_owned_book,
    list_user_notes,
)
from app.utils.books.serialization import (
    book_out,
    build_book_out_list,
)
from app.utils.books.writer_workspace import (
    touch_public_book_updated_at,
)
from app.utils.db_utils import run_read_with_retry

router = APIRouter()
log = logging.getLogger("lorevia.books")


# ─── Book mode & metadata ────────────────────────────────────────────────────


@router.put("/{book_id}/mode", response_model=BookOut)
async def update_book_mode(
    book_id: uuid.UUID,
    body: BookModeBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    require_book_owner_access(book, current_user, collaborator)
    require_author_access(current_user)
    mode = (body.mode or "").strip().lower()
    if mode not in {"reader", "author"}:
        raise HTTPException(400, "Invalid mode")
    book.mode = mode
    if mode == "author" and not book.source_kind:
        book.source_kind = "single_upload"
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    return await book_out(db, book, current_user.id, collaborator)


@router.put("/{book_id}/forum-metadata", response_model=BookOut)
async def update_book_forum_metadata(
    book_id: uuid.UUID,
    body: BookForumMetadataBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    normalized_title = _clean_text(body.title)
    normalized_genre = _clean_text(body.genre)
    normalized_description = _clean_text(body.description)
    if not normalized_title or not normalized_genre or not normalized_description:
        raise HTTPException(400, "Novel discussions require a title, genre, and description.")
    book.title = normalized_title
    book.genre = normalized_genre
    book.public_description = normalized_description
    touch_public_book_updated_at(book)
    await db.commit()
    await db.refresh(book)
    await mark_book_cache_dirty(str(book.id))
    await mark_user_dashboard_cache_dirty(current_user.id)
    return await book_out(db, book, current_user.id)


# ─── Book listing & stats ────────────────────────────────────────────────────


@router.get(
    "/page",
    response_model=BookPageOut,
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def list_books_page(
    include_hidden: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    async def load_page() -> BookPageOut:
        return await list_user_books_page(
            db,
            user_id=current_user.id,
            user_email=str(current_user.email),
            include_hidden=include_hidden,
            limit=limit,
            cursor=cursor,
        )

    return await run_read_with_retry(db, load_page)


@router.get(
    "/selector",
    response_model=list[BookSelectorOut],
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def list_book_selectors(
    include_hidden: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Navigation-sized project records; avoids progress and aggregate work."""
    return await run_read_with_retry(
        db,
        lambda: list_user_book_selectors(
            db,
            user_id=current_user.id,
            user_email=str(current_user.email),
            include_hidden=include_hidden,
            limit=limit,
        ),
    )


@router.get("/", response_model=list[BookOut])
async def list_books(
    include_hidden: bool = Query(False),
    response: Response = None,  # type: ignore[assignment]
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if response is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Link"] = '</api/v1/books/page>; rel="successor-version"'
    log.info("deprecated_books_list_requested", extra={"metric": "books.legacy_list_requested"})
    current_user_id = current_user.id
    current_user_email = str(current_user.email).strip().lower()

    async def load_book_list() -> list[BookOut]:
        stmt = (
            select(Book)
            .options(noload(Book.vault_note_series_links))
            .where(Book.user_id == current_user_id)
        )
        if not include_hidden:
            stmt = stmt.where(Book.hidden_at.is_(None))
        result = await db.execute(stmt.order_by(Book.created_at.desc()))
        books = list(result.scalars().all())
        shared_rows = (
            await db.execute(
                select(Book, BookCollaborator)
                .options(noload(Book.vault_note_series_links))
                .join(BookCollaborator, BookCollaborator.book_id == Book.id)
                .where(
                    BookCollaborator.email == current_user_email,
                    BookCollaborator.invite_status == "active",
                    Book.user_id != current_user_id,
                )
                .order_by(BookCollaborator.invited_at.desc())
            )
        ).all()
        if not include_hidden:
            shared_rows = [row for row in shared_rows if row[0].hidden_at is None]

        shared_books = [book for book, _ in shared_rows]
        owned_payloads = await build_book_out_list(db, books=books, user_id=current_user_id)
        shared_payloads = await build_book_out_list(
            db,
            books=shared_books,
            user_id=current_user_id,
            collaborators_by_book_id={book.id: collaborator for book, collaborator in shared_rows},
        )
        return owned_payloads + shared_payloads

    return await run_read_with_retry(db, load_book_list)


@router.get("/stats", response_model=UserStatsOut)
async def get_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    return await get_user_stats_cached(db, current_user)


@router.get("/quotes")
async def list_saved_quotes(
    db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    require_author_access(current_user)
    rows = (
        await db.execute(
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
        )
    ).all()
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


@router.get(
    "/quotes/page",
    response_model=SavedQuotePageOut,
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def list_saved_quotes_page_endpoint(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    return await list_saved_quotes_page(
        db, user_id=current_user.id, limit=limit, cursor=cursor
    )


@router.get("/notes", response_model=list[BookNoteOut])
async def list_saved_notes(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    return await list_user_notes(db, current_user.id)


@router.get(
    "/notes/page",
    response_model=BookNotePageOut,
    dependencies=[Depends(require_cursor_page_apis_enabled)],
)
async def list_saved_notes_page_endpoint(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=512),
    include_body: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    return await list_saved_notes_page(
        db,
        user_id=current_user.id,
        limit=limit,
        cursor=cursor,
        include_body=include_body,
    )


# ─── Book detail & overview ──────────────────────────────────────────────────


@router.get("/{book_id}", response_model=BookOut)
async def get_book(
    book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    book, collaborator = await get_book_with_collaboration_access(
        db,
        book_id,
        current_user,
    )
    await enqueue_processing_state_repair_if_needed(book)
    return await book_out(db, book, current_user.id, collaborator)


@router.post("/{book_id}/processing/retry", response_model=BookProcessingOut)
async def retry_book_processing_endpoint(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    require_book_owner_access(book, current_user, collaborator)
    processing = await retry_book_processing(db, book)
    if processing is None:
        raise HTTPException(409, "Processing retry is not available for this book.")
    return processing


@router.post("/{book_id}/processing/continue", response_model=BookProcessingOut)
async def continue_book_processing_endpoint(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    require_book_owner_access(book, current_user, collaborator)
    return await continue_book_processing(db, book)
