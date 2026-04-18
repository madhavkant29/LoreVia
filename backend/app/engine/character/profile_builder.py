"""
Confidence-weighted character profile builder.
Merges new trait info without overwriting and handles subjective narration.
"""
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
        return "appearance not yet described"
    
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


def _clean_line(value: str | None) -> str:
    if not value:
        return ""
    # Remove special characters including Unicode symbols
    cleaned = re.sub(r"[\u2726\u2318\u2600-\u26FF\u2700-\u27BF]", "", value)  # Remove misc symbols and dingbats
    cleaned = re.sub(r"[^\w\s.,!?;:'\"-]", " ", cleaned)  # Replace other special chars with space
    return " ".join(cleaned.split()).strip()


def choose_richer_text(*values: str | None) -> str | None:
    cleaned = [_clean_line(value) for value in values if value and value.strip()]
    if not cleaned:
        return None
    return max(cleaned, key=len)


def build_character_profile(extracted: dict, book_id: uuid.UUID, first_chapter: int) -> dict:
    raw_traits = extracted.get("traits", {})
    archetype = extracted.get("archetype")
    trait_state = merge_trait_states({}, raw_traits)

    return {
        "book_id": book_id,
        "name": extracted["name"],
        "aliases": extracted.get("aliases", []),
        "role": extracted.get("role"),
        "first_chapter": first_chapter,
        "trait_state": trait_state,
        "hair": flat(trait_state, "hair"),
        "eyes": flat(trait_state, "eyes"),
        "build": flat(trait_state, "build"),
        "age_descriptor": flat(trait_state, "age"),
        "distinguishing": flat(trait_state, "distinguishing"),
        "personality_tags": extracted.get("personality_tags", []),
        "motivations": extracted.get("motivations", []),
        "fears": extracted.get("fears", []),
        "arc_summary": extracted.get("arc_summary"),
        "archetype": archetype,
    }


def merge_profile_fields(existing, incoming) -> dict:
    existing_trait_state = existing.trait_state or {}
    incoming_trait_state = incoming.get("trait_state") if isinstance(incoming, dict) else incoming.trait_state or {}
    merged_traits = merge_trait_states(existing_trait_state, incoming_trait_state)

    existing_aliases = existing.aliases or []
    incoming_aliases = incoming.get("aliases", []) if isinstance(incoming, dict) else incoming.aliases or []
    incoming_name = incoming.get("name") if isinstance(incoming, dict) else incoming.name
    incoming_role = incoming.get("role") if isinstance(incoming, dict) else incoming.role
    incoming_first_chapter = incoming.get("first_chapter", existing.first_chapter) if isinstance(incoming, dict) else incoming.first_chapter
    incoming_personality = incoming.get("personality_tags") if isinstance(incoming, dict) else incoming.personality_tags
    incoming_motivations = incoming.get("motivations") if isinstance(incoming, dict) else incoming.motivations
    incoming_fears = incoming.get("fears") if isinstance(incoming, dict) else incoming.fears
    incoming_arc = incoming.get("arc_summary") if isinstance(incoming, dict) else incoming.arc_summary
    incoming_archetype = incoming.get("archetype") if isinstance(incoming, dict) else incoming.archetype

    aliases = merge_list_values(existing_aliases, incoming_aliases, [incoming_name] if incoming_name else [])
    aliases = [alias for alias in aliases if alias.lower() != existing.name.lower()]

    return {
        "aliases": aliases,
        "role": existing.role or incoming_role,
        "first_chapter": min(existing.first_chapter, incoming_first_chapter),
        "trait_state": merged_traits,
        "hair": flat(merged_traits, "hair"),
        "eyes": flat(merged_traits, "eyes"),
        "build": flat(merged_traits, "build"),
        "age_descriptor": flat(merged_traits, "age"),
        "distinguishing": flat(merged_traits, "distinguishing"),
        "personality_tags": merge_list_values(existing.personality_tags, incoming_personality),
        "motivations": merge_list_values(existing.motivations, incoming_motivations),
        "fears": merge_list_values(existing.fears, incoming_fears),
        "arc_summary": choose_richer_text(existing.arc_summary, incoming_arc),
        "archetype": choose_richer_text(existing.archetype, incoming_archetype),
    }


def update_profile(existing, extracted: dict) -> dict:
    return merge_profile_fields(existing, {
        "name": extracted.get("name"),
        "aliases": extracted.get("aliases", []),
        "role": extracted.get("role"),
        "first_chapter": extracted.get("first_chapter", existing.first_chapter),
        "trait_state": extracted.get("traits", {}),
        "personality_tags": extracted.get("personality_tags", []),
        "motivations": extracted.get("motivations", []),
        "fears": extracted.get("fears", []),
        "arc_summary": extracted.get("arc_summary"),
        "archetype": extracted.get("archetype"),
    })
