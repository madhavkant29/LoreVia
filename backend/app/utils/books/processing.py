"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def normalize_processing_timestamp(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    raw = " ".join(str(value).strip().split())
    if not raw:
        return None
    normalized = raw
    if len(normalized) >= 20 and normalized[10] == " ":
        normalized = f"{normalized[:10]}T{normalized[11:]}"
    if re.search(r"[+-]\d{2}$", normalized):
        normalized = f"{normalized}:00"
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    return normalized


PUBLIC_PROCESSING_STAGE_LABELS: dict[str, str] = {
    "queued": "Queued for processing",
    "parsing": "Parsing manuscript",
    "extracting": "Extracting story data",
    "summarizing": "Building summaries",
    "embedding": "Indexing search",
    "analyzing": "Running story analysis",
    "ready": "Ready",
    "failed": "Processing failed",
}

PROCESSING_STAGE_ALIASES: dict[str, str] = {
    "": "queued",
    "pending": "queued",
    "processing": "extracting",
    "uploading": "queued",
    "parse": "parsing",
    "parser": "parsing",
    "parsed": "parsing",
    "extraction": "extracting",
    "extract": "extracting",
    "chunking": "extracting",
    "summary": "summarizing",
    "summaries": "summarizing",
    "summarize": "summarizing",
    "embedding": "embedding",
    "embeddings": "embedding",
    "indexing": "embedding",
    "analysis": "analyzing",
    "analyze": "analyzing",
    "complete": "ready",
    "completed": "ready",
    "done": "ready",
    "error": "failed",
    "failed": "failed",
}


def normalize_public_processing_stage(
    status: str | None, stage: str | None, *, is_fully_ready: bool = False
) -> str:
    normalized_status = " ".join(str(status or "").strip().lower().replace("-", "_").split())
    normalized_stage = " ".join(str(stage or "").strip().lower().replace("-", "_").split())
    if is_fully_ready or normalized_status == "ready":
        return "ready"
    if normalized_status in {"failed", "error"}:
        return "failed"
    if normalized_stage in {"failed", "error"}:
        return "failed"
    if normalized_stage in PROCESSING_STAGE_ALIASES:
        return PROCESSING_STAGE_ALIASES[normalized_stage]
    if normalized_status in PROCESSING_STAGE_ALIASES:
        return PROCESSING_STAGE_ALIASES[normalized_status]
    return "extracting"


def processing_retry_available(
    status: str | None, stage: str | None, retry_actions: list[str], last_error: str | None
) -> bool:
    normalized_status = str(status or "").strip().lower()
    normalized_stage = str(stage or "").strip().lower()
    actionable_retries = [action for action in retry_actions if action != "wait_for_analysis"]
    return bool(
        normalized_status in {"failed", "error"}
        or normalized_stage in {"failed", "error"}
        or actionable_retries
        or last_error
    )


