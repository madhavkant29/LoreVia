"""Focused character merging workflows."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.character.profile_builder import (
    merge_profile_fields,
)
from app.models.character import (
    Character,
    CharacterAlias,
    CharacterDuplicateSuggestion,
    CharacterIdentityConstraint,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterState,
    CharacterSuppression,
    CharacterVoiceProfile,
)
from app.models.intelligence import (
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
    WikiEntry,
)
from app.services.character_identity.merge import record_identity_action
from app.utils.characters.classification import (
    update_character_classification,
)
from app.utils.characters.constants import (
    CHARACTER_APPROVAL_APPROVED,
    CHARACTER_APPROVAL_PENDING_REVIEW,
    CHARACTER_APPROVAL_PROTECTED,
    CHARACTER_APPROVAL_REJECTED,
    CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
    CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW,
    CHARACTER_DUPLICATE_ACCEPTED,
    CHARACTER_RELATIONSHIP_CANDIDATE_MERGED,
    CHARACTER_RELATIONSHIP_CANDIDATE_PENDING,
    CHARACTER_VISIBILITY_NOISE,
    CHARACTER_VISIBILITY_QUARANTINED,
    CHARACTER_VISIBILITY_VISIBLE,
)
from app.utils.characters.governance import (
    character_governance,
)
from app.utils.characters.identity import (
    normalize_character_name,
)
from app.utils.characters.manual import (
    _character_reference_values,
    _manual_character_description_value,
    _merge_character_descriptions,
    _normalize_character_reference,
    _replace_reference_list,
    apply_manual_character_description,
)
from app.utils.characters.review import (
    set_character_review_state,
)
from app.utils.relationship_utils import (
    repair_relationship_timelines,
)


def _merge_voice_profiles(
    primary_profile: CharacterVoiceProfile | None, secondary_profile: CharacterVoiceProfile | None
) -> None:
    if primary_profile is None or secondary_profile is None:
        return
    primary_profile.sample_dialogue_count = int(primary_profile.sample_dialogue_count or 0) + int(
        secondary_profile.sample_dialogue_count or 0
    )
    primary_profile.sample_word_count = int(primary_profile.sample_word_count or 0) + int(
        secondary_profile.sample_word_count or 0
    )
    for field_name in (
        "avg_sentence_length",
        "avg_word_length_x100",
        "contraction_rate_x1000",
        "question_rate_x1000",
        "exclamation_rate_x1000",
        "ellipsis_rate_x1000",
        "dash_rate_x1000",
        "uppercase_rate_x1000",
        "formality_score_x1000",
        "lexical_complexity_x1000",
        "emotional_intensity_x1000",
    ):
        if getattr(primary_profile, field_name) is None:
            setattr(primary_profile, field_name, getattr(secondary_profile, field_name))
    if not primary_profile.dominant_markers and secondary_profile.dominant_markers:
        primary_profile.dominant_markers = secondary_profile.dominant_markers
    if not primary_profile.signature_phrases and secondary_profile.signature_phrases:
        primary_profile.signature_phrases = secondary_profile.signature_phrases


async def _merge_character_references(
    db: AsyncSession,
    *,
    primary: Character,
    secondary: Character,
    book_id: uuid.UUID,
) -> None:
    reference_values = _character_reference_values(secondary)

    plot_threads = (
        (await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))).scalars().all()
    )
    for thread in plot_threads:
        updated_ids = _replace_reference_list(
            thread.character_ids, matches=reference_values, replacement=primary.name
        )
        if updated_ids:
            thread.character_ids = updated_ids

    wiki_entries = (
        (await db.execute(select(WikiEntry).where(WikiEntry.book_id == book_id))).scalars().all()
    )
    for entry in wiki_entries:
        related = _replace_reference_list(
            entry.related_char_ids, matches=reference_values, replacement=str(primary.id)
        )
        if related:
            entry.related_char_ids = related

    chapter_summaries = (
        (
            await db.execute(
                select(ChapterSummary)
                .join(ChapterSummary.chapter)
                .where(ChapterSummary.chapter.has(book_id=book_id))
            )
        )
        .scalars()
        .all()
    )
    for summary in chapter_summaries:
        key_events = [
            dict(event) if isinstance(event, dict) else event
            for event in (summary.key_events or [])
        ]
        changed = False
        for event in key_events:
            if not isinstance(event, dict):
                continue
            involved = _replace_reference_list(
                event.get("involved_characters"),
                matches=reference_values,
                replacement=str(primary.id),
            )
            if involved != list(event.get("involved_characters") or []):
                event["involved_characters"] = involved
                changed = True
        if changed:
            summary.key_events = key_events

        char_changes = [
            dict(change) if isinstance(change, dict) else change
            for change in (summary.char_changes or [])
        ]
        char_change_changed = False
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            candidate = " ".join(str(change.get("character") or "").split()).strip()
            if candidate and _normalize_character_reference(candidate) in reference_values:
                change["character"] = primary.name
                char_change_changed = True
        if char_change_changed:
            summary.char_changes = char_changes

    quotes = (
        (await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == book_id))).scalars().all()
    )
    for quote in quotes:
        if _normalize_character_reference(quote.character_name) in reference_values:
            quote.character_name = primary.name

    relationship_candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book_id
                )
            )
        )
        .scalars()
        .all()
    )
    for candidate in relationship_candidates:
        changed = False
        if candidate.matched_character_a_id == secondary.id:
            candidate.matched_character_a_id = primary.id
            changed = True
        if candidate.matched_character_b_id == secondary.id:
            candidate.matched_character_b_id = primary.id
            changed = True
        if changed and candidate.status == CHARACTER_RELATIONSHIP_CANDIDATE_PENDING:
            candidate.status = CHARACTER_RELATIONSHIP_CANDIDATE_MERGED


async def merge_characters(
    db: AsyncSession,
    primary_id: uuid.UUID,
    secondary_id: uuid.UUID,
    book_id: uuid.UUID,
) -> Character:
    """Merge duplicate character records and preserve aliases / references."""
    characters = (
        (
            await db.execute(
                select(Character)
                .options(selectinload(Character.voice_profile))
                .where(Character.id.in_([primary_id, secondary_id]))
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    characters_by_id = {character.id: character for character in characters}
    primary = characters_by_id.get(primary_id)
    secondary = characters_by_id.get(secondary_id)
    if not primary or not secondary:
        raise ValueError("Character not found")
    if primary.book_id != book_id or secondary.book_id != book_id:
        raise ValueError("Characters must belong to the same book")
    if primary.id == secondary.id:
        return primary
    primary_visibility, primary_approval, primary_source, primary_reason_codes = (
        character_governance(primary)
    )
    secondary_visibility, secondary_approval, secondary_source, secondary_reason_codes = (
        character_governance(secondary)
    )

    merged = merge_profile_fields(primary, secondary)
    merged_manual_description = _merge_character_descriptions(
        _manual_character_description_value(primary.trait_state),
        _manual_character_description_value(secondary.trait_state),
    )
    primary.aliases = merged["aliases"]
    primary.normalized_name = normalize_character_name(primary.name) or None
    primary.role = merged["role"]
    primary.first_chapter = merged["first_chapter"]
    primary.last_seen_chapter = merged["last_seen_chapter"]
    primary.mention_count = (primary.mention_count or 0) + (secondary.mention_count or 0)
    primary.trait_state = merged["trait_state"]
    if merged_manual_description:
        apply_manual_character_description(primary, merged_manual_description)
    primary.hair = merged["hair"]
    primary.eyes = merged["eyes"]
    primary.build = merged["build"]
    primary.age_descriptor = merged["age_descriptor"]
    primary.distinguishing = merged["distinguishing"]
    primary.personality_tags = merged["personality_tags"]
    primary.goal = merged["goal"]
    primary.motivations = merged["motivations"]
    primary.fears = merged["fears"]
    primary.lie_they_believe = merged["lie_they_believe"]
    primary.backstory_wound = merged["backstory_wound"]
    primary.arc_type = merged["arc_type"]
    primary.arc_summary = merged["arc_summary"]
    primary.archetype = merged["archetype"]
    primary.growth_events = merged["growth_events"]
    if primary.embedding is None and secondary.embedding is not None:
        primary.embedding = secondary.embedding
    if primary.voice_profile and secondary.voice_profile:
        _merge_voice_profiles(primary.voice_profile, secondary.voice_profile)
        # Detach the secondary profile and let delete-orphan remove it once.
        secondary.voice_profile = None
    elif primary.voice_profile is None and secondary.voice_profile is not None:
        moved_voice_profile = secondary.voice_profile
        secondary.voice_profile = None
        primary.voice_profile = moved_voice_profile
        moved_voice_profile.book_id = primary.book_id

    state_rows_result = await db.execute(
        select(CharacterState).where(CharacterState.character_id == secondary.id)
    )
    state_rows = state_rows_result.scalars().all()
    for state in state_rows:
        existing_state = (
            await db.execute(
                select(CharacterState).where(
                    CharacterState.character_id == primary.id,
                    CharacterState.at_chapter == state.at_chapter,
                )
            )
        ).scalar()
        if existing_state:
            existing_state.trait_snapshot = state.trait_snapshot or existing_state.trait_snapshot
            if state.motivations_snapshot and not existing_state.motivations_snapshot:
                existing_state.motivations_snapshot = state.motivations_snapshot
            if state.fears_snapshot and not existing_state.fears_snapshot:
                existing_state.fears_snapshot = state.fears_snapshot
            if state.prompt_delta and not existing_state.prompt_delta:
                existing_state.prompt_delta = state.prompt_delta
            if state.arc_note and not existing_state.arc_note:
                existing_state.arc_note = state.arc_note
            if state.growth_event and not existing_state.growth_event:
                existing_state.growth_event = state.growth_event
            await db.delete(state)
        else:
            state.character_id = primary.id

    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            or_(
                CharacterRelationship.character_a_id == secondary.id,
                CharacterRelationship.character_b_id == secondary.id,
            ),
        )
    )
    rels = rels_result.scalars().all()
    for rel in rels:
        if rel.character_a_id == secondary.id:
            rel.character_a_id = primary.id
        if rel.character_b_id == secondary.id:
            rel.character_b_id = primary.id
        if rel.character_a_id == rel.character_b_id:
            await db.delete(rel)

    await _merge_character_references(db, primary=primary, secondary=secondary, book_id=book_id)
    mention_rows = (
        (
            await db.execute(
                select(CharacterMention).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.matched_character_id == secondary.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for mention in mention_rows:
        mention.matched_character_id = primary.id

    alias_rows = (
        (
            await db.execute(
                select(CharacterAlias).where(
                    CharacterAlias.book_id == book_id,
                    CharacterAlias.character_id == secondary.id,
                )
            )
        )
        .scalars()
        .all()
    )
    existing_primary_aliases = {
        normalize_character_name(alias.alias_text)
        for alias in (
            await db.execute(
                select(CharacterAlias).where(
                    CharacterAlias.book_id == book_id,
                    CharacterAlias.character_id == primary.id,
                )
            )
        )
        .scalars()
        .all()
    }
    for alias in alias_rows:
        if alias.normalized_alias in existing_primary_aliases:
            await db.delete(alias)
        else:
            alias.character_id = primary.id
            existing_primary_aliases.add(alias.normalized_alias)

    suppression_rows = (
        (
            await db.execute(
                select(CharacterSuppression).where(
                    CharacterSuppression.book_id == book_id,
                    CharacterSuppression.character_id == secondary.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for suppression in suppression_rows:
        suppression.character_id = primary.id

    constraint_rows = (
        (
            await db.execute(
                select(CharacterIdentityConstraint).where(
                    CharacterIdentityConstraint.book_id == book_id,
                    or_(
                        CharacterIdentityConstraint.left_character_id == secondary.id,
                        CharacterIdentityConstraint.right_character_id == secondary.id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    for constraint in constraint_rows:
        if constraint.left_character_id == secondary.id:
            constraint.left_character_id = primary.id
            constraint.left_text = primary.name
        if constraint.right_character_id == secondary.id:
            constraint.right_character_id = primary.id
            constraint.right_text = primary.name
        if constraint.left_character_id == constraint.right_character_id:
            await db.delete(constraint)

    suggestion_rows = (
        (
            await db.execute(
                select(CharacterDuplicateSuggestion).where(
                    CharacterDuplicateSuggestion.book_id == book_id,
                    or_(
                        CharacterDuplicateSuggestion.primary_character_id == secondary.id,
                        CharacterDuplicateSuggestion.secondary_character_id == secondary.id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    for suggestion in suggestion_rows:
        next_primary_id = (
            primary.id
            if suggestion.primary_character_id == secondary.id
            else suggestion.primary_character_id
        )
        next_secondary_id = (
            primary.id
            if suggestion.secondary_character_id == secondary.id
            else suggestion.secondary_character_id
        )
        if next_primary_id == next_secondary_id:
            suggestion.status = CHARACTER_DUPLICATE_ACCEPTED
            continue
        existing_conflict = (
            await db.execute(
                select(CharacterDuplicateSuggestion).where(
                    CharacterDuplicateSuggestion.book_id == book_id,
                    CharacterDuplicateSuggestion.id != suggestion.id,
                    CharacterDuplicateSuggestion.primary_character_id == next_primary_id,
                    CharacterDuplicateSuggestion.secondary_character_id == next_secondary_id,
                )
            )
        ).scalar_one_or_none()
        if existing_conflict is not None:
            await db.delete(suggestion)
            continue
        suggestion.primary_character_id = next_primary_id
        suggestion.secondary_character_id = next_secondary_id

    await _dedupe_relationships(db, book_id)
    if (
        primary_approval == CHARACTER_APPROVAL_PROTECTED
        or secondary_approval == CHARACTER_APPROVAL_PROTECTED
    ):
        merged_visibility = CHARACTER_VISIBILITY_VISIBLE
        merged_approval = CHARACTER_APPROVAL_PROTECTED
        merged_source = CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
    elif (
        primary_visibility == CHARACTER_VISIBILITY_VISIBLE
        or secondary_visibility == CHARACTER_VISIBILITY_VISIBLE
    ):
        merged_visibility = CHARACTER_VISIBILITY_VISIBLE
        merged_approval = CHARACTER_APPROVAL_APPROVED
        merged_source = (
            primary_source or secondary_source or CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
        )
    else:
        merged_visibility = CHARACTER_VISIBILITY_QUARANTINED
        merged_approval = CHARACTER_APPROVAL_PENDING_REVIEW
        merged_source = (
            primary_source or secondary_source or CHARACTER_APPROVAL_SOURCE_MANUAL_REVIEW
        )
    set_character_review_state(
        primary,
        visibility_state=merged_visibility,
        approval_state=merged_approval,
        approval_source=merged_source,
        reason_codes=[*primary_reason_codes, *secondary_reason_codes, "merged_character_record"],
        action="character_merged",
        details={"secondary_character_id": str(secondary.id)},
    )
    secondary.merged_into_character_id = primary.id
    secondary.normalized_name = None
    secondary.is_auto_suppressed = True
    secondary.suppression_reason = "merged_character_record"
    set_character_review_state(
        secondary,
        visibility_state=CHARACTER_VISIBILITY_NOISE,
        approval_state=CHARACTER_APPROVAL_REJECTED,
        approval_source=CHARACTER_APPROVAL_SOURCE_DETERMINISTIC_AUTO,
        reason_codes=["merged_into_character", *secondary_reason_codes],
        action="character_soft_merged",
        details={"primary_character_id": str(primary.id)},
    )
    await record_identity_action(
        db,
        book_id=book_id,
        action_type="auto_merge",
        source_character_id=secondary.id,
        target_character_id=primary.id,
        surface_text=secondary.name,
        confidence=0.95,
        reason="merged_character_record",
        reversible=True,
        reversible_data={
            "secondary_name": secondary.name,
            "secondary_aliases": secondary.aliases or [],
            "secondary_visibility_state": secondary_visibility,
            "secondary_approval_state": secondary_approval,
        },
    )
    await db.flush()
    update_character_classification(primary)
    return primary


async def _dedupe_relationships(db: AsyncSession, book_id: uuid.UUID) -> None:
    await repair_relationship_timelines(db, book_id=book_id)
