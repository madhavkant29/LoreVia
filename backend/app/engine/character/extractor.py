"""
LLM character + relationship extraction with confidence-weighted traits.
Single LLM pass extracts both — cheaper and gives shared context.
"""
import json
import re
from collections import Counter

from app.core.config import settings
from app.core.llm import complete_with_fallback
from app.engine.character.entity_filters import looks_like_person_entity_name, person_name_shape_score

CHARACTER_SYSTEM = """You are a careful literary extraction engine.

Extract named characters actually present in the passage and relationships that are explicit or strongly implied.
Prefer precision, but do not miss clearly named people who appear in the passage. If a named person is present but lightly described, still include them with minimal fields.
Do not invent people, aliases, or relationships.
If a capitalized phrase is a place, institution, magic system, event, title fragment, or sentence starter instead of a person, exclude it.

TRAIT CONFIDENCE RULES:
- Explicit direct description → 0.85–1.0
- Implied/inferred → 0.5–0.7
- Narrator self-opinion ("plain", "ugly") → cap at 0.35, type="subjective"
- Single mention → max 0.6; repeated → boost toward 1.0

Return ONLY valid JSON, no markdown, no commentary:
{
  "characters": [
    {
      "name": "primary name",
      "aliases": ["other names"],
      "traits": {
        "hair":   {"value": "...", "confidence": 0.0, "type": "objective|subjective|abstract"},
        "eyes":   {"value": "...", "confidence": 0.0, "type": "..."},
        "build":  {"value": "...", "confidence": 0.0, "type": "..."},
        "age":    {"value": "teen|young adult|adult|middle-aged|elderly", "confidence": 0.0, "type": "..."},
        "face":   {"value": "...", "confidence": 0.0, "type": "..."},
        "distinguishing": {"value": "...", "confidence": 0.0, "type": "..."}
      },
      "personality_tags": ["max 3"],
      "motivations": ["what drives them"],
      "fears": ["what they fear"],
      "archetype": "japanese high school boy|mentor|trickster|villain|hero|etc",
      "first_appearance_context": "1 sentence"
    }
  ],
  "relationships": [
    {
      "character_a": "name",
      "character_b": "name",
      "type": "ally|enemy|romantic|family|political|mentor|rival|neutral",
      "sentiment": 0.0,
      "description": "one sentence"
    }
  ]
}

If nothing found, return {"characters": [], "relationships": []}.
Omit null trait fields entirely.
Return raw JSON only."""


