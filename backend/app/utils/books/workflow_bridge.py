from __future__ import annotations

import asyncio
import hashlib
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_asset_token, decode_token
from app.models.book import Book, Chapter
from app.services.chapter_recovery_service import download_stored_text_or_empty
from app.utils.books.imports import normalize_imported_chapters, parse_import_upload
from app.utils.scrivener_utils import build_scrivener_archive
from app.utils.storage_utils import bounded_storage_map

WORKFLOW_PREVIEW_RESOURCE_PREFIX = "workflow-preview:"


def _content_digest(value: str) -> str:
    normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_workflow_preview_token(
    *,
    user_id: object,
    book_id: object,
    format_name: str,
    raw: bytes,
    book_state_digest: str,
) -> str:
    digest = hashlib.sha256(raw).hexdigest()
    resource = (
        f"{WORKFLOW_PREVIEW_RESOURCE_PREFIX}{book_id}:{format_name}:{digest}:{book_state_digest}"
    )
    return create_asset_token(str(user_id), resource, expires_minutes=60)


def verify_workflow_preview_token(
    token: str,
    *,
    user_id: object,
    book_id: object,
    format_name: str,
    raw: bytes,
    book_state_digest: str,
) -> None:
    payload = decode_token(token)
    expected_resource = (
        f"{WORKFLOW_PREVIEW_RESOURCE_PREFIX}{book_id}:{format_name}:"
        f"{hashlib.sha256(raw).hexdigest()}:{book_state_digest}"
    )
    if (
        not payload
        or payload.get("type") != "asset"
        or str(payload.get("sub") or "") != str(user_id)
        or not secrets.compare_digest(str(payload.get("res") or ""), expected_resource)
    ):
        raise HTTPException(409, "This file no longer matches its preview. Preview it again.")


def workflow_book_state_digest(chapters: list[Chapter]) -> str:
    state = "\n".join(
        "|".join(
            (
                str(chapter.id),
                str(int(chapter.number)),
                str(chapter.title or ""),
                str(int(chapter.content_version or 1)),
                str(int(chapter.word_count or 0)),
                str(chapter.s3_key or ""),
            )
        )
        for chapter in sorted(chapters, key=lambda item: int(item.number))
    )
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


async def load_workflow_book_state_digest(
    db: AsyncSession,
    *,
    book_id: object,
    lock_for_update: bool = False,
) -> str:
    statement = select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number.asc())
    if lock_for_update:
        statement = statement.with_for_update()
    chapters = list((await db.execute(statement)).scalars().all())
    return workflow_book_state_digest(chapters)


async def build_workflow_import_jobs(filename: str, raw: bytes) -> list[dict[str, object]]:
    parsed = await parse_import_upload(filename, raw, split_into_chapters=True)
    import_jobs = normalize_imported_chapters(
        parsed,
        chapter_number=None,
        start_number=1,
        replace_existing=True,
        chunk_long_documents=False,
        preserve_exact_structure=True,
    )
    if not import_jobs:
        raise HTTPException(400, "The incoming project does not contain any manuscript text.")
    return import_jobs


async def preview_workflow_import(
    db: AsyncSession,
    *,
    book: Book,
    filename: str,
    raw: bytes,
    format_name: str,
) -> dict[str, Any]:
    incoming = await build_workflow_import_jobs(filename, raw)
    current = list(
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )
    incoming_numbers = {
        int(chapter.get("number") or index) for index, chapter in enumerate(incoming, start=1)
    }
    matched_current = [chapter for chapter in current if int(chapter.number) in incoming_numbers]
    current_texts = await bounded_storage_map(
        matched_current,
        lambda chapter: asyncio.to_thread(download_stored_text_or_empty, chapter),
    )
    current_by_number = {
        int(chapter.number): (chapter, text)
        for chapter, text in zip(matched_current, current_texts)
    }
    matched_numbers: set[int] = set()
    previews = []
    for index, chapter in enumerate(incoming, start=1):
        title = str(chapter.get("title") or f"Chapter {index}")
        incoming_number = int(chapter.get("number") or index)
        incoming_text = str(chapter.get("text") or "")
        match = current_by_number.get(incoming_number)
        if match is None:
            status = "new"
            matched_number = None
            current_word_count = None
        else:
            current_chapter, current_text = match
            matched_number = int(current_chapter.number)
            matched_numbers.add(matched_number)
            status = (
                "unchanged"
                if _content_digest(incoming_text) == _content_digest(current_text)
                else "changed"
            )
            current_word_count = int(current_chapter.word_count or len(current_text.split()))
        previews.append(
            {
                "incoming_number": incoming_number,
                "incoming_title": title,
                "matched_chapter_number": matched_number,
                "status": status,
                "incoming_word_count": len(incoming_text.split()),
                "current_word_count": current_word_count,
            }
        )
    counts = {
        status: sum(1 for item in previews if item["status"] == status)
        for status in ("new", "changed", "unchanged")
    }
    return {
        "format": format_name,
        "book_state_digest": workflow_book_state_digest(current),
        "incoming_chapter_count": len(previews),
        "new_count": counts["new"],
        "changed_count": counts["changed"],
        "unchanged_count": counts["unchanged"],
        "chapters": previews,
        "preserved_chapter_numbers": sorted(
            {int(chapter.number) for chapter in current} - matched_numbers
        ),
    }


async def export_book_to_scrivener(db: AsyncSession, *, book: Book) -> bytes:
    chapters = list(
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )
    texts = await bounded_storage_map(
        chapters,
        lambda chapter: asyncio.to_thread(download_stored_text_or_empty, chapter),
    )
    return await asyncio.to_thread(
        build_scrivener_archive,
        book.title,
        [
            {"title": chapter.title or f"Chapter {chapter.number}", "text": text}
            for chapter, text in zip(chapters, texts)
        ],
    )
