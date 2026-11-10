from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import get_openai_client
from app.core.redis import (
    get_book_cache_version,
    get_proactive_scan_cache,
    set_proactive_scan_cache,
)
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, WorldElement
from app.services.advisor_proactive_scan_service import (
    request_proactive_scan_result,
    run_bounded_scan_groups,
)
from app.utils.advisor_prompt_templates import PROACTIVE_SCAN_SYSTEM, PROACTIVE_SCAN_USER
from app.utils.advisor_prompt_utils import make_editorial_cache_key, safe_prompt_str
from app.utils.advisor_result_utils import normalize_proactive_scan_result
from app.utils.advisor_route_errors import advisor_scan_failure_category
from app.utils.advisor_story_context_utils import build_story_context
from app.utils.advisor_suggestions_utils import (
    advisor_clue_evidence,
    advisor_supported_relationship,
    build_advisor_chapter_evidence_blocks,
    build_advisor_item_evidence_blocks,
    build_open_thread_review_suggestions,
    build_relationship_drift_suggestions,
    build_world_drift_suggestions,
    partition_advisor_scan_evidence,
    proactive_advisor_finding_id,
)
from app.utils.plot_thread_utils import derive_plot_thread_status, is_plot_thread_open

log = logging.getLogger(__name__)

ADVISOR_SCAN_FALLBACK_ERRORS = (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAIError,
    HTTPException,
    SQLAlchemyError,
    TimeoutError,
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
)


