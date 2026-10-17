"""Focused book continuity workflows."""

from __future__ import annotations

import bisect
import json
import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
)
from app.models.character import (
    Character,
    CharacterState,
)
from app.models.intelligence import (
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
)
from app.schemas.books import (
    ChapterConsistencyReport,
    ChapterEditorialConcern,
    ChapterReportCharacter,
    ChapterRevisionQuestion,
)
from app.utils.books import (
    normalization,
)
from app.utils.books.character_cards import (
    _trait_value,
)
from app.utils.books.imports import (
    report_sentence,
)


def parse_chapter_editorial_note(
    content: str | None,
) -> tuple[list[ChapterEditorialConcern] | None, ChapterRevisionQuestion | None]:
    if not content:
        return None, None
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return None, None
    items = payload if isinstance(payload, list) else payload.get("concerns") if isinstance(payload, dict) else None
    question_data = payload.get("revision_question") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None, None
    concerns: list[ChapterEditorialConcern] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        issue = " ".join(str(item.get("issue") or "").split()).strip()
        evidence = " ".join(str(item.get("evidence") or "").split()).strip()
        suggestion = " ".join(str(item.get("suggestion") or "").split()).strip()
        if issue and evidence:
            concerns.append(
                ChapterEditorialConcern(issue=issue, evidence=evidence, suggestion=suggestion)
            )
    question: ChapterRevisionQuestion | None = None
    if isinstance(question_data, dict):
        question_text = " ".join(str(question_data.get("question") or "").split()).strip()
        evidence = " ".join(str(question_data.get("evidence") or "").split()).strip()
        if question_text.endswith("?") and evidence:
            question = ChapterRevisionQuestion(question=question_text, evidence=evidence)
    return concerns, question


def as_bool(value: str | None) -> bool:
    return (str(value) if value else "").strip().lower() in {"1", "true", "yes", "on"}


def _map_chapter_consistency_state_history(
    states: Sequence[CharacterState],
) -> tuple[list[int], list[CharacterState]]:
    chapter_numbers = [int(state.at_chapter or 0) for state in states]
    return chapter_numbers, list(states)


def _latest_state_before_chapter(
    chapter_numbers: Sequence[int],
    states: Sequence[CharacterState],
    chapter_number: int,
) -> CharacterState | None:
    idx = bisect.bisect_left(chapter_numbers, chapter_number) - 1
    if idx < 0:
        return None
    return states[idx]


def _detect_continuity_flags_from_rows(
    *,
    work_type: str,
    chapter_number: int,
    rows: Sequence[tuple[CharacterState, str]],
    prior_states_by_character: dict[uuid.UUID, tuple[list[int], list[CharacterState]]],
) -> list[str]:
    if not rows:
        return []

    flags: list[str] = []
    watched_traits = {
        "eyes": "eye description",
        "hair": "hair description",
        "build": "build description",
        "age_descriptor": "age description",
        "distinguishing": "distinguishing feature",
    }

    for state, char_name in rows:
        state_history = prior_states_by_character.get(state.character_id)
        if state_history is None:
            continue
        previous = _latest_state_before_chapter(state_history[0], state_history[1], chapter_number)
        if previous is None:
            continue
        current_snapshot = state.trait_snapshot or {}
        previous_snapshot = previous.trait_snapshot or {}
        for trait_key, label in watched_traits.items():
            previous_value = _trait_value(previous_snapshot.get(trait_key))
            current_value = _trait_value(current_snapshot.get(trait_key))
            if previous_value and current_value and previous_value.lower() != current_value.lower():
                flags.append(
                    f"{char_name}: {label} changed from '{previous_value}' to '{current_value}' since {normalization.story_unit_label(work_type, previous.at_chapter, lowercase=True)}."
                )
                break

    return flags


