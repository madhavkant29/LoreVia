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
MIN_SHORT_CHAPTER_WORDS = 12

# Minimum number of valid headings in the document needed to trust the
# chapter-split result. Below this, return a single-chapter fallback.
MIN_VALID_HEADINGS = 2

# Maximum words in a clean chapter title. Titles exceeding this after
# the heading keyword+number are likely contaminated with body text.
MAX_TITLE_WORDS = 12

# Regex to match just the heading keyword + number (for extracting clean
# titles from lines that may also contain body text after the heading).
_HEADING_BASE_RE = re.compile(
    r"^(?:chapter|ch\.?|part|volume|vol\.?|book|act|episode|section|scene)\s+"
    r"(?:\d+[a-z]?|[ivxlcdm]+|[a-z]{1,3})",
    re.IGNORECASE,
)

# Date patterns that indicate body text following a heading on the same line.
_DATE_PATTERN = re.compile(
    r"(?<!\w)(\d{1,2})\s+"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)",
    re.IGNORECASE,
)

_BARE_ROMAN_HEADING_RE = re.compile(r"([IVXLCDM]{1,6})\.?$", re.IGNORECASE | re.ASCII)


def _bare_roman_chapter_number(line: str) -> int | None:
    """Read a canonical, standalone Roman chapter number without treating prose as one."""
    match = _BARE_ROMAN_HEADING_RE.fullmatch(line.strip())
    if match is None:
        return None
    marker = match.group(1).upper()
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    number = 0
    for index, letter in enumerate(marker):
        value = values[letter]
        number += -value if index + 1 < len(marker) and value < values[marker[index + 1]] else value
    if not 1 <= number <= 30:
        return None
    remainder = number
    canonical = ""
    for value, symbol in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        count, remainder = divmod(remainder, value)
        canonical += symbol * count
    return number if marker == canonical else None


def _roman_chapters_inside_parts(
    raw_lines: list[str], candidates: list[tuple[int, str, str]]
) -> dict[int, int]:
    """Trust isolated Roman headings only as a complete sequence inside a Part."""
    part_lines = [index for index, _heading, kind in candidates if kind == "part"]
    accepted: dict[int, int] = {}
    for part_index, start in enumerate(part_lines):
        end = part_lines[part_index + 1] if part_index + 1 < len(part_lines) else len(raw_lines)
        if any(
            kind == "chapter"
            and start < index < end
            and _bare_roman_chapter_number(raw_lines[index]) is None
            for index, _heading, kind in candidates
        ):
            continue
        markers: list[tuple[int, int]] = []
        for index in range(start + 1, end):
            number = _bare_roman_chapter_number(raw_lines[index])
            if number is None:
                continue
            if raw_lines[index - 1].strip() or (
                index + 1 < len(raw_lines) and raw_lines[index + 1].strip()
            ):
                continue
            markers.append((index, number))
        if len(markers) < 2 or [number for _index, number in markers] != list(
            range(1, len(markers) + 1)
        ):
            continue
        if len(" ".join(raw_lines[start + 1 : markers[0][0]]).split()) > 100:
            continue
        boundaries = [index for index, _number in markers] + [end]
        if any(
            len(" ".join(raw_lines[left + 1 : right]).split()) < MIN_SHORT_CHAPTER_WORDS
            or has_toc_signals(raw_lines[left + 1 : min(right, left + 9)])
            for left, right in zip(boundaries, boundaries[1:])
        ):
            continue
        accepted.update((index, number) for index, number in markers)
    return accepted


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
    lines = [re.sub(r"^#{1,6}\s+", "", line.strip()) for line in raw_lines]

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

        if body_words >= MIN_BODY_WORDS_AFTER_HEADING or (
            stype in {"chapter", "prologue", "epilogue", "scene"}
            and (
                body_words >= MIN_SHORT_CHAPTER_WORDS
                or (body_words > 0 and body_text.rstrip().endswith((".", "!", "?", "…")))
            )
            and not has_toc_signals(body_lines[:8])
        ):
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
        return [
            {
                "title": title,
                "text": text.strip(),
                "number": 1,
                "section_type": "unknown",
            }
        ]

    # ── Build chapter dicts from valid heading splits ─────────────────
    chapters: list[dict] = []
    leading_lines = raw_lines[: valid_headings[0][0]]
    keep_leading_text = bool(" ".join(leading_lines).strip()) and not (
        has_toc_signals(leading_lines)
        or any(is_toc_indicator(line.strip()) for line in leading_lines)
    )
    for i, (idx, heading, stype) in enumerate(valid_headings):
        next_idx = valid_headings[i + 1][0] if i + 1 < len(valid_headings) else len(lines)
        # Reconstruct the chapter text from original (untrimmed) raw_lines
        raw_body = raw_lines[idx + 1 : next_idx]
        if i == 0 and keep_leading_text:
            raw_body = [*leading_lines, "", *raw_body]

        # Extract a clean title from the heading line, recovering any body
        # text that was merged onto the same line (common in some ebooks).
        clean_title, extra_body = _extract_clean_heading(heading)
        if extra_body:
            raw_body.insert(0, extra_body)
        chapter_text = "\n".join(raw_body).strip()

        chapters.append(
            {
                "title": clean_title,
                "text": chapter_text,
                "number": i + 1,
                "section_type": stype,
            }
        )

    return chapters


