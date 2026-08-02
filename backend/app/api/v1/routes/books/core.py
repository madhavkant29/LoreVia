import logging
import uuid
from typing import Any

import bleach  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

# â”€â”€â”€ Upload limits â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    BookOut,
    BookProcessingOut,
    PrivateUserStats,
    PublicUserStats,
    UserStatsOut,
)
from app.services.library_stats_service import load_library_aggregate_stats
from app.services.pipeline_state_service import (
    continue_book_processing,
    enqueue_processing_state_repair_if_needed,
    retry_book_processing,
)
from app.services.processing_allowance_service import (
    summarize_processing_allowances,
)
from app.utils.billing_utils import calculate_upload_usage_summary, require_author_access
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
from app.utils.llm_usage_utils import summarize_llm_usage_for_user
from app.utils.user_utils import (
    build_writing_dashboard_stats,
)

router = APIRouter()
log = logging.getLogger("lorevia.books")


# â”€â”€â”€ Book mode & metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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


# â”€â”€â”€ Book listing & stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.get("/", response_model=list[BookOut])
async def list_books(
    include_hidden: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
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
        repair_seen_book_ids: set[uuid.UUID] = set()
        for candidate in [*books, *shared_books]:
            if candidate.id in repair_seen_book_ids:
                continue
            repair_seen_book_ids.add(candidate.id)
            await enqueue_processing_state_repair_if_needed(candidate)

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
    library_stats = await load_library_aggregate_stats(db, current_user.id)
    saved_quotes = int(
        (
            await db.execute(
                select(func.count(QuoteEntry.id)).where(QuoteEntry.user_id == current_user.id)
            )
        ).scalar()
        or 0
    )
    writing_stats = await build_writing_dashboard_stats(db, current_user)
    upload_usage = await calculate_upload_usage_summary(db, current_user)
    processing_allowances = await summarize_processing_allowances(db, current_user)
    llm_usage = await summarize_llm_usage_for_user(db, current_user.id)

    return UserStatsOut(
        public=PublicUserStats(
            total_books_read=library_stats.total_books_read,
            total_words_read=library_stats.total_words_read,
        ),
        private=PrivateUserStats(
            total_uploads=upload_usage.total_uploads,
            manuscript_uploads=upload_usage.manuscript_uploads,
            worldbuilding_uploads=upload_usage.worldbuilding_uploads,
            upload_limit=upload_usage.upload_limit,
            uploads_remaining=upload_usage.uploads_remaining,
            upload_limit_unlimited=upload_usage.upload_limit_unlimited,
            active_analyzed_words=processing_allowances.active_analyzed_words,
            active_word_limit=processing_allowances.active_word_limit,
            active_words_remaining=processing_allowances.active_words_remaining,
            monthly_processed_words=processing_allowances.monthly_processed_words,
            monthly_processed_word_limit=processing_allowances.monthly_processed_word_limit,
            monthly_processed_words_remaining=processing_allowances.monthly_processed_words_remaining,
            source_storage_bytes=processing_allowances.source_storage_bytes,
            source_storage_limit_bytes=processing_allowances.source_storage_limit_bytes,
            source_storage_remaining_bytes=processing_allowances.source_storage_remaining_bytes,
            allowances_enforced=processing_allowances.allowances_enforced,
            total_token_consumption=library_stats.total_token_consumption,
            llm_request_count=llm_usage.request_count,
            llm_prompt_tokens=llm_usage.prompt_tokens,
            llm_completion_tokens=llm_usage.completion_tokens,
            llm_total_tokens=llm_usage.total_tokens,
            total_chapters_tracked=library_stats.total_chapters_tracked,
            saved_quotes=saved_quotes,
        ),
        writing=writing_stats,
    )


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


@router.get("/notes", response_model=list[BookNoteOut])
async def list_saved_notes(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_author_access(current_user)
    return await list_user_notes(db, current_user.id)


# â”€â”€â”€ Book detail & overview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
