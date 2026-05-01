"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import uuid
import zipfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import bleach  # type: ignore[import-untyped]
from bleach.css_sanitizer import CSSSanitizer
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.security import create_asset_token
from app.core.storage import download_book, get_presigned_url, upload_binary
from app.models.book import (
    Book,
    BookNote,
    Chapter,
    ChapterVersion,
    NoteBacklink,
    NoteLink,
    NoteSeriesLink,
    NoteTag,
    ObsidianVaultNote,
    ObsidianVaultNoteSource,
    Series,
    SeriesBook,
)
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
    "img",
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
    "img": ["src", "alt", "title", "width", "height"],
}
MANUSCRIPT_ALLOWED_STYLES = ["text-align"]
MANUSCRIPT_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel", "data"]
OBSIDIAN_WIKI_LINK_RE = re.compile(r"\[\[([^\[\]\n]+)\]\]")
OBSIDIAN_NOTE_REFERENCE_RE = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")
OBSIDIAN_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9/_-]*)")
OBSIDIAN_NOTE_SOURCES = {
    ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
    ObsidianVaultNoteSource.USER_NOTES.value,
}

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


DEFAULT_WRITING_TEMPLATES = [
    {
        "id": "chapter-three-act",
        "kind": "chapter",
        "title": "Chapter Three-Beat",
        "description": "Open with pressure, pivot in the middle, end on a story-moving turn.",
        "content": (
            "Opening beat\n"
            "- What changes immediately in this chapter?\n\n"
            "Middle escalation\n"
            "- What complication or reversal raises the cost?\n\n"
            "Closing turn\n"
            "- What question, threat, or choice launches the next chapter?"
        ),
    },
    {
        "id": "scene-goal-conflict-disaster",
        "kind": "scene",
        "title": "Scene Goal / Conflict / Disaster",
        "description": "Classic scene structure for momentum and tension.",
        "content": (
            "Goal\n"
            "- What does the point-of-view character want right now?\n\n"
            "Conflict\n"
            "- Who or what blocks them?\n\n"
            "Disaster / turn\n"
            "- What goes wrong, changes, or costs more than expected?"
        ),
    },
    {
        "id": "story-five-pivots",
        "kind": "story",
        "title": "Story Five Pivots",
        "description": "A compact scaffold for act structure and turning points.",
        "content": (
            "Setup promise\n"
            "- What emotional and plot promise does the story make?\n\n"
            "Inciting shift\n"
            "- What forces the protagonist out of stasis?\n\n"
            "Midpoint change\n"
            "- What truth, reveal, or victory changes the meaning of the conflict?\n\n"
            "Dark turn\n"
            "- What loss or collapse strips away the easy path?\n\n"
            "Climax and aftermath\n"
            "- What final choice resolves the central pressure?"
        ),
    },
]

DEFAULT_WRITER_WORKSPACE = {
    "word_count_goals": {
        "chapter_target": 2500,
        "book_target": 80000,
        "session_target": 1000,
    },
    "corkboard_cards": [],
    "templates": DEFAULT_WRITING_TEMPLATES,
    "publishing": {
        "active_preset": "standard_manuscript",
        "trim_size": "6x9",
        "include_title_page": True,
        "mirror_margins": True,
    },
}


