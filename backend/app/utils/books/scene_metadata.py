"""Focused book scene metadata workflows."""

from __future__ import annotations

import re
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
    NovelScene,
)
from app.utils.books import (
    book_text,
    manuscript,
    normalization,
)
from app.utils.books.chapter_titles import (
    _count_words,
)


async def refresh_screenplay_scene_rows(
    db: AsyncSession,
    *,
    book: Book,
    parsed_scenes: list[Any],
    starting_number: int = 1,
    replace_scene_numbers: set[int] | None = None,
) -> None:
    from app.utils.screenplay_utils import replace_book_scenes

    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.id)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number)
        )
    ).all()
    chapter_ids_by_number = {int(number): chapter_id for number, chapter_id in chapter_rows}
    await replace_book_scenes(
        db,
        book=book,
        parsed_scenes=parsed_scenes,
        chapter_ids_by_number=chapter_ids_by_number,
        starting_number=starting_number,
        replace_scene_numbers=replace_scene_numbers,
    )


def _scene_slug(value: str, fallback: str = "scene") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned or fallback


def _scene_display_title(text: str, index: int) -> str:
    for line in (text or "").splitlines():
        cleaned = " ".join(line.split()).strip()
        if cleaned and not normalization.SCENE_BREAK_LINE_RE.match(cleaned):
            return cleaned[:80]
    return f"Scene {index}"


def _scene_folder_for_chapter(chapter_number: int | None) -> str:
    if isinstance(chapter_number, int) and chapter_number > 0:
        return f"scenes/chapter-{chapter_number:02d}"
    return "scenes/unassigned"


def build_novel_scene_path(*, chapter_number: int | None, sort_order: int, title: str) -> str:
    return f"{_scene_folder_for_chapter(chapter_number)}/{sort_order:03d}-{_scene_slug(title)}.md"


