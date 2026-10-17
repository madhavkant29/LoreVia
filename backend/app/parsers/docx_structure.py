"""DOCX prose structure extraction with source paragraph locations."""

from __future__ import annotations

import re
from io import BytesIO

from docx import Document
from docx.table import Table

from app.parsers.text_parser import parse_text_structure


def parse_docx_structure(raw: bytes) -> list[dict]:
    document = Document(BytesIO(raw))
    lines: list[str] = []
    line_locations: list[str] = []
    heading_lines: set[int] = set()
    chapter_heading_lines: set[int] = set()
    for block_number, item in enumerate(document.iter_inner_content(), start=1):
        heading_level = None
        if isinstance(item, Table):
            text = "\n".join(
                " | ".join(" ".join(cell.text.split()) for cell in row.cells if cell.text.strip())
                for row in item.rows
            ).strip()
        else:
            text = item.text.strip()
            style_name = item.style.name.lower() if item.style else ""
            match = re.fullmatch(r"heading\s+(\d+)", style_name)
            heading_level = int(match.group(1)) if text and match else None
        if not text:
            continue
        location = f"{'table' if isinstance(item, Table) else 'paragraph'} {block_number}"
        if lines:
            lines.append("")
            line_locations.append(location)
        if heading_level is not None:
            heading_lines.add(len(lines))
            if heading_level >= 2:
                chapter_heading_lines.add(len(lines))
        for line in text.splitlines():
            lines.append(line)
            line_locations.append(location)
    sections = parse_text_structure(
        "\n".join(lines),
        heading_hint_lines=heading_lines,
        chapter_hint_lines=chapter_heading_lines,
        source_name="paragraph",
    )
    for section in sections:
        first_index = max(0, int(section.get("start_line") or 1) - 1)
        last_index = max(first_index, int(section.get("end_line") or 1) - 1)
        first = (
            line_locations[min(first_index, len(line_locations) - 1)] if line_locations else None
        )
        last = line_locations[min(last_index, len(line_locations) - 1)] if line_locations else first
        section["source_location"] = first if first == last else f"{first}–{last}"
    return sections
