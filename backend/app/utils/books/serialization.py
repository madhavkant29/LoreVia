"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_asset_token
from app.core.storage import download_book, upload_binary
from app.models.book import (
    Book,
    BookCollaborator,
    Chapter,
    Series,
    SeriesBook,
)
from app.models.progress import ReadingProgress
from app.schemas.books import (
    BookOut,
    SeriesOut,
)
from app.utils.books import collaboration, manuscript
from app.utils.books.writer_workspace import build_book_processing_payload
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS

if TYPE_CHECKING:
    pass


COVER_RENDER_EXCEPTIONS = (RuntimeError, ValueError, OSError)
COVER_PERSIST_EXCEPTIONS = STORAGE_IO_EXCEPTIONS + (SQLAlchemyError,)


@dataclass(slots=True)
class BookRenderContext:
    progress_by_book_id: dict[uuid.UUID, ReadingProgress]
    total_words_by_book_id: dict[uuid.UUID, int]
    cover_url_by_book_id: dict[uuid.UUID, str | None]


async def preload_book_render_context(
    db: AsyncSession,
    *,
    books: Sequence[Book],
    user_id: uuid.UUID,
) -> BookRenderContext:
    unique_books = list(dict.fromkeys(books))
    if not unique_books:
        return BookRenderContext(
            progress_by_book_id={},
            total_words_by_book_id={},
            cover_url_by_book_id={},
        )

    book_ids = [book.id for book in unique_books]
    progress_rows = (
        (
            await db.execute(
                select(ReadingProgress).where(
                    ReadingProgress.user_id == user_id,
                    ReadingProgress.book_id.in_(book_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    total_word_rows = (
        await db.execute(
            select(Chapter.book_id, func.coalesce(func.sum(Chapter.word_count), 0))
            .where(Chapter.book_id.in_(book_ids))
            .group_by(Chapter.book_id)
        )
    ).all()
    return BookRenderContext(
        progress_by_book_id={progress.book_id: progress for progress in progress_rows},
        total_words_by_book_id={
            book_id: int(total_words or 0) for book_id, total_words in total_word_rows
        },
        cover_url_by_book_id={book.id: cover_url_for_book(book) for book in unique_books},
    )


async def build_book_out_list(
    db: AsyncSession,
    *,
    books: Sequence[Book],
    user_id: uuid.UUID,
    collaborators_by_book_id: dict[uuid.UUID, BookCollaborator] | None = None,
) -> list[BookOut]:
    context = await preload_book_render_context(db, books=books, user_id=user_id)
    payloads: list[BookOut] = []
    for book in books:
        payloads.append(
            await book_out(
                db,
                book,
                user_id,
                collaborator=(collaborators_by_book_id or {}).get(book.id),
                context=context,
            )
        )
    return payloads


def _build_series_out_from_grouped_rows(
    *,
    series_rows: Sequence[Series],
    memberships_by_series_id: dict[uuid.UUID, list[tuple[SeriesBook, Book]]],
    book_payloads_by_id: dict[uuid.UUID, BookOut],
) -> list[SeriesOut]:
    output: list[SeriesOut] = []
    for series in series_rows:
        books: list[BookOut] = []
        for membership, book in memberships_by_series_id.get(series.id, []):
            enriched = book_payloads_by_id[book.id].model_copy(
                update={"marked_complete_in_series": membership.marked_complete}
            )
            books.append(enriched)
        output.append(
            SeriesOut(
                id=series.id,
                name=series.name,
                description=series.description,
                created_at=series.created_at,
                books=books,
            )
        )
    return output


async def build_series_out_list(
    db: AsyncSession,
    *,
    series_rows: Sequence[Series],
    membership_rows: Sequence[tuple[SeriesBook, Book]],
    user_id: uuid.UUID,
) -> list[SeriesOut]:
    ordered_books: list[Book] = []
    memberships_by_series_id: dict[uuid.UUID, list[tuple[SeriesBook, Book]]] = {}
    seen_book_ids: set[uuid.UUID] = set()
    for membership, book in membership_rows:
        memberships_by_series_id.setdefault(membership.series_id, []).append((membership, book))
        if book.id in seen_book_ids:
            continue
        seen_book_ids.add(book.id)
        ordered_books.append(book)
    book_payloads = await build_book_out_list(db, books=ordered_books, user_id=user_id)
    book_payloads_by_id = {payload.id: payload for payload in book_payloads}
    return _build_series_out_from_grouped_rows(
        series_rows=series_rows,
        memberships_by_series_id=memberships_by_series_id,
        book_payloads_by_id=book_payloads_by_id,
    )


async def build_single_series_out(
    db: AsyncSession,
    *,
    series: Series,
    user_id: uuid.UUID,
) -> SeriesOut:
    membership_rows = (
        await db.execute(
            select(SeriesBook, Book)
            .join(Book, Book.id == SeriesBook.book_id)
            .where(SeriesBook.series_id == series.id, Book.user_id == user_id)
            .order_by(SeriesBook.position, Book.created_at)
        )
    ).all()
    return (
        await build_series_out_list(
            db,
            series_rows=[series],
            membership_rows=membership_rows,
            user_id=user_id,
        )
    )[0]


async def book_out(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
    *,
    context: BookRenderContext | None = None,
    progress: ReadingProgress | None = None,
) -> BookOut:
    access = collaboration.build_book_access_context(
        book, user_id=user_id, collaborator=collaborator
    )
    if context is None:
        if progress is None:
            progress = (
                (
                    await db.execute(
                        select(ReadingProgress).where(
                            ReadingProgress.book_id == book.id,
                            ReadingProgress.user_id == user_id,
                        )
                    )
                )
                .scalars()
                .first()
            )
        total_words = (
            await db.scalar(
                select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                    Chapter.book_id == book.id
                )
            )
        ) or 0
        cover_url = cover_url_for_book(book)
    else:
        progress = context.progress_by_book_id.get(book.id)
        total_words = context.total_words_by_book_id.get(book.id, 0)
        cover_url = context.cover_url_by_book_id.get(book.id)
    chapters_read_count = len(set(progress.chapters_read or [])) if progress else 0
    total = book.total_chapters or 0
    percent = round((chapters_read_count / total) * 100, 1) if total else 0.0
    chapters_left = max(total - chapters_read_count, 0) if total else None
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        genre=book.genre,
        format=book.format,
        work_type=book.work_type,
        status=book.status,
        mode=book.mode or "reader",
        workspace_shell=access.workspace_shell,
        access_class=access.access_class,
        can_switch_workspace_mode=access.can_switch_workspace_mode,
        source_kind=book.source_kind or "single_upload",
        preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
        preserve_source_chapters=bool(book.preserve_source_chapters),
        cover_url=cover_url,
        total_chapters=book.total_chapters,
        total_tokens=book.total_tokens,
        total_words=int(total_words),
        is_truncated=book.is_truncated,
        primary_series_id=book.primary_series_id,
        series_name=book.series_name,
        series_order=book.series_order,
        is_public=book.is_public,
        public_status=getattr(book, "public_status", "draft"),
        public_slug=getattr(book, "public_slug", None),
        published_at=getattr(book, "published_at", None),
        public_updated_at=getattr(book, "public_updated_at", None),
        public_visibility=getattr(book, "public_visibility", "private"),
        rights_confirmation=bool(getattr(book, "rights_confirmation", False)),
        rights_confirmation_at=getattr(book, "rights_confirmation_at", None),
        content_source_type=getattr(book, "content_source_type", "user_original"),
        moderation_status=getattr(book, "moderation_status", "clean"),
        moderation_reason=getattr(book, "moderation_reason", None),
        takedown_reason=getattr(book, "takedown_reason", None),
        takedown_at=getattr(book, "takedown_at", None),
        public_upload_counted_at=getattr(book, "public_upload_counted_at", None),
        source_title=getattr(book, "source_title", None),
        source_author=getattr(book, "source_author", None),
        source_public_domain_note=getattr(book, "source_public_domain_note", None),
        source_url=getattr(book, "source_url", None),
        public_description=book.public_description,
        public_share_status=getattr(book, "public_share_status", None),
        public_share_requested_at=getattr(book, "public_share_requested_at", None),
        public_share_approved_at=getattr(book, "public_share_approved_at", None),
        copyright_warning=book.copyright_warning,
        is_editor_project=bool(getattr(book, "is_editor_project", False)),
        archived_at=book.archived_at,
        hidden_at=book.hidden_at,
        created_at=book.created_at,
        progress_pct=percent,
        chapters_read_count=chapters_read_count,
        chapters_left=chapters_left,
        processing=build_book_processing_payload(book),
        collaboration_role=access.collaboration_role,
        collaboration_scope=collaboration.collaboration_scope_model(access.collaboration_scope)
        if access.collaboration_scope
        else None,
        collaboration_permissions=(
            collaboration.collaboration_permissions_model(
                access.collaboration_permissions,
                role=access.collaboration_role or "viewer",
                scope=access.collaboration_scope,
            )
            if access.collaboration_permissions and access.collaboration_role
            else None
        ),
    )


# ─── Cover helpers ────────────────────────────────────────────────────────────


def cover_url_for_book(book: Book) -> str | None:
    if not book.cover_s3_key:
        return None
    token = create_asset_token(str(book.user_id), f"book-cover:{book.id}", expires_minutes=120)
    return f"{settings.API_V1_PREFIX}/books/{book.id}/cover?token={token}"


def build_blank_cover_image(title: str, author: str | None = None) -> tuple[bytes, str]:
    image = Image.new("RGB", (1200, 1800), color=(248, 245, 238))
    draw = ImageDraw.Draw(image)

    def load_font(size: int) -> ImageFont.ImageFont:
        for candidate in ("DejaVuSans.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    title_font = load_font(72)
    author_font = load_font(40)
    text_color = (28, 25, 23)
    accent_color = (79, 70, 229)
    max_text_width = 860

    def wrap_text(value: str, font: ImageFont.ImageFont) -> list[str]:
        words = [part for part in value.split() if part]
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if width <= max_text_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    normalized_title = " ".join((title or "").split()).strip() or "Untitled"
    normalized_author = " ".join((author or "").split()).strip()
    title_lines = wrap_text(normalized_title, title_font)[:5]
    if not title_lines:
        title_lines = ["Untitled"]
    author_line = normalized_author or "Unknown author"

    draw.rounded_rectangle(
        (180, 220, 1020, 1540), radius=36, outline=accent_color, width=8, fill=(255, 255, 255)
    )
    draw.rectangle((180, 220, 1020, 290), fill=accent_color)
    draw.text((600, 245), "LoreVia", font=author_font, fill=(255, 255, 255), anchor="mm")

    y = 520
    for line in title_lines:
        draw.text((600, y), line, font=title_font, fill=text_color, anchor="mm")
        y += 70

    draw.line((330, y + 30, 870, y + 30), fill=(203, 213, 225), width=3)
    draw.text((600, y + 110), author_line, font=author_font, fill=(68, 64, 60), anchor="mm")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"


async def ensure_book_cover(db: AsyncSession, book: Book) -> None:
    if book.format == "pdf" and not book.cover_s3_key and book.s3_key:
        from app.parsers.pdf_parser import extract_first_page_cover

        try:
            raw_book = await asyncio.to_thread(download_book, book.s3_key)
        except STORAGE_IO_EXCEPTIONS:
            raw_book = None

        if raw_book:
            try:
                cover = await asyncio.to_thread(extract_first_page_cover, raw_book)
            except COVER_RENDER_EXCEPTIONS:
                cover = None
            if cover:
                cover_bytes, content_type = cover
                try:
                    book.cover_s3_key = await asyncio.to_thread(
                        upload_binary,
                        f"covers/{book.user_id}/{uuid.uuid4()}.png",
                        cover_bytes,
                        content_type,
                    )
                    await db.flush()
                except COVER_PERSIST_EXCEPTIONS:
                    return

    if not book.cover_s3_key:
        try:
            cover_bytes, content_type = await asyncio.to_thread(
                build_blank_cover_image, book.title, book.author
            )
        except COVER_RENDER_EXCEPTIONS:
            return

        try:
            book.cover_s3_key = await asyncio.to_thread(
                upload_binary,
                f"covers/{book.user_id}/{uuid.uuid4()}.png",
                cover_bytes,
                content_type,
            )
            await db.flush()
        except COVER_PERSIST_EXCEPTIONS:
            return


# ─── Progress / word-count helpers ───────────────────────────────────────────


async def compute_words_read_for_book(
    db: AsyncSession,
    book: Book,
    progress: ReadingProgress | None,
    *,
    chapter_word_count_map: dict[tuple[uuid.UUID, int], int] | None = None,
    allow_content_fallback: bool = True,
) -> int:
    if progress is None:
        return 0

    read_chapters = sorted(set(progress.chapters_read or []))
    total_words = 0
    counted_chapters = set(read_chapters)

    for chapter_number in read_chapters:
        total_words += await chapter_word_count(
            db,
            book.id,
            chapter_number,
            chapter_word_count_map=chapter_word_count_map,
            allow_content_fallback=allow_content_fallback,
        )

    current_chapter = progress.current_chapter or 0
    if current_chapter > 0 and current_chapter not in counted_chapters:
        chapter_words = await chapter_word_count(
            db,
            book.id,
            current_chapter,
            chapter_word_count_map=chapter_word_count_map,
            allow_content_fallback=allow_content_fallback,
        )
        total_words += int(round(chapter_words * max(0.0, min(progress.scroll_pct or 0.0, 1.0))))

    return total_words


async def compute_words_read_for_books(
    db: AsyncSession,
    *,
    books: Sequence[Book],
    progress_rows: Sequence[ReadingProgress],
) -> dict[uuid.UUID, int]:
    if not books or not progress_rows:
        return {}

    relevant_numbers_by_book: dict[uuid.UUID, set[int]] = {}
    progress_by_book_id: dict[uuid.UUID, ReadingProgress] = {}
    for progress in progress_rows:
        progress_by_book_id[progress.book_id] = progress
        numbers = relevant_numbers_by_book.setdefault(progress.book_id, set())
        for chapter_number in progress.chapters_read or []:
            if chapter_number is not None:
                numbers.add(int(chapter_number))
        current_chapter = int(progress.current_chapter or 0)
        if current_chapter > 0:
            numbers.add(current_chapter)

    if not relevant_numbers_by_book:
        return {}

    chapter_rows = (
        await db.execute(
            select(Chapter.book_id, Chapter.number, Chapter.word_count).where(
                Chapter.book_id.in_(list(relevant_numbers_by_book.keys()))
            )
        )
    ).all()
    chapter_word_counts = {
        (book_id, int(chapter_number)): int(word_count or 0)
        for book_id, chapter_number, word_count in chapter_rows
        if chapter_number is not None
    }
    totals: dict[uuid.UUID, int] = {}
    for book in books:
        totals[book.id] = await compute_words_read_for_book(
            db,
            book,
            progress_by_book_id.get(book.id),
            chapter_word_count_map=chapter_word_counts,
            allow_content_fallback=False,
        )
    return totals


async def chapter_word_count(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_number: int,
    *,
    chapter_word_count_map: dict[tuple[uuid.UUID, int], int] | None = None,
    allow_content_fallback: bool = True,
) -> int:
    if chapter_word_count_map is not None:
        return int(chapter_word_count_map.get((book_id, chapter_number), 0))
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_number)
        )
    ).scalar()
    if chapter is None:
        return 0
    if chapter.word_count:
        return chapter.word_count
    if not chapter.s3_key or not allow_content_fallback:
        return 0
    try:
        raw = await asyncio.to_thread(download_book, chapter.s3_key)
    except STORAGE_IO_EXCEPTIONS:
        return 0
    stored = manuscript.deserialize_manuscript_content(raw)
    text = manuscript.clean_markdown_asterisks_str(str(stored.get("text") or ""))
    return len(text.replace("\r", " ").replace("\n", " ").split())
