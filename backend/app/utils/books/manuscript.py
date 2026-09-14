"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import mimetypes
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import bleach  # type: ignore[import-untyped]
from bleach.css_sanitizer import CSSSanitizer
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import download_book, upload_binary, upload_text
from app.models.book import (
    Book,
    BookCollaborator,
    Chapter,
    ChapterMedia,
)
from app.utils.books import (
    book_text,
    collaboration_access,
    normalization,
)
from app.utils.storage_utils import (
    STORAGE_IO_EXCEPTIONS,
    bounded_storage_map,
    delete_storage_keys_best_effort,
)

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
    "img",
    "mark",
    "hr",
    "a",
]
MANUSCRIPT_ALLOWED_ATTRIBUTES = {
    "p": ["style", "class", "data-text-align"],
    "div": ["style", "class", "data-text-align", "data-scene-break", "data-page-break"],
    "span": ["style", "class", "data-mention"],
    "h1": ["style", "class", "data-text-align"],
    "h2": ["style", "class", "data-text-align"],
    "h3": ["style", "class", "data-text-align"],
    "blockquote": ["style", "class", "data-text-align"],
    "ul": ["style", "class", "data-type"],
    "ol": ["style", "class"],
    "li": ["style", "class", "data-type", "data-checked"],
    "img": ["src", "alt", "title", "width", "height"],
    "a": ["href", "target", "rel"],
    "mark": ["style", "class"],
}
MANUSCRIPT_ALLOWED_STYLES = [
    "text-align",
    "color",
    "background-color",
    "font-family",
    "font-size",
    "line-height",
    "margin-bottom",
    "text-indent",
]
MANUSCRIPT_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel", "data"]


@dataclass(frozen=True)
class StagedEditorChapterContent:
    text: str
    html: str | None
    storage_key: str
    media: list[dict[str, Any]]
    retained_media_markers: set[str]
    should_sync_media: bool
    uploaded_keys: tuple[str, ...]


async def load_chapter_texts(chapters: list[Chapter]) -> dict[int, str]:
    """Load normalized manuscript text for chapters without failing the whole batch."""
    loaded: dict[int, str] = {}
    for chapter in chapters:
        if not chapter.s3_key:
            loaded[chapter.number] = ""
            continue
        try:
            raw = await asyncio.to_thread(download_book, chapter.s3_key)
        except STORAGE_IO_EXCEPTIONS:
            loaded[chapter.number] = ""
            continue
        payload = deserialize_manuscript_content(raw)
        loaded[chapter.number] = str(payload.get("text") or "").strip()
    return loaded


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
        lines = [book_text._clean_text(line) for line in paragraph.split("\n")]
        html_parts.append(
            f"<p>{'<br>'.join(line for line in lines if line or len(lines) == 1)}</p>"
        )
    return "".join(html_parts) or "<p></p>"


def clean_manuscript_html(html: str | None) -> str:
    cleaner = CSSSanitizer(allowed_css_properties=cast(Any, MANUSCRIPT_ALLOWED_STYLES))
    cleaned = str(
        bleach.clean(
            str(html or "").strip(),
            tags=cast(Any, MANUSCRIPT_ALLOWED_TAGS),
            attributes=cast(Any, MANUSCRIPT_ALLOWED_ATTRIBUTES),
            protocols=cast(Any, MANUSCRIPT_ALLOWED_PROTOCOLS),
            css_sanitizer=cast(Any, cleaner),
            strip=True,
        )
    )
    return book_text._normalize_unicode_replacements(cleaned)


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


def extract_inline_images_from_manuscript_html(
    html: str | None,
) -> tuple[str | None, list[dict[str, Any]], set[str]]:
    if not html or ("<img" not in html and "data:image/" not in html):
        return html, [], set()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(clean_manuscript_html(html), "html.parser")
    images: list[dict[str, Any]] = []
    retained_markers: set[str] = set()
    for image in soup.find_all("img"):
        src = str(image.get("src") or "")
        marker_ref = str(image.get("alt") or image.get("title") or "").strip()
        if marker_ref.startswith("[[IMAGE:") and marker_ref.endswith("]]"):
            retained_markers.add(marker_ref)
            marker_node = soup.new_tag("p")
            marker_node.string = marker_ref
            image.replace_with(marker_node)
            continue
        if not src.startswith("data:image/") or "," not in src:
            continue
        header, encoded = src.split(",", 1)
        content_type = header[5:].split(";", 1)[0].strip().lower()
        if content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            image.decompose()
            continue
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            image.decompose()
            continue
        if not raw:
            image.decompose()
            continue
        extension = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
            "image/gif": "gif",
        }.get(content_type, "bin")
        marker = f"[[IMAGE:{uuid.uuid4().hex}]]"
        images.append(
            {
                "marker": marker,
                "bytes": raw,
                "content_type": content_type,
                "filename": f"{uuid.uuid4().hex}.{extension}",
            }
        )
        marker_node = soup.new_tag("p")
        marker_node.string = marker
        image.replace_with(marker_node)
    if not images and not retained_markers:
        return html, [], set()
    return clean_manuscript_html(str(soup)), images, retained_markers


