"""
Confidence-weighted character profile builder.
Merges new trait info without overwriting and handles subjective narration.
"""
import re
import uuid
from collections.abc import Iterable

PROMPT_CONFIDENCE_THRESHOLD = 0.45
SUBJECTIVE_MAX_CONFIDENCE = 0.50

ARCHETYPE_PROMPTS = {
    "japanese high school boy": "teenage japanese boy, average build, school setting",
    "japanese high school girl": "teenage japanese girl, school setting",
    "medieval knight": "armored figure, strong build, battle-worn",
    "mentor": "older person, wise expression",
    "trickster": "sly expression, agile build",
    "villain": "imposing figure, sharp eyes",
    "hero": "determined expression, athletic build",
    "young adult male protagonist": "young adult male, determined expression",
}

SUBJECTIVE_TRANSLATIONS = {
    "plain": "average-looking",
    "mob-like": "average-looking, unremarkable",
    "ugly": "unconventional features",
    "background character": "ordinary appearance",
    "average": "average-looking",
}
GENERIC_SUMMARY_PHRASES = {
    "appearance not yet described",
    "background character",
    "is a character",
    "mysterious figure",
    "normal character",
    "plain character",
    "tragic figure",
    "supporting character",
    "this character is a character",
    "protagonist",
    "antagonist",
    "puppet master",
    "unknown character",
}


def merge_trait_states(existing: dict, new_traits: dict) -> dict:
    merged = dict(existing)
    for key, new_data in new_traits.items():
        if not isinstance(new_data, dict) or "value" not in new_data:
            continue
        new_conf = float(new_data.get("confidence", 0.5))
        new_type = new_data.get("type", "objective")
        if new_type == "subjective":
            new_conf = min(new_conf, SUBJECTIVE_MAX_CONFIDENCE)
        if key not in merged:
            merged[key] = {"value": new_data["value"], "confidence": new_conf, "type": new_type}
        else:
            ex_conf = float(merged[key].get("confidence", 0.5))
            if new_conf > ex_conf + 0.15:
                merged[key] = {"value": new_data["value"], "confidence": new_conf, "type": new_type}
            elif abs(new_conf - ex_conf) <= 0.15:
                if new_data["value"].lower() == merged[key]["value"].lower():
                    merged[key]["confidence"] = min(1.0, ex_conf + 0.1)
    return merged


def build_description(trait_state: dict, archetype: str | None) -> str:
    """Builds a natural-sounding description of the character for display and context."""
    manual = trait_state.get("manual_description", {})
    if isinstance(manual, dict) and manual.get("value"):
        return str(manual["value"]).strip()

    # Extract traits with confidence threshold
    traits = {}
    for key in ["age", "build", "hair", "eyes", "face", "distinguishing"]:
        t = trait_state.get(key, {})
        if isinstance(t, dict) and t.get("confidence", 0) >= PROMPT_CONFIDENCE_THRESHOLD:
            v = t["value"]
            if t.get("type") == "subjective":
                v = SUBJECTIVE_TRANSLATIONS.get(v.lower(), v)
            traits[key] = v
    
    # If no traits found, use archetype fallback
    if not traits and archetype:
        return ARCHETYPE_PROMPTS.get(archetype.lower(), archetype)
    elif not traits:
        return ""
    
    # Build natural sentences
    sentences = []
    
    # Age description
    if "age" in traits:
        age = traits["age"]
        if "build" in traits:
            sentences.append(f"A {age} with a {traits['build']} build")
        else:
            sentences.append(f"A {age}")
    elif "build" in traits:
        sentences.append(f"Has a {traits['build']} build")
    
    # Hair and eyes description
    hair_eyes_parts = []
    if "hair" in traits:
        hair_eyes_parts.append(f"{traits['hair']} hair")
    if "eyes" in traits:
        hair_eyes_parts.append(f"{traits['eyes']} eyes")
    
    if hair_eyes_parts:
        if len(hair_eyes_parts) == 1:
            sentences.append(f"Has {hair_eyes_parts[0]}")
        else:
            sentences.append(f"Has {hair_eyes_parts[0]} and {hair_eyes_parts[1]}")
    
    # Face description
    if "face" in traits:
        sentences.append(f"Features {traits['face']}")
    
    # Distinguishing features
    if "distinguishing" in traits:
        sentences.append(f"Notable for {traits['distinguishing']}")
    
    # Combine sentences into natural paragraph
    if len(sentences) == 1:
        return sentences[0]
    elif len(sentences) == 2:
        return f"{sentences[0]} and {sentences[1]}."
    else:
        return f"{'. '.join(sentences[:-1])}. {sentences[-1]}."


