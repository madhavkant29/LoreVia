from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.character.adjudicator import (
    ADJUDICATION_OBJECT,
    ADJUDICATION_ORGANIZATION,
    ADJUDICATION_PLACE,
    ADJUDICATION_QUARANTINED,
    ADJUDICATION_TITLE_OR_ROLE,
    ENTITY_JUNK,
    ENTITY_PERSON,
    adjudicate_character_candidate,
)
from app.models.character import Character, CharacterDuplicateSuggestion, CharacterMention
from app.services.character_identity.classification import CandidateKind, classify_candidate_kind
from app.services.character_identity.constraints import (
    add_identity_constraint,
    has_blocking_identity_constraint,
)
from app.services.character_identity.merge import add_character_alias, record_identity_action
from app.services.character_identity.normalization import (
    assign_unique_active_normalized_names,
    first_name_token,
    normalize_name,
)
from app.services.character_identity.suppression import suppress_candidate
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
    CHARACTER_DUPLICATE_DISMISSED,
    CHARACTER_DUPLICATE_PENDING,
    CHARACTER_VISIBILITY_NOISE,
    CHARACTER_VISIBILITY_QUARANTINED,
)
from app.utils.characters.duplicates import refresh_character_duplicate_suggestions
from app.utils.characters.identity import family_role_reference, has_conflicting_title_identity
from app.utils.characters.merging import merge_characters
from app.utils.characters.review import set_character_review_state
from app.utils.characters.serialization import is_protected_character


@dataclass
class CharacterIdentityRepairResult:
    book_id: str
    dry_run: bool
    allow_merge_safe_pairs: bool = True
    allow_demote_obvious_noise: bool = True
    auto_merged: int = 0
    auto_aliases: int = 0
    auto_suppressed: int = 0
    blocked_suggestions: int = 0
    remaining_review_items: int = 0
    planned_merges: list[tuple[str, str]] = field(default_factory=list)
    planned_aliases: list[tuple[str, str]] = field(default_factory=list)
    planned_suppressions: list[str] = field(default_factory=list)
    blocked_duplicate_suggestions: list[str] = field(default_factory=list)
    character_labels: dict[str, str] = field(default_factory=dict)
    pending_duplicate_suggestions: int = 0
    pending_character_candidates_suppressed: int = 0
    pending_relationship_candidates: int = 0

    def to_payload(self) -> dict:
        payload = asdict(self)
        payload.setdefault("planned_demotions", list(self.planned_suppressions))
        payload.setdefault("skipped_protected_merge_pairs", [])
        payload.setdefault("skipped_protected_demotions", [])
        payload.setdefault("updated_first_chapters", {})
        payload.setdefault("updated_last_seen_chapters", {})
        payload.setdefault("pending_character_candidates_kept", 0)
        payload.setdefault("pending_relationship_candidates_suppressed", 0)
        payload.setdefault("pending_relationship_candidates_kept", 0)
        payload.setdefault("protected_manual_records_skipped", 0)
        payload.setdefault("unresolved_relationship_deltas", {})
        payload.setdefault("merged_pairs", list(self.planned_merges))
        payload.setdefault("demoted_character_ids", list(self.planned_suppressions))
        payload.setdefault("first_chapter_recomputes", {})
        payload.setdefault("last_seen_chapter_recomputes", {})
        payload.setdefault("duplicate_suggestion_delta", {})
        return payload


