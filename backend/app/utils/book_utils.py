"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import bleach  # type: ignore[import-untyped]
from bleach.css_sanitizer import CSSSanitizer
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_asset_token
from app.core.storage import download_book, get_presigned_url, upload_binary
from app.models.book import Book, BookNote, Chapter, ChapterVersion, ObsidianVaultNote, Series
from app.models.character import Character, CharacterState
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread
from app.models.progress import ReadingProgress
from app.schemas.books import BookOut, ChapterConsistencyReport, ChapterReportCharacter
from app.utils.cover_processor import ProcessedCover, process_cover

if TYPE_CHECKING:
    pass


MANUSCRIPT_ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "h1",
    "h2",
    "h3",
    "blockquote",
    "ul",
    "ol",
    "li",
    "span",
    "div",
]
MANUSCRIPT_ALLOWED_ATTRIBUTES = {
    "p": ["style", "class", "data-text-align"],
    "div": ["style", "class", "data-text-align"],
    "span": ["style", "class"],
    "h1": ["style", "class", "data-text-align"],
    "h2": ["style", "class", "data-text-align"],
    "h3": ["style", "class", "data-text-align"],
    "blockquote": ["style", "class", "data-text-align"],
    "ul": ["style", "class"],
    "ol": ["style", "class"],
    "li": ["style", "class"],
}
MANUSCRIPT_ALLOWED_STYLES = ["text-align"]


# ─── Ownership guards ─────────────────────────────────────────────────────────

async def get_owned_book(db: AsyncSession, book_id: uuid.UUID, user_id: uuid.UUID) -> Book:
    book = await db.get(Book, book_id)
    if not book or book.user_id != user_id:
        raise HTTPException(404, "Book not found")
    return book


async def get_owned_series(db: AsyncSession, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
    series = await db.get(Series, series_id)
    if not series or series.user_id != user_id:
        raise HTTPException(404, "Series not found")
    return series


async def list_book_notes(db: AsyncSession, book: Book) -> list[dict]:
    rows = (
        await db.execute(
            select(BookNote, Chapter.title)
            .outerjoin(
                Chapter,
                (Chapter.book_id == BookNote.book_id) & (Chapter.number == BookNote.chapter_number),
            )
            .where(BookNote.book_id == book.id)
            .order_by(BookNote.chapter_number.asc().nullsfirst(), BookNote.updated_at.desc())
        )
    ).all()
    return [
        {
            "id": str(note.id),
            "book_id": str(book.id),
            "book_title": book.title,
            "chapter_number": note.chapter_number,
            "chapter_title": chapter_title,
            "title": note.title,
            "body": note.body,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note, chapter_title in rows
    ]


async def list_user_notes(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(BookNote, Book.title, Chapter.title)
            .join(Book, Book.id == BookNote.book_id)
            .outerjoin(
                Chapter,
                (Chapter.book_id == BookNote.book_id) & (Chapter.number == BookNote.chapter_number),
            )
            .where(BookNote.user_id == user_id)
            .order_by(BookNote.updated_at.desc())
        )
    ).all()
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "book_title": book_title,
            "chapter_number": note.chapter_number,
            "chapter_title": chapter_title,
            "title": note.title,
            "body": note.body,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note, book_title, chapter_title in rows
    ]


