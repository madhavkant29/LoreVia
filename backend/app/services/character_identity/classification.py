from __future__ import annotations

from enum import StrEnum

from app.engine.character.extractor import _is_title_only_name
from app.services.character_identity.normalization import (
    first_name_token,
    name_tokens,
    normalize_name,
)
from app.utils.characters.identity import family_role_reference


class CandidateKind(StrEnum):
    CANONICAL_NAME = "canonical_name"
    ALIAS = "alias"
    TITLE_NAME = "title_name"
    KINSHIP_DESCRIPTOR = "kinship_descriptor"
    ROLE_DESCRIPTOR = "role_descriptor"
    GROUP_DESCRIPTOR = "group_descriptor"
    FRAGMENT = "fragment"
    PRONOUN = "pronoun"
    OBJECT_OR_PLACE = "object_or_place"
    AMBIGUOUS = "ambiguous"


PRONOUNS = {"he", "she", "they", "them", "him", "her", "his", "hers", "their", "theirs", "we", "us"}
GROUP_WORDS = {
    "army",
    "audience",
    "children",
    "crew",
    "crowd",
    "family",
    "guards",
    "lodgers",
    "men",
    "parents",
    "people",
    "police",
    "servants",
    "soldiers",
    "staff",
    "team",
    "villagers",
    "women",
}
OBJECT_OR_PLACE_WORDS = {
    "avenue",
    "bed",
    "boat",
    "book",
    "bridge",
    "carriage",
    "cart",
    "chair",
    "church",
    "city",
    "county",
    "desk",
    "door",
    "empire",
    "floor",
    "forest",
    "garden",
    "hall",
    "hill",
    "hospital",
    "house",
    "inn",
    "kingdom",
    "lane",
    "letter",
    "market",
    "office",
    "port",
    "road",
    "room",
    "school",
    "ship",
    "square",
    "station",
    "street",
    "table",
    "town",
    "train",
    "vessel",
    "village",
    "wagon",
    "window",
}
ROLE_WORDS = {
    "assistant",
    "broker",
    "captain",
    "cleaner",
    "clerk",
    "cook",
    "doctor",
    "employee",
    "guard",
    "inspector",
    "lodger",
    "maid",
    "manager",
    "nurse",
    "officer",
    "servant",
    "teacher",
    "waiter",
}
TITLE_PREFIXES = {
    "mr",
    "mrs",
    "ms",
    "miss",
    "dr",
    "sir",
    "lady",
    "lord",
    "prof",
    "professor",
    "capt",
    "captain",
    "commander",
    "master",
    "mistress",
}


def classify_candidate_kind(
    surface_text: str | None, *, ner_label: str | None = None
) -> CandidateKind:
    text = " ".join(str(surface_text or "").split()).strip()
    if not text:
        return CandidateKind.FRAGMENT
    normalized = normalize_name(text)
    tokens = name_tokens(text)
    lowered = text.casefold().strip(" .,!?:;\"'")
    raw_tokens = [
        token.strip(" .,!?:;\"'").casefold() for token in text.split() if token.strip(" .,!?:;\"'")
    ]

    if _is_title_only_name(text) or lowered in TITLE_PREFIXES:
        return CandidateKind.FRAGMENT
    if lowered in PRONOUNS:
        return CandidateKind.PRONOUN
    if ner_label and ner_label.upper() in {"GPE", "LOC", "ORG", "FAC"}:
        return CandidateKind.OBJECT_OR_PLACE

    anchor, role = family_role_reference(text)
    if anchor and role:
        return CandidateKind.KINSHIP_DESCRIPTOR

    if raw_tokens and raw_tokens[0] in TITLE_PREFIXES and len(raw_tokens) >= 2:
        return CandidateKind.TITLE_NAME

    if raw_tokens and raw_tokens[0] in {"the", "a", "an"}:
        noun = raw_tokens[-1]
        if noun in GROUP_WORDS or noun.endswith("s"):
            return CandidateKind.GROUP_DESCRIPTOR
        if noun in OBJECT_OR_PLACE_WORDS:
            return CandidateKind.OBJECT_OR_PLACE
        if noun in ROLE_WORDS:
            return CandidateKind.ROLE_DESCRIPTOR

    if len(tokens) >= 2:
        return CandidateKind.CANONICAL_NAME
    if len(tokens) == 1:
        token = first_name_token(text)
        if token in ROLE_WORDS:
            return CandidateKind.ROLE_DESCRIPTOR
        if token in OBJECT_OR_PLACE_WORDS:
            return CandidateKind.OBJECT_OR_PLACE
        if normalized:
            return CandidateKind.ALIAS
    return CandidateKind.AMBIGUOUS