def chapter_media_storage_payload(media: ChapterMedia) -> dict[str, Any]:
    return {
        "marker": media.marker,
        "asset_type": media.asset_type or "image",
        "content_type": media.content_type,
        "caption": media.caption,
        "sort_order": media.sort_order,
        "storage_key": media.storage_key,
    }


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


def deserialize_manuscript_content(raw: str | bytes | memoryview | None) -> dict[str, str | None]:
    if raw is None:
        return {"format": "plain_text", "text": "", "html": None}
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    raw_text: str = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
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
        return {
            "format": "rich_text_v1",
            "text": text,
            "html": html or manuscript_text_to_html(text),
        }

    return {"format": "plain_text", "text": raw_text, "html": manuscript_text_to_html(raw_text)}


async def load_novel_export_chapters(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: BookCollaborator | None,
    include_images: bool,
) -> list[dict[str, Any]]:
    chapter_rows = (
        await db.execute(
            select(Chapter.id, Chapter.number, Chapter.title, Chapter.s3_key)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    if collaborator is not None:
        chapter_rows = [
            row
            for row in chapter_rows
            if collaboration_access.collaboration_allows_chapter(collaborator, int(row[1]))
        ]
    if not chapter_rows:
        raise HTTPException(404, "No chapters available to export")

    media_by_chapter_id: dict[uuid.UUID, list[dict[str, Any]]] = {}
    if include_images:
        chapter_ids = [row[0] for row in chapter_rows]
        media_rows = (
            (
                await db.execute(
                    select(ChapterMedia)
                    .where(ChapterMedia.chapter_id.in_(chapter_ids))
                    .order_by(ChapterMedia.sort_order.asc(), ChapterMedia.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        image_media = [
            media for media in media_rows if getattr(media, "asset_type", "image") == "image"
        ]

        async def load_media(media: ChapterMedia) -> tuple[ChapterMedia, bytes | None]:
            try:
                return media, await asyncio.to_thread(download_book, media.storage_key)
            except STORAGE_IO_EXCEPTIONS:
                return media, None

        for media, raw in await bounded_storage_map(image_media, load_media):
            if raw is None:
                continue
            media_by_chapter_id.setdefault(media.chapter_id, []).append(
                {
                    "raw": raw,
                    "content_type": media.content_type
                    or mimetypes.guess_type(media.storage_key)[0]
                    or "image/png",
                    "caption": media.caption,
                    "marker": media.marker,
                }
            )

    async def load_chapter(row: Any) -> dict[str, Any]:
        chapter_id, number, chapter_title, s3_key = row
        chapter_text = ""
        if s3_key:
            try:
                raw = await asyncio.to_thread(download_book, s3_key)
            except STORAGE_IO_EXCEPTIONS:
                chapter_text = ""
            else:
                stored = deserialize_manuscript_content(raw)
                chapter_text = str(stored.get("text") or "")
        return {
            "number": number,
            "title": chapter_title,
            "text": chapter_text,
            "media": media_by_chapter_id.get(chapter_id, []),
        }

    return await bounded_storage_map(chapter_rows, load_chapter)


async def load_novel_cover_image(book: Book) -> dict[str, Any] | None:
    if not book.cover_s3_key:
        return None
    try:
        raw = await asyncio.to_thread(download_book, book.cover_s3_key)
    except STORAGE_IO_EXCEPTIONS:
        return None
    return {
        "raw": raw,
        "content_type": mimetypes.guess_type(book.cover_s3_key)[0] or "image/png",
    }


async def sync_chapter_media_from_images(
    db: AsyncSession,
    *,
    book: Book,
    chapter: Chapter,
    images: list[dict[str, Any]],
    retain_markers: set[str] | None = None,
) -> None:
    retained = {str(marker) for marker in (retain_markers or set()) if str(marker).strip()}
    delete_statement = delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id)
    if retained:
        delete_statement = delete_statement.where(ChapterMedia.marker.not_in(retained))
    await db.execute(delete_statement)
    for index, image in enumerate(images):
        raw = image.get("bytes")
        marker = image.get("marker")
        storage_key = str(image.get("storage_key") or "")
        if not marker:
            continue
        if raw:
            filename = str(image.get("filename") or f"{uuid.uuid4().hex}.bin")
            storage_key = f"chapter-media/{book.id}/{chapter.number}/{index}-{filename}"
            await asyncio.to_thread(upload_binary, storage_key, raw, image.get("content_type"))
        elif not storage_key:
            continue
        db.add(
            ChapterMedia(
                book_id=book.id,
                chapter_id=chapter.id,
                marker=str(marker),
                asset_type=str(image.get("asset_type") or "image"),
                content_type=image.get("content_type"),
                storage_key=storage_key,
                caption=str(image.get("caption") or "").strip() or None,
                sort_order=index,
            )
        )


async def stage_editor_chapter_content(
    book: Book,
    *,
    chapter_number: int,
    text: str,
    html: str | None,
    images: list[dict[str, Any]] | None = None,
) -> StagedEditorChapterContent:
    """Upload immutable chapter content before opening the final write transaction."""
    extracted_images: list[dict[str, Any]] = []
    retained_image_markers: set[str] = set()
    if html and ("data:image/" in html or "<img" in html):
        html, extracted_images, retained_image_markers = extract_inline_images_from_manuscript_html(
            html
        )
        if extracted_images or retained_image_markers:
            text = manuscript_html_to_text(html) or text

    incoming_images = list(images or [])
    retained_existing_images = [
        dict(image)
        for image in incoming_images
        if image.get("storage_key") and str(image.get("marker") or "") in retained_image_markers
    ]
    fresh_images = [dict(image) for image in incoming_images if image.get("bytes")]
    media = [*retained_existing_images, *extracted_images, *fresh_images]
    should_sync_media = bool(media) or images is not None or bool(retained_image_markers)
    uploaded_keys: list[str] = []

    try:
        for image in media:
            raw = image.pop("bytes", None)
            if not raw:
                continue
            filename = str(image.get("filename") or f"{uuid.uuid4().hex}.bin")
            media_key = f"chapter-media/{book.id}/{chapter_number}/{uuid.uuid4().hex}-{filename}"
            image["storage_key"] = await asyncio.to_thread(
                upload_binary,
                media_key,
                raw,
                image.get("content_type"),
            )
            uploaded_keys.append(str(image["storage_key"]))

        content_key = f"chapters/{book.id}/{chapter_number}/{uuid.uuid4().hex}.txt"
        stored_key = await asyncio.to_thread(
            upload_text,
            content_key,
            serialize_manuscript_content(text, html),
        )
        uploaded_keys.append(stored_key)
    except STORAGE_IO_EXCEPTIONS:
        await delete_storage_keys_best_effort(
            uploaded_keys,
            context="chapter_save_staging",
        )
        raise

    return StagedEditorChapterContent(
        text=text,
        html=html,
        storage_key=stored_key,
        media=media,
        retained_media_markers=retained_image_markers,
        should_sync_media=should_sync_media,
        uploaded_keys=tuple(uploaded_keys),
    )


async def apply_staged_editor_chapter_content(
    db: AsyncSession,
    book: Book,
    *,
    chapter: Chapter | None,
    chapter_number: int,
    title: str | None,
    staged: StagedEditorChapterContent,
    description: str | None = None,
    chapter_kind: str | None = None,
    content_version: int = 1,
) -> Chapter:
    """Persist an already-uploaded chapter without performing remote storage I/O."""
    word_count = len(staged.text.split()) if staged.text.strip() else 0
    if chapter is None:
        chapter = Chapter(
            book_id=book.id,
            number=chapter_number,
            title=title,
            description=description,
            chapter_kind=normalization.normalize_chapter_kind(chapter_kind),
            s3_key=staged.storage_key,
            token_count=word_count,
            word_count=word_count,
            content_version=content_version,
            processed=False,
            analysis_state={},
        )
        db.add(chapter)
        await db.flush()
    else:
        previous_content_version = chapter.content_version
        chapter.title = title or chapter.title
        chapter.description = description or chapter.description
        chapter.chapter_kind = normalization.normalize_chapter_kind(chapter_kind)
        chapter.s3_key = staged.storage_key
        chapter.token_count = word_count
        chapter.word_count = word_count
        chapter.content_version = content_version
        chapter.processed = False
        chapter.analysis_state = {}
        if previous_content_version != content_version:
            from app.services.continuity.scan_service import mark_continuity_findings_stale

            await mark_continuity_findings_stale(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                content_version=content_version,
            )
        await db.flush()

    if staged.should_sync_media:
        await sync_chapter_media_from_images(
            db,
            book=book,
            chapter=chapter,
            images=staged.media,
            retain_markers=staged.retained_media_markers,
        )
    return chapter


async def persist_editor_chapter_content(
    db: AsyncSession,
    book: Book,
    *,
    chapter_number: int,
    title: str | None,
    text: str,
    html: str | None,
    description: str | None = None,
    chapter_kind: str | None = None,
    content_version: int = 1,
    images: list[dict[str, Any]] | None = None,
) -> Chapter:
    staged = await stage_editor_chapter_content(
        book,
        chapter_number=chapter_number,
        text=text,
        html=html,
        images=images,
    )
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    try:
        return await apply_staged_editor_chapter_content(
            db,
            book,
            chapter=chapter,
            chapter_number=chapter_number,
            title=title,
            staged=staged,
            description=description,
            chapter_kind=chapter_kind,
            content_version=content_version,
        )
    except Exception:
        await delete_storage_keys_best_effort(
            staged.uploaded_keys,
            context="chapter_persist_rollback",
        )
        raise
