import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_continuity_checker
from app.core.database import get_db
from app.schemas.books import (
    CanonFactOut,
    ContinuityFindingDecisionBody,
    ContinuityFindingOut,
    ContinuityScanOut,
    ContinuityScanRequest,
)
from app.services.continuity.scan_service import (
    apply_continuity_finding_decision,
    continuity_finding_payload,
    continuity_scan_payload,
    create_and_run_continuity_scan,
    get_canon_facts,
    get_continuity_scan,
    list_continuity_findings,
    recheck_continuity_finding,
)
from app.services.quality_metrics_service import record_quality_review
from app.utils.billing_utils import require_author_access
from app.utils.books.notes import get_owned_book

router = APIRouter()


@router.post("/{book_id}/continuity-scans", response_model=ContinuityScanOut)
async def create_continuity_scan(
    book_id: uuid.UUID,
    body: ContinuityScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _continuity_quota: None = Depends(rate_limit_continuity_checker),
):
    await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    scan = await create_and_run_continuity_scan(
        db,
        book_id=book_id,
        user_id=current_user.id,
        scope=body.scope,
        chapter_numbers=body.chapter_numbers,
    )
    return ContinuityScanOut(**continuity_scan_payload(scan))


@router.get(
    "/{book_id}/continuity-scans/{scan_id}",
    response_model=ContinuityScanOut,
)
async def read_continuity_scan(
    book_id: uuid.UUID,
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    scan = await get_continuity_scan(db, book_id=book_id, scan_id=scan_id)
    return ContinuityScanOut(**continuity_scan_payload(scan))


@router.get("/{book_id}/continuity-findings", response_model=list[ContinuityFindingOut])
async def read_continuity_findings(
    book_id: uuid.UUID,
    status: str | None = Query(None),
    category: str | None = Query(None),
    include_stale: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    findings = await list_continuity_findings(
        db,
        book_id=book_id,
        status=status,
        category=category,
        include_stale=include_stale,
    )
    return [ContinuityFindingOut(**continuity_finding_payload(item)) for item in findings]


@router.patch(
    "/{book_id}/continuity-findings/{finding_id}",
    response_model=ContinuityFindingOut,
)
async def decide_continuity_finding(
    book_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: ContinuityFindingDecisionBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    finding = await apply_continuity_finding_decision(
        db,
        book_id=book_id,
        finding_id=finding_id,
        user_id=current_user.id,
        decision=body.decision,
        action=body.action,
        reason=body.reason,
    )
    record_quality_review(
        db,
        book_id=book_id,
        user_id=current_user.id,
        entity_type="continuity_finding",
        entity_id=finding.id,
        outcome={
            "accepted": "accepted",
            "dismissed": "false_positive",
            "intentional": "intentional_change",
            "resolved": "resolved",
        }[body.decision],
        evidence={
            "extractor_version": finding.detector_version,
            "category": finding.category,
            "severity": finding.severity,
            "reason": body.reason,
            "scan_id": str(finding.scan_id),
        },
    )
    response_payload = continuity_finding_payload(finding)
    await db.commit()
    return ContinuityFindingOut(**response_payload)


@router.post(
    "/{book_id}/continuity-findings/{finding_id}/recheck",
    response_model=ContinuityScanOut,
)
async def recheck_finding(
    book_id: uuid.UUID,
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _continuity_quota: None = Depends(rate_limit_continuity_checker),
):
    await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    scan = await recheck_continuity_finding(
        db,
        book_id=book_id,
        finding_id=finding_id,
        user_id=current_user.id,
    )
    return ContinuityScanOut(**continuity_scan_payload(scan))


@router.get("/{book_id}/canon/facts", response_model=list[CanonFactOut])
async def read_canon_facts(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await get_owned_book(db, book_id, current_user.id)
    require_author_access(current_user)
    facts = await get_canon_facts(db, book_id=book_id)
    return [
        CanonFactOut(
            id=fact.id,
            scan_id=fact.scan_id,
            subject_type=fact.subject_type,
            subject_id=fact.subject_id,
            subject_label=fact.subject_label,
            predicate=fact.predicate,
            normalized_value=fact.normalized_value,
            display_value=fact.display_value,
            chapter_number=fact.chapter_number,
            content_version=fact.content_version,
            evidence_excerpt=fact.evidence_excerpt,
            confidence=fact.confidence,
            extractor_version=fact.extractor_version,
            provenance=fact.provenance or {},
            is_author_confirmed=fact.is_author_confirmed,
        )
        for fact in facts
    ]
