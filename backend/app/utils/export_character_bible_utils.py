from __future__ import annotations

from typing import Any, cast

from app.engine.character.profile_builder import build_description
from app.models.book import Book
from app.models.character import Character
from app.utils.books.normalization import story_unit_label, story_unit_name
from app.utils.characters.governance import character_status
from app.utils.characters.presentation import (
    dedupe_preserve_order,
    merge_description_with_relationships,
)
from app.utils.export_common_utils import (
    EXPORT_ATTRIBUTION,
    _apply_pdf_metadata,
    _clean_line,
    _export_font_docx_name,
    _export_font_pdf_names,
    _normalize_unicode_for_export,
    _set_docx_core_properties,
    append_export_attribution,
    export_filename_base,
)


def character_bible_markdown(
    *,
    book: Book,
    characters: list[Character],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
) -> tuple[bytes, str]:
    def _bullets(items: list[str]) -> str:
        cleaned = [item.strip() for item in items if item and item.strip()]
        return "\n".join(f"- {item}" for item in cleaned) if cleaned else ""

    title = _clean_line(book.title) or "LoreVia Character Bible"
    header = [
        f"# {title} - Character Bible",
        "",
        f"- Source: {book.title}",
        f"- Format: {book.format.upper()}",
        f"- Work type: {book.work_type.title()}",
        "",
        "This file is auto-generated from LoreVia's manuscript extraction pipeline.",
        "",
        "## Characters",
        "",
    ]

    body: list[str] = []
    for char in characters:
        relationship_lines = dedupe_preserve_order(rel_summaries.get(str(char.id), []))
        description = _clean_line(build_description(char.trait_state or {}, char.archetype))
        if relationship_lines:
            description = merge_description_with_relationships(description, relationship_lines)
        tags = [item for item in (char.personality_tags or []) if _clean_line(item)]
        motivations = [item for item in (char.motivations or []) if _clean_line(item)]
        fears = [item for item in (char.fears or []) if _clean_line(item)]

        body.extend(
            [
                f"### {char.name}",
                "",
                f"- Status: {character_status(char)}",
                f"- First appearance: {story_unit_label(book, char.first_chapter)}"
                if char.first_chapter
                else "- First appearance: -",
                f"- Last appearance: {story_unit_label(book, char.last_seen_chapter)}"
                if char.last_seen_chapter
                else "- Last appearance: -",
                f"- Mentions tracked: {char.mention_count or 0}",
                f"- Aliases: {', '.join(char.aliases or [])}"
                if (char.aliases or [])
                else "- Aliases: -",
                "",
                f"Short description: {description or 'LoreVia is still building this profile.'}",
                "",
            ]
        )

        if tags:
            body.append("Personality")
            body.append(_bullets(tags[:10]))
            body.append("")
        if _clean_line(getattr(char, "goal", None)):
            body.append("Goal")
            body.append(_bullets([_clean_line(getattr(char, "goal", None))]))
            body.append("")
        if motivations:
            body.append("Motivations")
            body.append(_bullets(motivations[:8]))
            body.append("")
        if fears:
            body.append("Fears")
            body.append(_bullets(fears[:8]))
            body.append("")
        if _clean_line(getattr(char, "lie_they_believe", None)):
            body.append("Lie they believe")
            body.append(_bullets([_clean_line(getattr(char, "lie_they_believe", None))]))
            body.append("")
        if _clean_line(getattr(char, "backstory_wound", None)):
            body.append("Wound / backstory")
            body.append(_bullets([_clean_line(getattr(char, "backstory_wound", None))]))
            body.append("")
        if _clean_line(getattr(char, "arc_type", None)):
            body.append("Arc type")
            body.append(_bullets([_clean_line(getattr(char, "arc_type", None))]))
            body.append("")
        if _clean_line(char.arc_summary):
            body.append("Arc summary")
            body.append(_bullets([_clean_line(char.arc_summary)]))
            body.append("")
        if relationship_lines:
            body.append("Relationships")
            body.append(_bullets(relationship_lines))
            body.append("")
        thread_lines = dedupe_preserve_order(thread_summaries.get(str(char.id), []))
        if thread_lines:
            body.append("Plot thread involvement")
            body.append(_bullets(thread_lines))
            body.append("")
        continuity_watch: list[str] = []
        if (
            char.last_seen_chapter
            and book.total_chapters
            and book.total_chapters - char.last_seen_chapter >= 25
        ):
            continuity_watch.append(
                f"Absent for {book.total_chapters - char.last_seen_chapter} {story_unit_name(book, plural=True, lowercase=True)}."
            )
        if continuity_watch:
            body.append("Continuity watch")
            body.append(_bullets(continuity_watch))
            body.append("")

        body.append("---")
        body.append("")

    content = append_export_attribution("\n".join(header + body))
    markdown = _normalize_unicode_for_export(content).encode("utf-8")
    return markdown, export_filename_base(book.title)


def character_bible_pdf(*, markdown: bytes, title: str, font_family: str | None = None) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
    )
    styles = getSampleStyleSheet()
    story = []

    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body_style = styles["BodyText"]
    pdf_regular, pdf_bold = _export_font_pdf_names(font_family)
    h1.fontName = pdf_bold
    h2.fontName = pdf_bold
    body_style.fontName = pdf_regular
    body_style.leading = 14
    body_style.textColor = colors.black

    def _draw_footer(canvas, doc_obj) -> None:
        canvas.saveState()
        _apply_pdf_metadata(canvas, title=title, subject="Character Bible")
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(doc_obj.pagesize[0] / 2, 0.45 * inch, EXPORT_ATTRIBUTION)
        canvas.restoreState()

    text = [
        line
        for line in markdown.decode("utf-8", errors="ignore").splitlines()
        if line.strip() != EXPORT_ATTRIBUTION
    ]
    story.append(Paragraph(title, h1))
    story.append(Spacer(1, 0.2 * inch))

    for line in text:
        if line.startswith("### "):
            story.append(Spacer(1, 0.14 * inch))
            story.append(Paragraph(line.replace("### ", ""), h2))
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            story.append(Spacer(1, 0.18 * inch))
            story.append(Paragraph(line.replace("## ", ""), h1))
            story.append(Spacer(1, 0.12 * inch))
            continue
        if not line.strip():
            story.append(Spacer(1, 0.10 * inch))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", body_style))
        else:
            story.append(Paragraph(line, body_style))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()


def character_bible_docx(*, markdown: bytes, title: str, font_family: str | None = None) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    _set_docx_core_properties(doc, title=title, subject="Character Bible")
    normal_style = cast(Any, doc.styles["Normal"])
    normal_style.font.name = _export_font_docx_name(font_family)
    doc.add_heading(title, level=1)
    doc.add_paragraph("")

    for line in markdown.decode("utf-8", errors="ignore").splitlines():
        if line.strip() == EXPORT_ATTRIBUTION:
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            doc.add_heading(line.replace("## ", ""), level=2)
            continue
        if line.startswith("### "):
            doc.add_heading(line.replace("### ", ""), level=3)
            continue
        if line.startswith("- "):
            doc.add_paragraph(line[2:], style="List Bullet")
            continue
        if line.strip() == "---":
            doc.add_page_break()
            continue
        doc.add_paragraph(line)

    for section in doc.sections:
        footer = section.footer
        paragraph = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        paragraph.text = EXPORT_ATTRIBUTION

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
