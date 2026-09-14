"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from app.models.book import (
    Book,
)
from app.utils.books import (
    writer_workspace,
)
from app.utils.books.domain_constants import REVISION_KEYWORD_STOPWORDS

if TYPE_CHECKING:
    pass


def _stable_revision_item_id(*parts: object) -> str:
    payload = "||".join(" ".join(str(part or "").split()).strip().lower() for part in parts)
    digest = hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"rev-{digest[:12]}"


def _revision_board_state_map(workspace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    board = (
        workspace.get("revision_board") if isinstance(workspace.get("revision_board"), dict) else {}
    )
    items = board.get("items") if isinstance(board, dict) else []
    state_map: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            continue
        state_map[item_id] = item
    return state_map


def _overlay_revision_state(
    item: dict[str, Any], state_map: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    payload = dict(item)
    state = state_map.get(str(item.get("id") or ""))
    if not isinstance(state, dict):
        state = {}
    payload["status"] = str(state.get("status") or payload.get("status") or "pending")
    payload["assigned_version_id"] = str(
        state.get("assigned_version_id") or ""
    ).strip() or payload.get("assigned_version_id")
    payload["task_id"] = str(state.get("task_id") or "").strip() or payload.get("task_id")
    payload["decision"] = str(state.get("decision") or "").strip() or None
    payload["action"] = str(state.get("action") or "").strip() or None
    payload["reason"] = str(state.get("reason") or "").strip() or None
    return payload


def _make_revision_action_item(
    *,
    category: str,
    title: str,
    description: str,
    severity: str,
    chapter_ref: int | None = None,
    source_label: str | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    return {
        "id": _stable_revision_item_id(category, chapter_ref or 0, title, description[:160]),
        "category": category,
        "title": title,
        "description": description,
        "severity": severity,
        "chapter_ref": chapter_ref,
        "source_label": source_label,
        "recommendation": recommendation,
        "status": "pending",
        "assigned_version_id": None,
        "task_id": None,
        "why_flagged": description,
        "evidence_strength": "limited",
        "evidence": [],
        "is_stale": False,
        "decision": None,
        "action": None,
        "reason": None,
    }


def _priority_revision_findings(
    items: list[dict[str, Any]], *, limit: int = 3
) -> list[dict[str, Any]]:
    severity_order = {"high": 0, "medium": 1, "low": 2}
    candidates = [item for item in items if item.get("status") not in {"fixed", "ignored"}]
    candidates.sort(
        key=lambda item: (
            severity_order.get(str(item.get("severity") or "low"), 3),
            int(item.get("chapter_ref") or 10**9),
            str(item.get("id") or ""),
        )
    )
    selected: list[dict[str, Any]] = []
    used_categories: set[str] = set()
    for item in candidates:
        category = str(item.get("category") or "")
        if category in used_categories:
            continue
        selected.append(item)
        used_categories.add(category)
        if len(selected) >= limit:
            return selected
    for item in candidates:
        if item in selected:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _finding_excerpt(text: str, item: dict[str, Any], *, max_chars: int = 360) -> tuple[str, bool]:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return "", False
    terms = [
        token.lower()
        for token in re.findall(
            r"[A-Za-z][A-Za-z'-]{3,}", f"{item.get('title', '')} {item.get('description', '')}"
        )
        if token.lower() not in REVISION_KEYWORD_STOPWORDS
    ]
    lowered = cleaned.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return cleaned[:max_chars].rstrip(), False
    center = min(positions)
    start = max(0, center - max_chars // 3)
    end = min(len(cleaned), start + max_chars)
    excerpt = cleaned[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(cleaned):
        excerpt = f"{excerpt}..."
    return excerpt, True


def apply_revision_finding_decision(
    book: Book,
    *,
    finding: dict[str, Any],
    decision: str,
    action: str | None,
    reason: str | None,
) -> None:
    if decision == "accepted" and action is None:
        action = "added_to_revision_plan"
    if decision == "dismissed" and reason is None:
        reason = "other"
    if decision != "accepted" and action is not None:
        raise HTTPException(422, "Only accepted findings can record an activation action.")

    workspace = writer_workspace.normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    board = writer_workspace._normalize_revision_board(workspace.get("revision_board"))
    finding_id = str(finding.get("id") or "").strip()
    existing = {str(item.get("item_id")): item for item in board["items"]}
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    status = (
        "task_created"
        if decision == "accepted"
        else "ignored"
        if decision == "dismissed"
        else "fixed"
    )
    source_versions = {
        str(evidence.get("chapter_ref")): int(evidence.get("source_content_version") or 1)
        for evidence in finding.get("evidence") or []
        if isinstance(evidence, dict) and evidence.get("chapter_ref")
    }
    existing[finding_id] = {
        **existing.get(finding_id, {}),
        "item_id": finding_id,
        "status": status,
        "assigned_version_id": existing.get(finding_id, {}).get("assigned_version_id"),
        "task_id": existing.get(finding_id, {}).get("task_id"),
        "updated_at": now,
        "decision": decision,
        "action": action,
        "reason": reason,
        "source_content_versions": source_versions,
        "finding_snapshot": finding,
    }
    board["items"] = list(existing.values())
    board["last_generated_at"] = now
    workspace["revision_board"] = board
    if decision == "accepted" and action:
        workspace["activation"] = {
            "completed_at": now,
            "completion_action": action,
            "completed_finding_id": finding_id,
        }
    book.writer_workspace = workspace