def normalize_writer_workspace(raw: dict | None) -> dict:
    payload = json.loads(json.dumps(DEFAULT_WRITER_WORKSPACE))
    source = raw if isinstance(raw, dict) else {}

    goals = source.get("word_count_goals")
    if isinstance(goals, dict):
        for key in ("chapter_target", "book_target", "session_target"):
            value = goals.get(key)
            payload["word_count_goals"][key] = int(value) if isinstance(value, (int, float)) and int(value) > 0 else None

    cards: list[dict[str, Any]] = []
    for card in source.get("corkboard_cards") or []:
        if not isinstance(card, dict):
            continue
        title = " ".join(str(card.get("title") or "").split()).strip()
        if not title:
            continue
        chapter_number = card.get("chapter_number")
        cards.append(
            {
                "id": str(card.get("id") or uuid.uuid4()),
                "title": title,
                "description": str(card.get("description") or "").strip(),
                "status": " ".join(str(card.get("status") or "planned").split()).strip() or "planned",
                "lane": " ".join(str(card.get("lane") or "ideas").split()).strip() or "ideas",
                "chapter_number": int(chapter_number) if isinstance(chapter_number, (int, float)) and int(chapter_number) > 0 else None,
                "template_id": " ".join(str(card.get("template_id") or "").split()).strip() or None,
            }
        )
    payload["corkboard_cards"] = cards

    templates: list[dict[str, str]] = []
    for template in source.get("templates") or DEFAULT_WRITING_TEMPLATES:
        if not isinstance(template, dict):
            continue
        template_id = " ".join(str(template.get("id") or "").split()).strip()
        kind = " ".join(str(template.get("kind") or "").split()).strip()
        title = " ".join(str(template.get("title") or "").split()).strip()
        content = str(template.get("content") or "").strip()
        if not template_id or not kind or not title or not content:
            continue
        templates.append(
            {
                "id": template_id,
                "kind": kind,
                "title": title,
                "description": " ".join(str(template.get("description") or "").split()).strip(),
                "content": content,
            }
        )
    payload["templates"] = templates or json.loads(json.dumps(DEFAULT_WRITING_TEMPLATES))

    publishing = source.get("publishing")
    if isinstance(publishing, dict):
        payload["publishing"] = {
            "active_preset": " ".join(str(publishing.get("active_preset") or "standard_manuscript").split()).strip() or "standard_manuscript",
            "trim_size": " ".join(str(publishing.get("trim_size") or "6x9").split()).strip() or "6x9",
            "include_title_page": bool(publishing.get("include_title_page", True)),
            "mirror_margins": bool(publishing.get("mirror_margins", True)),
        }

    return payload


def build_writer_workspace_payload(book: Book) -> dict:
    return normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)


def estimate_readability(text: str) -> dict[str, Any]:
    cleaned = " ".join((text or "").replace("\r", "\n").split())
    paragraphs = len([part for part in re.split(r"\n{2,}", text or "") if part.strip()]) or (1 if cleaned else 0)
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    sentences = [part for part in re.split(r"[.!?]+", text or "") if part.strip()]
    word_count = len(words)
    sentence_count = len(sentences) or (1 if word_count else 0)
    syllables = sum(_estimate_syllables(word) for word in words)
    average_sentence_length = round(word_count / sentence_count, 2) if sentence_count else 0.0
    reading_ease = 206.835 - (1.015 * average_sentence_length) - (84.6 * ((syllables / word_count) if word_count else 0))
    grade_level = 0.39 * average_sentence_length + 11.8 * ((syllables / word_count) if word_count else 0) - 15.59

    if reading_ease >= 80:
        label = "Very easy"
    elif reading_ease >= 65:
        label = "Easy"
    elif reading_ease >= 50:
        label = "Balanced"
    elif reading_ease >= 35:
        label = "Demanding"
    else:
        label = "Dense"

    return {
        "words": word_count,
        "sentences": sentence_count,
        "paragraphs": paragraphs,
        "average_sentence_length": round(average_sentence_length, 2),
        "reading_ease": round(reading_ease, 2),
        "grade_level": round(max(0.0, grade_level), 2),
        "label": label,
    }


def _estimate_syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 1
    groups = re.findall(r"[aeiouy]+", cleaned)
    syllables = len(groups)
    if cleaned.endswith("e") and syllables > 1:
        syllables -= 1
    return max(1, syllables)


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
            .where(
                ObsidianVaultNote.book_id == book.id,
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.source == ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
            )
            .order_by(ObsidianVaultNote.path.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "path": note.path,
            "source": note.source,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note in rows
    ]


async def load_obsidian_vault_overrides(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    *,
    source: str = ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
) -> dict[str, str]:
    normalized_source = normalize_obsidian_note_source(source)
    rows = (
        await db.execute(
            select(ObsidianVaultNote.path, ObsidianVaultNote.content)
            .where(
                ObsidianVaultNote.book_id == book.id,
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.source == normalized_source,
            )
        )
    ).all()
    return {path: content for path, content in rows}