async def list_obsidian_vault_notes(db: AsyncSession, book: Book, user_id: uuid.UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(ObsidianVaultNote)
            .where(ObsidianVaultNote.book_id == book.id, ObsidianVaultNote.user_id == user_id)
            .order_by(ObsidianVaultNote.path.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "path": note.path,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note in rows
    ]


async def load_obsidian_vault_overrides(db: AsyncSession, book: Book, user_id: uuid.UUID) -> dict[str, str]:
    rows = (
        await db.execute(
            select(ObsidianVaultNote.path, ObsidianVaultNote.content)
            .where(ObsidianVaultNote.book_id == book.id, ObsidianVaultNote.user_id == user_id)
        )
    ).all()
    return {path: content for path, content in rows}


async def save_obsidian_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    content: str,
) -> dict:
    normalized_path = (path or "").replace("\\", "/").strip()
    if not normalized_path:
        raise HTTPException(400, "Path is required")

    normalized_content = content.replace("\r\n", "\n")

    note: ObsidianVaultNote | None = (
        await db.execute(
            select(ObsidianVaultNote).where(
                ObsidianVaultNote.book_id == book.id,
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.path == normalized_path,
            )
        )
    ).scalars().first()

    if note is None:
        note = ObsidianVaultNote(user_id=user_id, book_id=book.id, path=normalized_path, content=normalized_content)
        db.add(note)
    else:
        note.path = normalized_path
        note.content = normalized_content

    await db.commit()
    await db.refresh(note)
    return {
        "path": note.path,
        "content": note.content,
        "persisted": True,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def save_book_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    note_id: str | None,
    chapter_number: int | None,
    title: str | None,
    body: str,
) -> dict:
    normalized_title = bleach.clean(" ".join((title or "").split()).strip(), tags=[], strip=True) or None
    normalized_body = bleach.clean(body.strip(), tags=[], strip=True)
    if not normalized_body:
        raise HTTPException(400, "Note body is required")

    if chapter_number is not None and chapter_number < 1:
        raise HTTPException(400, "Invalid chapter number")

    note: BookNote | None = None
    if note_id:
        try:
            parsed_note_id = uuid.UUID(note_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid note id") from exc
        note = await db.get(BookNote, parsed_note_id)
        if not note or note.user_id != user_id or note.book_id != book.id:
            raise HTTPException(404, "Note not found")
    else:
        note = BookNote(user_id=user_id, book_id=book.id)
        db.add(note)

    note.chapter_number = chapter_number
    note.title = normalized_title
    note.body = normalized_body
    await db.commit()
    await db.refresh(note)

    chapter_title = None
    if note.chapter_number is not None:
        chapter_title = (
            await db.execute(
                select(Chapter.title).where(Chapter.book_id == book.id, Chapter.number == note.chapter_number)
            )
        ).scalar_one_or_none()

    return {
        "id": str(note.id),
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": note.chapter_number,
        "chapter_title": chapter_title,
        "title": note.title,
        "body": note.body,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def delete_book_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    note_id: uuid.UUID,
) -> None:
    deleted = await db.execute(
        delete(BookNote).where(
            BookNote.id == note_id,
            BookNote.user_id == user_id,
            BookNote.book_id == book.id,
        )
    )
    if not deleted.rowcount:
        raise HTTPException(404, "Note not found")
    await db.commit()


async def resolve_owned_series_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    series_ids: list[str],
) -> list[Series]:
    cleaned_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    for raw in series_ids:
        value = (raw or "").strip()
        if not value:
            continue
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise HTTPException(400, "Invalid series id") from exc
        if parsed in seen:
            continue
        seen.add(parsed)
        cleaned_ids.append(parsed)

    if not cleaned_ids:
        return []

    rows = (
        await db.execute(
            select(Series).where(Series.user_id == user_id, Series.id.in_(cleaned_ids))
        )
    ).scalars().all()
    found = {series.id for series in rows}
    if len(found) != len(cleaned_ids):
        raise HTTPException(404, "Series not found")

    order = {series_id: index for index, series_id in enumerate(cleaned_ids)}
    return sorted(rows, key=lambda series: order[series.id])


# ─── BookOut construction ─────────────────────────────────────────────────────

async def book_out(db: AsyncSession, book: Book, user_id: uuid.UUID) -> BookOut:
    await ensure_book_cover(db, book)
    progress = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.book_id == book.id,
                ReadingProgress.user_id == user_id,
            )
        )
    ).scalars().first()
    chapters_read_count = len(set(progress.chapters_read or [])) if progress else 0
    total = book.total_chapters or 0
    percent = round((chapters_read_count / total) * 100, 1) if total else 0.0
    chapters_left = max(total - chapters_read_count, 0) if total else None
    cover_url = cover_url_for_book(book)
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        genre=book.genre,
        format=book.format,
        status=book.status,
        mode=book.mode or "reader",
        source_kind=book.source_kind or "single_upload",
        cover_url=cover_url,
        cover_processed_url=processed_cover_url_for_book(book),
        cover_edge_colors=book.cover_edge_colors or None,
        cover_processed_at=book.cover_processed_at,
        cover_crop_bounds=book.cover_crop_bounds or None,
        total_chapters=book.total_chapters,
        total_tokens=book.total_tokens,
        is_truncated=book.is_truncated,
        primary_series_id=book.primary_series_id,
        series_name=book.series_name,
        series_order=book.series_order,
        is_public=book.is_public,
        public_description=book.public_description,
        copyright_warning=book.copyright_warning,
        archived_at=book.archived_at,
        hidden_at=book.hidden_at,
        created_at=book.created_at,
        progress_pct=percent,
        chapters_read_count=chapters_read_count,
        chapters_left=chapters_left,
    )


# ─── Cover helpers ────────────────────────────────────────────────────────────

