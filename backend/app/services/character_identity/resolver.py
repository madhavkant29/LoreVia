from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
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
        return IdentityResolutionResult("auto_suppress", None, 0.86, "kinship_descriptor_unresolved_suppressed")

    if normalized:
        exact = (
            await db.execute(
                select(Character).where(
                    Character.book_id == book_id,
                    Character.normalized_name == normalized,
                    Character.merged_into_character_id.is_(None),
                ).limit(1)
            )
        ).scalars().first()
        if exact is None:
            candidates = (
                await db.execute(
                    select(Character).where(
                        Character.book_id == book_id,
                        Character.merged_into_character_id.is_(None),
                    )
                )
            ).scalars().all()
            exact = next((character for character in candidates if normalize_name(character.name) == normalized), None)
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
                await db.execute(
                    select(Character).where(
                        Character.book_id == book_id,
                        Character.merged_into_character_id.is_(None),
                    )
                )
            ).scalars().all()
            full_name_match = next(
                (
                    character
                    for character in candidates
                    if len(normalize_name(character.name).split()) >= 2
                    and normalize_name(character.name).split()[0] == token
                ),
                None,
            )
            if full_name_match is not None:
                await add_character_alias(
                    db,
                    character=full_name_match,
                    alias_text=surface_text,
                    alias_kind="first_name",
                    source="resolver",
                    confidence=0.9,
                )
                return IdentityResolutionResult("auto_alias", full_name_match.id, 0.9, "single_token_first_name_alias")

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
        return IdentityResolutionResult("auto_suppress", None, 0.88, "role_descriptor_low_evidence_suppressed")

    return IdentityResolutionResult("needs_review", None, 0.5, f"{kind.value}_needs_review")
