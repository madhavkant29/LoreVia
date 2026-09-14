from __future__ import annotations

from typing import Any, BinaryIO, cast

from app.utils.books.manuscript import clean_manuscript_html
from app.utils.export_common_utils import (
    EXPORT_ATTRIBUTION,
    _apply_pdf_metadata,
    _export_font_pdf_names,
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


def manuscript_pdf(
    *,
    title: str,
    chapters: list[dict],
    preset: str = "standard_manuscript",
    font_family: str | None = None,
) -> bytes:
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

    export_preset = manuscript_export_preset(preset)
    page_size = {"A4": A4, "A5": A5, "LETTER": LETTER}[str(export_preset["pdf_page_size"])]
    left_margin, right_margin, top_margin, bottom_margin = cast(
        tuple[float, float, float, float], export_preset["pdf_margins"]
    )
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
    pdf_regular, pdf_bold = _export_font_pdf_names(font_family)
    body.fontName = pdf_regular
    body.leading = 18
    heading_styles = {"h1": styles["Heading1"], "h2": styles["Heading2"], "h3": styles["Heading3"]}
    for heading_style in heading_styles.values():
        heading_style.fontName = pdf_bold

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
        story.extend(
            build_story_blocks(
                chapter.get("html"), str(chapter.get("text") or ""), body, heading_styles
            )
        )

    def _draw_footer(canvas, doc_obj) -> None:
        canvas.saveState()
        _apply_pdf_metadata(
            canvas, title=title or "LoreVia Manuscript Export", subject="Manuscript"
        )
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(doc_obj.pagesize[0] / 2, 0.45 * inch, EXPORT_ATTRIBUTION)
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()


def manuscript_pdf_compiled(
    *,
    title: str,
    chapters: list[dict],
    scenes: list[dict] | None = None,
    preset: str = "standard_manuscript",
    front_matter: dict | None = None,
    font_family: str | None = None,
    include_toc: bool = False,
    index_format: str = "arabic",
    output: BinaryIO | None = None,
) -> bytes | None:
    from io import BytesIO

    from reportlab.lib.pagesizes import A4, A5, LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
    from reportlab.platypus.tableofcontents import TableOfContents

    def escaped(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    export_preset = manuscript_export_preset(preset)
    front = _manuscript_front_matter(title, chapters, front_matter)
    page_size = {"A4": A4, "A5": A5, "LETTER": LETTER}[str(export_preset["pdf_page_size"])]
    left_margin, right_margin, top_margin, bottom_margin = cast(
        tuple[float, float, float, float], export_preset["pdf_margins"]
    )
    buffer = output or BytesIO()

    class ManuscriptPdfTemplate(SimpleDocTemplate):
        def afterFlowable(self, flowable) -> None:
            if not include_toc:
                return
            if (
                not isinstance(flowable, Paragraph)
                or getattr(flowable.style, "name", "") != "ChapterHeading"
            ):
                return
            toc_label = getattr(flowable, "_lorevia_toc_label", None)
            if not toc_label:
                return
            self.notify("TOCEntry", (0, toc_label, self.page))

    template_class = ManuscriptPdfTemplate if include_toc else SimpleDocTemplate
    doc = template_class(
        buffer,
        pagesize=page_size,
        leftMargin=left_margin * inch,
        rightMargin=right_margin * inch,
        topMargin=top_margin * inch,
        bottomMargin=bottom_margin * inch,
    )
    styles = getSampleStyleSheet()
    pdf_regular, pdf_bold = _export_font_pdf_names(font_family)
    body = ParagraphStyle(
        "ManuscriptBody",
        parent=styles["BodyText"],
        fontName=pdf_regular,
        fontSize=12,
        leading=24,
        firstLineIndent=0.5 * inch,
    )
    body_first = ParagraphStyle("ManuscriptBodyFirst", parent=body, firstLineIndent=0)
    centered = ParagraphStyle("CenteredBody", parent=body, alignment=1, firstLineIndent=0)
    chapter_heading = ParagraphStyle(
        "ChapterHeading",
        parent=styles["Heading2"],
        fontName=pdf_bold,
        fontSize=14,
        alignment=1,
        leading=18,
    )
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName=pdf_bold,
        fontSize=18,
        alignment=1,
        leading=24,
    )
    toc_entry_style = ParagraphStyle(
        "ManuscriptTOCEntry",
        parent=styles["BodyText"],
        fontName=pdf_regular,
        fontSize=11,
        leading=18,
    )

    story: list[Any] = []
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
    if contact_lines:
        story.append(Paragraph("<br/>".join(escaped(str(line)) for line in contact_lines), body))
    story.append(
        Paragraph(
            f"<para alignment='right'>{escaped(_approx_word_count_label(int(front['word_count'])))}</para>",
            body,
        )
    )
    story.append(Spacer(1, 2.0 * inch))
    story.append(Paragraph(escaped(front["title"]), title_style))
    if front["subtitle"]:
        story.append(Paragraph(escaped(front["subtitle"]), centered))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(escaped(front["display_author"] or " "), centered))

    if include_toc:
        toc = TableOfContents()
        toc.levelStyles = [toc_entry_style]
        story.append(PageBreak())
        story.append(Spacer(1, 0.6 * inch))
        story.append(Paragraph("Table of Contents", chapter_heading))
        story.append(Spacer(1, 0.3 * inch))
        story.append(toc)

    def _optional_page(heading: str, content: str) -> None:
        story.append(PageBreak())
        story.append(Spacer(1, 2.0 * inch))
        story.append(Paragraph(escaped(heading), chapter_heading))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph(escaped(content), centered))

    if front["include_dedication"] and front["dedication"]:
        _optional_page("Dedication", front["dedication"])
    if front["include_epigraph"] and front["epigraph"]:
        _optional_page("Epigraph", front["epigraph"])
    if front["include_acknowledgments"] and front["acknowledgments"]:
        _optional_page("Acknowledgments", front["acknowledgments"])
    if front["include_prologue"] and front["prologue"]:
        _optional_page("Prologue", front["prologue"])

    def _append_body_text(body_text: str) -> None:
        first_paragraph = True
        for kind, block in _chapter_body_blocks(body_text):
            story.append(
                Paragraph(
                    "***" if kind == "scene_break" else escaped(block).replace("\n", "<br/>"),
                    centered
                    if kind == "scene_break"
                    else (body_first if first_paragraph else body),
                )
            )
            first_paragraph = kind == "scene_break"

    for chapter in chapters:
        story.append(PageBreak())
        chapter_heading_text, chapter_subtitle = _chapter_heading_lines(chapter, index_format)
        story.append(Spacer(1, 2.2 * inch))
        heading_paragraph = Paragraph(escaped(chapter_heading_text), chapter_heading)
        if include_toc:
            setattr(
                heading_paragraph,
                "_lorevia_toc_label",
                _manuscript_toc_label(chapter, index_format),
            )
        story.append(heading_paragraph)
        if chapter_subtitle:
            story.append(Paragraph(escaped(chapter_subtitle), centered))
            story.append(Spacer(1, 0.1 * inch))
        _append_body_text(str(chapter.get("text") or ""))

    for index, scene in enumerate(scenes or [], start=1):
        scene_heading_text, scene_subtitle = _scene_heading_lines(scene, index, index_format)
        story.append(PageBreak())
        story.append(Spacer(1, 2.2 * inch))
        story.append(Paragraph(escaped(scene_heading_text), chapter_heading))
        if scene_subtitle:
            story.append(Paragraph(escaped(scene_subtitle), centered))
            story.append(Spacer(1, 0.1 * inch))
        _append_body_text(str(scene.get("body") or ""))

    story.append(PageBreak())
    story.append(Spacer(1, 2.2 * inch))
    story.append(Paragraph(_manuscript_end_marker(), chapter_heading))

    def _draw_first_page(canvas, doc_obj) -> None:
        _draw_later_pages(canvas, doc_obj)

    def _draw_later_pages(canvas, doc_obj) -> None:
        canvas.saveState()
        _apply_pdf_metadata(
            canvas,
            title=front["title"],
            author=front["display_author"] or "LoreVia",
            subject="Manuscript",
        )
        canvas.setFont(pdf_regular, 10)
        canvas.drawRightString(
            doc_obj.pagesize[0] - doc.rightMargin,
            doc_obj.pagesize[1] - 0.55 * inch,
            f"{front['header_last_name']} / {front['header_title']} / {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    if include_toc:
        doc.multiBuild(story, onFirstPage=_draw_first_page, onLaterPages=_draw_later_pages)
    else:
        doc.build(story, onFirstPage=_draw_first_page, onLaterPages=_draw_later_pages)
    if output is not None:
        return None
    return cast(Any, buffer).getvalue()
