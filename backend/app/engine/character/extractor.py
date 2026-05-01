"""
LLM character + relationship extraction with confidence-weighted traits.
Single LLM pass extracts both — cheaper and gives shared context.
"""
import json
import logging
import re
from collections import Counter
from typing import cast

from app.core.config import settings
from app.core.llm import complete_with_fallback
from app.engine.character.entity_filters import (
    looks_like_person_entity_name,
    person_name_shape_score,
)

log = logging.getLogger("lorevia.character.extractor")

CHARACTER_SYSTEM = """You are a careful literary extraction engine.

Extract named characters actually present in the passage and relationships that are explicit or strongly implied.
Prefer precision, but do not miss clearly named people who appear in the passage. If a named person is present but lightly described, still include them with minimal fields.
Do not invent people, aliases, or relationships.
If a capitalized phrase is a place, institution, magic system, event, title fragment, sentence starter, object, concept, or group instead of a person, exclude it.

STRICT REJECTION RULES:
- Reject locations, islands, schools, organizations, syndicates, conglomerates, concepts, techniques, objects, and sentence fragments.
- Reject names with leading sentence words that are not part of the actual name, such as "Since Hime-nee" or "With Onii-chan".
- Reject common one-word discourse markers or random nouns like "Well", "Right", "Even", "Yeah", or "Stairs".
- Reject title-only references unless they clearly point to a recurring individual in this passage.
- Treat honorific variants as the same person whenever the base name matches.
- Never return a cleaned or canonical name unless it is directly supported by the passage text.

CHARACTER TYPE SUGGESTION:
For each character, suggest their main type based on this passage:
- "complex": Has depth, growth, internal conflict, or significant narrative role
- "normal": Standard character with some traits but limited depth
- "gag": Comic relief, used primarily for humor or jokes
- "meme": Meta-commentary, fourth-wall breaking, or reference-based

This is a suggestion based on this passage only - the final classification will be computed from full character data.

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
      "canonical_name": "best canonical name from the passage or null",
      "aliases": ["other names"],
      "entity_type": "person|alias|organization|location|object|concept|title|unknown",
      "is_character": true,
      "confidence": 0.0,
      "suggested_type": "complex|normal|gag|meme",
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
      "arc_summary": "short natural summary of where this character seems to be emotionally or morally",
      "archetype": "japanese high school boy|mentor|trickster|villain|hero|etc",
      "first_appearance_context": "1 sentence",
      "rejection_reason": null,
      "growth_event": {
        "chapter": 0,
        "event": "specific event that shaped the character here",
        "impact": "how it changes or deepens them",
        "tone": "wounded|defiant|hopeful|corrupting|clarifying|etc"
      }
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
        characters = _apply_anti_merge_hints(chunk_text, characters)
        return {
            "characters": characters,
            "relationships": relationships,
        }
    except json.JSONDecodeError:
        characters = _augment_with_named_mentions(chunk_text, [], candidate_names)
        return {"characters": _apply_anti_merge_hints(chunk_text, characters), "relationships": []}


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
SINGLE_NAME_DISCOURSE_MARKERS = {
    "Again", "Also", "Although", "Because", "Before", "Finally", "First",
    "However", "Meanwhile", "Moreover", "Next", "Now", "Otherwise", "Since",
    "Suddenly", "Then", "Therefore", "Though", "Thus", "When", "While", "Yet",
}
SINGLE_NAME_TIME_WORDS = {
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
}
ACTION_VERB_CONTEXT = {
    "said", "asked", "replied", "called", "told", "whispered", "shouted", "muttered",
    "smiled", "laughed", "sighed", "nodded", "stared", "looked", "turned", "answered",
    "cried", "screamed", "warned", "snapped", "grinned",
}
MAX_AUTO_AUGMENTED_CHARACTERS = 10
MIN_CHARACTER_CONFIDENCE = 0.78
MIN_BORDERLINE_CONFIDENCE = 0.55
SAVE_SINGLE_MENTION_CONFIDENCE = 0.90
FRAGMENT_PREFIXES = (
    "about", "after", "before", "because", "but", "even", "following", "if", "just",
    "meeting", "nodded", "right", "seeing", "since", "then", "what", "when", "where", "with",
)
TITLE_ONLY_WORDS = {
    "doctor", "professor", "master", "assassin", "killer", "protagonist", "antagonist",
    "contractor", "creator", "teacher", "nurse", "mentor", "sister", "brother",
}
TITLE_PREFIXES = (
    "assistant professor",
    "professor",
    "doctor",
    "mr",
    "mrs",
    "ms",
    "miss",
    "sir",
    "lady",
    "lord",
)
GENERIC_PROFILE_PHRASES = {
    "appearance not yet described",
    "mysterious figure",
    "tragic figure",
    "normal character",
    "supporting character",
    "protagonist",
    "antagonist",
    "puppet master",
}
NON_CHARACTER_EXACT = {
    "back nozzle", "even", "feather island", "grim reaper", "imaginary weapon", "just",
    "kendo", "mad demon", "ordinary world", "right", "space creator", "stairs",
    "strongest contractor", "thirteen", "wet crow", "well", "yeah",
}
NON_CHARACTER_TOKENS = {
    "academy", "agency", "association", "conglomerate", "contractor", "corporation", "creator",
    "department", "island", "kingdom", "mansion", "object", "room", "school", "space",
    "stairs", "syndicate", "technique", "university", "weapon", "world",
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

    promoted = 0
    for candidate in candidates or _candidate_names(chunk_text):
        normalized = _normalize_name(candidate)
        if not normalized or normalized in known:
            continue
        if not _allow_auto_augmentation(chunk_text, candidate):
            continue
        characters.append(
            {
                "name": candidate,
                "canonical_name": candidate,
                "aliases": [],
                "entity_type": "person",
                "is_character": True,
                "confidence": MIN_CHARACTER_CONFIDENCE,
                "traits": {},
                "personality_tags": [],
                "motivations": [],
                "fears": [],
                "arc_summary": None,
                "archetype": None,
                "first_appearance_context": "Named in the passage but not yet richly described.",
                "rejection_reason": None,
                "growth_event": None,
            }
        )
        known.add(normalized)
        promoted += 1
        if promoted >= MAX_AUTO_AUGMENTED_CHARACTERS:
            break
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
        if _has_character_context(text, name) or count >= 4
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


def _clean_name_fragment(name: str) -> str:
    parts = name.strip().split()
    while parts and parts[0].casefold() in FRAGMENT_PREFIXES:
        parts.pop(0)
    return " ".join(parts).strip(" .,:;!?\"'")


def _split_titled_name(name: str) -> tuple[str, str | None]:
    lowered = name.casefold()
    for prefix in TITLE_PREFIXES:
        token = f"{prefix} "
        if lowered.startswith(token):
            remainder = name[len(token):].strip()
            if remainder:
                return remainder, name
    return name, None


def _contains_supported_subspan(raw_name: str, cleaned_name: str, source_text: str) -> bool:
    if not raw_name or not cleaned_name:
        return False
    if _find_name_mentions(source_text, raw_name):
        return True
    if cleaned_name != raw_name and cleaned_name in raw_name and _find_name_mentions(source_text, cleaned_name):
        return True
    return False


def _is_title_only_name(name: str) -> bool:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]*", name)]
    return bool(tokens) and all(token in TITLE_ONLY_WORDS for token in tokens)


def _reject_obvious_bad_name(name: str) -> str | None:
    normalized = _normalize_name(name)
    if not normalized:
        return "empty_name"
    if normalized in NON_CHARACTER_EXACT:
        return "known_non_character_phrase"

    tokens = normalized.split()
    if len(tokens) <= 1 and len(normalized) <= 2:
        return "name_too_short"
    if tokens and tokens[0] in FRAGMENT_PREFIXES:
        return "sentence_fragment_prefix"
    if any(token in NON_CHARACTER_TOKENS or token in ENTITY_NON_PERSON_TOKENS for token in tokens):
        return "non_person_token"
    if _is_title_only_name(name):
        return "title_only_reference"
    return None


def _sanitize_summary(value: object) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    if cleaned.casefold() in GENERIC_PROFILE_PHRASES:
        return None
    return cleaned


def _mention_support_score(source_text: str, name: str) -> tuple[int, int]:
    mentions = _find_name_mentions(source_text, name)
    strong_mentions = 0
    for start, end in mentions:
        context_before = source_text[max(0, start - 48):start]
        context_after = source_text[end:min(len(source_text), end + 48)]
        if _mention_has_person_context(context_before, context_after):
            strong_mentions += 1
    return len(mentions), strong_mentions


def _build_evidence(source_text: str, name: str, traits: dict, aliases: list[str]) -> dict:
    mention_count, strong_mentions = _mention_support_score(source_text, name)
    alias_mentions = 0
    for alias in aliases:
        alias_count, alias_strong = _mention_support_score(source_text, alias)
        alias_mentions += alias_count
        strong_mentions += alias_strong
    total_mentions = mention_count + alias_mentions
    has_description = any(isinstance(value, dict) and value.get("value") for value in traits.values())
    return {
        "mention_count": total_mentions,
        "strong_mention_count": strong_mentions,
        "has_dialogue_or_action": strong_mentions >= 1,
        "has_physical_description": has_description,
        "appears_multiple_times": total_mentions >= 2,
    }


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part and part.strip()]


def _apply_anti_merge_hints(source_text: str, characters: list[dict]) -> list[dict]:
    if len(characters) < 2:
        return characters

    sentence_blocks = _split_sentences(source_text)
    if not sentence_blocks:
        return characters

    for index, character in enumerate(characters):
        names = [character.get("name"), *(character.get("aliases") or [])]
        blocked: set[str] = set()
        for sentence in sentence_blocks:
            if not any(candidate and _find_name_mentions(sentence, candidate) for candidate in names):
                continue
            for other_index, other in enumerate(characters):
                if other_index == index:
                    continue
                other_names = [other.get("name"), *(other.get("aliases") or [])]
                if any(candidate and _find_name_mentions(sentence, candidate) for candidate in other_names):
                    if other.get("name"):
                        blocked.add(str(other["name"]))
        character["anti_merge_names"] = sorted(blocked)
    return characters


def _should_keep_character(name: str, confidence: float, source_text: str, traits: dict, arc_summary: str | None) -> bool:
    mentions, strong_mentions = _mention_support_score(source_text, name)
    if confidence < MIN_BORDERLINE_CONFIDENCE:
        return False
    if confidence >= MIN_CHARACTER_CONFIDENCE:
        return True
    if mentions >= 2 and strong_mentions >= 1:
        return True
    if confidence >= SAVE_SINGLE_MENTION_CONFIDENCE and (traits or arc_summary):
        return True
    return False


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
    if len(words) == 1 and (words[0] in SINGLE_NAME_DISCOURSE_MARKERS or words[0] in SINGLE_NAME_TIME_WORDS):
        return False
    if len(words) == 1 and words[0].isupper() and len(words[0]) > 1:
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
        cleaned_name = _clean_name_fragment(raw_name)
        normalized = _normalize_name(cleaned_name)
        if not raw_name or not cleaned_name or not normalized:
            continue
        if normalized in seen:
            continue

        if not _contains_supported_subspan(raw_name, cleaned_name, source_text):
            continue

        entity_type = str(item.get("entity_type") or "").strip().casefold() or "person"
        is_character = bool(item.get("is_character", True))
        confidence = float(item.get("confidence") or 0.0)
        if entity_type not in {"person", "alias", "unknown"} or not is_character:
            continue

        rejection_reason = _reject_obvious_bad_name(cleaned_name)
        if rejection_reason:
            log.info("Rejected extracted character '%s': %s", raw_name, rejection_reason)
            continue

        if normalized not in candidate_norms and not _looks_like_character_name(cleaned_name, source_text):
            continue
        if normalized in candidate_norms and person_name_shape_score(cleaned_name) < 1 and not _looks_like_character_name(cleaned_name, source_text):
            continue

        traits = cast(dict[str, object], item.get("traits") if isinstance(item.get("traits"), dict) else {})
        arc_summary = _sanitize_summary(item.get("arc_summary"))
        if not _should_keep_character(cleaned_name, confidence, source_text, traits, arc_summary):
            continue

        aliases = []
        for alias in item.get("aliases") or []:
            raw_alias = " ".join(str(alias or "").split()).strip(" .,:;!?\"'")
            cleaned_alias = _clean_name_fragment(raw_alias)
            alias_norm = _normalize_name(cleaned_alias)
            if (
                cleaned_alias
                and alias_norm
                and alias_norm != normalized
                and _contains_supported_subspan(raw_alias, cleaned_alias, source_text)
                and not _reject_obvious_bad_name(cleaned_alias)
                and _looks_like_character_name(cleaned_alias, source_text)
            ):
                aliases.append(cleaned_alias)

        cleaned_name, titled_alias = _split_titled_name(cleaned_name)
        normalized = _normalize_name(cleaned_name)
        if titled_alias and titled_alias != cleaned_name:
            aliases.append(titled_alias)

        canonical_name = _clean_name_fragment(" ".join(str(item.get("canonical_name") or "").split()).strip(" .,:;!?\"'"))
        if canonical_name and canonical_name != cleaned_name:
            if _contains_supported_subspan(raw_name, canonical_name, source_text) and _looks_like_character_name(canonical_name, source_text):
                aliases.append(cleaned_name)
                cleaned_name = canonical_name
                normalized = _normalize_name(cleaned_name)
            else:
                canonical_name = ""

        evidence = _build_evidence(source_text, cleaned_name, traits, aliases)

        cleaned.append({
            **item,
            "name": cleaned_name,
            "canonical_name": cleaned_name,
            "aliases": list(dict.fromkeys(aliases)),
            "entity_type": "person" if entity_type == "unknown" else entity_type,
            "confidence": confidence,
            "arc_summary": arc_summary,
            "archetype": _sanitize_summary(item.get("archetype")),
            "mention_count": evidence["mention_count"],
            "evidence": evidence,
            "rejection_reason": None,
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
    # Require stronger support: either repeated person-context mentions, or
    # repeated mid-sentence usage with at least one person-context hit.
    if strong_mentions >= 2:
        return True
    if strong_mentions >= 1 and (non_sentence_start_mentions >= 1 or len(mentions) >= 3):
        return True
    return len(mentions) >= 6 and non_sentence_start_mentions >= 4


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


def _allow_auto_augmentation(text: str, name: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    if len(words) == 1:
        return False
    mentions = _find_name_mentions(text, name)
    if not mentions:
        return False
    strong_mentions = 0
    non_sentence_start_mentions = 0
    for start, end in mentions:
        context_before = text[max(0, start - 48):start]
        context_after = text[end:min(len(text), end + 48)]
        if not _mention_is_sentence_start(text, start):
            non_sentence_start_mentions += 1
        if _mention_has_person_context(context_before, context_after):
            strong_mentions += 1
    return strong_mentions >= 1 and (non_sentence_start_mentions >= 1 or len(mentions) >= 2)


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
