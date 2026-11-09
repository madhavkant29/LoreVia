import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.engine.character.adjudicator import (
    ADJUDICATION_PROMOTED_CHARACTER,
    adjudicate_character_candidate,
)
from app.models.character import Character, CharacterCandidate
from app.services.character_identity.resolver import resolve_character_mention
from app.services.extraction_character_cache_service import (
    _find_character_ids_in_cache,
    _refresh_character_key_cache,
)
from app.services.extraction_character_decision_service import (
    _can_auto_save_character,
    _can_update_exact_existing_profile,
    _candidate_record_evidence,
    _character_save_decision,
    _entity_requires_manual_review,
    _record_character_disposition_candidate,
    _should_update_existing_character,
    load_author_review_holds,
)
from app.services.extraction_character_persistence_service import (
    _accept_existing_character_match,
    _blocked_character_ids,
    _record_cluster_member_candidates,
    _record_entity_cluster_mentions,
)
from app.services.extraction_new_character_resolution_service import (
    promote_or_match_new_character_entities,
)
from app.utils.characters.constants import CHARACTER_CANDIDATE_SUPPRESSED
from app.utils.characters.cross_chapter import combine_exact_name_chapter_evidence
from app.utils.characters.extraction import (
    cluster_character_entities,
    resolve_character_reference_from_roster,
)
from app.utils.characters.governance import is_cast_visible_character
from app.utils.characters.identity import normalize_character_name


@dataclass(slots=True)
class ChapterCharacterResolutionResult:
    aggregated_entities: list[dict[str, Any]]
    saved_character_count: int
    quarantined_candidate_count: int
    ambiguous_entity_count: int
    strict_hold_count: int
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]]
    pending_first_chapter_updates: dict[uuid.UUID, Character]


