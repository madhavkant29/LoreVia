from __future__ import annotations

import re
from collections import Counter


ELEMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "geography": ("kingdom", "empire", "city", "forest", "mountain", "river", "island", "desert"),
    "politics": ("council", "throne", "senate", "alliance", "rebellion", "faction"),
    "economics": ("coin", "currency", "trade", "market", "guild", "tax"),
    "magic_system": ("magic", "spell", "ritual", "mana", "curse", "artifact"),
    "culture": ("festival", "custom", "language", "clan", "tradition", "religion"),
    "technology": ("engine", "device", "machine", "clockwork", "weapon", "automaton"),
    "religion": ("god", "temple", "priest", "church", "faith", "prophecy"),
    "ecology": ("beast", "flora", "fauna", "plague", "harvest", "climate"),
}


def infer_element_type(name: str, description: str = "") -> str:
    haystack = f"{name} {description}".lower()
    for element_type, words in ELEMENT_PATTERNS.items():
        if any(word in haystack for word in words):
            return element_type
    return "culture"


def extract_world_elements_from_text(text: str, *, chapter_number: int | None = None) -> list[dict]:
    """Extract rough world-building candidates from text using capitalized phrases + keyword hints."""
    candidates: list[dict] = []
    seen: set[str] = set()
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return candidates

    phrases = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", cleaned)
    counts = Counter(phrases)
    for phrase, count in counts.most_common(30):
        if count < 2 or len(phrase) < 4:
            continue
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        element_type = infer_element_type(phrase, cleaned[:800])
        candidates.append(
            {
                "name": phrase,
                "element_type": element_type,
                "description": f"Mentioned {count} times in chapter {chapter_number}." if chapter_number else f"Mentioned {count} times.",
                "chapter_number": chapter_number,
                "usage_count": count,
            }
        )
    return candidates
