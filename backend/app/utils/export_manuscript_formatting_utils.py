from __future__ import annotations

import re
from typing import Any

from app.utils.index_format import format_index


def _clean_line(value: object | None) -> str:
    return " ".join(str(value or "").split()).strip()


def _manuscript_word_count(chapters: list[dict]) -> int:
    return sum(
        len(re.findall(r"[A-Za-z0-9']+", str(chapter.get("text") or ""))) for chapter in chapters
    )


def _manuscript_front_matter(
    title: str, chapters: list[dict], front_matter: dict | None
) -> dict[str, Any]:
    source = front_matter if isinstance(front_matter, dict) else {}
    resolved_title = _clean_line(source.get("title")) or _clean_line(title) or "LoreVia Manuscript"
    author_name = _clean_line(source.get("author_name"))
    pen_name = _clean_line(source.get("pen_name"))
    display_author = pen_name or author_name
    header_title = _clean_line(source.get("header_title")) or resolved_title
    header_last_name = _clean_line(source.get("header_last_name")) or (
        display_author.split()[-1] if display_author else ""
    )
    override = source.get("approximate_word_count_override")
    word_count = (
        int(override)
        if isinstance(override, (int, float)) and int(override) > 0
        else _manuscript_word_count(chapters)
    )
    return {
        "author_name": author_name,
        "pen_name": pen_name,
        "display_author": display_author,
        "contact_email": _clean_line(source.get("contact_email")),
        "contact_phone": _clean_line(source.get("contact_phone")),
        "contact_address": str(source.get("contact_address") or "").strip(),
        "title": resolved_title,
        "subtitle": _clean_line(source.get("subtitle")),
        "header_last_name": header_last_name,
        "header_title": header_title,
        "word_count": word_count,
        "dedication": str(source.get("dedication") or "").strip(),
        "acknowledgments": str(source.get("acknowledgments") or "").strip(),
        "epigraph": str(source.get("epigraph") or "").strip(),
        "prologue": str(source.get("prologue") or "").strip(),
        "include_dedication": bool(source.get("include_dedication", False)),
        "include_acknowledgments": bool(source.get("include_acknowledgments", False)),
        "include_epigraph": bool(source.get("include_epigraph", False)),
        "include_prologue": bool(source.get("include_prologue", False)),
    }


def _approx_word_count_label(count: int) -> str:
    if count <= 0:
        return "Approx. 0 words"
    return f"Approx. {max(100, int(round(count / 100.0) * 100)):,} words"


SCENE_BREAK_PATTERN = re.compile(r"^(?:(?:\*\s*){3,}|#{1,3}|(?:-|\u2013|\u2014){3,}|[~]{3,})$")


def _normalize_manuscript_block(block: str) -> str:
    return "\n".join(
        line.rstrip() for line in block.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ).strip()


def _is_scene_break_block(block: str) -> bool:
    normalized = _normalize_manuscript_block(block)
    if not normalized:
        return False
    return bool(
        SCENE_BREAK_PATTERN.fullmatch(normalized.replace("\n", " ").replace("\t", " ").strip())
    )


def _chapter_body_blocks(text: str) -> list[tuple[str, str]]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks: list[tuple[str, str]] = []
    for raw_block in re.split(r"\n{2,}", normalized):
        block = _normalize_manuscript_block(raw_block)
        if not block:
            continue
        if _is_scene_break_block(block):
            blocks.append(("scene_break", "***"))
        else:
            blocks.append(("paragraph", block))
    return blocks


def _is_special_chapter_heading(title: object | None) -> bool:
    cleaned = _clean_line(title).lower()
    return bool(re.match(r"^(prologue|epilogue)\b", cleaned))


def _chapter_heading_lines(
    chapter: dict[str, Any], index_format: str = "arabic"
) -> tuple[str, str | None]:
    chapter_number = chapter.get("number")
    chapter_title = _clean_line(chapter.get("title"))
    fmt_num = format_index(chapter_number, index_format) if chapter_number is not None else ""
    if _is_special_chapter_heading(chapter_title):
        return chapter_title or f"Chapter {fmt_num}", None
    default_heading = f"Chapter {fmt_num}"
    if chapter_title and chapter_title.lower() != default_heading.lower():
        return default_heading, chapter_title
    return default_heading, None


def _manuscript_toc_label(chapter: dict[str, Any], index_format: str = "arabic") -> str:
    chapter_heading, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
    return f"{chapter_heading}: {chapter_subtitle}" if chapter_subtitle else chapter_heading


def _scene_heading_lines(
    scene: dict[str, Any], index: int, index_format: str = "arabic"
) -> tuple[str, str | None]:
    chapter_number = scene.get("chapter_number")
    fmt_num = (
        format_index(chapter_number, index_format)
        if isinstance(chapter_number, int) and chapter_number > 0
        else ""
    )
    chapter_suffix = f" (Chapter {fmt_num})" if fmt_num else ""
    scene_title = _clean_line(scene.get("title")) or f"Scene {index}"
    return f"Scene #{index}{chapter_suffix}", scene_title


def _manuscript_end_marker() -> str:
    return "THE END"
