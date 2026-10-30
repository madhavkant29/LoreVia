"""Find representative, mention-bearing evidence for a character partition."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.engine.character.extractor import _find_name_mentions
from app.engine.character.profile_builder import merge_list_values


def collect_partition_evidence(
    chapter_rows: Sequence[tuple[int, str]],
    *,
    name: str,
    aliases: Sequence[str],
    max_snippets: int = 6,
    snippet_chars: int = 2_200,
) -> dict[str, Any]:
    """Count distinct name spans and sample evidence across all supplied chunks."""
    if max_snippets < 1 or snippet_chars < 1:
        raise ValueError("invalid_partition_evidence_window")

    candidates = [
        candidate for candidate in merge_list_values([name], list(aliases)) if candidate.strip()
    ]
    chapter_counts: dict[int, int] = {}
    windows: list[tuple[int, str]] = []
    for chapter_number, text in chapter_rows:
        spans = sorted(
            {span for candidate in candidates for span in _find_name_mentions(text, candidate)},
            key=lambda span: (span[0], -(span[1] - span[0])),
        )
        distinct_spans: list[tuple[int, int]] = []
        for start, end in spans:
            if distinct_spans and start < distinct_spans[-1][1]:
                continue
            distinct_spans.append((start, end))
        if not distinct_spans:
            continue

        chapter_counts[chapter_number] = chapter_counts.get(chapter_number, 0) + len(distinct_spans)
        previous_window_end = 0
        for start, end in distinct_spans:
            if end <= previous_window_end:
                continue
            window_start = min(
                max(0, start - snippet_chars // 3), max(0, len(text) - snippet_chars)
            )
            if end > window_start + snippet_chars:
                window_start = max(0, end - snippet_chars)
            window_end = min(len(text), window_start + snippet_chars)
            windows.append((chapter_number, text[window_start:window_end]))
            previous_window_end = window_end

    if len(windows) > max_snippets:
        indices = [
            round(index * (len(windows) - 1) / max(1, max_snippets - 1))
            for index in range(max_snippets)
        ]
        windows = [windows[index] for index in indices]

    ordered_chapters = sorted(chapter_counts)
    return {
        "chapter_counts": chapter_counts,
        "snippets": [text for _, text in windows],
        "snippet_chapters": [chapter for chapter, _ in windows],
        "mention_count": sum(chapter_counts.values()),
        "first_chapter": ordered_chapters[0] if ordered_chapters else None,
        "last_seen_chapter": ordered_chapters[-1] if ordered_chapters else None,
    }
