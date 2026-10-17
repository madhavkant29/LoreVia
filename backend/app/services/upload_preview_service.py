import asyncio
import hashlib
import json
import logging
import uuid
from typing import Any

from fastapi import HTTPException

from app.core.redis import cache_get, cache_set
from app.utils.books.imports import build_import_preview
from app.utils.books.structure_plan import PARSER_VERSION, validate_structure_plan

log = logging.getLogger(__name__)

UPLOAD_PREVIEW_CACHE_TTL_SECONDS = 15 * 60


def import_word_totals(preview: dict[str, Any], accepted_plan: dict[str, Any] | None = None) -> tuple[int, int]:
    """Count readable storage words separately from words sent for analysis."""
    if not preview.get("parser_version"):
        total = int(preview.get("total_words") or 0)
        return total, total
    sections = (accepted_plan or preview).get("sections") or []
    readable = sum(int(item.get("word_count") or 0) for item in sections if item.get("type") not in {"part", "toc"})
    analyzed = sum(
        int(item.get("word_count") or 0) for item in sections
        if item.get("type") not in {"part", "toc"} and item.get("include_in_analysis")
    )
    return readable, analyzed


def upload_preview_cache_key(user_id: uuid.UUID, raw: bytes, format_name: str, work_type: str) -> str:
    return (
        f"upload-preview:{PARSER_VERSION}:{user_id}:{format_name}:{work_type}:"
        f"{hashlib.sha256(raw).hexdigest()}"
    )


async def load_or_build_upload_preview(
    *,
    user_id: uuid.UUID,
    raw: bytes,
    format_name: str,
    work_type: str,
) -> dict[str, Any]:
    key = upload_preview_cache_key(user_id, raw, format_name, work_type)
    cached = await cache_get(key)
    if isinstance(cached, dict):
        return cached
    preview = await asyncio.to_thread(
        lambda: build_import_preview(
            format_name=format_name, work_type=work_type, raw=raw, language=None
        )
    )
    await cache_set(key, preview, UPLOAD_PREVIEW_CACHE_TTL_SECONDS)
    return preview


def accept_upload_structure_plan(
    *, preview: dict[str, Any], raw: bytes, submitted: str | None,
) -> dict[str, Any] | None:
    """Bind the confirmed outline to the exact source before queueing a worker."""
    if not preview.get("parser_version"):
        return None
    if preview.get("source_sha256") != hashlib.sha256(raw).hexdigest():
        raise HTTPException(409, "The source file changed after preview. Preview it again.")
    detected = {
        "source_sha256": preview["source_sha256"],
        "content_sha256": preview["content_sha256"],
        "parser_version": preview["parser_version"],
        "sections": preview["sections"],
        "blocks": [None] * int(preview.get("block_count") or 0),
        "warnings": preview.get("warnings") or [],
    }
    try:
        proposed = json.loads(submitted) if submitted is not None else None
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "The import outline could not be read.") from exc
    if proposed is not None and not isinstance(proposed, dict):
        raise HTTPException(400, "The import outline must be an object.")
    validated = validate_structure_plan(proposed, detected)
    counts = preview.get("block_word_counts") or []
    openings = preview.get("block_openings") or []
    closings = preview.get("block_closings") or []
    locations = preview.get("block_locations") or []
    for section in validated["sections"]:
        start = int(section["start_block"])
        end = int(section["end_block"])
        section["word_count"] = sum(counts[start:end])
        section["opening_excerpt"] = openings[start] if end > start and start < len(openings) else ""
        section["closing_excerpt"] = closings[end - 1] if end > start and end - 1 < len(closings) else ""
        first = locations[start] if start < len(locations) else None
        last = locations[end - 1] if end > start and end - 1 < len(locations) else first
        if first:
            section["source_location"] = first if not last or first == last else f"{first} – {last}"
    validated["warnings"] = [
        {"message": warning, "section_id": section["id"], "severity": "warning"}
        for section in validated["sections"] for warning in section.get("warnings", [])
    ]
    return {key: value for key, value in validated.items() if key != "blocks"}
