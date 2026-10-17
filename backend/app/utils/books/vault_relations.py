"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.book import (
    Book,
    NoteBacklink,
    NoteLink,
    NoteSeriesLink,
    NoteTag,
    VaultNote,
    VaultNoteSource,
)
from app.utils.books.vault import (
    _get_vault_note_by_path,
    _load_vault_scope_notes,
    _resolve_vault_reference,
    _serialize_vault_note_link,
    _serialize_vault_note_series_link,
    _serialize_vault_note_tag,
    extract_wiki_references,
    extract_wiki_tags,
    normalize_vault_note_source,
    vault_note_title,
)

if TYPE_CHECKING:
    pass


async def sync_vault_note_relations(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = VaultNoteSource.USER_NOTES.value,
    commit: bool = True,
) -> dict[str, int]:
    normalized_source = normalize_vault_note_source(source)
    if normalized_source != VaultNoteSource.USER_NOTES.value:
        return {"links": 0, "backlinks": 0, "tags": 0, "series_links": 0}

    notes, scoped_books = await _load_vault_scope_notes(
        db, book=book, user_id=user_id, source=normalized_source
    )
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
    notes_by_title: dict[str, VaultNote] = {}
    for note in notes:
        notes_by_title.setdefault(vault_note_title(note.path).lower(), note)

    links_created = 0
    backlinks_created = 0
    tags_created = 0
    series_links_created = 0

    for note in notes:
        references = extract_wiki_references(note.content)
        note_tags = extract_wiki_tags(note.content)

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
            target_note = _resolve_vault_reference(
                reference["target"], notes_by_path=notes_by_path, notes_by_title=notes_by_title
            )
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

            if (
                note.book_id != target_note.book_id
                and book.primary_series_id
                and target_note.book_id in scoped_books
            ):
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
    if commit:
        await db.commit()
    return {
        "links": links_created,
        "backlinks": backlinks_created,
        "tags": tags_created,
        "series_links": series_links_created,
    }


async def list_vault_note_links(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(VaultNote)
    target_note = aliased(VaultNote)
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
    return [
        _serialize_vault_note_link(link, source_path, target_path)
        for link, source_path, target_path in rows
    ]


async def list_vault_note_backlinks(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(VaultNote)
    target_note = aliased(VaultNote)
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
    return [
        _serialize_vault_note_link(link, source_path, target_path)
        for link, source_path, target_path in rows
    ]


async def list_vault_note_tags(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    rows = (
        await db.execute(
            select(NoteTag, VaultNote.path)
            .join(VaultNote, NoteTag.note_id == VaultNote.id)
            .where(
                NoteTag.user_id == user_id,
                NoteTag.book_id == book.id,
                NoteTag.note_id == note.id,
            )
            .order_by(NoteTag.tag_name.asc())
        )
    ).all()
    return [_serialize_vault_note_tag(tag, note_path) for tag, note_path in rows]


async def list_vault_note_series_links(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(VaultNote)
    target_note = aliased(VaultNote)
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
    return [
        _serialize_vault_note_series_link(link, source_path, target_path)
        for link, source_path, target_path in rows
    ]


async def list_vault_note_relations(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "links": await list_vault_note_links(db, book=book, user_id=user_id, path=path),
        "backlinks": await list_vault_note_backlinks(db, book=book, user_id=user_id, path=path),
        "tags": await list_vault_note_tags(db, book=book, user_id=user_id, path=path),
        "series_links": await list_vault_note_series_links(
            db, book=book, user_id=user_id, path=path
        ),
    }
