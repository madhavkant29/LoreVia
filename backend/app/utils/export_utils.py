"""
Export utility helpers — character card and character bible renderers
for Markdown, PDF (ReportLab), and DOCX (python-docx) formats.

Extracted from the books route to keep route handlers thin.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, cast

from app.engine.character.profile_builder import build_description
from app.models.book import Book
from app.models.character import Character
from app.utils.book_utils import clean_manuscript_html
from app.utils.character_utils import (
    append_unique_summary,
    character_status,
    dedupe_preserve_order,
    merge_description_with_relationships,
    relationship_summary_for_character,
)


def _clean_line(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_name(value: object | None) -> str:
    cleaned = _clean_line(value)
    return "".join(ch for ch in cleaned if ch.isalnum() or ch in {" ", "-", "_", "(", ")"}).strip().replace(" ", "-")


def _obsidian_note_title(value: object | None) -> str:
    cleaned = _clean_line(value)
    return cleaned or "Untitled"


def _obsidian_link(title: str) -> str:
    return f"[[{title}]]"


def _normalize_lookup(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def _to_int(value: object | None, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
        return default
    except (TypeError, ValueError):
        return default


def _build_link_targets(characters: list[Character]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for char in characters:
        if not char.name:
            continue
        title = _obsidian_note_title(char.name)
        targets.setdefault(_normalize_lookup(char.name), title)
        for alias in char.aliases or []:
            alias_key = _normalize_lookup(alias)
            if alias_key:
                targets.setdefault(alias_key, title)
    return targets


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


def _linkify_collection(values: list[str], targets: dict[str, str], *, skip: str | None = None) -> list[str]:
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


def _format_chapter_label(chapter_number: int | None, fallback: str = "-") -> str:
    return f"Chapter {chapter_number}" if chapter_number else fallback


def _format_growth_event_line(event: dict) -> str:
    chapter_number = _to_int(event.get("chapter_number") or event.get("chapter"), 0)
    chapter_label = f"Chapter {chapter_number}: " if chapter_number else ""
    title = _clean_line(str(event.get("event_title") or event.get("event") or ""))
    description = _clean_line(str(event.get("description") or event.get("impact") or ""))
    impact_score = event.get("impact_score") or event.get("importance")
    growth_direction = _clean_line(str(event.get("growth_direction") or ""))
    accomplishments = [str(item).strip() for item in (event.get("accomplishments") or []) if str(item).strip()]
    suffix: list[str] = []
    if impact_score not in (None, ""):
        suffix.append(f"impact {impact_score}/10")
    if growth_direction:
        suffix.append(growth_direction)
    if accomplishments:
        suffix.append("accomplishments: " + ", ".join(accomplishments[:3]))
    detail = description or ""
    if suffix:
        detail = (detail + " " if detail else "") + f"({' | '.join(suffix)})"
    return f"{chapter_label}{title}{(': ' + detail) if detail else ''}".strip()


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
                linked.append(_linkify_text(cleaned, targets))
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


def _build_obsidian_manifest(
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

    files: list[dict[str, str]] = []

    index_lines = [
        f"# {book.title or 'LoreVia'} - Obsidian Export",
        "",
        f"- Source: {book.title or 'Untitled'}",
        f"- Format: {book.format.upper()}",
        f"- Characters: {len(characters)}",
        f"- Plot threads: {len(thread_summaries)}",
        f"- Wiki entries: {len(wiki_entries)}",
        f"- Reading log chapters: {len(chapter_rows)}",
        f"- Major events: {len(chapter_events)}",
        "",
        "## Sections",
        "",
        "- [[Characters/Index|Characters]]",
        "- [[Relationships/Relationship Map|Relationships]]",
        "- [[Plot Threads/Index|Plot Threads]]",
        "- [[Wiki/Index|Wiki]]",
        "- [[Reading Log/Index|Reading Log]]",
        "- [[Story Major Events/Index|Story Major Events]]",
        "",
    ]
    files.append({
        "path": f"{root_folder}/000 - Index.md",
        "content": "\n".join(index_lines),
    })

    character_notes: list[tuple[str, str]] = []
    for char in characters:
        char_name = _obsidian_note_title(char.name)
        character_notes.append((char_name, str(char.id)))
    character_notes.sort(key=lambda item: item[0].lower())

    character_index_lines = [
        "# Characters",
        "",
        *[f"- [[Characters/{name}|{name}]]" for name, _ in character_notes],
        "",
    ]
    files.append({
        "path": f"{root_folder}/Characters/Index.md",
        "content": "\n".join(character_index_lines),
    })

    for char in characters:
        char_name = _obsidian_note_title(char.name)
        relationship_lines = dedupe_preserve_order(rel_summaries.get(str(char.id), []))
        description = _clean_line(build_description(char.trait_state or {}, char.archetype))
        if relationship_lines:
            description = merge_description_with_relationships(description, relationship_lines)
        description = relink(description, skip=char.name)
        tags = [relink(item, skip=char.name) for item in (char.personality_tags or []) if _clean_line(item)]
        motivations = [relink(item, skip=char.name) for item in (char.motivations or []) if _clean_line(item)]
        fears = [relink(item, skip=char.name) for item in (char.fears or []) if _clean_line(item)]
        linked_relationships = [relink(item, skip=char.name) for item in relationship_lines]
        thread_lines = dedupe_preserve_order(thread_summaries.get(str(char.id), []))
        linked_threads = [relink(item, skip=char.name) for item in thread_lines]

        growth_events = char.growth_events or []
        event_lines: list[str] = []
        for index, event in enumerate(growth_events, start=1):
            if not isinstance(event, dict):
                continue
            raw_line = _format_growth_event_line(event) or _parse_event_title(event, char.first_chapter, index)
            event_lines.append(f"- {relink(raw_line, skip=char.name)}")

        continuity_watch: list[str] = []
        if char.last_seen_chapter and book.total_chapters and book.total_chapters - char.last_seen_chapter >= 25:
            continuity_watch.append(f"Absent for {book.total_chapters - char.last_seen_chapter} chapters.")

        char_lines = [
            f"# {char_name}",
            "",
            f"- Status: {character_status(char)}",
            f"- First appearance: {_format_chapter_label(char.first_chapter)}",
            f"- Last appearance: {_format_chapter_label(char.last_seen_chapter)}",
            f"- Mentions tracked: {char.mention_count or 0}",
            f"- Aliases: {', '.join(char.aliases or [])}" if (char.aliases or []) else "- Aliases: -",
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
            char_lines.extend(["## Relationships", "", *[f"- {item}" for item in linked_relationships], ""])
        if linked_threads:
            char_lines.extend(["## Plot Thread Involvement", "", *[f"- {item}" for item in linked_threads], ""])
        if continuity_watch:
            char_lines.extend(["## Continuity Watch", "", *[f"- {item}" for item in continuity_watch], ""])

        files.append({
            "path": f"{root_folder}/Characters/{_safe_name(char_name)}.md",
            "content": "\n".join(char_lines),
        })

    relationship_index_lines = [
        "# Relationship Map",
        "",
        "| Character A | Character B | Type | Chapters | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for rel in relationships:
        a_name = _obsidian_note_title(_obj_value(rel, "character_a_name") or characters_by_id.get(str(_obj_value(rel, "character_a_id") or ""), "Unknown"))
        b_name = _obsidian_note_title(_obj_value(rel, "character_b_name") or characters_by_id.get(str(_obj_value(rel, "character_b_id") or ""), "Unknown"))
        rel_type = _clean_line(str(_obj_value(rel, "rel_type") or "neutral")).replace("_", " ").title()
        chapter_range = f"{_format_chapter_label(_to_int(_obj_value(rel, 'from_chapter') or 0) or None)}"
        if _obj_value(rel, "to_chapter"):
            chapter_range += f" to {_format_chapter_label(_to_int(_obj_value(rel, 'to_chapter') or 0) or None)}"
        else:
            chapter_range += " onward"
        note = relink(_clean_line(str(_obj_value(rel, "description") or "")), skip=a_name)
        relationship_index_lines.append(
            f"| [[{a_name}]] | [[{b_name}]] | {rel_type} | {chapter_range} | {note or '-'} |"
        )
    files.append({
        "path": f"{root_folder}/Relationships/Relationship Map.md",
        "content": "\n".join(relationship_index_lines + [""]),
    })

    thread_index_lines = ["# Plot Threads", ""]
    sorted_threads = sorted(
        plot_threads,
        key=lambda thread: (
            _obj_value(thread, "introduced_at") if _obj_value(thread, "introduced_at") is not None else 10**9,
            -_to_int(_obj_value(thread, "importance") or 0),
            _clean_line(str(_obj_value(thread, "title") or "")).lower(),
        ),
    )
    for thread in sorted_threads:
        title = _obsidian_note_title(_obj_value(thread, "title"))
        thread_index_lines.append(f"- [[{title}]]")
    thread_index_lines.append("")
    files.append({
        "path": f"{root_folder}/Plot Threads/Index.md",
        "content": "\n".join(thread_index_lines),
    })

    for thread in sorted_threads:
        title = _obsidian_note_title(_obj_value(thread, "title"))
        notes = relink(cast(str | None, _obj_value(thread, "note")), skip=title)
        description = relink(cast(str | None, _obj_value(thread, "description")), skip=title)
        char_ids = _obj_value(thread, "character_ids") or []
        linked_chars = _extract_related_character_names(char_ids, characters_by_id, link_targets)
        intro = _format_chapter_label(_to_int(_obj_value(thread, "introduced_at") or 0) or None, "Unknown start")
        resolved = cast(int | None, _obj_value(thread, "resolved_at"))
        lines = [
            f"# {title}",
            "",
            f"- Status: {_obj_value(thread, 'status') or 'unknown'}",
            f"- Importance: {_obj_value(thread, 'importance') or 5}/10",
            f"- Introduced: {intro}",
        ]
        if resolved:
            lines.append(f"- Resolved: {_format_chapter_label(resolved)}")
        lines.append("")
        if description:
            lines.extend([description, ""])
        if notes:
            lines.extend(["## Notes", "", notes, ""])
        if linked_chars:
            lines.extend(["## Linked Characters", "", *[f"- {item}" for item in linked_chars], ""])
        files.append({
            "path": f"{root_folder}/Plot Threads/{_safe_name(title)}.md",
            "content": "\n".join(lines),
        })

    wiki_index_lines = ["# Wiki", ""]
    wiki_groups: dict[str, list[object]] = defaultdict(list)
    for entry in wiki_entries:
        entry_type = _normalize_lookup(str(_obj_value(entry, "entry_type") or "concept"))
        wiki_groups[entry_type].append(entry)
    for folder_name, entry_type in [
        ("Locations", "location"),
        ("Factions", "faction"),
        ("Items", "item"),
        ("Events", "event"),
        ("Concepts", "concept"),
    ]:
        group = wiki_groups.get(entry_type, [])
        if not group:
            continue
        wiki_index_lines.append(f"## {folder_name}")
        for entry in sorted(group, key=lambda item: _normalize_lookup(str(_obj_value(item, "name") or ""))):
            name = _obsidian_note_title(_obj_value(entry, "name"))
            wiki_index_lines.append(f"- [[{name}]]")
        wiki_index_lines.append("")
    files.append({
        "path": f"{root_folder}/Wiki/Index.md",
        "content": "\n".join(wiki_index_lines),
    })

    for entry in wiki_entries:
        entry_type = _normalize_lookup(str(_obj_value(entry, "entry_type") or "concept"))
        folder_name = {
            "location": "Locations",
            "faction": "Factions",
            "item": "Items",
            "event": "Events",
            "concept": "Concepts",
        }.get(entry_type, "Concepts")
        name = _obsidian_note_title(_obj_value(entry, "name"))
        desc = relink(cast(str | None, _obj_value(entry, "description")))
        related_ids = _obj_value(entry, "related_char_ids")
        related_characters = _extract_related_character_names(related_ids, characters_by_id, link_targets)
        lines = [
            f"# {name}",
            "",
            f"- Type: {entry_type}",
            f"- First mention: {_format_chapter_label(cast(int | None, _obj_value(entry, 'first_mention')))}",
            "",
        ]
        if desc:
            lines.extend([desc, ""])
        if related_characters:
            lines.extend(["## Related Characters", "", *[f"- {item}" for item in related_characters], ""])
        files.append({
            "path": f"{root_folder}/Wiki/{folder_name}/{_safe_name(name)}.md",
            "content": "\n".join(lines),
        })

    reading_index_lines = ["# Reading Log", ""]
    sorted_chapters = sorted(chapter_rows, key=lambda row: int(row["number"]))
    for row in sorted_chapters:
        chapter_number = int(row["number"])
        reading_index_lines.append(f"- [[Chapter {chapter_number} Summary]]")
    reading_index_lines.append("")
    files.append({
        "path": f"{root_folder}/Reading Log/Index.md",
        "content": "\n".join(reading_index_lines),
    })

    events_by_chapter: dict[int, list[dict]] = defaultdict(list)
    for event in chapter_events:
        events_by_chapter[int(event["chapter_number"])].append(event)

    for row in sorted_chapters:
        chapter_number = int(row["number"])
        chapter_title = row.get("title") or f"Chapter {chapter_number}"
        summary_text = relink(cast(str | None, row.get("content")))
        key_events = events_by_chapter.get(chapter_number, [])
        lines = [
            f"# Chapter {chapter_number} Summary",
            "",
            f"- Title: {chapter_title}",
            "",
        ]
        if summary_text:
            lines.extend([summary_text, ""])
        if key_events:
            lines.extend(["## Key Events", ""])
            for event in key_events:
                lines.append(f"- [[{event['title']}]]")
            lines.append("")
        files.append({
            "path": f"{root_folder}/Reading Log/Chapter {chapter_number} Summary.md",
            "content": "\n".join(lines),
        })

    major_index_lines = ["# Story Major Events", ""]
    for event in chapter_events:
        major_index_lines.append(f"- [[{event['title']}]]")
    major_index_lines.append("")
    files.append({
        "path": f"{root_folder}/Story Major Events/Index.md",
        "content": "\n".join(major_index_lines),
    })

    sorted_events = sorted(
        chapter_events,
        key=lambda item: (
            int(item["chapter_number"]),
            _normalize_lookup(str(item["title"])),
        ),
    )
    for index, event in enumerate(sorted_events):
        title = _obsidian_note_title(event["title"])
        previous_title = sorted_events[index - 1]["title"] if index > 0 else None
        next_title = sorted_events[index + 1]["title"] if index + 1 < len(sorted_events) else None
        lines = [
            f"# {title}",
            "",
            f"- Chapter: {_format_chapter_label(cast(int | None, event['chapter_number']))}",
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
            lines.extend([relink(cast(str | None, event["description"])), ""])
        involved = _extract_related_character_names(event.get("involved_characters"), characters_by_id, link_targets)
        if involved:
            lines.extend(["## Involved Characters", "", *[f"- {item}" for item in involved], ""])
        files.append({
            "path": f"{root_folder}/Story Major Events/{_safe_name(title)}.md",
            "content": "\n".join(lines),
        })

    return root_folder, files


async def build_character_bible_obsidian_context(db, book_id) -> dict:
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
        select(Character).where(Character.book_id == book_id).order_by(Character.first_chapter, Character.name)
    )
    characters = characters_result.scalars().all()

    relationships_result = await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book_id))
    relationships = relationships_result.scalars().all()
    plot_threads_result = await db.execute(select(PlotThread).where(PlotThread.book_id == book_id))
    plot_threads = plot_threads_result.scalars().all()
    wiki_entries_result = await db.execute(select(WikiEntry).where(WikiEntry.book_id == book_id))
    wiki_entries = wiki_entries_result.scalars().all()
    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book_id, ChapterSummary.mode == "short")
            .order_by(Chapter.number)
        )
    ).all()

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
        if summary_a:
            append_unique_summary(rel_summaries, rel_keys, str(a.id), f"{rel.rel_type}:{b.name}".lower(), summary_a)
        if summary_b:
            append_unique_summary(rel_summaries, rel_keys, str(b.id), f"{rel.rel_type}:{a.name}".lower(), summary_b)

    thread_summaries: dict[str, list[str]] = {}
    for thread in plot_threads:
        for raw_name in thread.character_ids or []:
            owner = next((char for char in characters if char.name == raw_name), None)
            if owner is None:
                continue
            thread_summaries.setdefault(str(owner.id), []).append(
                f"{thread.title} [{thread.status}]" + (f" — note: {thread.note}" if thread.note else "")
            )

    chapter_events: list[dict] = []
    for chapter_number, chapter_title, content, key_events in chapter_rows:
        for index, event in enumerate(key_events or [], start=1):
            if isinstance(event, dict) and _parse_event_title(event, chapter_number, index):
                chapter_events.append({
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "title": _parse_event_title(event, chapter_number, index),
                    "description": _parse_event_description(event),
                    "importance": _parse_event_importance(event),
                    "involved_characters": event.get("involved_characters") if isinstance(event, dict) else None,
                })
            elif isinstance(event, str) and event.strip():
                chapter_events.append({
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "title": event.strip(),
                    "description": "",
                    "importance": None,
                    "involved_characters": None,
                })

    return {
        "book": book,
        "characters": characters,
        "relationships": relationships,
        "plot_threads": plot_threads,
        "wiki_entries": wiki_entries,
        "chapter_rows": [
            {"number": chapter_number, "title": chapter_title, "content": content}
            for chapter_number, chapter_title, content, _ in chapter_rows
        ],
        "chapter_events": chapter_events,
        "rel_summaries": rel_summaries,
        "thread_summaries": thread_summaries,
    }

# ─── Character card ──────────────────────────────────────────────────────────

def character_card_markdown(payload: dict) -> tuple[bytes, str]:
    def bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items if item]

    lines = [
        f"# {payload['name']} - Character Card",
        "",
        f"- Manuscript: {payload['book_title']}",
        f"- Status: {payload['status']}",
        f"- First appearance: Chapter {payload['first_appearance']}" if payload["first_appearance"] else "- First appearance: -",
        f"- Last appearance: Chapter {payload['last_appearance']}" if payload["last_appearance"] else "- Last appearance: -",
        f"- Mentions count: {payload['mentions_count']}",
        f"- Role: {payload['role'] or '-'}",
        f"- Aliases: {', '.join(payload['aliases'])}" if payload["aliases"] else "- Aliases: -",
        "",
        "## Overview",
        "",
        payload["description"] or "LoreVia is still building this profile.",
        "",
    ]
    if payload["personality_tags"]:
        lines.extend(["## Personality", "", *bullets(payload["personality_tags"]), ""])
    if payload["motivations"]:
        lines.extend(["## Motivations", "", *bullets(payload["motivations"]), ""])
    if payload["fears"]:
        lines.extend(["## Fears", "", *bullets(payload["fears"]), ""])
    if payload["arc_summary"]:
        lines.extend(["## Arc Summary", "", payload["arc_summary"], ""])
    if payload["growth_events"]:
        lines.extend(["## Key Growth Events", ""])
        for event in payload["growth_events"]:
            if not isinstance(event, dict):
                continue
            lines.append(f"- {_format_growth_event_line(event)}")
        lines.append("")
    if payload.get("plot_threads"):
        lines.extend(["## Plot Thread Involvement", ""])
        for thread in payload["plot_threads"]:
            status = thread.get("status", "unknown")
            chapter_span = f"Introduced in Chapter {thread.get('introduced_at') or '-'}"
            if thread.get("resolved_at"):
                chapter_span += f", resolved in Chapter {thread.get('resolved_at')}"
            lines.append(f"- {thread.get('title')}: {status}. {chapter_span}")
            if thread.get("note"):
                lines.append(f"  Author note: {thread.get('note')}")
        lines.append("")
    if payload.get("continuity_watch"):
        lines.extend(["## Continuity Watch", "", *bullets(payload["continuity_watch"]), ""])
    if payload["relationships"]:
        lines.extend(["## Relationships", ""])
        for rel in payload["relationships"]:
            active_range = f"Chapter {rel['from_chapter']}" if rel["from_chapter"] else "Unknown start"
            active_range += f" to Chapter {rel['to_chapter']}" if rel["to_chapter"] else " onward"
            lines.append(f"- {rel['name']}: {rel['type'].title()} | {active_range}")
            if rel["description"]:
                lines.append(f"  {rel['description']}")
        lines.append("")
    return "\n".join(lines).encode("utf-8"), payload["filename_base"]


def character_card_pdf(payload: dict) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"{payload['name']} - Character Card", styles["Heading1"]), Spacer(1, 0.14 * inch)]

    metadata = [
        ["Manuscript", payload["book_title"] or "-"],
        ["Status", payload["status"]],
        ["First appearance", f"Chapter {payload['first_appearance']}" if payload["first_appearance"] else "-"],
        ["Last appearance", f"Chapter {payload['last_appearance']}" if payload["last_appearance"] else "-"],
        ["Mentions count", str(payload["mentions_count"])],
        ["Aliases", ", ".join(payload["aliases"]) or "-"],
    ]
    metadata_table = Table(metadata, colWidths=[1.7 * inch, 4.8 * inch])
    metadata_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([metadata_table, Spacer(1, 0.16 * inch)])

    story.append(Paragraph("Overview", styles["Heading2"]))
    story.append(Paragraph(payload["description"] or "LoreVia is still building this profile.", styles["BodyText"]))
    story.append(Spacer(1, 0.12 * inch))

    for heading, items in [
        ("Personality", payload["personality_tags"]),
        ("Motivations", payload["motivations"]),
        ("Fears", payload["fears"]),
    ]:
        if not items:
            continue
        story.append(Paragraph(heading, styles["Heading2"]))
        for item in items:
            story.append(Paragraph(f"• {item}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    if payload["arc_summary"]:
        story.append(Paragraph("Arc Summary", styles["Heading2"]))
        story.append(Paragraph(payload["arc_summary"], styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    if payload["growth_events"]:
        story.append(Paragraph("Key Growth Events", styles["Heading2"]))
        for event in payload["growth_events"]:
            if not isinstance(event, dict):
                continue
            event_line = _format_growth_event_line(event)
            if not event_line:
                continue
            story.append(Paragraph(f"• {event_line}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))
    if payload.get("plot_threads"):
        story.append(Paragraph("Plot Thread Involvement", styles["Heading2"]))
        for thread in payload["plot_threads"]:
            chapter_span = f"Introduced in Chapter {thread.get('introduced_at') or '-'}"
            if thread.get("resolved_at"):
                chapter_span += f", resolved in Chapter {thread.get('resolved_at')}"
            note = f" Note: {thread.get('note')}" if thread.get("note") else ""
            story.append(Paragraph(f"â€¢ {thread.get('title')} ({thread.get('status', 'unknown')}). {chapter_span}.{note}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))
    if payload.get("continuity_watch"):
        story.append(Paragraph("Continuity Watch", styles["Heading2"]))
        for item in payload["continuity_watch"]:
            story.append(Paragraph(f"â€¢ {item}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    story.append(Paragraph("Relationships", styles["Heading2"]))
    if payload["relationships"]:
        rel_table_data = [["Character", "Type", "Chapters", "Note"]]
        for rel in payload["relationships"]:
            chapter_range = f"{rel['from_chapter'] or '-'}"
            chapter_range += f" to {rel['to_chapter']}" if rel["to_chapter"] else " onward"
            rel_table_data.append([rel["name"], rel["type"].title(), chapter_range, rel["description"] or "-"])
        rel_table = Table(rel_table_data, colWidths=[1.4 * inch, 1.15 * inch, 1.1 * inch, 3.0 * inch], repeatRows=1)
        rel_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(rel_table)
    else:
        story.append(Paragraph("No tracked relationships yet.", styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()


def character_card_docx(payload: dict) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    doc.add_heading(f"{payload['name']} - Character Card", level=1)
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in [
        ("Manuscript", payload["book_title"] or "-"),
        ("Status", payload["status"]),
        ("First appearance", f"Chapter {payload['first_appearance']}" if payload["first_appearance"] else "-"),
        ("Last appearance", f"Chapter {payload['last_appearance']}" if payload["last_appearance"] else "-"),
        ("Mentions count", str(payload["mentions_count"])),
        ("Aliases", ", ".join(payload["aliases"]) or "-"),
    ]:
        row = table.add_row().cells
        row[0].text = label
        row[1].text = value

    doc.add_heading("Overview", level=2)
    doc.add_paragraph(payload["description"] or "LoreVia is still building this profile.")
    for heading, items in [
        ("Personality", payload["personality_tags"]),
        ("Motivations", payload["motivations"]),
        ("Fears", payload["fears"]),
    ]:
        if not items:
            continue
        doc.add_heading(heading, level=2)
        for item in items:
            doc.add_paragraph(item, style="List Bullet")
    if payload["arc_summary"]:
        doc.add_heading("Arc Summary", level=2)
        doc.add_paragraph(payload["arc_summary"])
    if payload["growth_events"]:
        doc.add_heading("Key Growth Events", level=2)
        for event in payload["growth_events"]:
            if not isinstance(event, dict):
                continue
            event_line = _format_growth_event_line(event)
            if not event_line:
                continue
            doc.add_paragraph(event_line, style="List Bullet")
    if payload.get("plot_threads"):
        doc.add_heading("Plot Thread Involvement", level=2)
        for thread in payload["plot_threads"]:
            chapter_span = f"Introduced in Chapter {thread.get('introduced_at') or '-'}"
            if thread.get("resolved_at"):
                chapter_span += f", resolved in Chapter {thread.get('resolved_at')}"
            note = f" Note: {thread.get('note')}" if thread.get("note") else ""
            doc.add_paragraph(f"{thread.get('title')} ({thread.get('status', 'unknown')}). {chapter_span}.{note}", style="List Bullet")
    if payload.get("continuity_watch"):
        doc.add_heading("Continuity Watch", level=2)
        for item in payload["continuity_watch"]:
            doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("Relationships", level=2)
    rel_table = doc.add_table(rows=1, cols=4)
    rel_table.style = "Table Grid"
    for idx, heading in enumerate(["Character", "Type", "Chapters", "Note"]):
        rel_table.rows[0].cells[idx].text = heading
    for rel in payload["relationships"]:
        row = rel_table.add_row().cells
        row[0].text = rel["name"]
        row[1].text = rel["type"].title()
        row[2].text = f"{rel['from_chapter'] or '-'}" + (f" to {rel['to_chapter']}" if rel["to_chapter"] else " onward")
        row[3].text = rel["description"] or "-"

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ─── Character bible ─────────────────────────────────────────────────────────

def character_bible_markdown(
    *,
    book: Book,
    characters: list[Character],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
) -> tuple[bytes, str]:
    def _clean_line(value: object | None) -> str:
        return " ".join(str(value or "").split()).strip()

    def _bullets(items: list[str]) -> str:
        cleaned = [item.strip() for item in items if item and item.strip()]
        return "\n".join(f"- {item}" for item in cleaned) if cleaned else ""

    title = _clean_line(book.title) or "LoreVia Character Bible"
    header = [
        f"# {title} - Character Bible",
        "",
        f"- Source: {book.title}",
        f"- Format: {book.format.upper()}",
        "",
        "This file is auto-generated from LoreVia's manuscript extraction pipeline.",
        "",
        "## Characters",
        "",
    ]

    body: list[str] = []
    for char in characters:
        relationship_lines = dedupe_preserve_order(rel_summaries.get(str(char.id), []))
        description = _clean_line(build_description(char.trait_state or {}, char.archetype))
        if relationship_lines:
            description = merge_description_with_relationships(description, relationship_lines)
        tags = [item for item in (char.personality_tags or []) if _clean_line(item)]
        motivations = [item for item in (char.motivations or []) if _clean_line(item)]
        fears = [item for item in (char.fears or []) if _clean_line(item)]

        body.extend([
            f"### {char.name}",
            "",
            f"- Status: {character_status(char)}",
            f"- First appearance: Chapter {char.first_chapter}" if char.first_chapter else "- First appearance: -",
            f"- Last appearance: Chapter {char.last_seen_chapter}" if char.last_seen_chapter else "- Last appearance: -",
            f"- Mentions tracked: {char.mention_count or 0}",
            f"- Aliases: {', '.join(char.aliases or [])}" if (char.aliases or []) else "- Aliases: -",
            "",
            f"Short description: {description or 'LoreVia is still building this profile.'}",
            "",
        ])

        if tags:
            body.append("Personality")
            body.append(_bullets(tags[:10]))
            body.append("")
        if motivations:
            body.append("Motivations")
            body.append(_bullets(motivations[:8]))
            body.append("")
        if fears:
            body.append("Fears")
            body.append(_bullets(fears[:8]))
            body.append("")
        if _clean_line(char.arc_summary):
            body.append("Arc summary")
            body.append(_bullets([_clean_line(char.arc_summary)]))
            body.append("")
        if relationship_lines:
            body.append("Relationships")
            body.append(_bullets(relationship_lines))
            body.append("")
        thread_lines = dedupe_preserve_order(thread_summaries.get(str(char.id), []))
        if thread_lines:
            body.append("Plot thread involvement")
            body.append(_bullets(thread_lines))
            body.append("")
        continuity_watch: list[str] = []
        if char.last_seen_chapter and book.total_chapters and book.total_chapters - char.last_seen_chapter >= 25:
            continuity_watch.append(f"Absent for {book.total_chapters - char.last_seen_chapter} chapters.")
        if continuity_watch:
            body.append("Continuity watch")
            body.append(_bullets(continuity_watch))
            body.append("")

        body.append("---")
        body.append("")

    markdown = "\n".join(header + body).encode("utf-8")
    safe_name = "".join(ch for ch in (book.title or "lorevia") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-")
    return markdown, safe_name or "lorevia"


def character_bible_pdf(*, markdown: bytes, title: str) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    story = []

    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body_style = styles["BodyText"]
    body_style.leading = 14
    body_style.textColor = colors.black

    text = markdown.decode("utf-8", errors="ignore").splitlines()
    story.append(Paragraph(title, h1))
    story.append(Spacer(1, 0.2 * inch))

    for line in text:
        if line.startswith("### "):
            story.append(Spacer(1, 0.14 * inch))
            story.append(Paragraph(line.replace("### ", ""), h2))
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            story.append(Spacer(1, 0.18 * inch))
            story.append(Paragraph(line.replace("## ", ""), h1))
            story.append(Spacer(1, 0.12 * inch))
            continue
        if not line.strip():
            story.append(Spacer(1, 0.10 * inch))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", body_style))
        else:
            story.append(Paragraph(line, body_style))

    doc.build(story)
    return buffer.getvalue()


def character_bible_docx(*, markdown: bytes, title: str) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph("")

    for line in markdown.decode("utf-8", errors="ignore").splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            doc.add_heading(line.replace("## ", ""), level=2)
            continue
        if line.startswith("### "):
            doc.add_heading(line.replace("### ", ""), level=3)
            continue
        if line.startswith("- "):
            doc.add_paragraph(line[2:], style="List Bullet")
            continue
        if line.strip() == "---":
            doc.add_page_break()
            continue
        doc.add_paragraph(line)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def character_bible_obsidian_manifest(
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
    return _build_obsidian_manifest(
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


def _apply_obsidian_overrides(files: list[dict[str, str]], overrides: dict[str, str] | None) -> list[dict[str, str]]:
    if not overrides:
        return files
    return [
        {
            "path": file["path"],
            "content": overrides.get(file["path"], file["content"]),
        }
        for file in files
    ]


def character_bible_obsidian_folder(
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
) -> tuple[bytes, str]:
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    root_folder, files = character_bible_obsidian_manifest(
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
    files = _apply_obsidian_overrides(files, overrides)

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as zipf:
        for file in files:
            zipf.writestr(file["path"], file["content"])
    buffer.seek(0)
    return buffer.getvalue(), root_folder.replace("LoreVia Export - ", "")


def character_bible_obsidian_preview(
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
    root_folder, files = character_bible_obsidian_manifest(
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
    files = _apply_obsidian_overrides(files, overrides)
    return {
        "root_folder": root_folder,
        "files": files,
    }


def _manuscript_export_preset(preset: str) -> dict[str, Any]:
    normalized = " ".join((preset or "").split()).strip().lower()
    if normalized == "kdp_paperback":
        return {
            "docx_font": "Garamond",
            "docx_font_size": 11,
            "pdf_page_size": "LETTER",
            "pdf_margins": (0.88, 0.75, 0.8, 0.8),
            "title": "Amazon KDP paperback",
        }
    if normalized == "trade_paperback":
        return {
            "docx_font": "Garamond",
            "docx_font_size": 11,
            "pdf_page_size": "A5",
            "pdf_margins": (0.8, 0.8, 0.75, 0.75),
            "title": "Trade paperback",
        }
    return {
        "docx_font": "Times New Roman",
        "docx_font_size": 12,
        "pdf_page_size": "A4",
        "pdf_margins": (0.9, 0.9, 0.8, 0.8),
        "title": "Standard manuscript",
    }


def manuscript_docx(*, title: str, chapters: list[dict], preset: str = "standard_manuscript") -> bytes:
    from io import BytesIO

    from bs4 import BeautifulSoup
    from docx import Document
    from docx.shared import Pt

    def add_html_block(doc: Any, html: str | None, fallback_text: str) -> None:
        cleaned_html = clean_manuscript_html(html)
        if not cleaned_html:
            for block in fallback_text.splitlines():
                doc.add_paragraph(block)
            return

        soup = BeautifulSoup(cleaned_html, "html.parser")
        for node in soup.find_all(["h1", "h2", "h3", "p", "blockquote", "ul", "ol"]):
            if node.name in {"h1", "h2", "h3"}:
                level = {"h1": 2, "h2": 3, "h3": 4}[node.name]
                doc.add_heading(node.get_text(" ", strip=True), level=level)
                continue
            if node.name in {"ul", "ol"}:
                style = "List Bullet" if node.name == "ul" else "List Number"
                for li in node.find_all("li", recursive=False):
                    doc.add_paragraph(li.get_text(" ", strip=True), style=style)
                continue
            paragraph = doc.add_paragraph(node.get_text("\n", strip=True))
            if node.name == "blockquote":
                paragraph.style = "Intense Quote"

    export_preset = _manuscript_export_preset(preset)
    doc = Document()
    normal_style = cast(Any, doc.styles["Normal"])
    normal_style.font.name = str(export_preset["docx_font"])
    normal_style.font.size = Pt(int(export_preset["docx_font_size"]))

    doc.add_heading(title or "LoreVia Manuscript Export", level=1)
    doc.add_paragraph(f"Preset: {export_preset['title']}")
    for chapter in chapters:
        doc.add_page_break()
        chapter_number = chapter.get("number")
        chapter_title = chapter.get("title") or f"Chapter {chapter_number}"
        doc.add_heading(f"Chapter {chapter_number}", level=2)
        if chapter_title and chapter_title != f"Chapter {chapter_number}":
            doc.add_paragraph(chapter_title)
        add_html_block(doc, chapter.get("html"), str(chapter.get("text") or ""))

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def manuscript_pdf(*, title: str, chapters: list[dict], preset: str = "standard_manuscript") -> bytes:
    from io import BytesIO

    from bs4 import BeautifulSoup
    from reportlab.lib.pagesizes import A4, A5, LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    def escaped(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def build_story_blocks(html: str | None, fallback_text: str, body_style, heading_styles):
        cleaned_html = clean_manuscript_html(html)
        if not cleaned_html:
            for paragraph in fallback_text.splitlines():
                if paragraph.strip():
                    yield Paragraph(escaped(paragraph), body_style)
                else:
                    yield Spacer(1, 0.12 * inch)
            return

        soup = BeautifulSoup(cleaned_html, "html.parser")
        for node in soup.find_all(["h1", "h2", "h3", "p", "blockquote", "ul", "ol"]):
            if node.name in {"h1", "h2", "h3"}:
                yield Paragraph(escaped(node.get_text(" ", strip=True)), heading_styles[node.name])
                continue
            if node.name in {"ul", "ol"}:
                bullet = "•" if node.name == "ul" else "1."
                for li in node.find_all("li", recursive=False):
                    yield Paragraph(f"{bullet} {escaped(li.get_text(' ', strip=True))}", body_style)
                continue
            text = node.get_text("\n", strip=True)
            if text:
                yield Paragraph(escaped(text), body_style)
            else:
                yield Spacer(1, 0.12 * inch)

    export_preset = _manuscript_export_preset(preset)
    page_size = {"A4": A4, "A5": A5, "LETTER": LETTER}[str(export_preset["pdf_page_size"])]
    left_margin, right_margin, top_margin, bottom_margin = cast(tuple[float, float, float, float], export_preset["pdf_margins"])
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=left_margin * inch,
        rightMargin=right_margin * inch,
        topMargin=top_margin * inch,
        bottomMargin=bottom_margin * inch,
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontName = "Times-Roman"
    body.leading = 18
    heading_styles = {"h1": styles["Heading1"], "h2": styles["Heading2"], "h3": styles["Heading3"]}

    story = [
        Paragraph(title or "LoreVia Manuscript Export", styles["Heading1"]),
        Paragraph(f"Preset: {export_preset['title']}", styles["BodyText"]),
        Spacer(1, 0.2 * inch),
    ]
    for index, chapter in enumerate(chapters):
        if index > 0:
            story.append(PageBreak())
        chapter_number = chapter.get("number")
        chapter_title = chapter.get("title") or f"Chapter {chapter_number}"
        story.append(Paragraph(f"Chapter {chapter_number}", styles["Heading2"]))
        if chapter_title and chapter_title != f"Chapter {chapter_number}":
            story.append(Paragraph(chapter_title, body))
            story.append(Spacer(1, 0.1 * inch))
        story.extend(build_story_blocks(chapter.get("html"), str(chapter.get("text") or ""), body, heading_styles))

    doc.build(story)
    return buffer.getvalue()


def manuscript_epub(*, title: str, chapters: list[dict], preset: str = "standard_manuscript") -> bytes:
    from ebooklib import epub
    import os
    import tempfile

    book = epub.EpubBook()
    safe_title = _clean_line(title) or "LoreVia Manuscript Export"
    export_preset = _manuscript_export_preset(preset)
    book.set_identifier(_safe_name(safe_title) or "lorevia-manuscript")
    book.set_title(safe_title)
    book.set_language("en")
    book.add_author("LoreVia")

    spine: list[Any] = ["nav"]
    toc_entries: list[Any] = []
    stylesheet = epub.EpubItem(
        uid="style_nav",
        file_name="styles/main.css",
        media_type="text/css",
        content=(
            "body { font-family: serif; line-height: 1.6; margin: 5%; } "
            "h1, h2 { page-break-after: avoid; } "
            ".preset-note { font-size: 0.85em; color: #555; }"
        ).encode("utf-8"),
    )
    book.add_item(stylesheet)

    for chapter in chapters:
        chapter_number = chapter.get("number")
        chapter_title = _clean_line(chapter.get("title")) or f"Chapter {chapter_number}"
        chapter_html = clean_manuscript_html(chapter.get("html")) or f"<p>{_clean_line(chapter.get('text'))}</p>"
        item = epub.EpubHtml(
            title=chapter_title,
            file_name=f"chapter-{chapter_number}.xhtml",
            lang="en",
        )
        item.content = (
            f"<h1>{chapter_title}</h1>"
            f"<p class='preset-note'>Preset: {export_preset['title']}</p>"
            f"{chapter_html}"
        )
        item.add_item(stylesheet)
        book.add_item(item)
        spine.append(item)
        toc_entries.append(item)

    book.toc = tuple(toc_entries)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "manuscript.epub")
        epub.write_epub(target, book, {})
        with open(target, "rb") as handle:
            return handle.read()
