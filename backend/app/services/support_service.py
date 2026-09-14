from __future__ import annotations

import json
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import SupportIncident
from app.schemas.support import (
    SupportIncidentCreateBody,
    SupportIncidentOut,
    SupportUiContext,
)
from app.utils.books.notes import get_owned_book
from app.utils.logging.errors import redact_sensitive_text


def safe_support_context(context: SupportUiContext) -> dict[str, object]:
    """Return only schema-allowlisted, redacted diagnostic fields."""

    payload = context.model_dump(mode="json", exclude_none=True)
    for key, value in list(payload.items()):
        if isinstance(value, str):
            payload[key] = redact_sensitive_text(value) or ""
    return payload


def support_case_reference(incident_id: uuid.UUID) -> str:
    return f"LV-{incident_id.hex[:8].upper()}"


def _incident_out(incident: SupportIncident) -> SupportIncidentOut:
    return SupportIncidentOut(
        id=incident.id,
        reference=support_case_reference(incident.id),
        status=incident.status,
        category=incident.category,
        feature=incident.feature,
        summary=incident.summary,
        resolution=incident.resolution,
        created_at=incident.created_at,
    )


async def create_user_support_incident(
    db: AsyncSession,
    *,
    current_user,
    body: SupportIncidentCreateBody,
) -> SupportIncidentOut:
    if body.context.book_id is not None:
        await get_owned_book(db, body.context.book_id, current_user.id)
    summary = redact_sensitive_text(body.summary.strip()) or "Support request"
    diagnostics = safe_support_context(body.context)
    incident = SupportIncident(
        user_id=current_user.id,
        book_id=body.context.book_id,
        category=body.category,
        feature=(body.feature or body.context.tool_id or "support")[:100],
        severity="medium",
        summary=f"{summary}\nSafe diagnostics: {json.dumps(diagnostics, sort_keys=True)}",
        created_by_user_id=current_user.id,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return _incident_out(incident)


async def get_user_support_incident(
    db: AsyncSession,
    *,
    current_user,
    incident_id: uuid.UUID,
) -> SupportIncidentOut:
    incident = await db.get(SupportIncident, incident_id)
    if incident is None or incident.user_id != current_user.id:
        raise HTTPException(404, "Support case not found")
    return _incident_out(incident)
