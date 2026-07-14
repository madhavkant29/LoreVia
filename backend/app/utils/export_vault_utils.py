from __future__ import annotations

import io
import zipfile

from app.utils.export_common_utils import _clean_line, _safe_name, export_font_notice
from app.utils.export_manuscript_formatting_utils import _manuscript_front_matter
from app.utils.index_format import format_index


def manuscript_vault_zip(
    *,
    title: str,
    chapters: list[dict],
    scenes: list[dict],
    notes: list[dict],
    front_matter: dict | None = None,
    font_family: str | None = None,
    index_format: str = "arabic",
) -> bytes:
    front = _manuscript_front_matter(title, chapters, front_matter)
    root = _safe_name(front["title"] or title) or "LoreVia-Manuscript"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/_meta/FONT-NOTICE.txt", export_font_notice(font_family))
        archive.writestr(
            f"{root}/_meta/manuscript-front-matter.md",
            "\n".join(
                [
                    f"# {front['title']}",
                    "",
                    f"- Author: {front['display_author'] or '-'}",
                    f"- Contact email: {front['contact_email'] or '-'}",
                    f"- Contact phone: {front['contact_phone'] or '-'}",
                    f"- Approximate word count: {front['word_count']}",
                    "",
                ]
            ),
        )
        for chapter in chapters:
            chapter_number = int(chapter.get("number") or 0)
            fmt_num = format_index(chapter_number, index_format)
            chapter_title = _clean_line(chapter.get("title")) or f"Chapter {fmt_num}"
            archive.writestr(
                f"{root}/chapters/Chapter {chapter_number:02d}.md",
                f"# {chapter_title}\n\n{str(chapter.get('text') or '').strip()}\n",
            )
        for scene in scenes:
            scene_title = _clean_line(scene.get("title")) or "Scene"
            scene_description = str(scene.get("description") or "").strip()
            scene_metadata = (
                scene.get("metadata") if isinstance(scene.get("metadata"), dict) else {}
            )
            metadata_lines: list[str] = []
            for key, value in scene_metadata.items():
                label = str(key).replace("_", " ").title()
                if isinstance(value, list):
                    metadata_lines.append(f"{label}:")
                    metadata_lines.extend(
                        f"- {_clean_line(item)}" for item in value if _clean_line(item)
                    )
                elif _clean_line(value):
                    metadata_lines.append(f"{label}: {_clean_line(value)}")
            chapter_number = scene.get("chapter_number")
            folder = (
                f"chapter-{int(chapter_number):02d}"
                if isinstance(chapter_number, int) and chapter_number > 0
                else "unassigned"
            )
            archive.writestr(
                f"{root}/scenes/{folder}/{_safe_name(scene_title) or 'scene'}.md",
                "\n".join(
                    [
                        f"# {scene_title}",
                        "",
                        f"Description: {scene_description or '-'}",
                        f"Status: {scene.get('status') or 'unassigned'}",
                        f"Linked Chapter: {chapter_number or 'undecided'}",
                        "",
                        *metadata_lines,
                        "" if metadata_lines else "",
                        "---",
                        "",
                        str(scene.get("body") or "").strip(),
                        "",
                    ]
                ),
            )
        for note in notes:
            raw_path = str(note.get("path") or "").strip() or "Untitled.md"
            note_path = raw_path if raw_path.startswith("notes/") else f"notes/{raw_path}"
            archive.writestr(f"{root}/{note_path}", str(note.get("content") or ""))
    return buffer.getvalue()
