"""
Book utility helpers ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import (
    Book,
    VaultNote,
    VaultNoteSource,
)
from app.utils.books.vault import normalize_vault_note_path, normalize_vault_note_source
from app.utils.books.vault_relations import sync_vault_note_relations
from app.utils.upload_security_utils import validate_zip_archive_safety

if TYPE_CHECKING:
    pass


async def list_vault_notes(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> list[dict]:
    normalized_source = normalize_vault_note_source(source)
    rows = (
        (
            await db.execute(
                select(VaultNote)
                .where(
                    VaultNote.book_id == book.id,
                    VaultNote.user_id == user_id,
                    VaultNote.source == normalized_source,
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


async def save_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    content: str,
    source: str = VaultNoteSource.CHARACTER_BIBLE.value,
    sync_relations: bool = True,
) -> dict:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path)
    normalized_content = content.replace("\r\n", "\n")

    note: VaultNote | None = (
        (
            await db.execute(
                select(VaultNote).where(
                    VaultNote.book_id == book.id,
                    VaultNote.user_id == user_id,
                    VaultNote.path == normalized_path,
                    VaultNote.source == normalized_source,
                )
            )
        )
        .scalars()
        .first()
    )

    if note is None:
        note = VaultNote(
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
    if sync_relations and normalized_source == VaultNoteSource.USER_NOTES.value:
        await sync_vault_note_relations(db, book=book, user_id=user_id, source=normalized_source)
    return {
        "path": note.path,
        "source": note.source,
        "content": note.content,
        "persisted": True,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def delete_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> None:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path)
    deleted = await db.execute(
        delete(VaultNote).where(
            VaultNote.book_id == book.id,
            VaultNote.user_id == user_id,
            VaultNote.path == normalized_path,
            VaultNote.source == normalized_source,
        )
    )
    if not deleted.rowcount:
        raise HTTPException(404, "Note not found")
    await db.commit()
    if normalized_source == VaultNoteSource.USER_NOTES.value:
        await sync_vault_note_relations(db, book=book, user_id=user_id, source=normalized_source)


async def import_vault_notes_zip(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    archive_bytes: bytes,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> list[dict]:
    normalized_source = normalize_vault_note_source(source)
    if not archive_bytes:
        raise HTTPException(400, "ZIP file is empty")

    validate_zip_archive_safety(
        archive_bytes,
        max_entries=settings.UPLOAD_ARCHIVE_MAX_ENTRIES,
        max_total_uncompressed_bytes=settings.UPLOAD_ARCHIVE_MAX_UNCOMPRESSED_BYTES,
        max_compression_ratio=settings.UPLOAD_ARCHIVE_MAX_COMPRESSION_RATIO,
        label="ZIP file",
    )

    imported: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            for member in members:
                if member.filename.startswith("__MACOSX/"):
                    continue
                if not member.filename.lower().endswith(".md"):
                    continue
                normalized_path = normalize_vault_note_path(member.filename)
                content = archive.read(member).decode("utf-8")
                imported.append(
                    await save_vault_note(
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
    if normalized_source == VaultNoteSource.USER_NOTES.value:
        await sync_vault_note_relations(db, book=book, user_id=user_id, source=normalized_source)
    return imported


def export_vault_notes_zip(*, notes: list[dict[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for note in sorted(notes, key=lambda item: item["path"]):
            archive.writestr(note["path"], str(note["content"] or "").replace("\r\n", "\n"))
    return buffer.getvalue()