def normalize_obsidian_note_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized not in OBSIDIAN_NOTE_SOURCES:
        raise HTTPException(400, "Invalid Obsidian note source")
    return normalized


def normalize_obsidian_note_path(path: str) -> str:
    normalized_path = (path or "").replace("\\", "/").strip().strip("/")
    if not normalized_path:
        raise HTTPException(400, "Path is required")
    segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
    if not segments or any(segment in {".", ".."} for segment in segments):
        raise HTTPException(400, "Invalid path")
    return "/".join(segments)


def obsidian_note_title(path: str) -> str:
    filename = path.replace("\\", "/").split("/")[-1]
    return os.path.splitext(filename)[0].strip() or filename.strip()


def obsidian_note_folder(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/" not in normalized:
        return "Root"
    return normalized.rsplit("/", 1)[0] or "Root"


def extract_obsidian_wiki_links(markdown: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for reference in extract_obsidian_note_references(markdown):
        target = reference["target"]
        alias = reference["alias"]
        if not target:
            continue
        links.append({"target": target, "alias": alias or target})
    return links


def extract_obsidian_note_references(markdown: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for embed_prefix, raw_value in OBSIDIAN_NOTE_REFERENCE_RE.findall(markdown or ""):
        raw_target, _, raw_alias = raw_value.partition("|")
        target = raw_target.split("#", 1)[0].strip()
        alias = raw_alias.strip() or target
        if not target:
            continue
        references.append(
            {
                "target": target,
                "alias": alias,
                "link_type": "embed" if embed_prefix == "!" else "reference",
            }
        )
    return references


def extract_obsidian_tags(markdown: str) -> list[str]:
    tags: list[str] = []
    for match in OBSIDIAN_TAG_RE.findall(markdown or ""):
        cleaned = normalize_obsidian_tag(match)
        if cleaned:
            tags.append(cleaned)
    return list(dict.fromkeys(tags))


def normalize_obsidian_tag(tag: str) -> str:
    cleaned = " ".join((tag or "").replace("_", "-").split()).strip()
    cleaned = cleaned.strip("#")
    return cleaned.lower()


def build_obsidian_graph(notes: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    notes_by_path = {note["path"]: note for note in notes}
    title_to_path: dict[str, str] = {}
    for path in sorted(notes_by_path):
        title_to_path.setdefault(obsidian_note_title(path).lower(), path)

    nodes: list[dict[str, str | int]] = []
    link_counts = {path: 0 for path in notes_by_path}
    edges: list[dict[str, str | None]] = []
    edge_keys: set[tuple[str, str, str | None]] = set()

    for path, note in notes_by_path.items():
        for link in extract_obsidian_wiki_links(str(note.get("content") or "")):
            target_path = title_to_path.get(link["target"].lower())
            if not target_path:
                continue
            link_counts[path] += 1
            edge_key = (path, target_path, link["alias"])
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append({"source": path, "target": target_path, "label": link["alias"]})

    for path in sorted(notes_by_path):
        nodes.append(
            {
                "id": path,
                "path": path,
                "title": obsidian_note_title(path),
                "folder": obsidian_note_folder(path),
                "link_count": link_counts[path],
            }
        )

    return {"nodes": nodes, "edges": edges}


async def _load_obsidian_scope_notes(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str,
) -> tuple[list[ObsidianVaultNote], dict[str, Book]]:
    normalized_source = normalize_obsidian_note_source(source)
    scoped_books = {book.id: book}
    if book.primary_series_id:
        series_book_rows = (
            await db.execute(
                select(Book)
                .join(SeriesBook, SeriesBook.book_id == Book.id)
                .where(SeriesBook.series_id == book.primary_series_id, Book.user_id == user_id)
            )
        ).scalars().all()
        for row in series_book_rows:
            scoped_books[row.id] = row

    notes = (
        await db.execute(
            select(ObsidianVaultNote)
            .where(
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.source == normalized_source,
                ObsidianVaultNote.book_id.in_(list(scoped_books)),
            )
            .order_by(ObsidianVaultNote.book_id.asc(), ObsidianVaultNote.path.asc())
        )
    ).scalars().all()
    return notes, scoped_books


def _normalize_obsidian_note_path_key(path: str) -> str:
    return normalize_obsidian_note_path(path).lower()


def _resolve_obsidian_reference(reference: str, *, notes_by_path: dict[str, ObsidianVaultNote], notes_by_title: dict[str, ObsidianVaultNote]) -> ObsidianVaultNote | None:
    normalized_path = reference.replace("\\", "/").strip().lower()
    if normalized_path.endswith(".md"):
        normalized_path = normalized_path[:-3]

    for path_key, note in notes_by_path.items():
        candidate_path = path_key.lower()
        if candidate_path.endswith(".md"):
            candidate_path = candidate_path[:-3]
        if candidate_path == normalized_path:
            return note

    title_key = obsidian_note_title(reference).lower()
    return notes_by_title.get(title_key)


async def _get_obsidian_note_by_path(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = ObsidianVaultNoteSource.USER_NOTES.value,
) -> ObsidianVaultNote:
    normalized_source = normalize_obsidian_note_source(source)
    normalized_path = normalize_obsidian_note_path(path).lower()
    note = (
        await db.execute(
            select(ObsidianVaultNote).where(
                ObsidianVaultNote.book_id == book.id,
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.source == normalized_source,
                func.lower(ObsidianVaultNote.path) == normalized_path,
            )
        )
    ).scalars().first()
    if note is None:
        raise HTTPException(404, "Note not found")
    return note


def _serialize_obsidian_note_link(link: NoteLink, source_path: str, target_path: str) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "book_id": str(link.book_id),
        "source_note_id": str(link.source_note_id),
        "source_note_path": source_path,
        "target_note_id": str(link.target_note_id),
        "target_note_path": target_path,
        "link_type": link.link_type,
        "target_label": getattr(link, "target_label", None),
        "created_at": link.created_at,
    }


def _serialize_obsidian_note_tag(tag: NoteTag, note_path: str) -> dict[str, Any]:
    return {
        "id": str(tag.id),
        "book_id": str(tag.book_id),
        "note_id": str(tag.note_id),
        "note_path": note_path,
        "tag_name": tag.tag_name,
        "created_at": tag.created_at,
    }


def _serialize_obsidian_note_series_link(
    link: NoteSeriesLink,
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "series_id": str(link.series_id),
        "source_book_id": str(link.source_book_id),
        "target_book_id": str(link.target_book_id),
        "source_note_id": str(link.source_note_id),
        "source_note_path": source_path,
        "target_note_id": str(link.target_note_id),
        "target_note_path": target_path,
        "link_type": link.link_type,
        "created_at": link.created_at,
    }


async def sync_obsidian_note_relations(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = ObsidianVaultNoteSource.USER_NOTES.value,
) -> dict[str, int]:
    normalized_source = normalize_obsidian_note_source(source)
    if normalized_source != ObsidianVaultNoteSource.USER_NOTES.value:
        return {"links": 0, "backlinks": 0, "tags": 0, "series_links": 0}

    notes, scoped_books = await _load_obsidian_scope_notes(db, book=book, user_id=user_id, source=normalized_source)
    scoped_book_ids = list(scoped_books)

    for table in (NoteLink, NoteBacklink, NoteTag):
        await db.execute(
            delete(table).where(
                table.user_id == user_id,
                table.book_id.in_(scoped_book_ids),
            )
        )
    await db.execute(
        delete(NoteSeriesLink).where(
            NoteSeriesLink.user_id == user_id,
            NoteSeriesLink.source_book_id.in_(scoped_book_ids),
        )
    )
    await db.flush()

    notes_by_path = {note.path.lower(): note for note in notes}
    notes_by_title: dict[str, ObsidianVaultNote] = {}
    for note in notes:
        notes_by_title.setdefault(obsidian_note_title(note.path).lower(), note)

    links_created = 0
    backlinks_created = 0
    tags_created = 0
    series_links_created = 0

    for note in notes:
        references = extract_obsidian_note_references(note.content)
        note_tags = extract_obsidian_tags(note.content)

        for tag_name in note_tags:
            db.add(
                NoteTag(
                    user_id=user_id,
                    book_id=note.book_id,
                    note_id=note.id,
                    tag_name=tag_name,
                )
            )
            tags_created += 1

        for reference in references:
            target_note = _resolve_obsidian_reference(reference["target"], notes_by_path=notes_by_path, notes_by_title=notes_by_title)
            if target_note is None or target_note.id == note.id:
                continue

            db.add(
                NoteLink(
                    user_id=user_id,
                    book_id=note.book_id,
                    source_note_id=note.id,
                    target_note_id=target_note.id,
                    link_type=reference["link_type"],
                    target_label=reference["alias"],
                )
            )
            db.add(
                NoteBacklink(
                    user_id=user_id,
                    book_id=target_note.book_id,
                    source_note_id=note.id,
                    target_note_id=target_note.id,
                    link_type=reference["link_type"],
                )
            )
            links_created += 1
            backlinks_created += 1

            if note.book_id != target_note.book_id and book.primary_series_id and target_note.book_id in scoped_books:
                db.add(
                    NoteSeriesLink(
                        user_id=user_id,
                        series_id=book.primary_series_id,
                        source_book_id=note.book_id,
                        target_book_id=target_note.book_id,
                        source_note_id=note.id,
                        target_note_id=target_note.id,
                        link_type=reference["link_type"],
                    )
                )
                series_links_created += 1

    await db.flush()
    await db.commit()
    return {
        "links": links_created,
        "backlinks": backlinks_created,
        "tags": tags_created,
        "series_links": series_links_created,
    }


async def list_obsidian_note_links(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_obsidian_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(ObsidianVaultNote)
    target_note = aliased(ObsidianVaultNote)
    rows = (
        await db.execute(
            select(NoteLink, source_note.path, target_note.path)
            .join(source_note, NoteLink.source_note_id == source_note.id)
            .join(target_note, NoteLink.target_note_id == target_note.id)
            .where(
                NoteLink.user_id == user_id,
                NoteLink.book_id == book.id,
                NoteLink.source_note_id == note.id,
            )
            .order_by(NoteLink.created_at.asc())
        )
    ).all()
    return [_serialize_obsidian_note_link(link, source_path, target_path) for link, source_path, target_path in rows]


async def list_obsidian_note_backlinks(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_obsidian_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(ObsidianVaultNote)
    target_note = aliased(ObsidianVaultNote)
    rows = (
        await db.execute(
            select(NoteBacklink, source_note.path, target_note.path)
            .join(source_note, NoteBacklink.source_note_id == source_note.id)
            .join(target_note, NoteBacklink.target_note_id == target_note.id)
            .where(
                NoteBacklink.user_id == user_id,
                NoteBacklink.book_id == book.id,
                NoteBacklink.target_note_id == note.id,
            )
            .order_by(NoteBacklink.created_at.asc())
        )
    ).all()
    return [_serialize_obsidian_note_link(link, source_path, target_path) for link, source_path, target_path in rows]


async def list_obsidian_note_tags(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_obsidian_note_by_path(db, book=book, user_id=user_id, path=path)
    rows = (
        await db.execute(
            select(NoteTag, ObsidianVaultNote.path)
            .join(ObsidianVaultNote, NoteTag.note_id == ObsidianVaultNote.id)
            .where(
                NoteTag.user_id == user_id,
                NoteTag.book_id == book.id,
                NoteTag.note_id == note.id,
            )
            .order_by(NoteTag.tag_name.asc())
        )
    ).all()
    return [_serialize_obsidian_note_tag(tag, note_path) for tag, note_path in rows]


async def list_obsidian_note_series_links(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_obsidian_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(ObsidianVaultNote)
    target_note = aliased(ObsidianVaultNote)
    rows = (
        await db.execute(
            select(NoteSeriesLink, source_note.path, target_note.path)
            .join(source_note, NoteSeriesLink.source_note_id == source_note.id)
            .join(target_note, NoteSeriesLink.target_note_id == target_note.id)
            .where(
                NoteSeriesLink.user_id == user_id,
                NoteSeriesLink.source_book_id == book.id,
                NoteSeriesLink.source_note_id == note.id,
            )
            .order_by(NoteSeriesLink.created_at.asc())
        )
    ).all()
    return [_serialize_obsidian_note_series_link(link, source_path, target_path) for link, source_path, target_path in rows]


async def list_obsidian_note_relations(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "links": await list_obsidian_note_links(db, book=book, user_id=user_id, path=path),
        "backlinks": await list_obsidian_note_backlinks(db, book=book, user_id=user_id, path=path),
        "tags": await list_obsidian_note_tags(db, book=book, user_id=user_id, path=path),
        "series_links": await list_obsidian_note_series_links(db, book=book, user_id=user_id, path=path),
    }


async def list_obsidian_notes(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = ObsidianVaultNoteSource.USER_NOTES.value,
) -> list[dict]:
    normalized_source = normalize_obsidian_note_source(source)
    rows = (
        await db.execute(
            select(ObsidianVaultNote)
            .where(
                ObsidianVaultNote.book_id == book.id,
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.source == normalized_source,
            )
            .order_by(ObsidianVaultNote.path.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "path": note.path,
            "source": note.source,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note in rows
    ]


async def save_obsidian_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    content: str,
    source: str = ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
    sync_relations: bool = True,
) -> dict:
    normalized_source = normalize_obsidian_note_source(source)
    normalized_path = normalize_obsidian_note_path(path)
    normalized_content = content.replace("\r\n", "\n")

    note: ObsidianVaultNote | None = (
        await db.execute(
            select(ObsidianVaultNote).where(
                ObsidianVaultNote.book_id == book.id,
                ObsidianVaultNote.user_id == user_id,
                ObsidianVaultNote.path == normalized_path,
                ObsidianVaultNote.source == normalized_source,
            )
        )
    ).scalars().first()

    if note is None:
        note = ObsidianVaultNote(
            user_id=user_id,
            book_id=book.id,
            path=normalized_path,
            source=normalized_source,
            content=normalized_content,
        )
        db.add(note)
    else:
        note_any = cast(Any, note)
        note_any.path = normalized_path
        note_any.source = normalized_source
        note_any.content = normalized_content

    await db.commit()
    await db.refresh(note)
    if sync_relations and normalized_source == ObsidianVaultNoteSource.USER_NOTES.value:
        await sync_obsidian_note_relations(db, book=book, user_id=user_id, source=normalized_source)
    return {
        "path": note.path,
        "source": note.source,
        "content": note.content,
        "persisted": True,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def delete_obsidian_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = ObsidianVaultNoteSource.USER_NOTES.value,
) -> None:
    normalized_source = normalize_obsidian_note_source(source)
    normalized_path = normalize_obsidian_note_path(path)
    deleted = await db.execute(
        delete(ObsidianVaultNote).where(
            ObsidianVaultNote.book_id == book.id,
            ObsidianVaultNote.user_id == user_id,
            ObsidianVaultNote.path == normalized_path,
            ObsidianVaultNote.source == normalized_source,
        )
    )
    if not deleted.rowcount:
        raise HTTPException(404, "Note not found")
    await db.commit()
    if normalized_source == ObsidianVaultNoteSource.USER_NOTES.value:
        await sync_obsidian_note_relations(db, book=book, user_id=user_id, source=normalized_source)


async def import_obsidian_notes_zip(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    archive_bytes: bytes,
    source: str = ObsidianVaultNoteSource.USER_NOTES.value,
) -> list[dict]:
    normalized_source = normalize_obsidian_note_source(source)
    if not archive_bytes:
        raise HTTPException(400, "ZIP file is empty")

    imported: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            for member in members:
                if member.filename.startswith("__MACOSX/"):
                    continue
                if not member.filename.lower().endswith(".md"):
                    continue
                normalized_path = normalize_obsidian_note_path(member.filename)
                content = archive.read(member).decode("utf-8")
                imported.append(
                    await save_obsidian_vault_note(
                        db,
                        book=book,
                        user_id=user_id,
                        path=normalized_path,
                        content=content,
                        source=normalized_source,
                        sync_relations=False,
                    )
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Invalid ZIP file") from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "ZIP contains a non-UTF-8 markdown file") from exc

    if not imported:
        raise HTTPException(400, "ZIP did not contain any markdown notes")
    if normalized_source == ObsidianVaultNoteSource.USER_NOTES.value:
        await sync_obsidian_note_relations(db, book=book, user_id=user_id, source=normalized_source)
    return imported


def export_obsidian_notes_zip(*, notes: list[dict[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for note in sorted(notes, key=lambda item: item["path"]):
            archive.writestr(note["path"], str(note["content"] or "").replace("\r\n", "\n"))
    return buffer.getvalue()


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
    normalized_title = _clean_optional_text(" ".join((title or "").split()).strip())
    normalized_body = _clean_text(body)
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

    note_any = cast(Any, note)
    note_any.chapter_number = chapter_number
    note_any.title = normalized_title
    note_any.body = normalized_body
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
        preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
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
        lines = [_clean_text(line) for line in paragraph.split("\n")]
        html_parts.append(f"<p>{'<br>'.join(line for line in lines if line or len(lines) == 1)}</p>")
    return "".join(html_parts) or "<p></p>"


def clean_manuscript_html(html: str | None) -> str:
    cleaner = CSSSanitizer(allowed_css_properties=cast(Any, MANUSCRIPT_ALLOWED_STYLES))
    return str(bleach.clean(
        str(html or "").strip(),
        tags=cast(Any, MANUSCRIPT_ALLOWED_TAGS),
        attributes=cast(Any, MANUSCRIPT_ALLOWED_ATTRIBUTES),
        protocols=cast(Any, MANUSCRIPT_ALLOWED_PROTOCOLS),
        css_sanitizer=cast(Any, cleaner),
        strip=True,
    ))


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
        title = _clean_optional_text(" ".join(str(chapter.get("title") or "").split()).strip())
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


def build_emotional_arc_payload(characters: list[Character]) -> dict[str, Any]:
    tracked: list[dict[str, Any]] = []
    latest_turning_points: list[str] = []
    direction_map = {
        "positive": 1.0,
        "up": 1.0,
        "growth": 0.8,
        "negative": -1.0,
        "down": -1.0,
        "collapse": -0.9,
        "setback": -0.7,
        "neutral": 0.0,
    }

    def direction_score(direction: str) -> float:
        normalized = " ".join((direction or "").split()).strip().lower()
        for key, score in direction_map.items():
            if key in normalized:
                return score
        return 0.0

    ordered_characters = sorted(
        characters,
        key=lambda item: (item.role not in {"mc", "sc"}, -(item.mention_count or 0), item.name.lower()),
    )
    for character in ordered_characters:
        raw_events = [item for item in (character.growth_events or []) if isinstance(item, dict)]
        if not raw_events:
            continue
        raw_events.sort(key=lambda item: int(item.get("chapter_number") or item.get("chapter") or 0))
        points: list[dict[str, Any]] = []
        trajectory_score = 0.0
        for event in raw_events:
            chapter_number = int(event.get("chapter_number") or event.get("chapter") or character.first_chapter or 0)
            if chapter_number <= 0:
                continue
            label = " ".join(str(event.get("event_title") or event.get("event") or "").split()).strip() or f"Chapter {chapter_number} shift"
            impact_score = int(event.get("impact_score") or event.get("importance") or 5)
            growth_direction = " ".join(str(event.get("growth_direction") or "neutral").split()).strip() or "neutral"
            sentiment = round(direction_score(growth_direction) * max(1, impact_score) / 10, 2)
            trajectory_score += sentiment
            points.append(
                {
                    "chapter_number": chapter_number,
                    "label": label,
                    "sentiment": sentiment,
                    "impact_score": impact_score,
                    "growth_direction": growth_direction,
                }
            )
        if not points:
            continue
        latest = points[-1]
        latest_turning_points.append(f"{character.name}: {latest['label']} (chapter {latest['chapter_number']})")
        tracked.append(
            {
                "character_id": str(character.id),
                "character_name": character.name,
                "role": character.role,
                "arc_summary": character.arc_summary,
                "trajectory_score": round(trajectory_score, 2),
                "points": points,
            }
        )

    tracked.sort(key=lambda item: (item["role"] not in {"mc", "sc"}, -abs(item["trajectory_score"]), item["character_name"].lower()))
    return {
        "focus_character_count": len(tracked),
        "latest_turning_points": latest_turning_points[:8],
        "characters": tracked[:10],
    }


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