def flat(trait_state: dict, key: str) -> str | None:
    t = trait_state.get(key, {})
    if isinstance(t, dict) and t.get("confidence", 0) >= PROMPT_CONFIDENCE_THRESHOLD:
        return t["value"]
    return None


def merge_list_values(*groups: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in group or []:
            cleaned = " ".join(item.split()).strip()
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            merged.append(cleaned)
    return merged


def merge_growth_events(*groups: Iterable[dict] | None) -> list[dict]:
    seen: set[tuple[int | None, str]] = set()
    merged: list[dict] = []
    for group in groups:
        for item in group or []:
            if not isinstance(item, dict):
                continue
            event = " ".join(str(item.get("event") or "").split()).strip()
            if not event:
                continue
            chapter = item.get("chapter")
            signature = (chapter if isinstance(chapter, int) else None, event.lower())
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(
                {
                    "chapter": chapter if isinstance(chapter, int) else None,
                    "event": event,
                    "impact": _clean_line(item.get("impact")),
                    "tone": _clean_line(item.get("tone")),
                }
            )
    merged.sort(key=lambda item: (item.get("chapter") or 10**9, item.get("event") or ""))
    return merged[-12:]


def _normalize_trait_state(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _growth_event_group(value: object) -> list[dict]:
    return [value] if isinstance(value, dict) else []


def _clean_line(value: str | None) -> str:
    if not value:
        return ""
    # Remove special characters including Unicode symbols
    cleaned = re.sub(r"[\u2726\u2318\u2600-\u26FF\u2700-\u27BF]", "", value)  # Remove misc symbols and dingbats
    cleaned = re.sub(r"[^\w\s.,!?;:'\"-]", " ", cleaned)  # Replace other special chars with space
    return " ".join(cleaned.split()).strip()


def choose_richer_text(*values: str | None) -> str | None:
    cleaned = [_clean_line(value) for value in values if value and value.strip()]
    cleaned = [value for value in cleaned if value and value.casefold() not in GENERIC_SUMMARY_PHRASES]
    if not cleaned:
        return None
    return max(cleaned, key=len)


def build_character_analysis_metadata(extracted: dict, *, persistence_reason: str | None = None) -> dict:
    evidence = extracted.get("evidence") if isinstance(extracted.get("evidence"), dict) else {}
    mention_count = int(evidence.get("mention_count") or 0)
    strong_mentions = int(evidence.get("strong_mention_count") or 0)
    grounding_passage_count = max(mention_count, strong_mentions)
    cluster_size = int(evidence.get("cluster_size") or 1)
    cluster_mention_count = int(evidence.get("cluster_mention_count") or mention_count or 0)
    canonical_confidence = float(extracted.get("canonical_confidence") or extracted.get("confidence") or 0.0)
    grounding_coverage = round(strong_mentions / max(1, mention_count), 3) if mention_count else 0.0
    quality_flags: list[str] = []
    if not extracted.get("arc_summary") or str(extracted.get("arc_summary")).strip().casefold() in GENERIC_SUMMARY_PHRASES:
        quality_flags.append("generic_summary")
    if grounding_passage_count <= 1:
        quality_flags.append("light_grounding")
    if not evidence.get("has_dialogue_or_action"):
        quality_flags.append("no_dialogue_or_action")
    confidence = float(extracted.get("confidence") or 0.0)
    if confidence >= 0.9 and grounding_passage_count >= 2:
        confidence_band = "high"
    elif confidence >= 0.65 or grounding_passage_count >= 1:
        confidence_band = "medium"
    else:
        confidence_band = "low"
    summary_quality = "generic" if "generic_summary" in quality_flags else ("grounded" if grounding_passage_count >= 2 else "thin")
    return {
        "persistence_reason": persistence_reason or "extracted_character",
        "evidence_count": mention_count,
        "summary_quality": summary_quality,
        "needs_review": bool(quality_flags),
        "rejected_duplicate_candidates": [],
        "quality_flags": quality_flags,
        "grounding_passage_count": grounding_passage_count,
        "confidence_band": confidence_band,
        "canonical_confidence": canonical_confidence,
        "grounding_coverage": grounding_coverage,
        "cluster_size": cluster_size,
        "cluster_mention_count": cluster_mention_count,
        "resolver_status": str(extracted.get("resolver_status") or evidence.get("resolver_status") or "").strip() or None,
    }


def build_character_profile(extracted: dict, book_id: uuid.UUID, first_chapter: int) -> dict:
    raw_traits = _normalize_trait_state(extracted.get("traits"))
    archetype = extracted.get("archetype")
    trait_state = merge_trait_states({}, raw_traits)
    evidence = extracted.get("evidence") if isinstance(extracted.get("evidence"), dict) else {}
    mention_weight = max(
        1,
        int(evidence.get("cluster_size") or 0),
        int(extracted.get("cluster_size") or 0),
    )

    return {
        "book_id": book_id,
        "name": extracted["name"],
        "aliases": extracted.get("aliases", []),
        "role": extracted.get("role"),
        "first_chapter": first_chapter,
        "last_seen_chapter": first_chapter,   # set on first appearance
        "mention_count": mention_weight,
        "trait_state": trait_state,
        "hair": flat(trait_state, "hair"),
        "eyes": flat(trait_state, "eyes"),
        "build": flat(trait_state, "build"),
        "age_descriptor": flat(trait_state, "age"),
        "distinguishing": flat(trait_state, "distinguishing"),
        "personality_tags": extracted.get("personality_tags", []),
        "goal": extracted.get("goal"),
        "motivations": extracted.get("motivations", []),
        "fears": extracted.get("fears", []),
        "lie_they_believe": extracted.get("lie_they_believe"),
        "backstory_wound": extracted.get("backstory_wound"),
        "arc_type": extracted.get("arc_type"),
        "arc_summary": extracted.get("arc_summary"),
        "archetype": archetype,
        "growth_events": merge_growth_events(_growth_event_group(extracted.get("growth_event"))),
        "analysis_metadata": build_character_analysis_metadata(extracted),
    }


def merge_profile_fields(existing, incoming) -> dict:
    existing_trait_state = existing.trait_state or {}
    incoming_trait_state = (
        _normalize_trait_state(incoming.get("trait_state"))
        if isinstance(incoming, dict)
        else _normalize_trait_state(incoming.trait_state)
    )
    merged_traits = merge_trait_states(existing_trait_state, incoming_trait_state)

    existing_aliases = existing.aliases or []
    incoming_aliases = incoming.get("aliases", []) if isinstance(incoming, dict) else incoming.aliases or []
    incoming_name = incoming.get("name") if isinstance(incoming, dict) else incoming.name
    incoming_role = incoming.get("role") if isinstance(incoming, dict) else incoming.role
    incoming_first_chapter = incoming.get("first_chapter", existing.first_chapter) if isinstance(incoming, dict) else incoming.first_chapter
    incoming_personality = incoming.get("personality_tags") if isinstance(incoming, dict) else incoming.personality_tags
    incoming_goal = incoming.get("goal") if isinstance(incoming, dict) else getattr(incoming, "goal", None)
    incoming_motivations = incoming.get("motivations") if isinstance(incoming, dict) else incoming.motivations
    incoming_fears = incoming.get("fears") if isinstance(incoming, dict) else incoming.fears
    incoming_lie = incoming.get("lie_they_believe") if isinstance(incoming, dict) else getattr(incoming, "lie_they_believe", None)
    incoming_wound = incoming.get("backstory_wound") if isinstance(incoming, dict) else getattr(incoming, "backstory_wound", None)
    incoming_arc_type = incoming.get("arc_type") if isinstance(incoming, dict) else getattr(incoming, "arc_type", None)
    incoming_arc = incoming.get("arc_summary") if isinstance(incoming, dict) else incoming.arc_summary
    incoming_archetype = incoming.get("archetype") if isinstance(incoming, dict) else incoming.archetype
    incoming_last_seen = incoming.get("last_seen_chapter") if isinstance(incoming, dict) else getattr(incoming, "last_seen_chapter", None)
    incoming_growth_events = incoming.get("growth_events") if isinstance(incoming, dict) else getattr(incoming, "growth_events", None)
    incoming_evidence = incoming.get("evidence") if isinstance(incoming, dict) and isinstance(incoming.get("evidence"), dict) else {}
    mention_weight = max(
        1,
        int(incoming_evidence.get("cluster_size") or 0),
        int(incoming.get("cluster_size") or 0) if isinstance(incoming, dict) else 0,
    )

    aliases = merge_list_values(existing_aliases, incoming_aliases, [incoming_name] if incoming_name else [])
    aliases = [alias for alias in aliases if alias.lower() != existing.name.lower()]

    # last_seen_chapter: take the highest chapter number seen so far
    current_last_seen = existing.last_seen_chapter or existing.first_chapter
    new_last_seen = max(current_last_seen, incoming_last_seen or 0, incoming_first_chapter)

    return {
        "aliases": aliases,
        "role": existing.role or incoming_role,
        "first_chapter": min(existing.first_chapter, incoming_first_chapter),
        "last_seen_chapter": new_last_seen,
        "mention_count": (existing.mention_count or 0) + mention_weight,
        "trait_state": merged_traits,
        "hair": flat(merged_traits, "hair"),
        "eyes": flat(merged_traits, "eyes"),
        "build": flat(merged_traits, "build"),
        "age_descriptor": flat(merged_traits, "age"),
        "distinguishing": flat(merged_traits, "distinguishing"),
        "personality_tags": merge_list_values(existing.personality_tags, incoming_personality),
        "goal": choose_richer_text(getattr(existing, "goal", None), incoming_goal),
        "motivations": merge_list_values(existing.motivations, incoming_motivations),
        "fears": merge_list_values(existing.fears, incoming_fears),
        "lie_they_believe": choose_richer_text(getattr(existing, "lie_they_believe", None), incoming_lie),
        "backstory_wound": choose_richer_text(getattr(existing, "backstory_wound", None), incoming_wound),
        "arc_type": choose_richer_text(getattr(existing, "arc_type", None), incoming_arc_type),
        "arc_summary": choose_richer_text(existing.arc_summary, incoming_arc),
        "archetype": choose_richer_text(existing.archetype, incoming_archetype),
        "growth_events": merge_growth_events(existing.growth_events, incoming_growth_events),
        "analysis_metadata": {
            **(existing.analysis_metadata or {}),
            **build_character_analysis_metadata(
                incoming if isinstance(incoming, dict) else {},
                persistence_reason=str((existing.analysis_metadata or {}).get("persistence_reason") or "updated_character"),
            ),
            "rejected_duplicate_candidates": list((existing.analysis_metadata or {}).get("rejected_duplicate_candidates") or []),
        },
    }

def update_profile(existing, extracted: dict) -> dict:
    chapter = extracted.get("first_chapter", existing.first_chapter)
    return merge_profile_fields(existing, {
        "name": extracted.get("name"),
        "aliases": extracted.get("aliases", []),
        "role": extracted.get("role"),
        "first_chapter": chapter,
        "last_seen_chapter": chapter,   # chapter currently being processed
        "trait_state": extracted.get("traits", {}),
        "personality_tags": extracted.get("personality_tags", []),
        "goal": extracted.get("goal"),
        "motivations": extracted.get("motivations", []),
        "fears": extracted.get("fears", []),
        "lie_they_believe": extracted.get("lie_they_believe"),
        "backstory_wound": extracted.get("backstory_wound"),
        "arc_type": extracted.get("arc_type"),
        "arc_summary": extracted.get("arc_summary"),
        "archetype": extracted.get("archetype"),
        "growth_events": merge_growth_events(_growth_event_group(extracted.get("growth_event"))),
    })