class CharacterIdentityRepairJob:
    def __init__(
        self,
        db: AsyncSession,
        *,
        book_id: uuid.UUID,
        repair_run_id: str | None = None,
        allow_merge_safe_pairs: bool = True,
        allow_demote_obvious_noise: bool = True,
    ) -> None:
        self.db = db
        self.book_id = book_id
        self.repair_run_id = repair_run_id or f"character-identity-repair:{book_id}"
        self.allow_merge_safe_pairs = allow_merge_safe_pairs
        self.allow_demote_obvious_noise = allow_demote_obvious_noise

    async def preview(self) -> CharacterIdentityRepairResult:
        return await self._run(dry_run=True)

    async def apply(self) -> CharacterIdentityRepairResult:
        return await self._run(dry_run=False)

    async def _load_characters(self) -> list[Character]:
        return list(
            (
                await self.db.execute(
                    select(Character)
                    .where(Character.book_id == self.book_id)
                    .order_by(Character.first_chapter, Character.name)
                )
            )
            .scalars()
            .all()
        )

    async def _run(self, *, dry_run: bool) -> CharacterIdentityRepairResult:
        result = CharacterIdentityRepairResult(
            book_id=str(self.book_id),
            dry_run=dry_run,
            allow_merge_safe_pairs=self.allow_merge_safe_pairs,
            allow_demote_obvious_noise=self.allow_demote_obvious_noise,
        )
        characters = await self._load_characters()
        result.character_labels = {str(character.id): character.name for character in characters}
        active = [
            character
            for character in characters
            if character.merged_into_character_id is None
            and character.approval_state != CHARACTER_APPROVAL_REJECTED
            and character.visibility_state != CHARACTER_VISIBILITY_NOISE
        ]

        if self.allow_merge_safe_pairs:
            await self._handle_exact_duplicates(active, result, dry_run=dry_run)
        characters = await self._load_characters()
        active = [
            character
            for character in characters
            if character.merged_into_character_id is None
            and character.approval_state != CHARACTER_APPROVAL_REJECTED
            and character.visibility_state != CHARACTER_VISIBILITY_NOISE
        ]
        if not dry_run and self.allow_merge_safe_pairs:
            assign_unique_active_normalized_names(active)
        if self.allow_merge_safe_pairs:
            await self._handle_first_name_aliases(active, result, dry_run=dry_run)
        if self.allow_demote_obvious_noise:
            await self._handle_suppressions(active, result, dry_run=dry_run)
        if self.allow_merge_safe_pairs:
            await self._handle_duplicate_suggestions(result, dry_run=dry_run)

        if not dry_run and self.allow_merge_safe_pairs:
            suggestions = await refresh_character_duplicate_suggestions(
                self.db, book_id=self.book_id
            )
            result.pending_duplicate_suggestions = sum(
                1
                for suggestion in suggestions
                if suggestion.status == CHARACTER_DUPLICATE_PENDING
                and int(suggestion.confidence or 0) >= 75
            )
        else:
            suggestions = (
                (
                    await self.db.execute(
                        select(CharacterDuplicateSuggestion).where(
                            CharacterDuplicateSuggestion.book_id == self.book_id,
                            CharacterDuplicateSuggestion.status == CHARACTER_DUPLICATE_PENDING,
                        )
                    )
                )
                .scalars()
                .all()
            )
            result.pending_duplicate_suggestions = sum(
                1 for suggestion in suggestions if int(suggestion.confidence or 0) >= 75
            )
        result.remaining_review_items = result.pending_duplicate_suggestions
        return result

    async def _handle_exact_duplicates(
        self,
        characters: list[Character],
        result: CharacterIdentityRepairResult,
        *,
        dry_run: bool,
    ) -> None:
        by_normalized: dict[str, list[Character]] = defaultdict(list)
        for character in characters:
            normalized = normalize_name(character.name)
            if normalized:
                by_normalized[normalized].append(character)

        for duplicates in by_normalized.values():
            if len(duplicates) < 2:
                continue
            ordered = sorted(
                duplicates,
                key=lambda item: (int(item.mention_count or 0), -int(item.first_chapter or 0)),
                reverse=True,
            )
            primary = ordered[0]
            for secondary in ordered[1:]:
                if is_protected_character(primary) or is_protected_character(secondary):
                    continue
                if await has_blocking_identity_constraint(
                    self.db,
                    book_id=self.book_id,
                    left_character_id=primary.id,
                    right_character_id=secondary.id,
                ):
                    continue
                result.planned_merges.append((str(primary.id), str(secondary.id)))
                result.auto_merged += 1
                if dry_run:
                    continue
                await merge_characters(self.db, primary.id, secondary.id, self.book_id)

    async def _handle_first_name_aliases(
        self,
        characters: list[Character],
        result: CharacterIdentityRepairResult,
        *,
        dry_run: bool,
    ) -> None:
        full_name_by_first: dict[str, list[Character]] = defaultdict(list)
        single_token: list[Character] = []
        for character in characters:
            normalized_tokens = normalize_name(character.name).split()
            if len(normalized_tokens) == 1:
                single_token.append(character)
            elif len(normalized_tokens) >= 2:
                full_name_by_first[normalized_tokens[0]].append(character)

        for alias_character in single_token:
            token = first_name_token(alias_character.name)
            matches = full_name_by_first.get(token) or []
            if not matches or is_protected_character(alias_character):
                continue
            target = sorted(matches, key=lambda item: int(item.mention_count or 0), reverse=True)[0]
            if is_protected_character(target):
                continue
            if int(target.mention_count or 0) < int(alias_character.mention_count or 0):
                continue
            if await has_blocking_identity_constraint(
                self.db,
                book_id=self.book_id,
                left_character_id=alias_character.id,
                right_character_id=target.id,
            ):
                continue
            result.planned_aliases.append((str(alias_character.id), str(target.id)))
            result.auto_aliases += 1
            if dry_run:
                continue
            await add_character_alias(
                self.db,
                character=target,
                alias_text=alias_character.name,
                alias_kind="first_name",
                source="repair",
                confidence=0.9,
                repair_run_id=self.repair_run_id,
            )
            alias_character.merged_into_character_id = target.id
            alias_character.is_auto_suppressed = True
            alias_character.suppression_reason = "single_token_first_name_alias"
            set_character_review_state(
                alias_character,
                visibility_state=CHARACTER_VISIBILITY_NOISE,
                approval_state=CHARACTER_APPROVAL_REJECTED,
                approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
                reason_codes=["single_token_first_name_alias"],
                action="character_auto_alias_suppressed",
                details={"target_character_id": str(target.id)},
            )
            mention_rows = (
                (
                    await self.db.execute(
                        select(CharacterMention).where(
                            CharacterMention.book_id == self.book_id,
                            CharacterMention.matched_character_id == alias_character.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for mention in mention_rows:
                mention.matched_character_id = target.id
            await record_identity_action(
                self.db,
                book_id=self.book_id,
                action_type="auto_alias",
                source_character_id=alias_character.id,
                target_character_id=target.id,
                surface_text=alias_character.name,
                confidence=0.9,
                reason="single_token_first_name_alias",
                reversible=True,
                repair_run_id=self.repair_run_id,
            )

    async def _handle_suppressions(
        self,
        characters: list[Character],
        result: CharacterIdentityRepairResult,
        *,
        dry_run: bool,
    ) -> None:
        for character in characters:
            if is_protected_character(character):
                continue
            adjudication = adjudicate_character_candidate(
                character.name,
                aliases=character.aliases or [],
                evidence={
                    "mention_count": character.mention_count,
                    "has_physical_description": bool(
                        character.trait_state
                        or character.hair
                        or character.eyes
                        or character.build
                        or character.age_descriptor
                        or character.distinguishing
                    ),
                },
            )
            kind = classify_candidate_kind(character.name)
            reason = ""
            if (
                adjudication.adjudication_status
                in {
                    ADJUDICATION_PLACE,
                    ADJUDICATION_ORGANIZATION,
                    ADJUDICATION_OBJECT,
                    ADJUDICATION_TITLE_OR_ROLE,
                }
                or adjudication.entity_type == ENTITY_JUNK
            ):
                reason = f"{adjudication.adjudication_status}_adjudicated"
            elif (
                adjudication.adjudication_status == ADJUDICATION_QUARANTINED
                and adjudication.entity_type != ENTITY_PERSON
            ):
                reason = "adjudication_quarantined_for_review"
            elif kind == CandidateKind.FRAGMENT:
                reason = "title_only_fragment_suppressed"
            elif (
                kind == CandidateKind.KINSHIP_DESCRIPTOR
                and family_role_reference(character.name)[1]
            ):
                reason = "kinship_descriptor_unresolved_suppressed"
            elif kind in {CandidateKind.GROUP_DESCRIPTOR, CandidateKind.OBJECT_OR_PLACE}:
                reason = f"{kind.value}_suppressed"
            elif kind == CandidateKind.ROLE_DESCRIPTOR and int(character.mention_count or 0) <= 2:
                reason = "role_descriptor_low_evidence_suppressed"
            if not reason:
                continue
            result.planned_suppressions.append(str(character.id))
            result.auto_suppressed += 1
            if dry_run:
                continue
            if reason == "adjudication_quarantined_for_review":
                set_character_review_state(
                    character,
                    visibility_state=CHARACTER_VISIBILITY_QUARANTINED,
                    approval_state=CHARACTER_APPROVAL_PENDING_REVIEW,
                    approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
                    reason_codes=[reason, *list(adjudication.reason_codes)],
                    action="character_adjudication_quarantined",
                    details={
                        "adjudication_status": adjudication.adjudication_status,
                        "entity_type": adjudication.entity_type,
                        "character_score": adjudication.character_score,
                    },
                )
                continue
            character.is_auto_suppressed = True
            character.suppression_reason = reason
            set_character_review_state(
                character,
                visibility_state=CHARACTER_VISIBILITY_NOISE,
                approval_state=CHARACTER_APPROVAL_REJECTED,
                approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
                reason_codes=[reason, *list(adjudication.reason_codes)],
                action="character_auto_suppressed",
                details={
                    "candidate_kind": kind.value,
                    "adjudication_status": adjudication.adjudication_status,
                    "entity_type": adjudication.entity_type,
                    "character_score": adjudication.character_score,
                },
            )
            await suppress_candidate(
                self.db,
                book_id=self.book_id,
                character_id=character.id,
                surface_text=character.name,
                candidate_kind=adjudication.entity_type or kind.value,
                reason=reason,
                confidence=0.9,
                repair_run_id=self.repair_run_id,
            )

    async def _handle_duplicate_suggestions(
        self,
        result: CharacterIdentityRepairResult,
        *,
        dry_run: bool,
    ) -> None:
        suggestions = (
            (
                await self.db.execute(
                    select(CharacterDuplicateSuggestion).where(
                        CharacterDuplicateSuggestion.book_id == self.book_id,
                        CharacterDuplicateSuggestion.status == CHARACTER_DUPLICATE_PENDING,
                    )
                )
            )
            .scalars()
            .all()
        )
        character_map = {character.id: character for character in await self._load_characters()}
        for suggestion in suggestions:
            primary = character_map.get(suggestion.primary_character_id)
            secondary = character_map.get(suggestion.secondary_character_id)
            confidence = int(suggestion.confidence or 0)
            reason = ""
            if confidence < 75:
                reason = "low_confidence_duplicate_suggestion"
            elif (
                primary
                and secondary
                and has_conflicting_title_identity(primary.name, secondary.name)
            ):
                reason = "conflicting_title_identity"
            if not reason:
                continue
            result.blocked_suggestions += 1
            result.blocked_duplicate_suggestions.append(str(suggestion.id))
            if dry_run:
                continue
            suggestion.status = CHARACTER_DUPLICATE_DISMISSED
            suggestion.dismissal_reason = reason
            suggestion.auto_dismissed = True
            if primary and secondary:
                await add_identity_constraint(
                    self.db,
                    book_id=self.book_id,
                    left_character_id=primary.id,
                    right_character_id=secondary.id,
                    left_text=primary.name,
                    right_text=secondary.name,
                    constraint_type="not_same_character"
                    if reason == "conflicting_title_identity"
                    else "blocked_merge",
                    reason=reason,
                    source="repair",
                    confidence=1.0 if reason == "conflicting_title_identity" else 0.75,
                    repair_run_id=self.repair_run_id,
                )
