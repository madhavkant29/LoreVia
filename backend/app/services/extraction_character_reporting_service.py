from __future__ import annotations

import uuid
from typing import Any

from app.engine.embeddings.embedder import build_character_embedding_text, embed_batch
from app.services.extraction_character_decision_service import _entity_evidence


def _append_rejected_character_reports(
    target: list[dict[str, Any]], entries: list[dict[str, Any]] | None
) -> None:
    if not entries:
        return
    seen = {
        (
            str(item.get("name") or "").casefold(),
            str(item.get("stage") or "").casefold(),
            str(item.get("reason") or "").casefold(),
        )
        for item in target
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("name") or "").casefold(),
            str(entry.get("stage") or "").casefold(),
            str(entry.get("reason") or "").casefold(),
        )
        if not key[0] or key in seen:
            continue
        seen.add(key)
        target.append(
            {
                "name": str(entry.get("name") or ""),
                "stage": str(entry.get("stage") or ""),
                "reason": str(entry.get("reason") or ""),
                "confidence": entry.get("confidence"),
                "evidence": entry.get("evidence") or {},
            }
        )


def _summarize_rejected_character_reports(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return entries[:40]


def _first_chapter_lookup_candidates(name: str | None, aliases: list[str] | None) -> list[str]:
    candidates = [str(name or "").strip(), *[str(alias).strip() for alias in aliases or []]]
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


async def _embed_new_character_candidates(
    pending_new_entities: list[tuple[dict[str, Any], set[uuid.UUID]]],
    *,
    db,
    user_id: uuid.UUID,
    book_id: uuid.UUID,
) -> list[list[float]]:
    if not pending_new_entities:
        return []

    embedding_inputs = [
        build_character_embedding_text(
            name=str(entity.get("name") or ""),
            traits=entity.get("traits") if isinstance(entity.get("traits"), dict) else {},
            aliases=entity.get("aliases") if isinstance(entity.get("aliases"), list) else [],
            role=str(entity.get("role") or "").strip() or None,
            arc_summary=str(entity.get("arc_summary") or "").strip() or None,
            evidence_snippets=[
                str(item).strip()
                for item in (
                    (_entity_evidence(entity).get("snippets") or [])
                    if isinstance(_entity_evidence(entity).get("snippets"), list)
                    else []
                )
                if str(item).strip()
            ],
        )
        for entity, _blocked_ids in pending_new_entities
    ]
    return await embed_batch(
        embedding_inputs,
        db=db,
        user_id=user_id,
        book_id=book_id,
        feature="character_embedding",
    )
