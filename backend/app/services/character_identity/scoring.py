from __future__ import annotations

from dataclasses import dataclass

from app.models.character import Character
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.services.character_identity.normalization import (
    first_name_token,
    name_tokens,
    normalize_name,
)
from app.utils.characters.identity import has_conflicting_title_identity
from app.utils.characters.similarity import name_similarity


@dataclass(frozen=True)
class IdentityScores:
    promotion_confidence: float
    merge_confidence: float
    alias_confidence: float
    fake_confidence: float
    reasons: tuple[str, ...]


def score_identity_evidence(
    *,
    surface_text: str | None,
    character: Character | None = None,
    target: Character | None = None,
    evidence: dict | None = None,
) -> IdentityScores:
    evidence = evidence or {}
    kind = classify_candidate_kind(surface_text)
    reasons: list[str] = [f"kind:{kind.value}"]
    mention_count = max(
        int(evidence.get("mention_count") or 0),
        int(getattr(character, "mention_count", 0) or 0) if character is not None else 0,
    )
    chapter_count = len(
        {int(value) for value in evidence.get("chapter_numbers", []) if str(value).isdigit()}
    )
    has_profile = bool(
        character
        and (
            character.arc_summary
            or character.trait_state
            or character.personality_tags
            or character.motivations
            or character.fears
        )
    )

    promotion = min(0.95, 0.25 + min(mention_count, 8) * 0.06 + min(chapter_count, 4) * 0.06)
    if has_profile:
        promotion += 0.18
        reasons.append("profile_evidence")
    if kind in {
        CandidateKind.FRAGMENT,
        CandidateKind.PRONOUN,
        CandidateKind.OBJECT_OR_PLACE,
        CandidateKind.GROUP_DESCRIPTOR,
    }:
        promotion = min(promotion, 0.2)

    merge = 0.0
    alias = 0.0
    if character is not None and target is not None:
        left = character.name
        right = target.name
        if has_conflicting_title_identity(left, right):
            reasons.append("conflicting_title_identity")
        else:
            left_norm = normalize_name(left)
            right_norm = normalize_name(right)
            if left_norm and left_norm == right_norm:
                merge = 0.95
                reasons.append("exact_normalized_name")
            else:
                similarity = name_similarity(left, right)
                merge = max(merge, min(0.9, similarity * 0.8))
                if similarity >= 0.88:
                    reasons.append("high_name_similarity")
            left_tokens = name_tokens(left)
            right_tokens = name_tokens(right)
            if (
                len(left_tokens) == 1
                and len(right_tokens) >= 2
                and left_tokens[0] == right_tokens[0]
            ):
                alias = 0.9
                reasons.append("single_token_first_name_alias")
            elif (
                len(right_tokens) == 1
                and len(left_tokens) >= 2
                and right_tokens[0] == left_tokens[0]
            ):
                alias = 0.9
                reasons.append("single_token_first_name_alias")
            if left_norm in {normalize_name(value) for value in target.aliases or []}:
                alias = max(alias, 0.92)
                reasons.append("listed_alias")
            if right_norm in {normalize_name(value) for value in character.aliases or []}:
                alias = max(alias, 0.92)
                reasons.append("listed_alias")
    elif kind == CandidateKind.ALIAS and first_name_token(surface_text):
        alias = 0.5

    fake = 0.0
    if kind in {
        CandidateKind.FRAGMENT,
        CandidateKind.PRONOUN,
        CandidateKind.OBJECT_OR_PLACE,
        CandidateKind.GROUP_DESCRIPTOR,
    }:
        fake = 0.95
    elif kind == CandidateKind.ROLE_DESCRIPTOR:
        fake = 0.75 if mention_count >= 3 else 0.88
    elif kind == CandidateKind.KINSHIP_DESCRIPTOR:
        fake = 0.86

    return IdentityScores(
        promotion_confidence=max(0.0, min(1.0, promotion)),
        merge_confidence=max(0.0, min(1.0, merge)),
        alias_confidence=max(0.0, min(1.0, alias)),
        fake_confidence=max(0.0, min(1.0, fake)),
        reasons=tuple(reasons),
    )