async def extract_characters_and_relationships(chunk_text: str) -> dict:
    candidate_names = _candidate_names(chunk_text)
    candidate_hint = (
        "\n\nPotential person names seen in this passage:\n- "
        + "\n- ".join(candidate_names[:24])
        + "\nUse them only if they are actually people in the passage."
        if candidate_names else ""
    )
    raw = await complete_with_fallback(
        system=CHARACTER_SYSTEM,
        user=f"{chunk_text[:12000]}{candidate_hint}",
        openai_model=settings.OPENAI_EXTRACT_MODEL,
        gemini_model=settings.GEMINI_EXTRACT_MODEL,
        temperature=0.1,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(raw)
        characters = _clean_character_entries(parsed.get("characters", []), candidate_names, chunk_text)
        relationships = parsed.get("relationships", [])
        characters = _augment_with_named_mentions(chunk_text, characters, candidate_names)
        return {
            "characters": characters,
            "relationships": relationships,
        }
    except json.JSONDecodeError:
        return {"characters": _augment_with_named_mentions(chunk_text, [], candidate_names), "relationships": []}


HONORIFIC_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Lady|Lord|Sir)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")
FULL_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:[-'][A-Za-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Za-z]+)?){1,2}\b")
PARTICLE_NAME_RE = re.compile(r"\b(?:[Ll]e|[Ll]a|[Ll]es|[Dd]e|[Dd]u|[Dd]es|[Vv]an|[Vv]on)\s+[A-Z][a-z]+(?:[-'][A-Za-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Za-z]+)?){0,2}\b")
SINGLE_NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
NAME_STOPWORDS = {
    "Chapter", "Prologue", "Epilogue", "Interlude", "Afterword", "Appendix", "Volume", "Part",
    "Section", "Scene", "Page", "Book", "Story", "Note",
    "The", "This", "That", "These", "Those",
    # Common sentence-start words that are frequent false positives
    "From", "When", "Then", "Now", "Once", "After", "Before", "Because", "While", "Until",
}
CHARACTER_CONTEXT_HINTS = {
    "said", "asked", "replied", "called", "told", "whispered", "shouted", "muttered",
    "brother", "sister", "father", "mother", "uncle",
    "aunt", "teacher", "professor", "doctor", "captain", "lord", "lady", "sir", "mr",
    "mrs", "ms", "miss", "dr",
}
SINGLE_NAME_NON_PERSON_SUFFIXES = ("ing", "edly", "edly", "ness")
SINGLE_NAME_NON_PERSON_EXACT = {
    "Compiled", "Translated", "Illustrations", "Formatted",
}
ACTION_VERB_CONTEXT = {
    "said", "asked", "replied", "called", "told", "whispered", "shouted", "muttered",
    "smiled", "laughed", "sighed", "nodded", "stared", "looked", "turned", "answered",
    "cried", "screamed", "warned", "snapped", "grinned",
}
ENTITY_NON_PERSON_TOKENS = {
    "association", "convention", "crest", "energy", "fundamentals", "magecraft", "ritual",
    "spirit", "tower", "towers", "department", "academy", "school", "city", "country",
    "kingdom", "republic", "empire", "nation", "university", "agency", "office",
}


def _augment_with_named_mentions(chunk_text: str, characters: list[dict], candidates: list[str] | None = None) -> list[dict]:
    existing_names = {_normalize_name(item.get("name")) for item in characters if item.get("name")}
    existing_aliases = {
        _normalize_name(alias)
        for item in characters
        for alias in (item.get("aliases") or [])
        if alias
    }
    known = {name for name in existing_names | existing_aliases if name}

    for candidate in candidates or _candidate_names(chunk_text):
        normalized = _normalize_name(candidate)
        if not normalized or normalized in known:
            continue
        characters.append(
            {
                "name": candidate,
                "aliases": [],
                "traits": {},
                "personality_tags": [],
                "motivations": [],
                "fears": [],
                "archetype": None,
                "first_appearance_context": "Named in the passage but not yet richly described.",
            }
        )
        known.add(normalized)
    return characters


def _candidate_names(text: str) -> list[str]:
    candidates: list[str] = []
    candidates.extend(HONORIFIC_RE.findall(text))
    candidates.extend(FULL_NAME_RE.findall(text))
    candidates.extend(PARTICLE_NAME_RE.findall(text))

    singles = [
        token
        for token in SINGLE_NAME_RE.findall(text)
        if token not in NAME_STOPWORDS and token.lower() not in {"the", "this", "that"}
    ]
    single_counts = Counter(singles)
    candidates.extend(
        name
        for name, count in single_counts.items()
        if _has_character_context(text, name) or count >= 3
    )

    deduped: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        cleaned = " ".join(name.split()).strip(" .,:;!?\"'")
        normalized = _normalize_name(cleaned)
        if not cleaned or not normalized or normalized in seen:
            continue
        if not _looks_like_character_name(cleaned, text):
            continue
        seen.add(normalized)
        deduped.append(cleaned)
    return deduped


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    # Remove special characters including Unicode symbols like \u2726 (black diamond) and \u2318 (place of interest)
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    cleaned = re.sub(r"[\u2726\u2318\u2600-\u26FF\u2700-\u27BF]", "", cleaned)  # Remove misc symbols and dingbats
    return re.sub(r"\s+", " ", cleaned).strip()


def _looks_like_character_name(name: str, source_text: str) -> bool:
    cleaned = " ".join(name.split()).strip(" .,:;!?\"'")
    if not cleaned:
        return False
    if cleaned.endswith("'s"):
        return False
    if not looks_like_person_entity_name(cleaned):
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", cleaned)
    if not words:
        return False
    if len(words) == 1 and _looks_like_sentence_fragment(words[0]):
        return False
    if len(words) == 1 and (words[0] in NAME_STOPWORDS or len(words[0]) <= 3):
        return False
    if any(word in NAME_STOPWORDS for word in words):
        return False
    if any(word.casefold() in ENTITY_NON_PERSON_TOKENS for word in words):
        return False
    return _has_name_support(source_text, cleaned)


def _clean_character_entries(characters: list[dict], candidate_names: list[str], source_text: str) -> list[dict]:
    cleaned: list[dict] = []
    seen: set[str] = set()
    candidate_norms = {_normalize_name(name) for name in candidate_names}

    for item in characters:
        if not isinstance(item, dict):
            continue
        raw_name = " ".join(str(item.get("name") or "").split()).strip(" .,:;!?\"'")
        normalized = _normalize_name(raw_name)
        if not raw_name or not normalized:
            continue
        if normalized in seen:
            continue
        if normalized not in candidate_norms and not _looks_like_character_name(raw_name, source_text):
            continue
        if normalized in candidate_norms and person_name_shape_score(raw_name) < 1 and not _looks_like_character_name(raw_name, source_text):
            continue

        aliases = []
        for alias in item.get("aliases") or []:
            cleaned_alias = " ".join(str(alias or "").split()).strip(" .,:;!?\"'")
            alias_norm = _normalize_name(cleaned_alias)
            if (
                cleaned_alias
                and alias_norm
                and alias_norm != normalized
                and _looks_like_character_name(cleaned_alias, source_text)
            ):
                aliases.append(cleaned_alias)

        cleaned.append({
            **item,
            "name": raw_name,
            "aliases": list(dict.fromkeys(aliases)),
        })
        seen.add(normalized)

    return cleaned


def _has_character_context(text: str, name: str) -> bool:
    if _looks_like_sentence_fragment(name):
        return False

    escaped = re.escape(name)
    context_patterns = [
        rf"\b{escaped}\b\s+(?:said|asked|replied|called|told|whispered|shouted|muttered)\b",
        rf"\b(?:said|asked|replied|called|told|whispered|shouted|muttered)\s+\b{escaped}\b",
        rf"\b(?:mr|mrs|ms|miss|dr|lord|lady|sir|professor|captain)\.?\s+{escaped}\b",
        rf"\b{escaped}'s\b",
        rf"\b{escaped}\b\s+(?:brother|sister|father|mother|uncle|aunt|teacher|doctor|captain)\b",
        rf"\b(?:brother|sister|father|mother|uncle|aunt|teacher|doctor|captain)\s+{escaped}\b",
    ]
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in context_patterns)