def _normalize_processing_state(raw: dict | None) -> dict | None:
    source = raw if isinstance(raw, dict) else {}

    status = " ".join(str(source.get("status") or "").split()).strip() or None
    stage = " ".join(str(source.get("stage") or "").split()).strip() or None
    progress_pct = source.get("progress_pct")
    chapters_completed = source.get("chapters_completed")
    chapters_total = source.get("chapters_total")
    eta_seconds = source.get("eta_seconds")
    queue_wait_ms = source.get("queue_wait_ms")
    last_chapter_number = source.get("last_chapter_number")
    last_chapter_title = (
        " ".join(str(source.get("last_chapter_title") or "").split()).strip() or None
    )
    started_at = source.get("started_at")
    updated_at = source.get("updated_at")
    last_error = " ".join(str(source.get("last_error") or "").split()).strip() or None
    parser_diagnostics = (
        source.get("parser_diagnostics")
        if isinstance(source.get("parser_diagnostics"), dict)
        else None
    )
    is_fully_ready = bool(source.get("is_fully_ready", False))
    retry_actions = [
        " ".join(str(item).split()).strip()
        for item in (source.get("retry_actions") or [])
        if " ".join(str(item).split()).strip()
    ]
    raw_pipeline = source.get("pipeline") if isinstance(source.get("pipeline"), dict) else {}

    payload: dict[str, Any] = {}
    public_stage = normalize_public_processing_stage(status, stage, is_fully_ready=is_fully_ready)
    payload["status"] = status or ("ready" if public_stage == "ready" else "processing")
    payload["stage"] = public_stage
    payload["current_step_label"] = PUBLIC_PROCESSING_STAGE_LABELS[public_stage]
    if isinstance(progress_pct, (int, float)):
        payload["progress_pct"] = float(progress_pct)
    if isinstance(chapters_completed, (int, float)) and int(chapters_completed) >= 0:
        payload["chapters_completed"] = int(chapters_completed)
    if isinstance(chapters_total, (int, float)) and int(chapters_total) >= 0:
        payload["chapters_total"] = int(chapters_total)
    if isinstance(eta_seconds, (int, float)) and int(eta_seconds) >= 0:
        payload["eta_seconds"] = int(eta_seconds)
    if isinstance(queue_wait_ms, (int, float)) and int(queue_wait_ms) >= 0:
        payload["queue_wait_ms"] = int(queue_wait_ms)
    if isinstance(last_chapter_number, (int, float)) and int(last_chapter_number) >= 0:
        payload["last_chapter_number"] = int(last_chapter_number)
    if last_chapter_title:
        payload["last_chapter_title"] = last_chapter_title
    if started_at:
        payload["started_at"] = normalize_processing_timestamp(started_at)
    if updated_at:
        payload["updated_at"] = normalize_processing_timestamp(updated_at)
    if last_error:
        payload["last_error"] = last_error
    if parser_diagnostics:
        payload["parser_diagnostics"] = parser_diagnostics
    payload["is_fully_ready"] = is_fully_ready
    if retry_actions:
        payload["retry_actions"] = retry_actions
    for key in (
        "processing_run_id",
        "pause_reason",
        "auto_resume",
        "resume_available",
        "resume_blockers",
        "next_chapter_number",
        "next_resume_at",
    ):
        if key in source:
            payload[key] = source[key]
    payload["retry_available"] = processing_retry_available(
        status, public_stage, retry_actions, last_error
    )
    if raw_pipeline:
        pipeline: dict[str, Any] = {}
        for key in ("extraction", "analysis"):
            stage = raw_pipeline.get(key) if isinstance(raw_pipeline.get(key), dict) else None
            if not stage:
                continue
            normalized_stage: dict[str, Any] = {}
            normalized_status = " ".join(str(stage.get("status") or "").split()).strip() or None
            if normalized_status:
                normalized_stage["status"] = normalized_status
            completed = stage.get("completed_chapters")
            if isinstance(completed, (int, float)) and int(completed) >= 0:
                normalized_stage["completed_chapters"] = int(completed)
            total = stage.get("total_chapters")
            if isinstance(total, (int, float)) and int(total) >= 0:
                normalized_stage["total_chapters"] = int(total)
            stage_updated = stage.get("updated_at")
            if stage_updated:
                normalized_stage["updated_at"] = normalize_processing_timestamp(stage_updated)
            stage_eta = stage.get("eta_seconds")
            if isinstance(stage_eta, (int, float)) and int(stage_eta) >= 0:
                normalized_stage["eta_seconds"] = int(stage_eta)
            stage_error = " ".join(str(stage.get("last_error") or "").split()).strip() or None
            if stage_error:
                normalized_stage["last_error"] = stage_error
            failed_chapters = stage.get("failed_chapters")
            if isinstance(failed_chapters, list):
                normalized_stage["failed_chapters"] = [
                    int(item)
                    for item in failed_chapters
                    if isinstance(item, (int, float)) and int(item) > 0
                ]
            if normalized_stage:
                pipeline[key] = normalized_stage
        if pipeline:
            payload["pipeline"] = pipeline

    return payload or None


def _normalize_internal_processing_state(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict):
        return None
    payload = json.loads(json.dumps(raw, default=str))
    for key in ("status", "stage", "last_chapter_title", "last_error"):
        if key not in payload:
            continue
        cleaned = " ".join(str(payload.get(key) or "").split()).strip()
        if cleaned:
            payload[key] = cleaned
        else:
            payload.pop(key, None)
    for key in ("started_at", "updated_at"):
        if payload.get(key):
            normalized = normalize_processing_timestamp(payload.get(key))
            if normalized:
                payload[key] = normalized
    if isinstance(payload.get("retry_actions"), list):
        payload["retry_actions"] = [
            cleaned
            for cleaned in (
                " ".join(str(item).split()).strip() for item in payload["retry_actions"]
            )
            if cleaned
        ]
    return payload or None


def normalize_reprocess_metadata(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    payload = json.loads(json.dumps(source, default=str))
    payload["auto_reprocess_enabled"] = bool(source.get("auto_reprocess_enabled", True))
    pending_chapters = sorted(
        {
            int(item)
            for item in (source.get("pending_chapters") or [])
            if isinstance(item, (int, float)) and int(item) > 0
        }
    )
    payload["pending_chapters"] = pending_chapters
    for key in (
        "last_mode_changed_at",
        "last_manual_chapter_started_at",
        "last_manual_chapter_number",
    ):
        value = source.get(key)
        if value is None or value == "":
            payload.pop(key, None)
        elif key == "last_manual_chapter_number" and isinstance(value, (int, float)):
            payload[key] = int(value)
        else:
            payload[key] = str(value).strip()
    return payload
