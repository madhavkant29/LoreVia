"""Focused book planning workflows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
)
from app.models.character import (
    Character,
)
from app.models.intelligence import (
    ChapterSummary,
    PlotThread,
)
from app.utils.books.continuity import (
    build_chapter_consistency_report,
)
from app.utils.plot_thread_utils import (
    derive_plot_thread_status,
    is_plot_thread_open,
)


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
        key=lambda item: (
            item.role not in {"mc", "sc"},
            -(item.mention_count or 0),
            item.name.lower(),
        ),
    )
    for character in ordered_characters:
        raw_events = [item for item in (character.growth_events or []) if isinstance(item, dict)]
        if not raw_events:
            continue
        raw_events.sort(
            key=lambda item: int(item.get("chapter_number") or item.get("chapter") or 0)
        )
        points: list[dict[str, Any]] = []
        trajectory_score = 0.0
        for event in raw_events:
            chapter_number = int(
                event.get("chapter_number") or event.get("chapter") or character.first_chapter or 0
            )
            if chapter_number <= 0:
                continue
            label = (
                " ".join(str(event.get("event_title") or event.get("event") or "").split()).strip()
                or f"Chapter {chapter_number} shift"
            )
            impact_score = int(event.get("impact_score") or event.get("importance") or 5)
            growth_direction = (
                " ".join(str(event.get("growth_direction") or "neutral").split()).strip()
                or "neutral"
            )
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
        latest_turning_points.append(
            f"{character.name}: {latest['label']} (chapter {latest['chapter_number']})"
        )
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

    tracked.sort(
        key=lambda item: (
            item["role"] not in {"mc", "sc"},
            -abs(item["trajectory_score"]),
            item["character_name"].lower(),
        )
    )
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
        (
            await db.execute(
                select(Character)
                .where(Character.book_id == book.id, Character.last_seen_chapter.isnot(None))
                .order_by(
                    Character.last_seen_chapter.desc(),
                    Character.mention_count.desc(),
                    Character.name,
                )
                .limit(8)
            )
        )
        .scalars()
        .all()
    )
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
        (
            await db.execute(
                select(PlotThread)
                .where(PlotThread.book_id == book.id)
                .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
                .limit(8)
            )
        )
        .scalars()
        .all()
    )
    unresolved_threads = [
        {
            "id": str(thread.id),
            "title": thread.title,
            "status": derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=book.total_chapters,
            ),
            "introduced_at": thread.introduced_at,
            "note": thread.note,
        }
        for thread in unresolved_threads_rows
        if is_plot_thread_open(
            derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=book.total_chapters,
            )
        )
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
                recent_events.append(
                    {
                        "chapter_number": chapter_number,
                        "chapter_title": chapter_title,
                        "detail": str(event.get("event")).strip(),
                    }
                )
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
            alerts.append(
                {
                    "kind": "dormant_character",
                    "title": f"{name} has been absent for {total_chapters - last_seen_chapter} chapters",
                    "body": f"Readers may notice if {name} mattered earlier but never returns. Decide whether to revive, reference, or close that thread.",
                    "chapter_ref": last_seen_chapter,
                }
            )
    recent_report = (
        await build_chapter_consistency_report(db, book, total_chapters) if total_chapters else None
    )
    for flag in (recent_report.continuity_flags if recent_report else [])[:2]:
        alerts.append(
            {
                "kind": "continuity_risk",
                "title": "Readers might notice a continuity wobble",
                "body": flag,
                "chapter_ref": recent_report.chapter_number if recent_report else None,
            }
        )
    return {
        "upcoming_chapter": upcoming_chapter,
        "active_characters": active_characters,
        "unresolved_threads": unresolved_threads,
        "recent_events": recent_events[:6],
        "alerts": alerts[:4],
    }