def cover_url_for_book(book: Book) -> str | None:
    if not book.cover_s3_key:
        return None
    presigned = get_presigned_url(book.cover_s3_key)
    if presigned:
        return presigned
    token = create_asset_token(str(book.user_id), f"book-cover:{book.id}", expires_minutes=120)
    return f"{settings.API_V1_PREFIX}/books/{book.id}/cover?token={token}"


def processed_cover_url_for_book(book: Book) -> str | None:
    if not book.cover_s3_key:
        return None
    token = create_asset_token(str(book.user_id), f"book-cover-processed:{book.id}", expires_minutes=120)
    return f"{settings.API_V1_PREFIX}/books/{book.id}/cover/processed?token={token}"


async def process_and_store_book_cover(
    db: AsyncSession,
    book: Book,
    cover_bytes: bytes,
) -> ProcessedCover | None:
    if not cover_bytes:
        return None
    try:
        processed = await asyncio.to_thread(process_cover, cover_bytes)
        processed_key = await asyncio.to_thread(
            upload_binary,
            f"covers/{book.user_id}/{book.id}/processed/{uuid.uuid4()}.png",
            processed.image_bytes,
            processed.mime_type,
        )
    except Exception:
        return None

    book.cover_processed_url = processed_key
    book.cover_edge_colors = processed.edge_colors
    book.cover_processed_at = datetime.now(UTC)
    book.cover_crop_bounds = processed.crop_bounds
    await db.flush()
    return processed


async def ensure_book_cover(db: AsyncSession, book: Book, *, force: bool = False) -> None:
    if book.format == "pdf" and not book.cover_s3_key and book.s3_key:
        from app.parsers.pdf_parser import extract_first_page_cover

        try:
            raw_book = await asyncio.to_thread(download_book, book.s3_key)
        except Exception:
            raw_book = None

        if raw_book:
            cover = await asyncio.to_thread(extract_first_page_cover, raw_book)
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
                except Exception:
                    return

    if not book.cover_s3_key or (book.cover_processed_url and not force):
        return

    try:
        raw = await asyncio.to_thread(download_book, book.cover_s3_key)
    except Exception:
        return

    try:
        await process_and_store_book_cover(db, book, raw)
        await db.commit()
        await db.refresh(book)
    except Exception:
        return


# ─── Progress / word-count helpers ───────────────────────────────────────────

async def compute_words_read_for_book(
    db: AsyncSession,
    book: Book,
    progress: ReadingProgress | None,
) -> int:
    if progress is None:
        return 0

    read_chapters = sorted(set(progress.chapters_read or []))
    total_words = 0
    counted_chapters = set(read_chapters)

    for chapter_number in read_chapters:
        total_words += await chapter_word_count(db, book.id, chapter_number)

    current_chapter = progress.current_chapter or 0
    if current_chapter > 0 and current_chapter not in counted_chapters:
        chapter_words = await chapter_word_count(db, book.id, current_chapter)
        total_words += int(round(chapter_words * max(0.0, min(progress.scroll_pct or 0.0, 1.0))))

    return total_words


async def chapter_word_count(db: AsyncSession, book_id: uuid.UUID, chapter_number: int) -> int:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_number)
        )
    ).scalar()
    if chapter is None:
        return 0
    if chapter.word_count:
        return chapter.word_count
    if not chapter.s3_key:
        return 0
    try:
        stored = deserialize_manuscript_content(download_book(chapter.s3_key))
        text = clean_markdown_asterisks_str(str(stored.get("text") or ""))
    except Exception:
        return 0
    return len(text.replace("\r", " ").replace("\n", " ").split())


def clean_markdown_asterisks_str(text: str) -> str:
    """Remove asterisks for word counting only - does not strip markdown syntax for display."""
    if not text:
        return ""
    return text.replace("**", "").replace("*", "")