async def build_advisor_suggestions_payload(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    skip_llm: bool = False,
    force_audit: bool = False,
    cache_only: bool = False,
    on_audit_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """Run the full heuristic + optional LLM advisor scan and return the result dict."""
    book_id = book.id
    total_ch = book.total_chapters or 1
    suggestions: list[dict] = []
    scan_basis: list[str] = []
    data_gaps: list[str] = []

    all_chars = (
        (
            await db.execute(
                select(Character)
                .where(Character.book_id == book_id)
                .order_by(Character.mention_count.desc(), Character.first_chapter, Character.name)
            )
        )
        .scalars()
        .all()
    )
    character_count = len(all_chars)
    character_names = {char.id: char.name for char in all_chars}
    if character_count:
        scan_basis.append("characters")
    else:
        data_gaps.append("characters")

    all_threads = (
        (
            await db.execute(
                select(PlotThread)
                .where(PlotThread.book_id == book_id)
                .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
            )
        )
        .scalars()
        .all()
    )
    if all_threads:
        scan_basis.append("plot threads")
    else:
        data_gaps.append("plot threads")

    all_relationship_rows = (
        (
            await db.execute(
                select(CharacterRelationship)
                .where(CharacterRelationship.book_id == book_id)
                .order_by(CharacterRelationship.from_chapter, CharacterRelationship.id)
            )
        )
        .scalars()
        .all()
    )
    relationship_rows = [
        rel for rel in all_relationship_rows if advisor_supported_relationship(rel, character_names)
    ]
    relationship_count = len(relationship_rows)
    if relationship_count:
        scan_basis.append("relationships")
    else:
        data_gaps.append("verified relationships" if all_relationship_rows else "relationships")

    world_rows = (
        (
            await db.execute(
                select(WorldElement)
                .where(WorldElement.book_id == book_id)
                .order_by(WorldElement.usage_count.desc(), WorldElement.name.asc())
            )
        )
        .scalars()
        .all()
    )
    world_element_count = len(world_rows)
    if world_element_count:
        scan_basis.append("world elements")
    else:
        data_gaps.append("world elements")

    physical_traits = ["eyes", "hair", "build", "age_descriptor", "distinguishing"]

    all_states = (
        await db.execute(
            select(
                CharacterState.character_id,
                CharacterState.at_chapter,
                CharacterState.trait_snapshot,
                Character.name,
            )
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book_id,
                CharacterState.trait_snapshot.isnot(None),
            )
            .order_by(CharacterState.character_id, CharacterState.at_chapter)
        )
    ).all()
    state_count = len(all_states)
    if state_count:
        scan_basis.append("character states")
    else:
        data_gaps.append("character states")

    char_state_map: dict[str, list[Any]] = {}
    for row in all_states:
        key = str(row.character_id)
        if key not in char_state_map:
            char_state_map[key] = []
        char_state_map[key].append(row)

    contradiction_count = 0
    for char_id, states in char_state_map.items():
        if len(states) < 2 or contradiction_count >= 3:
            break
        char_name = states[0].name
        earliest = states[0]
        for later in states[1:]:
            if contradiction_count >= 3:
                break
            snap_a = earliest.trait_snapshot or {}
            snap_b = later.trait_snapshot or {}
            for trait in physical_traits:
                val_a = None
                val_b = None
                raw_a = snap_a.get(trait)
                raw_b = snap_b.get(trait)
                if isinstance(raw_a, dict):
                    val_a = raw_a.get("value")
                elif isinstance(raw_a, str):
                    val_a = raw_a
                if isinstance(raw_b, dict):
                    val_b = raw_b.get("value")
                elif isinstance(raw_b, str):
                    val_b = raw_b
                if val_a and val_b and val_a.lower() != val_b.lower():
                    suggestions.append(
                        {
                            "id": f"trait-{char_id}-{trait}",
                            "type": "trait_contradiction",
                            "severity": "warning",
                            "title": f"Conflicting {trait} description: {char_name}",
                            "description": (
                                f'{char_name}\'s {trait} is described as "{val_a}" in chapter '
                                f'{earliest.at_chapter} but "{val_b}" in chapter {later.at_chapter}. '
                                f"No character state change was recorded between these chapters."
                            ),
                            "chapter_ref": earliest.at_chapter,
                            "action_label": "Investigate this contradiction",
                            "ask_prompt": (
                                f"There's a potential continuity issue with {char_name}'s {trait}: "
                                f'"{val_a}" in chapter {earliest.at_chapter} vs "{val_b}" in chapter '
                                f"{later.at_chapter}. Is this a plothole or an intentional change?"
                            ),
                        }
                    )
                    contradiction_count += 1
                    break

    dropped_threads_result = await db.execute(
        select(PlotThread)
        .where(
            PlotThread.book_id == book_id,
            PlotThread.introduced_at <= total_ch - 30,
        )
        .order_by(PlotThread.importance.desc())
        .limit(12)
    )
    dropped_threads = [
        thread
        for thread in dropped_threads_result.scalars().all()
        if is_plot_thread_open(
            derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=total_ch,
            )
        )
    ][:5]

    for thread in dropped_threads:
        suggestions.append(
            {
                "id": f"thread-{thread.id}",
                "type": "dropped_thread",
                "severity": "warning",
                "title": f'Unresolved thread: "{thread.title}"',
                "description": (
                    f"Introduced at chapter {thread.introduced_at}, "
                    f"still marked '{derive_plot_thread_status(thread.status, introduced_at=thread.introduced_at, last_mentioned_at=thread.last_mentioned_at or thread.introduced_at, resolved_at=thread.resolved_at, current_chapter=total_ch)}' with {total_ch - (thread.introduced_at or 0)} chapters elapsed. "
                    f"{thread.description or 'No additional detail recorded.'}"
                ),
                "chapter_ref": thread.introduced_at,
                "action_label": "Ask advisor about this thread",
                "ask_prompt": f'Is there a plothole or missed opportunity with the "{thread.title}" plot thread?',
            }
        )

    absent_chars: list[Character] = []
    try:
        absent_chars_result = await db.execute(
            select(Character)
            .where(
                Character.book_id == book_id,
                Character.mention_count > 5,
                Character.last_seen_chapter <= total_ch - 30,
            )
            .order_by(Character.mention_count.desc())
            .limit(5)
        )
        absent_chars = list(absent_chars_result.scalars().all())
    except SQLAlchemyError:
        log.warning("advisor_suggestions_absent_characters_unavailable", exc_info=True)

    for char in absent_chars:
        suggestions.append(
            {
                "id": f"absent-{char.id}",
                "type": "character_absent",
                "severity": "info",
                "title": f"{char.name} hasn't appeared in {total_ch - (char.last_seen_chapter or 0)} chapters",
                "description": (
                    f"Last seen around chapter {char.last_seen_chapter}. "
                    f"Mentioned {char.mention_count} times overall. "
                    f"{char.role or ''} — {char.arc_summary[:120] + '...' if char.arc_summary and len(char.arc_summary) > 120 else (char.arc_summary or 'No arc summary yet.')}"
                ),
                "chapter_ref": char.last_seen_chapter,
                "action_label": "Explore this character's arc",
                "ask_prompt": f"What are good opportunities to bring {char.name} back into the story?",
            }
        )

    hot_threads_result = await db.execute(
        select(PlotThread)
        .where(
            PlotThread.book_id == book_id,
            PlotThread.importance >= 7,
        )
        .order_by(PlotThread.importance.desc())
        .limit(8)
    )
    hot_threads = [
        thread
        for thread in hot_threads_result.scalars().all()
        if derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=total_ch,
        )
        in {"developing", "paused", "possibly_abandoned", "forgotten", "introduced"}
    ][:3]

    for thread in hot_threads:
        if thread.introduced_at and total_ch - thread.introduced_at > 15:
            suggestions.append(
                {
                    "id": f"arc-{thread.id}",
                    "type": "arc_opportunity",
                    "severity": "opportunity",
                    "title": f'Arc decision point: "{thread.title}"',
                    "description": (
                        f"High-importance thread (importance {thread.importance}/10), "
                        f"active since chapter {thread.introduced_at}. "
                        f"Decision points examined now can be planted as foreshadowing retroactively. "
                        f"{thread.description or ''}"
                    ),
                    "chapter_ref": thread.introduced_at,
                    "action_label": "Debate how to end this arc",
                    "ask_prompt": f'What are the best ways to resolve the "{thread.title}" arc? What are the story tradeoffs?',
                }
            )

    if total_ch >= 20:
        late_threads_result = await db.execute(
            select(PlotThread)
            .where(
                PlotThread.book_id == book_id,
                PlotThread.introduced_at <= int(total_ch * 0.4),
                PlotThread.importance >= 5,
            )
            .order_by(PlotThread.importance.desc())
            .limit(8)
        )
        late_threads = [
            thread
            for thread in late_threads_result.scalars().all()
            if is_plot_thread_open(
                derive_plot_thread_status(
                    thread.status,
                    introduced_at=thread.introduced_at,
                    last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                    resolved_at=thread.resolved_at,
                    current_chapter=total_ch,
                )
            )
        ][:3]

        for thread in late_threads:
            already_covered = any(s["id"] == f"arc-{thread.id}" for s in suggestions)
            if already_covered:
                continue
            suggestions.append(
                {
                    "id": f"direction-{thread.id}",
                    "type": "future_direction",
                    "severity": "direction",
                    "title": f'Future direction: how does "{thread.title}" end?',
                    "description": (
                        f"This thread has been running since chapter {thread.introduced_at} "
                        f"— {total_ch - (thread.introduced_at or 0)} chapters in. "
                        f"At this stage, it's worth stress-testing your ending options and "
                        f"checking whether earlier chapters planted enough foreshadowing. "
                        f"{thread.description[:120] + '...' if thread.description and len(thread.description) > 120 else (thread.description or '')}"
                    ),
                    "chapter_ref": thread.introduced_at,
                    "action_label": "Explore ending options",
                    "ask_prompt": (
                        f'I\'m thinking about how to end the "{thread.title}" thread. '
                        f"What options do I have and what are the narrative tradeoffs of each?"
                    ),
                }
            )

    underused_chars: list[Character] = []
    try:
        underused_chars_result = await db.execute(
            select(Character)
            .where(
                Character.book_id == book_id,
                Character.role == "minor",
                Character.mention_count > 8,
            )
            .order_by(Character.mention_count.desc())
            .limit(3)
        )
        underused_chars = list(underused_chars_result.scalars().all())
    except SQLAlchemyError:
        log.warning("advisor_suggestions_underused_characters_unavailable", exc_info=True)

    for char in underused_chars:
        suggestions.append(
            {
                "id": f"underused-{char.id}",
                "type": "foreshadowing_opportunity",
                "severity": "opportunity",
                "title": f"Foreshadowing opportunity: {char.name}",
                "description": (
                    f"{char.name} appears {char.mention_count} times but is still tagged as a minor character. "
                    f"High mention count with a minor role often signals unused narrative potential — "
                    f"this character could serve as a plot connector or a foreshadowing anchor."
                ),
                "chapter_ref": char.first_chapter,
                "action_label": "Explore narrative potential",
                "ask_prompt": f"How could {char.name} be used more effectively in the story? Are there foreshadowing opportunities?",
            }
        )

    detailed_summaries = (
        await db.execute(
            select(ChapterSummary.clues, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "detailed",
            )
            .order_by(Chapter.number.asc())
        )
    ).all()
    clue_count = 0
    if detailed_summaries:
        scan_basis.append("chapter summaries")
    else:
        data_gaps.append("chapter summaries")

    seen_clues: set[str] = set()
    clue_evidence_by_chapter: dict[int, list[str]] = {}
    for clues, chapter_num, chapter_title in detailed_summaries:
        clue_lines = advisor_clue_evidence(clues)
        clue_evidence_by_chapter.setdefault(chapter_num, []).extend(clue_lines)
        clue_count += len(clue_lines)
        for clue in clue_lines:
            clue_key = " ".join(clue.casefold().split())
            if clue_key not in seen_clues and len(seen_clues) < 3:
                seen_clues.add(clue_key)
                clue_str = clue[:120]
                suggestions.append(
                    {
                        "id": f"clue-{book_id}-{chapter_num}-{len(seen_clues)}",
                        "type": "unresolved_clue",
                        "severity": "opportunity",
                        "title": f"Planted clue from chapter {chapter_num}",
                        "description": (
                            f'Chapter {chapter_num} ({chapter_title or "Untitled"}) contains: "{clue_str}". '
                            f"If this hasn't paid off yet, it's either a plothole or a foreshadowing opportunity."
                        ),
                        "chapter_ref": chapter_num,
                        "action_label": "Check if this clue resolved",
                        "ask_prompt": f"Has the clue from chapter {chapter_num} been resolved? '{clue_str}'",
                    }
                )

    thread_statuses = {
        thread.id: derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=total_ch,
        )
        for thread in all_threads
    }
    open_threads = [
        thread for thread in all_threads if is_plot_thread_open(thread_statuses[thread.id])
    ]
    open_thread_count = len(open_threads)

    thread_review_suggestions = build_open_thread_review_suggestions(
        open_threads, thread_statuses, total_chapters=total_ch
    )
    suggestions.extend(thread_review_suggestions)

    for thread in [
        item
        for item in all_threads
        if item.status == "contradicted" or thread_statuses[item.id] == "contradicted"
    ]:
        suggestions.append(
            {
                "id": f"contradicted-{thread.id}",
                "type": "event_conflict",
                "severity": "warning",
                "title": f'Thread contradiction: "{thread.title}"',
                "description": (
                    "This tracked thread is already marked as contradicted"
                    + (
                        f" after chapter {thread.last_mentioned_at}"
                        if thread.last_mentioned_at
                        else ""
                    )
                    + ". Review the affected scenes before building more logic on top of it."
                    + (f" {thread.description}" if thread.description else "")
                ),
                "chapter_ref": thread.last_mentioned_at or thread.introduced_at,
                "action_label": "Trace the contradiction",
                "ask_prompt": f'Walk me through where the "{thread.title}" thread started contradicting itself and how to fix it.',
                "source": "heuristic",
            }
        )

    suggestions.extend(build_relationship_drift_suggestions(relationship_rows, character_names))
    suggestions.extend(build_world_drift_suggestions(world_rows))

    heuristic_count = len(suggestions)
    proactive_audit_applied = False
    audit_summary: str | None = None
    audit_failure_category: str | None = None
    audit_groups_total = 0
    audit_groups_completed = 0
    if not skip_llm and (
        force_audit or cache_only or heuristic_count - len(thread_review_suggestions) < 3
    ):
        detailed_summary_rows = (
            await db.execute(
                select(
                    Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events
                )
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == book_id,
                    ChapterSummary.mode.in_(["short", "detailed"]),
                )
                .order_by(Chapter.number.desc(), ChapterSummary.mode.asc())
            )
        ).all()
        recent_summary_blocks: list[str] = []
        seen_summary_chapters: set[int] = set()
        for chapter_num, chapter_title, content, key_events in detailed_summary_rows:
            if chapter_num in seen_summary_chapters:
                continue
            seen_summary_chapters.add(chapter_num)
            recent_summary_blocks.extend(
                build_advisor_chapter_evidence_blocks(
                    chapter_number=chapter_num,
                    chapter_title=chapter_title,
                    content=content,
                    key_events=key_events,
                    clues=clue_evidence_by_chapter.get(chapter_num),
                )
            )

        open_thread_blocks = [
            block
            for thread in open_threads
            for block in build_advisor_item_evidence_blocks(
                f"- {thread.title} [{thread_statuses[thread.id]}]"
                + (f" introduced ch.{thread.introduced_at}" if thread.introduced_at else ""),
                thread.description,
                separator=": ",
            )
        ]
        relationship_blocks = [
            block
            for rel in relationship_rows
            for block in build_advisor_item_evidence_blocks(
                f"- {character_names.get(rel.character_a_id, 'Unknown')} / {character_names.get(rel.character_b_id, 'Unknown')}: "
                f"{rel.rel_type.replace('_', ' ')} at chapter {rel.from_chapter}",
                rel.description,
            )
        ]
        world_watch_blocks = [
            block
            for element in world_rows
            for block in build_advisor_item_evidence_blocks(
                f"- {element.name} [{element.element_type}] usage={element.usage_count}"
                + (
                    f" gap={round(float(element.gap_score), 2)}"
                    if element.gap_score is not None
                    else ""
                ),
                element.description,
            )
        ]
        evidence_groups = partition_advisor_scan_evidence(
            summaries=recent_summary_blocks,
            threads=open_thread_blocks,
            relationships=relationship_blocks,
            world_elements=world_watch_blocks,
        )
        audit_groups_total = len(evidence_groups)
        if on_audit_progress is not None:
            await on_audit_progress(0, audit_groups_total)
        cache_version = await get_book_cache_version(str(book.id))
        group_results: dict[int, dict[str, Any]] = {}
        pending_groups: list[tuple[int, tuple[dict[str, list[str]], list[str], str]]] = []
        finished_groups = 0
        for group_index, group in enumerate(evidence_groups):
            source_blocks = [item for items in group.values() for item in items]
            proactive_cache_key = make_editorial_cache_key(
                f"scan:v4:{book_id}:{total_ch}:{group_index}",
                "\n".join(source_blocks),
                heuristic_count,
            )
            proactive_result = await get_proactive_scan_cache(
                str(book.id), proactive_cache_key, version=cache_version
            )
            if proactive_result is not None:
                try:
                    if proactive_result.get("partial"):
                        raise ValueError("advisor_scan_cached_partial_result")
                    proactive_result = normalize_proactive_scan_result(
                        json.dumps(proactive_result),
                        strict=True,
                        source_blocks=source_blocks,
                    )
                except (TypeError, ValueError) as exc:
                    proactive_result = None
                    if cache_only:
                        audit_failure_category = "invalid_ai_response"
                    log.warning(
                        "advisor_proactive_scan_cache_invalid group=%s error_type=%s",
                        group_index + 1,
                        type(exc).__name__,
                    )
            if proactive_result is None:
                if cache_only:
                    continue
                if not (settings.OPENAI_API_KEY and settings.OPENAI_INTEL_MODEL):
                    audit_failure_category = "not_configured"
                    continue
                pending_groups.append((group_index, (group, source_blocks, proactive_cache_key)))
                continue
            group_results[group_index] = proactive_result
            audit_groups_completed += 1
            finished_groups += 1
            if on_audit_progress is not None:
                await on_audit_progress(finished_groups, audit_groups_total)

        if pending_groups:
            try:
                story_context = await build_story_context(db, book_id, total_ch)
                # All SQL reads are complete before parallel provider requests.
                await db.commit()
                client = get_openai_client()
            except ADVISOR_SCAN_FALLBACK_ERRORS as exc:
                if isinstance(exc, SQLAlchemyError):
                    await db.rollback()
                audit_failure_category = advisor_scan_failure_category(exc)
                log.warning(
                    "advisor_proactive_scan_setup_unavailable error_type=%s category=%s",
                    type(exc).__name__,
                    audit_failure_category,
                )
                for _ in pending_groups:
                    finished_groups += 1
                    if on_audit_progress is not None:
                        await on_audit_progress(finished_groups, audit_groups_total)
            else:

                async def scan_one(
                    group_index: int,
                    request_data: tuple[dict[str, list[str]], list[str], str],
                ) -> tuple[dict[str, Any] | None, str | None]:
                    group, source_blocks, proactive_cache_key = request_data
                    try:
                        proactive_result = await request_proactive_scan_result(
                            client=client,
                            db=db,
                            user_id=user_id,
                            book_id=book.id,
                            model=settings.OPENAI_INTEL_MODEL,
                            source_blocks=source_blocks,
                            messages=[
                                {
                                    "role": "system",
                                    "content": PROACTIVE_SCAN_SYSTEM.format(
                                        title=safe_prompt_str(book.title),
                                        story_context=safe_prompt_str(story_context),
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": PROACTIVE_SCAN_USER.format(
                                        recent_summaries="\n".join(group["summaries"])
                                        or "No recent summaries available.",
                                        open_threads="\n".join(group["threads"])
                                        or "No open threads available.",
                                        relationships="\n".join(group["relationships"])
                                        or "No relationship transitions available.",
                                        world_watch="\n".join(group["world_elements"])
                                        or "No world elements available.",
                                    ),
                                },
                            ],
                        )
                        if not proactive_result.get("partial"):
                            await set_proactive_scan_cache(
                                str(book.id),
                                proactive_cache_key,
                                proactive_result,
                                expected_version=cache_version,
                            )
                        return proactive_result, None
                    except ADVISOR_SCAN_FALLBACK_ERRORS as exc:
                        category = advisor_scan_failure_category(exc)
                        log.warning(
                            "advisor_proactive_scan_unavailable group=%s error_type=%s category=%s",
                            group_index + 1,
                            type(exc).__name__,
                            category,
                        )
                        return None, category

                async def record_group_completion(
                    group_index: int,
                    outcome: tuple[dict[str, Any] | None, str | None],
                ) -> None:
                    nonlocal audit_failure_category, audit_groups_completed, finished_groups
                    proactive_result, category = outcome
                    if category:
                        audit_failure_category = category
                    if proactive_result is not None:
                        group_results[group_index] = proactive_result
                        if proactive_result.get("partial"):
                            audit_failure_category = "invalid_ai_response"
                            log.warning(
                                "advisor_proactive_scan_partial group=%s category=%s",
                                group_index + 1,
                                audit_failure_category,
                            )
                        else:
                            audit_groups_completed += 1
                    finished_groups += 1
                    if on_audit_progress is not None:
                        await on_audit_progress(finished_groups, audit_groups_total)

                await run_bounded_scan_groups(
                    pending_groups,
                    scan_one=scan_one,
                    on_complete=record_group_completion,
                    concurrency=max(1, min(2, settings.LLM_MAX_CONCURRENT_CALLS_PER_USER)),
                )

        for group_index in sorted(group_results):
            proactive_result = group_results[group_index]
            proactive_audit_applied = True
            for finding in proactive_result.get("findings") or []:
                suggestions.append(
                    {
                        "id": proactive_advisor_finding_id(finding),
                        **finding,
                        "source": "proactive_audit",
                    }
                )
            if proactive_result.get("overall_note"):
                audit_summary = proactive_result["overall_note"]
        if audit_failure_category:
            audit_summary = (
                f"AI audit completed {audit_groups_completed} of {audit_groups_total} evidence groups; "
                "remaining groups can be retried. Heuristic checks are still shown."
            )
        elif cache_only and audit_groups_completed < audit_groups_total:
            audit_summary = (
                f"AI audit has reviewed {audit_groups_completed} of {audit_groups_total} evidence groups. "
                "Refresh checks to scan the remaining groups."
            )

    for item in suggestions:
        item.setdefault("source", "heuristic")

    deduped_suggestions: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    seen_ids: set[str] = set()
    for item in suggestions:
        finding_id = str(item.get("id") or "")
        dedupe_key = (
            " ".join(str(item.get("title") or "").split()).strip().lower(),
            " ".join(str(item.get("description") or "").split()).strip().lower(),
            " ".join(str(item.get("evidence_excerpt") or "").split()).strip().lower(),
        )
        if finding_id in seen_ids or dedupe_key in seen_keys:
            continue
        seen_ids.add(finding_id)
        seen_keys.add(dedupe_key)
        deduped_suggestions.append(item)
    suggestions = deduped_suggestions

    if (
        proactive_audit_applied
        and audit_groups_total > 1
        and audit_groups_completed == audit_groups_total
        and audit_failure_category is None
    ):
        supported_count = sum(item.get("source") == "proactive_audit" for item in suggestions)
        audit_summary = (
            f"AI audit reviewed all {audit_groups_total} evidence groups and found "
            f"{supported_count} distinct supported check{'s' if supported_count != 1 else ''}. "
            "See the findings below."
        )

    fallback_applied = False

    severity_order = {"warning": 0, "direction": 1, "opportunity": 2, "info": 3}
    suggestions.sort(key=lambda s: severity_order.get(s["severity"], 4))

    scan_basis = list(dict.fromkeys(scan_basis))
    data_gaps = list(dict.fromkeys(data_gaps))

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "book_title": book.title,
        "meta": {
            "character_count": character_count,
            "state_count": state_count,
            "open_thread_count": open_thread_count,
            "clue_count": clue_count,
            "relationship_count": relationship_count,
            "world_element_count": world_element_count,
            "heuristic_count": heuristic_count,
            "fallback_applied": fallback_applied,
            "proactive_audit_applied": proactive_audit_applied,
            "scan_basis": scan_basis,
            "data_gaps": data_gaps,
            "audit_summary": audit_summary,
            "audit_failure_category": audit_failure_category,
            "audit_groups_total": audit_groups_total,
            "audit_groups_completed": audit_groups_completed,
        },
    }
