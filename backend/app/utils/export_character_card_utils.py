from __future__ import annotations

from app.utils.books.normalization import story_unit_name
from app.utils.export_common_utils import (
    _apply_pdf_metadata,
    _clean_line,
    _normalize_unicode_for_export,
    _set_docx_core_properties,
)
from app.utils.export_story_utils import (
    _format_growth_event_line,
    _story_unit_from_payload,
    _story_unit_heading,
    _story_unit_range,
)


def character_card_markdown(payload: dict) -> tuple[bytes, str]:
    def bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items if item]

    lines = [
        f"# {payload['name']} - Character Card",
        "",
        f"- Manuscript: {payload['book_title']}",
        f"- Status: {payload['status']}",
        f"- First appearance: {_story_unit_heading(payload, payload['first_appearance'])}"
        if payload["first_appearance"]
        else "- First appearance: -",
        f"- Last appearance: {_story_unit_heading(payload, payload['last_appearance'])}"
        if payload["last_appearance"]
        else "- Last appearance: -",
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
    if payload.get("goal"):
        lines.extend(["## Goal", "", payload["goal"], ""])
    if payload["motivations"]:
        lines.extend(["## Motivations", "", *bullets(payload["motivations"]), ""])
    if payload["fears"]:
        lines.extend(["## Fears", "", *bullets(payload["fears"]), ""])
    if payload.get("lie_they_believe"):
        lines.extend(["## Lie They Believe", "", payload["lie_they_believe"], ""])
    if payload.get("backstory_wound"):
        lines.extend(["## Wound / Backstory", "", payload["backstory_wound"], ""])
    if payload.get("arc_type"):
        lines.extend(["## Arc Type", "", payload["arc_type"], ""])
    if payload["arc_summary"]:
        lines.extend(["## Arc Summary", "", payload["arc_summary"], ""])
    if payload["growth_events"]:
        lines.extend(["## Key Growth Events", ""])
        for event in payload["growth_events"]:
            if not isinstance(event, dict):
                continue
            lines.append(f"- {_format_growth_event_line(event, _story_unit_from_payload(payload))}")
        lines.append("")
    if payload.get("plot_threads"):
        lines.extend(["## Plot Thread Involvement", ""])
        for thread in payload["plot_threads"]:
            status = thread.get("status", "unknown")
            chapter_span = (
                f"Introduced in {_story_unit_heading(payload, thread.get('introduced_at'))}"
            )
            if thread.get("resolved_at"):
                chapter_span += (
                    f", resolved in {_story_unit_heading(payload, thread.get('resolved_at'))}"
                )
            lines.append(f"- {thread.get('title')}: {status}. {chapter_span}")
            if thread.get("note"):
                lines.append(f"  Author note: {thread.get('note')}")
        lines.append("")
    if payload.get("continuity_watch"):
        lines.extend(["## Continuity Watch", "", *bullets(payload["continuity_watch"]), ""])
    if payload["relationships"]:
        lines.extend(["## Relationships", ""])
        for rel in payload["relationships"]:
            active_range = _story_unit_range(payload, rel["from_chapter"], rel["to_chapter"])
            lines.append(f"- {rel['name']}: {rel['type'].title()} | {active_range}")
            if rel["description"]:
                lines.append(f"  {rel['description']}")
        lines.append("")
    return _normalize_unicode_for_export("\n".join(lines)).encode("utf-8"), payload["filename_base"]


def character_card_pdf(payload: dict) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    export_title = (
        f"{payload['book_title']} - {payload['name']} Character Card"
        if _clean_line(payload.get("book_title"))
        else f"{payload['name']} - Character Card"
    )
    story = [
        Paragraph(f"{payload['name']} - Character Card", styles["Heading1"]),
        Spacer(1, 0.14 * inch),
    ]

    metadata = [
        ["Manuscript", payload["book_title"] or "-"],
        ["Status", payload["status"]],
        [
            "First appearance",
            _story_unit_heading(payload, payload["first_appearance"])
            if payload["first_appearance"]
            else "-",
        ],
        [
            "Last appearance",
            _story_unit_heading(payload, payload["last_appearance"])
            if payload["last_appearance"]
            else "-",
        ],
        ["Mentions count", str(payload["mentions_count"])],
        ["Aliases", ", ".join(payload["aliases"]) or "-"],
    ]
    metadata_table = Table(metadata, colWidths=[1.7 * inch, 4.8 * inch])
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([metadata_table, Spacer(1, 0.16 * inch)])

    story.append(Paragraph("Overview", styles["Heading2"]))
    story.append(
        Paragraph(
            payload["description"] or "LoreVia is still building this profile.", styles["BodyText"]
        )
    )
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
            if not isinstance(event, dict):
                continue
            event_line = _format_growth_event_line(event, _story_unit_from_payload(payload))
            if not event_line:
                continue
            story.append(Paragraph(f"• {event_line}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))
    if payload.get("plot_threads"):
        story.append(Paragraph("Plot Thread Involvement", styles["Heading2"]))
        for thread in payload["plot_threads"]:
            chapter_span = (
                f"Introduced in {_story_unit_heading(payload, thread.get('introduced_at'))}"
            )
            if thread.get("resolved_at"):
                chapter_span += (
                    f", resolved in {_story_unit_heading(payload, thread.get('resolved_at'))}"
                )
            note = f" Note: {thread.get('note')}" if thread.get("note") else ""
            story.append(
                Paragraph(
                    f"• {thread.get('title')} ({thread.get('status', 'unknown')}). {chapter_span}.{note}",
                    styles["BodyText"],
                )
            )
        story.append(Spacer(1, 0.08 * inch))
    if payload.get("continuity_watch"):
        story.append(Paragraph("Continuity Watch", styles["Heading2"]))
        for item in payload["continuity_watch"]:
            story.append(Paragraph(f"• {item}", styles["BodyText"]))
        story.append(Spacer(1, 0.08 * inch))

    story.append(Paragraph("Relationships", styles["Heading2"]))
    if payload["relationships"]:
        rel_table_data = [
            [
                "Character",
                "Type",
                story_unit_name(_story_unit_from_payload(payload), plural=True),
                "Note",
            ]
        ]
        for rel in payload["relationships"]:
            chapter_range = _story_unit_range(payload, rel["from_chapter"], rel["to_chapter"])
            rel_table_data.append(
                [rel["name"], rel["type"].title(), chapter_range, rel["description"] or "-"]
            )
        rel_table = Table(
            rel_table_data,
            colWidths=[1.4 * inch, 1.15 * inch, 1.1 * inch, 3.0 * inch],
            repeatRows=1,
        )
        rel_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(rel_table)
    else:
        story.append(Paragraph("No tracked relationships yet.", styles["BodyText"]))

    def _decorate_pdf(canvas, _doc_obj) -> None:
        _apply_pdf_metadata(canvas, title=export_title, subject="Character Card")

    doc.build(story, onFirstPage=_decorate_pdf, onLaterPages=_decorate_pdf)
    return buffer.getvalue()


def character_card_docx(payload: dict) -> bytes:
    from io import BytesIO

    from docx import Document

    doc = Document()
    export_title = (
        f"{payload['book_title']} - {payload['name']} Character Card"
        if _clean_line(payload.get("book_title"))
        else f"{payload['name']} - Character Card"
    )
    _set_docx_core_properties(doc, title=export_title, subject="Character Card")
    doc.add_heading(f"{payload['name']} - Character Card", level=1)
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in [
        ("Manuscript", payload["book_title"] or "-"),
        ("Status", payload["status"]),
        (
            "First appearance",
            _story_unit_heading(payload, payload["first_appearance"])
            if payload["first_appearance"]
            else "-",
        ),
        (
            "Last appearance",
            _story_unit_heading(payload, payload["last_appearance"])
            if payload["last_appearance"]
            else "-",
        ),
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
    for heading, value in [
        ("Goal", payload.get("goal")),
        ("Lie They Believe", payload.get("lie_they_believe")),
        ("Wound / Backstory", payload.get("backstory_wound")),
        ("Arc Type", payload.get("arc_type")),
    ]:
        if not value:
            continue
        doc.add_heading(heading, level=2)
        doc.add_paragraph(str(value))
    if payload["arc_summary"]:
        doc.add_heading("Arc Summary", level=2)
        doc.add_paragraph(payload["arc_summary"])
    if payload["growth_events"]:
        doc.add_heading("Key Growth Events", level=2)
        for event in payload["growth_events"]:
            if not isinstance(event, dict):
                continue
            event_line = _format_growth_event_line(event, _story_unit_from_payload(payload))
            if not event_line:
                continue
            doc.add_paragraph(event_line, style="List Bullet")
    if payload.get("plot_threads"):
        doc.add_heading("Plot Thread Involvement", level=2)
        for thread in payload["plot_threads"]:
            chapter_span = (
                f"Introduced in {_story_unit_heading(payload, thread.get('introduced_at'))}"
            )
            if thread.get("resolved_at"):
                chapter_span += (
                    f", resolved in {_story_unit_heading(payload, thread.get('resolved_at'))}"
                )
            note = f" Note: {thread.get('note')}" if thread.get("note") else ""
            doc.add_paragraph(
                f"{thread.get('title')} ({thread.get('status', 'unknown')}). {chapter_span}.{note}",
                style="List Bullet",
            )
    if payload.get("continuity_watch"):
        doc.add_heading("Continuity Watch", level=2)
        for item in payload["continuity_watch"]:
            doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("Relationships", level=2)
    rel_table = doc.add_table(rows=1, cols=4)
    rel_table.style = "Table Grid"
    for idx, heading in enumerate(
        [
            "Character",
            "Type",
            story_unit_name(_story_unit_from_payload(payload), plural=True),
            "Note",
        ]
    ):
        rel_table.rows[0].cells[idx].text = heading
    for rel in payload["relationships"]:
        row = rel_table.add_row().cells
        row[0].text = rel["name"]
        row[1].text = rel["type"].title()
        row[2].text = _story_unit_range(payload, rel["from_chapter"], rel["to_chapter"])
        row[3].text = rel["description"] or "-"

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