def markdown_to_html(markdown_text: str) -> str:
    """Convert markdown text to HTML using markdown-it-py."""
    if not markdown_text:
        return ""
    try:
        from markdown_it import MarkdownIt

        md = MarkdownIt()
        html = md.render(markdown_text)
        # Clean the HTML to ensure it only contains allowed tags
        return clean_manuscript_html(html)
    except ImportError:
        # Fallback if markdown-it-py is not installed
        # Basic conversion for common markdown elements
        lines = markdown_text.split("\n")
        html_parts = []
        in_paragraph = False

        for line in lines:
            line = line.strip()
            if not line:
                if in_paragraph:
                    html_parts.append("</p>")
                    in_paragraph = False
                continue

            # Headers
            if line.startswith("#"):
                if in_paragraph:
                    html_parts.append("</p>")
                    in_paragraph = False
                level = len(line) - len(line.lstrip("#"))
                if level <= 6:
                    content = line.lstrip("#").strip()
                    html_parts.append(f"<h{level}>{content}</h{level}>")
                else:
                    html_parts.append(f"<p>{line}</p>")
            # Lists
            elif line.startswith("- ") or line.startswith("* "):
                if in_paragraph:
                    html_parts.append("</p>")
                    in_paragraph = False
                content = line[2:].strip()
                html_parts.append(f"<li>{content}</li>")
            # Bold/italic
            else:
                if not in_paragraph:
                    html_parts.append("<p>")
                    in_paragraph = True
                # Simple bold/italic replacement
                line = line.replace("**", "<strong>").replace("*", "<em>")
                line = line.replace("<strong>", "<strong>", 1).replace("<em>", "<em>", 1)
                # Close tags (simplified)
                line = line.replace("<strong>", "<strong>", line.count("<strong>"))
                line = line.replace("<em>", "<em>", line.count("<em>"))
                html_parts.append(line)

        if in_paragraph:
            html_parts.append("</p>")

        return clean_manuscript_html("".join(html_parts))


def manuscript_text_to_html(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return "<p></p>"
    paragraphs = [segment.strip() for segment in cleaned.split("\n\n")]
    html_parts: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        lines = [bleach.clean(line, tags=[], strip=True) for line in paragraph.split("\n")]
        html_parts.append(f"<p>{'<br>'.join(line for line in lines if line or len(lines) == 1)}</p>")
    return "".join(html_parts) or "<p></p>"


def clean_manuscript_html(html: str | None) -> str:
    cleaner = CSSSanitizer(allowed_css_properties=MANUSCRIPT_ALLOWED_STYLES)
    return bleach.clean(
        (html or "").strip(),
        tags=MANUSCRIPT_ALLOWED_TAGS,
        attributes=MANUSCRIPT_ALLOWED_ATTRIBUTES,
        css_sanitizer=cleaner,
        strip=True,
    )


def manuscript_html_to_text(html: str | None) -> str:
    from bs4 import BeautifulSoup

    cleaned_html = clean_manuscript_html(html)
    if not cleaned_html:
        return ""

    soup = BeautifulSoup(cleaned_html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")

    blocks: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "p", "blockquote", "li"]):
        text = node.get_text("\n", strip=False)
        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if normalized:
            blocks.append(normalized)

    if not blocks:
        return soup.get_text("\n", strip=True)

    return "\n\n".join(blocks)


def serialize_manuscript_content(text: str, html: str | None = None) -> str:
    normalized_text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized_html = clean_manuscript_html(html) if html else ""
    if not normalized_html and normalized_text:
        normalized_html = manuscript_text_to_html(normalized_text)
    if not normalized_html:
        return normalized_text
    normalized_text = manuscript_html_to_text(normalized_html) or normalized_text
    return json.dumps(
        {"format": "rich_text_v1", "html": normalized_html, "text": normalized_text},
        ensure_ascii=False,
    )


def deserialize_manuscript_content(raw: str | bytes | None) -> dict[str, str | None]:
    if raw is None:
        return {"format": "plain_text", "text": "", "html": None}
    raw_text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
    trimmed = raw_text.strip()
    if not trimmed:
        return {"format": "plain_text", "text": "", "html": None}
    try:
        payload = json.loads(trimmed)
    except json.JSONDecodeError:
        return {"format": "plain_text", "text": raw_text, "html": manuscript_text_to_html(raw_text)}

    if isinstance(payload, dict) and payload.get("format") == "rich_text_v1":
        html = clean_manuscript_html(str(payload.get("html") or ""))
        text = manuscript_html_to_text(html) or str(payload.get("text") or "")
        return {"format": "rich_text_v1", "text": text, "html": html or manuscript_text_to_html(text)}

    return {"format": "plain_text", "text": raw_text, "html": manuscript_text_to_html(raw_text)}


def report_sentence(text: str | None) -> str:
    cleaned = clean_markdown_asterisks_str((text or "").strip())
    if not cleaned:
        return ""
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return lines[0] if lines else ""


# ─── Chapter number helpers ───────────────────────────────────────────────────

async def next_chapter_number(db: AsyncSession, book_id: uuid.UUID) -> int:
    current_max = await db.scalar(select(func.max(Chapter.number)).where(Chapter.book_id == book_id))
    return int(current_max or 0) + 1


# ─── Manuscript import helpers ────────────────────────────────────────────────

