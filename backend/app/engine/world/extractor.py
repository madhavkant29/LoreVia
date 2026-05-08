from __future__ import annotations

import functools
import re
from collections import Counter

from app.engine.character.entity_filters import (
    COMMON_NON_NAME_WORDS,
    looks_like_person_entity_name,
    normalize_entity_name,
    person_name_shape_score,
)


ELEMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "country": ("country", "kingdom", "nation", "empire", "realm", "republic", "sovereignty"),
    "region": ("area", "province", "region", "territory", "borderland", "frontier", "wastes"),
    "race": ("race", "species", "people", "folk", "tribe", "clan", "bloodline"),
    "magic_system": ("aether", "arcana", "magic", "mana", "spell", "spellcraft", "sorcery", "witchcraft"),
    "culture": ("culture", "custom", "festival", "holiday", "taboo", "tradition"),
    "language": ("dialect", "language", "script", "tongue"),
    "religion": ("church", "deity", "faith", "god", "goddess", "pantheon", "religion", "ritual", "temple"),
    "creature": ("beast", "creature", "dragon", "monster", "spirit"),
    "technology": ("device", "engine", "machine", "technology"),
    "place": ("city", "street", "lane", "square", "river", "canal", "bridge", "palace", "district", "island", "mountain", "forest", "desert", "capital"),
    "organization": ("council", "throne", "senate", "alliance", "rebellion", "faction", "guild", "church", "office", "department", "university", "police"),
    "object": ("artifact", "axe", "coin", "device", "machine", "ring", "sword", "weapon", "watch"),
    "event": ("festival", "murder", "rebellion", "trial", "war", "confession", "exile", "funeral"),
    "concept": ("culture", "custom", "faith", "idea", "language", "magic", "mana", "philosophy", "prophecy", "religion", "ritual", "theory", "tradition"),
    "era": ("century", "era", "summer", "winter", "year"),
}
SECTION_LABEL_TYPES: dict[str, str] = {
    "area": "region",
    "areas": "region",
    "beast": "creature",
    "beasts": "creature",
    "bloodline": "race",
    "bloodlines": "race",
    "city": "place",
    "cities": "place",
    "clan": "race",
    "clans": "race",
    "country": "country",
    "countries": "country",
    "creature": "creature",
    "creatures": "creature",
    "culture": "culture",
    "cultures": "culture",
    "deities": "religion",
    "deity": "religion",
    "district": "region",
    "districts": "region",
    "empire": "country",
    "empires": "country",
    "faith": "religion",
    "faiths": "religion",
    "faction": "organization",
    "factions": "organization",
    "folk": "race",
    "geography": "region",
    "god": "religion",
    "goddess": "religion",
    "gods": "religion",
    "government": "organization",
    "governments": "organization",
    "kingdom": "country",
    "kingdoms": "country",
    "language": "language",
    "languages": "language",
    "location": "place",
    "locations": "place",
    "magic": "magic_system",
    "magic system": "magic_system",
    "magic systems": "magic_system",
    "mana": "magic_system",
    "nation": "country",
    "nations": "country",
    "pantheon": "religion",
    "pantheons": "religion",
    "people": "race",
    "peoples": "race",
    "place": "place",
    "places": "place",
    "power system": "magic_system",
    "power systems": "magic_system",
    "province": "region",
    "provinces": "region",
    "race": "race",
    "races": "race",
    "realm": "country",
    "realms": "country",
    "region": "region",
    "regions": "region",
    "religion": "religion",
    "religions": "religion",
    "species": "race",
    "spellcasting": "magic_system",
    "technology": "technology",
    "territories": "region",
    "territory": "region",
    "tribe": "race",
    "tribes": "race",
}
SECTION_BOUNDARY_WORDS = {
    "areas",
    "countries",
    "cultures",
    "factions",
    "geography",
    "languages",
    "locations",
    "magic",
    "pantheons",
    "places",
    "races",
    "regions",
    "religions",
    "spellcasting",
    "technology",
}

