from __future__ import annotations

from html import escape
from typing import Any

from app.utils.books.manuscript import clean_manuscript_html
from app.utils.export_common_utils import (
    _clean_line,
    _export_font_epub_stack,
    _safe_name,
)
from app.utils.export_manuscript_formatting_utils import (
    _approx_word_count_label,
    _chapter_body_blocks,
    _chapter_heading_lines,
    _manuscript_end_marker,
    _manuscript_front_matter,
    _manuscript_toc_label,
    _scene_heading_lines,
)
from app.utils.export_preset_utils import manuscript_export_preset


def manuscript_epub(
    *,
    title: str,
    chapters: list[dict],
    preset: str = "standard_manuscript",
    font_family: str | None = None,
) -> bytes:
    import os
    import tempfile

    from ebooklib import epub

    book = epub.EpubBook()
    safe_title = _clean_line(title) or "LoreVia Manuscript Export"
    export_preset = manuscript_export_preset(preset)
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
            f"body {{ font-family: {_export_font_epub_stack(font_family)}; line-height: 1.6; margin: 5%; }} "
            "h1, h2 { page-break-after: avoid; } "
            ".preset-note { font-size: 0.85em; color: #555; }"
        ).encode(),
    )
    book.add_item(stylesheet)

    for chapter in chapters:
        chapter_number = chapter.get("number")
        chapter_title = _clean_line(chapter.get("title")) or f"Chapter {chapter_number}"
        chapter_html = (
            clean_manuscript_html(chapter.get("html"))
            or f"<p>{_clean_line(chapter.get('text'))}</p>"
        )
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


