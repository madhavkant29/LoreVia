from __future__ import annotations

import hashlib
import uuid


def make_advisor_cache_key(book_id: str | uuid.UUID, last_user_message: str) -> str:
    """SHA-256 key for the (book, message) pair."""
    payload = f"{book_id}||{last_user_message.strip()}"
    return hashlib.sha256(payload.encode()).hexdigest()


def make_editorial_cache_key(
    book_id: str | uuid.UUID,
    text: str,
    chapter_num: int | None,
    discriminator: str | uuid.UUID | None = None,
) -> str:
    """SHA-256 key for editorial review (book, text, chapter)."""
    payload = f"{book_id}||{text.strip()[:500]}||{chapter_num or 0}||{discriminator or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()


def make_advisor_suggestions_cache_key(
    *,
    book_id: str | uuid.UUID,
    total_chapters: int,
    character_count: int,
    thread_count: int,
    state_count: int,
    relationship_count: int,
    world_element_count: int,
) -> str:
    """SHA-256 cache key for advisor suggestions scan results."""
    payload = (
        f"scan:{book_id}:ch{total_chapters}"
        f":cc{character_count}:tc{thread_count}:sc{state_count}"
        f":rc{relationship_count}:wc{world_element_count}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_synopsis_content_fingerprint(chapter_rows: list[tuple]) -> str:
    """SHA-256 fingerprint from first 3 chapters' (s3_key, content_version) tuples."""
    parts: list[str] = []
    for row in chapter_rows:
        s3_key = str(row[2] or "") if len(row) > 2 else ""
        content_version = str(row[3] or "1") if len(row) > 3 else "1"
        parts.append(f"{s3_key}|{content_version}")
    payload = "||".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def safe_prompt_str(value: str | None) -> str:
    return (value or "").replace("{", "{{").replace("}", "}}")


_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
}

_SUPPORTED_LANGUAGES = frozenset(_LANGUAGE_NAMES.keys())


def language_context_hint(language: str | None) -> str:
    """Return a prompt hint instructing the LLM about the manuscript language.

    When the language is non-English, the hint asks the model to:
    - Extract and return structured JSON with English field names
    - Preserve character names, locations, and quoted evidence in the source language
    - Write descriptions and summaries in English

    Returns an empty string for English or unknown languages.
    """
    if not language or language == "en" or language not in _SUPPORTED_LANGUAGES:
        return ""
    lang_name = _LANGUAGE_NAMES.get(language, language)
    return (
        f"The manuscript is in {lang_name}. "
        "Extract characters, locations, events, relationships, and continuity issues. "
        "Return structured JSON with English field names. "
        "Preserve names and quoted evidence in the original language. "
        "Write descriptions and summaries in English.\n\n"
    )