def _has_name_support(text: str, name: str) -> bool:
    mentions = _find_name_mentions(text, name)
    if not mentions:
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    multi_word = len(words) >= 2
    strong_mentions = 0
    non_sentence_start_mentions = 0

    for start, end in mentions:
        context_before = text[max(0, start - 48):start]
        context_after = text[end:min(len(text), end + 48)]
        if not _mention_is_sentence_start(text, start):
            non_sentence_start_mentions += 1
        if _mention_has_person_context(context_before, context_after):
            strong_mentions += 1

    if multi_word:
        if person_name_shape_score(name) >= 3:
            return strong_mentions >= 1 or non_sentence_start_mentions >= 1 or len(mentions) >= 2
        return strong_mentions >= 1 or len(mentions) >= 2

    # Single-token names are the noisiest failure mode (random capitalized words).
    # Require at least one "person-context" mention (said/asked, honorific, possessive, etc),
    # OR a higher bar of repeated mid-sentence usage.
    return strong_mentions >= 1 or (len(mentions) >= 4 and non_sentence_start_mentions >= 3)


def _find_name_mentions(text: str, name: str) -> list[tuple[int, int]]:
    pattern = re.compile(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])")
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def _mention_is_sentence_start(text: str, start: int) -> bool:
    prefix = text[:start].rstrip()
    if not prefix:
        return True
    return prefix[-1] in ".!?\n\"'"


def _mention_has_person_context(before: str, after: str) -> bool:
    before_words = re.findall(r"[A-Za-z']+", before.casefold())
    after_words = re.findall(r"[A-Za-z']+", after.casefold())
    before_tail = before_words[-3:]
    after_head = after_words[:4]
    return (
        any(word in CHARACTER_CONTEXT_HINTS for word in before_tail + after_head)
        or any(word in ACTION_VERB_CONTEXT for word in before_tail + after_head)
        or "'" in after[:2]
        or bool(re.match(r"^[, ]+(said|asked|replied|called|told|smiled|laughed|sighed)\b", after.casefold()))
    )


def _looks_like_sentence_fragment(word: str) -> bool:
    lowered = word.casefold()
    if word in SINGLE_NAME_NON_PERSON_EXACT:
        return True
    if lowered.endswith("ly"):
        return True
    if lowered.endswith("ing") and len(word) > 5:
        return True
    if lowered.endswith("ed") and len(word) > 5:
        return True
    if lowered.endswith("tion") and len(word) > 6:
        return True
    if any(lowered.endswith(suffix) for suffix in SINGLE_NAME_NON_PERSON_SUFFIXES):
        return True
    return False