WORLD_ELEMENT_BLOCKLIST = {
    "chapter",
    "crime",
    "end",
    "manuscript",
    "note",
    "part",
    "preface",
    "punishment",
    "reading",
    "source",
    "sources",
    "system",
    "world",
}
WORLD_META_HINTS = (
    "a note on sources",
    "adaptation",
    "based on the novel by",
    "end of manuscript",
    "first published",
    "for further reading",
    "translation by",
    "widely considered",
)
STRUCTURAL_LINE_HINTS = (
    "a note on sources",
    "adaptation",
    "end of manuscript",
    "first published",
    "for further reading",
    "translation by",
    "widely considered",
)
PLACE_SUFFIXES = {
    "alley",
    "avenue",
    "bridge",
    "canal",
    "cathedral",
    "city",
    "district",
    "fortress",
    "island",
    "lane",
    "market",
    "office",
    "palace",
    "precinct",
    "prospekt",
    "river",
    "road",
    "square",
    "street",
    "university",
}
COUNTRY_SUFFIXES = {"country", "empire", "kingdom", "nation", "realm", "republic", "state", "states", "sovereignty"}
REGION_SUFFIXES = {"area", "borderland", "district", "frontier", "lands", "province", "region", "territories", "territory", "wastes"}
RACE_SUFFIXES = {"bloodline", "clan", "clans", "folk", "kin", "people", "race", "species", "tribe", "tribes"}
MAGIC_SUFFIXES = {"arcana", "binding", "craft", "magic", "mana", "mancy", "spellcraft", "sorcery"}
ORGANIZATION_SUFFIXES = {"church", "court", "department", "guild", "office", "order", "police", "senate", "tribunal"}
OBJECT_SUFFIXES = {"axe", "book", "coin", "document", "ring", "sword", "ticket", "watch"}
EVENT_SUFFIXES = {"confession", "festival", "murder", "rebellion", "trial", "war"}
CONCEPT_SUFFIXES = {"culture", "faith", "idea", "language", "morality", "philosophy", "religion", "theory", "tradition"}
COMMON_VERB_LEMMAS = {
    "ask",
    "be",
    "become",
    "begin",
    "bring",
    "call",
    "come",
    "do",
    "fall",
    "feel",
    "find",
    "follow",
    "go",
    "have",
    "hear",
    "hold",
    "keep",
    "know",
    "leave",
    "look",
    "make",
    "mean",
    "need",
    "remain",
    "return",
    "say",
    "seem",
    "see",
    "show",
    "stand",
    "take",
    "tell",
    "think",
    "turn",
    "walk",
    "want",
    "work",
}
NON_ENTITY_POS_TAGS = {"VERB", "AUX", "DET", "PRON", "ADV", "ADP", "CCONJ", "SCONJ", "PART", "INTJ"}
NEGATION_TERMS = {"no", "not", "never", "neither", "nor", "without", "hardly"}

_pos_nlp = None
_pos_nlp_loaded = False


def infer_element_type(name: str, description: str = "") -> str:
    normalized_name = normalize_entity_name(name)
    words = normalized_name.split()
    lowered = f"{normalized_name} {description}".lower()
    if words:
        last_word = words[-1]
        if last_word in COUNTRY_SUFFIXES:
            return "country"
        if last_word in REGION_SUFFIXES:
            return "region"
        if last_word in RACE_SUFFIXES:
            return "race"
        if last_word in MAGIC_SUFFIXES or last_word.endswith("mancy"):
            return "magic_system"
        if last_word in PLACE_SUFFIXES:
            return "place"
        if last_word in ORGANIZATION_SUFFIXES:
            return "organization"
        if last_word in OBJECT_SUFFIXES:
            return "object"
        if last_word in EVENT_SUFFIXES:
            return "event"
        if last_word in CONCEPT_SUFFIXES:
            return "concept"
    if "magic system" in lowered or "power system" in lowered:
        return "magic_system"
    haystack = f"{name} {description}".lower()
    for element_type, words in ELEMENT_PATTERNS.items():
        if any(word in haystack for word in words):
            return element_type
    if looks_like_person_entity_name(name):
        return "character"
    if re.search(r"\b(18|19|20)\d{2}\b", lowered):
        return "era"
    return "concept"


