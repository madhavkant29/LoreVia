"""
Book utility helpers ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    NoteLink,
    NoteSeriesLink,
    NoteTag,
    SeriesBook,
    VaultNote,
    VaultNoteSource,
)

if TYPE_CHECKING:
    pass

VAULT_NOTE_SOURCES = {
    VaultNoteSource.CHARACTER_BIBLE.value,
    VaultNoteSource.USER_NOTES.value,
}
WIKI_REFERENCE_RE = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")
WIKI_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9/_-]*)")


async def list_vault_bible_notes(db: AsyncSession, book: Book, user_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(VaultNote)
                .where(
                    VaultNote.book_id == book.id,
                    VaultNote.user_id == user_id,
                    VaultNote.source == VaultNoteSource.CHARACTER_BIBLE.value,
                )
                .order_by(VaultNote.path.asc())
            )
        )
        .scalars()
        .all()
    )
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


async def load_vault_note_overrides(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    *,
    source: str = VaultNoteSource.CHARACTER_BIBLE.value,
) -> dict[str, str]:
    normalized_source = normalize_vault_note_source(source)
    rows = (
        await db.execute(
            select(VaultNote.path, VaultNote.content).where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.source == normalized_source,
            )
        )
    ).all()
    return {path: content for path, content in rows}


def normalize_vault_note_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized not in VAULT_NOTE_SOURCES:
        raise HTTPException(400, "Invalid vault note source")
    return normalized


def normalize_vault_note_path(path: str) -> str:
    normalized_path = (path or "").replace("\\", "/").strip().strip("/")
    if not normalized_path:
        raise HTTPException(400, "Path is required")
    segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
    if not segments or any(segment in {".", ".."} for segment in segments):
        raise HTTPException(400, "Invalid path")
    return "/".join(segments)


def vault_note_title(path: str) -> str:
    filename = path.replace("\\", "/").split("/")[-1]
    return os.path.splitext(filename)[0].strip() or filename.strip()


def vault_note_folder(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/" not in normalized:
        return "Root"
    return normalized.rsplit("/", 1)[0] or "Root"


def extract_wiki_links(markdown: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for reference in extract_wiki_references(markdown):
        target = reference["target"]
        alias = reference["alias"]
        if not target:
            continue
        links.append({"target": target, "alias": alias or target})
    return links


def extract_wiki_references(markdown: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for embed_prefix, raw_value in WIKI_REFERENCE_RE.findall(markdown or ""):
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


def extract_wiki_tags(markdown: str) -> list[str]:
    tags: list[str] = []
    for match in WIKI_TAG_RE.findall(markdown or ""):
        cleaned = normalize_wiki_tag(match)
        if cleaned:
            tags.append(cleaned)
    return list(dict.fromkeys(tags))


def normalize_wiki_tag(tag: str) -> str:
    cleaned = " ".join((tag or "").replace("_", "-").split()).strip()
    cleaned = cleaned.strip("#")
    return cleaned.lower()


def build_vault_graph(notes: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    notes_by_path = {note["path"]: note for note in notes}
    title_to_path: dict[str, str] = {}
    for path in sorted(notes_by_path):
        title_to_path.setdefault(vault_note_title(path).lower(), path)

    nodes: list[dict[str, str | int]] = []
    link_counts = {path: 0 for path in notes_by_path}
    edges: list[dict[str, str | None]] = []
    edge_keys: set[tuple[str, str, str | None]] = set()

    for path, note in notes_by_path.items():
        for link in extract_wiki_links(str(note.get("content") or "")):
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
                "title": vault_note_title(path),
                "folder": vault_note_folder(path),
                "link_count": link_counts[path],
            }
        )

    return {"nodes": nodes, "edges": edges}


async def _load_vault_scope_notes(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str,
) -> tuple[list[VaultNote], dict[uuid.UUID, Book]]:
    normalized_source = normalize_vault_note_source(source)
    scoped_books = {book.id: book}
    if book.primary_series_id:
        series_book_rows = (
            (
                await db.execute(
                    select(Book)
                    .join(SeriesBook, SeriesBook.book_id == Book.id)
                    .where(SeriesBook.series_id == book.primary_series_id, Book.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        for row in series_book_rows:
            scoped_books[row.id] = row

    notes = (
        (
            await db.execute(
                select(VaultNote)
                .where(
                    VaultNote.user_id == user_id,
                    VaultNote.source == normalized_source,
                    VaultNote.book_id.in_(list(scoped_books)),
                )
                .order_by(VaultNote.book_id.asc(), VaultNote.path.asc())
            )
        )
        .scalars()
        .all()
    )
    notes = list(notes)
    return notes, scoped_books


def _normalize_vault_note_path_key(path: str) -> str:
    return normalize_vault_note_path(path).lower()


def _resolve_vault_reference(
    reference: str, *, notes_by_path: dict[str, VaultNote], notes_by_title: dict[str, VaultNote]
) -> VaultNote | None:
    normalized_path = reference.replace("\\", "/").strip().lower()
    if normalized_path.endswith(".md"):
        normalized_path = normalized_path[:-3]

    for path_key, note in notes_by_path.items():
        candidate_path = path_key.lower()
        if candidate_path.endswith(".md"):
            candidate_path = candidate_path[:-3]
        if candidate_path == normalized_path:
            return note

    title_key = vault_note_title(reference).lower()
    return notes_by_title.get(title_key)


async def _get_vault_note_by_path(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> VaultNote:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path).lower()
    note = (
        (
            await db.execute(
                select(VaultNote).where(
                    VaultNote.book_id == book.id,
                    VaultNote.user_id == user_id,
                    VaultNote.source == normalized_source,
                    func.lower(VaultNote.path) == normalized_path,
                )
            )
        )
        .scalars()
        .first()
    )
    if note is None:
        raise HTTPException(404, "Note not found")
    return note


def _serialize_vault_note_link(
    link: NoteLink, source_path: str, target_path: str
) -> dict[str, Any]:
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


def _serialize_vault_note_tag(tag: NoteTag, note_path: str) -> dict[str, Any]:
    return {
        "id": str(tag.id),
        "book_id": str(tag.book_id),
        "note_id": str(tag.note_id),
        "note_path": note_path,
        "tag_name": tag.tag_name,
        "created_at": tag.created_at,
    }


def _serialize_vault_note_series_link(
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