async def parse_import_upload(filename: str, raw: bytes, split_into_chapters: bool) -> list[dict]:
    lower = filename.lower()
    stem = os.path.splitext(os.path.basename(filename))[0] or "Imported chapter"
    if lower.endswith(".pdf"):
        from app.parsers.pdf_parser import parse_pdf
        chapters = await asyncio.to_thread(parse_pdf, raw)
        if split_into_chapters and chapters:
            return chapters
        merged_text = "\n\n".join((ch.get("text") or "").strip() for ch in chapters if ch.get("text"))
        return [{"title": stem, "text": merged_text or "", "number": 1}]
    if lower.endswith(".epub"):
        from app.parsers.epub_parser import parse_epub
        chapters = await asyncio.to_thread(parse_epub, raw)
        if split_into_chapters and chapters:
            return chapters
        merged_text = "\n\n".join((ch.get("text") or "").strip() for ch in chapters if ch.get("text"))
        return [{"title": stem, "text": merged_text or "", "number": 1}]
    if lower.endswith(".docx"):
        from io import BytesIO

        from docx import Document
        doc = Document(BytesIO(raw))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
        return [{"title": stem, "text": text, "number": 1}]
    if lower.endswith(".doc"):
        # Legacy .doc format requires additional system dependencies (antiword/textract)
        # For now, we'll attempt to use python-docx which may work for some .doc files
        # that are actually .docx with wrong extension
        try:
            from io import BytesIO

            from docx import Document
            doc = Document(BytesIO(raw))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
            return [{"title": stem, "text": text, "number": 1}]
        except Exception:
            raise HTTPException(
                400,
                "Legacy .doc files require additional system dependencies. Please convert to .docx format."
            )
    if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".fountain"):
        text = raw.decode("utf-8", errors="ignore")
        if lower.endswith(".md"):
            # Convert markdown to HTML for proper rendering
            html = markdown_to_html(text)
            return [{"title": stem, "text": text, "html": html, "number": 1}]
        return [{"title": stem, "text": text, "number": 1}]
    raise HTTPException(400, f"Unsupported manuscript import file: {filename}")


async def parse_screenplay_upload(filename: str, raw: bytes) -> list[dict]:
    """Parse screenplay files and return scene data."""
    lower = filename.lower()
    stem = os.path.splitext(os.path.basename(filename))[0] or "Imported screenplay"
    
    if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".fountain"):
        text = raw.decode("utf-8", errors="ignore")
        from app.parsers.screenplay_parser import analyze_screenplay_stats, parse_screenplay
        
        scenes = await asyncio.to_thread(parse_screenplay, text)
        stats = await asyncio.to_thread(analyze_screenplay_stats, scenes)
        
        return [{
            "title": stem,
            "text": text,
            "scenes": len(scenes),
            "stats": stats,
            "number": 1
        }]
    
    # For PDF screenplays, extract text then parse
    if lower.endswith(".pdf"):
        from app.parsers.pdf_parser import parse_pdf
        chapters = await asyncio.to_thread(parse_pdf, raw)
        merged_text = "\n\n".join((ch.get("text") or "").strip() for ch in chapters if ch.get("text"))
        
        from app.parsers.screenplay_parser import analyze_screenplay_stats, parse_screenplay
        scenes = await asyncio.to_thread(parse_screenplay, merged_text)
        stats = await asyncio.to_thread(analyze_screenplay_stats, scenes)
        
        return [{
            "title": stem,
            "text": merged_text,
            "scenes": len(scenes),
            "stats": stats,
            "number": 1
        }]
    
    raise HTTPException(400, f"Unsupported screenplay format: {filename}")


def is_screenplay_file(filename: str) -> bool:
    """Check if file is likely a screenplay based on extension."""
    screenplay_extensions = {".fountain", ".screenplay", ".script"}
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in screenplay_extensions) or "screenplay" in lower


def normalize_imported_chapters(
    chapters: list[dict],
    *,
    chapter_number: int | None,
    start_number: int,
    replace_existing: bool,
    chunk_long_documents: bool,
) -> list[dict]:
    normalized: list[dict] = []
    running_number = start_number
    for chapter in chapters:
        text = (chapter.get("text") or "").strip()
        if not text:
            continue
        title = bleach.clean((" ".join(str(chapter.get("title") or "").split())).strip(), tags=[], strip=True) or None
        html = clean_manuscript_html(chapter.get("html")) if chapter.get("html") else None
        desired_number = chapter_number if replace_existing and chapter_number else running_number
        parts = split_long_document(text) if chunk_long_documents else [text]
        for index, part in enumerate(parts, start=1):
            part_title = title
            if len(parts) > 1:
                base = title or f"Chapter {desired_number}"
                part_title = f"{base} (Part {index})"
            normalized.append({
                "number": desired_number,
                "title": part_title,
                "text": part,
                "html": html if len(parts) == 1 else manuscript_text_to_html(part),
            })
            desired_number += 1
        running_number = desired_number
    return normalized