def manuscript_epub_compiled(
    *,
    title: str,
    chapters: list[dict],
    scenes: list[dict] | None = None,
    preset: str = "standard_manuscript",
    front_matter: dict | None = None,
    font_family: str | None = None,
    include_toc: bool = False,
    index_format: str = "arabic",
) -> bytes:
    import os
    import tempfile

    from ebooklib import epub

    front = _manuscript_front_matter(title, chapters, front_matter)
    safe_title = _clean_line(front["title"]) or "LoreVia Manuscript Export"
    book = epub.EpubBook()
    book.set_identifier(_safe_name(safe_title) or "lorevia-manuscript")
    book.set_title(safe_title)
    book.set_language("en")
    if front["display_author"]:
        book.add_author(front["display_author"])

    stylesheet = epub.EpubItem(
        uid="style_nav",
        file_name="styles/main.css",
        media_type="text/css",
        content=(
            f"body {{ font-family: {_export_font_epub_stack(font_family)}; font-size: 12pt; line-height: 2; margin: 8%; }} "
            "h1, h2 { text-align: center; } "
            ".title-page, .end-marker { text-align: center; margin-top: 20%; } "
            ".toc-page { page-break-before: always; } "
            ".toc-page ol { line-height: 1.8; } "
            ".scene-break { text-align: center; letter-spacing: 0.2em; } "
            ".first-paragraph { text-indent: 0; } "
            "p { text-indent: 1.5em; margin: 0 0 1em; }"
        ).encode(),
    )
    book.add_item(stylesheet)

    spine: list[Any] = ["nav"]
    toc_entries: list[Any] = []

    def _body_html(text: str) -> str:
        parts: list[str] = []
        first_paragraph = True
        for kind, block in _chapter_body_blocks(text):
            if kind == "scene_break":
                parts.append("<p class='scene-break'>***</p>")
                first_paragraph = True
                continue
            css_class = "first-paragraph" if first_paragraph else ""
            safe_block = escape(block).replace("\n", "<br/>")
            parts.append(
                f"<p class='{css_class}'>{safe_block}</p>" if css_class else f"<p>{safe_block}</p>"
            )
            first_paragraph = False
        return "".join(parts) or "<p class='first-paragraph'></p>"

    title_page = epub.EpubHtml(title="Title Page", file_name="title-page.xhtml", lang="en")
    contact_lines = [
        line
        for line in [
            front["author_name"] or front["display_author"],
            front["contact_email"],
            front["contact_phone"],
            front["contact_address"],
        ]
        if line
    ]
    title_page.content = (
        "<section class='title-page'>"
        f"<h1>{escape(front['title'])}</h1>"
        f"{f'<h2>{escape(front["subtitle"])}</h2>' if front['subtitle'] else ''}"
        f"<p class='first-paragraph'>{escape(front['display_author'] or ' ')}</p>"
        f"{''.join(f'<p class="first-paragraph">{escape(str(line))}</p>' for line in contact_lines)}"
        f"<p class='first-paragraph'>{_approx_word_count_label(int(front['word_count']))}</p>"
        "</section>"
    )
    title_page.add_item(stylesheet)
    book.add_item(title_page)
    spine.append(title_page)
    toc_entries.append(title_page)

    if include_toc:
        toc_item = epub.EpubHtml(
            title="Table of Contents", file_name="table-of-contents.xhtml", lang="en"
        )
        toc_items = []
        for chapter in chapters:
            chapter_number = chapter.get("number")
            toc_items.append(
                f"<li><a href='chapter-{chapter_number}.xhtml'>{escape(_manuscript_toc_label(chapter, index_format))}</a></li>"
            )
        toc_item.content = (
            "<section class='toc-page'><h1>Table of Contents</h1><ol>"
            + "".join(toc_items)
            + "</ol></section>"
        )
        toc_item.add_item(stylesheet)
        book.add_item(toc_item)
        spine.append(toc_item)
        toc_entries.append(toc_item)

    optional_sections: list[tuple[str, str]] = []
    if front["include_dedication"] and front["dedication"]:
        optional_sections.append(("Dedication", front["dedication"]))
    if front["include_epigraph"] and front["epigraph"]:
        optional_sections.append(("Epigraph", front["epigraph"]))
    if front["include_acknowledgments"] and front["acknowledgments"]:
        optional_sections.append(("Acknowledgments", front["acknowledgments"]))
    if front["include_prologue"] and front["prologue"]:
        optional_sections.append(("Prologue", front["prologue"]))

    for index, (heading, content) in enumerate(optional_sections, start=1):
        item = epub.EpubHtml(title=heading, file_name=f"front-{index}.xhtml", lang="en")
        item.content = f"<h1>{escape(heading)}</h1><p class='first-paragraph'>{escape(content)}</p>"
        item.add_item(stylesheet)
        book.add_item(item)
        spine.append(item)
        toc_entries.append(item)

    for chapter in chapters:
        chapter_number = chapter.get("number")
        chapter_heading_text, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
        item = epub.EpubHtml(
            title=chapter_subtitle or chapter_heading_text,
            file_name=f"chapter-{chapter_number}.xhtml",
            lang="en",
        )
        item.content = (
            f"<h1>{escape(chapter_heading_text)}</h1>"
            f"{f'<h2>{escape(chapter_subtitle)}</h2>' if chapter_subtitle else ''}"
            f"{_body_html(str(chapter.get('text') or ''))}"
        )
        item.add_item(stylesheet)
        book.add_item(item)
        spine.append(item)
        toc_entries.append(item)

    for index, scene in enumerate(scenes or [], start=1):
        scene_heading_text, scene_subtitle = _scene_heading_lines(scene, index, index_format)
        item = epub.EpubHtml(
            title=scene_subtitle or scene_heading_text,
            file_name=f"scene-{index}.xhtml",
            lang="en",
        )
        item.content = (
            f"<h1>{escape(scene_heading_text)}</h1>"
            f"{f'<h2>{escape(scene_subtitle)}</h2>' if scene_subtitle else ''}"
            f"{_body_html(str(scene.get('body') or ''))}"
        )
        item.add_item(stylesheet)
        book.add_item(item)
        spine.append(item)
        toc_entries.append(item)

    ending = epub.EpubHtml(title="The End", file_name="the-end.xhtml", lang="en")
    ending.content = f"<section class='end-marker'><h1>{_manuscript_end_marker()}</h1></section>"
    ending.add_item(stylesheet)
    book.add_item(ending)
    spine.append(ending)
    toc_entries.append(ending)

    book.toc = tuple(toc_entries)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "manuscript.epub")
        epub.write_epub(target, book, {})
        with open(target, "rb") as handle:
            return handle.read()
