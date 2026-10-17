"""Source-matched, lossless section plans for newly imported prose books."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from fastapi import HTTPException

from app.parsers.heading_patterns import classify_heading_type
from app.schemas.section import SectionMeta, SectionTypeLiteral

PARSER_VERSION = "prose-structure-2"
SECTION_TYPES = set(SectionTypeLiteral.__args__)
NON_STORY_TYPES = {
    "toc", "notes", "chronology", "title_page", "copyright", "dedication",
    "acknowledgements", "glossary",
}


def _section_id(source_sha256: str, index: int, kind: str) -> str:
    return hashlib.sha256(f"{source_sha256}:{index}:{kind}".encode()).hexdigest()[:32]


def _paragraph_blocks(text: str) -> list[str]:
    return [piece.strip() for piece in re.split(r"\n\s*\n", text or "") if piece.strip()]


def build_structure_plan(
    raw: bytes,
    parsed_sections: list[dict[str, Any]],
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Give every extracted prose block exactly one ordered section owner."""
    source_hash = hashlib.sha256(raw).hexdigest()
    blocks: list[str] = []
    block_locations: list[str | None] = []
    sections: list[SectionMeta] = []
    images_by_marker: dict[str, dict[str, Any]] = {}
    active_part_id: str | None = None
    for index, parsed in enumerate(parsed_sections):
        title = " ".join(str(parsed.get("title") or "").split())[:200]
        explicit_kind = parsed.get("section_type") or parsed.get("chapter_kind")
        raw_kind = str(explicit_kind or "unknown")
        detected_kind, _ = classify_heading_type(title, language)
        kind = raw_kind if raw_kind in SECTION_TYPES and explicit_kind is not None else detected_kind
        if kind not in SECTION_TYPES:
            kind = "unknown"
        text = str(parsed.get("text") or "").strip()
        for image in parsed.get("images") or []:
            if isinstance(image, dict) and image.get("marker"):
                images_by_marker[str(image["marker"])] = image
        parts = _paragraph_blocks(text)
        start = len(blocks)
        if kind == "toc" and not parts:
            sections.append(SectionMeta(
                id=_section_id(source_hash, index, "toc"), type="toc", title=title or "Contents",
                start_block=start, end_block=start, include_in_analysis=False,
                source_location=parsed.get("source_location"),
            ))
            continue
        if kind == "part":
            part_id = _section_id(source_hash, index, "part")
            sections.append(SectionMeta(
                id=part_id, type="part", title=title or f"Part {index + 1}",
                number=parsed.get("source_number"),
                source_label=title or None,
                source_location=parsed.get("source_location"),
                start_page=parsed.get("start_page"), end_page=parsed.get("end_page"),
                start_block=start, end_block=start, include_in_analysis=False,
            ))
            active_part_id = part_id
            if not parts:
                continue
            kind = "part_opening"
            title = f"{title} — opening" if title else "Part opening"
        blocks.extend(parts)
        block_locations.extend([parsed.get("source_location")] * len(parts))
        end = len(blocks)
        if start == end:
            continue
        section_id = _section_id(source_hash, index, kind)
        warning = (
            "The section type is uncertain. It will be readable and analyzed; review it if it contains supplemental material."
            if kind == "unknown" else None
        )
        section = SectionMeta(
            id=section_id, type=kind, title=title or f"Section {len(sections) + 1}",
            number=parsed.get("source_number"),
            parent_id=active_part_id,
            source_label=str(parsed.get("title") or "").strip() or None,
            source_location=parsed.get("source_location"),
            start_page=parsed.get("start_page"), end_page=parsed.get("end_page"),
            start_block=start, end_block=end,
            include_in_analysis=kind not in NON_STORY_TYPES,
            word_count=len(text.split()),
            opening_excerpt=parts[0][:180], closing_excerpt=parts[-1][-180:],
            warnings=[warning] if warning else [],
        )
        sections.append(section)
    content_hash = hashlib.sha256(
        json.dumps(blocks, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "source_sha256": source_hash,
        "content_sha256": content_hash,
        "parser_version": PARSER_VERSION,
        "sections": [section.model_dump() for section in sections],
        "blocks": blocks,
        "block_locations": block_locations,
        "images_by_marker": images_by_marker,
    }


def validate_structure_plan(
    proposed: dict[str, Any] | None,
    detected: dict[str, Any],
) -> dict[str, Any]:
    """Reject stale plans, skipped text, overlapping spans, and invalid Part trees."""
    if proposed is None:
        proposed = detected
    for key in ("source_sha256", "content_sha256", "parser_version"):
        if proposed.get(key) != detected[key]:
            raise HTTPException(409, "The import preview is stale. Preview this file again before importing.")
    raw_sections = proposed.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise HTTPException(400, "The import outline must contain at least one section.")
    try:
        sections = [SectionMeta.model_validate(item) for item in raw_sections]
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "The import outline is invalid.") from exc
    seen_ids: set[str] = set()
    part_ids: set[str] = set()
    detected_toc_ids = {
        item["id"] for item in detected["sections"] if item["type"] == "toc"
    }
    cursor = 0
    readable_count = 0
    for section in sections:
        if section.id in seen_ids or not section.id or len(section.title) > 200:
            raise HTTPException(400, "The import outline contains a duplicate ID or invalid title.")
        seen_ids.add(section.id)
        if section.type == "toc" and section.id not in detected_toc_ids:
            raise HTTPException(400, "Only detected contents pages may be marked as a TOC.")
        if section.type == "part" or (
            section.type == "toc" and section.start_block == section.end_block
        ):
            if section.start_block != cursor or section.end_block != cursor or section.parent_id:
                raise HTTPException(400, "A heading cannot move manuscript text.")
            if section.type == "part":
                part_ids.add(section.id)
            continue
        if section.parent_id and section.parent_id not in part_ids:
            raise HTTPException(400, "A section refers to a missing or later Part.")
        if section.start_block != cursor or section.end_block <= cursor:
            raise HTTPException(400, "The import outline has a gap, overlap, or empty section.")
        if section.end_block > len(detected["blocks"]):
            raise HTTPException(400, "The import outline extends beyond the source text.")
        if section.type != "toc":
            readable_count += 1
        cursor = section.end_block
    if cursor != len(detected["blocks"]):
        raise HTTPException(400, "The import outline leaves manuscript text unassigned.")
    if not readable_count:
        raise HTTPException(400, "The import outline needs at least one readable section.")
    accepted: list[dict[str, Any]] = []
    for section in sections:
        item = section.model_dump()
        matching = next((original for original in detected["sections"] if original["id"] == section.id), None)
        if matching and section.start_block == matching["start_block"] and section.end_block == matching["end_block"]:
            for field in ("source_location", "start_page", "end_page"):
                item[field] = matching.get(field)
        else:
            locations = detected.get("block_locations") or []
            span_locations = [location for location in locations[section.start_block:section.end_block] if location]
            if section.type == "part" and not span_locations and section.start_block < len(locations):
                span_locations = [locations[section.start_block]] if locations[section.start_block] else []
            item["source_location"] = (
                span_locations[0] if len(set(span_locations)) <= 1 else
                f"{span_locations[0]} – {span_locations[-1]}"
            ) if span_locations else None
            item["start_page"] = None
            item["end_page"] = None
        if detected["blocks"] and detected["blocks"][0] is not None:
            block_text = [str(block) for block in detected["blocks"][section.start_block:section.end_block]]
            item["word_count"] = sum(len(block.split()) for block in block_text)
            item["opening_excerpt"] = block_text[0][:180] if block_text else ""
            item["closing_excerpt"] = block_text[-1][-180:] if block_text else ""
        item["warnings"] = (
            ["The section type is uncertain. It will be readable and analyzed; review it if it contains supplemental material."]
            if section.type == "unknown" else []
        )
        if section.type in NON_STORY_TYPES or section.type == "part":
            item["include_in_analysis"] = False
        accepted.append(item)
    return {**detected, "sections": accepted}


def materialize_structure_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Materialize only readable sections; preserve Part and TOC metadata separately."""
    output: list[dict[str, Any]] = []
    blocks = plan["blocks"]
    for raw_section in plan["sections"]:
        section = SectionMeta.model_validate(raw_section)
        if section.type in {"part", "toc"}:
            continue
        text = "\n\n".join(blocks[section.start_block : section.end_block])
        if not text.strip():
            continue
        output.append({
            "number": len(output) + 1,
            "title": section.title,
            "text": text,
            "section_type": section.type,
            "source_number": section.number,
            "structure_section_id": section.id,
            "parent_part_id": section.parent_id,
            "source_label": section.source_label,
            "include_in_analysis": section.include_in_analysis,
            "images": [
                image for marker, image in plan.get("images_by_marker", {}).items()
                if marker in text
            ],
        })
    return output
