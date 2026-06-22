"""Focused book series bible workflows."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Dialogue,
    Scene,
    Series,
    SeriesBook,
)
from app.models.character import (
    Character,
)
from app.models.intelligence import (
    CharacterRelationship,
    PlotThread,
    WikiEntry,
)
from app.schemas.books import (
    SeriesBibleCanonEntryOut,
    SeriesBibleCharacterOut,
    SeriesBibleEpisodeOut,
    SeriesBibleOut,
    SeriesBiblePlotThreadOut,
    SeriesBibleRelationshipOut,
)
from app.utils.plot_thread_utils import (
    is_plot_thread_closed,
)


def _series_bible_key(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()


async def build_series_bible_payload(
    db: AsyncSession,
    *,
    series: Series,
) -> SeriesBibleOut:
    membership_rows = (
        await db.execute(
            select(SeriesBook, Book)
            .join(Book, Book.id == SeriesBook.book_id)
            .where(SeriesBook.series_id == series.id, Book.hidden_at.is_(None))
            .order_by(
                SeriesBook.position.asc().nullslast(), Book.created_at.asc(), Book.title.asc()
            )
        )
    ).all()

    if not membership_rows:
        return SeriesBibleOut(
            series_id=str(series.id),
            name=series.name,
            description=series.description,
            work_type="screenplay",
            episode_count=0,
            episodes=[],
            recurring_characters=[],
            recurring_relationships=[],
            unresolved_plot_threads=[],
            canon_entries=[],
            continuity_risks=[],
        )

    screenplay_rows = [
        (membership, book) for membership, book in membership_rows if book.work_type == "screenplay"
    ]
    active_rows = screenplay_rows or membership_rows
    series_work_type = (
        "screenplay"
        if screenplay_rows
        else (active_rows[0][1].work_type if active_rows else "novel")
    )
    book_ids = [book.id for _, book in active_rows]

    scene_stats_rows = (
        (
            await db.execute(
                select(
                    Scene.book_id,
                    func.count(Scene.id),
                    func.coalesce(func.sum(Scene.word_count), 0),
                )
                .where(Scene.book_id.in_(book_ids))
                .group_by(Scene.book_id)
            )
        ).all()
        if book_ids
        else []
    )
    dialogue_stats_rows = (
        (
            await db.execute(
                select(Scene.book_id, func.count(Dialogue.id))
                .join(Dialogue, Dialogue.scene_id == Scene.id)
                .where(Scene.book_id.in_(book_ids))
                .group_by(Scene.book_id)
            )
        ).all()
        if book_ids
        else []
    )
    scene_stats_by_book = {
        book_id: {"total_scenes": int(total_scenes or 0), "total_words": int(total_words or 0)}
        for book_id, total_scenes, total_words in scene_stats_rows
    }
    dialogue_stats_by_book = {
        book_id: int(total_dialogue or 0) for book_id, total_dialogue in dialogue_stats_rows
    }

    episodes: list[SeriesBibleEpisodeOut] = []
    episode_lookup: dict[uuid.UUID, SeriesBibleEpisodeOut] = {}
    for membership, book in active_rows:
        scene_stats = scene_stats_by_book.get(book.id, {})
        episode = SeriesBibleEpisodeOut(
            book_id=str(book.id),
            title=book.title,
            episode_number=membership.position,
            format=book.format,
            work_type=book.work_type,
            total_scenes=int(scene_stats.get("total_scenes", book.total_chapters or 0) or 0),
            total_dialogue_lines=dialogue_stats_by_book.get(book.id, 0),
            total_words=int(scene_stats.get("total_words", 0) or 0),
            status=book.status,
        )
        episodes.append(episode)
        episode_lookup[book.id] = episode

    characters = (
        (
            await db.execute(
                select(Character)
                .where(Character.book_id.in_(book_ids))
                .order_by(Character.book_id, Character.first_chapter, Character.name)
            )
        )
        .scalars()
        .all()
        if book_ids
        else []
    )
    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id.in_(book_ids))
            )
        )
        .scalars()
        .all()
        if book_ids
        else []
    )
    plot_threads = (
        (
            await db.execute(
                select(PlotThread)
                .where(PlotThread.book_id.in_(book_ids))
                .order_by(PlotThread.importance.desc(), PlotThread.title)
            )
        )
        .scalars()
        .all()
        if book_ids
        else []
    )
    wiki_entries = (
        (
            await db.execute(
                select(WikiEntry)
                .where(WikiEntry.book_id.in_(book_ids))
                .order_by(WikiEntry.entry_type, WikiEntry.name)
            )
        )
        .scalars()
        .all()
        if book_ids
        else []
    )

    character_groups: dict[str, dict[str, Any]] = {}
    for character in characters:
        key = _series_bible_key(character.name)
        if not key:
            continue
        bucket = character_groups.setdefault(
            key,
            {
                "name": character.name,
                "episodes": set(),
                "mentions": 0,
                "first_episode": None,
                "last_episode": None,
            },
        )
        bucket["episodes"].add(character.book_id)
        bucket["mentions"] += int(character.mention_count or 0)
        episode = episode_lookup.get(character.book_id)
        if episode is not None and episode.episode_number is not None:
            if bucket["first_episode"] is None or episode.episode_number < bucket["first_episode"]:
                bucket["first_episode"] = episode.episode_number
            if bucket["last_episode"] is None or episode.episode_number > bucket["last_episode"]:
                bucket["last_episode"] = episode.episode_number

    recurring_characters = sorted(
        (
            SeriesBibleCharacterOut(
                name=bucket["name"],
                normalized_name=key,
                episode_count=len(bucket["episodes"]),
                total_mentions=int(bucket["mentions"]),
                first_episode=bucket["first_episode"],
                last_episode=bucket["last_episode"],
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (
                            episode_lookup[item].episode_number or 10**6,
                            episode_lookup[item].title.lower(),
                        ),
                    )
                ],
            )
            for key, bucket in character_groups.items()
            if len(bucket["episodes"]) >= 2
        ),
        key=lambda item: (-item.episode_count, -item.total_mentions, item.name.lower()),
    )

    relationship_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    continuity_risks: list[str] = []
    pair_type_tracker: dict[tuple[str, str], set[str]] = {}
    name_by_book_and_id = {
        (character.book_id, character.id): character.name for character in characters
    }
    for relationship in relationships:
        a_name = name_by_book_and_id.get(
            (relationship.book_id, relationship.character_a_id), "Unknown"
        )
        b_name = name_by_book_and_id.get(
            (relationship.book_id, relationship.character_b_id), "Unknown"
        )
        pair: tuple[str, str] = (min(a_name, b_name), max(a_name, b_name))
        relationship_type = " ".join(str(relationship.rel_type or "").split()).strip() or "unknown"
        pair_type_tracker.setdefault(pair, set()).add(relationship_type)
        key = (pair[0].lower(), pair[1].lower(), relationship_type)
        bucket = relationship_groups.setdefault(
            key,
            {
                "characters": [pair[0], pair[1]],
                "relationship_type": relationship_type,
                "episodes": set(),
                "note": relationship.description,
            },
        )
        bucket["episodes"].add(relationship.book_id)
        if not bucket.get("note") and relationship.description:
            bucket["note"] = relationship.description

    recurring_relationships = sorted(
        (
            SeriesBibleRelationshipOut(
                characters=bucket["characters"],
                relationship_type=bucket["relationship_type"],
                episode_count=len(bucket["episodes"]),
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (
                            episode_lookup[item].episode_number or 10**6,
                            episode_lookup[item].title.lower(),
                        ),
                    )
                ],
                note=bucket.get("note"),
            )
            for bucket in relationship_groups.values()
            if len(bucket["episodes"]) >= 2
        ),
        key=lambda item: (
            -item.episode_count,
            item.characters[0].lower(),
            item.characters[1].lower(),
            item.relationship_type.lower(),
        ),
    )

    for pair, rel_types in pair_type_tracker.items():
        if len(rel_types) > 1:
            continuity_risks.append(
                f"{pair[0]} and {pair[1]} shift relationship labels across episodes: {', '.join(sorted(rel_types))}."
            )

    plot_thread_groups: dict[str, dict[str, Any]] = {}
    for thread in plot_threads:
        key = _series_bible_key(thread.title)
        if not key:
            continue
        bucket = plot_thread_groups.setdefault(
            key,
            {
                "title": thread.title,
                "episodes": set(),
                "statuses": set(),
                "note": thread.note,
            },
        )
        if not is_plot_thread_closed(thread.status):
            bucket["episodes"].add(thread.book_id)
        bucket["statuses"].add(thread.status)
        if not bucket.get("note") and thread.note:
            bucket["note"] = thread.note

    unresolved_plot_threads = sorted(
        (
            SeriesBiblePlotThreadOut(
                title=bucket["title"],
                status="developing"
                if "developing" in bucket["statuses"] or "ongoing" in bucket["statuses"]
                else sorted(bucket["statuses"])[0],
                episode_count=len(bucket["episodes"]),
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (
                            episode_lookup[item].episode_number or 10**6,
                            episode_lookup[item].title.lower(),
                        ),
                    )
                ],
                note=bucket.get("note"),
            )
            for bucket in plot_thread_groups.values()
            if bucket["episodes"]
        ),
        key=lambda item: (-item.episode_count, item.title.lower()),
    )

    canon_groups: dict[tuple[str, str], dict[str, Any]] = {}
    description_tracker: dict[tuple[str, str], set[str]] = {}
    for entry in wiki_entries:
        key = (entry.entry_type, _series_bible_key(entry.name))
        if not key[1]:
            continue
        bucket = canon_groups.setdefault(
            key,
            {
                "name": entry.name,
                "entry_type": entry.entry_type,
                "episodes": set(),
                "description": entry.description,
            },
        )
        bucket["episodes"].add(entry.book_id)
        if not bucket.get("description") and entry.description:
            bucket["description"] = entry.description
        if entry.description:
            description_tracker.setdefault(key, set()).add(" ".join(entry.description.split()))

    canon_entries = sorted(
        (
            SeriesBibleCanonEntryOut(
                name=bucket["name"],
                entry_type=bucket["entry_type"],
                episode_count=len(bucket["episodes"]),
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (
                            episode_lookup[item].episode_number or 10**6,
                            episode_lookup[item].title.lower(),
                        ),
                    )
                ],
                description=bucket.get("description"),
            )
            for bucket in canon_groups.values()
        ),
        key=lambda item: (-item.episode_count, item.entry_type.lower(), item.name.lower()),
    )

    for key, descriptions in description_tracker.items():
        if len(descriptions) > 1:
            continuity_risks.append(
                f"{canon_groups[key]['name']} has differing {canon_groups[key]['entry_type']} descriptions across episodes."
            )

    role_tracker: dict[str, set[str]] = {}
    for character in characters:
        key = _series_bible_key(character.name)
        if not key or not character.role:
            continue
        role_tracker.setdefault(key, set()).add(character.role)
    for key, roles in role_tracker.items():
        if len(roles) > 1:
            display_name = character_groups.get(key, {}).get("name", key.title())
            continuity_risks.append(
                f"{display_name} shifts role labels across episodes: {', '.join(sorted(roles))}."
            )

    return SeriesBibleOut(
        series_id=str(series.id),
        name=series.name,
        description=series.description,
        work_type=series_work_type,
        episode_count=len(episodes),
        episodes=episodes,
        recurring_characters=recurring_characters[:12],
        recurring_relationships=recurring_relationships[:12],
        unresolved_plot_threads=unresolved_plot_threads[:12],
        canon_entries=canon_entries[:18],
        continuity_risks=list(dict.fromkeys(continuity_risks))[:12],
    )