def split_long_document(text: str, max_words: int = 3500) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parts: list[str] = []
    bucket: list[str] = []
    bucket_words = 0
    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        if bucket and bucket_words + paragraph_words > max_words:
            parts.append("\n\n".join(bucket))
            bucket = []
            bucket_words = 0
        bucket.append(paragraph)
        bucket_words += paragraph_words
    if bucket:
        parts.append("\n\n".join(bucket))
    return parts or [text]


# ─── Misc ─────────────────────────────────────────────────────────────────────

def as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


async def build_chapter_consistency_report(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
) -> ChapterConsistencyReport:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")

    short_summary = (
        await db.execute(
            select(ChapterSummary).where(
                ChapterSummary.chapter_id == chapter.id,
                ChapterSummary.mode == "short",
            )
        )
    ).scalar()

    new_characters = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book.id, Character.first_chapter == chapter_number)
            .order_by(Character.name)
        )
    ).scalars().all()

    character_names = (
        await db.execute(
            select(Character.id, Character.name).where(Character.book_id == book.id)
        )
    ).all()
    names_by_id = {char_id: name for char_id, name in character_names}

    relationship_changes = []
    seen_relationships: set[tuple[str, str, str]] = set()
    rels = (
        await db.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.book_id == book.id,
                CharacterRelationship.from_chapter == chapter_number,
            )
        )
    ).scalars().all()
    for rel in rels:
        a_name = names_by_id.get(rel.character_a_id, "Unknown")
        b_name = names_by_id.get(rel.character_b_id, "Unknown")
        key = tuple(sorted((a_name, b_name)) + [rel.rel_type])
        if key in seen_relationships:
            continue
        seen_relationships.add(key)
        relationship_changes.append(
            f"{a_name} and {b_name}: {rel.rel_type.replace('_', ' ')}"
            + (f" — {rel.description}" if rel.description else "")
        )

    opened_threads = (
        await db.execute(
            select(PlotThread).where(
                PlotThread.book_id == book.id,
                PlotThread.introduced_at == chapter_number,
            )
            .order_by(PlotThread.importance.desc(), PlotThread.title)
        )
    ).scalars().all()
    resolved_threads = (
        await db.execute(
            select(PlotThread).where(
                PlotThread.book_id == book.id,
                PlotThread.resolved_at == chapter_number,
            )
            .order_by(PlotThread.importance.desc(), PlotThread.title)
        )
    ).scalars().all()

    continuity_flags = await detect_chapter_continuity_flags(db, book.id, chapter_number)
    summary_line = report_sentence(short_summary.content if short_summary else "")
    if not summary_line:
        summary_line = f"Chapter {chapter_number} was imported and analysed."

    additions = []
    if new_characters:
        additions.append(f"{len(new_characters)} new character{'s' if len(new_characters) != 1 else ''}")
    if relationship_changes:
        additions.append(f"{len(relationship_changes)} relationship shift{'s' if len(relationship_changes) != 1 else ''}")
    if opened_threads:
        additions.append(f"{len(opened_threads)} plot thread{'s' if len(opened_threads) != 1 else ''} opened")
    if resolved_threads:
        additions.append(f"{len(resolved_threads)} resolved")
    if continuity_flags:
        additions.append(f"{len(continuity_flags)} continuity flag{'s' if len(continuity_flags) != 1 else ''}")
    if additions:
        summary_line = f"{summary_line} This upload surfaced " + ", ".join(additions) + "."

    return ChapterConsistencyReport(
        chapter_number=chapter_number,
        chapter_title=chapter.title,
        summary=summary_line,
        new_characters=[
            ChapterReportCharacter(
                id=str(char.id),
                name=char.name,
                role=char.role,
                first_chapter=char.first_chapter,
                arc_summary=char.arc_summary,
            )
            for char in new_characters
        ],
        relationship_changes=list(dict.fromkeys(relationship_changes[:6])),
        plot_threads_opened=list(dict.fromkeys(thread.title for thread in opened_threads[:6])),
        plot_threads_resolved=list(dict.fromkeys(thread.title for thread in resolved_threads[:6])),
        continuity_flags=list(dict.fromkeys(continuity_flags[:6])),
    )


