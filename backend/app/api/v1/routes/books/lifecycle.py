import asyncio
import logging
import mimetypes
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


from app.api.deps.auth import get_current_user
from app.core import storage
from app.core.database import get_db
from app.core.redis import (
    mark_book_cache_dirty,
)
from app.core.security import decode_token
from app.models.book import (
    Book,
    Chapter,
)
from app.models.character import (
    Character,
)
from app.schemas.books import (
    BookOut,
    PermanentBookDeletionBody,
    PermanentBookDeletionOut,
)
from app.services.privacy_service import queue_book_permanent_deletion
from app.services.processing_allowance_service import (
    ensure_active_word_capacity,
)
from app.utils.books.character_cards import build_character_card_payload
from app.utils.books.notes import (
    get_owned_book,
)
from app.utils.books.serialization import (
    book_out,
    ensure_book_cover,
)
from app.utils.public.serialization import (
    ensure_public_mode_enabled,
)
from app.utils.storage_utils import delete_storage_key_best_effort


async def _read_upload_bounded(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    parts: list[bytes] = []
    total = 0

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break

        total += len(chunk)

        if total > max_bytes:
            raise HTTPException(
                413,
                f"{label} exceeds the maximum allowed size ({max_bytes // 1024 // 1024} MB).",
            )

        parts.append(chunk)

    await upload.seek(0)
    return b"".join(parts)


def _validate_cover_magic(raw: bytes) -> tuple[str, str]:
    for magic, (suffix, mime) in _COVER_MAGIC.items():
        if raw[: len(magic)] == magic:
            if mime == "image/webp" and raw[8:12] != b"WEBP":
                continue
            return suffix, mime
    raise HTTPException(400, "Cover image must be a JPEG, PNG, GIF, or WebP file.")


router = APIRouter()
log = logging.getLogger("lorevia.books.lifecycle")


@router.put("/{book_id}/archive", response_model=BookOut)
async def archive_book(
    book_id: uuid.UUID,
    archived: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if not archived and book.archived_at is not None:
        restoring_words = int(
            await db.scalar(
                select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                    Chapter.book_id == book.id
                )
            )
            or 0
        )
        await ensure_active_word_capacity(db, current_user, restoring_words)
    book.archived_at = datetime.now(UTC) if archived else None
    if archived:
        book.hidden_at = None
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.put("/{book_id}/hide", response_model=BookOut)
async def hide_book(
    book_id: uuid.UUID,
    hidden: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if hidden and book.archived_at is not None:
        restoring_words = int(
            await db.scalar(
                select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                    Chapter.book_id == book.id
                )
            )
            or 0
        )
        await ensure_active_word_capacity(db, current_user, restoring_words)
    book.hidden_at = datetime.now(UTC) if hidden else None
    if hidden:
        book.archived_at = None
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.delete("/{book_id}", response_model=BookOut)
async def delete_book(
    book_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    if book.archived_at is not None:
        restoring_words = int(
            await db.scalar(
                select(func.coalesce(func.sum(Chapter.word_count), 0)).where(
                    Chapter.book_id == book.id
                )
            )
            or 0
        )
        await ensure_active_word_capacity(db, current_user, restoring_words)
    book.hidden_at = datetime.now(UTC)
    book.archived_at = None
    await db.commit()
    await db.refresh(book)
    return await book_out(db, book, current_user.id)


@router.delete("/{book_id}/permanent", response_model=PermanentBookDeletionOut)
async def permanently_delete_book(
    book_id: uuid.UUID,
    body: PermanentBookDeletionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    request = await queue_book_permanent_deletion(db, book, body.confirmation_text, current_user)
    return PermanentBookDeletionOut(
        book_id=book_id, deletion_request_id=request.id, status=request.status
    )


# â”€â”€â”€ Cover management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@router.put("/{book_id}/cover", response_model=BookOut)
async def update_book_cover(
    book_id: uuid.UUID,
    cover_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    previous_cover_s3_key = book.cover_s3_key
    raw = await _read_upload_bounded(cover_file, MAX_COVER_UPLOAD_BYTES, "Cover image")
    if not raw:
        raise HTTPException(400, "Cover file is empty")
    suffix, content_type = _validate_cover_magic(raw)
    next_cover_s3_key = await asyncio.to_thread(
        storage.upload_binary,
        f"covers/{current_user.id}/{uuid.uuid4()}.{suffix}",
        raw,
        content_type,
    )
    book.cover_s3_key = next_cover_s3_key
    await db.commit()
    await db.refresh(book)
    if previous_cover_s3_key and previous_cover_s3_key != next_cover_s3_key:
        await delete_storage_key_best_effort(previous_cover_s3_key, context="book_cover")
    await mark_book_cache_dirty(str(book.id))
    return await book_out(db, book, current_user.id)


@router.delete("/{book_id}/cover", response_model=BookOut)
async def remove_book_cover(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_book(db, book_id, current_user.id)
    previous_cover_s3_key = book.cover_s3_key
    book.cover_s3_key = None
    await db.commit()
    await db.refresh(book)
    if previous_cover_s3_key:
        await delete_storage_key_best_effort(previous_cover_s3_key, context="book_cover")
    await mark_book_cache_dirty(str(book.id))
    return await book_out(db, book, current_user.id)


# â”€â”€â”€ Public asset endpoints (not router-decorated; used directly by router.py) â”€


async def get_book_cover_public(
    book_id: uuid.UUID, token: str = Query(...), db: AsyncSession = Depends(get_db)
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"book-cover:{book.id}"
    ):
        raise HTTPException(401, "Invalid cover token")

    await ensure_book_cover(db, book)
    if not book.cover_s3_key:
        raise HTTPException(404, "Cover not found")

    raw = await asyncio.to_thread(storage.download_book, book.cover_s3_key)
    media_type = mimetypes.guess_type(book.cover_s3_key)[0] or "image/png"
    return Response(
        content=raw,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


async def get_book_character_card_public(
    book_id: uuid.UUID,
    character_id: uuid.UUID,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    ensure_public_mode_enabled()
    book = await db.get(Book, book_id)
    character = await db.get(Character, character_id)
    if not book or not character or character.book_id != book.id:
        raise HTTPException(404, "Character not found")

    payload = decode_token(token)
    if (
        not payload
        or payload.get("type") != "asset"
        or payload.get("sub") != str(book.user_id)
        or payload.get("res") != f"character-card:{book.id}:{character.id}"
    ):
        raise HTTPException(401, "Invalid share token")

    return await build_character_card_payload(db, book, character)
