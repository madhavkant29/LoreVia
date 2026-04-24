"""
Export utility helpers — character card and character bible renderers
for Markdown, PDF (ReportLab), and DOCX (python-docx) formats.

Extracted from the books route to keep route handlers thin.
"""
from __future__ import annotations

from app.engine.character.profile_builder import build_description
from app.models.book import Book
from app.models.character import Character
from app.utils.book_utils import clean_manuscript_html
from app.utils.character_utils import (
    character_status,
    dedupe_preserve_order,
    merge_description_with_relationships,
)

# ─── Character card ──────────────────────────────────────────────────────────

def character_card_markdown(payload: dict) -> tuple[bytes, str]:
    def bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items if item]

    lines = [
        f"# {payload['name']} - Character Card",
        "",
        f"- Manuscript: {payload['book_title']}",
        f"- Status: {payload['status']}",
        f"- First appearance: Chapter {payload['first_appearance']}" if payload["first_appearance"] else "- First appearance: -",
        f"- Last appearance: Chapter {payload['last_appearance']}" if payload["last_appearance"] else "- Last appearance: -",
        f"- Mentions count: {payload['mentions_count']}",
        f"- Role: {payload['role'] or '-'}",
        f"- Aliases: {', '.join(payload['aliases'])}" if payload["aliases"] else "- Aliases: -",
        "",
        "## Overview",
        "",
        payload["description"] or "LoreVia is still building this profile.",
        "",
    ]
    if payload["personality_tags"]:
        lines.extend(["## Personality", "", *bullets(payload["personality_tags"]), ""])
    if payload["motivations"]:
        lines.extend(["## Motivations", "", *bullets(payload["motivations"]), ""])
    if payload["fears"]:
        lines.extend(["## Fears", "", *bullets(payload["fears"]), ""])
    if payload["arc_summary"]:
        lines.extend(["## Arc Summary", "", payload["arc_summary"], ""])
    if payload["growth_events"]:
        lines.extend(["## Key Growth Events", ""])
        for event in payload["growth_events"]:
            if not isinstance(event, dict):
                continue
            chapter_label = f"Chapter {event.get('chapter')}: " if event.get("chapter") else ""
            impact = f" ({event.get('impact')})" if event.get("impact") else ""
            lines.append(f"- {chapter_label}{event.get('event', '').strip()}{impact}".strip())
        lines.append("")
    if payload.get("plot_threads"):
        lines.extend(["## Plot Thread Involvement", ""])
        for thread in payload["plot_threads"]:
            status = thread.get("status", "unknown")
            chapter_span = f"Introduced in Chapter {thread.get('introduced_at') or '-'}"
            if thread.get("resolved_at"):
                chapter_span += f", resolved in Chapter {thread.get('resolved_at')}"
            lines.append(f"- {thread.get('title')}: {status}. {chapter_span}")
            if thread.get("note"):
                lines.append(f"  Author note: {thread.get('note')}")
        lines.append("")
    if payload.get("continuity_watch"):
        lines.extend(["## Continuity Watch", "", *bullets(payload["continuity_watch"]), ""])
    if payload["relationships"]:
        lines.extend(["## Relationships", ""])
        for rel in payload["relationships"]:
            active_range = f"Chapter {rel['from_chapter']}" if rel["from_chapter"] else "Unknown start"
            active_range += f" to Chapter {rel['to_chapter']}" if rel["to_chapter"] else " onward"
            lines.append(f"- {rel['name']}: {rel['type'].title()} | {active_range}")
            if rel["description"]:
                lines.append(f"  {rel['description']}")
        lines.append("")
    return "\n".join(lines).encode("utf-8"), payload["filename_base"]


