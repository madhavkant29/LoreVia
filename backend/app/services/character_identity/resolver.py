from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character, CharacterCandidate, CharacterMention
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.services.character_identity.merge import add_character_alias, record_identity_action
from app.services.character_identity.normalization import first_name_token, normalize_name
from app.services.character_identity.suppression import suppress_candidate


@dataclass(frozen=True)
class IdentityResolutionResult:
    action: str
    target_character_id: uuid.UUID | None
    confidence: float
    reason: str


async def resolve_character_mention(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_number: int,
    surface_text: str,
    evidence: dict[str, Any] | None = None,
) -> IdentityResolutionResult:
    evidence = evidence or {}
    kind = classify_candidate_kind(surface_text, ner_label=evidence.get("ner_label"))
    normalized = normalize_name(surface_text)
    if kind in {
        CandidateKind.FRAGMENT,
        CandidateKind.PRONOUN,
        CandidateKind.OBJECT_OR_PLACE,
        CandidateKind.GROUP_DESCRIPTOR,
    }:
        await suppress_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            surface_text=surface_text,
            candidate_kind=kind.value,
            reason=f"{kind.value}_suppressed",
            confidence=0.95,
        )
        return IdentityResolutionResult("auto_suppress", None, 0.95, f"{kind.value}_suppressed")

    if kind == CandidateKind.KINSHIP_DESCRIPTOR:
        await suppress_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            surface_text=surface_text,
            candidate_kind=kind.value,
            reason="kinship_descriptor_unresolved_suppressed",
            confidence=0.86,
        )
        return IdentityResolutionResult(
            "auto_suppress", None, 0.86, "kinship_descriptor_unresolved_suppressed"
        )

    if kind == CandidateKind.TITLE_NAME:
        return IdentityResolutionResult("needs_review", None, 0.5, "title_name_requires_review")

    if normalized:
        exact = (
            (
                await db.execute(
                    select(Character)
                    .where(
                        Character.book_id == book_id,
                        Character.normalized_name == normalized,
                        Character.merged_into_character_id.is_(None),
                        Character.visibility_state == "visible",
                        Character.approval_state.in_(("approved", "protected")),
                    )
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if exact is None:
            candidates = (
                (
                    await db.execute(
                        select(Character).where(
                            Character.book_id == book_id,
                            Character.merged_into_character_id.is_(None),
                            Character.visibility_state == "visible",
                            Character.approval_state.in_(("approved", "protected")),
                        )
                    )
                )
                .scalars()
                .all()
            )
            exact = next(
                (
                    character
                    for character in candidates
                    if normalize_name(character.name) == normalized
                ),
                None,
            )
        if exact is not None:
            await record_identity_action(
                db,
                book_id=book_id,
                action_type="auto_merge",
                target_character_id=exact.id,
                surface_text=surface_text,
                confidence=0.95,
                reason="exact_normalized_name",
            )
            return IdentityResolutionResult("auto_merge", exact.id, 0.95, "exact_normalized_name")

    if kind == CandidateKind.ALIAS:
        token = first_name_token(surface_text)
        if token:
            candidates = (
                (
                    await db.execute(
                        select(Character).where(
                            Character.book_id == book_id,
                            Character.merged_into_character_id.is_(None),
                            Character.visibility_state == "visible",
                            Character.approval_state.in_(("approved", "protected")),
                        )
                    )
                )
                .scalars()
                .all()
            )
            full_name_matches = [
                character
                for character in candidates
                if len(normalize_name(character.name).split()) >= 2
                and normalize_name(character.name).split()[0] == token
            ]
            if len(full_name_matches) == 1:
                full_name_match = full_name_matches[0]
                await add_character_alias(
                    db,
                    character=full_name_match,
                    alias_text=surface_text,
                    alias_kind="first_name",
                    source="resolver",
                    confidence=0.9,
                )
                return IdentityResolutionResult(
                    "auto_alias", full_name_match.id, 0.9, "single_token_first_name_alias"
                )
            if len(full_name_matches) > 1:
                return IdentityResolutionResult(
                    "needs_review",
                    None,
                    0.35,
                    "ambiguous_single_token_first_name",
                )

    if kind == CandidateKind.ROLE_DESCRIPTOR:
        await suppress_candidate(
            db,
            book_id=book_id,
            chapter_number=chapter_number,
            surface_text=surface_text,
            candidate_kind=kind.value,
            reason="role_descriptor_low_evidence_suppressed",
            confidence=0.88,
        )
        return IdentityResolutionResult(
            "auto_suppress", None, 0.88, "role_descriptor_low_evidence_suppressed"
        )

    return IdentityResolutionResult("needs_review", None, 0.5, f"{kind.value}_needs_review")


async def reconcile_pending_first_name_alias_candidates(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int | None = None,
) -> int:
    characters = (
        (
            await db.execute(
                select(Character).where(
                    Character.book_id == book_id,
                    Character.merged_into_character_id.is_(None),
                    Character.visibility_state == "visible",
                    Character.approval_state.in_(("approved", "protected")),
                )
            )
        )
        .scalars()
        .all()
    )
    full_name_by_first_token: dict[str, list[Character]] = {}
    for character in characters:
        tokens = normalize_name(character.name).split()
        if len(tokens) >= 2:
            full_name_by_first_token.setdefault(tokens[0], []).append(character)

    candidate_filters = [
        CharacterCandidate.book_id == book_id,
        CharacterCandidate.status == "pending",
        CharacterCandidate.matched_character_id.is_(None),
    ]
    if chapter_number is not None:
        candidate_filters.append(CharacterCandidate.chapter_number == chapter_number)
    candidates = (
        (await db.execute(select(CharacterCandidate).where(*candidate_filters))).scalars().all()
    )
    reconciled = 0
    for candidate in candidates:
        if classify_candidate_kind(candidate.proposed_name) != CandidateKind.ALIAS:
            continue
        tokens = normalize_name(candidate.proposed_name).split()
        matches = full_name_by_first_token.get(tokens[0], []) if len(tokens) == 1 else []
        if len(matches) != 1:
            continue
        target = matches[0]
        alias = await add_character_alias(
            db,
            character=target,
            alias_text=candidate.proposed_name,
            alias_kind="first_name",
            source="extraction_reconcile",
            confidence=0.9,
        )
        if alias is None:
            continue
        candidate.matched_character_id = target.id
        candidate.status = "accepted"
        candidate.reason_codes = ["first_name_alias_reconciled"]
        mentions = (
            (
                await db.execute(
                    select(CharacterMention).where(
                        CharacterMention.book_id == book_id,
                        CharacterMention.chapter_number == candidate.chapter_number,
                        CharacterMention.normalized_name == candidate.normalized_name,
                        CharacterMention.matched_character_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for mention in mentions:
            mention.matched_character_id = target.id
            mention.resolver_status = "auto_alias"
            mention.resolver_reasons = ["first_name_alias_reconciled"]
        reconciled += 1
    return reconciled
