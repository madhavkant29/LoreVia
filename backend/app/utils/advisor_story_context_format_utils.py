from __future__ import annotations


def format_story_character_lines(book: object | None) -> list[str]:
    characters = list(getattr(book, "characters", None) or []) if book is not None else []
    if not characters:
        return []
    lines = ["\nCHARACTERS (extracted from manuscript):"]
    sorted_chars = sorted(characters, key=lambda c: (c.first_chapter or 0, c.name or ""))[:20]
    for character in sorted_chars:
        role_str = f"[{character.role}]" if character.role else ""
        arc = (
            (character.arc_summary[:120] + "...")
            if character.arc_summary and len(character.arc_summary) > 120
            else (character.arc_summary or "")
        )
        tags = ", ".join((character.personality_tags or [])[:3])
        motives = "; ".join((character.motivations or [])[:2])
        growth = ""
        if isinstance(character.growth_events, list) and character.growth_events:
            latest_growth = next(
                (
                    item
                    for item in reversed(character.growth_events)
                    if isinstance(item, dict) and (item.get("event") or item.get("event_title"))
                ),
                None,
            )
            if latest_growth:
                growth_title = latest_growth.get("event") or latest_growth.get("event_title")
                growth = f"Recent growth beat: {growth_title}."
        trait_bits: list[str] = []
        if isinstance(character.trait_state, dict):
            for trait_key in ("eyes", "hair", "build", "age_descriptor"):
                raw = character.trait_state.get(trait_key)
                value = (
                    raw.get("value")
                    if isinstance(raw, dict)
                    else (raw if isinstance(raw, str) else None)
                )
                if value:
                    trait_bits.append(f"{trait_key}={value}")
        traits_str = "; ".join(trait_bits[:3])
        lines.append(
            f"  \u00e2\u20ac\u00a2 {character.name} {role_str} "
            f"\u00e2\u20ac\u201d first ch.{character.first_chapter}. "
            + (f"Arc: {arc} " if arc else "")
            + (f"Personality: {tags}. " if tags else "")
            + (f"Physical: {traits_str}. " if traits_str else "")
            + (f"Drives: {motives}. " if motives else "")
            + growth
        )
    return lines


def format_story_plot_thread_lines(book: object | None) -> list[str]:
    plot_threads = list(getattr(book, "plot_threads", None) or []) if book is not None else []
    if not plot_threads:
        return []
    lines = ["\nPLOT THREADS (extracted from manuscript):"]
    sorted_threads = sorted(
        plot_threads,
        key=lambda thread: thread.importance or 5,
        reverse=True,
    )[:12]
    for thread in sorted_threads:
        desc = (
            (thread.description[:100] + "...")
            if thread.description and len(thread.description) > 100
            else (thread.description or "")
        )
        status_label = str(thread.status or "introduced").upper()
        lines.append(
            f"  \u00e2\u20ac\u00a2 [{status_label}] {thread.title} "
            f"(importance {thread.importance}/10, introduced ch.{thread.introduced_at}). {desc}"
        )
    return lines


def format_world_reference_lines(world_rows: list[tuple]) -> list[str]:
    if not world_rows:
        return []
    lines = ["\nWORLD REFERENCE CORPUS (author-supplied lore):"]
    for name, element_type, description, _usage_count in world_rows:
        snippet = (
            (description[:120] + "...")
            if description and len(description) > 120
            else (description or "")
        )
        lines.append(f"  \u00e2\u20ac\u00a2 {name} [{element_type}] {snippet}")
    return lines


def format_major_event_lines(event_rows: list[tuple]) -> list[str]:
    event_lines: list[str] = []
    for chapter_num, chapter_title, key_events in event_rows:
        if not isinstance(key_events, list):
            continue
        for item in key_events[:3]:
            if not isinstance(item, dict):
                continue
            title = " ".join(
                str(item.get("event_title") or item.get("event") or "").split()
            ).strip()
            if not title:
                continue
            chapter_label = f"ch.{chapter_num}"
            if chapter_title:
                chapter_label += f" ({chapter_title})"
            event_lines.append(f"  - {title} [{chapter_label}]")
    if not event_lines:
        return []
    return ["\nMAJOR EVENTS (extracted from manuscript):", *event_lines[:12]]


def format_story_world_element_lines(book: object | None) -> list[str]:
    world_elements = list(getattr(book, "world_elements", None) or []) if book is not None else []
    if not world_elements:
        return []
    lines = ["\nWORLD ELEMENTS (extracted from manuscript):"]
    sorted_world = sorted(
        world_elements,
        key=lambda world_element: world_element.usage_count or 0,
        reverse=True,
    )[:12]
    for world_element in sorted_world:
        desc = " ".join(str(world_element.description or "").split()).strip()
        if len(desc) > 100:
            desc = desc[:100] + "..."
        lines.append(
            f"  - {world_element.name} [{world_element.element_type}] "
            f"usage={world_element.usage_count}. {desc}"
        )
    return lines


def format_theme_lines(theme_rows: list[tuple]) -> list[str]:
    theme_lines: list[str] = []
    seen_themes: set[str] = set()
    for chapter_num, themes in theme_rows:
        if not isinstance(themes, list):
            continue
        for item in themes:
            if not isinstance(item, dict):
                continue
            name = " ".join(str(item.get("theme") or "").split()).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen_themes:
                continue
            seen_themes.add(key)
            signal = item.get("signal")
            depth = item.get("depth")
            evidence = " ".join(str(item.get("evidence") or "").split()).strip()
            theme_lines.append(
                f"  \u00e2\u20ac\u00a2 {name} (chapter {chapter_num}"
                + (f", {signal}" if signal else "")
                + (f", {depth}" if depth else "")
                + f"). {evidence[:120]}"
            )
            if len(theme_lines) >= 10:
                break
        if len(theme_lines) >= 10:
            break
    if not theme_lines:
        return []
    return ["\nTHEMES (including philosophical subtext):", *theme_lines]
