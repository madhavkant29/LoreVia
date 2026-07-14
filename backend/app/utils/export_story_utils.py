from __future__ import annotations

from app.models.book import Book
from app.utils.books.normalization import story_unit_label, story_unit_name
from app.utils.export_common_utils import _clean_line


def _to_int(value: object | None, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
        return default
    except (TypeError, ValueError):
        return default


def _format_story_label(book: Book, chapter_number: int | None, fallback: str = "-") -> str:
    return story_unit_label(book, chapter_number, fallback=fallback)


def _story_unit_from_payload(payload: dict) -> str:
    return str(payload.get("work_type") or "novel")


def _story_unit_heading(payload: dict, chapter_number: int | None, fallback: str = "-") -> str:
    return story_unit_label(_story_unit_from_payload(payload), chapter_number, fallback=fallback)


def _story_unit_range(payload: dict, from_chapter: int | None, to_chapter: int | None) -> str:
    unit_name = story_unit_name(_story_unit_from_payload(payload))
    active_range = f"{unit_name} {from_chapter}" if from_chapter else "Unknown start"
    active_range += f" to {unit_name} {to_chapter}" if to_chapter else " onward"
    return active_range


def _format_growth_event_line(event: dict, book: Book | str | None = None) -> str:
    chapter_number = _to_int(event.get("chapter_number") or event.get("chapter"), 0)
    chapter_label = (
        f"{story_unit_label(book or 'novel', chapter_number)}: " if chapter_number else ""
    )
    title = _clean_line(str(event.get("event_title") or event.get("event") or ""))
    description = _clean_line(str(event.get("description") or event.get("impact") or ""))
    impact_score = event.get("impact_score") or event.get("importance")
    growth_direction = _clean_line(str(event.get("growth_direction") or ""))
    accomplishments = [
        str(item).strip() for item in (event.get("accomplishments") or []) if str(item).strip()
    ]
    suffix: list[str] = []
    if impact_score not in (None, ""):
        suffix.append(f"impact {impact_score}/10")
    if growth_direction:
        suffix.append(growth_direction)
    if accomplishments:
        suffix.append("accomplishments: " + ", ".join(accomplishments[:3]))
    detail = description or ""
    if suffix:
        detail = (detail + " " if detail else "") + f"({' | '.join(suffix)})"
    return f"{chapter_label}{title}{(': ' + detail) if detail else ''}".strip()
