import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.engine.character.deduplicator import find_similar
from app.models.character import Character
from app.services.extraction_character_cache_service import _find_character_ids_in_cache
from app.services.extraction_character_decision_service import (
    _record_character_disposition_candidate,
)
from app.services.extraction_character_persistence_service import (
    _accept_existing_character_match,
    _promote_new_character_from_entity,
    _record_cluster_member_candidates,
    _record_entity_cluster_mentions,
    reconcile_cross_chapter_candidates,
)
from app.utils.characters.constants import CHARACTER_CANDIDATE_SUPPRESSED


@dataclass(slots=True)
class NewCharacterResolutionResult:
    saved_character_count: int
    quarantined_candidate_count: int
    ambiguous_entity_count: int


async def promote_or_match_new_character_entities(
    db,
    *,
    book,
    chapter_number: int,
    existing_characters: list[Character],
    character_key_cache: dict[uuid.UUID, set[str]],
    pending_first_chapter_candidates: dict[uuid.UUID, list[str]],
    pending_first_chapter_updates: dict[uuid.UUID, Character],
    pending_new_entities: list[tuple[dict[str, Any], set[uuid.UUID], str | None, list[float]]],
    saved_character_count: int,
    quarantined_candidate_count: int,
    ambiguous_entity_count: int,
) -> NewCharacterResolutionResult:
    for entity, blocked_ids, entity_source_batch_key, emb in pending_new_entities:
        if not emb:
            raise RuntimeError("character_embedding_result_incomplete")
        matching_ids = _find_character_ids_in_cache(
            existing_characters,
            str(entity.get("name") or ""),
            entity.get("aliases", []),
            blocked_ids=blocked_ids,
            key_cache=character_key_cache,
        )
        if len(matching_ids) > 1:
            ambiguous_entity_count += 1
            quarantined_candidate_count += 1
            status, reasons, _evidence = await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=None,
                reason_codes=["ambiguous_roster_match_after_cluster"],
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
                else "ambiguous",
                resolver_reasons=reasons,
            )
            continue
        if len(matching_ids) == 1:
            existing_id = matching_ids[0]
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
                reason_code="matched_existing_character_after_cluster",
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
                    resolver_reasons=["matched_existing_character_after_cluster"],
                )
                await _record_cluster_member_candidates(
                    db,
                    book_id=book.id,
                    chapter_number=chapter_number,
                    entity=entity,
                    matched_character_id=existing_id,
                    reason_code="matched_existing_character_after_cluster",
                )
            continue

        existing_id = await find_similar(
            db,
            book.id,
            emb,
            settings.DEDUP_SIMILARITY_THRESHOLD,
            excluded_ids=blocked_ids,
        )
        if existing_id:
            quarantined_candidate_count += 1
            status, reasons, _evidence = await _record_character_disposition_candidate(
                db,
                book_id=book.id,
                chapter_number=chapter_number,
                entity=entity,
                matched_character_id=existing_id,
                reason_codes=["embedding_match_requires_review"],
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
                resolver_reasons=reasons,
            )
            continue

        promoted = await _promote_new_character_from_entity(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            entity=entity,
            embedding=emb,
            existing_characters=existing_characters,
            character_key_cache=character_key_cache,
            pending_first_chapter_candidates=pending_first_chapter_candidates,
            pending_first_chapter_updates=pending_first_chapter_updates,
            source_batch_key=entity_source_batch_key,
        )
        saved_character_count += 1
        await reconcile_cross_chapter_candidates(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            entity=entity,
            character_id=promoted.id,
        )
        await _record_entity_cluster_mentions(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            entity=entity,
            matched_character_id=promoted.id,
            resolver_status="promoted",
            resolver_reasons=["new_character_promoted"],
        )
        await _record_cluster_member_candidates(
            db,
            book_id=book.id,
            chapter_number=chapter_number,
            entity=entity,
            matched_character_id=promoted.id,
            reason_code="matched_cluster_member",
        )

    return NewCharacterResolutionResult(
        saved_character_count=saved_character_count,
        quarantined_candidate_count=quarantined_candidate_count,
        ambiguous_entity_count=ambiguous_entity_count,
    )
