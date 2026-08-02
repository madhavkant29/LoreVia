from __future__ import annotations


def build_continuity_report_markdown(
    *,
    title: str,
    chapter_num: int | None,
    review: dict,
    retrieved_passages: list[dict],
    open_threads: list[dict],
) -> str:
    lines = [
        "# LoreVia Continuity Review Report",
        "",
        f"- Manuscript: {title}",
        f"- Chapter under review: {chapter_num if chapter_num is not None else 'Not specified'}",
        "- Document type: Editorial continuity assessment",
        "",
        "## Executive Summary",
        "",
        str(review.get("overall_verdict") or "No verdict generated."),
        "",
        "## Thematic Fit",
        "",
        f"- Rating: {review.get('thematic_fit', {}).get('score', 'unknown')}",
        f"- Notes: {review.get('thematic_fit', {}).get('notes', 'No notes provided.')}",
        "",
        "## Continuity Findings",
        "",
    ]

    issues = review.get("continuity_issues") or []
    if issues:
        for issue in issues:
            lines.extend(
                [
                    f"### {issue.get('title', 'Untitled issue')}",
                    f"- Severity: {issue.get('severity', 'unknown')}",
                    f"- Type: {issue.get('type', 'unknown')}",
                    f"- Finding: {issue.get('description', 'No description provided.')}",
                    f"- Recommended action: {issue.get('suggestion', 'No recommendation provided.')}",
                    "",
                ]
            )
    else:
        lines.extend(["No continuity conflicts were identified.", ""])

    insertions = review.get("insertion_opportunities") or []
    lines.extend(["## Insertion Opportunities", ""])
    if insertions:
        for item in insertions:
            lines.extend(
                [
                    f"### {item.get('title', 'Untitled opportunity')}",
                    f"- Target chapter: {item.get('target_chapter', '-')}",
                    f"- Problem addressed: {item.get('problem', 'No problem stated.')}",
                    f"- Add: {item.get('what_to_add', 'No suggestion provided.')}",
                    f"- Why here: {item.get('why_here', 'No reasoning provided.')}",
                    "",
                ]
            )
    else:
        lines.extend(["No insertion opportunities were identified.", ""])

    lines.extend(["## Grammar And Formatting", ""])
    grammar = review.get("grammar_issues") or []
    if grammar:
        for issue in grammar:
            lines.append(
                f'- {issue.get("issue", "Grammar issue")}: "{issue.get("original", "")}" -> "{issue.get("fix", "")}"'
            )
    else:
        lines.append("- No grammar issues recorded.")
    lines.append("")

    formatting = review.get("formatting_notes") or []
    if formatting:
        lines.extend(["Formatting notes:"] + [f"- {note}" for note in formatting] + [""])

    lines.extend(["## Forgotten Threads And Follow-Up Watchlist", ""])
    if open_threads:
        for item in open_threads:
            lines.append(
                f"- {item.get('title', 'Untitled')}: {item.get('description', 'No detail recorded.')}"
            )
    else:
        lines.append("- No forgotten-thread warnings were active for this manuscript state.")
    lines.append("")

    lines.extend(["## Supporting Passages", ""])
    if retrieved_passages:
        for passage in retrieved_passages:
            chapter_label = f"Chapter {passage.get('chapter_num')}"
            if passage.get("chapter_title"):
                chapter_label += f" — {passage.get('chapter_title')}"
            lines.append(f"- {chapter_label}: {passage.get('excerpt', '')}")
    else:
        lines.append("- No passages were attached to this review.")

    return "\n".join(lines) + "\n"


def build_continuity_report_pdf(markdown: str, *, title: str, chapter_num: int | None) -> bytes:
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
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    heading = styles["Heading1"]
    subheading = styles["Heading2"]
    body = styles["BodyText"]
    body.leading = 14
    body.textColor = colors.black
    story = [
        Paragraph("LoreVia Continuity Review Report", heading),
        Spacer(1, 0.16 * inch),
        Paragraph(f"Manuscript: {title}", body),
        Paragraph(
            f"Chapter under review: {chapter_num if chapter_num is not None else 'Not specified'}",
            body,
        ),
        Spacer(1, 0.18 * inch),
    ]

    for line in markdown.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            story.append(Spacer(1, 0.12 * inch))
            story.append(Paragraph(line[3:], subheading))
            continue
        if line.startswith("### "):
            story.append(Spacer(1, 0.08 * inch))
            story.append(Paragraph(line[4:], body))
            continue
        if not line.strip():
            story.append(Spacer(1, 0.08 * inch))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", body))
        else:
            story.append(Paragraph(line, body))

    doc.build(story)
    return buffer.getvalue()
