"""
LLM character + relationship extraction with confidence-weighted traits.
Single LLM pass extracts both — cheaper and gives shared context.
"""
import json
import logging
import re
import uuid
from collections import Counter
from typing import cast

from app.core.config import settings
from app.core.llm import complete_with_fallback
from app.engine.character.entity_filters import (
    COMMON_NON_NAME_WORDS,
    SINGLE_TOKEN_DISCOURSE_WORDS,
    contextual_ner_entity_label,
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
      "goal": "what they are trying to achieve in this passage or larger arc",
      "motivations": ["what drives them"],
      "fears": ["what they fear"],
      "lie_they_believe": "false belief shaping their choices",
      "backstory_wound": "relevant wound or backstory pressure visible here",
      "arc_type": "positive change|negative change|flat|fall|disillusionment|redemption|corruption|etc",
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

MENTION_VERIFIER_SYSTEM = """You verify whether candidate mentions in story passages refer to actual people/characters.

Rules:
- Decide from the passage context, not from capitalization alone.
- Reject interjections, commands, discourse markers, narration fragments, places, groups, organizations, concepts, and objects.
- A candidate can be a person even if lightly described, if the local passage clearly uses it as a person mention.
- If the passage is still ambiguous, return is_person as null.
- Never invent names that are not supported by the supplied mention windows.

Return ONLY valid JSON:
{
  "results": [
    {
      "id": "candidate id",
      "is_person": true,
      "confidence": 0.0,
      "canonical_name_or_null": null,
      "reason": "short reason"
    }
  ]
}
"""


async def extract_characters_and_relationships(
    chunk_text: str,
    *,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
    known_characters: list[dict] | None = None,
) -> dict:
    candidate_names = _candidate_names(chunk_text)
    candidate_hint = (
        "\n\nPotential person names seen in this passage:\n- "
        + "\n- ".join(candidate_names[:24])
        + "\nUse them only if they are actually people in the passage."
        if candidate_names else ""
    )
    roster_hint = _known_character_prompt_block(known_characters)
    raw = await complete_with_fallback(
        system=CHARACTER_SYSTEM,
        user=f"{chunk_text[:12000]}{candidate_hint}{roster_hint}",
        openai_model=settings.OPENAI_EXTRACT_MODEL,
        gemini_model=settings.GEMINI_EXTRACT_MODEL,
        temperature=0.1,
        max_tokens=3000,
        response_format={"type": "json_object"},
        usage_feature="character_relationship_extraction",
        usage_user_id=user_id,
        usage_book_id=book_id,
    )
    try:
        parsed = json.loads(raw)
        rejected_characters: list[dict] = []
        characters = _clean_character_entries(
            parsed.get("characters", []),
            candidate_names,
            chunk_text,
            rejected_characters=rejected_characters,
        )
        relationships = parsed.get("relationships", [])
        characters = _augment_with_named_mentions(
            chunk_text,
            characters,
            candidate_names,
            rejected_characters=rejected_characters,
        )
        characters = await _apply_contextual_mention_verification(
            chunk_text,
            characters,
            rejected_characters=rejected_characters,
            user_id=user_id,
            book_id=book_id,
        )
        characters = _apply_anti_merge_hints(chunk_text, characters)
        return {
            "characters": characters,
            "relationships": relationships,
            "rejected_characters": rejected_characters,
        }
    except json.JSONDecodeError:
        rejected_characters: list[dict] = []
        characters = _augment_with_named_mentions(
            chunk_text,
            [],
            candidate_names,
            rejected_characters=rejected_characters,
        )
        characters = await _apply_contextual_mention_verification(
            chunk_text,
            characters,
            rejected_characters=rejected_characters,
            user_id=user_id,
            book_id=book_id,
        )
        return {
            "characters": _apply_anti_merge_hints(chunk_text, characters),
            "relationships": [],
            "rejected_characters": rejected_characters,
        }


async def fallback_character_mentions(
    chunk_text: str,
    *,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> dict:
    candidate_names = _candidate_names(chunk_text, allow_review_singletons=True)
    rejected_characters: list[dict] = []
    characters = _augment_with_named_mentions(
        chunk_text,
        [],
        candidate_names,
        rejected_characters=rejected_characters,
        allow_review_candidates=True,
    )
    filtered = await _apply_contextual_mention_verification(
        chunk_text,
        characters,
        rejected_characters=rejected_characters,
        user_id=user_id,
        book_id=book_id,
    )
    for character in filtered:
        evidence = dict(character.get("evidence") if isinstance(character.get("evidence"), dict) else {})
        evidence["deterministic_fallback"] = True
        character["evidence"] = evidence
    return {
        "characters": _apply_anti_merge_hints(chunk_text, filtered),
        "relationships": [],
        "rejected_characters": rejected_characters,
    }


def _known_character_prompt_block(known_characters: list[dict] | None) -> str:
    lines: list[str] = []
    for item in known_characters or []:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("name") or "").split()).strip()
        if not name:
            continue
        aliases = [str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip()]
        role = " ".join(str(item.get("role") or "").split()).strip()
        summary = " ".join(str(item.get("summary") or "").split()).strip()
        marker = "manual anchor" if item.get("is_manual") else "known character"
        parts = [f"{name} [{marker}]"]
        if aliases:
            parts.append(f"aliases: {', '.join(aliases[:6])}")
        if role:
            parts.append(f"role: {role}")
        if summary:
            parts.append(f"summary: {summary[:180]}")
        lines.append(" | ".join(parts))
    if not lines:
        return ""
    return (
        "\n\nKnown story roster. Prefer resolving mentions to these existing characters when the passage supports it. "
        "Do not invent canon names beyond the passage.\n- " + "\n- ".join(lines[:24])
    )


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
    "cried", "screamed", "warned", "snapped", "grinned", "awoke", "woke", "watched",
    "walked", "stepped", "moved", "stood", "sat", "rose", "opened", "closed", "reached",
    "grabbed", "held", "took", "came", "went", "ran", "hurried", "followed", "glanced",
    "noticed", "saw", "heard", "felt",
}
MAX_AUTO_AUGMENTED_CHARACTERS = 10
MIN_CHARACTER_CONFIDENCE = 0.78
MIN_BORDERLINE_CONFIDENCE = 0.55
SAVE_SINGLE_MENTION_CONFIDENCE = 0.90
FALLBACK_STRONG_MENTION_CONFIDENCE = 0.92
FRAGMENT_PREFIXES = (
    "about", "after", "before", "because", "but", "even", "following", "if", "just",
    "meeting", "nodded", "right", "seeing", "since", "then", "what", "when", "where", "with",
)
TITLE_ONLY_WORDS = {
    "doctor", "professor", "master", "assassin", "killer", "protagonist", "antagonist",
    "contractor", "creator", "teacher", "nurse", "mentor", "sister", "brother",
    "mother", "father",
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
    "background character",
    "is a character",
    "mysterious figure",
    "plain character",
    "tragic figure",
    "normal character",
    "supporting character",
    "this character is a character",
    "protagonist",
    "antagonist",
    "puppet master",
    "unknown character",
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


def _record_rejected_character(
    rejected_characters: list[dict] | None,
    *,
    stage: str,
    name: str,
    reason: str,
    confidence: float | None = None,
    evidence: dict | None = None,
) -> None:
    if rejected_characters is None:
        return
    rejected_characters.append(
        {
            "name": name,
            "stage": stage,
            "reason": reason,
            "confidence": confidence,
            "evidence": evidence or {},
        }
    )


def _mention_window_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind("\n", 0, start),
    )
    right_candidates = [
        value
        for value in (
            text.find(".", end),
            text.find("!", end),
            text.find("?", end),
            text.find("\n", end),
        )
        if value >= 0
    ]
    right = min(right_candidates) if right_candidates else len(text)
    window_start = max(0, left + 1)
    window_end = len(text) if right == len(text) else right + 1
    return window_start, window_end