def parse_text_structure(
    text: str,
    *,
    language: str | None = None,
    title: str = "Manuscript",
    heading_hint_lines: set[int] | None = None,
    chapter_hint_lines: set[int] | None = None,
    source_name: str = "line",
) -> list[dict]:
    """Keep front/back matter and Part boundaries while avoiding TOC-only headings."""
    if not text.strip():
        return []
    detected_language = language or detect_language(text)["detected"]
    heading_regex = build_heading_regex(languages=[detected_language])
    raw_lines = text.splitlines()
    candidates: list[tuple[int, str, str]] = []
    for index, raw_line in enumerate(raw_lines):
        line = re.sub(r"^#{1,6}\s+", "", raw_line.strip())
        if not line or is_toc_indicator(line):
            continue
        author_matter = line.casefold() in {
            "about the author",
            "about the authors",
            "author biography",
        }
        explicit = bool(heading_regex.fullmatch(line)) or author_matter
        styled = heading_hint_lines is not None and index in heading_hint_lines
        if not explicit and not styled:
            continue
        kind, _ = classify_heading_type(line, detected_language)
        if author_matter:
            kind = "notes"
        if kind == "unknown" and chapter_hint_lines and index in chapter_hint_lines:
            kind = "chapter"
        candidates.append((index, line, kind))

    roman_numbers = _roman_chapters_inside_parts(raw_lines, candidates)
    candidates = [
        (index, heading, "chapter" if index in roman_numbers else kind)
        for index, heading, kind in candidates
    ]
    known_indices = {index for index, _heading, _kind in candidates}
    candidates.extend(
        (index, raw_lines[index].strip(), "chapter")
        for index in roman_numbers
        if index not in known_indices
    )
    candidates.sort(key=lambda item: item[0])

    accepted: list[tuple[int, str, str]] = []
    for index, (line_index, heading, kind) in enumerate(candidates):
        next_index = candidates[index + 1][0] if index + 1 < len(candidates) else len(raw_lines)
        body = " ".join(
            line.strip() for line in raw_lines[line_index + 1 : next_index] if line.strip()
        )
        words = len(body.split())
        if kind in {"part", "toc"}:
            accepted.append((line_index, heading, kind))
        elif kind in {
            "notes",
            "chronology",
            "preface",
            "foreword",
            "appendix",
            "afterword",
            "glossary",
            "acknowledgements",
            "dedication",
            "prologue",
            "epilogue",
            "interlude",
        }:
            if words or kind in {"dedication", "prologue", "epilogue"}:
                accepted.append((line_index, heading, kind))
        elif words >= MIN_SHORT_CHAPTER_WORDS or (
            words > 0 and body.rstrip().endswith((".", "!", "?", "…"))
        ):
            if not has_toc_signals(raw_lines[line_index + 1 : min(next_index, line_index + 9)]):
                accepted.append((line_index, heading, kind))
        elif words and not has_toc_signals(
            raw_lines[line_index + 1 : min(next_index, line_index + 9)]
        ):
            accepted.append((line_index, heading, "unknown"))

    if not accepted:
        return [
            {
                "title": title,
                "text": text.strip(),
                "number": 1,
                "section_type": "unknown",
                "source_location": f"{source_name} 1",
                "start_line": 1,
                "end_line": len(raw_lines),
            }
        ]

    from app.parsers.pdf_parser import _extract_source_number_from_heading

    sections: list[dict] = []
    if accepted[0][0] > 0:
        leading = "\n".join(raw_lines[: accepted[0][0]]).strip()
        if leading:
            title_page = len(leading.split()) <= 400 and bool(
                re.search(r"\b(?:copyright|all rights reserved)\b", leading, re.IGNORECASE)
            )
            sections.append(
                {
                    "title": "Opening material",
                    "text": leading,
                    "section_type": "title_page" if title_page else "unknown",
                    "source_location": f"{source_name} 1–{accepted[0][0]}",
                    "start_line": 1,
                    "end_line": accepted[0][0],
                }
            )
    for index, (line_index, heading, kind) in enumerate(accepted):
        end = accepted[index + 1][0] if index + 1 < len(accepted) else len(raw_lines)
        body = "\n".join(raw_lines[line_index + 1 : end]).strip()
        sections.append(
            {
                "number": len(sections) + 1,
                "title": heading,
                "text": body,
                "section_type": kind,
                "source_number": roman_numbers.get(line_index)
                or _extract_source_number_from_heading(heading),
                "source_location": f"{source_name} {line_index + 1}–{end}",
                "start_line": line_index + 1,
                "end_line": end,
            }
        )
    return sections


