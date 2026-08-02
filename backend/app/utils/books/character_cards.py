"""Focused book character cards workflows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
)
from app.models.character import (
    Character,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import (
    CharacterRelationship,
    PlotThread,
)
from app.utils.books import (
    normalization,
)
from app.utils.plot_thread_utils import (
    is_plot_thread_closed,
)


def _trait_value(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("value")
        return value.strip() if isinstance(value, str) and value.strip() else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


async def build_character_card_payload(db: AsyncSession, book: Book, character: Character) -> dict:
    def _reference_keys() -> set[str]:
        keys = {
            " ".join((character.name or "").split()).strip().lower(),
            str(character.id).strip().lower(),
        }
        keys.update(
            " ".join(str(alias or "").split()).strip().lower()
            for alias in (character.aliases or [])
        )
        return {key for key in keys if key}

    reference_keys = _reference_keys()

    rels = (
        (
            await db.execute(
                select(CharacterRelationship)
                .where(
                    CharacterRelationship.book_id == book.id,
                    (CharacterRelationship.character_a_id == character.id)
                    | (CharacterRelationship.character_b_id == character.id),
                )
                .order_by(CharacterRelationship.from_chapter, CharacterRelationship.id)
            )
        )
        .scalars()
        .all()
    )

    other_ids = {
        rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        for rel in rels
    }
    others = (
        (await db.execute(select(Character).where(Character.id.in_(other_ids)))).scalars().all()
        if other_ids
        else []
    )
    others_by_id = {other.id: other for other in others}
    counterpart_names = {other.id: other.name for other in others}

    from app.engine.character.profile_builder import build_description
    from app.utils.characters.governance import character_status
    from app.utils.characters.tracking import build_character_arc_tracker

    relationship_rows = []
    for rel in rels:
        counterpart_id = (
            rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        )
        counterpart = others_by_id.get(counterpart_id)
        relationship_rows.append(
            {
                "name": counterpart.name if counterpart else "Unknown character",
                "type": rel.rel_type.replace("_", " "),
                "description": rel.description,
                "sentiment": rel.sentiment,
                "from_chapter": rel.from_chapter,
                "to_chapter": rel.to_chapter,
            }
        )

    description = build_description(character.trait_state or {}, character.archetype)
    filename_source = " ".join(part for part in [book.title, character.name] if part).strip()
    safe_name = (
        "".join(
            ch for ch in (filename_source or "character") if ch.isalnum() or ch in {" ", "-", "_"}
        )
        .strip()
        .replace(" ", "-")
        or "character"
    )
    linked_threads = (
        (
            await db.execute(
                select(PlotThread)
                .where(PlotThread.book_id == book.id)
                .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
            )
        )
        .scalars()
        .all()
    )
    character_threads = [
        {
            "title": thread.title,
            "status": thread.status,
            "introduced_at": thread.introduced_at,
            "resolved_at": thread.resolved_at,
            "note": thread.note,
        }
        for thread in linked_threads
        if any(
            " ".join(str(item or "").split()).strip().lower() in reference_keys
            for item in (thread.character_ids or [])
        )
    ]
    continuity_watch: list[str] = []
    if (
        character.last_seen_chapter
        and book.total_chapters
        and book.total_chapters - character.last_seen_chapter >= 25
    ):
        story_units = normalization.story_unit_name(book, plural=True, lowercase=True)
        continuity_watch.append(
            f"{character.name} has not appeared for {book.total_chapters - character.last_seen_chapter} {story_units}."
        )
    if character_threads:
        unresolved = [
            thread["title"]
            for thread in character_threads
            if not is_plot_thread_closed(thread["status"])
        ]
        if unresolved:
            continuity_watch.append(
                f"Still tied to unresolved threads: {', '.join(unresolved[:3])}."
            )
    states = (
        (
            await db.execute(
                select(CharacterState)
                .where(CharacterState.character_id == character.id)
                .order_by(CharacterState.at_chapter)
            )
        )
        .scalars()
        .all()
    )
    voice_profile = (
        await db.execute(
            select(CharacterVoiceProfile).where(CharacterVoiceProfile.character_id == character.id)
        )
    ).scalar_one_or_none()
    return {
        "book_title": book.title,
        "work_type": book.work_type,
        "character_id": str(character.id),
        "name": character.name,
        "aliases": character.aliases or [],
        "role": character.role,
        "status": character_status(character),
        "description": description,
        "first_appearance": character.first_chapter,
        "last_appearance": character.last_seen_chapter,
        "mentions_count": character.mention_count or 0,
        "personality_tags": character.personality_tags or [],
        "goal": character.goal,
        "motivations": character.motivations or [],
        "fears": character.fears or [],
        "lie_they_believe": character.lie_they_believe,
        "backstory_wound": character.backstory_wound,
        "arc_type": character.arc_type,
        "arc_summary": character.arc_summary,
        "growth_events": character.growth_events or [],
        "relationships": relationship_rows,
        "plot_threads": character_threads,
        "continuity_watch": continuity_watch,
        "arc_tracker": build_character_arc_tracker(
            character,
            states=list(states),
            relationships=list(rels),
            counterpart_names=counterpart_names,
            voice_profile=voice_profile,
            total_chapters=book.total_chapters,
        ),
        "filename_base": safe_name,
    }
