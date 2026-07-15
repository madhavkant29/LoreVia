from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import cast

from app.engine.character.profile_builder import build_description
from app.models.book import Book
from app.models.character import Character
from app.utils.books.normalization import story_unit_label, story_unit_name
from app.utils.characters.governance import character_status
from app.utils.characters.presentation import (
    append_unique_summary,
    dedupe_preserve_order,
    merge_description_with_relationships,
    relationship_summary_for_character,
)
from app.utils.export_common_utils import (
    _clean_line,
    _safe_name,
    append_export_attribution,
    export_font_notice,
)
from app.utils.export_story_utils import (
    _format_growth_event_line,
    _format_story_label,
    _to_int,
)
from app.utils.relationship_utils import normalize_relationship_labels, relationship_label_display

def _vault_note_title(value: object | None) -> str:
    cleaned = _clean_line(value)
    return cleaned or "Untitled"


def _vault_safe_name(value: object | None) -> str:
    cleaned = _vault_note_title(value)
    safe = "".join(ch for ch in cleaned if ch.isalnum() or ch in {" ", "-", "_", "(", ")"}).strip()
    return safe or "Untitled"


def _vault_link(title: str) -> str:
    return f"[[{title}]]"


def _normalize_lookup(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _build_link_targets(characters: list[Character]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for char in characters:
        if not char.name:
            continue
        title = _vault_note_title(char.name)
        targets.setdefault(_normalize_lookup(char.name), title)
        for alias in char.aliases or []:
            alias_key = _normalize_lookup(alias)
            if alias_key:
                targets.setdefault(alias_key, title)
    return targets


def _character_reference_keys(char: Character) -> set[str]:
    keys = {_normalize_lookup(char.name), str(char.id).strip().lower()}
    keys.update(_normalize_lookup(alias) for alias in (char.aliases or []) if _clean_line(alias))
    return {key for key in keys if key}


def _find_character_reference(
    value: object,
    characters: list[Character],
    *,
    keys_by_character: dict[str, set[str]] | None = None,
) -> Character | None:
    normalized = _normalize_lookup(value)
    if not normalized:
        return None
    for char in characters:
        keys = (
            keys_by_character.get(str(char.id), set())
            if keys_by_character
            else _character_reference_keys(char)
        )
        if normalized in keys:
            return char
    return None


def _character_names_from_values(
    values: Iterable[object] | None,
    characters: list[Character],
    *,
    keys_by_character: dict[str, set[str]] | None = None,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        match = _find_character_reference(value, characters, keys_by_character=keys_by_character)
        if match is not None and match.name and match.name not in seen:
            seen.add(match.name)
            names.append(match.name)
    return names


def _major_event_path(root_folder: str, title: str) -> str:
    return f"{root_folder}/Major Events/{_vault_safe_name(title)}.md"


def _plot_thread_path(root_folder: str, title: str) -> str:
    return f"{root_folder}/Plot Threads/{_vault_safe_name(title)}.md"


def _dedupe_vault_path(path: str, used_paths: set[str]) -> str:
    if path not in used_paths:
        used_paths.add(path)
        return path

    stem, dot, extension = path.rpartition(".")
    base = stem if dot else path
    suffix = f".{extension}" if dot else ""
    counter = 2
    candidate = f"{base} ({counter}){suffix}"
    while candidate in used_paths:
        counter += 1
        candidate = f"{base} ({counter}){suffix}"
    used_paths.add(candidate)
    return candidate


def _linkify_text(value: str | None, targets: dict[str, str], *, skip: str | None = None) -> str:
    text = _clean_line(value)
    if not text or not targets:
        return text

    skip_key = _normalize_lookup(skip) if skip else None
    sorted_targets = sorted(targets.items(), key=lambda item: len(item[0]), reverse=True)

    for target_key, target_title in sorted_targets:
        if skip_key and target_key == skip_key:
            continue
        pattern = re.compile(rf"(?<!\w)({re.escape(target_key)})(?!\w)", re.IGNORECASE)

        def _replace(match: re.Match[str]) -> str:
            matched = match.group(0)
            if _normalize_lookup(matched) == _normalize_lookup(target_title):
                return f"[[{matched}]]"
            return f"[[{target_title}|{matched}]]"

        text = pattern.sub(_replace, text)
    return text


def _linkify_collection(
    values: list[str], targets: dict[str, str], *, skip: str | None = None
) -> list[str]:
    return [_linkify_text(value, targets, skip=skip) for value in values if _clean_line(value)]


def _parse_event_title(event: object, chapter_number: int, index: int) -> str:
    if isinstance(event, dict):
        for key in ("event_title", "title", "event", "name"):
            title = _clean_line(event.get(key))
            if title:
                return title
    if isinstance(event, str):
        title = _clean_line(event)
        if title:
            return title
    return f"Chapter {chapter_number} Event {index}"


def _parse_event_description(event: object) -> str:
    if isinstance(event, dict):
        for key in ("description", "impact", "note", "details", "summary"):
            description = _clean_line(event.get(key))
            if description:
                return description
    if isinstance(event, str):
        return _clean_line(event)
    return ""


def _parse_event_importance(event: object) -> int | None:
    if isinstance(event, dict):
        for key in ("importance", "impact_score", "impact"):
            raw = event.get(key)
            if isinstance(raw, (int, float)):
                return int(raw)
            if isinstance(raw, str) and raw.strip().isdigit():
                return int(raw.strip())
    return None


def _extract_related_character_names(
    value: object,
    characters_by_id: dict[str, str],
    targets: dict[str, str],
) -> list[str]:
    linked: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                cleaned = _clean_line(item)
                if not cleaned:
                    continue
                linked.append(_linkify_text(characters_by_id.get(cleaned, cleaned), targets))
                continue
            if isinstance(item, dict):
                for key in ("name", "character_name", "title"):
                    raw = item.get(key)
                    if isinstance(raw, str) and raw.strip():
                        linked.append(_linkify_text(raw, targets))
                        break
                continue
            if item is not None:
                raw = str(item).strip()
                if raw:
                    linked.append(_linkify_text(characters_by_id.get(raw, raw), targets))
    elif isinstance(value, dict):
        for raw in value.values():
            linked.extend(_extract_related_character_names(raw, characters_by_id, targets))
    return list(dict.fromkeys(linked))


def _obj_value(obj: object, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _build_vault_manifest(
    *,
    book: Book,
    characters: list[Character],
    relationships: list[object],
    plot_threads: list[object],
    wiki_entries: list[object],
    chapter_rows: list[dict],
    chapter_events: list[dict],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
) -> tuple[str, list[dict[str, str]]]:
    safe_book_title = _safe_name(book.title) or "LoreVia"
    root_folder = f"LoreVia Export - {safe_book_title}"
    link_targets = _build_link_targets(characters)
    characters_by_id = {str(char.id): char.name for char in characters if char.name}

    def relink(text: str | None, *, skip: str | None = None) -> str:
        return _linkify_text(text, link_targets, skip=skip)

    def add_file(path: str, content: str) -> None:
        files.append(
            {
                "path": _dedupe_vault_path(path, used_paths),
                "content": append_export_attribution(content),
            }
        )

    files: list[dict[str, str]] = []
    used_paths: set[str] = set()
    character_keys = {str(char.id): _character_reference_keys(char) for char in characters}
    chapter_lookup = {
        int(row["number"]): row for row in chapter_rows if row.get("number") is not None
    }

    for char in characters:
        char_name = _vault_note_title(char.name)
        relationship_lines = dedupe_preserve_order(rel_summaries.get(str(char.id), []))
        description = _clean_line(build_description(char.trait_state or {}, char.archetype))
        if relationship_lines:
            description = merge_description_with_relationships(description, relationship_lines)
        description = relink(description, skip=char.name)
        tags = [
            relink(item, skip=char.name)
            for item in (char.personality_tags or [])
            if _clean_line(item)
        ]
        motivations = [
            relink(item, skip=char.name) for item in (char.motivations or []) if _clean_line(item)
        ]
        fears = [relink(item, skip=char.name) for item in (char.fears or []) if _clean_line(item)]
        linked_relationships = [relink(item, skip=char.name) for item in relationship_lines]
        thread_lines = dedupe_preserve_order(thread_summaries.get(str(char.id), []))
        linked_threads = [relink(item, skip=char.name) for item in thread_lines]

        growth_events = char.growth_events or []
        event_lines: list[str] = []
        for index, event in enumerate(growth_events, start=1):
            if not isinstance(event, dict):
                continue
            raw_line = _format_growth_event_line(event, book) or _parse_event_title(
                event, char.first_chapter, index
            )
            event_lines.append(f"- {relink(raw_line, skip=char.name)}")

        continuity_watch: list[str] = []
        if (
            char.last_seen_chapter
            and book.total_chapters
            and book.total_chapters - char.last_seen_chapter >= 25
        ):
            continuity_watch.append(
                f"Absent for {book.total_chapters - char.last_seen_chapter} chapters."
            )

        char_lines = [
            f"# {char_name}",
            "",
            f"- Status: {character_status(char)}",
            f"- First appearance: {_format_story_label(book, char.first_chapter)}",
            f"- Last appearance: {_format_story_label(book, char.last_seen_chapter)}",
            f"- Mentions tracked: {char.mention_count or 0}",
            f"- Aliases: {', '.join(char.aliases or [])}"
            if (char.aliases or [])
            else "- Aliases: -",
            "",
            f"Short description: {description or 'LoreVia is still building this profile.'}",
            "",
        ]
        if tags:
            char_lines.extend(["## Personality", "", *[f"- {item}" for item in tags], ""])
        if motivations:
            char_lines.extend(["## Motivations", "", *[f"- {item}" for item in motivations], ""])
        if fears:
            char_lines.extend(["## Fears", "", *[f"- {item}" for item in fears], ""])
        if _clean_line(char.arc_summary):
            char_lines.extend(["## Arc Summary", "", relink(char.arc_summary, skip=char.name), ""])
        if event_lines:
            char_lines.extend(["## Character Major Events", "", *event_lines, ""])
        if linked_relationships:
            char_lines.extend(
                ["## Relationships", "", *[f"- {item}" for item in linked_relationships], ""]
            )
        if linked_threads:
            char_lines.extend(
                ["## Plot Thread Involvement", "", *[f"- {item}" for item in linked_threads], ""]
            )
        if continuity_watch:
            char_lines.extend(
                ["## Continuity Watch", "", *[f"- {item}" for item in continuity_watch], ""]
            )

        add_file(
            f"{root_folder}/Characters/{_vault_safe_name(char_name)}.md", "\n".join(char_lines)
        )

    relationship_index_lines = [
        "# Relationship Map",
        "",
        f"| Character A | Character B | Type | {story_unit_name(book, plural=True)} | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for rel in relationships:
        a_name = _vault_note_title(
            _obj_value(rel, "character_a_name")
            or characters_by_id.get(str(_obj_value(rel, "character_a_id") or ""), "Unknown")
        )
        b_name = _vault_note_title(
            _obj_value(rel, "character_b_name")
            or characters_by_id.get(str(_obj_value(rel, "character_b_id") or ""), "Unknown")
        )
        labels = (
            normalize_relationship_labels(_obj_value(rel, "character_a_to_b_labels"))
            + normalize_relationship_labels(_obj_value(rel, "character_b_to_a_labels"))
            + normalize_relationship_labels(_obj_value(rel, "shared_labels"))
        )
        rel_type = (
            ", ".join(relationship_label_display(label) for label in labels[:5])
            or _clean_line(str(_obj_value(rel, "rel_type") or "neutral")).replace("_", " ")
        ).title()
        chapter_range = (
            f"{_format_story_label(book, _to_int(_obj_value(rel, 'from_chapter') or 0) or None)}"
        )
        if _obj_value(rel, "to_chapter"):
            chapter_range += f" to {_format_story_label(book, _to_int(_obj_value(rel, 'to_chapter') or 0) or None)}"
        else:
            chapter_range += " onward"
        note = relink(_clean_line(str(_obj_value(rel, "description") or "")), skip=a_name)
        relationship_index_lines.append(
            f"| [[{a_name}]] | [[{b_name}]] | {rel_type} | {chapter_range} | {note or '-'} |"
        )
    add_file(
        f"{root_folder}/Relationships/Relationship Map.md",
        "\n".join(relationship_index_lines + [""]),
    )

    sorted_threads = sorted(
        plot_threads,
        key=lambda thread: (
            _obj_value(thread, "introduced_at")
            if _obj_value(thread, "introduced_at") is not None
            else 10**9,
            -_to_int(_obj_value(thread, "importance") or 0),
            _clean_line(str(_obj_value(thread, "title") or "")).lower(),
        ),
    )
    for thread in sorted_threads:
        title = _vault_note_title(_obj_value(thread, "title"))
        notes = relink(cast(str | None, _obj_value(thread, "note")), skip=title)
        description = relink(cast(str | None, _obj_value(thread, "description")), skip=title)
        related_names = _character_names_from_values(
            _obj_value(thread, "character_ids") or [], characters, keys_by_character=character_keys
        )
        linked_chars = [relink(name, skip=title) for name in related_names]
        intro = _format_story_label(
            book, _to_int(_obj_value(thread, "introduced_at") or 0) or None, "Unknown start"
        )
        resolved = cast(int | None, _obj_value(thread, "resolved_at"))
        connected_events: list[str] = []
        connected_event_keys: set[str] = set()
        thread_start = _to_int(_obj_value(thread, "introduced_at") or 0)
        thread_end = _to_int(resolved or 0)
        for event in chapter_events:
            event_title = _vault_note_title(event["title"])
            event_chapter = int(event.get("chapter_number") or 0)
            involved_names = _character_names_from_values(
                event.get("involved_characters"), characters, keys_by_character=character_keys
            )
            overlaps_characters = bool(set(involved_names) & set(related_names))
            within_range = event_chapter >= thread_start if thread_start else True
            if thread_end:
                within_range = within_range and event_chapter <= thread_end
            if not overlaps_characters and not within_range:
                continue
            if event_title.lower() in connected_event_keys:
                continue
            connected_event_keys.add(event_title.lower())
            connected_events.append(event_title)

        lines = [
            f"# {title}",
            "",
            f"- Status: {_obj_value(thread, 'status') or 'unknown'}",
            f"- Importance: {_obj_value(thread, 'importance') or 5}/10",
            f"- Introduced: {intro}",
        ]
        if resolved:
            lines.append(f"- Resolved: {_format_story_label(book, resolved)}")
        lines.append("")
        if description:
            lines.extend(["## Thread Overview", "", description, ""])
        if notes:
            lines.extend(["## Author Notes", "", notes, ""])
        if connected_events:
            lines.extend(["## Major Beats", ""])
            for event_title in connected_events[:10]:
                lines.append(f"- [[{event_title}]]")
            lines.append("")
        if linked_chars:
            lines.extend(["## Linked Characters", "", *[f"- {item}" for item in linked_chars], ""])
        if notes:
            lines.extend(
                [
                    "## Arc Pressure",
                    "",
                    "This thread stays active because it keeps redirecting character choices and raising continuity stakes across the manuscript.",
                    "",
                ]
            )
        if connected_events:
            progression_lines = [
                f"- {event_title}: tied to {title.lower()} during {_format_story_label(book, cast(int | None, next((event.get('chapter_number') for event in chapter_events if _vault_note_title(event['title']) == event_title), None)))}."
                for event_title in connected_events[:6]
            ]
            lines.extend(["## Progression", "", *progression_lines, ""])
        add_file(f"{root_folder}/Plot Threads/{_vault_safe_name(title)}.md", "\n".join(lines))

    wiki_groups: dict[str, list[object]] = defaultdict(list)
    for entry in wiki_entries:
        entry_type = _normalize_lookup(str(_obj_value(entry, "entry_type") or "concept"))
        wiki_groups[entry_type].append(entry)

    for entry in wiki_entries:
        entry_type = _normalize_lookup(str(_obj_value(entry, "entry_type") or "concept"))
        folder_name = {
            "location": "Locations",
            "faction": "Factions",
            "item": "Items",
            "event": "Events",
            "concept": "Concepts",
        }.get(entry_type, "Concepts")
        name = _vault_note_title(_obj_value(entry, "name"))
        desc = relink(cast(str | None, _obj_value(entry, "description")))
        related_ids = _obj_value(entry, "related_char_ids")
        related_characters = _extract_related_character_names(
            related_ids, characters_by_id, link_targets
        )
        lines = [
            f"# {name}",
            "",
            f"- Type: {entry_type}",
            f"- First mention: {_format_story_label(book, cast(int | None, _obj_value(entry, 'first_mention')))}",
            "",
        ]
        if desc:
            lines.extend([desc, ""])
        if related_characters:
            lines.extend(
                ["## Related Characters", "", *[f"- {item}" for item in related_characters], ""]
            )
        add_file(f"{root_folder}/Wiki/{folder_name}/{_vault_safe_name(name)}.md", "\n".join(lines))

    sorted_chapters = sorted(chapter_rows, key=lambda row: int(row["number"]))
    events_by_chapter: dict[int, list[dict]] = defaultdict(list)
    for event in chapter_events:
        events_by_chapter[int(event["chapter_number"])].append(event)

    for row in sorted_chapters:
        chapter_number = int(row["number"])
        chapter_title = row.get("title") or story_unit_label(book, chapter_number)
        summary_text = (
            relink(cast(str | None, row.get("content")))
            or f"{story_unit_label(book, chapter_number)} moves the story forward, but LoreVia has not generated a full reading summary for it yet."
        )
        key_events = events_by_chapter.get(chapter_number, [])
        file_label = f"{story_unit_label(book, chapter_number)} - {_vault_safe_name(chapter_title)}"
        lines = [
            f"# {story_unit_label(book, chapter_number)}",
            "",
            f"- Title: {chapter_title}",
            "",
            "## Reading Log",
            "",
        ]
        lines.extend([summary_text, ""])
        if key_events:
            lines.extend(["## Key Events", ""])
            for event in key_events:
                lines.append(f"- [[{event['title']}]]")
            lines.append("")
        add_file(f"{root_folder}/Reading Log/{file_label}.md", "\n".join(lines))

    sorted_events = sorted(
        chapter_events,
        key=lambda item: (
            int(item["chapter_number"]),
            _normalize_lookup(str(item["title"])),
        ),
    )
    for index, event in enumerate(sorted_events):
        title = _vault_note_title(event["title"])
        previous_title = sorted_events[index - 1]["title"] if index > 0 else None
        next_title = sorted_events[index + 1]["title"] if index + 1 < len(sorted_events) else None
        chapter_number = cast(int | None, event["chapter_number"])
        chapter_row = chapter_lookup.get(int(chapter_number or 0), {})
        involved_names = _character_names_from_values(
            event.get("involved_characters"), characters, keys_by_character=character_keys
        )
        involved = [relink(name, skip=title) for name in involved_names]
        related_threads: list[str] = []
        for thread in sorted_threads:
            thread_title = _vault_note_title(_obj_value(thread, "title"))
            thread_names = _character_names_from_values(
                _obj_value(thread, "character_ids") or [],
                characters,
                keys_by_character=character_keys,
            )
            thread_start = _to_int(_obj_value(thread, "introduced_at") or 0)
            thread_end = _to_int(_obj_value(thread, "resolved_at") or 0)
            chapter_match = chapter_number is not None and (
                thread_start == chapter_number or (thread_end and thread_end == chapter_number)
            )
            if set(thread_names) & set(involved_names) or chapter_match:
                related_threads.append(thread_title)
        related_threads = list(dict.fromkeys(related_threads))
        arc_lines = []
        for name in involved_names:
            character = next((item for item in characters if item.name == name), None)
            if character is None:
                continue
            arc_detail = relink(
                character.arc_summary
                or build_description(character.trait_state or {}, character.archetype),
                skip=name,
            )
            if arc_detail:
                arc_lines.append(f"- [[{name}]]: {arc_detail}")
        context_summary = (
            relink(cast(str | None, chapter_row.get("content"))) if chapter_row else ""
        )
        lines = [
            f"# {title}",
            "",
            f"- {story_unit_name(book)}: {_format_story_label(book, chapter_number)}",
            f"- Chapter title: {chapter_row.get('title') or event.get('chapter_title') or '-'}",
        ]
        if event.get("importance") is not None:
            lines.append(f"- Importance: {event['importance']}/10")
        if previous_title or next_title:
            links = []
            if previous_title:
                links.append(f"Previous: [[{previous_title}]]")
            if next_title:
                links.append(f"Next: [[{next_title}]]")
            lines.append(f"- {' | '.join(links)}")
        lines.append("")
        if event.get("description"):
            lines.extend(
                ["## What Happens", "", relink(cast(str | None, event["description"])), ""]
            )
        if context_summary:
            lines.extend(["## Reading Log Context", "", context_summary, ""])
        if related_threads:
            lines.extend(
                [
                    "## Connected Plot Threads",
                    "",
                    *[f"- [[{thread_title}]]" for thread_title in related_threads],
                    "",
                ]
            )
        if arc_lines:
            lines.extend(["## Arc Movement", "", *arc_lines, ""])
        if involved:
            lines.extend(["## Involved Characters", "", *[f"- {item}" for item in involved], ""])
        if related_threads or arc_lines:
            explanation_parts: list[str] = []
            if related_threads:
                explanation_parts.append(
                    f"This moment pushes {', '.join(_vault_link(thread_title) for thread_title in related_threads[:3])} into its next phase."
                )
            if involved_names:
                explanation_parts.append(
                    f"It also changes the pressure around {', '.join(_vault_link(name) for name in involved_names[:3])}."
                )
            lines.extend(["## Why It Matters", "", " ".join(explanation_parts), ""])
        add_file(f"{root_folder}/Major Events/{_vault_safe_name(title)}.md", "\n".join(lines))

    return root_folder, files


async def build_character_bible_vault_context(db, book_id) -> dict:
    from sqlalchemy import select

    from app.engine.character.consolidator import consolidate_characters
    from app.models.book import Chapter
    from app.models.character import Character
    from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread, WikiEntry

    book = await db.get(Book, book_id)
    if book is None:
        return {}

    await consolidate_characters(db, book_id)

    characters_result = await db.execute(
        select(Character)
        .where(Character.book_id == book_id)
        .order_by(Character.first_chapter, Character.name)
    )
    characters = characters_result.scalars().all()

    relationships_result = await db.execute(
        select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
    )
    relationships = relationships_result.scalars().all()
    plot_threads_result = await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))
    plot_threads = plot_threads_result.scalars().all()
    wiki_entries_result = await db.execute(select(WikiEntry).where(WikiEntry.book_id == book_id))
    wiki_entries = wiki_entries_result.scalars().all()
    chapter_rows = (
        await db.execute(
            select(
                Chapter.number,
                Chapter.title,
                Chapter.description,
                ChapterSummary.content,
                ChapterSummary.key_events,
            )
            .outerjoin(
                ChapterSummary,
                (ChapterSummary.chapter_id == Chapter.id) & (ChapterSummary.mode == "short"),
            )
            .where(Chapter.book_id == book_id)
            .order_by(Chapter.number)
        )
    ).all()
    character_keys = {str(char.id): _character_reference_keys(char) for char in characters}

    char_by_id = {char.id: char for char in characters}
    rel_summaries: dict[str, list[str]] = {}
    rel_keys: dict[str, set[str]] = {}
    for rel in relationships:
        a = char_by_id.get(rel.character_a_id)
        b = char_by_id.get(rel.character_b_id)
        if not a or not b:
            continue
        summary_a = relationship_summary_for_character(rel, a.name, b.name, a.name)
        summary_b = relationship_summary_for_character(rel, a.name, b.name, b.name)
        label_signature = ":".join(
            ",".join(str(item) for item in (getattr(rel, field, None) or []))
            for field in ("shared_labels", "character_a_to_b_labels", "character_b_to_a_labels")
        )
        if summary_a:
            append_unique_summary(
                rel_summaries,
                rel_keys,
                str(a.id),
                f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{b.name}".lower(),
                summary_a,
            )
        if summary_b:
            append_unique_summary(
                rel_summaries,
                rel_keys,
                str(b.id),
                f"{rel.rel_type}:{rel.from_chapter}:{rel.to_chapter}:{label_signature}:{a.name}".lower(),
                summary_b,
            )

    thread_summaries: dict[str, list[str]] = {}
    for thread in plot_threads:
        for raw_name in thread.character_ids or []:
            owner = _find_character_reference(
                raw_name, characters, keys_by_character=character_keys
            )
            if owner is None:
                continue
            thread_summaries.setdefault(str(owner.id), []).append(
                f"{thread.title} [{thread.status}]"
                + (f" — note: {thread.note}" if thread.note else "")
            )

    chapter_events: list[dict] = []
    major_event_keys: set[tuple[int, str]] = set()
    for chapter_number, chapter_title, _chapter_description, content, key_events in chapter_rows:
        for index, event in enumerate(key_events or [], start=1):
            if isinstance(event, dict) and _parse_event_title(event, chapter_number, index):
                major_event_keys.add(
                    (
                        int(chapter_number),
                        _normalize_lookup(_parse_event_title(event, chapter_number, index)),
                    )
                )
                chapter_events.append(
                    {
                        "chapter_number": chapter_number,
                        "chapter_title": chapter_title,
                        "title": _parse_event_title(event, chapter_number, index),
                        "description": _parse_event_description(event),
                        "importance": _parse_event_importance(event),
                        "involved_characters": event.get("involved_characters")
                        if isinstance(event, dict)
                        else None,
                    }
                )
            elif isinstance(event, str) and event.strip():
                major_event_keys.add((int(chapter_number), _normalize_lookup(event.strip())))
                chapter_events.append(
                    {
                        "chapter_number": chapter_number,
                        "chapter_title": chapter_title,
                        "title": event.strip(),
                        "description": "",
                        "importance": None,
                        "involved_characters": None,
                    }
                )

    for char in characters:
        for index, raw_event in enumerate(char.growth_events or [], start=1):
            if not isinstance(raw_event, dict):
                continue
            chapter_number = _to_int(
                raw_event.get("chapter_number") or raw_event.get("chapter") or char.first_chapter, 0
            )
            if chapter_number <= 0:
                continue
            importance = _parse_event_importance(raw_event) or _to_int(
                raw_event.get("impact_score") or raw_event.get("growth_magnitude"), 0
            )
            if not (bool(raw_event.get("is_major")) or importance >= 7):
                continue
            title = _parse_event_title(raw_event, chapter_number, index)
            identity = (chapter_number, _normalize_lookup(title))
            if identity in major_event_keys:
                continue
            chapter_meta = next(
                (row for row in chapter_rows if int(row[0]) == chapter_number), None
            )
            major_event_keys.add(identity)
            chapter_events.append(
                {
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_meta[1] if chapter_meta else None,
                    "title": title,
                    "description": _parse_event_description(raw_event),
                    "importance": importance or None,
                    "involved_characters": [str(char.id)],
                }
            )

    return {
        "book": book,
        "characters": characters,
        "relationships": relationships,
        "plot_threads": plot_threads,
        "wiki_entries": wiki_entries,
        "chapter_rows": [
            {
                "number": chapter_number,
                "title": chapter_title,
                "content": content
                or chapter_description
                or (
                    f"{story_unit_label(book, chapter_number)} establishes {chapter_title}."
                    if chapter_title
                    else ""
                ),
            }
            for chapter_number, chapter_title, chapter_description, content, _ in chapter_rows
        ],
        "chapter_events": chapter_events,
        "rel_summaries": rel_summaries,
        "thread_summaries": thread_summaries,
    }


# ─── Character card ──────────────────────────────────────────────────────────


def character_bible_vault_manifest(
    *,
    book: Book,
    characters: list[Character],
    relationships: list[object],
    plot_threads: list[object],
    wiki_entries: list[object],
    chapter_rows: list[dict],
    chapter_events: list[dict],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
) -> tuple[str, list[dict[str, str]]]:
    return _build_vault_manifest(
        book=book,
        characters=characters,
        relationships=relationships,
        plot_threads=plot_threads,
        wiki_entries=wiki_entries,
        chapter_rows=chapter_rows,
        chapter_events=chapter_events,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )


def _apply_vault_overrides(
    files: list[dict[str, str]], overrides: dict[str, str] | None
) -> list[dict[str, str]]:
    if not overrides:
        return files
    return [
        {
            "path": file["path"],
            "content": append_export_attribution(overrides.get(file["path"], file["content"])),
        }
        for file in files
    ]


def character_bible_vault_folder(
    *,
    book: Book,
    characters: list[Character],
    relationships: list[object],
    plot_threads: list[object],
    wiki_entries: list[object],
    chapter_rows: list[dict],
    chapter_events: list[dict],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
    overrides: dict[str, str] | None = None,
    font_family: str | None = None,
) -> tuple[bytes, str]:
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    root_folder, files = character_bible_vault_manifest(
        book=book,
        characters=characters,
        relationships=relationships,
        plot_threads=plot_threads,
        wiki_entries=wiki_entries,
        chapter_rows=chapter_rows,
        chapter_events=chapter_events,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )
    files = _apply_vault_overrides(files, overrides)

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{root_folder}/FONT-NOTICE.txt", export_font_notice(font_family))
        for file in files:
            zipf.writestr(file["path"], file["content"])
    buffer.seek(0)
    return buffer.getvalue(), root_folder.replace("LoreVia Export - ", "")


def character_bible_vault_preview(
    *,
    book: Book,
    characters: list[Character],
    relationships: list[object],
    plot_threads: list[object],
    wiki_entries: list[object],
    chapter_rows: list[dict],
    chapter_events: list[dict],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
    overrides: dict[str, str] | None = None,
) -> dict:
    root_folder, files = character_bible_vault_manifest(
        book=book,
        characters=characters,
        relationships=relationships,
        plot_threads=plot_threads,
        wiki_entries=wiki_entries,
        chapter_rows=chapter_rows,
        chapter_events=chapter_events,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )
    files = _apply_vault_overrides(files, overrides)
    return {
        "root_folder": root_folder,
        "files": files,
    }
