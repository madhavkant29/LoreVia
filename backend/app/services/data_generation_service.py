"""Generation staging, visibility context, promotion, and retirement."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, cast, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.ext.asyncio import AsyncSession

_CURRENT_GENERATION_ID: ContextVar[uuid.UUID | None] = ContextVar(
    "lorevia_current_generation_id",
    default=None,
)

ACTIVE_GENERATION = "active"
STAGING_GENERATION = "staging"
RETIRED_GENERATION = "retired"
FAILED_GENERATION = "failed"


def generation_id_for_rebuild(rebuild_run_id: str) -> uuid.UUID:
    normalized = str(rebuild_run_id).strip()
    try:
        return uuid.UUID(normalized)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"lorevia:rebuild:{normalized}")


def current_generation_id() -> uuid.UUID | None:
    return _CURRENT_GENERATION_ID.get()


@contextmanager
def generation_scope(rebuild_run_id: str | None) -> Iterator[uuid.UUID | None]:
    generation_id = generation_id_for_rebuild(rebuild_run_id) if rebuild_run_id else None
    token: Token[uuid.UUID | None] = _CURRENT_GENERATION_ID.set(generation_id)
    try:
        yield generation_id
    finally:
        _CURRENT_GENERATION_ID.reset(token)


def _all_generations(statement):
    return statement.execution_options(include_all_generations=True)


async def preserve_author_candidate_reviews(db: AsyncSession, *, book_id: uuid.UUID) -> None:
    """Detach author decisions from generations that a rebuild can retire."""
    from app.models.character import (
        CharacterCandidate,
        CharacterDecisionEvent,
        CharacterRelationshipCandidate,
    )
    from app.models.operations import AiQualityEvent

    reviewed_character_ids = select(AiQualityEvent.entity_id).where(
        AiQualityEvent.book_id == book_id,
        AiQualityEvent.entity_type == "character_candidate",
        AiQualityEvent.actor_user_id.is_not(None),
        AiQualityEvent.outcome.in_(("accepted", "promoted", "rejected")),
    )
    await db.execute(
        _all_generations(
            update(CharacterCandidate)
            .where(
                CharacterCandidate.book_id == book_id,
                CharacterCandidate.generation_id.is_not(None),
                or_(
                    CharacterCandidate.source_batch_key.like("manual-demote:%"),
                    CharacterCandidate.rejection_reason == "author_marked_place",
                    func.array_position(
                        CharacterCandidate.reason_codes, "author_reviewed_candidate"
                    ).is_not(None),
                    func.array_position(
                        CharacterCandidate.reason_codes, "author_rejected_candidate"
                    ).is_not(None),
                    cast(CharacterCandidate.id, String).in_(reviewed_character_ids),
                ),
            )
            .values(generation_id=None)
        )
    )

    reviewed_relationship_ids = select(AiQualityEvent.entity_id).where(
        AiQualityEvent.book_id == book_id,
        AiQualityEvent.entity_type == "relationship_candidate",
        AiQualityEvent.actor_user_id.is_not(None),
        AiQualityEvent.outcome.in_(("accepted", "resolved", "rejected")),
    )
    attached_relationship_ids = select(
        CharacterDecisionEvent.evidence["relationship_candidate_id"].as_string()
    ).where(
        CharacterDecisionEvent.book_id == book_id,
        CharacterDecisionEvent.action.in_(
            ("relationship_candidate_attached_a", "relationship_candidate_attached_b")
        ),
    )
    await db.execute(
        _all_generations(
            update(CharacterRelationshipCandidate)
            .where(
                CharacterRelationshipCandidate.book_id == book_id,
                cast(CharacterRelationshipCandidate.id, String).in_(attached_relationship_ids),
                func.array_position(
                    CharacterRelationshipCandidate.reason_codes, "author_attached_endpoint"
                ).is_(None),
            )
            .values(
                reason_codes=func.array_append(
                    func.coalesce(
                        CharacterRelationshipCandidate.reason_codes,
                        cast(array([]), ARRAY(String)),
                    ),
                    "author_attached_endpoint",
                ),
                generation_id=None,
            )
        )
    )
    await db.execute(
        _all_generations(
            update(CharacterRelationshipCandidate)
            .where(
                CharacterRelationshipCandidate.book_id == book_id,
                CharacterRelationshipCandidate.generation_id.is_not(None),
                or_(
                    CharacterRelationshipCandidate.status.in_(("accepted", "resolved", "rejected")),
                    func.array_position(
                        CharacterRelationshipCandidate.reason_codes, "author_attached_endpoint"
                    ).is_not(None),
                    cast(CharacterRelationshipCandidate.id, String).in_(reviewed_relationship_ids),
                    cast(CharacterRelationshipCandidate.id, String).in_(attached_relationship_ids),
                ),
            )
            .values(generation_id=None)
        )
    )


async def ensure_active_generation(db: AsyncSession, *, book_id: uuid.UUID) -> uuid.UUID:
    """Adopt an unversioned generated baseline before the first staged rebuild."""
    from app.models.book import Chapter
    from app.models.character import (
        Character,
        CharacterAlias,
        CharacterCandidate,
        CharacterDuplicateSuggestion,
        CharacterMention,
        CharacterRelationshipCandidate,
        CharacterState,
        CharacterVoiceProfile,
    )
    from app.models.generation import BookDataGeneration
    from app.models.intelligence import (
        BookChunk,
        ChapterSummary,
        CharacterRelationship,
        PlotThread,
        ReaderEvent,
        WikiEntry,
        WorldElement,
        WorldGapAnalysis,
    )
    from app.services.editor_project_service import _resolve_character_anchor_ids

    await preserve_author_candidate_reviews(db, book_id=book_id)
    active_id = await db.scalar(
        select(BookDataGeneration.id).where(
            BookDataGeneration.book_id == book_id,
            BookDataGeneration.status == ACTIVE_GENERATION,
        )
    )
    if active_id is not None:
        return active_id

    generation = BookDataGeneration(
        id=uuid.uuid4(),
        book_id=book_id,
        rebuild_run_id=uuid.uuid4().hex,
        status=ACTIVE_GENERATION,
        reason="legacy_baseline_adoption",
        promoted_at=datetime.now(UTC),
    )
    db.add(generation)
    await db.flush()

    for model in (
        BookChunk,
        ReaderEvent,
        WikiEntry,
        WorldGapAnalysis,
        CharacterMention,
        CharacterDuplicateSuggestion,
        CharacterVoiceProfile,
    ):
        await db.execute(
            _all_generations(
                update(model)
                .where(model.book_id == book_id, model.generation_id.is_(None))
                .values(generation_id=generation.id)
            )
        )

    chapter_ids = select(Chapter.id).where(Chapter.book_id == book_id)
    await db.execute(
        _all_generations(
            update(ChapterSummary)
            .where(
                ChapterSummary.chapter_id.in_(chapter_ids),
                ChapterSummary.generation_id.is_(None),
            )
            .values(generation_id=generation.id)
        )
    )

    for model in (CharacterRelationship, PlotThread, WorldElement):
        await db.execute(
            _all_generations(
                update(model)
                .where(
                    model.book_id == book_id,
                    model.generation_id.is_(None),
                    model.edited_by_author.is_(False),
                )
                .values(generation_id=generation.id)
            )
        )
    anchor_ids = await _resolve_character_anchor_ids(db, book_id)
    generated_candidate_filter = [
        CharacterCandidate.book_id == book_id,
        CharacterCandidate.generation_id.is_(None),
        CharacterCandidate.status.not_in(("rejected", "merged")),
        CharacterCandidate.rejection_reason.is_not_distinct_from(None),
    ]
    if anchor_ids:
        generated_candidate_filter.append(
            CharacterCandidate.matched_character_id.not_in(anchor_ids)
            | CharacterCandidate.matched_character_id.is_(None)
        )
    await db.execute(
        _all_generations(
            update(CharacterCandidate)
            .where(*generated_candidate_filter)
            .values(generation_id=generation.id)
        )
    )
    await db.execute(
        _all_generations(
            update(CharacterRelationshipCandidate)
            .where(
                CharacterRelationshipCandidate.book_id == book_id,
                CharacterRelationshipCandidate.generation_id.is_(None),
                CharacterRelationshipCandidate.status.in_(("pending", "suppressed")),
            )
            .values(generation_id=generation.id)
        )
    )

    generated_character_filter = [
        Character.book_id == book_id,
        Character.generation_id.is_(None),
    ]
    if anchor_ids:
        generated_character_filter.append(Character.id.not_in(anchor_ids))
    await db.execute(
        _all_generations(
            update(Character).where(*generated_character_filter).values(generation_id=generation.id)
        )
    )
    generated_character_ids = _all_generations(
        select(Character.id).where(
            Character.book_id == book_id,
            Character.generation_id == generation.id,
        )
    )
    await db.execute(
        _all_generations(
            update(CharacterAlias)
            .where(
                CharacterAlias.character_id.in_(generated_character_ids),
                CharacterAlias.generation_id.is_(None),
            )
            .values(generation_id=generation.id)
        )
    )
    await db.execute(
        _all_generations(
            update(CharacterState)
            .where(
                CharacterState.character_id.in_(
                    _all_generations(select(Character.id).where(Character.book_id == book_id))
                ),
                CharacterState.generation_id.is_(None),
            )
            .values(generation_id=generation.id)
        )
    )
    await preserve_author_candidate_reviews(db, book_id=book_id)
    await db.flush()
    return generation.id


async def create_staging_generation(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    rebuild_run_id: str,
    reason: str,
) -> uuid.UUID:
    from app.models.generation import BookDataGeneration

    generation_id = generation_id_for_rebuild(rebuild_run_id)
    existing = await db.get(BookDataGeneration, generation_id)
    if existing is not None:
        if existing.book_id != book_id or existing.status != STAGING_GENERATION:
            raise RuntimeError("rebuild_generation_conflict")
        return existing.id
    db.add(
        BookDataGeneration(
            id=generation_id,
            book_id=book_id,
            rebuild_run_id=rebuild_run_id,
            status=STAGING_GENERATION,
            reason=reason,
        )
    )
    await db.flush()
    return generation_id


async def has_active_generation(db: AsyncSession, *, book_id: uuid.UUID) -> bool:
    from app.models.generation import BookDataGeneration

    generation_id = await db.scalar(
        select(BookDataGeneration.id)
        .where(
            BookDataGeneration.book_id == book_id,
            BookDataGeneration.status == ACTIVE_GENERATION,
        )
        .limit(1)
    )
    return generation_id is not None


async def promote_staging_generation(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    rebuild_run_id: str,
) -> bool:
    from app.models.generation import BookDataGeneration

    now = datetime.now(UTC)
    generation_id = generation_id_for_rebuild(rebuild_run_id)
    generations = list(
        (
            await db.execute(
                select(BookDataGeneration)
                .where(BookDataGeneration.book_id == book_id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    staging = next((item for item in generations if item.id == generation_id), None)
    if staging is None or staging.status != STAGING_GENERATION:
        return False
    for generation in generations:
        if generation.status == ACTIVE_GENERATION:
            generation.status = RETIRED_GENERATION
            generation.updated_at = now
    # The partial unique index is immediate, so release the old active slot
    # before activating the staged row. Both writes remain in one transaction
    # and are therefore still observed atomically by other sessions.
    await db.flush()
    staging.status = ACTIVE_GENERATION
    staging.chapter_state_snapshot = None
    staging.promoted_at = now
    staging.updated_at = now
    await db.flush()
    return True


async def fail_staging_generation(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    rebuild_run_id: str,
) -> bool:
    from app.models.book import Chapter
    from app.models.generation import BookDataGeneration

    generation = await db.get(
        BookDataGeneration, generation_id_for_rebuild(rebuild_run_id), with_for_update=True
    )
    if (
        generation is None
        or generation.book_id != book_id
        or generation.status != STAGING_GENERATION
    ):
        return False
    snapshot = generation.chapter_state_snapshot
    if (
        isinstance(snapshot, dict)
        and snapshot.get("rebuild_run_id") == rebuild_run_id
        and isinstance(snapshot.get("chapters"), dict)
    ):
        chapters = (
            (await db.execute(select(Chapter).where(Chapter.book_id == book_id).with_for_update()))
            .scalars()
            .all()
        )
        for chapter in chapters:
            prior = snapshot["chapters"].get(str(chapter.id))
            if not isinstance(prior, dict) or type(prior.get("processed")) is not bool:
                continue
            if (
                prior.get("content_version") != chapter.content_version
                or prior.get("structure_version") != chapter.structure_version
                or prior.get("number") != chapter.number
                or prior.get("title") != chapter.title
                or prior.get("s3_key") != chapter.s3_key
                or prior.get("word_count") != chapter.word_count
            ):
                # A manuscript edit invalidates only that chapter's old result.
                continue
            prior_analysis = prior.get("analysis_state")
            if prior_analysis is not None and not isinstance(prior_analysis, dict):
                continue
            chapter.processed = prior["processed"]
            chapter.analysis_state = deepcopy(prior_analysis)
    now = datetime.now(UTC)
    generation.status = FAILED_GENERATION
    generation.chapter_state_snapshot = None
    generation.failed_at = now
    generation.updated_at = now
    await db.flush()
    return True


async def cleanup_inactive_generations(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    retention: timedelta = timedelta(days=7),
    limit: int = 100,
) -> int:
    from app.models.generation import BookDataGeneration

    cutoff = (now or datetime.now(UTC)) - retention
    generation_ids = list(
        (
            await db.execute(
                select(BookDataGeneration.id)
                .where(
                    BookDataGeneration.status.in_((RETIRED_GENERATION, FAILED_GENERATION)),
                    BookDataGeneration.updated_at < cutoff,
                )
                .order_by(BookDataGeneration.updated_at.asc())
                .limit(max(1, min(int(limit), 1000)))
            )
        )
        .scalars()
        .all()
    )
    if generation_ids:
        await db.execute(
            delete(BookDataGeneration).where(BookDataGeneration.id.in_(generation_ids))
        )
        await db.commit()
    return len(generation_ids)
