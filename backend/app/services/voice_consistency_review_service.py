"""Source-backed baseline retrieval and complete passage review orchestration."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.storage import download_book
from app.models.book import Chapter
from app.models.character import Character, VoiceReviewDecision
from app.utils.books.manuscript import deserialize_manuscript_content
from app.utils.characters.governance import is_cast_visible_character
from app.utils.characters.narrator import (
    first_person_addressed_name,
    first_person_self_identification,
)
from app.utils.ingestion_utils import build_chapter_storage_key, load_staged_chapter_payload
from app.utils.llm_usage_utils import (
    LLMIncompleteResponseError,
    is_transient_llm_provider_error,
    short_llm_coordination_retry_delay,
)
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.voice_review_coverage import aggregate_voice_review_coverage
from app.utils.voice_review_utils import (
    VoiceReviewFormatError,
    attributed_voice_samples,
    first_person_narration_samples,
    select_diverse_voice_baseline_samples,
    split_voice_passage,
    validate_voice_section_result,
    voice_baseline_sufficient,
    voice_finding_key,
    voice_ranges_cover_text,
    voice_source_covers_submitted_passage,
    voice_source_matches_submitted,
    voice_source_ranges_for_section,
)


class VoiceBaselineSourceError(RuntimeError):
    """A stored chapter needed for a voice baseline could not be read."""


async def load_voice_review_characters(
    db: AsyncSession, *, book_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Use the same approved cast as the Character Bible for voice attribution."""
    characters = (
        await db.scalars(
            select(Character)
            .where(Character.book_id == book_id)
            .order_by(Character.mention_count.desc(), Character.first_chapter, Character.name)
            .options(
                load_only(
                    Character.id,
                    Character.generation_id,
                    Character.name,
                    Character.aliases,
                    Character.role,
                    Character.first_chapter,
                    Character.mention_count,
                    Character.arc_summary,
                    Character.personality_tags,
                    Character.motivations,
                    Character.fears,
                    Character.goal,
                    Character.trait_state,
                    Character.analysis_metadata,
                    Character.visibility_state,
                    Character.approval_state,
                    Character.approval_source,
                    Character.approval_reason_codes,
                    Character.is_manual,
                    Character.merged_into_character_id,
                    Character.lie_they_believe,
                    Character.backstory_wound,
                    Character.arc_type,
                    Character.archetype,
                    Character.growth_events,
                    raiseload=True,
                )
            )
        )
    ).all()
    return [
        {
            "id": character.id,
            "generation_id": character.generation_id,
            "name": character.name,
            "aliases": character.aliases,
            "role": character.role,
            "first_chapter": character.first_chapter,
            "arc_summary": character.arc_summary,
            "personality_tags": character.personality_tags,
            "motivations": character.motivations,
            "fears": character.fears,
            "goal": character.goal,
            "trait_state": character.trait_state,
            "analysis_metadata": character.analysis_metadata,
        }
        for character in characters
        if is_cast_visible_character(character)
    ]