async def resolve_chapter_character_entities(
    db,
    *,
    book,
    chapter_number: int,
    existing_characters: list[Character],
    character_key_cache: dict[uuid.UUID, set[str]],
    raw_character_entities: list[dict[str, Any]],
    aggregated_entities: list[dict[str, Any]] | None = None,
    precomputed_embeddings: list[list[float]],
) -> ChapterCharacterResolutionResult:
    if aggregated_entities is None:
        aggregated_entities = cluster_character_entities(raw_character_entities)
    if len(precomputed_embeddings) != len(aggregated_entities):
        raise RuntimeError("character_embedding_result_incomplete")
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]] = {}
    pending_first_chapter_updates: dict[uuid.UUID, Character] = {}
    saved_character_count = 0
    quarantined_candidate_count = 0
    ambiguous_entity_count = 0
    strict_hold_count = 0
    author_review_holds = await load_author_review_holds(db, book_id=book.id, chapter_number=None)

    pending_new_entities: list[tuple[dict[str, Any], set[uuid.UUID], str | None, list[float]]] = []
    for entity, precomputed_embedding in zip(aggregated_entities, precomputed_embeddings):
        # These IDs are assigned only after reading verified rows below. Never
        # accept candidate links supplied by an extraction response.
        raw_evidence = entity.get("evidence")
        if isinstance(raw_evidence, dict) and "cross_chapter_candidate_ids" in raw_evidence:
            clean_evidence = dict(raw_evidence)
            clean_evidence.pop("cross_chapter_candidate_ids", None)
            entity = {**entity, "evidence": clean_evidence}
        cluster_members = (
            entity.get("cluster_members") if isinstance(entity.get("cluster_members"), list) else []
        )
        entity_source_batch_key = next(
            (
                str(member.get("source_batch_key") or "")
                for member in cluster_members
                if str(member.get("source_batch_key") or "").strip()
            ),
            None,
        )
        author_hold = author_review_holds.get(normalize_character_name(entity.get("name")))
        if author_hold:
            quarantined_candidate_count += 1
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                resolver_status="held_for_review"
                if author_hold == "manual_demoted_for_review"
                else "suppressed",
                resolver_reasons=[author_hold],
            )
            continue
        entity_evidence = entity.get("evidence")
        if (
            isinstance(entity_evidence, dict)
            and entity_evidence.get("profile_enrichment_status") == "unanchored_reference"
        ):
            # Discovery may propose an identity absent from its source batch.
            # Retain the proposal for diagnostics, but do not attach a fabricated
            # mention or update a previously grounded character.
            quarantined_candidate_count += 1
            strict_hold_count += 1
            await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                reason_codes=["unanchored_character_reference"],
                source_batch_key=entity_source_batch_key,
            )
            continue
        context_text = "\n\n".join(
            str(member.get("source_text") or "").strip()
            for member in cluster_members[:3]
            if str(member.get("source_text") or "").strip()
        )
        blocked_ids = _blocked_character_ids(
            existing_characters, entity, key_cache=character_key_cache
        )
        matching_ids = _find_character_ids_in_cache(
            existing_characters,
            str(entity.get("name") or ""),
            entity.get("aliases", []),
            blocked_ids=blocked_ids,
            key_cache=character_key_cache,
        )
        if len(matching_ids) != 1 and context_text:
            resolver_match = resolve_character_reference_from_roster(
                [char for char in existing_characters if char.id not in blocked_ids],
                str(entity.get("name") or ""),
                context_text=context_text,
            )
            if resolver_match is not None:
                matching_ids = [resolver_match.id]

        existing_id = matching_ids[0] if len(matching_ids) == 1 else None
        decision = _character_save_decision(entity)
        manual_review_reason = _entity_requires_manual_review(entity)
        existing_match = (
            next((item for item in existing_characters if item.id == existing_id), None)
            if existing_id is not None
            else None
        )
        identity_resolution = await resolve_character_mention(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            surface_text=str(entity.get("name") or ""),
            evidence=_candidate_record_evidence(entity),
        )
        if identity_resolution.action == "auto_suppress":
            quarantined_candidate_count += 1
            await _record_cluster_member_candidates(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                reason_code=identity_resolution.reason,
                status=CHARACTER_CANDIDATE_SUPPRESSED,
            )
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                resolver_status="suppressed",
                resolver_reasons=[identity_resolution.reason],
            )
            continue
        if identity_resolution.reason == "single_token_alias_link_unverified":
            quarantined_candidate_count += 1
            strict_hold_count += 1
            status, reasons, _evidence = await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                reason_codes=[identity_resolution.reason],
                source_batch_key=entity_source_batch_key,
            )
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                resolver_status="suppressed"
                if status == CHARACTER_CANDIDATE_SUPPRESSED
                else "held_for_review",
                resolver_reasons=reasons,
            )
            continue
        if (
            identity_resolution.action in {"auto_alias", "auto_merge"}
            and identity_resolution.target_character_id
        ):
            resolved_target = next(
                (
                    item
                    for item in existing_characters
                    if item.id == identity_resolution.target_character_id
                ),
                None,
            )
            if resolved_target is None:
                resolved_target = await db.get(Character, identity_resolution.target_character_id)
                if resolved_target is not None and resolved_target.book_id == book.id:
                    existing_characters.append(resolved_target)
                    _refresh_character_key_cache(character_key_cache, resolved_target)
            if resolved_target is not None and resolved_target.book_id == book.id:
                if not is_cast_visible_character(resolved_target):
                    quarantined_candidate_count += 1
                    (
                        status,
                        resolved_reasons,
                        _evidence,
                    ) = await _record_character_disposition_candidate(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=resolved_target.id,
                        reason_codes=["matched_quarantined_character", identity_resolution.reason],
                        source_batch_key=entity_source_batch_key,
                    )
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=resolved_target.id,
                        resolver_status="suppressed"
                        if status == CHARACTER_CANDIDATE_SUPPRESSED
                        else "matched_needs_review",
                        resolver_reasons=resolved_reasons,
                    )
                    continue
                accepted = await _accept_existing_character_match(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    existing_id=resolved_target.id,
                    existing_characters=existing_characters,
                    character_key_cache=character_key_cache,
                    pending_first_chapter_candidates=pending_first_chapter_candidates,
                    pending_first_chapter_updates=pending_first_chapter_updates,
                    reason_code=identity_resolution.reason,
                    source_batch_key=entity_source_batch_key,
                )
                if accepted:
                    saved_character_count += 1
                    await _record_entity_cluster_mentions(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=resolved_target.id,
                        resolver_status=identity_resolution.action,
                        resolver_reasons=[identity_resolution.reason],
                    )
                    await _record_cluster_member_candidates(
                        db,
                        book_id=book.id,
                        chapter_number=chapter_number,
                        entity=entity,
                        matched_character_id=resolved_target.id,
                        reason_code=identity_resolution.reason,
                    )
                continue

        if len(matching_ids) > 1:
            ambiguous_entity_count += 1
            quarantined_candidate_count += 1
            status, reasons, _evidence = await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                reason_codes=["ambiguous_roster_match"],
                source_batch_key=entity_source_batch_key,
            )
            await _record_cluster_member_candidates(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                reason_code="ambiguous_roster_match",
                status=status,
            )
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                resolver_status="suppressed"
                if status == CHARACTER_CANDIDATE_SUPPRESSED
                else "ambiguous",
                resolver_reasons=reasons,
            )
            continue

        if existing_id is not None:
            if existing_match is not None and not is_cast_visible_character(existing_match):
                reasons = ["matched_quarantined_character", *list(decision.reasons or [])]
                quarantined_candidate_count += 1
                (
                    status,
                    resolved_reasons,
                    _evidence,
                ) = await _record_character_disposition_candidate(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    reason_codes=reasons,
                    source_batch_key=entity_source_batch_key,
                )
                await _record_entity_cluster_mentions(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    resolver_status="suppressed"
                    if status == CHARACTER_CANDIDATE_SUPPRESSED
                    else "matched_needs_review",
                    resolver_reasons=resolved_reasons,
                )
                continue
            exact_profile_update = (
                existing_match is not None
                and _can_update_exact_existing_profile(entity, existing_match.name)
            )
            if not exact_profile_update and (
                not decision.allowed or not _should_update_existing_character(entity)
            ):
                reasons = list(decision.reasons or []) or ["existing_match_needs_review"]
                if manual_review_reason and manual_review_reason not in reasons:
                    reasons.append(manual_review_reason)
                if manual_review_reason:
                    strict_hold_count += 1
                quarantined_candidate_count += 1
                (
                    status,
                    resolved_reasons,
                    _evidence,
                ) = await _record_character_disposition_candidate(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    reason_codes=reasons,
                    source_batch_key=entity_source_batch_key,
                )
                await _record_entity_cluster_mentions(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    resolver_status="suppressed"
                    if status == CHARACTER_CANDIDATE_SUPPRESSED
                    else "matched_needs_review",
                    resolver_reasons=resolved_reasons,
                )
                continue

            accepted = await _accept_existing_character_match(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                existing_id=existing_id,
                existing_characters=existing_characters,
                character_key_cache=character_key_cache,
                pending_first_chapter_candidates=pending_first_chapter_candidates,
                pending_first_chapter_updates=pending_first_chapter_updates,
                reason_code="matched_existing_character",
                source_batch_key=entity_source_batch_key,
            )
            if accepted:
                saved_character_count += 1
                await _record_entity_cluster_mentions(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    resolver_status="matched_existing",
                    resolver_reasons=["matched_existing_character"],
                )
                await _record_cluster_member_candidates(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    reason_code="matched_existing_character",
                )
            continue

        chapter_entity = entity
        prior_candidates = (
            (
                await db.execute(
                    select(CharacterCandidate).where(
                        CharacterCandidate.book_id == book.id,
                        CharacterCandidate.normalized_name
                        == normalize_character_name(entity.get("name")),
                        CharacterCandidate.chapter_number != chapter_number,
                    )
                )
            )
            .scalars()
            .all()
        )
        entity = combine_exact_name_chapter_evidence(
            entity,
            chapter_number=chapter_number,
            prior_candidates=prior_candidates,
        )
        decision = _character_save_decision(entity)
        manual_review_reason = _entity_requires_manual_review(entity)

        if not decision.allowed or manual_review_reason or not _can_auto_save_character(entity):
            reasons = list(decision.reasons or []) or ["low_confidence_needs_review"]
            if manual_review_reason and manual_review_reason not in reasons:
                reasons.append(manual_review_reason)
            if manual_review_reason:
                strict_hold_count += 1
            quarantined_candidate_count += 1
            status, resolved_reasons, _evidence = await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=chapter_entity,
                matched_character_id=None,
                reason_codes=reasons,
                source_batch_key=entity_source_batch_key,
            )
            await _record_cluster_member_candidates(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=chapter_entity,
                matched_character_id=None,
                reason_code=resolved_reasons[0] if resolved_reasons else reasons[0],
                status=status,
            )
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=chapter_entity,
                matched_character_id=None,
                resolver_status="suppressed"
                if status == CHARACTER_CANDIDATE_SUPPRESSED
                else "held_for_review",
                resolver_reasons=resolved_reasons,
            )
            continue

        promotion_adjudication = adjudicate_character_candidate(
            str(entity.get("name") or ""),
            aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            confidence=entity.get("confidence"),
            evidence=_candidate_record_evidence(entity),
            reason_codes=decision.reasons,
        )
        if promotion_adjudication.adjudication_status != ADJUDICATION_PROMOTED_CHARACTER:
            quarantined_candidate_count += 1
            status, resolved_reasons, _evidence = await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=chapter_entity,
                matched_character_id=None,
                reason_codes=[
                    "adjudication_requires_review",
                    *list(promotion_adjudication.reason_codes),
                ],
                source_batch_key=entity_source_batch_key,
            )
            await _record_cluster_member_candidates(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=chapter_entity,
                matched_character_id=None,
                reason_code=resolved_reasons[0]
                if resolved_reasons
                else "adjudication_requires_review",
                status=status,
            )
            await _record_entity_cluster_mentions(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=chapter_entity,
                matched_character_id=None,
                resolver_status="suppressed"
                if status == CHARACTER_CANDIDATE_SUPPRESSED
                else "held_for_review",
                resolver_reasons=resolved_reasons,
            )
            continue

        pending_new_entities.append(
            (entity, blocked_ids, entity_source_batch_key, precomputed_embedding)
        )

    new_character_resolution = await promote_or_match_new_character_entities(
        db,
        book=book,
        chapter_number=chapter_number,
        existing_characters=existing_characters,
        character_key_cache=character_key_cache,
        pending_first_chapter_candidates=pending_first_chapter_candidates,
        pending_first_chapter_updates=pending_first_chapter_updates,
        pending_new_entities=pending_new_entities,
        saved_character_count=saved_character_count,
        quarantined_candidate_count=quarantined_candidate_count,
        ambiguous_entity_count=ambiguous_entity_count,
    )
    saved_character_count = new_character_resolution.saved_character_count
    quarantined_candidate_count = new_character_resolution.quarantined_candidate_count
    ambiguous_entity_count = new_character_resolution.ambiguous_entity_count

    return ChapterCharacterResolutionResult(
        aggregated_entities=aggregated_entities,
        saved_character_count=saved_character_count,
        quarantined_candidate_count=quarantined_candidate_count,
        ambiguous_entity_count=ambiguous_entity_count,
        strict_hold_count=strict_hold_count,
        pending_first_chapter_candidates=pending_first_chapter_candidates,
        pending_first_chapter_updates=pending_first_chapter_updates,
    )