def _extract_clean_heading(line: str) -> tuple[str, str]:
    """Extract a clean chapter title from a heading line.

    When PDF text extraction or plain-text formatting merges body text
    onto the same line as the chapter heading, the full line becomes an
    over-long title. This function splits the line into a clean title
    (heading keyword + number + optional short descriptive text) and any
    body text that followed on the same line.

    Returns:
        (clean_title, extra_body_text) — extra_body_text is empty when the
        line contained only a clean heading.
    """
    m = _HEADING_BASE_RE.match(line)
    if not m:
        return line, ""

    base = m.group(0).strip()
    rest = line[m.end() :].strip()
    if not rest:
        return base, ""

    # Check for a separator (colon, period, dash) that may introduce a title
    sep_match = re.match(r"\s*[:.\-]\s*", rest)
    if sep_match:
        after_sep = rest[sep_match.end() :]
        # Look for body-text indicators in the text after the separator
        body_pos = _find_body_text_start(after_sep)
        if body_pos is not None:
            title_text = after_sep[:body_pos].strip()
            extra = after_sep[body_pos:].strip()
            if title_text:
                return f"{base}{sep_match.group(0)}{title_text}", extra
            return base, rest
        # No body-text indicator — it may be a clean multi-word title
        words = after_sep.split()
        if len(words) <= MAX_TITLE_WORDS:
            return line, ""
        # Title is suspiciously long; keep only the separator + short portion
        title_text = " ".join(words[:MAX_TITLE_WORDS])
        extra = " ".join(words[MAX_TITLE_WORDS:])
        return f"{base}{sep_match.group(0)}{title_text}", extra

    # No separator found — the rest is body text on the same line
    return base, rest


def _find_body_text_start(text: str) -> int | None:
    """Find where body text starts after a heading's title portion.

    Looks for patterns like dates ("5 May") that signal the title has
    ended and body prose has begun.
    """
    m = _DATE_PATTERN.search(text)
    if m:
        return m.start()
    return None


def _count_words(text: str) -> int:
    return len(text.split())