async def load_voice_baseline_samples(
    db: AsyncSession,
    *,
    book_id: Any,
    character_name: str,
    aliases: Sequence[str],
    submitted_text: str,
    submitted_chapter: int | None,
    voice_mode: str = "dialogue",
    max_samples: int = 128,
    source_cache: dict[str, str] | None = None,
    known_character_names: Sequence[str] = (),
    allowed_chapter_range: tuple[int | None, int | None] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve voice samples from current manuscript sources, never stale derived chunks."""
    if max_samples < 1:
        return []
    statement = select(Chapter.number, Chapter.s3_key).where(Chapter.book_id == book_id)
    if submitted_chapter is not None:
        statement = statement.where(Chapter.number < submitted_chapter)
    if allowed_chapter_range is not None:
        chapter_start, chapter_end = allowed_chapter_range
        if chapter_start is not None:
            statement = statement.where(Chapter.number >= chapter_start)
        if chapter_end is not None:
            statement = statement.where(Chapter.number <= chapter_end)
    statement = statement.order_by(Chapter.number)
    source_rows = (await db.execute(statement)).all()
    # Release the read transaction before object-storage calls.
    await db.commit()

    loaded_sources = source_cache if source_cache is not None else {}
    samples: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    submitted_source = submitted_text.strip()
    for chapter_number, storage_key in source_rows:
        if submitted_chapter is not None and chapter_number >= submitted_chapter:
            continue
        cache_key = str(storage_key or "").strip() or build_chapter_storage_key(
            book_id, chapter_number
        )
        if cache_key not in loaded_sources:
            if storage_key:
                try:
                    raw = await asyncio.to_thread(download_book, storage_key)
                    stored_payload = deserialize_manuscript_content(raw)
                except STORAGE_IO_EXCEPTIONS:
                    stored_payload = await load_staged_chapter_payload(book_id, chapter_number)
            else:
                stored_payload = await load_staged_chapter_payload(book_id, chapter_number)
            if stored_payload is None:
                raise VoiceBaselineSourceError("voice_baseline_source_unavailable")
            loaded_sources[cache_key] = str(stored_payload.get("text") or "")
        source = loaded_sources[cache_key]
        if not source:
            continue
        if submitted_chapter is None and voice_source_matches_submitted(source, submitted_source):
            break
        if submitted_chapter is not None and voice_source_covers_submitted_passage(
            source, submitted_source
        ):
            # The selected chapter can be stale or a different passage can be
            # pasted into the editor. Do not cite that same source as baseline.
            continue
        if voice_mode == "first_person_narration" and any(
            first_person_self_identification(source, known_name, allow_single_name=True)
            for known_name in known_character_names
            if known_name and known_name.casefold() != character_name.casefold()
        ):
            # This chapter explicitly names another first-person narrator. A
            # chapter-wide baseline cannot safely assign its prose to this one.
            continue
        narrator_identified = bool(
            voice_mode == "first_person_narration"
            and first_person_self_identification(source, character_name, allow_single_name=True)
        )
        narrator_addressed = bool(
            voice_mode == "first_person_narration"
            and first_person_addressed_name(source, character_name, allow_single_name=True)
        )
        explicit_dialogue_narrator = bool(
            voice_mode == "dialogue"
            and known_character_names
            and any(
                first_person_self_identification(source, candidate, allow_single_name=True)
                for candidate in (character_name, *aliases)
                if candidate
            )
            and not any(
                first_person_self_identification(source, known_name, allow_single_name=True)
                for known_name in known_character_names
                if known_name and known_name.casefold() != character_name.casefold()
            )
        )
        source_samples = (
            first_person_narration_samples(
                source, chapter_number=chapter_number, include_offsets=True
            )
            if voice_mode == "first_person_narration"
            else attributed_voice_samples(
                source,
                character_name=character_name,
                aliases=aliases,
                chapter_number=chapter_number,
                include_offsets=True,
                first_person_speaker=explicit_dialogue_narrator,
            )
        )
        for sample in source_samples:
            if voice_mode == "first_person_narration":
                sample["attribution_confidence"] = (
                    "explicit"
                    if narrator_identified
                    else "contextual"
                    if narrator_addressed
                    else "unverified_narrator"
                )
            key = (chapter_number, sample["excerpt"])
            if (submitted_chapter is None and sample["excerpt"] in submitted_text) or key in seen:
                continue
            seen.add(key)
            samples.append(sample)
    limit = min(max_samples, 16)
    minimum_words = 120 if voice_mode == "first_person_narration" else 60
    selected: list[dict[str, Any]] = []
    while True:
        candidate = select_diverse_voice_baseline_samples(
            samples,
            submitted_text=submitted_text,
            character_name=character_name,
            aliases=aliases,
            max_samples=limit,
        )
        if (
            limit > 16
            and sum(
                len(f"Chapter {item['chapter_number']}: {item['excerpt']}") for item in candidate
            )
            > 12_000
        ):
            break
        selected = candidate
        # Many short quotes or narrator paragraphs can collectively establish
        # a voice even when the first sixteen excerpts miss the word floor.
        # Expand only while needed, without sending an unbounded baseline.
        if voice_baseline_sufficient(selected, min_words=minimum_words) or limit >= min(
            max_samples, len(samples)
        ):
            break
        limit = min(max_samples, len(samples), limit + 8)
    return selected


async def save_voice_review_decision(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    finding_key: str,
    decision: str,
    note: str | None,
) -> dict[str, Any]:
    statement = (
        insert(VoiceReviewDecision)
        .values(
            id=uuid.uuid4(),
            book_id=book_id,
            user_id=user_id,
            finding_key=finding_key,
            decision=decision,
            note=note,
        )
        .on_conflict_do_update(
            constraint="uq_voice_review_decisions_user_finding",
            set_={"decision": decision, "note": note, "updated_at": func.now()},
        )
    )
    await db.execute(statement)
    await db.commit()
    return {"finding_key": finding_key, "decision": decision, "note": note}


async def load_voice_review_decisions(
    db: AsyncSession, *, book_id: uuid.UUID, user_id: uuid.UUID, keys: Sequence[str]
) -> dict[str, dict[str, Any]]:
    if not keys:
        return {}
    rows = (
        (
            await db.execute(
                select(
                    VoiceReviewDecision.finding_key,
                    VoiceReviewDecision.decision,
                    VoiceReviewDecision.note,
                ).where(
                    VoiceReviewDecision.book_id == book_id,
                    VoiceReviewDecision.user_id == user_id,
                    VoiceReviewDecision.finding_key.in_(keys),
                )
            )
        )
        .mappings()
        .all()
    )
    return {row["finding_key"]: dict(row) for row in rows}


def apply_voice_review_decisions(
    payload: dict[str, Any], decisions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    review = dict(payload.get("review") or {})
    active: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for issue in review.get("issues") or []:
        decision = decisions.get(issue.get("finding_key"))
        if decision:
            suppressed.append({**issue, "decision": decision["decision"]})
        else:
            active.append(issue)
    review["issues"] = active
    if suppressed:
        if active:
            review["overall_verdict"] = (
                f"New voice findings to review: {len(active)}. "
                f"Previously reviewed findings shown below: {len(suppressed)}."
            )
        elif review.get("status") == "partial_evidence":
            review["overall_verdict"] = (
                "No new unresolved voice findings. Previously reviewed findings are listed separately, "
                "but the review remains limited by the available evidence."
            )
        else:
            review["overall_verdict"] = (
                "No new unresolved voice findings. All supported findings in this review "
                "have recorded decisions."
            )
    return {**payload, "review": review, "suppressed_findings": suppressed}


async def personalize_voice_review_payload(
    db: AsyncSession, *, book_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    issues = (payload.get("review") or {}).get("issues") or []
    keys = [issue["finding_key"] for issue in issues if issue.get("finding_key")]
    decisions = await load_voice_review_decisions(db, book_id=book_id, user_id=user_id, keys=keys)
    return apply_voice_review_decisions(payload, decisions)


async def review_voice_sections(
    passage: str,
    *,
    character_name: str,
    baseline_samples: Sequence[dict[str, Any]],
    submitted_samples: Sequence[dict[str, Any]],
    model_call: Callable[[dict[str, Any]], Awaitable[str]],
    source_chapter: int | None = None,
) -> dict[str, Any]:
    """Review every source range; incomplete or unsupported output is a failure."""
    sections = split_voice_passage(passage)
    completed: list[dict[str, Any]] = []
    compared: list[dict[str, int]] = []
    unattributed: list[dict[str, int]] = []
    issues: list[dict[str, Any]] = []
    verdicts: list[str] = []
    seen_issues: set[tuple[str, str, int]] = set()
    # Scope decisions to the source chapter, not the entire editable passage.
    # Unrelated passage edits must not resurrect an unchanged cited finding.
    source_fingerprint = f"chapter:{source_chapter}" if source_chapter is not None else "custom"
    for section in sections:
        attributable_ranges = voice_source_ranges_for_section(passage, section, submitted_samples)
        if not attributable_ranges:
            unattributed.append({"start": section["start"], "end": section["end"]})
            continue
        for attempt in range(2):
            try:
                raw = await model_call(section)
            except LLMIncompleteResponseError as exc:
                if attempt:
                    raise VoiceReviewFormatError("voice_review_incomplete_model_output") from exc
                continue
            except (APIConnectionError, APITimeoutError, RateLimitError, TimeoutError):
                if attempt:
                    raise
                await asyncio.sleep(0.25)
                continue
            except APIStatusError as exc:
                if attempt or not is_transient_llm_provider_error(exc):
                    raise
                await asyncio.sleep(0.25)
                continue
            except HTTPException as exc:
                # Budget/configuration errors are not temporary slot contention.
                delay = short_llm_coordination_retry_delay(exc)
                if attempt or delay is None:
                    raise
                await asyncio.sleep(delay)
                continue
            try:
                validated = validate_voice_section_result(
                    raw,
                    section_text=section["text"],
                    section_start=section["start"],
                    baseline_samples=baseline_samples,
                    submitted_samples=submitted_samples,
                    character_name=character_name,
                )
                break
            except VoiceReviewFormatError:
                if attempt:
                    raise
        completed.append({"start": section["start"], "end": section["end"]})
        compared.extend(attributable_ranges)
        verdicts.append(validated["overall_verdict"])
        for issue in validated["issues"]:
            key = (
                issue["submitted_excerpt"],
                issue["baseline_excerpt"],
                issue["baseline_chapter_number"],
            )
            if key not in seen_issues:
                seen_issues.add(key)
                issues.append(
                    {
                        **issue,
                        "finding_key": voice_finding_key(
                            issue, source_fingerprint=source_fingerprint
                        ),
                    }
                )
    if not completed:
        raise VoiceReviewFormatError("voice_review_no_attributable_sections")
    compared_coverage = aggregate_voice_review_coverage(
        [
            {
                "coverage": {
                    "processed_ranges": compared,
                    "total_characters": len(passage),
                }
            }
        ],
        total_characters=len(passage),
    )
    if not voice_ranges_cover_text([*completed, *unattributed], len(passage)):
        raise VoiceReviewFormatError("voice_review_incomplete_coverage")
    return {
        "issues": issues,
        "overall_verdict": " ".join(dict.fromkeys(verdicts)),
        "coverage": {
            "processed_ranges": completed,
            "unattributed_ranges": unattributed,
            "compared_ranges": compared_coverage["processed_ranges"],
            "not_compared_ranges": compared_coverage["unattributed_ranges"],
            "total_characters": len(passage),
        },
    }