async def _load_chapter_consistency_context(
    db: AsyncSession,
    book: Book,
    chapter_numbers: Sequence[int],
) -> dict[str, Any]:
    unique_chapter_numbers = sorted({int(number) for number in chapter_numbers if int(number) > 0})
    if not unique_chapter_numbers:
        return {
            "chapters_by_number": {},
            "summary_by_chapter_id": {},
            "editorial_by_chapter_id": {},
            "new_characters_by_chapter": {},
            "names_by_id": {},
            "relationships_by_chapter": {},
            "opened_threads_by_chapter": {},
            "resolved_threads_by_chapter": {},
            "continuity_flags_by_chapter": {},
        }

    chapters = (
        (
            await db.execute(
                select(Chapter).where(
                    Chapter.book_id == book.id, Chapter.number.in_(unique_chapter_numbers)
                )
            )
        )
        .scalars()
        .all()
    )
    chapters_by_number = {
        int(chapter.number): chapter for chapter in chapters if chapter.number is not None
    }
    chapter_ids = [chapter.id for chapter in chapters]

    summary_rows = (
        (
            await db.execute(
                select(ChapterSummary).where(
                    ChapterSummary.chapter_id.in_(chapter_ids),
                    ChapterSummary.mode.in_(("short", "editorial_note")),
                )
            )
        )
        .scalars()
        .all()
        if chapter_ids
        else []
    )
    summary_by_chapter_id = {
        summary.chapter_id: summary for summary in summary_rows if summary.mode == "short"
    }
    editorial_by_chapter_id = {
        summary.chapter_id: summary for summary in summary_rows if summary.mode == "editorial_note"
    }

    new_characters = (
        (
            await db.execute(
                select(Character)
                .where(
                    Character.book_id == book.id,
                    Character.first_chapter.in_(unique_chapter_numbers),
                )
                .order_by(Character.first_chapter.asc(), Character.name)
            )
        )
        .scalars()
        .all()
    )
    new_characters_by_chapter: dict[int, list[Character]] = {}
    for character in new_characters:
        if character.first_chapter is None:
            continue
        new_characters_by_chapter.setdefault(int(character.first_chapter), []).append(character)

    character_names = (
        await db.execute(select(Character.id, Character.name).where(Character.book_id == book.id))
    ).all()
    names_by_id = {char_id: name for char_id, name in character_names}

    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(
                    CharacterRelationship.book_id == book.id,
                    CharacterRelationship.from_chapter.in_(unique_chapter_numbers),
                )
            )
        )
        .scalars()
        .all()
    )
    relationships_by_chapter: dict[int, list[CharacterRelationship]] = {}
    for relationship in relationships:
        if relationship.from_chapter is None:
            continue
        relationships_by_chapter.setdefault(int(relationship.from_chapter), []).append(relationship)

    plot_threads = (
        (
            await db.execute(
                select(PlotThread)
                .where(PlotThread.book_id == book.id)
                .where(
                    (PlotThread.introduced_at.in_(unique_chapter_numbers))
                    | (PlotThread.resolved_at.in_(unique_chapter_numbers))
                )
                .order_by(PlotThread.importance.desc(), PlotThread.title)
            )
        )
        .scalars()
        .all()
    )
    opened_threads_by_chapter: dict[int, list[PlotThread]] = {}
    resolved_threads_by_chapter: dict[int, list[PlotThread]] = {}
    for thread in plot_threads:
        if thread.introduced_at is not None and int(thread.introduced_at) in unique_chapter_numbers:
            opened_threads_by_chapter.setdefault(int(thread.introduced_at), []).append(thread)
        if thread.resolved_at is not None and int(thread.resolved_at) in unique_chapter_numbers:
            resolved_threads_by_chapter.setdefault(int(thread.resolved_at), []).append(thread)

    continuity_state_rows = (
        await db.execute(
            select(CharacterState, Character.name)
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book.id,
                CharacterState.at_chapter.in_(unique_chapter_numbers),
            )
        )
    ).all()
    continuity_rows_by_chapter: dict[int, list[tuple[CharacterState, str]]] = {}
    tracked_character_ids = {
        state.character_id
        for state, _char_name in continuity_state_rows
        if state.character_id is not None
    }
    for state, char_name in continuity_state_rows:
        if state.at_chapter is None:
            continue
        continuity_rows_by_chapter.setdefault(int(state.at_chapter), []).append((state, char_name))

    max_chapter_number = max(unique_chapter_numbers)
    prior_states = (
        (
            await db.execute(
                select(CharacterState)
                .where(
                    CharacterState.character_id.in_(tracked_character_ids),
                    CharacterState.at_chapter < max_chapter_number,
                )
                .order_by(CharacterState.character_id.asc(), CharacterState.at_chapter.asc())
            )
        )
        .scalars()
        .all()
        if tracked_character_ids
        else []
    )
    prior_states_by_character: dict[uuid.UUID, tuple[list[int], list[CharacterState]]] = {}
    grouped_states: dict[uuid.UUID, list[CharacterState]] = {}
    for state in prior_states:
        if state.character_id is None or state.at_chapter is None:
            continue
        grouped_states.setdefault(state.character_id, []).append(state)
    for character_id, states in grouped_states.items():
        prior_states_by_character[character_id] = _map_chapter_consistency_state_history(states)

    continuity_flags_by_chapter = {
        chapter_number: _detect_continuity_flags_from_rows(
            work_type=book.work_type or "novel",
            chapter_number=chapter_number,
            rows=rows,
            prior_states_by_character=prior_states_by_character,
        )
        for chapter_number, rows in continuity_rows_by_chapter.items()
    }

    return {
        "chapters_by_number": chapters_by_number,
        "summary_by_chapter_id": summary_by_chapter_id,
        "editorial_by_chapter_id": editorial_by_chapter_id,
        "new_characters_by_chapter": new_characters_by_chapter,
        "names_by_id": names_by_id,
        "relationships_by_chapter": relationships_by_chapter,
        "opened_threads_by_chapter": opened_threads_by_chapter,
        "resolved_threads_by_chapter": resolved_threads_by_chapter,
        "continuity_flags_by_chapter": continuity_flags_by_chapter,
    }


