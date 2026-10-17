from __future__ import annotations

import math
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_asset_token, decode_token
from app.models.beta_read import BetaReadAssignment
from app.models.book import Book, Chapter
from app.schemas.beta_reads import BetaReadGuestReviewOut
from app.services.chapter_recovery_service import resolve_reader_chapter_payload
from app.utils.beta_read_assignment_query_utils import build_beta_read_assignment_detail_out
from app.utils.beta_read_lifecycle_utils import start_beta_read
from app.utils.beta_read_policy_utils import (
    ACTIVE_READER_STATES,
    assignment_scope_bounds,
    ensure_timezone,
    utc_now,
)

GUEST_RESOURCE_PREFIX = "beta-review:"


def build_beta_read_guest_link(assignment: BetaReadAssignment) -> dict[str, Any]:
    if getattr(assignment, "reader_user_id", None) is not None:
        raise HTTPException(
            409,
            "Guest links are only available for beta readers without a LoreVia account.",
        )
    now = utc_now()
    expires_at = ensure_timezone(assignment.expires_at)
    if assignment.state not in ACTIVE_READER_STATES or expires_at <= now:
        raise HTTPException(409, "Guest links are only available for active beta reads.")
    minutes = max(1, math.ceil((expires_at - now).total_seconds() / 60))
    token = create_asset_token(
        str(assignment.author_user_id),
        f"{GUEST_RESOURCE_PREFIX}{assignment.id}",
        expires_minutes=minutes,
    )
    return {
        "share_url": f"{settings.APP_URL.rstrip('/')}/review/beta/{token}",
        "expires_at": expires_at,
    }


async def resolve_beta_read_guest_assignment(db: AsyncSession, *, token: str) -> BetaReadAssignment:
    payload = decode_token(token)
    resource = str((payload or {}).get("res") or "")
    if (payload or {}).get("type") != "asset" or not resource.startswith(GUEST_RESOURCE_PREFIX):
        raise HTTPException(404, "This review link is invalid or has expired.")
    raw_id = resource.removeprefix(GUEST_RESOURCE_PREFIX)
    try:
        assignment_id = uuid.UUID(raw_id)
    except ValueError as exc:
        raise HTTPException(404, "This review link is invalid or has expired.") from exc
    assignment = await db.get(BetaReadAssignment, assignment_id)
    if assignment is None or str(assignment.author_user_id) != str(payload.get("sub") or ""):
        raise HTTPException(404, "This review link is invalid or has expired.")
    if assignment.reader_user_id is not None:
        raise HTTPException(404, "This review link is invalid or has expired.")
    if (
        assignment.state not in ACTIVE_READER_STATES
        or ensure_timezone(assignment.expires_at) <= utc_now()
    ):
        raise HTTPException(410, "This review link is no longer active.")
    return assignment


def record_beta_read_guest_chapter(
    assignment: BetaReadAssignment,
    *,
    total_chapters: int,
    chapter_number: int,
) -> None:
    start, end = assignment_scope_bounds(assignment, total_chapters)
    if not start <= chapter_number <= end:
        raise HTTPException(403, "That chapter is outside this beta read scope.")
    metadata = dict(assignment.metadata_json or {})
    read_chapters = {
        int(value)
        for value in metadata.get("guest_read_chapters", [])
        if isinstance(value, int) or str(value).isdigit()
    }
    read_chapters.add(chapter_number)
    metadata["guest_read_chapters"] = sorted(read_chapters)
    metadata["guest_last_opened_at"] = utc_now().isoformat()
    assignment.metadata_json = metadata


async def mark_beta_read_guest_chapter_read(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    chapter_number: int,
) -> None:
    book = await db.get(Book, assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found.")
    record_beta_read_guest_chapter(
        assignment,
        total_chapters=int(book.total_chapters or 0),
        chapter_number=chapter_number,
    )
    await db.commit()


async def build_beta_read_guest_review(
    db: AsyncSession, *, assignment: BetaReadAssignment
) -> BetaReadGuestReviewOut:
    book = await db.get(Book, assignment.book_id)
    if book is None:
        raise HTTPException(404, "Book not found.")
    start, end = assignment_scope_bounds(assignment, int(book.total_chapters or 0))
    chapters = list(
        (
            await db.execute(
                select(Chapter)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.number >= start,
                    Chapter.number <= end,
                )
                .order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )
    if assignment.first_opened_at is None:
        await start_beta_read(db, assignment=assignment, current_user=None)
    metadata = dict(assignment.metadata_json or {})
    metadata["guest_last_opened_at"] = utc_now().isoformat()
    assignment.metadata_json = metadata
    await db.commit()
    await db.refresh(assignment)

    chapter_payloads = []
    for chapter in chapters:
        resolved = await resolve_reader_chapter_payload(
            db,
            book=book,
            chapter=chapter,
            chapter_num=int(chapter.number),
            current_user=None,
        )
        chapter_payloads.append(
            {
                "number": int(chapter.number),
                "title": str(chapter.title or f"Chapter {chapter.number}"),
                "text": str((resolved or {}).get("text_content") or ""),
            }
        )
    detail = await build_beta_read_assignment_detail_out(db, assignment=assignment)
    return BetaReadGuestReviewOut(
        assignment=detail.assignment,
        author_questions=detail.author_questions,
        feedback_items=detail.feedback_items,
        feedback_summary=detail.feedback_summary,
        chapters=chapter_payloads,
    )
