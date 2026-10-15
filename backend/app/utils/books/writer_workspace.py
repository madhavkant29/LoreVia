"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.models.book import Book
from app.schemas.books import BookProcessingOut
from app.utils.advisor_beta_reader_report_utils import normalize_ai_beta_reader_state
from app.utils.books import normalization
from app.utils.books.processing import (
    _normalize_internal_processing_state,
    _normalize_processing_state,
    normalize_reprocess_metadata,
)
from app.utils.books.workspace_constants import (
    DEFAULT_WRITER_WORKSPACE,
    DEFAULT_WRITING_TEMPLATES,
)
from app.utils.first_impression_utils import normalize_first_impression_state
from app.utils.index_format import INDEX_FORMATS

if TYPE_CHECKING:
    pass


def _derive_front_matter_defaults(
    raw: dict | None = None, *, title: str = "", author: str = ""
) -> dict[str, Any]:
    payload = json.loads(json.dumps(DEFAULT_WRITER_WORKSPACE["manuscript_front_matter"]))
    source = raw if isinstance(raw, dict) else {}

    payload["author_name"] = " ".join(
        str(source.get("author_name") or author or "").split()
    ).strip()
    payload["pen_name"] = " ".join(str(source.get("pen_name") or "").split()).strip()
    payload["contact_email"] = " ".join(str(source.get("contact_email") or "").split()).strip()
    payload["contact_phone"] = " ".join(str(source.get("contact_phone") or "").split()).strip()
    payload["contact_address"] = str(source.get("contact_address") or "").strip()
    payload["title"] = " ".join(str(source.get("title") or title or "").split()).strip()
    payload["subtitle"] = " ".join(str(source.get("subtitle") or "").split()).strip()

    header_last_name = " ".join(str(source.get("header_last_name") or "").split()).strip()
    if not header_last_name:
        fallback_name = payload["pen_name"] or payload["author_name"]
        header_last_name = fallback_name.split()[-1] if fallback_name else ""
    payload["header_last_name"] = header_last_name
    payload["header_title"] = " ".join(
        str(source.get("header_title") or payload["title"] or "").split()
    ).strip()

    override = source.get("approximate_word_count_override")
    payload["approximate_word_count_override"] = (
        int(override) if isinstance(override, (int, float)) and int(override) > 0 else None
    )

    for key in ("dedication", "acknowledgments", "epigraph", "prologue"):
        payload[key] = str(source.get(key) or "").strip()
    for key in (
        "include_dedication",
        "include_acknowledgments",
        "include_epigraph",
        "include_prologue",
    ):
        payload[key] = bool(source.get(key, False))

    return payload


def _normalize_revision_board(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    items: list[dict[str, Any]] = []
    seen_item_ids: set[str] = set()
    for item in source.get("items") or []:
        if not isinstance(item, dict):
            continue
        item_id = " ".join(str(item.get("item_id") or "").split()).strip()
        if not item_id or item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        status = " ".join(str(item.get("status") or "pending").split()).strip().lower() or "pending"
        if status not in normalization.REVISION_ITEM_STATUSES:
            status = "pending"
        assigned_version_id = (
            " ".join(str(item.get("assigned_version_id") or "").split()).strip() or None
        )
        task_id = " ".join(str(item.get("task_id") or "").split()).strip() or None
        updated_at = " ".join(str(item.get("updated_at") or "").split()).strip() or None
        items.append(
            {
                "item_id": item_id,
                "status": status,
                "assigned_version_id": assigned_version_id,
                "task_id": task_id,
                "updated_at": updated_at,
                "decision": " ".join(str(item.get("decision") or "").split()).strip() or None,
                "action": " ".join(str(item.get("action") or "").split()).strip() or None,
                "reason": " ".join(str(item.get("reason") or "").split()).strip() or None,
                "source_content_versions": {
                    str(key): int(value)
                    for key, value in (item.get("source_content_versions") or {}).items()
                    if str(key).isdigit() and isinstance(value, (int, float))
                },
                "finding_snapshot": item.get("finding_snapshot")
                if isinstance(item.get("finding_snapshot"), dict)
                else None,
            }
        )
    return {
        "items": items,
        "last_generated_at": " ".join(str(source.get("last_generated_at") or "").split()).strip()
        or None,
    }


def _normalize_activation_state(raw: object) -> dict[str, str | None]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "completed_at": " ".join(str(source.get("completed_at") or "").split()).strip() or None,
        "completion_action": " ".join(str(source.get("completion_action") or "").split()).strip()
        or None,
        "completed_finding_id": " ".join(
            str(source.get("completed_finding_id") or "").split()
        ).strip()
        or None,
    }


