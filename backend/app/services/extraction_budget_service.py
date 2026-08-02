from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update

from app.core.config import settings
from app.models.book import Book
from app.models.user import User
from app.parsers.chunker import count_tokens
from app.utils.billing_utils import has_paid_reading_access


async def apply_ingestion_token_budget(
    db,
    *,
    book: Book,
    user: User | None,
    all_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    full_tokens = sum(count_tokens(chapter["text"]) for chapter in all_chapters)
    if user is None or has_paid_reading_access(user):
        return {
            "full_tokens": full_tokens,
            "processed_tokens": full_tokens,
            "was_truncated": False,
            "ai_chapters": all_chapters,
            "error": None,
        }

    result = await db.execute(
        select(func.sum(Book.total_tokens)).where(
            Book.user_id == user.id, Book.id != book.id, Book.status != "error"
        )
    )
    used_so_far = result.scalar() or 0
    remaining_budget = max(0, settings.FREE_TOTAL_TOKEN_BUDGET - used_so_far)

    if remaining_budget == 0:
        await db.execute(
            update(Book).where(Book.id == book.id).values(status="error", total_tokens=0)
        )
        await db.commit()
        return {
            "full_tokens": full_tokens,
            "processed_tokens": 0,
            "was_truncated": False,
            "ai_chapters": [],
            "error": "budget_exhausted",
            "used_so_far": used_so_far,
        }

    partial_chapters: list[dict[str, Any]] = []
    current_sum = 0
    was_truncated = False
    for chapter in all_chapters:
        chapter_tokens = count_tokens(chapter["text"])
        if current_sum + chapter_tokens <= remaining_budget:
            partial_chapters.append(chapter)
            current_sum += chapter_tokens
        else:
            was_truncated = True
            break

    if not partial_chapters:
        await db.execute(
            update(Book).where(Book.id == book.id).values(status="error", total_tokens=0)
        )
        await db.commit()
        return {
            "full_tokens": full_tokens,
            "processed_tokens": 0,
            "was_truncated": False,
            "ai_chapters": [],
            "error": "insufficient_remaining_budget",
            "remaining_budget": remaining_budget,
        }

    return {
        "full_tokens": full_tokens,
        "processed_tokens": current_sum,
        "was_truncated": was_truncated,
        "ai_chapters": partial_chapters,
        "error": None,
        "remaining_budget": remaining_budget,
    }
