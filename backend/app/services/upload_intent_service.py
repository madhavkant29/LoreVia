"""Crash-safe ownership intents for book-upload storage objects."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.book import Book
from app.utils.storage_utils import delete_storage_key_best_effort

log = logging.getLogger("lorevia.upload_intents")

UPLOAD_INTENT_PREFIX = "system/upload-intents"
UPLOAD_INTENT_VERSION = 1
DEFAULT_UPLOAD_INTENT_GRACE = timedelta(hours=24)


@dataclass(frozen=True)
class BookUploadIntent:
    intent_key: str
    book_id: uuid.UUID
    user_id: uuid.UUID
    source_key: str
    cover_key: str | None
    created_at: datetime

    @property
    def object_keys(self) -> tuple[str, ...]:
        return tuple(key for key in (self.source_key, self.cover_key) if key)


def build_book_upload_intent(
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    has_cover: bool,
    cover_suffix: str | None,
) -> BookUploadIntent:
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        safe_name = "manuscript"
    source_key = storage.validate_storage_key(f"books/{user_id}/{book_id}/{safe_name}")
    normalized_suffix = (
        "".join(
            character for character in str(cover_suffix or "png").lower() if character.isalnum()
        )[:12]
        or "png"
    )
    cover_key = (
        storage.validate_storage_key(f"covers/{user_id}/{book_id}.{normalized_suffix}")
        if has_cover
        else None
    )
    return BookUploadIntent(
        intent_key=f"{UPLOAD_INTENT_PREFIX}/{uuid.uuid4()}.json",
        book_id=book_id,
        user_id=user_id,
        source_key=source_key,
        cover_key=cover_key,
        created_at=datetime.now(UTC),
    )


def serialize_upload_intent(intent: BookUploadIntent) -> bytes:
    return json.dumps(
        {
            "version": UPLOAD_INTENT_VERSION,
            "book_id": str(intent.book_id),
            "user_id": str(intent.user_id),
            "source_key": intent.source_key,
            "cover_key": intent.cover_key,
            "created_at": intent.created_at.isoformat(),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def parse_upload_intent(intent_key: str, raw: bytes) -> BookUploadIntent:
    if len(raw) > 16_384:
        raise ValueError("Upload intent exceeds the maximum size.")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("version") != UPLOAD_INTENT_VERSION:
        raise ValueError("Unsupported upload intent version.")
    book_id = uuid.UUID(str(payload["book_id"]))
    user_id = uuid.UUID(str(payload["user_id"]))
    source_key = storage.validate_storage_key(str(payload["source_key"]))
    cover_value = payload.get("cover_key")
    cover_key = storage.validate_storage_key(str(cover_value)) if cover_value else None
    expected_source_prefix = f"books/{user_id}/{book_id}/"
    expected_cover_prefix = f"covers/{user_id}/{book_id}."
    if not source_key.startswith(expected_source_prefix):
        raise ValueError("Upload intent source key is outside its book scope.")
    if cover_key and not cover_key.startswith(expected_cover_prefix):
        raise ValueError("Upload intent cover key is outside its book scope.")
    created_at = datetime.fromisoformat(str(payload["created_at"]))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return BookUploadIntent(
        intent_key=storage.validate_storage_key(intent_key),
        book_id=book_id,
        user_id=user_id,
        source_key=source_key,
        cover_key=cover_key,
        created_at=created_at.astimezone(UTC),
    )


async def persist_upload_intent(intent: BookUploadIntent) -> None:
    await asyncio.to_thread(
        storage.upload_binary,
        intent.intent_key,
        serialize_upload_intent(intent),
        "application/json",
    )


async def clear_upload_intent(intent_key: str) -> bool:
    return await delete_storage_key_best_effort(intent_key, context="book_upload_intent")


async def reconcile_stale_upload_intents(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    grace: timedelta = DEFAULT_UPLOAD_INTENT_GRACE,
    limit: int = 250,
) -> dict[str, int]:
    """Remove abandoned upload objects while preserving every committed book object."""
    cutoff = (now or datetime.now(UTC)) - grace
    intent_keys = await asyncio.to_thread(
        storage.list_object_keys,
        UPLOAD_INTENT_PREFIX,
        limit=limit,
    )
    result = {"checked": 0, "reconciled": 0, "committed": 0, "invalid": 0, "failed": 0}
    for intent_key in intent_keys:
        result["checked"] += 1
        try:
            raw = await asyncio.to_thread(storage.download_book, intent_key)
            intent = parse_upload_intent(intent_key, raw)
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError):
            result["invalid"] += 1
            log.exception("upload_intent_invalid intent_key=%s", intent_key)
            continue
        if intent.created_at > cutoff:
            continue

        committed_storage = (
            await db.execute(
                select(Book.s3_key, Book.cover_s3_key)
                .where(Book.id == intent.book_id, Book.user_id == intent.user_id)
                .limit(1)
            )
        ).one_or_none()
        referenced_keys = (
            {key for key in committed_storage if key} if committed_storage is not None else set()
        )

        object_cleanup_succeeded = True
        for object_key in intent.object_keys:
            if object_key in referenced_keys:
                continue
            object_cleanup_succeeded = (
                await delete_storage_key_best_effort(
                    object_key,
                    context="abandoned_book_upload",
                )
                and object_cleanup_succeeded
            )
        if committed_storage is not None:
            if object_cleanup_succeeded and await clear_upload_intent(intent.intent_key):
                result["committed"] += 1
            else:
                result["failed"] += 1
            continue

        if object_cleanup_succeeded and await clear_upload_intent(intent.intent_key):
            result["reconciled"] += 1
            log.warning(
                "abandoned_book_upload_reconciled intent_key=%s book_id=%s object_count=%s",
                intent.intent_key,
                intent.book_id,
                len(intent.object_keys),
            )
        else:
            result["failed"] += 1
    return result