def _scene_metadata_key(label: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", label.strip().lower()).strip()
    if not normalized:
        return None
    alias = normalization.SCENE_METADATA_ALIASES.get(normalized)
    if alias:
        return alias
    key = normalized.replace(" ", "_")
    return key if key in normalization.SCENE_METADATA_LABELS else None


def _append_scene_metadata_value(metadata: dict[str, Any], key: str, value: str) -> None:
    cleaned = book_text._clean_text(value)
    if not cleaned:
        return
    if key in normalization.SCENE_METADATA_LIST_FIELDS:
        values = metadata.setdefault(key, [])
        if isinstance(values, list) and cleaned not in values:
            values.append(cleaned)
        return
    metadata[key] = cleaned


def extract_scene_metadata(text: str, *, description: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    active_list_key: str | None = None
    for raw_line in (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line or normalization.SCENE_BREAK_LINE_RE.match(line):
            active_list_key = None
            continue
        label_match = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", line)
        if label_match:
            key = _scene_metadata_key(label_match.group(1))
            if key is None:
                active_list_key = None
                continue
            value = label_match.group(2).strip()
            if value:
                _append_scene_metadata_value(metadata, key, value)
                active_list_key = None
            else:
                if key in normalization.SCENE_METADATA_LIST_FIELDS:
                    metadata.setdefault(key, [])
                active_list_key = key
            continue
        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        if bullet_match and active_list_key:
            _append_scene_metadata_value(metadata, active_list_key, bullet_match.group(1))
            continue
        active_list_key = None
    if description and "summary" not in metadata:
        metadata["summary"] = book_text._clean_text(description)
    return {key: value for key, value in metadata.items() if value not in ("", [], None)}


def normalize_scene_metadata(
    metadata: dict[str, Any] | None, *, description: str | None = None
) -> dict[str, Any]:
    base = extract_scene_metadata("", description=description)
    source = metadata if isinstance(metadata, dict) else {}
    normalized: dict[str, Any] = {}

    def _clean_list(values: object) -> list[str]:
        cleaned_values: list[str] = []
        if isinstance(values, list):
            for value in values:
                cleaned = book_text._clean_text(value)
                if cleaned and cleaned not in cleaned_values:
                    cleaned_values.append(cleaned)
        elif values is not None:
            cleaned = book_text._clean_text(values)
            if cleaned:
                cleaned_values.append(cleaned)
        return cleaned_values

    for key in normalization.SCENE_METADATA_UI_FIELDS:
        value = source.get(key)
        if key in {"tags", "mood", "anchors", "bookmarks"}:
            cleaned_list = _clean_list(value)
            if cleaned_list:
                normalized[key] = cleaned_list
            continue
        cleaned = book_text._clean_optional_text(cast(str | None, value))
        if cleaned:
            normalized[key] = cleaned

    inferred = extract_scene_metadata(str(source.get("summary") or ""), description=description)
    merged = {**base, **inferred, **normalized}
    if description and "summary" not in merged:
        merged["summary"] = book_text._clean_text(description)
    return {key: value for key, value in merged.items() if value not in ("", [], None)}


def _scene_title_line_matches(line: str, title: str) -> bool:
    cleaned = " ".join(line.split()).strip()
    if not cleaned:
        return False
    heading_match = normalization.SCENE_HEADING_LINE_RE.match(cleaned)
    if heading_match and heading_match.group(1):
        cleaned = heading_match.group(1).strip()
    title_cleaned = " ".join((title or "").split()).strip()
    return bool(title_cleaned and cleaned.lower() == title_cleaned.lower())


def strip_scene_planning_block(text: str, *, title: str | None = None) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        cleaned = lines[index].strip()
        if (title and _scene_title_line_matches(cleaned, title)) or re.match(
            r"^#{1,3}\s+Scene\b", cleaned, re.IGNORECASE
        ):
            index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1

    consumed_metadata = False
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            if consumed_metadata:
                index += 1
                continue
            break
        if stripped == "---" and consumed_metadata:
            index += 1
            break
        if stripped == "---":
            index += 1
            continue
        label_match = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", stripped)
        if label_match and _scene_metadata_key(label_match.group(1)) is not None:
            consumed_metadata = True
            index += 1
            while index < len(lines):
                continuation = lines[index].strip()
                if not continuation:
                    index += 1
                    break
                next_label = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", continuation)
                if next_label and _scene_metadata_key(next_label.group(1)) is not None:
                    break
                if re.match(r"^[-*]\s+.+$", continuation):
                    index += 1
                    continue
                break
            continue
        break
    return "\n".join(lines[index:]).strip()


def build_scene_chapter_import_text(
    scene: dict[str, Any],
    *,
    scene_number: int,
    include_metadata: bool = True,
) -> str:
    title = book_text._clean_text(scene.get("title")) or f"Scene {scene_number}"
    body = strip_scene_planning_block(str(scene.get("body") or ""), title=title)
    if not include_metadata:
        return body

    heading = title
    scene_label_match = re.match(r"^Scene\s+\d+\b", title, re.IGNORECASE)
    if not scene_label_match:
        heading = f"Scene {scene_number} - {title}"
    lines = [f"## {heading}", ""]
    metadata = scene.get("metadata") or scene.get("scene_metadata") or {}
    if not isinstance(metadata, dict) or not metadata:
        metadata = extract_scene_metadata(
            str(scene.get("body") or ""), description=cast(str | None, scene.get("description"))
        )

    for key in ["pov", "location", "time", "timeline"]:
        value = metadata.get(key)
        if value:
            lines.append(f"{normalization.SCENE_METADATA_LABELS[key]}: {value}")
    if any(metadata.get(key) for key in ["pov", "location", "time", "timeline"]):
        lines.append("")
    for key in ["characters", "objects", "goals", "plot_threads", "mood"]:
        values = metadata.get(key)
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list) and values:
            lines.append(f"{normalization.SCENE_METADATA_LABELS[key]}:")
            for value in values:
                cleaned = book_text._clean_text(value)
                if cleaned:
                    lines.append(f"- {cleaned}")
            lines.append("")
    conflict = metadata.get("conflict")
    if conflict:
        lines.extend(["Conflict:", f"- {book_text._clean_text(conflict)}", ""])
    summary = metadata.get("summary")
    if summary:
        lines.extend(["Summary:", f"- {book_text._clean_text(summary)}", ""])
    lines.extend(["---", "", body])
    return "\n".join(lines).strip()


def build_workspace_chapter_text_from_scenes(scenes: list[NovelScene | dict[str, Any]]) -> str:
    compiled_blocks: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        if isinstance(scene, dict):
            title = str(scene.get("title") or "").strip()
            body = str(scene.get("body") or "")
            scene_payload = {
                "title": title,
                "description": scene.get("description"),
                "body": body,
                "metadata": scene.get("metadata") or scene.get("scene_metadata") or {},
            }
        else:
            title = str(getattr(scene, "title", "") or "").strip()
            body = str(getattr(scene, "body", "") or "")
            scene_payload = {
                "title": title,
                "description": getattr(scene, "description", None),
                "body": body,
                "metadata": getattr(scene, "scene_metadata", None) or {},
            }
        compiled_block = build_scene_chapter_import_text(
            scene_payload,
            scene_number=index,
            include_metadata=True,
        )
        if compiled_block:
            compiled_blocks.append(compiled_block)
    return "\n\n***\n\n".join(compiled_blocks).strip()


def chapter_body_needs_scene_workspace_fallback(
    text: str | None,
    *,
    chapter_number: int,
    chapter_title: str | None = None,
) -> bool:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return True

    token = re.sub(r"[^a-z0-9]+", "", normalized.lower())
    if not token:
        return True

    placeholder_tokens = {
        str(chapter_number),
        f"chapter{chapter_number}",
    }
    if chapter_title:
        title_token = re.sub(r"[^a-z0-9]+", "", chapter_title.lower())
        if title_token:
            placeholder_tokens.add(title_token)

    roman_value = _romanize_chapter_number(chapter_number)
    if roman_value:
        placeholder_tokens.add(roman_value.lower())

    return _count_words(normalized) <= 3 and token in placeholder_tokens


def strip_scene_metadata_from_manuscript_text(text: str) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    output: list[str] = []

    def last_non_empty_output() -> str:
        for value in reversed(output):
            if value.strip():
                return value.strip()
        return ""

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if re.match(r"^#{1,3}\s+Scene\b", stripped, re.IGNORECASE):
            if any(line.strip() for line in output) and last_non_empty_output() != "***":
                output.extend(["", "***", ""])
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            consumed_metadata = False
            while index < len(lines):
                current = lines[index].strip()
                if current == "---":
                    index += 1
                    if consumed_metadata:
                        break
                    continue
                label_match = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", current)
                if label_match and _scene_metadata_key(label_match.group(1)) is not None:
                    consumed_metadata = True
                    index += 1
                    continue
                if consumed_metadata and (not current or re.match(r"^[-*]\s+.+$", current)):
                    index += 1
                    continue
                break
            continue
        if normalization.SCENE_BREAK_LINE_RE.match(stripped):
            if any(line.strip() for line in output) and last_non_empty_output() != "***":
                output.extend(["", "***", ""])
            index += 1
            continue
        output.append(lines[index].rstrip())
        index += 1
    cleaned = "\n".join(output)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _romanize_chapter_number(chapter_number: int) -> str:
    if chapter_number <= 0 or chapter_number >= 4000:
        return ""
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    remaining = chapter_number
    parts: list[str] = []
    for value, symbol in numerals:
        while remaining >= value:
            parts.append(symbol)
            remaining -= value
    return "".join(parts)


def _split_scene_blocks(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.rstrip()
        if normalization.SCENE_BREAK_LINE_RE.match(line):
            if current and any(part.strip() for part in current):
                blocks.append("\n".join(current).strip())
                current = []
            continue
        heading_match = normalization.SCENE_HEADING_LINE_RE.match(line)
        if heading_match:
            if current and any(part.strip() for part in current):
                blocks.append("\n".join(current).strip())
                current = []
            if heading_match.group(1):
                current.append(line)
            continue
        current.append(line)
    if current and any(part.strip() for part in current):
        blocks.append("\n".join(current).strip())
    return blocks or [normalized]


def extract_novel_scene_candidates(
    *,
    text: str,
    chapter_number: int | None,
    source: str = "extracted",
) -> list[dict[str, Any]]:
    blocks = _split_scene_blocks(text)
    scenes: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines()]
        title = _scene_display_title(block, index)
        description = ""
        remaining_lines = lines
        if remaining_lines:
            first_line = " ".join(remaining_lines[0].split()).strip()
            heading_match = normalization.SCENE_HEADING_LINE_RE.match(first_line)
            if heading_match and heading_match.group(1):
                title = heading_match.group(1).strip() or title
                remaining_lines = remaining_lines[1:]
            elif len(first_line) <= 80:
                title = first_line or title
                remaining_lines = remaining_lines[1:]
        preview = " ".join(
            " ".join(line.split()) for line in remaining_lines if line.strip()
        ).strip()
        if preview:
            description = preview[:180]
            if len(preview) > 180:
                description = description.rstrip() + "..."
        body = "\n".join(lines).strip()
        scene_metadata = extract_scene_metadata(body, description=description or None)
        scenes.append(
            {
                "chapter_number": chapter_number,
                "title": title,
                "description": description or None,
                "body": body,
                "html_body": manuscript.manuscript_text_to_html(body),
                "metadata": scene_metadata,
                "status": "assigned" if chapter_number else "unassigned",
                "sort_order": index,
                "source": source,
                "origin_chapter_number": chapter_number,
                "path": build_novel_scene_path(
                    chapter_number=chapter_number, sort_order=index, title=title
                ),
            }
        )
    return scenes
