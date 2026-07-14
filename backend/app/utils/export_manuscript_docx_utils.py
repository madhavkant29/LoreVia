from __future__ import annotations

from typing import Any, cast

from app.utils.export_common_utils import _export_font_docx_name, _set_docx_core_properties
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


def manuscript_docx(
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
    from io import BytesIO

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    export_preset = manuscript_export_preset(preset)
    front = _manuscript_front_matter(title, chapters, front_matter)
    doc = Document()
    _set_docx_core_properties(
        doc,
        title=front["title"],
        author=front["display_author"] or "LoreVia",
        subject="Manuscript",
    )
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.different_first_page_header_footer = False

    normal_style = cast(Any, doc.styles["Normal"])
    normal_style.font.name = _export_font_docx_name(font_family, str(export_preset["docx_font"]))
    normal_style.font.size = Pt(int(export_preset["docx_font_size"]))
    normal_style.paragraph_format.line_spacing = 2.0

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.add_run(f"{front['header_last_name']} / {front['header_title']} / ")
    run = header.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    fld_text = OxmlElement("w:instrText")
    fld_text.set(qn("xml:space"), "preserve")
    fld_text.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(fld_text)
    run._r.append(fld_end)

    def append_field(paragraph: Any, instruction: str, placeholder: str | None = None) -> None:
        run = paragraph.add_run()
        field_begin = OxmlElement("w:fldChar")
        field_begin.set(qn("w:fldCharType"), "begin")
        field_text = OxmlElement("w:instrText")
        field_text.set(qn("xml:space"), "preserve")
        field_text.text = instruction
        run._r.append(field_begin)
        run._r.append(field_text)
        if placeholder:
            field_separate = OxmlElement("w:fldChar")
            field_separate.set(qn("w:fldCharType"), "separate")
            run._r.append(field_separate)
            paragraph.add_run(placeholder)
        field_end = OxmlElement("w:fldChar")
        field_end.set(qn("w:fldCharType"), "end")
        end_run = paragraph.add_run()
        end_run._r.append(field_end)

    def field_quote(value: str) -> str:
        return value.replace('"', "'")

    contact = doc.add_paragraph()
    contact.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for value in [
        front["author_name"] or front["display_author"],
        front["contact_email"],
        front["contact_phone"],
        front["contact_address"],
    ]:
        if value:
            contact.add_run(str(value))
            contact.add_run("\n")

    word_count_p = doc.add_paragraph()
    word_count_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    word_count_p.add_run(_approx_word_count_label(int(front["word_count"])))
    for _ in range(6):
        doc.add_paragraph("")
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run(front["title"])
    title_run.bold = True
    if front["subtitle"]:
        subtitle_p = doc.add_paragraph()
        subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_p.add_run(front["subtitle"])
    author_p = doc.add_paragraph()
    author_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author_p.add_run(front["display_author"] or " ")

    if include_toc:
        doc.add_page_break()
        for _ in range(2):
            doc.add_paragraph("")
        toc_heading = doc.add_paragraph()
        toc_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        toc_heading.add_run("Table of Contents").bold = True
        toc_field = doc.add_paragraph()
        append_field(
            toc_field, r"TOC \f \h \z", "Update this table in Word to refresh page numbers."
        )

    def add_optional_page(heading: str, content: str) -> None:
        doc.add_page_break()
        for _ in range(5):
            doc.add_paragraph("")
        heading_p = doc.add_paragraph()
        heading_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        heading_p.add_run(heading)
        content_p = doc.add_paragraph()
        content_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        content_p.add_run(content)

    if front["include_dedication"] and front["dedication"]:
        add_optional_page("Dedication", front["dedication"])
    if front["include_epigraph"] and front["epigraph"]:
        add_optional_page("Epigraph", front["epigraph"])
    if front["include_acknowledgments"] and front["acknowledgments"]:
        add_optional_page("Acknowledgments", front["acknowledgments"])
    if front["include_prologue"] and front["prologue"]:
        add_optional_page("Prologue", front["prologue"])

    def add_body_text(body_text: str) -> None:
        first_paragraph = True
        for kind, block in _chapter_body_blocks(body_text):
            paragraph = doc.add_paragraph()
            if kind == "scene_break":
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.first_line_indent = Pt(0)
                paragraph.add_run("***")
                first_paragraph = True
                continue
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.first_line_indent = (
                Inches(0) if first_paragraph else Inches(0.5)
            )
            lines = block.split("\n")
            paragraph.add_run(lines[0] if lines else "")
            for line in lines[1:]:
                paragraph.add_run("\n")
                paragraph.add_run(line)
            first_paragraph = False

    for chapter in chapters:
        doc.add_page_break()
        chapter_heading_text, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
        for _ in range(4):
            doc.add_paragraph("")
        chapter_heading = doc.add_paragraph()
        chapter_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if include_toc:
            append_field(
                chapter_heading,
                f'TC "{field_quote(_manuscript_toc_label(chapter, index_format))}" \\l 1',
            )
        chapter_heading.add_run(chapter_heading_text)
        if chapter_subtitle:
            chapter_title_p = doc.add_paragraph()
            chapter_title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            chapter_title_p.add_run(chapter_subtitle)
        add_body_text(str(chapter.get("text") or ""))

    for index, scene in enumerate(scenes or [], start=1):
        doc.add_page_break()
        scene_heading_text, scene_subtitle = _scene_heading_lines(scene, index, index_format)
        for _ in range(4):
            doc.add_paragraph("")
        scene_heading = doc.add_paragraph()
        scene_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        scene_heading.add_run(scene_heading_text)
        if scene_subtitle:
            scene_title_p = doc.add_paragraph()
            scene_title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            scene_title_p.add_run(scene_subtitle)
        add_body_text(str(scene.get("body") or ""))

    doc.add_page_break()
    ending = doc.add_paragraph()
    ending.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ending.paragraph_format.first_line_indent = Pt(0)
    ending.add_run(_manuscript_end_marker())

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