async def detect_chapter_continuity_flags(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_number: int,
) -> list[str]:
    rows = (
        await db.execute(
            select(CharacterState, Character.name)
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book_id,
                CharacterState.at_chapter == chapter_number,
            )
        )
    ).all()
    if not rows:
        return []

    flags: list[str] = []
    watched_traits = {
        "eyes": "eye description",
        "hair": "hair description",
        "build": "build description",
        "age_descriptor": "age description",
        "distinguishing": "distinguishing feature",
    }

    for state, char_name in rows:
        previous = (
            await db.execute(
                select(CharacterState)
                .where(
                    CharacterState.character_id == state.character_id,
                    CharacterState.at_chapter < chapter_number,
                )
                .order_by(CharacterState.at_chapter.desc())
                .limit(1)
            )
        ).scalar()
        if previous is None:
            continue
        current_snapshot = state.trait_snapshot or {}
        previous_snapshot = previous.trait_snapshot or {}
        for trait_key, label in watched_traits.items():
            previous_value = _trait_value(previous_snapshot.get(trait_key))
            current_value = _trait_value(current_snapshot.get(trait_key))
            if previous_value and current_value and previous_value.lower() != current_value.lower():
                flags.append(
                    f"{char_name}: {label} changed from '{previous_value}' to '{current_value}' since chapter {previous.at_chapter}."
                )
                break

    return flags


def _trait_value(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("value")
        return value.strip() if isinstance(value, str) and value.strip() else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


# ─── Character card payload ───────────────────────────────────────────────────

async def build_character_card_payload(db: AsyncSession, book: Book, character: Character) -> dict:
    rels = (
        await db.execute(
            select(CharacterRelationship)
            .where(
                CharacterRelationship.book_id == book.id,
                (CharacterRelationship.character_a_id == character.id) | (CharacterRelationship.character_b_id == character.id),
            )
            .order_by(CharacterRelationship.from_chapter, CharacterRelationship.id)
        )
    ).scalars().all()

    other_ids = {
        rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        for rel in rels
    }
    others = (
        await db.execute(select(Character).where(Character.id.in_(other_ids)))
    ).scalars().all() if other_ids else []
    others_by_id = {other.id: other for other in others}

    from app.engine.character.profile_builder import build_description
    from app.utils.character_utils import character_status

    relationship_rows = []
    for rel in rels:
        counterpart_id = rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        counterpart = others_by_id.get(counterpart_id)
        relationship_rows.append(
            {
                "name": counterpart.name if counterpart else "Unknown character",
                "type": rel.rel_type.replace("_", " "),
                "description": rel.description,
                "sentiment": rel.sentiment,
                "from_chapter": rel.from_chapter,
                "to_chapter": rel.to_chapter,
            }
        )

    description = build_description(character.trait_state or {}, character.archetype)
    safe_name = "".join(ch for ch in (character.name or "character") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-") or "character"
    linked_threads = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book.id)
            .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
        )
    ).scalars().all()
    character_threads = [
        {
            "title": thread.title,
            "status": thread.status,
            "introduced_at": thread.introduced_at,
            "resolved_at": thread.resolved_at,
            "note": thread.note,
        }
        for thread in linked_threads
        if character.name in (thread.character_ids or [])
    ]
    continuity_watch: list[str] = []
    if character.last_seen_chapter and book.total_chapters and book.total_chapters - character.last_seen_chapter >= 25:
        continuity_watch.append(
            f"{character.name} has not appeared for {book.total_chapters - character.last_seen_chapter} chapters."
        )
    if character_threads:
        unresolved = [thread["title"] for thread in character_threads if thread["status"] not in {"resolved", "abandoned"}]
        if unresolved:
            continuity_watch.append(f"Still tied to unresolved threads: {', '.join(unresolved[:3])}.")
    return {
        "book_title": book.title,
        "character_id": str(character.id),
        "name": character.name,
        "aliases": character.aliases or [],
        "role": character.role,
        "status": character_status(character),
        "description": description,
        "first_appearance": character.first_chapter,
        "last_appearance": character.last_seen_chapter,
        "mentions_count": character.mention_count or 0,
        "personality_tags": character.personality_tags or [],
        "motivations": character.motivations or [],
        "fears": character.fears or [],
        "arc_summary": character.arc_summary,
        "growth_events": character.growth_events or [],
        "relationships": relationship_rows,
        "plot_threads": character_threads,
        "continuity_watch": continuity_watch,
        "filename_base": safe_name,
    }


