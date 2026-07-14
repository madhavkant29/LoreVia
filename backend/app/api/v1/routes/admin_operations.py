from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.redis
from app.api.deps.auth import (
    require_admin_csrf,
    require_admin_step_up,
    require_super_admin,
)
from app.api.v1.routes.admin_common import admin_scopes_from_request
from app.core.database import get_db
from app.models.operations import SupportIncident
from app.models.user import User
from app.schemas.admin import (
    AdminTaskActionBody,
    SupportIncidentCreateBody,
    SupportIncidentResolveBody,
)
from app.services.admin_service import record_admin_audit_event, record_admin_read
from app.services.operations_admin_service import (
    contribution_margin,
    dismiss_terminal_execution,
    list_task_executions,
    operations_metrics,
    quality_metrics,
    retry_terminal_execution,
)
from app.utils.redis_utils import maybe_await

router = APIRouter()


@router.get("/queue-depth")
async def queue_depth(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    redis = await app.core.redis.get_redis()
    payload = {
        "extraction": await maybe_await(redis.llen("extraction")),
        "analysis": await maybe_await(redis.llen("analysis")),
        "embedding": await maybe_await(redis.llen("embedding")),
        "intelligence": await maybe_await(redis.llen("intelligence")),
    }
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="queue_depth_viewed",
        reason="Viewed worker queue depths.",
    )
    return payload


@router.get("/task-executions")
async def admin_task_executions(
    request: Request,
    status: str | None = Query(default="failed_terminal"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await list_task_executions(db, status=status, limit=limit, offset=offset)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="task_execution_list_viewed",
        reason="Viewed durable task executions.",
    )
    return payload


@router.post("/task-executions/{execution_id}/retry")
async def admin_retry_task_execution(
    request: Request,
    execution_id: uuid.UUID,
    body: AdminTaskActionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    try:
        execution = await retry_terminal_execution(db, execution_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=execution.user_id,
        target_book_id=execution.book_id,
        action_type="task_execution_retried",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"execution_id": str(execution.id)},
    )
    await db.commit()
    return {"id": str(execution.id), "status": execution.status}


@router.post("/task-executions/{execution_id}/dismiss")
async def admin_dismiss_task_execution(
    request: Request,
    execution_id: uuid.UUID,
    body: AdminTaskActionBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    try:
        execution = await dismiss_terminal_execution(
            db, execution_id, admin_user_id=admin_user.id, reason=body.reason
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=execution.user_id,
        target_book_id=execution.book_id,
        action_type="task_execution_dismissed",
        result="allowed",
        reason=body.reason,
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"execution_id": str(execution.id)},
    )
    await db.commit()
    return {"id": str(execution.id), "status": execution.status}


@router.get("/operations-metrics")
async def admin_operations_metrics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await operations_metrics(db)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="operations_metrics_viewed",
        reason="Viewed processing operations metrics.",
    )
    return payload


@router.get("/ai-quality")
async def admin_ai_quality(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await quality_metrics(db)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="ai_quality_viewed",
        reason="Viewed AI quality metrics.",
    )
    return payload


@router.get("/contribution-margin")
async def admin_contribution_margin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    payload = await contribution_margin(db)
    await record_admin_read(
        db=db,
        request=request,
        admin_user=admin_user,
        action_type="contribution_margin_viewed",
        reason="Viewed contribution-margin estimates.",
    )
    return payload


@router.get("/support-incidents")
async def admin_support_incidents(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_super_admin),
):
    rows = (
        await db.execute(
            select(SupportIncident).order_by(SupportIncident.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id) if row.user_id else None,
            "book_id": str(row.book_id) if row.book_id else None,
            "category": row.category,
            "feature": row.feature,
            "severity": row.severity,
            "status": row.status,
            "summary": row.summary,
            "resolution": row.resolution,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/support-incidents")
async def admin_create_support_incident(
    request: Request,
    body: SupportIncidentCreateBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    incident = SupportIncident(
        user_id=body.user_id,
        book_id=body.book_id,
        task_execution_id=body.task_execution_id,
        category=body.category,
        feature=body.feature,
        severity=body.severity,
        summary=body.summary,
        created_by_user_id=admin_user.id,
    )
    db.add(incident)
    await db.flush()
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=body.user_id,
        target_book_id=body.book_id,
        action_type="support_incident_created",
        result="allowed",
        reason=body.summary,
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"incident_id": str(incident.id), "category": body.category},
    )
    await db.commit()
    return {"id": str(incident.id), "status": incident.status}


@router.post("/support-incidents/{incident_id}/resolve")
async def admin_resolve_support_incident(
    request: Request,
    incident_id: uuid.UUID,
    body: SupportIncidentResolveBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin_csrf),
    __: None = Depends(require_admin_step_up),
    admin_user: User = Depends(require_super_admin),
):
    incident = await db.get(SupportIncident, incident_id)
    if incident is None:
        raise HTTPException(404, "Support incident not found")
    incident.status = "resolved"
    incident.resolution = body.resolution
    incident.resolved_at = datetime.now(UTC)
    await record_admin_audit_event(
        db,
        actor_user_id=admin_user.id,
        target_user_id=incident.user_id,
        target_book_id=incident.book_id,
        action_type="support_incident_resolved",
        result="allowed",
        reason=body.resolution,
        request=request,
        scopes_snapshot=admin_scopes_from_request(request),
        metadata={"incident_id": str(incident.id)},
    )
    await db.commit()
    return {"id": str(incident.id), "status": incident.status}