def _normalize_revision_recent_edits(raw: object) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        edit_id = " ".join(str(item.get("id") or "").split()).strip() or str(uuid.uuid4())
        kind = " ".join(str(item.get("kind") or "").split()).strip().lower() or "chapter"
        if kind not in {"chapter", "scene", "scene_deleted", "scene_reordered"}:
            kind = "chapter"
        chapter_number = item.get("chapter_number")
        edits.append(
            {
                "id": edit_id,
                "kind": kind,
                "chapter_number": int(chapter_number)
                if isinstance(chapter_number, (int, float)) and int(chapter_number) > 0
                else None,
                "scene_id": " ".join(str(item.get("scene_id") or "").split()).strip() or None,
                "scene_title": " ".join(str(item.get("scene_title") or "").split()).strip() or None,
                "unit_label": " ".join(str(item.get("unit_label") or "").split()).strip() or None,
                "before_text": str(item.get("before_text") or "").strip(),
                "after_text": str(item.get("after_text") or "").strip(),
                "updated_at": " ".join(str(item.get("updated_at") or "").split()).strip() or None,
                "source_version_id": " ".join(
                    str(item.get("source_version_id") or "").split()
                ).strip()
                or None,
            }
        )
    edits.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return edits[: normalization.MAX_REVISION_RECENT_EDITS]


def _append_recent_revision_edit(
    book: Book,
    *,
    kind: str,
    chapter_number: int | None,
    before_text: str,
    after_text: str,
    scene_id: str | None = None,
    scene_title: str | None = None,
    source_version_id: str | None = None,
) -> None:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    existing = _normalize_revision_recent_edits(
        (book.writer_workspace or {}).get("revision_recent_edits")
        if isinstance(book.writer_workspace, dict)
        else []
    )
    unit_label = (
        f'Scene "{scene_title}"'
        if kind.startswith("scene") and scene_title
        else normalization.story_unit_label(book, chapter_number, fallback="manuscript change")
    )
    next_edit = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "chapter_number": chapter_number,
        "scene_id": scene_id,
        "scene_title": scene_title,
        "unit_label": unit_label,
        "before_text": (before_text or "").strip(),
        "after_text": (after_text or "").strip(),
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_version_id": source_version_id,
    }
    deduped = [
        item
        for item in existing
        if not (
            item.get("kind") == next_edit["kind"]
            and item.get("chapter_number") == next_edit["chapter_number"]
            and item.get("scene_id") == next_edit["scene_id"]
        )
    ]
    workspace["revision_recent_edits"] = [next_edit, *deduped][
        : normalization.MAX_REVISION_RECENT_EDITS
    ]
    book.writer_workspace = workspace


def touch_public_book_updated_at(book: Book, *, changed_at: datetime | None = None) -> None:
    book.public_updated_at = changed_at or datetime.now(UTC)


