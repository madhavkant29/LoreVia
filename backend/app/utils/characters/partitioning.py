"""Focused character partitioning workflows."""

from __future__ import annotations

import uuid
from typing import Any

from openai import OpenAIError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.engine.character.extractor import extract_characters_and_relationships
from app.engine.character.profile_builder import (
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
from app.parsers.chunker import count_tokens
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
from app.utils.characters.partition_evidence import collect_partition_evidence
from app.utils.characters.profile_evidence import (
    PROFILE_LIST_FIELDS,
    PROFILE_SCALAR_FIELDS,
    merge_grounded_profile_claims,
    profile_claim_records,
)
from app.utils.characters.text import (
    clean_optional_text,
    clean_string_list,
    split_text_for_token_budget,
)

PARTITION_ENRICHMENT_EXCEPTIONS = (
    OpenAIError,
    TimeoutError,
    RuntimeError,
    TypeError,
    ValueError,
)


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
        if not merged["role"]:
            merged["role"] = entity.get("role")
        growth_event = entity.get("growth_event")
        merged_growth_events = merge_growth_events(
            merged_growth_events, [growth_event] if isinstance(growth_event, dict) else []
        )

    grounded, _ = merge_grounded_profile_claims(entities, merged_traits)
    merged["traits"] = grounded["traits"]
    merged["aliases"] = [
        alias
        for alias in merged_aliases
        if normalize_character_name(alias) != normalize_character_name(name)
    ]
    for field in PROFILE_SCALAR_FIELDS:
        merged[field] = grounded[field]
    for field in PROFILE_LIST_FIELDS:
        merged[field] = grounded[field]
    merged["growth_events"] = [
        event
        for event in merged_growth_events
        if any(
            item.get("growth_event") == event
            and isinstance(item.get("evidence"), dict)
            and isinstance(item["evidence"].get("profile_claims"), dict)
            and isinstance(item["evidence"]["profile_claims"].get("growth_event"), dict)
            and item["evidence"]["profile_claims"]["growth_event"].get("quote")
            for item in entities
        )
    ]
    profile_records: list[dict[str, Any]] = []
    seen_records: set[tuple[str, str, str, int]] = set()
    for item in entities:
        chapter = item.get("_chapter_number")
        if not isinstance(chapter, int) or isinstance(chapter, bool) or chapter < 1:
            continue
        for record in profile_claim_records(item, chapter_number=chapter):
            field, value = record["field"], record["value"]
            if field.startswith("trait:"):
                trait = merged["traits"].get(field.removeprefix("trait:"))
                kept = isinstance(trait, dict) and trait.get("value") == value
            elif field == "growth_event":
                kept = any(event.get("event") == value for event in merged["growth_events"])
            elif field in PROFILE_LIST_FIELDS:
                kept = value in merged[field]
            else:
                kept = merged.get(field) == value
            key = (field, value, record["quote"], chapter)
            if kept and key not in seen_records:
                seen_records.add(key)
                profile_records.append(
                    {
                        "field": field,
                        "value": value,
                        "quote": record["quote"],
                        "chapter_number": chapter,
                    }
                )
    merged["profile_claim_records"] = profile_records
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
            snippet_chapters = evidence.get("snippet_chapters") or []
            for snippet_index, snippet in enumerate(evidence["snippets"]):
                chapter = (
                    snippet_chapters[snippet_index]
                    if snippet_index < len(snippet_chapters)
                    else evidence.get("first_chapter")
                )
                for passage in split_text_for_token_budget(
                    snippet,
                    max_tokens=settings.EXTRACTION_BATCH_MAX_TOKENS,
                    count_tokens=count_tokens,
                ):
                    extracted = await extract_characters_and_relationships(
                        passage,
                        user_id=user_id,
                        book_id=book_id,
                    )
                    entities.extend(
                        {**entity, "_chapter_number": chapter}
                        for entity in extracted.get("characters", [])
                        if isinstance(entity, dict)
                        and _partition_matches_entity(name, aliases, entity)
                    )
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
        "analysis_metadata": {"profile_claims": merged_entity["profile_claim_records"]},
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
        evidence = collect_partition_evidence(
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
