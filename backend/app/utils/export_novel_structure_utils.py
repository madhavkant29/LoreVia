from __future__ import annotations

from typing import Any

from app.utils.books.serialization import build_blank_cover_image
from app.utils.export_common_utils import _clean_line, _normalize_unicode_for_export
from app.utils.export_manuscript_formatting_utils import _manuscript_front_matter

NOVEL_IMAGE_PLACEMENTS = {"end", "inline", "plates"}


def normalize_novel_image_placement(value: object | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in NOVEL_IMAGE_PLACEMENTS else "end"


def _clean_export_body(value: object | None) -> str:
    return _normalize_unicode_for_export(str(value or "").strip())


def _novel_front_matter(
    title: str,
    chapters: list[dict],
    front_matter: dict | None,
    preface: str | None,
    novel_front_matter: dict | None = None,
    epub_metadata: dict | None = None,
) -> dict[str, Any]:
    front = _manuscript_front_matter(title, chapters, front_matter)
    novel_matter = novel_front_matter if isinstance(novel_front_matter, dict) else {}
    metadata = epub_metadata if isinstance(epub_metadata, dict) else {}
    front["preface"] = _clean_export_body(preface)
    front["dedication"] = _clean_export_body(novel_matter.get("dedication"))
    front["acknowledgements"] = _clean_export_body(
        novel_matter.get("acknowledgements") or novel_matter.get("acknowledgments")
    )
    front["copyright_page"] = _clean_export_body(novel_matter.get("copyright_page"))
    front["about_author"] = _clean_export_body(novel_matter.get("about_author"))
    front["series_book_list"] = _clean_export_body(novel_matter.get("series_book_list"))
    front["publisher"] = _clean_line(metadata.get("publisher"))
    front["language"] = _clean_line(metadata.get("language")) or "en"
    front["isbn"] = _clean_line(metadata.get("isbn"))
    front["description"] = _clean_export_body(metadata.get("description"))
    front["series_name"] = _clean_line(metadata.get("series_name"))
    front["series_number"] = _clean_line(metadata.get("series_number"))
    return front


def _image_extension(content_type: object | None, fallback: str = "png") -> str:
    normalized = str(content_type or "").split(";")[0].strip().lower()
    if normalized == "image/jpeg":
        return "jpg"
    if normalized == "image/png":
        return "png"
    if normalized == "image/webp":
        return "webp"
    if normalized == "image/gif":
        return "gif"
    return fallback


def _cover_image_payload(
    title: str, author: str | None, cover_image: dict[str, Any] | None
) -> dict[str, Any]:
    if isinstance(cover_image, dict) and cover_image.get("raw"):
        return {
            "raw": cover_image["raw"],
            "content_type": cover_image.get("content_type") or "image/png",
        }
    raw, content_type = build_blank_cover_image(title, author)
    return {"raw": raw, "content_type": content_type}


def _chapter_media_items(chapter: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in chapter.get("media") or [] if isinstance(item, dict) and item.get("raw")
    ]


def _front_matter_sections(front: dict[str, Any]) -> list[dict[str, str]]:
    sections = [
        {
            "key": "copyright_page",
            "title": "Copyright",
            "text": str(front.get("copyright_page") or ""),
        },
        {"key": "dedication", "title": "Dedication", "text": str(front.get("dedication") or "")},
        {"key": "preface", "title": "Preface", "text": str(front.get("preface") or "")},
    ]
    return [section for section in sections if section["text"].strip()]


def _back_matter_sections(front: dict[str, Any]) -> list[dict[str, str]]:
    sections = [
        {
            "key": "acknowledgements",
            "title": "Acknowledgements",
            "text": str(front.get("acknowledgements") or ""),
        },
        {
            "key": "about_author",
            "title": "About the Author",
            "text": str(front.get("about_author") or ""),
        },
        {
            "key": "series_book_list",
            "title": "Also by the Author",
            "text": str(front.get("series_book_list") or ""),
        },
    ]
    return [section for section in sections if section["text"].strip()]


def _chapter_inline_segments(
    chapter: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = str(chapter.get("text") or "")
    media_items = _chapter_media_items(chapter)
    matches: list[tuple[int, int, dict[str, Any]]] = []
    used_ids: set[int] = set()
    for media in media_items:
        marker = str(media.get("marker") or "").strip()
        if not marker:
            continue
        position = text.find(marker)
        if position < 0:
            continue
        matches.append((position, position + len(marker), media))
        used_ids.add(id(media))
    matches.sort(key=lambda item: item[0])
    segments: list[dict[str, Any]] = []
    cursor = 0
    for start, end, media in matches:
        if start < cursor:
            continue
        if start > cursor:
            segments.append({"kind": "text", "text": text[cursor:start]})
        segments.append({"kind": "image", "media": media})
        cursor = end
    if cursor < len(text):
        segments.append({"kind": "text", "text": text[cursor:]})
    if not segments:
        segments.append({"kind": "text", "text": text})
    unmatched = [media for media in media_items if id(media) not in used_ids]
    return segments, unmatched