def character_card_pdf(payload: dict) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"{payload['name']} - Character Card", styles["Heading1"]), Spacer(1, 0.14 * inch)]

    metadata = [
        ["Manuscript", payload["book_title"] or "-"],
        ["Status", payload["status"]],
        ["First appearance", f"Chapter {payload['first_appearance']}" if payload["first_appearance"] else "-"],
        ["Last appearance", f"Chapter {payload['last_appearance']}" if payload["last_appearance"] else "-"],
        ["Mentions count", str(payload["mentions_count"])],
        ["Aliases", ", ".join(payload["aliases"]) or "-"],
    ]
    metadata_table = Table(metadata, colWidths=[1.7 * inch, 4.8 * inch])
    metadata_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([metadata_table, Spacer(1, 0.16 * inch)])

    story.append(Paragraph("Overview", styles["Heading2"]))
    story.append(Paragraph(payload["description"] or "LoreVia is still building this profile.", styles["BodyText"]))
    story.append(Spacer(1, 0.12 * inch))

    for heading, items in [
        ("Personality", payload["personality_tags"]),
        ("Motivations", payload["motivations"]),
        ("Fears", payload["fears"]),
    ]:
        if not items:
            continue
        story.append(Paragraph(heading, styles["Heading2"]))
        for item in items:
            story.append(Paragraph(f"• {item}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    if payload["arc_summary"]:
        story.append(Paragraph("Arc Summary", styles["Heading2"]))
        story.append(Paragraph(payload["arc_summary"], styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    if payload["growth_events"]:
        story.append(Paragraph("Key Growth Events", styles["Heading2"]))
        for event in payload["growth_events"]:
            if not isinstance(event, dict) or not event.get("event"):
                continue
            chapter = f"Chapter {event.get('chapter')}: " if event.get("chapter") else ""
            impact = f" {event.get('impact')}" if event.get("impact") else ""
            story.append(Paragraph(f"• {chapter}{event.get('event')}{impact}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))
    if payload.get("plot_threads"):
        story.append(Paragraph("Plot Thread Involvement", styles["Heading2"]))
        for thread in payload["plot_threads"]:
            chapter_span = f"Introduced in Chapter {thread.get('introduced_at') or '-'}"
            if thread.get("resolved_at"):
                chapter_span += f", resolved in Chapter {thread.get('resolved_at')}"
            note = f" Note: {thread.get('note')}" if thread.get("note") else ""
            story.append(Paragraph(f"â€¢ {thread.get('title')} ({thread.get('status', 'unknown')}). {chapter_span}.{note}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))
    if payload.get("continuity_watch"):
        story.append(Paragraph("Continuity Watch", styles["Heading2"]))
        for item in payload["continuity_watch"]:
            story.append(Paragraph(f"â€¢ {item}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    story.append(Paragraph("Relationships", styles["Heading2"]))
    if payload["relationships"]:
        rel_table_data = [["Character", "Type", "Chapters", "Note"]]
        for rel in payload["relationships"]:
            chapter_range = f"{rel['from_chapter'] or '-'}"
            chapter_range += f" to {rel['to_chapter']}" if rel["to_chapter"] else " onward"
            rel_table_data.append([rel["name"], rel["type"].title(), chapter_range, rel["description"] or "-"])
        rel_table = Table(rel_table_data, colWidths=[1.4 * inch, 1.15 * inch, 1.1 * inch, 3.0 * inch], repeatRows=1)
        rel_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(rel_table)
    else:
        story.append(Paragraph("No tracked relationships yet.", styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()


def character_card_docx(payload: dict) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    doc.add_heading(f"{payload['name']} - Character Card", level=1)
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in [
        ("Manuscript", payload["book_title"] or "-"),
        ("Status", payload["status"]),
        ("First appearance", f"Chapter {payload['first_appearance']}" if payload["first_appearance"] else "-"),
        ("Last appearance", f"Chapter {payload['last_appearance']}" if payload["last_appearance"] else "-"),
        ("Mentions count", str(payload["mentions_count"])),
        ("Aliases", ", ".join(payload["aliases"]) or "-"),
    ]:
        row = table.add_row().cells
        row[0].text = label
        row[1].text = value

    doc.add_heading("Overview", level=2)
    doc.add_paragraph(payload["description"] or "LoreVia is still building this profile.")
    for heading, items in [
        ("Personality", payload["personality_tags"]),
        ("Motivations", payload["motivations"]),
        ("Fears", payload["fears"]),
    ]:
        if not items:
            continue
        doc.add_heading(heading, level=2)
        for item in items:
            doc.add_paragraph(item, style="List Bullet")
    if payload["arc_summary"]:
        doc.add_heading("Arc Summary", level=2)
        doc.add_paragraph(payload["arc_summary"])
    if payload["growth_events"]:
        doc.add_heading("Key Growth Events", level=2)
        for event in payload["growth_events"]:
            if not isinstance(event, dict) or not event.get("event"):
                continue
            chapter = f"Chapter {event.get('chapter')}: " if event.get("chapter") else ""
            impact = f" ({event.get('impact')})" if event.get("impact") else ""
            doc.add_paragraph(f"{chapter}{event.get('event')}{impact}", style="List Bullet")
    if payload.get("plot_threads"):
        doc.add_heading("Plot Thread Involvement", level=2)
        for thread in payload["plot_threads"]:
            chapter_span = f"Introduced in Chapter {thread.get('introduced_at') or '-'}"
            if thread.get("resolved_at"):
                chapter_span += f", resolved in Chapter {thread.get('resolved_at')}"
            note = f" Note: {thread.get('note')}" if thread.get("note") else ""
            doc.add_paragraph(f"{thread.get('title')} ({thread.get('status', 'unknown')}). {chapter_span}.{note}", style="List Bullet")
    if payload.get("continuity_watch"):
        doc.add_heading("Continuity Watch", level=2)
        for item in payload["continuity_watch"]:
            doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("Relationships", level=2)
    rel_table = doc.add_table(rows=1, cols=4)
    rel_table.style = "Table Grid"
    for idx, heading in enumerate(["Character", "Type", "Chapters", "Note"]):
        rel_table.rows[0].cells[idx].text = heading
    for rel in payload["relationships"]:
        row = rel_table.add_row().cells
        row[0].text = rel["name"]
        row[1].text = rel["type"].title()
        row[2].text = f"{rel['from_chapter'] or '-'}" + (f" to {rel['to_chapter']}" if rel["to_chapter"] else " onward")
        row[3].text = rel["description"] or "-"

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ─── Character bible ─────────────────────────────────────────────────────────

def character_bible_markdown(
    *,
    book: Book,
    characters: list[Character],
    rel_summaries: dict[str, list[str]],
    thread_summaries: dict[str, list[str]],
) -> tuple[bytes, str]:
    def _clean_line(value: str | None) -> str:
        return " ".join((value or "").split()).strip()

    def _bullets(items: list[str]) -> str:
        cleaned = [item.strip() for item in items if item and item.strip()]
        return "\n".join(f"- {item}" for item in cleaned) if cleaned else ""

    title = _clean_line(book.title) or "LoreVia Character Bible"
    header = [
        f"# {title} - Character Bible",
        "",
        f"- Source: {book.title}",
        f"- Format: {book.format.upper()}",
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

        body.extend([
            f"### {char.name}",
            "",
            f"- Status: {character_status(char)}",
            f"- First appearance: Chapter {char.first_chapter}" if char.first_chapter else "- First appearance: -",
            f"- Last appearance: Chapter {char.last_seen_chapter}" if char.last_seen_chapter else "- Last appearance: -",
            f"- Mentions tracked: {char.mention_count or 0}",
            f"- Aliases: {', '.join(char.aliases or [])}" if (char.aliases or []) else "- Aliases: -",
            "",
            f"Short description: {description or 'LoreVia is still building this profile.'}",
            "",
        ])

        if tags:
            body.append("Personality")
            body.append(_bullets(tags[:10]))
            body.append("")
        if motivations:
            body.append("Motivations")
            body.append(_bullets(motivations[:8]))
            body.append("")
        if fears:
            body.append("Fears")
            body.append(_bullets(fears[:8]))
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
        if char.last_seen_chapter and book.total_chapters and book.total_chapters - char.last_seen_chapter >= 25:
            continuity_watch.append(f"Absent for {book.total_chapters - char.last_seen_chapter} chapters.")
        if continuity_watch:
            body.append("Continuity watch")
            body.append(_bullets(continuity_watch))
            body.append("")

        body.append("---")
        body.append("")

    markdown = "\n".join(header + body).encode("utf-8")
    safe_name = "".join(ch for ch in (book.title or "lorevia") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-")
    return markdown, safe_name or "lorevia"


def character_bible_pdf(*, markdown: bytes, title: str) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    story = []

    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body_style = styles["BodyText"]
    body_style.leading = 14
    body_style.textColor = colors.black

    text = markdown.decode("utf-8", errors="ignore").splitlines()
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

    doc.build(story)
    return buffer.getvalue()


def character_bible_docx(*, markdown: bytes, title: str) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph("")

    for line in markdown.decode("utf-8", errors="ignore").splitlines():
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

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def manuscript_docx(*, title: str, chapters: list[dict]) -> bytes:
    from io import BytesIO

    from bs4 import BeautifulSoup
    from docx import Document
    from docx.shared import Pt

    def add_html_block(doc: Document, html: str | None, fallback_text: str) -> None:
        cleaned_html = clean_manuscript_html(html)
        if not cleaned_html:
            for block in fallback_text.splitlines():
                doc.add_paragraph(block)
            return

        soup = BeautifulSoup(cleaned_html, "html.parser")
        for node in soup.find_all(["h1", "h2", "h3", "p", "blockquote", "ul", "ol"]):
            if node.name in {"h1", "h2", "h3"}:
                level = {"h1": 2, "h2": 3, "h3": 4}[node.name]
                doc.add_heading(node.get_text(" ", strip=True), level=level)
                continue
            if node.name in {"ul", "ol"}:
                style = "List Bullet" if node.name == "ul" else "List Number"
                for li in node.find_all("li", recursive=False):
                    doc.add_paragraph(li.get_text(" ", strip=True), style=style)
                continue
            paragraph = doc.add_paragraph(node.get_text("\n", strip=True))
            if node.name == "blockquote":
                paragraph.style = "Intense Quote"

    doc = Document()
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Times New Roman"
    normal_style.font.size = Pt(12)

    doc.add_heading(title or "LoreVia Manuscript Export", level=1)
    for chapter in chapters:
        doc.add_page_break()
        chapter_number = chapter.get("number")
        chapter_title = chapter.get("title") or f"Chapter {chapter_number}"
        doc.add_heading(f"Chapter {chapter_number}", level=2)
        if chapter_title and chapter_title != f"Chapter {chapter_number}":
            doc.add_paragraph(chapter_title)
        add_html_block(doc, chapter.get("html"), str(chapter.get("text") or ""))

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def manuscript_pdf(*, title: str, chapters: list[dict]) -> bytes:
    from io import BytesIO

    from bs4 import BeautifulSoup
    from reportlab.lib.pagesizes import A4
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

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontName = "Times-Roman"
    body.leading = 18
    heading_styles = {"h1": styles["Heading1"], "h2": styles["Heading2"], "h3": styles["Heading3"]}

    story = [Paragraph(title or "LoreVia Manuscript Export", styles["Heading1"]), Spacer(1, 0.2 * inch)]
    for index, chapter in enumerate(chapters):
        if index > 0:
            story.append(PageBreak())
        chapter_number = chapter.get("number")
        chapter_title = chapter.get("title") or f"Chapter {chapter_number}"
        story.append(Paragraph(f"Chapter {chapter_number}", styles["Heading2"]))
        if chapter_title and chapter_title != f"Chapter {chapter_number}":
            story.append(Paragraph(chapter_title, body))
            story.append(Spacer(1, 0.1 * inch))
        story.extend(build_story_blocks(chapter.get("html"), str(chapter.get("text") or ""), body, heading_styles))

    doc.build(story)
    return buffer.getvalue()