def extract_claims_from_text(name: str, description: str, element_type: str) -> list[dict]:
    return _extract_claims(name, description, element_type)


def extract_world_elements_from_text(text: str, *, chapter_number: int | None = None) -> list[dict]:
    """Extract world-building candidates with lightweight typing, confidence, and provenance."""
    candidates: list[dict] = []
    seen: set[str] = set()
    raw_text = text or ""
    cleaned = _preprocess_world_text(raw_text)
    if not cleaned:
        return candidates

    for labeled_candidate in _extract_labeled_world_candidates(raw_text, chapter_number=chapter_number):
        phrase = str(labeled_candidate.get("name") or "").strip()
        key = phrase.lower()
        if key in seen:
            continue
        if is_valid_world_element_candidate(
            phrase,
            raw_text,
            count=int(labeled_candidate.get("usage_count") or 1),
            description=str(labeled_candidate.get("description") or ""),
            provenance=labeled_candidate.get("provenance") if isinstance(labeled_candidate.get("provenance"), dict) else None,
        ):
            seen.add(key)
            candidates.append(labeled_candidate)

    sentence_spans = _split_sentences_with_offsets(cleaned)
    matches = list(re.finditer(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", cleaned))
    phrases = [match.group(0) for match in matches]
    counts = Counter(phrases)
    occurrences_by_phrase: dict[str, list[dict]] = {}
    for match in matches:
        occurrences_by_phrase.setdefault(match.group(0), []).append(
            {
                "start": match.start(),
                "end": match.end(),
            }
        )
    for phrase, count in counts.most_common(30):
        occurrence_entries = occurrences_by_phrase.get(phrase) or []
        provenance = _best_provenance(cleaned, phrase, occurrence_entries, sentence_spans)
        description = str((provenance or {}).get("excerpt") or "").strip()
        narrative_mode = str((provenance or {}).get("narrative_mode") or "unknown")
        element_type = infer_element_type(phrase, description or cleaned[:800])
        if (
            (
                count < 1
                or (
                    count < 2
                    and chapter_number is not None
                    and not _allow_single_mention_chapter_candidate(
                        phrase,
                        description,
                        element_type=element_type,
                        narrative_mode=narrative_mode,
                    )
                )
            )
            or len(phrase) < 4
            or not is_valid_world_element_candidate(
                phrase,
                cleaned,
                count=count,
                description=description,
                provenance=provenance,
            )
        ):
            continue
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        if not description:
            description = f"Mentioned {count} times in chapter {chapter_number}." if chapter_number else f"Mentioned {count} times."
        confidence = _candidate_confidence(phrase, description, count=count, element_type=element_type, narrative_mode=narrative_mode)
        candidates.append(
            {
                "name": phrase,
                "element_type": element_type,
                "description": description,
                "chapter_number": chapter_number,
                "usage_count": count,
                "canonical_name": phrase,
                "aliases": [],
                "confidence": confidence,
                "provenance": provenance or {
                    "sentence_index": _sentence_index(cleaned, description),
                    "sentence_start": 0,
                    "sentence_end": len(description),
                    "match_start": 0,
                    "match_end": len(phrase),
                    "excerpt": description,
                    "narrative_mode": narrative_mode,
                },
                "claims": _extract_claims(phrase, description, element_type),
            }
        )
    return candidates


def _allow_single_mention_chapter_candidate(
    phrase: str,
    description: str,
    *,
    element_type: str,
    narrative_mode: str,
) -> bool:
    if narrative_mode == "dialogue":
        return False

    normalized_words = normalize_entity_name(phrase).split()
    if len(normalized_words) >= 2:
        return True
    if element_type in {"place", "country", "region", "organization", "religion", "event", "object", "magic_system", "character"}:
        return True
    return bool(_extract_claims(phrase, description, element_type))


def is_valid_world_element_candidate(
    phrase: str,
    text: str,
    *,
    count: int = 1,
    description: str = "",
    provenance: dict | None = None,
) -> bool:
    normalized = normalize_entity_name(phrase)
    if not normalized:
        return False

    words = normalized.split()
    if not words:
        return False
    if normalized in SECTION_LABEL_TYPES:
        return False
    if any(word in WORLD_ELEMENT_BLOCKLIST for word in words):
        return False
    if len(words) > 1 and words[-1] in SECTION_BOUNDARY_WORDS:
        return False
    if len(words) == 1 and words[0] in COMMON_NON_NAME_WORDS:
        return False

    description_lower = description.lower()
    if len(words) == 1 and count == 1 and any(hint in description_lower for hint in WORLD_META_HINTS):
        return False
    if len(words) == 1 and words[0] in {"this", "that", "these", "they", "there", "then", "well", "what", "come"}:
        return False
    if len(words) == 1 and words[0] in {"crime", "punishment"} and "crime and punishment" in description_lower:
        return False
    if len(words) == 1 and _looks_like_non_entity_usage(phrase, description, provenance=provenance):
        return False

    return True


def _preprocess_world_text(text: str) -> str:
    kept_lines: list[str] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line or _is_structural_line(line):
            continue
        kept_lines.append(line)
    cleaned = " ".join(kept_lines)
    cleaned = re.sub(r"[—-]\s*\d+\s*[—-]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_labeled_world_candidates(text: str, *, chapter_number: int | None) -> list[dict]:
    candidates: list[dict] = []
    current_type: str | None = None
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line_start = offset
        offset += len(raw_line)
        line = raw_line.strip()
        if not line:
            current_type = None
            continue

        cleaned_line = _strip_world_note_marker(line)
        if not cleaned_line or _is_structural_line(cleaned_line):
            continue

        label_match = re.match(r"^([A-Za-z][A-Za-z\s/&-]{1,40})\s*[:\-]\s*(.+)$", cleaned_line)
        if label_match:
            label = _normalize_section_label(label_match.group(1))
            element_type = SECTION_LABEL_TYPES.get(label)
            if element_type:
                current_type = element_type
                candidates.extend(
                    _candidates_from_labeled_value(
                        label_match.group(2),
                        element_type=element_type,
                        description=cleaned_line,
                        source_text=text,
                        line_start=line_start,
                        chapter_number=chapter_number,
                    )
                )
                continue

        section_type = SECTION_LABEL_TYPES.get(_normalize_section_label(cleaned_line))
        if section_type:
            current_type = section_type
            continue

        if current_type and re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)?[A-Za-z0-9'\"(]", line):
            candidates.extend(
                _candidates_from_labeled_value(
                    cleaned_line,
                    element_type=current_type,
                    description=cleaned_line,
                    source_text=text,
                    line_start=line_start,
                    chapter_number=chapter_number,
                )
            )
    return candidates


def _strip_world_note_marker(line: str) -> str:
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", line.strip())
    cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", cleaned)
    return cleaned.strip()


def _normalize_section_label(label: str) -> str:
    cleaned = re.sub(r"\s+", " ", (label or "").replace("_", " ").strip().lower())
    cleaned = cleaned.strip(" :.-")
    if cleaned.startswith("world "):
        cleaned = cleaned[6:]
    return cleaned


def _candidates_from_labeled_value(
    value: str,
    *,
    element_type: str,
    description: str,
    source_text: str,
    line_start: int,
    chapter_number: int | None,
) -> list[dict]:
    results: list[dict] = []
    for raw_part in re.split(r"[,;|/]+", value):
        name = _name_from_labeled_part(raw_part)
        if not name:
            continue
        occurrence_count = len(re.findall(rf"\b{re.escape(name)}\b", source_text, flags=re.IGNORECASE))
        local_match = re.search(re.escape(name), description, flags=re.IGNORECASE)
        match_start = line_start + (local_match.start() if local_match else 0)
        match_end = match_start + len(name)
        provenance = {
            "sentence_index": None,
            "sentence_start": line_start,
            "sentence_end": line_start + len(description),
            "match_start": match_start,
            "match_end": match_end,
            "excerpt": description,
            "narrative_mode": "worldbuilding_note",
        }
        results.append(
            {
                "name": name,
                "element_type": element_type,
                "description": description,
                "chapter_number": chapter_number,
                "usage_count": max(1, occurrence_count),
                "canonical_name": name,
                "aliases": [],
                "confidence": _labeled_candidate_confidence(name, element_type, description),
                "provenance": provenance,
                "claims": _extract_claims(name, description, element_type),
            }
        )
    return results


def _name_from_labeled_part(value: str) -> str | None:
    cleaned = " ".join((value or "").split()).strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", cleaned)
    cleaned = cleaned.strip(" \"'`[]")
    cleaned = re.sub(r"\([^)]*\)", "", cleaned).strip()
    cleaned = re.split(
        r"\s+(?:is|are|was|were|uses|use|draws|draw|converts|convert|governs|govern|controls|control|comes|come|lives|live|known|ruled|located)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    cleaned = re.split(r"\s[:\-]\s", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.strip(" .,:;")
    if not cleaned:
        return None

    title_match = re.match(r"^(?:the\s+)?[A-Z][A-Za-z0-9'-]*(?:\s+[A-Z][A-Za-z0-9'-]*){0,5}", cleaned)
    if title_match:
        cleaned = title_match.group(0).strip()
    elif re.fullmatch(r"[a-z][a-z0-9'-]*(?:\s+[a-z][a-z0-9'-]*){0,3}", cleaned):
        cleaned = " ".join(part.capitalize() for part in cleaned.split())
    else:
        return None

    normalized = normalize_entity_name(cleaned)
    if not normalized:
        return None
    if len(normalized.split()) > 6:
        return None
    return cleaned


def _labeled_candidate_confidence(name: str, element_type: str, description: str) -> float:
    score = 0.72
    if element_type in {"country", "region", "race", "magic_system"}:
        score += 0.12
    if len(normalize_entity_name(name).split()) >= 2:
        score += 0.04
    if len(description.split()) >= 5:
        score += 0.04
    return min(0.99, round(score, 3))


def _is_structural_line(line: str) -> bool:
    lowered = line.lower()
    if re.fullmatch(r"[—\-–\s\d]+", line):
        return True
    if re.fullmatch(r"(page\s+)?\d+(\s+of\s+\d+)?", lowered):
        return True
    if any(hint in lowered for hint in STRUCTURAL_LINE_HINTS):
        return True
    if line.count("—") >= 3 or line.count("-") >= 6:
        return True
    return False


def _narrative_mode(sentence: str) -> str:
    text = sentence.strip()
    if not text:
        return "unknown"
    quote_count = text.count('"') + text.count("“") + text.count("”")
    if quote_count >= 2:
        return "dialogue"
    if ":" in text and text.split(":", 1)[0].count(" ") <= 3:
        return "quoted_context"
    return "narration"


def _split_sentences_with_offsets(text: str) -> list[dict]:
    spans: list[dict] = []
    for match in re.finditer(r"[^.!?]+[.!?]?(?:\s+|$)", text):
        raw = match.group(0)
        if not raw.strip():
            continue
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        start = match.start() + leading
        end = match.start() + trailing
        excerpt = text[start:end].strip()
        if excerpt:
            spans.append({"start": start, "end": end, "excerpt": excerpt})
    return spans


def _best_provenance(text: str, phrase: str, occurrences: list[dict], sentence_spans: list[dict]) -> dict | None:
    if not phrase or not occurrences:
        return None

    best: dict | None = None
    best_rank = -10**9
    for occurrence in occurrences:
        sentence_index, sentence = _sentence_span_for_offset(occurrence["start"], sentence_spans)
        if sentence is None:
            continue
        narrative_mode = _narrative_mode(str(sentence.get("excerpt") or ""))
        rank = 0
        if narrative_mode == "narration":
            rank += 4
        if not any(hint in str(sentence.get("excerpt") or "").lower() for hint in WORLD_META_HINTS):
            rank += 3
        rank += min(3, len(str(sentence.get("excerpt") or "")) // 40)
        if best is None or rank > best_rank:
            best_rank = rank
            best = {
                "sentence_index": sentence_index,
                "sentence_start": int(sentence["start"]),
                "sentence_end": int(sentence["end"]),
                "match_start": int(occurrence["start"]),
                "match_end": int(occurrence["end"]),
                "excerpt": str(sentence["excerpt"]),
                "narrative_mode": narrative_mode,
            }
    return best


def _sentence_span_for_offset(offset: int, sentence_spans: list[dict]) -> tuple[int | None, dict | None]:
    for idx, sentence in enumerate(sentence_spans):
        if int(sentence["start"]) <= offset < int(sentence["end"]):
            return idx, sentence
    return None, None


def _candidate_confidence(
    phrase: str,
    description: str,
    *,
    count: int,
    element_type: str,
    narrative_mode: str,
) -> float:
    score = 0.35
    words = normalize_entity_name(phrase).split()
    if len(words) >= 2:
        score += 0.18
    if count >= 2:
        score += 0.12
    if person_name_shape_score(phrase) >= 1:
        score += 0.16
    if element_type in {"place", "organization", "event", "object", "character"}:
        score += 0.08
    if narrative_mode == "dialogue":
        score -= 0.12
    if any(hint in description.lower() for hint in WORLD_META_HINTS):
        score -= 0.25
    if len(words) == 1 and words and words[0] in COMMON_NON_NAME_WORDS:
        score -= 0.20
    if len(words) == 1 and _looks_like_non_entity_usage(phrase, description):
        score -= 0.30
    return max(0.05, min(0.99, round(score, 3)))


def _sentence_index(text: str, sentence: str) -> int | None:
    if not sentence:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text)
    lowered = sentence.lower()
    for idx, candidate in enumerate(sentences):
        if candidate.lower() == lowered:
            return idx
    return None


def _extract_claims(phrase: str, description: str, element_type: str) -> list[dict]:
    text = " ".join((description or "").split())
    lowered = text.lower()
    claims: list[dict] = []

    age_match = re.search(r"\b(\d{1,3})\s+years? old\b", lowered)
    if age_match:
        claims.append(_claim("age", age_match.group(1), 0.9, negated=False))

    occupation_match = re.search(
        r"\b(?:is|was|becomes|remains|served as|works as|acts as)\s+(?:(not|never)\s+)?(?:an?|the)\s+([a-z][a-z\s-]{2,40})",
        lowered,
    )
    if occupation_match:
        value = occupation_match.group(2).strip(" .,;:")
        if len(value.split()) <= 6:
            claims.append(_claim("occupation", value, 0.75, negated=bool(occupation_match.group(1)), cue=occupation_match.group(1)))

    relation_match = re.search(
        r"\b(?:(not|never)\s+)?(?:mother|father|sister|brother|wife|husband|friend|stepdaughter|stepson|daughter|son)\b",
        lowered,
    )
    if relation_match:
        relation_value = relation_match.group(0).replace("not ", "").replace("never ", "").strip()
        claims.append(_claim("relation", relation_value, 0.7, negated=bool(relation_match.group(1)), cue=relation_match.group(1)))

    location_match = re.search(
        r"\b(?:in|on|near|at|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",
        text,
    )
    if location_match and element_type in {"character", "place", "organization"}:
        negation = _window_negation(lowered, location_match.start(1))
        claims.append(_claim("location", location_match.group(1), 0.72, negated=bool(negation), cue=negation))

    role_phrase_match = re.search(
        r"\b(?:(not|never)\s+)?(?:a|an)\s+((?:frozen|desert|winter|summer|imperial|police|moral|psychological)\s+[a-z]+)\b",
        lowered,
    )
    if role_phrase_match:
        claims.append(_claim("descriptor", role_phrase_match.group(2), 0.68, negated=bool(role_phrase_match.group(1)), cue=role_phrase_match.group(1)))

    climate_match = re.search(r"\b(frozen|ice|icy|winter|snow|desert|arid|heat|hot|humid|rain|marsh)\b", lowered)
    if climate_match:
        negation = _window_negation(lowered, climate_match.start(1))
        claims.append(_claim("climate", climate_match.group(1), 0.7, negated=bool(negation), cue=negation))

    return claims


def _sentence_snippet(text: str, phrase: str) -> str | None:
    normalized_phrase = phrase.strip()
    if not normalized_phrase:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        if normalized_phrase.lower() in sentence.lower():
            return sentence.strip()
    return None


def _claim(attribute: str, value: str, confidence: float, *, negated: bool, cue: str | None = None) -> dict:
    payload = {
        "attribute": attribute,
        "value": " ".join((value or "").split()).strip(),
        "confidence": confidence,
        "negated": bool(negated),
    }
    cleaned_cue = " ".join((cue or "").split()).strip()
    if cleaned_cue:
        payload["cue"] = cleaned_cue
    return payload


def _window_negation(text: str, value_start: int) -> str | None:
    window = text[max(0, value_start - 24):value_start]
    for term in ("not", "never", "without", "no"):
        if re.search(rf"\b{term}\b", window):
            return term
    return None


@functools.lru_cache(maxsize=1)
def _get_pos_nlp():
    global _pos_nlp, _pos_nlp_loaded
    if _pos_nlp_loaded:
        return _pos_nlp
    try:
        import spacy

        _pos_nlp = spacy.load("en_core_web_sm", exclude=["ner"])
    except Exception:
        _pos_nlp = None
    _pos_nlp_loaded = True
    return _pos_nlp


def _looks_like_non_entity_usage(phrase: str, description: str, *, provenance: dict | None = None) -> bool:
    normalized = normalize_entity_name(phrase)
    if not normalized:
        return True
    words = normalized.split()
    if len(words) != 1:
        return False

    token = words[0]
    if token in WORLD_ELEMENT_BLOCKLIST or token in COMMON_NON_NAME_WORDS or token in NEGATION_TERMS:
        return True
    if token in COMMON_VERB_LEMMAS:
        return True

    excerpt = " ".join((description or "").split()).strip()
    if not excerpt:
        return False
    lowered_excerpt = excerpt.lower()
    if lowered_excerpt.startswith(f"{token} ") and len(excerpt.split()) > 1:
        next_token = excerpt.split()[1].strip(".,;:!?").lower()
        if next_token and next_token not in PLACE_SUFFIXES and token in COMMON_VERB_LEMMAS:
            return True

    pos_label = _context_pos_label(phrase, excerpt, provenance=provenance)
    if pos_label in NON_ENTITY_POS_TAGS:
        return True
    return False


def _context_pos_label(phrase: str, excerpt: str, *, provenance: dict | None = None) -> str | None:
    nlp = _get_pos_nlp()
    if nlp is None or not excerpt:
        return None
    try:
        doc = nlp(excerpt)
    except Exception:
        return None

    phrase_lower = phrase.lower()
    match_start = None
    match_end = None
    if provenance:
        sentence_start = int(provenance.get("sentence_start") or 0)
        if provenance.get("match_start") is not None and provenance.get("match_end") is not None:
            match_start = int(provenance["match_start"]) - sentence_start
            match_end = int(provenance["match_end"]) - sentence_start

    if match_start is not None and match_end is not None:
        for token in doc:
            if token.idx == match_start and token.idx + len(token.text) == match_end:
                return token.pos_
        span = doc.char_span(match_start, match_end)
        if span and len(span) == 1:
            return span[0].pos_

    for token in doc:
        if token.text.lower() == phrase_lower:
            return token.pos_
    return None