def _mention_window(text: str, start: int, end: int) -> str:
    window_start, window_end = _mention_window_bounds(text, start, end)
    window = " ".join(text[window_start:window_end].split()).strip()
    if window:
        return window
    return " ".join(text[max(0, start - 90): min(len(text), end + 90)].split()).strip()


def _looks_like_interjection_clause(after: str) -> bool:
    lowered = after.casefold()
    return bool(
        re.match(r"^[,!?]\s+(?:he|she|they|it|i|we|you|the|a|an)\b", lowered)
        or re.match(r"^[,!?]\s+(?:was|were|is|are|had|has|have)\b", lowered)
        or re.match(r"^[,!?]\s+(?:said|asked|replied|shouted|whispered|muttered)\b", lowered)
    )


def _single_token_starts_like_interjection(name: str, after: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    if len(words) != 1:
        return False
    return _looks_like_interjection_clause(after)


def _single_token_subject_action(after: str) -> bool:
    lowered = after.casefold()
    return bool(
        re.match(
            r"^\s+(?:said|asked|replied|called|told|whispered|shouted|muttered|smiled|laughed|sighed|nodded|stared|looked|turned|answered|cried|screamed|warned|snapped|grinned|awoke|woke|watched|walked|stepped|moved|stood|sat|rose|opened|closed|reached|grabbed|held|took|came|went|ran|hurried|followed|glanced|noticed|saw|heard|felt)\b",
            lowered,
        )
    )


def _clean_verifier_reason(value: object | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def _local_mention_verifier(
    source_text: str,
    name: str,
    *,
    aliases: list[str] | None = None,
    traits: dict | None = None,
    entity_type: str | None = None,
) -> dict:
    targets = [candidate for candidate in [name, *(aliases or [])] if candidate]
    mention_windows: list[dict] = []
    person_context_mentions = 0
    mid_sentence_mentions = 0
    sentence_start_mentions = 0
    person_ner_mentions = 0
    non_person_ner_mentions = 0
    interjection_like_mentions = 0
    subject_action_mentions = 0

    for candidate in targets:
        for start, end in _find_name_mentions(source_text, candidate):
            before = source_text[max(0, start - 48):start]
            after = source_text[end:min(len(source_text), end + 72)]
            window = _mention_window(source_text, start, end)
            is_sentence_start = _mention_is_sentence_start(source_text, start)
            interjection_like = is_sentence_start and _single_token_starts_like_interjection(candidate, after)
            subject_action = is_sentence_start and not interjection_like and _single_token_subject_action(after)
            has_person_context = _mention_has_person_context(before, after) and not interjection_like
            ner_label = contextual_ner_entity_label(window, candidate)
            if has_person_context:
                person_context_mentions += 1
            if is_sentence_start:
                sentence_start_mentions += 1
            else:
                mid_sentence_mentions += 1
            if subject_action:
                subject_action_mentions += 1
            if ner_label == "PERSON":
                person_ner_mentions += 1
            elif ner_label in {"ORG", "GPE", "LOC", "FAC", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE", "NORP"}:
                non_person_ner_mentions += 1
            if interjection_like:
                interjection_like_mentions += 1

            mention_windows.append(
                {
                    "text": window,
                    "has_person_context": has_person_context,
                    "sentence_start": is_sentence_start,
                    "ner_label": ner_label,
                }
            )

    mention_count = len(mention_windows)
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
    normalized = _normalize_name(name)
    has_description = any(isinstance(value, dict) and value.get("value") for value in (traits or {}).values())
    allowed_entity_type = str(entity_type or "person").strip().casefold() in {"person", "alias", "unknown"}
    non_person_tokens = [token for token in normalized.split() if token in NON_CHARACTER_TOKENS or token in ENTITY_NON_PERSON_TOKENS]
    suspicious_single_token = bool(len(words) == 1 and words[0].casefold() in COMMON_NON_NAME_WORDS)
    title_like_single_token = bool(len(words) == 1 and words[0].casefold() in TITLE_ONLY_WORDS)

    reasons: list[str] = []
    positive_signals: list[str] = []
    negative_signals: list[str] = []
    band = "review"
    is_person_like = False

    if not allowed_entity_type:
        reasons.append("entity_type_not_person")
        band = "reject"
    elif not mention_windows:
        reasons.append("no_grounded_mentions")
        band = "reject"
    elif normalized in NON_CHARACTER_EXACT:
        reasons.append("known_non_character_phrase")
        band = "reject"
    elif non_person_tokens and person_context_mentions == 0 and person_ner_mentions == 0:
        reasons.append("context_contains_non_person_tokens")
        band = "reject"
    elif len(words) == 1:
        if person_ner_mentions >= 1:
            positive_signals.append("single_token_grounded_by_person_ner")
            band = "accept"
            is_person_like = True
        elif title_like_single_token and (person_context_mentions >= 1 or subject_action_mentions >= 1 or mention_count >= 1):
            reasons.append("role_title_single_token_requires_review")
        elif subject_action_mentions >= 1 and not suspicious_single_token:
            positive_signals.append("single_token_subject_action_grounding")
            band = "accept"
            is_person_like = True
        elif person_context_mentions >= 2 and (mid_sentence_mentions >= 1 or mention_count >= 2) and not suspicious_single_token:
            positive_signals.append("single_token_grounded_by_context")
            band = "accept"
            is_person_like = True
        elif person_context_mentions >= 1 and (mid_sentence_mentions >= 1 or has_description) and not suspicious_single_token:
            positive_signals.append("single_token_has_mid_sentence_grounding")
            band = "accept"
            is_person_like = True
        elif non_person_ner_mentions >= 1 and person_context_mentions == 0 and person_ner_mentions == 0:
            negative_signals.append("single_token_ner_non_person")
            reasons.append("contextual_ner_non_person")
            band = "reject"
        elif interjection_like_mentions >= 1 and person_context_mentions == 0 and person_ner_mentions == 0:
            negative_signals.append("single_token_interjection_like")
            reasons.append("interjection_like_usage")
            band = "reject"
        elif sentence_start_mentions == mention_count and person_context_mentions == 0 and person_ner_mentions == 0:
            negative_signals.append("single_token_sentence_start_only")
            reasons.append("sentence_start_capitalization_only")
            band = "reject"
        elif suspicious_single_token and person_context_mentions >= 1:
            reasons.append("single_token_common_word_requires_review")
        else:
            reasons.append("ambiguous_single_token_mention")
    else:
        if person_context_mentions >= 1 or person_ner_mentions >= 1:
            positive_signals.append("multi_token_grounded_by_context")
            band = "accept"
            is_person_like = True
        elif mention_count >= 2 and mid_sentence_mentions >= 1:
            positive_signals.append("multi_token_repeated_mid_sentence")
            band = "accept"
            is_person_like = True
        elif non_person_ner_mentions >= 1 and person_context_mentions == 0 and person_ner_mentions == 0:
            negative_signals.append("multi_token_ner_non_person")
            reasons.append("contextual_ner_non_person")
            band = "reject"
        else:
            reasons.append("ambiguous_multi_token_mention")

    if band == "accept" and not is_person_like:
        is_person_like = True
    if band == "reject":
        is_person_like = False

    return {
        "is_person_like": is_person_like,
        "confidence_band": band,
        "reasons": reasons,
        "positive_signals": positive_signals,
        "negative_signals": negative_signals,
        "mention_count": mention_count,
        "person_context_mentions": person_context_mentions,
        "mid_sentence_mentions": mid_sentence_mentions,
        "sentence_start_mentions": sentence_start_mentions,
        "subject_action_mentions": subject_action_mentions,
        "person_ner_mentions": person_ner_mentions,
        "non_person_ner_mentions": non_person_ner_mentions,
        "interjection_like_mentions": interjection_like_mentions,
        "windows": mention_windows[:3],
    }


async def verify_character_candidate_personhood(
    source_text: str,
    name: str,
    *,
    aliases: list[str] | None = None,
    traits: dict | None = None,
    entity_type: str | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> dict:
    local = _local_mention_verifier(
        source_text,
        name,
        aliases=aliases,
        traits=traits,
        entity_type=entity_type,
    )
    if local["confidence_band"] != "review":
        return {
            "local": local,
            "llm": {"used": False, "is_person_like": None, "confidence": None, "canonical_name": None, "reason": None},
            "final": {
                "confidence_band": local["confidence_band"],
                "is_person_like": bool(local["is_person_like"]),
                "reasons": list(local["reasons"]),
            },
        }

    payload = await _verify_review_candidates_with_llm(
        source_text,
        [
            {
                "id": "candidate-0",
                "name": name,
                "aliases": aliases or [],
                "entity_type": entity_type or "person",
                "traits": traits or {},
                "verifier_local": local,
            }
        ],
        user_id=user_id,
        book_id=book_id,
    )
    llm_result = payload.get("candidate-0", {})
    final_band = "review"
    final_is_person_like = False
    final_reasons = list(local["reasons"])
    llm_is_person = llm_result.get("is_person_like")
    llm_confidence = llm_result.get("confidence")
    if llm_is_person is True:
        final_band = "accept"
        final_is_person_like = True
        final_reasons = ["llm_confirmed_person", *final_reasons]
    elif llm_is_person is False and (llm_confidence is None or float(llm_confidence) >= 0.55):
        final_band = "reject"
        final_reasons = ["llm_rejected_person", *final_reasons]
    return {
        "local": local,
        "llm": llm_result,
        "final": {
            "confidence_band": final_band,
            "is_person_like": final_is_person_like,
            "reasons": final_reasons,
        },
    }


async def _verify_review_candidates_with_llm(
    source_text: str,
    candidates: list[dict],
    *,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> dict[str, dict]:
    if not candidates:
        return {}

    request_items = []
    for item in candidates:
        verifier_local = item.get("verifier_local") if isinstance(item.get("verifier_local"), dict) else {}
        request_items.append(
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or "").strip(),
                "entity_type": str(item.get("entity_type") or "person").strip() or "person",
                "aliases": [str(alias).strip() for alias in (item.get("aliases") or []) if str(alias).strip()][:4],
                "local_reasons": [str(reason).strip() for reason in (verifier_local.get("reasons") or []) if str(reason).strip()][:4],
                "windows": [
                    str(window.get("text") or "").strip()
                    for window in (verifier_local.get("windows") or [])
                    if isinstance(window, dict) and str(window.get("text") or "").strip()
                ][:3],
            }
        )

    raw = await complete_with_fallback(
        system=MENTION_VERIFIER_SYSTEM,
        user=json.dumps({"passage": source_text[:4000], "candidates": request_items}, ensure_ascii=True),
        openai_model=settings.OPENAI_EXTRACT_MODEL,
        gemini_model=settings.GEMINI_EXTRACT_MODEL,
        temperature=0.0,
        max_tokens=1200,
        response_format={"type": "json_object"},
        usage_feature="character_mention_verification",
        usage_user_id=user_id,
        usage_book_id=book_id,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    results: dict[str, dict] = {}
    for item in parsed.get("results", []):
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("id") or "").strip()
        if not candidate_id:
            continue
        raw_confidence = item.get("confidence")
        try:
            confidence = float(raw_confidence) if raw_confidence is not None else None
        except (TypeError, ValueError):
            confidence = None
        is_person_raw = item.get("is_person")
        is_person_like = is_person_raw if isinstance(is_person_raw, bool) else None
        results[candidate_id] = {
            "used": True,
            "is_person_like": is_person_like,
            "confidence": confidence,
            "canonical_name": _clean_verifier_reason(item.get("canonical_name_or_null")),
            "reason": _clean_verifier_reason(item.get("reason")),
        }
    return results


async def _apply_contextual_mention_verification(
    source_text: str,
    characters: list[dict],
    *,
    rejected_characters: list[dict] | None = None,
    user_id: uuid.UUID | None = None,
    book_id: uuid.UUID | None = None,
) -> list[dict]:
    if not characters:
        return []

    reviewed_candidates: list[dict] = []
    verified: list[dict] = []
    for index, character in enumerate(characters):
        name = str(character.get("name") or "").strip()
        if not name:
            continue
        candidate_id = f"candidate-{index}"
        traits = cast(dict[str, object], character.get("traits") if isinstance(character.get("traits"), dict) else {})
        aliases = [str(alias).strip() for alias in (character.get("aliases") or []) if str(alias).strip()]
        verifier = {
            "local": _local_mention_verifier(
                source_text,
                name,
                aliases=aliases,
                traits=traits,
                entity_type=str(character.get("entity_type") or "person"),
            ),
            "llm": {"used": False, "is_person_like": None, "confidence": None, "canonical_name": None, "reason": None},
            "final": {},
        }
        local = verifier["local"]
        if local["confidence_band"] == "accept":
            verifier["final"] = {
                "confidence_band": "accept",
                "is_person_like": True,
                "reasons": list(local["reasons"]),
            }
        elif local["confidence_band"] == "reject":
            verifier["final"] = {
                "confidence_band": "reject",
                "is_person_like": False,
                "reasons": list(local["reasons"]),
            }
        else:
            reviewed_candidates.append(
                {
                    "id": candidate_id,
                    "name": name,
                    "aliases": aliases,
                    "entity_type": str(character.get("entity_type") or "person"),
                    "traits": traits,
                    "verifier_local": local,
                }
            )
            verifier["final"] = {
                "confidence_band": "review",
                "is_person_like": False,
                "reasons": list(local["reasons"]),
            }
        evidence = dict(character.get("evidence") if isinstance(character.get("evidence"), dict) else {})
        evidence["verifier"] = verifier
        character["evidence"] = evidence
        character["_verifier_candidate_id"] = candidate_id
        verified.append(character)

    llm_results = await _verify_review_candidates_with_llm(
        source_text,
        reviewed_candidates,
        user_id=user_id,
        book_id=book_id,
    )
    for character in verified:
        evidence = dict(character.get("evidence") if isinstance(character.get("evidence"), dict) else {})
        verifier = dict(evidence.get("verifier") if isinstance(evidence.get("verifier"), dict) else {})
        local = dict(verifier.get("local") if isinstance(verifier.get("local"), dict) else {})
        if local.get("confidence_band") != "review":
            continue
        llm_result = dict(llm_results.get(str(character.get("_verifier_candidate_id") or "")) or {})
        verifier["llm"] = {
            "used": bool(llm_result),
            "is_person_like": llm_result.get("is_person_like"),
            "confidence": llm_result.get("confidence"),
            "canonical_name": llm_result.get("canonical_name"),
            "reason": llm_result.get("reason"),
        }
        llm_is_person = llm_result.get("is_person_like")
        llm_confidence = llm_result.get("confidence")
        if llm_is_person is True:
            verifier["final"] = {
                "confidence_band": "accept",
                "is_person_like": True,
                "reasons": ["llm_confirmed_person", *[str(reason).strip() for reason in (local.get("reasons") or []) if str(reason).strip()]],
            }
        elif llm_is_person is False and (llm_confidence is None or float(llm_confidence) >= 0.55):
            verifier["final"] = {
                "confidence_band": "reject",
                "is_person_like": False,
                "reasons": ["llm_rejected_person", *[str(reason).strip() for reason in (local.get("reasons") or []) if str(reason).strip()]],
            }
        evidence["verifier"] = verifier
        character["evidence"] = evidence
        canonical_name = _clean_verifier_reason(llm_result.get("canonical_name"))
        if canonical_name and canonical_name != str(character.get("name") or "") and _contains_supported_subspan(
            str(character.get("name") or ""),
            canonical_name,
            source_text,
        ):
            character["llm_canonical_name"] = canonical_name

    accepted_or_review: list[dict] = []
    for character in verified:
        evidence = dict(character.get("evidence") if isinstance(character.get("evidence"), dict) else {})
        verifier = dict(evidence.get("verifier") if isinstance(evidence.get("verifier"), dict) else {})
        final = dict(verifier.get("final") if isinstance(verifier.get("final"), dict) else {})
        if final.get("confidence_band") == "reject":
            _record_rejected_character(
                rejected_characters,
                stage="mention_verifier",
                name=str(character.get("name") or ""),
                reason=";".join(str(reason).strip() for reason in (final.get("reasons") or []) if str(reason).strip()) or "mention_verifier_rejected",
                confidence=float(character.get("confidence") or 0.0),
                evidence=evidence,
            )
            continue
        character.pop("_verifier_candidate_id", None)
        accepted_or_review.append(character)
    return accepted_or_review


def _augment_with_named_mentions(
    chunk_text: str,
    characters: list[dict],
    candidates: list[str] | None = None,
    *,
    rejected_characters: list[dict] | None = None,
    allow_review_candidates: bool = False,
) -> list[dict]:
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
        if not _allow_auto_augmentation(
            chunk_text,
            candidate,
            allow_review_singletons=allow_review_candidates,
        ):
            evidence = _build_evidence(chunk_text, candidate, {}, [])
            _record_rejected_character(
                rejected_characters,
                stage="candidate_augmentation",
                name=candidate,
                reason="insufficient_augmentation_support",
                evidence=evidence,
            )
            continue
        evidence = _build_evidence(chunk_text, candidate, {}, [])
        confidence = (
            FALLBACK_STRONG_MENTION_CONFIDENCE
            if int(evidence.get("strong_mention_count") or 0) >= 1
            else MIN_BORDERLINE_CONFIDENCE
        )
        characters.append(
            {
                "name": candidate,
                "canonical_name": candidate,
                "aliases": [],
                "entity_type": "person",
                "is_character": True,
                "confidence": confidence,
                "traits": {},
                "personality_tags": [],
                "goal": None,
                "motivations": [],
                "fears": [],
                "lie_they_believe": None,
                "backstory_wound": None,
                "arc_type": None,
                "arc_summary": None,
                "archetype": None,
                "first_appearance_context": "Named in the passage but not yet richly described.",
                "mention_count": evidence["mention_count"],
                "evidence": evidence,
                "rejection_reason": None,
                "growth_event": None,
            }
        )
        known.add(normalized)
        promoted += 1
        if promoted >= MAX_AUTO_AUGMENTED_CHARACTERS:
            break
    return characters


def _candidate_viability_band(
    text: str,
    name: str,
    *,
    allow_review: bool = False,
) -> str | None:
    local = _local_mention_verifier(text, name, entity_type="person")
    band = str(local.get("confidence_band") or "").strip()
    if band == "accept":
        return "accept"
    if allow_review and band == "review":
        return "review"
    return None


def _candidate_names(text: str, *, allow_review_singletons: bool = False) -> list[str]:
    candidates: list[str] = []
    candidates.extend(HONORIFIC_RE.findall(text))
    full_names = FULL_NAME_RE.findall(text)
    candidates.extend(full_names)
    candidates.extend(PARTICLE_NAME_RE.findall(text))
    masked_full_name_text = text
    for full_name in full_names:
        masked_full_name_text = re.sub(
            rf"\b{re.escape(full_name)}\b",
            " " * len(full_name),
            masked_full_name_text,
        )
    full_name_last_tokens = {
        words[-1]
        for full_name in full_names
        if (words := re.findall(r"[A-Za-z][A-Za-z'-]*", full_name))
    }

    singles = [
        token
        for token in SINGLE_NAME_RE.findall(text)
        if token not in NAME_STOPWORDS and token.casefold() not in COMMON_NON_NAME_WORDS and token.lower() not in {"the", "this", "that"}
        and not (
            token in full_name_last_tokens
            and not re.search(rf"\b{re.escape(token)}\b", masked_full_name_text)
        )
    ]
    single_counts = Counter(singles)
    candidates.extend(
        name
        for name, count in single_counts.items()
        if (
            _has_character_context(text, name)
            or count >= 2
            or _candidate_viability_band(text, name, allow_review=allow_review_singletons) is not None
        )
    )

    deduped: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        cleaned = " ".join(name.split()).strip(" .,:;!?\"'")
        normalized = _normalize_name(cleaned)
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", cleaned)
        viability_band = (
            _candidate_viability_band(text, cleaned, allow_review=allow_review_singletons)
            if len(words) == 1
            else None
        )
        if not cleaned or not normalized or normalized in seen:
            continue
        if not _looks_like_character_name(cleaned, text):
            if not (len(words) == 1 and viability_band is not None and looks_like_person_entity_name(cleaned)):
                continue
        elif len(words) == 1 and viability_band == "reject":
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


def _split_titled_name(name: str, source_text: str) -> tuple[str, str | None]:
    lowered = name.casefold()
    for prefix in TITLE_PREFIXES:
        token = f"{prefix} "
        if lowered.startswith(token):
            remainder = name[len(token):].strip()
            if remainder:
                remainder_tokens = re.findall(r"[A-Za-z][A-Za-z'-]*", remainder)
                if len(remainder_tokens) <= 1:
                    # Keep titled surname-only forms distinct. "Mr. Samsa" and
                    # "Mrs. Samsa" are often separate characters, while bare
                    # "Samsa" is too ambiguous to use as the canonical name.
                    return name, None
                if _find_name_mentions(source_text, remainder):
                    return remainder, name
                return name, None
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
    mention_snippets = _evidence_snippets(source_text, name)
    for alias in aliases:
        alias_count, alias_strong = _mention_support_score(source_text, alias)
        alias_mentions += alias_count
        strong_mentions += alias_strong
        mention_snippets.extend(_evidence_snippets(source_text, alias))
    total_mentions = mention_count + alias_mentions
    has_description = any(isinstance(value, dict) and value.get("value") for value in traits.values())
    return {
        "mention_count": total_mentions,
        "strong_mention_count": strong_mentions,
        "has_dialogue_or_action": strong_mentions >= 1,
        "has_physical_description": has_description,
        "appears_multiple_times": total_mentions >= 2,
        "snippets": mention_snippets[:3],
    }


def _evidence_snippets(source_text: str, name: str) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for start, end in _find_name_mentions(source_text, name):
        excerpt = " ".join(source_text[max(0, start - 90): min(len(source_text), end + 90)].split()).strip()
        if not excerpt:
            continue
        if excerpt in seen:
            continue
        seen.add(excerpt)
        snippets.append(excerpt)
        if len(snippets) >= 3:
            break
    return snippets


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
    if len(words) == 1 and (
        words[0] in SINGLE_NAME_DISCOURSE_MARKERS
        or words[0] in SINGLE_NAME_TIME_WORDS
        or words[0].casefold() in SINGLE_TOKEN_DISCOURSE_WORDS
    ):
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


def _clean_character_entries(
    characters: list[dict],
    candidate_names: list[str],
    source_text: str,
    *,
    rejected_characters: list[dict] | None = None,
) -> list[dict]:
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
            _record_rejected_character(
                rejected_characters,
                stage="llm_clean",
                name=raw_name,
                reason="unsupported_subspan",
                confidence=float(item.get("confidence") or 0.0),
            )
            continue

        entity_type = str(item.get("entity_type") or "").strip().casefold() or "person"
        is_character = bool(item.get("is_character", True))
        confidence = float(item.get("confidence") or 0.0)
        if entity_type not in {"person", "alias", "unknown"} or not is_character:
            _record_rejected_character(
                rejected_characters,
                stage="llm_clean",
                name=raw_name,
                reason="non_character_entity_type",
                confidence=confidence,
            )
            continue

        rejection_reason = _reject_obvious_bad_name(cleaned_name)
        if rejection_reason:
            log.info("Rejected extracted character '%s': %s", raw_name, rejection_reason)
            _record_rejected_character(
                rejected_characters,
                stage="llm_clean",
                name=raw_name,
                reason=rejection_reason,
                confidence=confidence,
            )
            continue

        if normalized not in candidate_norms and not _looks_like_character_name(cleaned_name, source_text):
            _record_rejected_character(
                rejected_characters,
                stage="llm_clean",
                name=raw_name,
                reason="fails_character_name_shape",
                confidence=confidence,
            )
            continue
        if normalized in candidate_norms and person_name_shape_score(cleaned_name) < 1 and not _looks_like_character_name(cleaned_name, source_text):
            _record_rejected_character(
                rejected_characters,
                stage="llm_clean",
                name=raw_name,
                reason="candidate_name_shape_too_weak",
                confidence=confidence,
            )
            continue

        traits = cast(dict[str, object], item.get("traits") if isinstance(item.get("traits"), dict) else {})
        arc_summary = _sanitize_summary(item.get("arc_summary"))

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

        cleaned_name, titled_alias = _split_titled_name(cleaned_name, source_text)
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
            "goal": _sanitize_summary(item.get("goal")),
            "lie_they_believe": _sanitize_summary(item.get("lie_they_believe")),
            "backstory_wound": _sanitize_summary(item.get("backstory_wound")),
            "arc_type": _sanitize_summary(item.get("arc_type")),
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

    escaped = re.escape(name.casefold())
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


def _allow_auto_augmentation(
    text: str,
    name: str,
    *,
    allow_review_singletons: bool = False,
) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", name)
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
    subject_action_mentions = sum(
        1
        for start, end in mentions
        if _mention_is_sentence_start(text, start)
        and _single_token_subject_action(text[end:min(len(text), end + 48)])
    )
    if len(words) == 1:
        viability_band = _candidate_viability_band(text, name, allow_review=allow_review_singletons)
        normalized = words[0].casefold()
        subject_action_mentions = sum(
            1
            for start, end in mentions
            if _mention_is_sentence_start(text, start)
            and not _single_token_starts_like_interjection(name, text[end:min(len(text), end + 48)])
            and _single_token_subject_action(text[end:min(len(text), end + 48)])
        )
        if viability_band == "accept":
            if normalized in SINGLE_TOKEN_DISCOURSE_WORDS:
                return strong_mentions >= 2 and non_sentence_start_mentions >= 1
            return bool(
                subject_action_mentions >= 1
                or strong_mentions >= 2
                or (strong_mentions >= 1 and non_sentence_start_mentions >= 1)
            )
        if viability_band == "review":
            return allow_review_singletons and normalized not in SINGLE_TOKEN_DISCOURSE_WORDS
        # Single-token names are noisy, but named mid-sentence with grounded
        # person context ("his sister Grete called") should still recover.
        return strong_mentions >= 2 or (strong_mentions >= 1 and non_sentence_start_mentions >= 1)
    return strong_mentions >= 1 and (
        non_sentence_start_mentions >= 1
        or len(mentions) >= 2
        or subject_action_mentions >= 1
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
