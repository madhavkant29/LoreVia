from __future__ import annotations

import re
from typing import Iterable


PERSON_ROLE_WORDS = {
    "mr", "mrs", "ms", "miss", "dr", "doctor", "professor", "captain", "commander",
    "sir", "lady", "lord", "king", "queen", "prince", "princess", "duke", "duchess",
    "baron", "master", "mistress", "mentor", "servant", "rider", "saber", "archer",
    "lancer", "caster", "berserker", "assassin", "ruler", "shielder", "avenger",
    "foreigner", "alterego", "alter", "teacher", "father", "mother", "brother",
    "sister", "uncle", "aunt",
}

NON_PERSON_HEADWORDS = {
    "academy", "association", "catholicism", "church", "city", "circles", "convention",
    "country", "crest", "department", "designations", "enforcers", "energy", "empire",
    "eyes", "fundamentals", "gospel", "kingdom", "magecraft", "magic", "mystic",
    "nation", "office", "order", "republic", "ritual", "school", "sequence", "society",
    "spirit", "system", "temple", "theory", "tower", "towers", "university", "wonders",
}

LEADING_DESCRIPTOR_WORDS = {
    "ancient", "arcane", "central", "eastern", "first", "fourth", "great", "holy",
    "last", "magic", "mystic", "northern", "old", "roman", "royal", "sacred",
    "second", "seventh", "silver", "southern", "starless", "third", "western", "young",
}

ABSTRACT_SUFFIXES = ("ism", "tion", "ness", "ity", "ology", "ship", "ment", "ance", "ence")
NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
}


def entity_words(name: str | None) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", name or "")


def normalize_entity_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", name.lower())).strip()


def person_name_shape_score(name: str | None) -> int:
    words = entity_words(name)
    if not words:
        return -10

    lowered = [word.casefold() for word in words]
    score = 0

    if len(words) == 1:
        score += 1 if len(words[0]) >= 4 else 0
    else:
        score += 2

    if any("-" in word or "'" in word for word in words):
        score += 1
    if any(word in PERSON_ROLE_WORDS for word in lowered):
        score += 2
    if lowered[0] in {"mr", "mrs", "ms", "miss", "dr", "sir", "lady", "lord"}:
        score += 1

    if len(words) >= 2 and lowered[-1].endswith("s") and lowered[-1] not in PERSON_ROLE_WORDS:
        score -= 3
    if lowered[-1] in NON_PERSON_HEADWORDS:
        score -= 4
    if any(word in NON_PERSON_HEADWORDS for word in lowered[1:-1]):
        score -= 3
    if any(word.endswith(ABSTRACT_SUFFIXES) for word in lowered):
        score -= 3
    if lowered[0] in LEADING_DESCRIPTOR_WORDS and lowered[-1] not in PERSON_ROLE_WORDS:
        score -= 2
    if lowered[0] in NUMBER_WORDS and lowered[-1] not in PERSON_ROLE_WORDS:
        score -= 2

    return score


def looks_like_person_entity_name(name: str | None) -> bool:
    words = entity_words(name)
    if not words:
        return False
    cleaned = " ".join(words)
    if cleaned.endswith("'s"):
        return False
    if len(words) == 1 and len(words[0]) <= 3:
        return False
    return person_name_shape_score(cleaned) >= 1


def profile_evidence_score(
    *,
    role: str | None = None,
    aliases: Iterable[str] | None = None,
    personality_tags: Iterable[str] | None = None,
    motivations: Iterable[str] | None = None,
    fears: Iterable[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
) -> int:
    score = 0
    if role:
        score += 1
    if aliases:
        score += 1
    if personality_tags:
        score += 1
    if motivations or fears:
        score += 1
    if archetype:
        score += 1
    if trait_state:
        score += 1
    if relationship_count > 0:
        score += 1
    return score


def is_displayable_character_entity(
    name: str | None,
    *,
    role: str | None = None,
    aliases: Iterable[str] | None = None,
    personality_tags: Iterable[str] | None = None,
    motivations: Iterable[str] | None = None,
    fears: Iterable[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
) -> bool:
    words = entity_words(name)
    if not words:
        return False

    shape_score = person_name_shape_score(name)
    evidence_score = profile_evidence_score(
        role=role,
        aliases=aliases,
        personality_tags=personality_tags,
        motivations=motivations,
        fears=fears,
        archetype=archetype,
        trait_state=trait_state,
        relationship_count=relationship_count,
    )

    if len(words) == 1:
        return shape_score >= 1 and evidence_score >= 1

    return shape_score >= 2 and (evidence_score >= 1 or shape_score >= 3)
