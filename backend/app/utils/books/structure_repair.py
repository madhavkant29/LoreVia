"""Conservative mapping of reader positions when saved Part chapters are split."""

from __future__ import annotations

from app.utils.books.chapter_boundaries import split_saved_part_chapters


def chapter_number_map(saved: list[dict], proposed: list[dict]) -> dict[int, list[int]]:
    """Map each original chapter to the contiguous chapters made from its text."""
    mapping: dict[int, list[int]] = {}
    next_number = 1
    for row in saved:
        title = str(row.get("title") or "")
        text = str(row.get("text") or "")
        count = (
            len(split_saved_part_chapters(title.removesuffix(" — opening"), text))
            if title.endswith(" — opening")
            else 1
        )
        mapping[int(row["number"])] = list(range(next_number, next_number + count))
        next_number += count
    if next_number != len(proposed) + 1:
        raise ValueError("saved_part_chapter_mapping_mismatch")
    return mapping


def map_reading_position(
    mapping: dict[int, list[int]],
    proposed: list[dict],
    *,
    current_chapter: int,
    scroll_pct: float,
    chapters_read: list[int] | None,
) -> dict:
    """Preserve progress approximately by word offset within a formerly large Part."""
    numbers = mapping.get(current_chapter)
    if not numbers:
        raise ValueError("saved_reading_chapter_unmapped")
    completed = sorted({new for old in chapters_read or [] for new in mapping.get(old, [])})
    ratio = max(0.0, min(float(scroll_pct or 0.0), 1.0))
    if ratio == 1.0:
        return {
            "current_chapter": numbers[-1],
            "scroll_pct": 1.0,
            "chapters_read": completed,
        }
    weights = [max(1, len(str(proposed[number - 1]["text"]).split())) for number in numbers]
    remaining = sum(weights) * ratio
    for number, weight in zip(numbers, weights):
        if remaining < weight:
            return {
                "current_chapter": number,
                "scroll_pct": remaining / weight,
                "chapters_read": completed,
            }
        remaining -= weight
    raise ValueError("saved_reading_position_unmapped")
