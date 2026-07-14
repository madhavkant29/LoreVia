from __future__ import annotations

from typing import Any, cast

from app.utils.export_common_utils import (
    _apply_pdf_metadata,
    _clean_line,
    _export_font_docx_name,
    _export_font_epub_stack,
    _export_font_pdf_names,
    _normalize_unicode_for_export,
    _safe_name,
    _set_docx_core_properties,
)
from app.utils.export_manuscript_formatting_utils import (
    _chapter_body_blocks,
    _chapter_heading_lines,
    _manuscript_end_marker,
    _manuscript_toc_label,
)
from app.utils.export_novel_structure_utils import (
    _back_matter_sections,
    _chapter_inline_segments,
    _chapter_media_items,
    _cover_image_payload,
    _front_matter_sections,
    _image_extension,
    _novel_front_matter,
    normalize_novel_image_placement,
)
from app.utils.export_preset_utils import novel_export_preset


def novel_docx(
    *,
    title: str,
    chapters: list[dict],
    preset: str = "standard_novel",
    front_matter: dict | None = None,
    preface: str | None = None,
    novel_front_matter: dict | None = None,
    epub_metadata: dict | None = None,
    cover_image: dict[str, Any] | None = None,
    font_family: str | None = None,
    include_images: bool = False,
    image_placement: str = "end",
    include_image_captions: bool = False,
    index_format: str = "arabic",
) -> bytes:
    from io import BytesIO

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.image.exceptions import UnrecognizedImageError
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    export_preset = novel_export_preset(preset)
    front = _novel_front_matter(
        title, chapters, front_matter, preface, novel_front_matter, epub_metadata
    )
    image_placement = normalize_novel_image_placement(image_placement)
    doc = Document()
    _set_docx_core_properties(
        doc,
        title=front["title"],
        author=front["display_author"] or "LoreVia",
        subject="Novel",
    )
    section = doc.sections[0]
    page_width, page_height = cast(tuple[float, float], export_preset["docx_page_size"])
    section.page_width = Inches(page_width)
    section.page_height = Inches(page_height)
    left_margin, right_margin, top_margin, bottom_margin = cast(
        tuple[float, float, float, float], export_preset["pdf_margins"]
    )
    section.left_margin = Inches(left_margin)
    section.right_margin = Inches(right_margin)
    section.top_margin = Inches(top_margin)
    section.bottom_margin = Inches(bottom_margin)

    normal_style = cast(Any, doc.styles["Normal"])
    normal_style.font.name = _export_font_docx_name(font_family, str(export_preset["docx_font"]))
    normal_style.font.size = Pt(int(export_preset["docx_font_size"]))
    normal_style.paragraph_format.line_spacing = 1.35

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.add_run(f"{front['display_author'] or 'LoreVia'} / {front['title']} / ")
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

    def _append_field(paragraph: Any, instruction: str, placeholder: str | None = None) -> None:
        field_run = paragraph.add_run()
        field_begin = OxmlElement("w:fldChar")
        field_begin.set(qn("w:fldCharType"), "begin")
        field_text = OxmlElement("w:instrText")
        field_text.set(qn("xml:space"), "preserve")
        field_text.text = instruction
        field_run._r.append(field_begin)
        field_run._r.append(field_text)
        if placeholder:
            field_separate = OxmlElement("w:fldChar")
            field_separate.set(qn("w:fldCharType"), "separate")
            field_run._r.append(field_separate)
            paragraph.add_run(placeholder)
        field_end = OxmlElement("w:fldChar")
        field_end.set(qn("w:fldCharType"), "end")
        end_run = paragraph.add_run()
        end_run._r.append(field_end)

    def _field_quote(value: str) -> str:
        return value.replace('"', "'")

    cover = _cover_image_payload(front["title"], front["display_author"], cover_image)
    cover_paragraph = doc.add_paragraph()
    cover_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        cover_paragraph.add_run().add_picture(
            BytesIO(cover["raw"]), width=Inches(min(page_width - left_margin - right_margin, 5.5))
        )
    except (KeyError, OSError, TypeError, ValueError, UnrecognizedImageError):
        cover_paragraph.add_run(front["title"]).bold = True
    doc.add_page_break()

    toc_heading = doc.add_paragraph()
    toc_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    toc_heading.add_run("Table of Contents").bold = True
    toc_field = doc.add_paragraph()
    _append_field(toc_field, r"TOC \f \h \z", "Update this table in Word to refresh page numbers.")
    toc_note = doc.add_paragraph()
    toc_note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    toc_note.add_run(
        "In Word, right-click the table of contents and choose Update Field after opening."
    ).italic = True

    def _add_body_text(body_text: str) -> None:
        first_paragraph = True
        for kind, block in _chapter_body_blocks(_normalize_unicode_for_export(body_text)):
            paragraph = doc.add_paragraph()
            if kind == "scene_break":
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                paragraph.paragraph_format.first_line_indent = Pt(0)
                paragraph.add_run("***")
                first_paragraph = True
                continue
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.first_line_indent = (
                Inches(0) if first_paragraph else Inches(0.3)
            )
            lines = block.split("\n")
            paragraph.add_run(lines[0] if lines else "")
            for line in lines[1:]:
                paragraph.add_run("\n")
                paragraph.add_run(line)
            first_paragraph = False

    def _add_docx_image(media: dict[str, Any]) -> None:
        try:
            image_p = doc.add_paragraph()
            image_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            image_p.add_run().add_picture(
                BytesIO(media["raw"]),
                width=Inches(min(page_width - left_margin - right_margin, 5.5)),
            )
            if include_image_captions and _clean_line(media.get("caption")):
                caption_p = doc.add_paragraph()
                caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                caption_p.add_run(_clean_line(media.get("caption"))).italic = True
        except (KeyError, OSError, TypeError, ValueError, UnrecognizedImageError):
            return

    for section_data in _front_matter_sections(front):
        doc.add_page_break()
        heading = doc.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _append_field(heading, f'TC "{_field_quote(section_data["title"])}" \\l 1')
        heading.add_run(section_data["title"]).bold = True
        _add_body_text(section_data["text"])

    for chapter in chapters:
        doc.add_page_break()
        chapter_heading_text, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
        for _ in range(3):
            doc.add_paragraph("")
        chapter_heading = doc.add_paragraph()
        chapter_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _append_field(
            chapter_heading,
            f'TC "{_field_quote(_manuscript_toc_label(chapter, index_format))}" \\l 1',
        )
        chapter_heading.add_run(chapter_heading_text).bold = True
        if chapter_subtitle:
            chapter_title_p = doc.add_paragraph()
            chapter_title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            chapter_title_p.add_run(chapter_subtitle)
        if include_images and image_placement == "inline":
            segments, unmatched_images = _chapter_inline_segments(chapter)
            for segment in segments:
                if segment["kind"] == "image":
                    _add_docx_image(segment["media"])
                else:
                    _add_body_text(str(segment.get("text") or ""))
            for media in unmatched_images:
                _add_docx_image(media)
        else:
            _add_body_text(str(chapter.get("text") or ""))
            if include_images:
                for media in _chapter_media_items(chapter):
                    if image_placement == "plates":
                        doc.add_page_break()
                    _add_docx_image(media)

    doc.add_page_break()
    ending = doc.add_paragraph()
    ending.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ending.paragraph_format.first_line_indent = Pt(0)
    ending.add_run(_manuscript_end_marker()).bold = True

    for section_data in _back_matter_sections(front):
        doc.add_page_break()
        heading = doc.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _append_field(heading, f'TC "{_field_quote(section_data["title"])}" \\l 1')
        heading.add_run(section_data["title"]).bold = True
        _add_body_text(section_data["text"])

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def novel_pdf_compiled(
    *,
    title: str,
    chapters: list[dict],
    preset: str = "standard_novel",
    front_matter: dict | None = None,
    preface: str | None = None,
    novel_front_matter: dict | None = None,
    epub_metadata: dict | None = None,
    cover_image: dict[str, Any] | None = None,
    font_family: str | None = None,
    include_images: bool = False,
    image_placement: str = "end",
    include_image_captions: bool = False,
    index_format: str = "arabic",
) -> bytes:
    from io import BytesIO

    from reportlab.lib.pagesizes import A5, LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
    from reportlab.platypus.tableofcontents import TableOfContents

    def escaped(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    export_preset = novel_export_preset(preset)
    front = _novel_front_matter(
        title, chapters, front_matter, preface, novel_front_matter, epub_metadata
    )
    image_placement = normalize_novel_image_placement(image_placement)
    page_size = {"A5": A5, "LETTER": LETTER}[str(export_preset["pdf_page_size"])]
    left_margin, right_margin, top_margin, bottom_margin = cast(
        tuple[float, float, float, float], export_preset["pdf_margins"]
    )
    buffer = BytesIO()

    class NovelPdfTemplate(SimpleDocTemplate):
        def afterFlowable(self, flowable) -> None:
            if (
                not isinstance(flowable, Paragraph)
                or getattr(flowable.style, "name", "") != "ChapterHeading"
            ):
                return
            toc_label = getattr(flowable, "_lorevia_toc_label", None)
            bookmark_key = getattr(flowable, "_lorevia_bookmark_key", None)
            if toc_label:
                if bookmark_key:
                    self.canv.bookmarkPage(bookmark_key)
                    self.canv.addOutlineEntry(toc_label, bookmark_key, level=0, closed=False)
                    self.notify("TOCEntry", (0, toc_label, self.page, bookmark_key))
                else:
                    self.notify("TOCEntry", (0, toc_label, self.page))

    doc = NovelPdfTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=left_margin * inch,
        rightMargin=right_margin * inch,
        topMargin=top_margin * inch,
        bottomMargin=bottom_margin * inch,
    )
    styles = getSampleStyleSheet()
    pdf_regular, pdf_bold = _export_font_pdf_names(font_family)
    font_size = int(export_preset["docx_font_size"])
    body = ParagraphStyle(
        "NovelBody",
        parent=styles["BodyText"],
        fontName=pdf_regular,
        fontSize=font_size,
        leading=font_size * 1.55,
        firstLineIndent=0.3 * inch,
    )
    body_first = ParagraphStyle("NovelBodyFirst", parent=body, firstLineIndent=0)
    centered = ParagraphStyle("NovelCentered", parent=body, alignment=1, firstLineIndent=0)
    chapter_heading = ParagraphStyle(
        "ChapterHeading",
        parent=styles["Heading2"],
        fontName=pdf_bold,
        fontSize=font_size + 4,
        alignment=1,
        leading=font_size + 8,
    )
    toc_entry_style = ParagraphStyle(
        "NovelTOCEntry",
        parent=styles["BodyText"],
        fontName=pdf_regular,
        fontSize=font_size,
        leading=font_size + 6,
    )

    story: list[Any] = []
    cover = _cover_image_payload(front["title"], front["display_author"], cover_image)
    story.append(Spacer(1, 0.01 * inch))

    toc = TableOfContents()
    toc.levelStyles = [toc_entry_style]
    story.append(PageBreak())
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("Table of Contents", chapter_heading))
    story.append(Spacer(1, 0.3 * inch))
    story.append(toc)

    def _append_body_text(body_text: str) -> None:
        first_paragraph = True
        for kind, block in _chapter_body_blocks(_normalize_unicode_for_export(body_text)):
            story.append(
                Paragraph(
                    "***" if kind == "scene_break" else escaped(block).replace("\n", "<br/>"),
                    centered
                    if kind == "scene_break"
                    else (body_first if first_paragraph else body),
                )
            )
            first_paragraph = kind == "scene_break"

    def _append_pdf_image(media: dict[str, Any]) -> None:
        try:
            image_flowable = Image(BytesIO(media["raw"]))
            max_width = page_size[0] - (left_margin + right_margin) * inch
            max_height = page_size[1] - (top_margin + bottom_margin) * inch
            scale = min(
                1.0, max_width / image_flowable.imageWidth, max_height / image_flowable.imageHeight
            )
            image_flowable.drawWidth = image_flowable.imageWidth * scale
            image_flowable.drawHeight = image_flowable.imageHeight * scale
            story.append(Spacer(1, 0.2 * inch))
            story.append(image_flowable)
            if include_image_captions and _clean_line(media.get("caption")):
                story.append(Paragraph(escaped(_clean_line(media.get("caption"))), centered))
        except (KeyError, OSError, TypeError, ValueError):
            return

    def _append_pdf_section(section_data: dict[str, str]) -> None:
        story.append(PageBreak())
        heading = Paragraph(escaped(section_data["title"]), chapter_heading)
        setattr(heading, "_lorevia_toc_label", section_data["title"])
        setattr(heading, "_lorevia_bookmark_key", f"novel-{section_data['key']}")
        story.append(heading)
        story.append(Spacer(1, 0.2 * inch))
        _append_body_text(section_data["text"])

    for section_data in _front_matter_sections(front):
        _append_pdf_section(section_data)

    for chapter_index, chapter in enumerate(chapters, start=1):
        story.append(PageBreak())
        chapter_heading_text, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
        story.append(Spacer(1, 1.2 * inch))
        heading_paragraph = Paragraph(escaped(chapter_heading_text), chapter_heading)
        setattr(
            heading_paragraph, "_lorevia_toc_label", _manuscript_toc_label(chapter, index_format)
        )
        setattr(heading_paragraph, "_lorevia_bookmark_key", f"chapter-{chapter_index}")
        story.append(heading_paragraph)
        if chapter_subtitle:
            story.append(Paragraph(escaped(chapter_subtitle), centered))
            story.append(Spacer(1, 0.1 * inch))
        if include_images and image_placement == "inline":
            segments, unmatched_images = _chapter_inline_segments(chapter)
            for segment in segments:
                if segment["kind"] == "image":
                    _append_pdf_image(segment["media"])
                else:
                    _append_body_text(str(segment.get("text") or ""))
            for media in unmatched_images:
                _append_pdf_image(media)
        else:
            _append_body_text(str(chapter.get("text") or ""))
            if include_images:
                for media in _chapter_media_items(chapter):
                    if image_placement == "plates":
                        story.append(PageBreak())
                    _append_pdf_image(media)

    story.append(PageBreak())
    story.append(Spacer(1, 2.0 * inch))
    ending = Paragraph(_manuscript_end_marker(), chapter_heading)
    setattr(ending, "_lorevia_toc_label", _manuscript_end_marker())
    setattr(ending, "_lorevia_bookmark_key", "the-end")
    story.append(ending)

    for section_data in _back_matter_sections(front):
        _append_pdf_section(section_data)

    def _draw_page(canvas, doc_obj) -> None:
        canvas.saveState()
        _apply_pdf_metadata(
            canvas,
            title=front["title"],
            author=front["display_author"] or "LoreVia",
            subject="Novel",
        )
        if canvas.getPageNumber() == 1:
            try:
                cover_reader = ImageReader(BytesIO(cover["raw"]))
                image_width, image_height = cover_reader.getSize()
                scale = max(doc_obj.pagesize[0] / image_width, doc_obj.pagesize[1] / image_height)
                draw_width = image_width * scale
                draw_height = image_height * scale
                canvas.drawImage(
                    cover_reader,
                    (doc_obj.pagesize[0] - draw_width) / 2,
                    (doc_obj.pagesize[1] - draw_height) / 2,
                    width=draw_width,
                    height=draw_height,
                    mask="auto",
                )
            except (KeyError, OSError, TypeError, ValueError):
                canvas.setFont(pdf_bold, font_size + 8)
                canvas.drawCentredString(
                    doc_obj.pagesize[0] / 2, doc_obj.pagesize[1] / 2, front["title"]
                )
            canvas.restoreState()
            return
        if canvas.getPageNumber() > 1:
            canvas.setFont(pdf_regular, 9)
            canvas.drawRightString(
                doc_obj.pagesize[0] - doc.rightMargin,
                doc_obj.pagesize[1] - 0.45 * inch,
                f"{front['display_author'] or 'LoreVia'} / {front['title']} / {canvas.getPageNumber()}",
            )
        canvas.restoreState()

    doc.multiBuild(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()


def novel_epub_compiled(
    *,
    title: str,
    chapters: list[dict],
    preset: str = "standard_novel",
    front_matter: dict | None = None,
    preface: str | None = None,
    novel_front_matter: dict | None = None,
    epub_metadata: dict | None = None,
    cover_image: dict[str, Any] | None = None,
    font_family: str | None = None,
    include_images: bool = False,
    image_placement: str = "end",
    include_image_captions: bool = False,
    index_format: str = "arabic",
) -> bytes:
    import os
    import tempfile
    from html import escape

    from ebooklib import epub

    export_preset = novel_export_preset(preset)
    front = _novel_front_matter(
        title, chapters, front_matter, preface, novel_front_matter, epub_metadata
    )
    image_placement = normalize_novel_image_placement(image_placement)
    safe_title = _clean_line(front["title"]) or "LoreVia Novel Export"
    book = epub.EpubBook()
    book.set_identifier(_safe_name(safe_title) or "lorevia-novel")
    book.set_title(safe_title)
    book.set_language(front["language"] or "en")
    if front["display_author"]:
        book.add_author(front["display_author"])
    if front["publisher"]:
        book.add_metadata("DC", "publisher", front["publisher"])
    if front["description"]:
        book.add_metadata("DC", "description", front["description"])
    if front["isbn"]:
        book.add_metadata("DC", "identifier", front["isbn"], {"id": "isbn"})
    if front["series_name"]:
        book.add_metadata(None, "meta", front["series_name"], {"name": "calibre:series"})
    if front["series_number"]:
        book.add_metadata(None, "meta", front["series_number"], {"name": "calibre:series_index"})

    cover = _cover_image_payload(front["title"], front["display_author"], cover_image)
    cover_extension = _image_extension(cover.get("content_type"))
    try:
        book.set_cover(f"cover.{cover_extension}", cover["raw"])
    except (KeyError, OSError, TypeError, ValueError):
        pass

    stylesheet = epub.EpubItem(
        uid="style_nav",
        file_name="styles/main.css",
        media_type="text/css",
        content=(
            f"body {{ font-family: {_export_font_epub_stack(font_family)}; font-size: {int(export_preset['docx_font_size'])}pt; line-height: 1.7; margin: 8%; }} "
            "h1, h2 { text-align: center; } "
            ".title-page, .cover-page, .end-marker { text-align: center; margin-top: 20%; } "
            ".toc-page { page-break-before: always; } "
            ".toc-page ol { line-height: 1.8; } "
            ".scene-break { text-align: center; letter-spacing: 0.2em; text-indent: 0; } "
            ".first-paragraph, .caption { text-indent: 0; } "
            ".chapter-image { max-width: 100%; height: auto; display: block; margin: 1.5em auto 0.5em; } "
            ".image-plate { max-width: 100%; height: auto; display: block; margin: 20% auto 0.5em; page-break-before: always; } "
            ".caption { text-align: center; font-style: italic; } "
            "p { text-indent: 1.4em; margin: 0 0 1em; }"
        ).encode(),
    )
    book.add_item(stylesheet)

    spine: list[Any] = ["nav"]
    toc_entries: list[Any] = []

    def _body_html(text: str) -> str:
        parts: list[str] = []
        first_paragraph = True
        for kind, block in _chapter_body_blocks(_normalize_unicode_for_export(text)):
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

    def _epub_image_html(
        chapter_number: object, index: int, media: dict[str, Any], css_class: str = "chapter-image"
    ) -> str:
        parts: list[str] = []
        extension = _image_extension(media.get("content_type"))
        filename = f"images/chapter-{chapter_number}-{index}.{extension}"
        image_item = epub.EpubItem(
            uid=f"chapter_{chapter_number}_image_{index}",
            file_name=filename,
            media_type=str(media.get("content_type") or f"image/{extension}"),
            content=media["raw"],
        )
        book.add_item(image_item)
        parts.append(
            f"<img class='{css_class}' src='../{filename}' alt='{escape(_clean_line(media.get('caption')) or 'Chapter image')}'/>"
        )
        if include_image_captions and _clean_line(media.get("caption")):
            parts.append(f"<p class='caption'>{escape(_clean_line(media.get('caption')))}</p>")
        return "".join(parts)

    def _chapter_images_html(
        chapter: dict[str, Any],
        media_items: list[dict[str, Any]] | None = None,
        css_class: str = "chapter-image",
    ) -> str:
        if not include_images:
            return ""
        chapter_number = chapter.get("number") or "x"
        return "".join(
            _epub_image_html(chapter_number, index, media, css_class)
            for index, media in enumerate(
                media_items if media_items is not None else _chapter_media_items(chapter), start=1
            )
        )

    title_page = epub.EpubHtml(title="Title Page", file_name="title-page.xhtml", lang="en")
    title_page.content = (
        "<section class='title-page'>"
        f"<h1>{escape(front['title'])}</h1>"
        f"{f'<h2>{escape(front["subtitle"])}</h2>' if front['subtitle'] else ''}"
        f"<p class='first-paragraph'>{escape(front['display_author'] or ' ')}</p>"
        "</section>"
    )
    title_page.add_item(stylesheet)
    book.add_item(title_page)
    spine.append(title_page)
    toc_entries.append(title_page)

    toc_item = epub.EpubHtml(
        title="Table of Contents", file_name="table-of-contents.xhtml", lang="en"
    )
    toc_items = []
    for section_data in _front_matter_sections(front):
        toc_items.append(
            f"<li><a href='{section_data['key']}.xhtml'>{escape(section_data['title'])}</a></li>"
        )
    for chapter in chapters:
        chapter_number = chapter.get("number")
        toc_items.append(
            f"<li><a href='chapter-{chapter_number}.xhtml'>{escape(_manuscript_toc_label(chapter, index_format))}</a></li>"
        )
    toc_items.append("<li><a href='the-end.xhtml'>THE END</a></li>")
    for section_data in _back_matter_sections(front):
        toc_items.append(
            f"<li><a href='{section_data['key']}.xhtml'>{escape(section_data['title'])}</a></li>"
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

    def _add_epub_section(section_data: dict[str, str]) -> None:
        item = epub.EpubHtml(
            title=section_data["title"], file_name=f"{section_data['key']}.xhtml", lang="en"
        )
        item.content = f"<h1>{escape(section_data['title'])}</h1>{_body_html(section_data['text'])}"
        item.add_item(stylesheet)
        book.add_item(item)
        spine.append(item)
        toc_entries.append(item)

    for section_data in _front_matter_sections(front):
        _add_epub_section(section_data)

    for chapter in chapters:
        chapter_number = chapter.get("number")
        chapter_heading_text, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
        image_html = ""
        if include_images and image_placement == "inline":
            rendered_parts: list[str] = []
            image_index = 1
            segments, unmatched_images = _chapter_inline_segments(chapter)
            for segment in segments:
                if segment["kind"] == "image":
                    rendered_parts.append(
                        _epub_image_html(chapter_number, image_index, segment["media"])
                    )
                    image_index += 1
                else:
                    rendered_parts.append(_body_html(str(segment.get("text") or "")))
            for media in unmatched_images:
                rendered_parts.append(_epub_image_html(chapter_number, image_index, media))
                image_index += 1
            body_html = "".join(rendered_parts)
        else:
            body_html = _body_html(str(chapter.get("text") or ""))
            if include_images:
                image_html = _chapter_images_html(
                    chapter,
                    css_class="image-plate" if image_placement == "plates" else "chapter-image",
                )
        item = epub.EpubHtml(
            title=chapter_subtitle or chapter_heading_text,
            file_name=f"chapter-{chapter_number}.xhtml",
            lang="en",
        )
        item.content = (
            f"<h1>{escape(chapter_heading_text)}</h1>"
            f"{f'<h2>{escape(chapter_subtitle)}</h2>' if chapter_subtitle else ''}"
            f"{body_html}"
            f"{image_html}"
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

    for section_data in _back_matter_sections(front):
        _add_epub_section(section_data)

    book.toc = tuple(toc_entries)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "novel.epub")
        epub.write_epub(target, book, {})
        with open(target, "rb") as handle:
            return handle.read()
