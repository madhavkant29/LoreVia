"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import uuid
import zipfile
from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

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


def _encode_vault_note_page_cursor(path: str, note_id: uuid.UUID) -> str:
    payload = json.dumps({"path": path, "id": str(note_id)}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_vault_note_page_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        path = str(payload["path"])
        if not path:
            raise ValueError("Cursor path must not be empty")
        return path, uuid.UUID(str(payload["id"]))
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise HTTPException(400, "Invalid vault note page cursor") from exc


def _vault_note_payload(note: VaultNote, *, include_content: bool) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "book_id": str(note.book_id),
        "path": note.path,
        "source": note.source,
        "content": note.content if include_content else None,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def list_vault_notes_page(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = VaultNoteSource.USER_NOTES.value,
    limit: int = 50,
    cursor: str | None = None,
    include_content: bool = False,
) -> dict[str, Any]:
    """Return a path-ordered vault page without sending note content by default."""
    normalized_source = normalize_vault_note_source(source)
    bounded_limit = max(1, min(int(limit), 100))
    statement = select(VaultNote).where(
        VaultNote.book_id == book.id,
        VaultNote.user_id == user_id,
        VaultNote.source == normalized_source,
    )
    if not include_content:
        statement = statement.options(
            load_only(
                VaultNote.id,
                VaultNote.book_id,
                VaultNote.path,
                VaultNote.source,
                VaultNote.created_at,
                VaultNote.updated_at,
            )
        )
    if cursor:
        cursor_path, cursor_id = _decode_vault_note_page_cursor(cursor)
        statement = statement.where(
            or_(
                VaultNote.path > cursor_path,
                and_(VaultNote.path == cursor_path, VaultNote.id > cursor_id),
            )
        )
    rows = list(
        (
            await db.execute(
                statement.order_by(VaultNote.path.asc(), VaultNote.id.asc()).limit(bounded_limit + 1)
            )
        )
        .scalars()
        .all()
    )
    has_more = len(rows) > bounded_limit
    notes = rows[:bounded_limit]
    return {
        "items": [_vault_note_payload(note, include_content=include_content) for note in notes],
        "next_cursor": (
            _encode_vault_note_page_cursor(notes[-1].path, notes[-1].id)
            if has_more and notes
            else None
        ),
        "has_more": has_more,
    }


async def get_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> dict[str, Any]:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path)
    note = (
        await db.execute(
            select(VaultNote).where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.source == normalized_source,
                VaultNote.path == normalized_path,
            )
        )
    ).scalar_one_or_none()
    if note is None:
        raise HTTPException(404, "Vault note not found")
    return _vault_note_payload(note, include_content=True)


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

    entries_by_path: dict[str, str] = {}
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
                # ZIP members are processed in archive order. Retaining the
                # last entry gives duplicate paths the same deterministic
                # last-write-wins behavior as the former sequential importer.
                entries_by_path[normalized_path] = content.replace("\r\n", "\n")
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Invalid ZIP file") from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "ZIP contains a non-UTF-8 markdown file") from exc

    if not entries_by_path:
        raise HTTPException(400, "ZIP did not contain any markdown notes")

    paths = sorted(entries_by_path)
    try:
        existing_rows = list(
            (
                await db.execute(
                    select(VaultNote).where(
                        VaultNote.book_id == book.id,
                        VaultNote.user_id == user_id,
                        VaultNote.source == normalized_source,
                        VaultNote.path.in_(paths),
                    )
                )
            )
            .scalars()
            .all()
        )
        notes_by_path = {note.path: note for note in existing_rows}
        imported_notes: list[VaultNote] = []
        for path in paths:
            note = notes_by_path.get(path)
            if note is None:
                note = VaultNote(
                    user_id=user_id,
                    book_id=book.id,
                    path=path,
                    source=normalized_source,
                    content=entries_by_path[path],
                )
                db.add(note)
            else:
                note.content = entries_by_path[path]
            imported_notes.append(note)

        await db.flush()
        if normalized_source == VaultNoteSource.USER_NOTES.value:
            await sync_vault_note_relations(
                db,
                book=book,
                user_id=user_id,
                source=normalized_source,
                commit=False,
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return [
        {
            "path": note.path,
            "source": note.source,
            "content": note.content,
            "persisted": True,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note in imported_notes
    ]


def export_vault_notes_zip(*, notes: list[dict[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for note in sorted(notes, key=lambda item: item["path"]):
            archive.writestr(note["path"], str(note["content"] or "").replace("\r\n", "\n"))
    return buffer.getvalue()
