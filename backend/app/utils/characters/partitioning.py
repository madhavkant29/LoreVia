"""Focused character partitioning workflows."""

from __future__ import annotations

import uuid
from typing import Any

from openai import OpenAIError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.profile_builder import (
    choose_richer_text,
    flat,
    merge_growth_events,
    merge_list_values,
    merge_trait_states,
)
from app.models.book import Chapter
from app.models.character import (
    Character,
    CharacterState,
)
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
    WikiEntry,
)
from app.utils.characters.classification import (
    update_character_classification,
)
from app.utils.characters.identity import (
    normalize_character_name,
    partition_identity_key,
)
from app.utils.characters.manual import (
    _character_reference_values,
    _expand_reference_list,
    _find_name_occurrences,
    _normalize_character_reference,
)
from app.utils.characters.merging import (
    _dedupe_relationships,
)
from app.utils.characters.text import clean_optional_text, clean_string_list

PARTITION_ENRICHMENT_EXCEPTIONS = (
    OpenAIError,
    TimeoutError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _collect_partition_evidence(
    chapter_rows: list[tuple[int, str]],
    *,
    name: str,
    aliases: list[str],
) -> dict[str, Any]:
    candidates = merge_list_values([name], aliases)
    snippets: list[str] = []
    chapter_counts: dict[int, int] = {}
    mention_count = 0
    for chapter_number, text in chapter_rows:
        score = sum(_find_name_occurrences(text, candidate) for candidate in candidates)
        if score <= 0:
            continue
        mention_count += score
        chapter_counts[chapter_number] = chapter_counts.get(chapter_number, 0) + score
        if len(snippets) < 6:
            snippets.append(text[:2200])
    ordered_chapters = sorted(chapter_counts)
    return {
        "chapter_counts": chapter_counts,
        "snippets": snippets,
        "mention_count": mention_count,
        "first_chapter": ordered_chapters[0] if ordered_chapters else None,
        "last_seen_chapter": ordered_chapters[-1] if ordered_chapters else None,
    }


def _partition_matches_entity(name: str, aliases: list[str], entity: dict[str, Any]) -> bool:
    from app.engine.character.deduplicator import names_equivalent

    entity_name = str(entity.get("name") or "").strip()
    entity_aliases = [str(alias) for alias in (entity.get("aliases") or []) if str(alias).strip()]
    if not entity_name:
        return False
    if names_equivalent(name, aliases, entity_name, entity_aliases):
        return True
    partition_keys = {
        normalize_character_name(name),
        *(normalize_character_name(alias) for alias in aliases),
    }
    entity_keys = {
        normalize_character_name(entity_name),
        *(normalize_character_name(alias) for alias in entity_aliases),
    }
    partition_keys.discard("")
    entity_keys.discard("")
    return bool(partition_keys & entity_keys)


def _merge_partition_entities(
    name: str, aliases: list[str], entities: list[dict[str, Any]]
) -> dict[str, Any]:
    merged_traits: dict[str, Any] = {}
    merged_growth_events: list[dict] = []
    merged_personality: list[str] = []
    merged_motivations: list[str] = []
    merged_fears: list[str] = []
    merged_aliases = merge_list_values([name], aliases)
    merged: dict[str, Any] = {
        "name": name,
        "aliases": aliases,
        "role": None,
        "goal": None,
        "lie_they_believe": None,
        "backstory_wound": None,
        "arc_type": None,
        "arc_summary": None,
        "archetype": None,
    }

    for entity in entities:
        merged_traits = merge_trait_states(
            merged_traits, entity.get("traits") if isinstance(entity.get("traits"), dict) else {}
        )
        merged_aliases = merge_list_values(
            merged_aliases, entity.get("aliases") if isinstance(entity.get("aliases"), list) else []
        )
        merged_personality = merge_list_values(
            merged_personality,
            entity.get("personality_tags")
            if isinstance(entity.get("personality_tags"), list)
            else [],
        )
        merged_motivations = merge_list_values(
            merged_motivations,
            entity.get("motivations") if isinstance(entity.get("motivations"), list) else [],
        )
        merged_fears = merge_list_values(
            merged_fears, entity.get("fears") if isinstance(entity.get("fears"), list) else []
        )
        if not merged["role"]:
            merged["role"] = entity.get("role")
        merged["goal"] = choose_richer_text(merged["goal"], entity.get("goal"))
        merged["lie_they_believe"] = choose_richer_text(
            merged["lie_they_believe"], entity.get("lie_they_believe")
        )
        merged["backstory_wound"] = choose_richer_text(
            merged["backstory_wound"], entity.get("backstory_wound")
        )
        merged["arc_type"] = choose_richer_text(merged["arc_type"], entity.get("arc_type"))
        merged["arc_summary"] = choose_richer_text(merged["arc_summary"], entity.get("arc_summary"))
        merged["archetype"] = choose_richer_text(merged["archetype"], entity.get("archetype"))
        growth_event = entity.get("growth_event")
        merged_growth_events = merge_growth_events(
            merged_growth_events, [growth_event] if isinstance(growth_event, dict) else []
        )

    merged["traits"] = merged_traits
    merged["aliases"] = [
        alias
        for alias in merged_aliases
        if normalize_character_name(alias) != normalize_character_name(name)
    ]
    merged["personality_tags"] = merged_personality
    merged["motivations"] = merged_motivations
    merged["fears"] = merged_fears
    merged["growth_events"] = merged_growth_events
    return merged


async def _build_partition_payload(
    *,
    source: Character,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    aliases: list[str],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    if evidence["snippets"]:
        try:
            extracted = await extract_characters_and_relationships(
                "\n\n".join(evidence["snippets"])[:12000],
                user_id=user_id,
                book_id=book_id,
            )
            entities = [
                entity
                for entity in extracted.get("characters", [])
                if isinstance(entity, dict) and _partition_matches_entity(name, aliases, entity)
            ]
        except PARTITION_ENRICHMENT_EXCEPTIONS:
            entities = []

    merged_entity = _merge_partition_entities(name, aliases, entities)
    trait_state = merge_trait_states(
        {}, merged_entity.get("traits") if isinstance(merged_entity.get("traits"), dict) else {}
    )
    first_chapter = int(evidence.get("first_chapter") or source.first_chapter or 1)
    last_seen_chapter = int(
        evidence.get("last_seen_chapter")
        or source.last_seen_chapter
        or source.first_chapter
        or first_chapter
    )
    mention_count = max(1, int(evidence.get("mention_count") or 0))

    return {
        "book_id": book_id,
        "name": name,
        "aliases": merged_entity.get("aliases") or aliases,
        "role": merged_entity.get("role") or source.role,
        "first_chapter": first_chapter,
        "last_seen_chapter": last_seen_chapter,
        "mention_count": mention_count,
        "trait_state": trait_state,
        "hair": flat(trait_state, "hair"),
        "eyes": flat(trait_state, "eyes"),
        "build": flat(trait_state, "build"),
        "age_descriptor": flat(trait_state, "age"),
        "distinguishing": flat(trait_state, "distinguishing"),
        "personality_tags": merged_entity.get("personality_tags") or [],
        "goal": merged_entity.get("goal"),
        "motivations": merged_entity.get("motivations") or [],
        "fears": merged_entity.get("fears") or [],
        "lie_they_believe": merged_entity.get("lie_they_believe"),
        "backstory_wound": merged_entity.get("backstory_wound"),
        "arc_type": merged_entity.get("arc_type"),
        "arc_summary": merged_entity.get("arc_summary"),
        "archetype": merged_entity.get("archetype"),
        "growth_events": merged_entity.get("growth_events") or [],
    }


def _best_partition_for_chapter(
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
    chapter_number: int | None,
) -> Character | None:
    if chapter_number is None:
        return None
    scored = [
        (
            int(
                (evidence_by_character_id.get(character.id) or {})
                .get("chapter_counts", {})
                .get(chapter_number, 0)
            ),
            character,
        )
        for character in partitions
    ]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _best_partition_for_text(
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
    text: str | None,
) -> Character | None:
    scored = []
    for character in partitions:
        candidates = merge_list_values([character.name], character.aliases or [])
        score = sum(_find_name_occurrences(text or "", candidate) for candidate in candidates)
        if score > 0:
            scored.append((score, character))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return None
        return scored[0][1]
    return None


async def _reassign_partition_references(
    db: AsyncSession,
    *,
    source: Character,
    partitions: list[Character],
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]],
) -> None:
    primary_partition = max(
        partitions,
        key=lambda character: int(
            (evidence_by_character_id.get(character.id) or {}).get("mention_count", 0)
        ),
    )
    reference_values = _character_reference_values(source)

    state_rows = (
        (await db.execute(select(CharacterState).where(CharacterState.character_id == source.id)))
        .scalars()
        .all()
    )
    for state in state_rows:
        target = (
            _best_partition_for_chapter(partitions, evidence_by_character_id, state.at_chapter)
            or primary_partition
        )
        state.character_id = target.id

    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(
                    CharacterRelationship.book_id == source.book_id,
                    or_(
                        CharacterRelationship.character_a_id == source.id,
                        CharacterRelationship.character_b_id == source.id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    for relationship in relationships:
        target = (
            _best_partition_for_chapter(
                partitions, evidence_by_character_id, relationship.from_chapter
            )
            or primary_partition
        )
        if relationship.character_a_id == source.id:
            relationship.character_a_id = target.id
        if relationship.character_b_id == source.id:
            relationship.character_b_id = target.id
        if relationship.character_a_id == relationship.character_b_id:
            await db.delete(relationship)

    plot_threads = (
        (await db.execute(select(PlotThread).where(PlotThread.book_id == source.book_id)))
        .scalars()
        .all()
    )
    for thread in plot_threads:
        updated_ids = _expand_reference_list(
            thread.character_ids,
            matches=reference_values,
            replacements=[character.name for character in partitions],
        )
        if updated_ids:
            thread.character_ids = updated_ids

    wiki_entries = (
        (await db.execute(select(WikiEntry).where(WikiEntry.book_id == source.book_id)))
        .scalars()
        .all()
    )
    for entry in wiki_entries:
        updated_related = _expand_reference_list(
            entry.related_char_ids,
            matches=reference_values,
            replacements=[str(character.id) for character in partitions],
        )
        if updated_related:
            entry.related_char_ids = updated_related

    chapter_summaries = (
        await db.execute(
            select(ChapterSummary, Chapter.number)
            .join(ChapterSummary.chapter)
            .where(Chapter.book_id == source.book_id)
        )
    ).all()
    for summary, chapter_number in chapter_summaries:
        target = (
            _best_partition_for_chapter(partitions, evidence_by_character_id, chapter_number)
            or primary_partition
        )
        key_events = [
            dict(event) if isinstance(event, dict) else event
            for event in (summary.key_events or [])
        ]
        key_events_changed = False
        for event in key_events:
            if not isinstance(event, dict):
                continue
            involved = _expand_reference_list(
                event.get("involved_characters"),
                matches=reference_values,
                replacements=[str(target.id)],
            )
            if involved != list(event.get("involved_characters") or []):
                event["involved_characters"] = involved
                key_events_changed = True
        if key_events_changed:
            summary.key_events = key_events

        char_changes = [
            dict(change) if isinstance(change, dict) else change
            for change in (summary.char_changes or [])
        ]
        char_changes_changed = False
        for change in char_changes:
            if not isinstance(change, dict):
                continue
            candidate = " ".join(str(change.get("character") or "").split()).strip()
            if candidate and _normalize_character_reference(candidate) in reference_values:
                change["character"] = target.name
                char_changes_changed = True
        if char_changes_changed:
            summary.char_changes = char_changes

    quotes = (
        (await db.execute(select(QuoteEntry).where(QuoteEntry.book_id == source.book_id)))
        .scalars()
        .all()
    )
    for quote in quotes:
        if _normalize_character_reference(quote.character_name) not in reference_values:
            continue
        target = (
            _best_partition_for_text(partitions, evidence_by_character_id, quote.quote_text)
            or primary_partition
        )
        quote.character_name = target.name


async def partition_character(
    db: AsyncSession,
    *,
    source: Character,
    user_id: uuid.UUID,
    partitions: list[dict[str, list[str] | str]],
) -> list[Character]:
    cleaned_partitions: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for partition in partitions:
        cleaned_name = clean_optional_text(partition.get("name"))
        if not cleaned_name:
            continue
        normalized_name = normalize_character_name(cleaned_name)
        identity_key = partition_identity_key(cleaned_name)
        if not identity_key or identity_key in seen_names:
            continue
        seen_names.add(identity_key)
        aliases = [
            alias
            for alias in clean_string_list(
                partition.get("aliases") if isinstance(partition.get("aliases"), list) else []
            )
            if normalize_character_name(alias) != normalized_name
        ]
        cleaned_partitions.append({"name": cleaned_name, "aliases": aliases})

    if len(cleaned_partitions) < 2:
        raise ValueError("At least two distinct partition targets are required")

    chapter_rows = (
        await db.execute(
            select(Chapter.number, BookChunk.text)
            .join(BookChunk, BookChunk.chapter_id == Chapter.id)
            .where(BookChunk.book_id == source.book_id)
            .order_by(Chapter.number.asc(), BookChunk.chunk_index.asc())
        )
    ).all()

    created_partitions: list[Character] = []
    evidence_by_character_id: dict[uuid.UUID, dict[str, Any]] = {}
    for partition in cleaned_partitions:
        evidence = _collect_partition_evidence(
            chapter_rows,
            name=str(partition["name"]),
            aliases=[str(alias) for alias in partition["aliases"]],
        )
        payload = await _build_partition_payload(
            source=source,
            book_id=source.book_id,
            user_id=user_id,
            name=str(partition["name"]),
            aliases=[str(alias) for alias in partition["aliases"]],
            evidence=evidence,
        )
        character = Character(**payload)
        db.add(character)
        await db.flush()
        update_character_classification(character)
        created_partitions.append(character)
        evidence_by_character_id[character.id] = evidence

    await _reassign_partition_references(
        db,
        source=source,
        partitions=created_partitions,
        evidence_by_character_id=evidence_by_character_id,
    )
    await _dedupe_relationships(db, source.book_id)
    await db.delete(source)
    await db.flush()
    return created_partitions
