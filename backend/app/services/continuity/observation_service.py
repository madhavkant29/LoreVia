from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Chapter, NovelScene
from app.models.character import Character, CharacterMention, CharacterState
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    ContinuityObservation,
    ContinuityScan,
    PlotThread,
    WikiEntry,
)

EXTRACTOR_VERSION = "continuity-ledger-v1"
STRUCTURED_CONTINUITY_PREDICATES = {
    "character.location",
    "character.current_location",
    "character.age",
    "character.injury",
    "character.ability",
    "character.possession",
    "knowledge.acquired",
    "knowledge.used",
    "object.state",
    "object.owner",
    "object.location",
    "object.properties",
    "relationship.type",
    "world.rule",
}


@dataclass(frozen=True)
class ChapterEvidence:
    id: uuid.UUID
    number: int
    content_version: int
    word_count: int
    processed: bool
    chunks: tuple[BookChunk, ...]


def normalize_observation_value(value: object) -> str:
    """Normalize values for deterministic comparisons without changing display text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def trait_value_and_confidence(raw_value: object) -> tuple[object | None, float]:
    if isinstance(raw_value, dict):
        value = raw_value.get("value")
        confidence = raw_value.get("confidence", 0.65)
    else:
        value = raw_value
        confidence = 0.65
    if value is None or not normalize_observation_value(value):
        return None, 0.0
    try:
        normalized_confidence = min(1.0, max(0.0, float(confidence)))
    except (TypeError, ValueError):
        normalized_confidence = 0.65
    return value, normalized_confidence


async def load_chapter_evidence(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_numbers: Iterable[int] | None = None,
) -> list[ChapterEvidence]:
    requested = {int(number) for number in (chapter_numbers or []) if int(number) > 0}
    chapter_query = select(Chapter).where(Chapter.book_id == book_id)
    if requested:
        chapter_query = chapter_query.where(Chapter.number.in_(requested))
    chapters = list((await db.execute(chapter_query.order_by(Chapter.number))).scalars().all())
    if not chapters:
        return []

    chunks = list(
        (
            await db.execute(
                select(BookChunk)
                .where(BookChunk.chapter_id.in_([chapter.id for chapter in chapters]))
                .order_by(BookChunk.chapter_id, BookChunk.chunk_index)
            )
        )
        .scalars()
        .all()
    )
    chunks_by_chapter: dict[uuid.UUID, list[BookChunk]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_chapter[chunk.chapter_id].append(chunk)
    return [
        ChapterEvidence(
            id=chapter.id,
            number=chapter.number,
            content_version=chapter.content_version,
            word_count=int(chapter.word_count or 0),
            processed=bool(chapter.processed),
            chunks=tuple(chunks_by_chapter.get(chapter.id, [])),
        )
        for chapter in chapters
    ]


def chapter_versions(chapters: Iterable[ChapterEvidence]) -> dict[str, int]:
    return {str(chapter.number): chapter.content_version for chapter in chapters}


async def collect_observations(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapters: list[ChapterEvidence],
) -> list[ContinuityObservation]:
    if not chapters:
        return []
    chapter_by_number = {chapter.number: chapter for chapter in chapters}
    chapter_numbers = set(chapter_by_number)

    characters = list(
        (
            await db.execute(
                select(Character).where(
                    Character.book_id == scan.book_id,
                    Character.merged_into_character_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    characters_by_id = {character.id: character for character in characters}
    states = list(
        (
            await db.execute(
                select(CharacterState)
                .join(Character, Character.id == CharacterState.character_id)
                .where(
                    Character.book_id == scan.book_id,
                    CharacterState.at_chapter.in_(chapter_numbers),
                )
                .order_by(CharacterState.character_id, CharacterState.at_chapter)
            )
        )
        .scalars()
        .all()
    )
    mentions = list(
        (
            await db.execute(
                select(CharacterMention)
                .where(
                    CharacterMention.book_id == scan.book_id,
                    CharacterMention.chapter_number.in_(chapter_numbers),
                )
                .order_by(CharacterMention.chapter_number, CharacterMention.created_at)
            )
        )
        .scalars()
        .all()
    )
    mentions_by_character_chapter: dict[tuple[uuid.UUID, int], list[CharacterMention]] = (
        defaultdict(list)
    )
    for mention in mentions:
        if mention.matched_character_id:
            mentions_by_character_chapter[
                (mention.matched_character_id, mention.chapter_number)
            ].append(mention)

    observations: list[ContinuityObservation] = []
    for state in states:
        character = characters_by_id.get(state.character_id)
        chapter = chapter_by_number.get(state.at_chapter)
        if character is None or chapter is None:
            continue
        state_mentions = mentions_by_character_chapter.get((character.id, state.at_chapter), [])
        source_mention = state_mentions[0] if state_mentions else None
        observed_trait_keys = _state_observed_trait_keys(state)
        for trait_name, raw_value in (state.trait_snapshot or {}).items():
            if observed_trait_keys is not None and trait_name not in observed_trait_keys:
                continue
            value, confidence = trait_value_and_confidence(raw_value)
            if value is None:
                continue
            excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                chapter,
                value=value,
                fallback=(
                    source_mention.mention_text
                    if source_mention and source_mention.mention_text
                    else character.name
                ),
            )
            observations.append(
                _observation(
                    scan=scan,
                    chapter=chapter,
                    subject_type="character",
                    subject_id=str(character.id),
                    subject_label=character.name,
                    predicate=f"character.{_normalize_predicate_part(trait_name)}",
                    value=value,
                    confidence=confidence,
                    excerpt=excerpt,
                    source_chunk_id=source_chunk_id,
                    provenance={
                        "source": "character_state",
                        "character_state_id": str(state.id),
                        "citation_quality": citation_quality,
                    },
                )
            )

    for mention in mentions:
        character = characters_by_id.get(mention.matched_character_id)
        chapter = chapter_by_number.get(mention.chapter_number)
        if character is None or chapter is None:
            continue
        excerpt, source_chunk_id, citation_quality = _evidence_for_value(
            chapter,
            value=mention.raw_name,
            fallback=mention.mention_text or mention.raw_name,
        )
        observations.append(
            _observation(
                scan=scan,
                chapter=chapter,
                subject_type="character",
                subject_id=str(character.id),
                subject_label=character.name,
                predicate="identity.alias",
                value=mention.raw_name,
                confidence=_mention_confidence(mention),
                excerpt=excerpt,
                source_chunk_id=source_chunk_id,
                provenance={
                    "source": "character_mention",
                    "mention_id": str(mention.id),
                    "resolver_status": mention.resolver_status,
                    "citation_quality": citation_quality,
                },
            )
        )

    observations.extend(
        await _collect_relationship_observations(
            db,
            scan=scan,
            chapters=chapter_by_number,
            characters=characters_by_id,
        )
    )
    observations.extend(
        await _collect_plot_thread_observations(
            db,
            scan=scan,
            chapters=chapter_by_number,
        )
    )
    observations.extend(
        await _collect_summary_observations(
            db,
            scan=scan,
            chapters=chapter_by_number,
            characters=characters_by_id,
        )
    )
    observations.extend(
        await _collect_world_observations(
            db,
            scan=scan,
            chapters=chapter_by_number,
        )
    )
    observations.extend(
        await _collect_scene_observations(
            db,
            scan=scan,
            chapters=chapter_by_number,
        )
    )
    unique_observations: dict[str, ContinuityObservation] = {}
    for observation in observations:
        unique_observations.setdefault(observation.identity_key, observation)
    for observation in unique_observations.values():
        db.add(observation)
    return list(unique_observations.values())


def _state_observed_trait_keys(state: CharacterState) -> set[str] | None:
    if state.observed_trait_keys is not None:
        return {str(key) for key in state.observed_trait_keys if str(key).strip()}
    delta = str(state.prompt_delta or "").strip()
    if not delta or delta == "minor update":
        return None
    keys: set[str] = set()
    for change in delta.split(";"):
        label = change.split(":", 1)[0].strip().removeprefix("+").strip()
        if label:
            keys.add(label)
    return keys or None


async def _collect_relationship_observations(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapters: dict[int, ChapterEvidence],
    characters: dict[uuid.UUID, Character],
) -> list[ContinuityObservation]:
    relationships = list(
        (
            await db.execute(
                select(CharacterRelationship)
                .where(CharacterRelationship.book_id == scan.book_id)
                .order_by(CharacterRelationship.from_chapter)
            )
        )
        .scalars()
        .all()
    )
    observations: list[ContinuityObservation] = []
    for relationship in relationships:
        chapter = chapters.get(relationship.from_chapter)
        character_a = characters.get(relationship.character_a_id)
        character_b = characters.get(relationship.character_b_id)
        if chapter is None or character_a is None or character_b is None:
            continue
        evidence_payload = relationship.label_evidence or {}
        fallback = _relationship_evidence_excerpt(
            evidence_payload,
            relationship.description,
            relationship.rel_type,
        )
        excerpt, source_chunk_id, citation_quality = _evidence_for_value(
            chapter,
            value=fallback,
            fallback=fallback,
        )
        pair_id = ":".join(
            sorted([str(relationship.character_a_id), str(relationship.character_b_id)])
        )
        observations.append(
            _observation(
                scan=scan,
                chapter=chapter,
                subject_type="relationship",
                subject_id=pair_id,
                subject_label=f"{character_a.name} / {character_b.name}",
                predicate="relationship.type",
                value=relationship.rel_type,
                confidence=0.82 if citation_quality == "exact" else 0.62,
                excerpt=excerpt,
                source_chunk_id=source_chunk_id,
                provenance={
                    "source": "character_relationship",
                    "relationship_id": str(relationship.id),
                    "has_transition_evidence": bool(relationship.description or evidence_payload),
                    "citation_quality": citation_quality,
                },
            )
        )
    return observations


async def _collect_plot_thread_observations(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapters: dict[int, ChapterEvidence],
) -> list[ContinuityObservation]:
    threads = list(
        (
            await db.execute(
                select(PlotThread)
                .where(PlotThread.book_id == scan.book_id)
                .order_by(PlotThread.introduced_at, PlotThread.created_at)
            )
        )
        .scalars()
        .all()
    )
    observations: list[ContinuityObservation] = []
    for thread in threads:
        chapter_events = [
            ("plot.promise_introduced", thread.introduced_at, "introduced"),
            ("plot.last_known", thread.last_mentioned_at, thread.status or "unknown"),
        ]
        if thread.resolved_at:
            chapter_events.append(("plot.payoff", thread.resolved_at, "resolved"))
        seen: set[tuple[str, int]] = set()
        for predicate, chapter_number, value in chapter_events:
            if not chapter_number or chapter_number not in chapters:
                continue
            event_key = (predicate, chapter_number)
            if event_key in seen:
                continue
            seen.add(event_key)
            chapter = chapters[chapter_number]
            excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                chapter,
                value=thread.title,
                fallback=thread.description or thread.title,
            )
            observations.append(
                _observation(
                    scan=scan,
                    chapter=chapter,
                    subject_type="plot_thread",
                    subject_id=str(thread.id),
                    subject_label=thread.title,
                    predicate=predicate,
                    value=value,
                    confidence=0.72 if citation_quality == "exact" else 0.55,
                    excerpt=excerpt,
                    source_chunk_id=source_chunk_id,
                    provenance={
                        "source": "plot_thread",
                        "plot_thread_id": str(thread.id),
                        "thread_type": thread.thread_type,
                        "importance": thread.importance,
                        "citation_quality": citation_quality,
                    },
                )
            )
    return observations


async def _collect_summary_observations(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapters: dict[int, ChapterEvidence],
    characters: dict[uuid.UUID, Character],
) -> list[ContinuityObservation]:
    summaries = list(
        (
            await db.execute(
                select(ChapterSummary)
                .join(Chapter, Chapter.id == ChapterSummary.chapter_id)
                .where(
                    Chapter.book_id == scan.book_id,
                    Chapter.number.in_(chapters),
                    ChapterSummary.mode == "detailed",
                )
                .order_by(Chapter.number, ChapterSummary.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    chapter_number_by_id = {
        chapter.id: chapter.number
        for chapter in (
            (
                await db.execute(
                    select(Chapter).where(
                        Chapter.book_id == scan.book_id,
                        Chapter.number.in_(chapters),
                    )
                )
            )
            .scalars()
            .all()
        )
    }
    character_by_name: dict[str, Character] = {}
    for character in characters.values():
        for name in [character.name, *(character.aliases or [])]:
            normalized_name = normalize_observation_value(name)
            if normalized_name:
                character_by_name.setdefault(normalized_name, character)
    observations: list[ContinuityObservation] = []
    seen_chapters: set[int] = set()
    for summary in summaries:
        chapter_number = chapter_number_by_id.get(summary.chapter_id)
        chapter = chapters.get(chapter_number) if chapter_number is not None else None
        if chapter is None or chapter.number in seen_chapters:
            continue
        seen_chapters.add(chapter.number)
        for index, event in enumerate(summary.key_events or []):
            if not isinstance(event, dict):
                continue
            title = str(event.get("event_title") or event.get("event") or "").strip()
            description = str(event.get("description") or event.get("impact") or title).strip()
            if not title:
                continue
            excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                chapter,
                value=description,
                fallback=description,
            )
            observations.append(
                _observation(
                    scan=scan,
                    chapter=chapter,
                    subject_type="timeline_event",
                    subject_id=f"{summary.id}:{index}",
                    subject_label=title,
                    predicate="timeline.event",
                    value=description,
                    confidence=0.76 if citation_quality == "exact" else 0.58,
                    excerpt=excerpt,
                    source_chunk_id=source_chunk_id,
                    provenance={
                        "source": "chapter_summary",
                        "chapter_summary_id": str(summary.id),
                        "event_type": event.get("event_type"),
                        "involved_characters": event.get("involved_characters") or [],
                        "citation_quality": citation_quality,
                    },
                )
            )
            for fact_index, fact in enumerate(event.get("continuity_facts") or []):
                if not isinstance(fact, dict):
                    continue
                structured = _structured_continuity_fact(
                    fact,
                    characters=character_by_name,
                )
                if structured is None:
                    continue
                evidence = str(fact.get("evidence") or "").strip()
                excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                    chapter,
                    value=evidence,
                    fallback=evidence,
                )
                observations.append(
                    _observation(
                        scan=scan,
                        chapter=chapter,
                        subject_type=structured["subject_type"],
                        subject_id=structured["subject_id"],
                        subject_label=structured["subject_label"],
                        predicate=structured["predicate"],
                        value=structured["value"],
                        confidence=0.86 if citation_quality == "exact" else 0.55,
                        excerpt=excerpt,
                        source_chunk_id=source_chunk_id,
                        provenance={
                            "source": "chapter_summary_continuity_fact",
                            "chapter_summary_id": str(summary.id),
                            "event_index": index,
                            "fact_index": fact_index,
                            "fact_key": structured["fact_key"],
                            "has_transition_evidence": bool(fact.get("has_transition_evidence")),
                            "perspective": str(fact.get("perspective") or "").strip() or None,
                            "unreliable_narration": bool(fact.get("unreliable_narration")),
                            "citation_quality": citation_quality,
                        },
                    )
                )
        for index, clue in enumerate(summary.clues or []):
            if not isinstance(clue, dict):
                continue
            clue_text = str(clue.get("clue") or "").strip()
            if not clue_text:
                continue
            excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                chapter,
                value=clue_text,
                fallback=str(clue.get("why_it_matters") or clue_text),
            )
            observations.append(
                _observation(
                    scan=scan,
                    chapter=chapter,
                    subject_type="plot_clue",
                    subject_id=f"{summary.id}:{index}",
                    subject_label=clue_text,
                    predicate="plot.clue",
                    value=clue.get("foreshadows") or clue_text,
                    confidence=0.74 if citation_quality == "exact" else 0.55,
                    excerpt=excerpt,
                    source_chunk_id=source_chunk_id,
                    provenance={
                        "source": "chapter_summary",
                        "chapter_summary_id": str(summary.id),
                        "citation_quality": citation_quality,
                    },
                )
            )
        for index, change in enumerate(summary.char_changes or []):
            if not isinstance(change, dict):
                continue
            change_text = str(change.get("change") or change.get("description") or "").strip()
            character_name = normalize_observation_value(change.get("character"))
            character = character_by_name.get(character_name)
            if (
                character is None
                or not change_text
                or not re.search(
                    r"\b(learns?|discovers?|realizes?|is told|finds? out|understands?)\b",
                    change_text,
                    flags=re.IGNORECASE,
                )
            ):
                continue
            evidence = str(change.get("evidence") or change_text).strip()
            excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                chapter,
                value=evidence,
                fallback=evidence,
            )
            observations.append(
                _observation(
                    scan=scan,
                    chapter=chapter,
                    subject_type="character",
                    subject_id=str(character.id),
                    subject_label=character.name,
                    predicate="knowledge.acquired",
                    value=change_text,
                    confidence=0.7 if citation_quality == "exact" else 0.52,
                    excerpt=excerpt,
                    source_chunk_id=source_chunk_id,
                    provenance={
                        "source": "chapter_summary",
                        "chapter_summary_id": str(summary.id),
                        "change_index": index,
                        "citation_quality": citation_quality,
                    },
                )
            )
    return observations


def _structured_continuity_fact(
    fact: dict[str, Any],
    *,
    characters: dict[str, Character],
) -> dict[str, str] | None:
    predicate = normalize_observation_value(fact.get("predicate")).replace(" ", "_")
    if predicate not in STRUCTURED_CONTINUITY_PREDICATES:
        return None
    subject_label = " ".join(str(fact.get("subject") or "").split()).strip()
    value = " ".join(str(fact.get("value") or "").split()).strip()
    if not subject_label or not value:
        return None

    normalized_subject = normalize_observation_value(subject_label)
    if predicate.startswith("character.") or predicate.startswith("knowledge."):
        character = characters.get(normalized_subject)
        if character is None:
            return None
        subject_type = "character"
        subject_id = str(character.id)
        subject_label = character.name
    elif predicate.startswith("relationship."):
        subject_type = "relationship"
        subject_id = f"relationship:{normalized_subject}"
    elif predicate.startswith("object."):
        subject_type = "object"
        subject_id = f"object:{normalized_subject}"
    else:
        subject_type = "world_rule"
        subject_id = f"world_rule:{normalized_subject}"

    fact_key = " ".join(str(fact.get("fact_key") or "").split()).strip()
    return {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "subject_label": subject_label,
        "predicate": predicate,
        "value": value,
        "fact_key": fact_key or normalize_observation_value(value),
    }


async def _collect_world_observations(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapters: dict[int, ChapterEvidence],
) -> list[ContinuityObservation]:
    entries = list(
        (
            await db.execute(
                select(WikiEntry)
                .where(
                    WikiEntry.book_id == scan.book_id,
                    WikiEntry.first_mention.in_(chapters),
                )
                .order_by(WikiEntry.first_mention, WikiEntry.entry_type, WikiEntry.name)
            )
        )
        .scalars()
        .all()
    )
    observations: list[ContinuityObservation] = []
    for entry in entries:
        chapter = chapters.get(entry.first_mention or 0)
        if chapter is None:
            continue
        entry_type = normalize_observation_value(entry.entry_type)
        subject_type = "object" if entry_type == "item" else "world_element"
        predicate = {
            "item": "object.properties",
            "event": "timeline.event",
            "concept": "world.rule",
            "location": "world.location",
            "faction": "world.faction",
        }.get(entry_type, "world.description")
        value = entry.description or entry.name
        excerpt, source_chunk_id, citation_quality = _evidence_for_value(
            chapter,
            value=entry.name,
            fallback=value,
        )
        observations.append(
            _observation(
                scan=scan,
                chapter=chapter,
                subject_type=subject_type,
                subject_id=str(entry.id),
                subject_label=entry.name,
                predicate=predicate,
                value=value,
                confidence=0.72 if citation_quality == "exact" else 0.54,
                excerpt=excerpt,
                source_chunk_id=source_chunk_id,
                provenance={
                    "source": "wiki_entry",
                    "wiki_entry_id": str(entry.id),
                    "entry_type": entry.entry_type,
                    "citation_quality": citation_quality,
                },
            )
        )
    return observations


async def _collect_scene_observations(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapters: dict[int, ChapterEvidence],
) -> list[ContinuityObservation]:
    scenes = list(
        (
            await db.execute(
                select(NovelScene)
                .where(
                    NovelScene.book_id == scan.book_id,
                    NovelScene.chapter_number.in_(chapters),
                )
                .order_by(NovelScene.chapter_number, NovelScene.sort_order)
            )
        )
        .scalars()
        .all()
    )
    observations: list[ContinuityObservation] = []
    for scene in scenes:
        chapter = chapters.get(scene.chapter_number or 0)
        if chapter is None:
            continue
        metadata = scene.scene_metadata or {}
        location = metadata.get("location") or metadata.get("setting")
        time_marker = (
            metadata.get("time") or metadata.get("time_of_day") or metadata.get("timeline")
        )
        for predicate, value in (
            ("scene.location", location),
            ("timeline.scene_time", time_marker),
        ):
            if not str(value or "").strip():
                continue
            excerpt, source_chunk_id, citation_quality = _evidence_for_value(
                chapter,
                value=value,
                fallback=scene.description or scene.body[:600],
            )
            observations.append(
                _observation(
                    scan=scan,
                    chapter=chapter,
                    subject_type="scene",
                    subject_id=str(scene.id),
                    subject_label=scene.title,
                    predicate=predicate,
                    value=value,
                    confidence=0.8 if citation_quality == "exact" else 0.6,
                    excerpt=excerpt,
                    source_chunk_id=source_chunk_id,
                    provenance={
                        "source": "novel_scene",
                        "scene_id": str(scene.id),
                        "sort_order": scene.sort_order,
                        "citation_quality": citation_quality,
                    },
                )
            )
    return observations


def _observation(
    *,
    scan: ContinuityScan,
    chapter: ChapterEvidence,
    subject_type: str,
    subject_id: str | None,
    subject_label: str,
    predicate: str,
    value: object,
    confidence: float,
    excerpt: str,
    source_chunk_id: uuid.UUID | None,
    provenance: dict[str, Any],
) -> ContinuityObservation:
    display_value = re.sub(r"\s+", " ", str(value)).strip()
    normalized_value = normalize_observation_value(value)
    identity_source = "|".join(
        [
            str(scan.id),
            str(chapter.number),
            str(chapter.content_version),
            subject_type,
            subject_id or subject_label.casefold(),
            predicate,
            normalized_value,
            hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        ]
    )
    return ContinuityObservation(
        identity_key=hashlib.sha256(identity_source.encode("utf-8")).hexdigest(),
        scan_id=scan.id,
        book_id=scan.book_id,
        chapter_id=chapter.id,
        source_chunk_id=source_chunk_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_label=subject_label,
        predicate=predicate,
        normalized_value=normalized_value,
        display_value=display_value,
        value_json={"value": value},
        chapter_number=chapter.number,
        content_version=chapter.content_version,
        evidence_excerpt=excerpt,
        confidence=confidence,
        extractor_version=EXTRACTOR_VERSION,
        provenance=provenance,
    )


def _evidence_for_value(
    chapter: ChapterEvidence,
    *,
    value: object,
    fallback: str,
) -> tuple[str, uuid.UUID | None, str]:
    for chunk in chapter.chunks:
        excerpt = _exact_excerpt_around(chunk.text, str(value))
        if excerpt is not None:
            return excerpt, chunk.id, "exact"
    if chapter.chunks:
        fallback_text = re.sub(r"\s+", " ", str(fallback or "")).strip()
        excerpt = fallback_text or re.sub(r"\s+", " ", chapter.chunks[0].text).strip()[:320]
        return excerpt[:600], chapter.chunks[0].id, "approximate"
    fallback_text = re.sub(r"\s+", " ", str(fallback or "")).strip()
    return (fallback_text or str(value))[:600], None, "derived"


def _excerpt_around(text: str, value: str, *, radius: int = 220) -> str:
    exact = _exact_excerpt_around(text, value, radius=radius)
    if exact is not None:
        return exact
    return re.sub(r"\s+", " ", str(text or "")).strip()[: radius * 2]


def _exact_excerpt_around(text: str, value: str, *, radius: int = 220) -> str | None:
    normalized_text = str(text or "")
    value_parts = [part for part in re.split(r"\s+", str(value or "").strip()) if part]
    if not value_parts:
        return None
    match = re.search(
        r"\s+".join(re.escape(part) for part in value_parts),
        normalized_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    start = max(0, match.start() - radius)
    end = min(len(normalized_text), match.end() + radius)
    return re.sub(r"\s+", " ", normalized_text[start:end]).strip()


def _normalize_predicate_part(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold())
    return normalized.strip("_") or "unknown"


def _mention_confidence(mention: CharacterMention) -> float:
    evidence = mention.evidence or {}
    raw_confidence = evidence.get("confidence", 0.75)
    try:
        confidence = float(raw_confidence)
        if confidence > 1:
            confidence /= 100
    except (TypeError, ValueError):
        confidence = 0.75
    if mention.resolver_status in {"needs_review", "unresolved"}:
        confidence = min(confidence, 0.49)
    return min(1.0, max(0.0, confidence))


def _relationship_evidence_excerpt(
    evidence: dict[str, Any],
    description: str | None,
    fallback: str,
) -> str:
    for value in evidence.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
        if isinstance(value, list):
            for nested in value:
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
                if isinstance(nested, dict):
                    quote = nested.get("quote") or nested.get("excerpt")
                    if isinstance(quote, str) and quote.strip():
                        return quote.strip()
    return str(description or fallback).strip()
