"""Focused book chapter titles workflows."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from app.utils.books import (
    book_text,
)
from app.utils.books.domain_constants import (
    CHAPTER_TITLE_MAX_WORDS,
    CHAPTER_TITLE_MIN_WORDS,
    CHAPTER_TITLE_STOPWORDS,
    CHAPTER_TITLE_WORD_RE,
)


def _count_words(text: str) -> int:
    cleaned = " ".join((text or "").split()).strip()
    return len(cleaned.split()) if cleaned else 0


def _chapter_title_word_count(title: str | None) -> int:
    return len(CHAPTER_TITLE_WORD_RE.findall(title or ""))


def normalize_chapter_title(title: str | None) -> str | None:
    cleaned = book_text._clean_optional_text(" ".join(str(title or "").split()).strip())
    if cleaned is None:
        return None
    word_count = _chapter_title_word_count(cleaned)
    if word_count < CHAPTER_TITLE_MIN_WORDS or word_count > CHAPTER_TITLE_MAX_WORDS:
        raise HTTPException(
            400,
            f"Chapter title must be between {CHAPTER_TITLE_MIN_WORDS} and {CHAPTER_TITLE_MAX_WORDS} words.",
        )
    return cleaned


def chapter_title_is_placeholder(title: str | None, *, chapter_number: int | None = None) -> bool:
    cleaned = " ".join(str(title or "").split()).strip().lower()
    if not cleaned:
        return True
    if chapter_number is not None and cleaned == f"chapter {chapter_number}".lower():
        return True
    return bool(
        re.fullmatch(
            r"(chapter|part|section|scene|act|book|episode|volume)\s+([0-9]+|[ivxlcdm]+|[a-z])",
            cleaned,
        )
    )


def suggest_source_chapter_title(
    title: str | None,
    *,
    source_label: str | None,
    section_kind: str | None,
    summary: str | None,
    key_events: list[dict[str, Any]] | None = None,
    chapter_number: int | None = None,
) -> str | None:
    """Offer a recap-derived title without changing the printed chapter heading."""
    cleaned = " ".join(str(title or "").split()).strip()
    numbered_source_label = (
        section_kind == "chapter"
        and cleaned == " ".join(str(source_label or "").split()).strip()
        and bool(re.fullmatch(r"(?:[IVXLCDM]{1,8}|[0-9]{1,4})[.]?", cleaned, re.IGNORECASE))
    )
    if not numbered_source_label and not chapter_title_is_placeholder(
        title, chapter_number=chapter_number
    ):
        return None
    ranked_events = sorted(
        (event for event in (key_events or []) if isinstance(event, dict)),
        key=lambda event: _event_importance(event),
        reverse=True,
    )
    suggestion = None
    if ranked_events:
        event_title = book_text._clean_optional_text(
            str(ranked_events[0].get("event_title") or ranked_events[0].get("event") or "")
        )
        event_words = CHAPTER_TITLE_WORD_RE.findall(event_title or "")
        if 1 <= len(event_words) <= CHAPTER_TITLE_MAX_WORDS:
            suggestion = " ".join(
                word
                if any(character.isupper() for character in word[1:])
                else word[:1].upper() + word[1:]
                for word in event_words
            )
    suggestion = suggestion or build_chapter_title_from_summary(summary, key_events=ranked_events)
    if not suggestion or suggestion.casefold() == cleaned.casefold():
        return None
    return suggestion


def _event_importance(event: dict[str, Any]) -> int:
    try:
        return int(event.get("importance") or 0)
    except (TypeError, ValueError):
        return 0


def build_chapter_title_from_summary(
    summary: str | None,
    *,
    key_events: list[dict[str, Any]] | None = None,
) -> str | None:
    candidates: list[str] = []
    for event in key_events or []:
        if not isinstance(event, dict):
            continue
        event_title = book_text._clean_optional_text(
            str(event.get("event_title") or event.get("event") or "").strip()
        )
        if event_title:
            candidates.append(event_title)
    cleaned_summary = book_text._clean_optional_text(summary)
    if cleaned_summary:
        first_sentence = re.split(r"(?<=[.!?])\s+", cleaned_summary, maxsplit=1)[0].strip()
        if first_sentence:
            candidates.append(first_sentence)
        candidates.append(cleaned_summary)

    for candidate in candidates:
        words = CHAPTER_TITLE_WORD_RE.findall(candidate)
        if not words:
            continue
        meaningful_words = [word for word in words if word.lower() not in CHAPTER_TITLE_STOPWORDS]
        selected_words = (meaningful_words or words)[:CHAPTER_TITLE_MAX_WORDS]
        generated = " ".join(word.capitalize() for word in selected_words).strip()
        if generated:
            return generated
    return None