async def build_chapter_consistency_report(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
) -> ChapterConsistencyReport:
    context = await _load_chapter_consistency_context(db, book, [chapter_number])
    chapter = context["chapters_by_number"].get(chapter_number)
    if chapter is None:
        raise HTTPException(404, "Chapter not found")

    short_summary = context["summary_by_chapter_id"].get(chapter.id)
    editorial_note = context["editorial_by_chapter_id"].get(chapter.id)
    new_characters = context["new_characters_by_chapter"].get(chapter_number, [])
    names_by_id = context["names_by_id"]

    relationship_changes = []
    seen_relationships: set[tuple[str, str, str]] = set()
    rels = context["relationships_by_chapter"].get(chapter_number, [])
    for rel in rels:
        a_name = names_by_id.get(rel.character_a_id, "Unknown")
        b_name = names_by_id.get(rel.character_b_id, "Unknown")
        key = tuple(sorted((a_name, b_name)) + [rel.rel_type])
        if key in seen_relationships:
            continue
        seen_relationships.add(key)
        relationship_changes.append(
            f"{a_name} and {b_name}: {rel.rel_type.replace('_', ' ')}"
            + (f" - {rel.description}" if rel.description else "")
        )

    opened_threads = context["opened_threads_by_chapter"].get(chapter_number, [])
    resolved_threads = context["resolved_threads_by_chapter"].get(chapter_number, [])
    continuity_flags = context["continuity_flags_by_chapter"].get(chapter_number, [])
    summary_line = report_sentence(short_summary.content if short_summary else "")
    if not summary_line:
        summary_line = (
            f"{normalization.story_unit_label(book, chapter_number)} was imported and analysed."
        )

    additions = []
    if new_characters:
        additions.append(
            f"{len(new_characters)} new character{'s' if len(new_characters) != 1 else ''}"
        )
    if relationship_changes:
        additions.append(
            f"{len(relationship_changes)} relationship shift{'s' if len(relationship_changes) != 1 else ''}"
        )
    if opened_threads:
        additions.append(
            f"{len(opened_threads)} plot thread{'s' if len(opened_threads) != 1 else ''} opened"
        )
    if resolved_threads:
        additions.append(f"{len(resolved_threads)} resolved")
    if continuity_flags:
        additions.append(
            f"{len(continuity_flags)} continuity flag{'s' if len(continuity_flags) != 1 else ''}"
        )
    if additions:
        summary_line = f"{summary_line} This upload surfaced " + ", ".join(additions) + "."

    editorial_concerns, revision_question = (
        parse_chapter_editorial_note(editorial_note.content)
        if editorial_note else (None, None)
    )

    return ChapterConsistencyReport(
        chapter_number=chapter_number,
        chapter_title=chapter.title,
        summary=summary_line,
        new_characters=[
            ChapterReportCharacter(
                id=str(char.id),
                name=char.name,
                role=char.role,
                first_chapter=char.first_chapter,
                arc_summary=char.arc_summary,
            )
            for char in new_characters
        ],
        relationship_changes=list(dict.fromkeys(relationship_changes[:6])),
        plot_threads_opened=list(dict.fromkeys(thread.title for thread in opened_threads[:6])),
        plot_threads_resolved=list(dict.fromkeys(thread.title for thread in resolved_threads[:6])),
        continuity_flags=list(dict.fromkeys(continuity_flags[:6])),
        editorial_concerns=editorial_concerns,
        revision_question=revision_question,
    )


async def detect_chapter_continuity_flags(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_number: int,
) -> list[str]:
    work_type = await db.scalar(select(Book.work_type).where(Book.id == book_id)) or "novel"
    rows = (
        await db.execute(
            select(CharacterState, Character.name)
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book_id,
                CharacterState.at_chapter == chapter_number,
            )
        )
    ).all()
    tracked_character_ids = {
        state.character_id for state, _char_name in rows if state.character_id is not None
    }
    prior_states = (
        (
            await db.execute(
                select(CharacterState)
                .where(
                    CharacterState.character_id.in_(tracked_character_ids),
                    CharacterState.at_chapter < chapter_number,
                )
                .order_by(CharacterState.character_id.asc(), CharacterState.at_chapter.asc())
            )
        )
        .scalars()
        .all()
        if tracked_character_ids
        else []
    )
    grouped_states: dict[uuid.UUID, list[CharacterState]] = {}
    for state in prior_states:
        if state.character_id is None or state.at_chapter is None:
            continue
        grouped_states.setdefault(state.character_id, []).append(state)
    prior_states_by_character = {
        character_id: _map_chapter_consistency_state_history(states)
        for character_id, states in grouped_states.items()
    }
    return _detect_continuity_flags_from_rows(
        work_type=work_type,
        chapter_number=chapter_number,
        rows=rows,
        prior_states_by_character=prior_states_by_character,
    )
