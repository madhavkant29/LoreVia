from __future__ import annotations

import logging
import uuid
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_proactive_scan_cache, set_proactive_scan_cache
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, WorldElement
from app.utils.advisor_prompt_templates import PROACTIVE_SCAN_SYSTEM, PROACTIVE_SCAN_USER
from app.utils.advisor_prompt_utils import make_editorial_cache_key, safe_prompt_str
from app.utils.advisor_result_utils import (
    build_fallback_advisor_suggestions,
    normalize_proactive_scan_result,
)
from app.utils.advisor_story_context_utils import build_story_context
from app.utils.advisor_suggestions_utils import (
    build_relationship_drift_suggestions,
    build_world_drift_suggestions,
)
from app.utils.llm_usage_utils import create_tracked_chat_completion
from app.utils.plot_thread_utils import derive_plot_thread_status, is_plot_thread_open

log = logging.getLogger(__name__)

ADVISOR_SCAN_FALLBACK_ERRORS = (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAIError,
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

    relationship_rows = (
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
    relationship_count = len(relationship_rows)
    if relationship_count:
        scan_basis.append("relationships")
    else:
        data_gaps.append("relationships")

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

    recent_summaries = (
        await db.execute(
            select(ChapterSummary.clues, Chapter.number, Chapter.title)
            .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "short",
                ChapterSummary.clues.isnot(None),
            )
            .order_by(Chapter.number.asc())
            .limit(10)
        )
    ).all()
    clue_count = 0
    if recent_summaries:
        scan_basis.append("chapter summaries")
    else:
        data_gaps.append("chapter summaries")

    seen_clues: set[str] = set()
    for clues, chapter_num, chapter_title in recent_summaries:
        if not clues:
            continue
        clue_list = (
            clues
            if isinstance(clues, list)
            else list(clues.values())
            if isinstance(clues, dict)
            else []
        )
        clue_count += len(clue_list)
        for clue in clue_list[:2]:
            clue_str = str(clue)[:120]
            if clue_str not in seen_clues:
                seen_clues.add(clue_str)
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
            if len(seen_clues) >= 3:
                break
        if len(seen_clues) >= 3:
            break

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

    for thread in [
        item
        for item in all_threads
        if item.status == "contradicted" or thread_statuses[item.id] == "contradicted"
    ][:2]:
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
    if not skip_llm and heuristic_count < 3 and (recent_summaries or open_threads or world_rows):
        detailed_summary_rows = (
            await db.execute(
                select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events)
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == book_id,
                    ChapterSummary.mode.in_(["short", "detailed"]),
                )
                .order_by(Chapter.number.desc(), ChapterSummary.mode.asc())
                .limit(10)
            )
        ).all()
        recent_summary_blocks: list[str] = []
        seen_summary_chapters: set[int] = set()
        for chapter_num, chapter_title, content, key_events in detailed_summary_rows:
            if chapter_num in seen_summary_chapters:
                continue
            seen_summary_chapters.add(chapter_num)
            key_bits: list[str] = []
            if isinstance(key_events, list):
                for item in key_events[:3]:
                    if isinstance(item, dict):
                        key_bits.append(
                            " ".join(
                                str(item.get("event_title") or item.get("event") or "").split()
                            ).strip()
                        )
            key_line = "; ".join(item for item in key_bits if item)
            recent_summary_blocks.append(
                f"Chapter {chapter_num} ({chapter_title or 'Untitled'}): "
                f"{' '.join(str(content or '').split())[:240]}"
                + (f" Key events: {key_line[:180]}" if key_line else "")
            )
            if len(recent_summary_blocks) >= 4:
                break

        open_thread_blocks = [
            f"- {thread.title} [{thread_statuses[thread.id]}]"
            + (f" introduced ch.{thread.introduced_at}" if thread.introduced_at else "")
            + (
                f": {' '.join(str(thread.description or '').split())[:160]}"
                if thread.description
                else ""
            )
            for thread in open_threads[:5]
        ]
        relationship_blocks = [
            f"- {character_names.get(rel.character_a_id, 'Unknown')} / {character_names.get(rel.character_b_id, 'Unknown')}: "
            f"{rel.rel_type.replace('_', ' ')} at chapter {rel.from_chapter}"
            + (f". {' '.join(str(rel.description or '').split())[:140]}" if rel.description else "")
            for rel in relationship_rows[-5:]
        ]
        world_watch_blocks = [
            f"- {element.name} [{element.element_type}] usage={element.usage_count}"
            + (
                f" gap={round(float(element.gap_score), 2)}"
                if element.gap_score is not None
                else ""
            )
            + (
                f". {' '.join(str(element.description or '').split())[:160]}"
                if element.description
                else ""
            )
            for element in world_rows[:6]
        ]
        story_context = await build_story_context(db, book_id, total_ch)
        proactive_cache_key = make_editorial_cache_key(
            f"scan:{book_id}:{total_ch}",
            "\n".join(recent_summary_blocks + open_thread_blocks + world_watch_blocks),
            heuristic_count,
        )
        proactive_result = await get_proactive_scan_cache(str(book.id), proactive_cache_key)
        if proactive_result is None:
            if settings.OPENAI_API_KEY and settings.OPENAI_INTEL_MODEL:
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                try:
                    response = await create_tracked_chat_completion(
                        client=client,
                        feature="advisor_proactive_scan",
                        model=settings.OPENAI_INTEL_MODEL,
                        db=db,
                        user_id=user_id,
                        book_id=book.id,
                        temperature=0.2,
                        max_tokens=900,
                        response_format={"type": "json_object"},
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
                                    recent_summaries="\n".join(recent_summary_blocks)
                                    or "No recent summaries available.",
                                    open_threads="\n".join(open_thread_blocks)
                                    or "No open threads available.",
                                    relationships="\n".join(relationship_blocks)
                                    or "No relationship transitions available.",
                                    world_watch="\n".join(world_watch_blocks)
                                    or "No world elements available.",
                                ),
                            },
                        ],
                    )
                    proactive_result = normalize_proactive_scan_result(
                        response.choices[0].message.content or "{}"
                    )
                    await set_proactive_scan_cache(
                        str(book.id), proactive_cache_key, proactive_result
                    )
                except ADVISOR_SCAN_FALLBACK_ERRORS:
                    proactive_result = {
                        "findings": [],
                        "overall_note": "Proactive audit was unavailable, so this scan is showing heuristic-only results.",
                    }
                finally:
                    await client.close()
            else:
                proactive_result = {
                    "findings": [],
                    "overall_note": "Proactive audit is unavailable until AI scan settings are configured.",
                }

        proactive_findings = (proactive_result or {}).get("findings") or []
        for index, finding in enumerate(proactive_findings):
            suggestions.append(
                {
                    "id": f"proactive-{index}-{finding['type']}",
                    **finding,
                    "source": "proactive_audit",
                }
            )
        proactive_audit_applied = bool(proactive_findings)
        audit_summary = (proactive_result or {}).get("overall_note") or None

    for item in suggestions:
        item.setdefault("source", "heuristic")

    deduped_suggestions: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in suggestions:
        dedupe_key = (
            " ".join(str(item.get("title") or "").split()).strip().lower(),
            " ".join(str(item.get("description") or "").split()).strip().lower(),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_suggestions.append(item)
    suggestions = deduped_suggestions

    fallback_applied = False
    if not suggestions:
        focus_thread = None
        if open_threads:
            thread = open_threads[0]
            focus_thread = {
                "title": thread.title,
                "introduced_at": thread.introduced_at,
                "description": thread.description,
            }
        suggestions = [
            {**item, "source": "fallback"}
            for item in build_fallback_advisor_suggestions(
                book_title=book.title,
                total_chapters=total_ch,
                character_count=character_count,
                open_thread_count=open_thread_count,
                focus_thread=focus_thread,
            )
        ]
        fallback_applied = True

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
        },
    }