def normalize_writer_workspace(raw: dict | None) -> dict:
    payload = json.loads(json.dumps(DEFAULT_WRITER_WORKSPACE))
    source = raw if isinstance(raw, dict) else {}

    goals = source.get("word_count_goals")
    if isinstance(goals, dict):
        for key in ("chapter_target", "book_target", "session_target"):
            value = goals.get(key)
            payload["word_count_goals"][key] = (
                int(value) if isinstance(value, (int, float)) and int(value) > 0 else None
            )

    calendar_items: list[dict[str, Any]] = []
    for item in source.get("goal_calendar") or []:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split()).strip()
        due_date = " ".join(str(item.get("due_date") or "").split()).strip()
        if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
            continue
        quota_value = item.get("quota_value")
        quota_unit = " ".join(str(item.get("quota_unit") or "").split()).strip() or None
        calendar_items.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "title": title,
                "due_date": due_date,
                "quota_value": int(quota_value)
                if isinstance(quota_value, (int, float)) and int(quota_value) > 0
                else None,
                "quota_unit": quota_unit,
                "completed": bool(item.get("completed", False)),
            }
        )
    payload["goal_calendar"] = calendar_items

    cards: list[dict[str, Any]] = []
    for card in source.get("corkboard_cards") or []:
        if not isinstance(card, dict):
            continue
        title = " ".join(str(card.get("title") or "").split()).strip()
        if not title:
            continue
        chapter_number = card.get("chapter_number")
        cards.append(
            {
                "id": str(card.get("id") or uuid.uuid4()),
                "title": title,
                "description": str(card.get("description") or "").strip(),
                "status": " ".join(str(card.get("status") or "planned").split()).strip()
                or "planned",
                "lane": " ".join(str(card.get("lane") or "ideas").split()).strip() or "ideas",
                "chapter_number": int(chapter_number)
                if isinstance(chapter_number, (int, float)) and int(chapter_number) > 0
                else None,
                "template_id": " ".join(str(card.get("template_id") or "").split()).strip() or None,
            }
        )
    payload["corkboard_cards"] = cards

    templates: list[dict[str, str]] = []
    for template in source.get("templates") or DEFAULT_WRITING_TEMPLATES:
        if not isinstance(template, dict):
            continue
        template_id = " ".join(str(template.get("id") or "").split()).strip()
        kind = " ".join(str(template.get("kind") or "").split()).strip()
        title = " ".join(str(template.get("title") or "").split()).strip()
        content = str(template.get("content") or "").strip()
        if not template_id or not kind or not title or not content:
            continue
        templates.append(
            {
                "id": template_id,
                "kind": kind,
                "title": title,
                "description": " ".join(str(template.get("description") or "").split()).strip(),
                "content": content,
            }
        )
    payload["templates"] = templates or json.loads(json.dumps(DEFAULT_WRITING_TEMPLATES))

    publishing = source.get("publishing")
    if isinstance(publishing, dict):
        payload["publishing"] = {
            "active_preset": " ".join(
                str(publishing.get("active_preset") or "standard_manuscript").split()
            ).strip()
            or "standard_manuscript",
            "trim_size": " ".join(str(publishing.get("trim_size") or "6x9").split()).strip()
            or "6x9",
            "include_title_page": bool(publishing.get("include_title_page", True)),
            "mirror_margins": bool(publishing.get("mirror_margins", True)),
        }

    editor_preferences = source.get("editor_preferences")
    if isinstance(editor_preferences, dict):
        payload["editor_preferences"] = {
            "font_family": " ".join(
                str(editor_preferences.get("font_family") or "Times New Roman").split()
            ).strip()
            or "Times New Roman",
            "font_size": int(editor_preferences.get("font_size"))
            if isinstance(editor_preferences.get("font_size"), (int, float))
            and 8 <= int(editor_preferences.get("font_size")) <= 36
            else 12,
            "line_height": float(editor_preferences.get("line_height"))
            if isinstance(editor_preferences.get("line_height"), (int, float))
            and 1 <= float(editor_preferences.get("line_height")) <= 3
            else 1.8,
            "manuscript_width": " ".join(
                str(editor_preferences.get("manuscript_width") or "standard").split()
            ).strip()
            or "standard",
            "show_page_guides": bool(editor_preferences.get("show_page_guides", True)),
            "focus_mode": bool(editor_preferences.get("focus_mode", False)),
            "default_scene_separator": " ".join(
                str(editor_preferences.get("default_scene_separator") or "asterisks").split()
            ).strip()
            or "asterisks",
        }

    reading_themes = source.get("reading_themes")
    if isinstance(reading_themes, dict):
        payload["reading_themes"] = {
            "active_theme": " ".join(
                str(reading_themes.get("active_theme") or "light").split()
            ).strip()
            or "light",
            "allow_dark_mode": bool(reading_themes.get("allow_dark_mode", True)),
        }

    typewriter_mode = source.get("typewriter_mode")
    if isinstance(typewriter_mode, dict):
        payload["typewriter_mode"] = {
            "enabled": bool(typewriter_mode.get("enabled", False)),
            "center_offset_px": int(typewriter_mode.get("center_offset_px"))
            if isinstance(typewriter_mode.get("center_offset_px"), (int, float))
            else 160,
        }

    manuscript_layout = source.get("manuscript_layout")
    if isinstance(manuscript_layout, dict):
        payload["manuscript_layout"] = {
            "margins": " ".join(str(manuscript_layout.get("margins") or "standard").split()).strip()
            or "standard",
            "page_size": " ".join(
                str(manuscript_layout.get("page_size") or "letter").split()
            ).strip()
            or "letter",
            "orientation": " ".join(
                str(manuscript_layout.get("orientation") or "portrait").split()
            ).strip()
            or "portrait",
            "show_headers": bool(manuscript_layout.get("show_headers", True)),
            "show_footers": bool(manuscript_layout.get("show_footers", True)),
            "page_numbering": bool(manuscript_layout.get("page_numbering", True)),
            "different_first_page": bool(manuscript_layout.get("different_first_page", True)),
        }

    structure_tree = source.get("structure_tree")
    if isinstance(structure_tree, list):
        payload["structure_tree"] = json.loads(json.dumps(structure_tree))

    payload["manuscript_front_matter"] = _derive_front_matter_defaults(
        source.get("manuscript_front_matter")
    )
    payload["novel_preface"] = str(source.get("novel_preface") or "").strip()
    novel_front_matter = source.get("novel_front_matter")
    if isinstance(novel_front_matter, dict):
        payload["novel_front_matter"] = {
            "dedication": str(novel_front_matter.get("dedication") or "").strip(),
            "acknowledgements": str(
                novel_front_matter.get("acknowledgements")
                or novel_front_matter.get("acknowledgments")
                or ""
            ).strip(),
            "copyright_page": str(novel_front_matter.get("copyright_page") or "").strip(),
            "about_author": str(novel_front_matter.get("about_author") or "").strip(),
            "series_book_list": str(novel_front_matter.get("series_book_list") or "").strip(),
        }
    novel_epub_metadata = source.get("novel_epub_metadata")
    if isinstance(novel_epub_metadata, dict):
        language = (
            " ".join(str(novel_epub_metadata.get("language") or "en").split()).strip() or "en"
        )
        payload["novel_epub_metadata"] = {
            "publisher": str(novel_epub_metadata.get("publisher") or "").strip(),
            "language": language[:24],
            "isbn": str(novel_epub_metadata.get("isbn") or "").strip(),
            "description": str(novel_epub_metadata.get("description") or "").strip(),
            "series_name": str(novel_epub_metadata.get("series_name") or "").strip(),
            "series_number": str(novel_epub_metadata.get("series_number") or "").strip(),
        }
    payload["revision_board"] = _normalize_revision_board(source.get("revision_board"))
    payload["activation"] = _normalize_activation_state(source.get("activation"))
    payload["revision_recent_edits"] = _normalize_revision_recent_edits(
        source.get("revision_recent_edits") or []
    )
    revision_rounds: list[dict[str, Any]] = []
    for item in source.get("revision_rounds") or []:
        if not isinstance(item, dict) or not item.get("id") or not item.get("created_at"):
            continue
        chapters = [
            chapter for chapter in (item.get("chapters") or []) if isinstance(chapter, dict)
        ]
        revision_rounds.append(
            {
                "id": str(item["id"]),
                "label": " ".join(str(item.get("label") or "Revision round").split())[:120],
                "note": str(item.get("note") or "").strip()[:1000] or None,
                "created_at": str(item["created_at"]),
                "chapters": chapters,
                "summary": item.get("summary") if isinstance(item.get("summary"), dict) else {},
            }
        )
    payload["revision_rounds"] = revision_rounds[-20:]
    payload["ai_beta_reader"] = normalize_ai_beta_reader_state(source.get("ai_beta_reader"))
    payload["first_impression"] = normalize_first_impression_state(source.get("first_impression"))
    payload["processing"] = (
        _normalize_internal_processing_state(source.get("processing"))
        if isinstance(source.get("processing"), dict)
        else None
    )
    payload["reprocess"] = normalize_reprocess_metadata(
        source.get("reprocess") if isinstance(source.get("reprocess"), dict) else None
    )

    index_fmt = source.get("index_format")
    if isinstance(index_fmt, str) and index_fmt in INDEX_FORMATS:
        payload["index_format"] = index_fmt

    fingerprint = " ".join(str(source.get("source_fingerprint") or "").split()).strip()
    payload["source_fingerprint"] = fingerprint[:128] or None

    return payload


def build_writer_workspace_payload(book: Book) -> dict:
    payload = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    payload["processing"] = (
        _normalize_processing_state(payload.get("processing"))
        if isinstance(payload.get("processing"), dict)
        else None
    )
    payload["manuscript_front_matter"] = _derive_front_matter_defaults(
        payload.get("manuscript_front_matter"),
        title=book.title or "",
        author=book.author or "",
    )
    return payload


def build_book_processing_payload(book: Book) -> dict[str, Any] | None:
    workspace = normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    processing = workspace.get("processing")
    if not isinstance(processing, dict) or not processing:
        return None
    return BookProcessingOut.model_validate(_normalize_processing_state(processing)).model_dump(
        mode="json"
    )
