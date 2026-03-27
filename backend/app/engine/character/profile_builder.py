"""
Confidence-weighted character profile builder.
Merges new trait info without overwriting — handles subjective narration.
"""
import uuid
import random

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
    """Builds a plain-text description of the character for display and context."""
    parts = []
    for key in ["age", "build", "hair", "eyes", "face", "distinguishing"]:
        t = trait_state.get(key, {})
        if isinstance(t, dict) and t.get("confidence", 0) >= PROMPT_CONFIDENCE_THRESHOLD:
            v = t["value"]
            if t.get("type") == "subjective":
                v = SUBJECTIVE_TRANSLATIONS.get(v.lower(), v)
            if key == "hair":
                parts.append(f"{v} hair")
            elif key == "eyes":
                parts.append(f"{v} eyes")
            else:
                parts.append(v)
    if not parts and archetype:
        return ARCHETYPE_PROMPTS.get(archetype.lower(), archetype)
    return ", ".join(parts) if parts else "appearance not yet described"


def flat(trait_state: dict, key: str) -> str | None:
    t = trait_state.get(key, {})
    if isinstance(t, dict) and t.get("confidence", 0) >= PROMPT_CONFIDENCE_THRESHOLD:
        return t["value"]
    return None


def build_character_profile(extracted: dict, book_id: uuid.UUID, first_chapter: int) -> dict:
    raw_traits = extracted.get("traits", {})
    archetype = extracted.get("archetype")
    trait_state = merge_trait_states({}, raw_traits)

    return {
        "book_id": book_id,
        "name": extracted["name"],
        "aliases": extracted.get("aliases", []),
        "role": None,
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
        "archetype": archetype,
    }


def update_profile(existing_trait_state: dict, new_traits: dict, archetype: str | None) -> dict:
    updated = merge_trait_states(existing_trait_state, new_traits)
    return {
        "trait_state": updated,
        "description": build_description(updated, archetype),
        "hair": flat(updated, "hair"),
        "eyes": flat(updated, "eyes"),
        "build": flat(updated, "build"),
        "age_descriptor": flat(updated, "age"),
        "distinguishing": flat(updated, "distinguishing"),
    }
