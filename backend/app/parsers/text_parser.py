"""
Generic text-based chapter parser for TXT, DOCX, MD, and DOC files.

Splits plain text into chapters by detecting multilingual heading patterns
(using heading_patterns.py) and applying the same boundary heuristics as the
PDF parser — body-text-after-heading check, TOC exclusion, and confidence
scoring. Falls back to single-chapter mode when fewer than 2 headings are
found.

Public entry point: parse_text_chapters()
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.parsers.heading_patterns import (
    build_heading_regex,
    classify_heading_type,
    has_toc_signals,
    is_toc_indicator,
)
from app.utils.language_utils import detect_language

# Minimum word count of body text that must follow a heading to accept it
# as a valid chapter boundary (avoids isolated headings / TOC entries).
MIN_BODY_WORDS_AFTER_HEADING = 100

# Minimum number of valid headings in the document needed to trust the
# chapter-split result. Below this, return a single-chapter fallback.
MIN_VALID_HEADINGS = 2


def parse_text_chapters(
    text: str,
    *,
    language: str | None = None,
    title: str = "Chapter",
) -> list[dict]:
    """Split plain text into chapters using multilingual heading detection.

    Args:
        text: The full manuscript text.
        language: ISO 639-1 code. If None, auto-detected from text.
        title: Default chapter title prefix for auto-numbered chapters.

    Returns:
        List of chapter dicts with keys: title, text, number, section_type.
        Returns single-chapter fallback if fewer than MIN_VALID_HEADINGS
        headings are found.
    """
    if not text or not text.strip():
        return [{"title": title, "text": "", "number": 1, "section_type": "unknown"}]

    # ── Language detection ──────────────────────────────────────────────
    detected_language = language
    if detected_language is None:
        result = detect_language(text)
        detected_language = result["detected"]

    heading_regex = build_heading_regex(languages=[detected_language])

    # ── Split into lines ──────────────────────────────────────────────
    raw_lines = text.splitlines()
    lines = [line.strip() for line in raw_lines]

    # ── Find candidate heading line indices ───────────────────────────
    heading_candidates: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        if not line:
            continue
        if is_toc_indicator(line):
            continue
        m = heading_regex.match(line)
        if m:
            section_type, _ = classify_heading_type(line, detected_language)
            heading_candidates.append((idx, line, section_type))

    # ── Filter candidates: must have body text after them ──────────────
    valid_headings: list[tuple[int, str, str]] = []
    for i, (idx, heading, stype) in enumerate(heading_candidates):
        # Find the text between this heading and the next heading (or EOF)
        next_idx = heading_candidates[i + 1][0] if i + 1 < len(heading_candidates) else len(lines)
        body_lines = lines[idx + 1 : next_idx]
        body_text = " ".join(line for line in body_lines if line)
        body_words = len(body_text.split())

        if body_words >= MIN_BODY_WORDS_AFTER_HEADING:
            valid_headings.append((idx, heading, stype))

    # ── TOC detection on candidate headings ──────────────────────────
    # If heading-like lines cluster too densely (many headings in few lines),
    # those are likely TOC page entries rather than real chapters.
    if len(valid_headings) >= 3:
        heading_indices = [idx for idx, _, _ in valid_headings]
        heading_line_texts = [lines[idx] for idx in heading_indices if idx < len(lines)]
        if has_toc_signals(heading_line_texts):
            # Filter out headings that look like TOC entries
            filtered: list[tuple[int, str, str]] = []
            for idx, h, stype in valid_headings:
                if not is_toc_indicator(lines[idx] if idx < len(lines) else h):
                    filtered.append((idx, h, stype))
            if len(filtered) >= MIN_VALID_HEADINGS:
                valid_headings = filtered

    # ── Fallback: single chapter ──────────────────────────────────────
    if len(valid_headings) < MIN_VALID_HEADINGS:
        return [{
            "title": title,
            "text": text.strip(),
            "number": 1,
            "section_type": "unknown",
        }]

    # ── Build chapter dicts from valid heading splits ─────────────────
    chapters: list[dict] = []
    for i, (idx, heading, stype) in enumerate(valid_headings):
        next_idx = valid_headings[i + 1][0] if i + 1 < len(valid_headings) else len(lines)
        body_lines = lines[idx + 1 : next_idx]
        # Reconstruct the chapter text from original (untrimmed) raw_lines
        raw_body = raw_lines[idx + 1 : next_idx]
        chapter_text = "\n".join(raw_body).strip()

        chapters.append({
            "title": heading,
            "text": chapter_text,
            "number": i + 1,
            "section_type": stype,
        })

    return chapters


def _count_words(text: str) -> int:
    return len(text.split())