async def list_chapter_consistency_reports(
    db: AsyncSession,
    book: Book,
    limit: int = 12,
) -> list[ChapterConsistencyReport]:
    chapter_numbers = (
        await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.desc())
            .limit(limit)
        )
    ).scalars().all()

    reports: list[ChapterConsistencyReport] = []
    for chapter_number in chapter_numbers:
        reports.append(await build_chapter_consistency_report(db, book, chapter_number))
    return reports


async def snapshot_chapter_version(
    db: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    note: str,
) -> ChapterVersion | None:
    if not chapter.s3_key:
        return None
    try:
        raw = await asyncio.to_thread(download_book, chapter.s3_key)
    except Exception:
        return None

    version_key = await asyncio.to_thread(
        upload_binary,
        f"versions/{book.user_id}/{book.id}/{chapter.number}/{uuid.uuid4()}.txt",
        raw,
        "text/plain; charset=utf-8",
    )
    version = ChapterVersion(
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        title=chapter.title,
        s3_key=version_key,
        word_count=chapter.word_count,
        note=note,
    )
    db.add(version)
    await db.flush()
    return version


async def list_chapter_versions(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
    limit: int = 12,
) -> list[dict]:
    versions = (
        await db.execute(
            select(ChapterVersion)
            .where(ChapterVersion.book_id == book.id, ChapterVersion.chapter_number == chapter_number)
            .order_by(ChapterVersion.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(version.id),
            "chapter_number": version.chapter_number,
            "title": version.title,
            "word_count": version.word_count,
            "note": version.note,
            "created_at": version.created_at,
        }
        for version in versions
    ]


async def build_prewriting_check(
    db: AsyncSession,
    book: Book,
    upcoming_chapter: int,
) -> dict:
    total_chapters = book.total_chapters or 0
    active_characters_rows = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book.id, Character.last_seen_chapter.isnot(None))
            .order_by(Character.last_seen_chapter.desc(), Character.mention_count.desc(), Character.name)
            .limit(8)
        )
    ).scalars().all()
    active_characters = [
        {
            "id": str(char.id),
            "name": char.name,
            "role": char.role,
            "last_seen_chapter": char.last_seen_chapter,
            "arc_summary": char.arc_summary,
        }
        for char in active_characters_rows
    ]

    unresolved_threads_rows = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book.id, PlotThread.status.in_(["introduced", "ongoing", "unknown"]))
            .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
            .limit(8)
        )
    ).scalars().all()
    unresolved_threads = [
        {
            "id": str(thread.id),
            "title": thread.title,
            "status": thread.status,
            "introduced_at": thread.introduced_at,
            "note": thread.note,
        }
        for thread in unresolved_threads_rows
    ]

    recent_summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id, ChapterSummary.mode == "short")
            .order_by(Chapter.number.desc())
            .limit(3)
        )
    ).all()
    recent_events: list[dict] = []
    for chapter_number, chapter_title, key_events in recent_summary_rows:
        for event in (key_events or [])[:2]:
            if isinstance(event, dict) and event.get("event"):
                recent_events.append({
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "detail": str(event.get("event")).strip(),
                })
    alerts: list[dict] = []
    dormant_rows = (
        await db.execute(
            select(Character.name, Character.last_seen_chapter, Character.mention_count)
            .where(
                Character.book_id == book.id,
                Character.last_seen_chapter.isnot(None),
                Character.mention_count >= 6,
            )
            .order_by(Character.mention_count.desc(), Character.last_seen_chapter)
            .limit(6)
        )
    ).all()
    for name, last_seen_chapter, mention_count in dormant_rows:
        if last_seen_chapter and total_chapters and total_chapters - last_seen_chapter >= 40:
            alerts.append({
                "kind": "dormant_character",
                "title": f"{name} has been absent for {total_chapters - last_seen_chapter} chapters",
                "body": f"Readers may notice if {name} mattered earlier but never returns. Decide whether to revive, reference, or close that thread.",
                "chapter_ref": last_seen_chapter,
            })
    recent_report = await build_chapter_consistency_report(db, book, total_chapters) if total_chapters else None
    for flag in (recent_report.continuity_flags if recent_report else [])[:2]:
        alerts.append({
            "kind": "continuity_risk",
            "title": "Readers might notice a continuity wobble",
            "body": flag,
            "chapter_ref": recent_report.chapter_number if recent_report else None,
        })
    return {
        "upcoming_chapter": upcoming_chapter,
        "active_characters": active_characters,
        "unresolved_threads": unresolved_threads,
        "recent_events": recent_events[:6],
        "alerts": alerts[:4],
    }
