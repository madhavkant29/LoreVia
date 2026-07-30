from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState
from app.models.intelligence import (
    ContinuityFinding,
    ContinuityFindingEvidence,
    ContinuityObservation,
    ContinuityScan,
)
from app.services.continuity.detector_service import DETECTOR_VERSION, generate_findings
from app.services.continuity.observation_service import (
    chapter_versions,
    collect_observations,
    load_chapter_evidence,
)
from app.utils.books import writer_workspace

log = logging.getLogger("lorevia.continuity")


async def create_and_run_continuity_scan(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    scope: str = "full_book",
    chapter_numbers: list[int] | None = None,
) -> ContinuityScan:
    requested_chapters = sorted({int(number) for number in (chapter_numbers or []) if number > 0})
    if scope == "targeted" and not requested_chapters:
        raise HTTPException(400, "Targeted scans require at least one chapter number.")

    dependent_chapters = (
        await _dependent_chapter_numbers(
            db,
            book_id=book_id,
            requested_chapters=requested_chapters,
        )
        if scope == "targeted"
        else None
    )
    scan = ContinuityScan(
        book_id=book_id,
        user_id=user_id,
        scope=scope,
        status="queued",
        continuity_status="insufficient_evidence",
        detector_version=DETECTOR_VERSION,
    )
    db.add(scan)
    await db.flush()
    await db.commit()
    scan_id = scan.id
    scan = await db.get(ContinuityScan, scan_id)
    if scan is None:
        raise RuntimeError("Continuity scan could not be persisted.")
    started = time.perf_counter()
    try:
        await _run_continuity_scan(
            db,
            scan=scan,
            chapter_numbers=dependent_chapters,
            requested_chapter_numbers=requested_chapters if scope == "targeted" else None,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        failed_scan = await db.get(ContinuityScan, scan_id)
        if failed_scan is None:
            raise
        failed_scan.status = "failed"
        failed_scan.continuity_status = "insufficient_evidence"
        failed_scan.error_detail = str(exc)[:2000]
        failed_scan.started_at = failed_scan.started_at or datetime.now(UTC)
        failed_scan.completed_at = datetime.now(UTC)
        failed_scan.duration_ms = max(1, int((time.perf_counter() - started) * 1000))
        failed_scan.metrics = {
            "detector_version": DETECTOR_VERSION,
            "failure_type": type(exc).__name__,
        }
        await db.commit()
        log.exception("continuity_scan_failed scan_id=%s book_id=%s", scan_id, book_id)
    return await get_continuity_scan(db, book_id=book_id, scan_id=scan_id)


async def run_live_canon_guard_if_needed(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    chapter_number: int,
    content_version: int,
    author_mode: bool,
) -> ContinuityScan | None:
    if not author_mode or content_version <= 1:
        return None
    latest_targeted = (
        await db.execute(
            select(ContinuityScan)
            .where(
                ContinuityScan.book_id == book_id,
                ContinuityScan.scope == "targeted",
            )
            .order_by(ContinuityScan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if (
        latest_targeted is not None
        and latest_targeted.status == "ready"
        and (latest_targeted.chapter_versions or {}).get(str(chapter_number)) == content_version
        and chapter_number
        in {
            int(number)
            for number in (latest_targeted.coverage or {}).get(
                "requested_chapter_numbers",
                [],
            )
        }
    ):
        return latest_targeted
    return await create_and_run_continuity_scan(
        db,
        book_id=book_id,
        user_id=user_id,
        scope="targeted",
        chapter_numbers=[chapter_number],
    )


async def _run_continuity_scan(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    chapter_numbers: list[int] | None,
    requested_chapter_numbers: list[int] | None,
) -> None:
    started = time.perf_counter()
    scan.status = "processing"
    scan.started_at = datetime.now(UTC)
    scope_chapters = await load_chapter_evidence(
        db,
        book_id=scan.book_id,
        chapter_numbers=chapter_numbers,
    )
    captured_versions = chapter_versions(scope_chapters)
    scan.chapter_versions = captured_versions
    scan.word_count = sum(chapter.word_count for chapter in scope_chapters)
    requested_set = set(requested_chapter_numbers or [])
    missing_requested_chapters = sorted(
        requested_set - {chapter.number for chapter in scope_chapters if chapter.processed}
    )
    analysis_chapters = (
        []
        if missing_requested_chapters
        else [chapter for chapter in scope_chapters if chapter.processed]
    )

    observations = await collect_observations(
        db,
        scan=scan,
        chapters=analysis_chapters,
    )
    await db.flush()
    exact_citations = sum(
        1 for item in observations if (item.provenance or {}).get("citation_quality") == "exact"
    )
    cited_observations = sum(1 for item in observations if item.evidence_excerpt)
    domain_counts: dict[str, int] = {}
    for observation in observations:
        domain = observation.predicate.split(".", 1)[0]
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    coverage = {
        "chapters_analyzed": len(analysis_chapters),
        "chapters_requested": len(requested_chapter_numbers or scope_chapters),
        "chapter_numbers": [chapter.number for chapter in analysis_chapters],
        "requested_chapter_numbers": requested_chapter_numbers
        or [chapter.number for chapter in scope_chapters],
        "dependent_chapter_numbers": [
            chapter.number
            for chapter in analysis_chapters
            if chapter.number not in set(requested_chapter_numbers or [])
        ],
        "missing_chapter_numbers": [
            *missing_requested_chapters,
            *[
                chapter.number
                for chapter in scope_chapters
                if not chapter.processed and chapter.number not in requested_set
            ],
        ],
        "observation_count": len(observations),
        "domains": domain_counts,
        "citation_coverage": (
            round(cited_observations / len(observations), 4) if observations else 0.0
        ),
        "exact_citation_rate": (
            round(exact_citations / len(observations), 4) if observations else 0.0
        ),
    }
    scan.coverage = coverage
    findings = generate_findings(scan=scan, observations=observations, coverage=coverage)
    for finding in findings:
        db.add(finding)
    await db.flush()

    current_versions = await _current_chapter_versions(
        db,
        book_id=scan.book_id,
        chapter_numbers=[chapter.number for chapter in scope_chapters],
    )
    if current_versions != captured_versions:
        await db.execute(
            delete(ContinuityFindingEvidence).where(
                ContinuityFindingEvidence.finding_id.in_(
                    select(ContinuityFinding.id).where(ContinuityFinding.scan_id == scan.id)
                )
            )
        )
        await db.execute(delete(ContinuityFinding).where(ContinuityFinding.scan_id == scan.id))
        await db.execute(
            delete(ContinuityObservation).where(ContinuityObservation.scan_id == scan.id)
        )
        scan.status = "failed"
        scan.continuity_status = "stale"
        scan.error_detail = (
            "Chapter content changed during the scan; derived evidence was discarded."
        )
    else:
        scan.status = "ready"
        scan.continuity_status = _continuity_status(
            findings=findings,
            coverage=coverage,
        )
        if scan.scope == "full_book":
            is_authoritative = await _claim_full_scan_authority(
                db,
                scan=scan,
                findings=findings,
            )
            if not is_authoritative:
                scan.continuity_status = "stale"
    scan.completed_at = datetime.now(UTC)

    duration_ms = max(1, int((time.perf_counter() - started) * 1000))
    scan.duration_ms = duration_ms
    scan.cost_usd = 0
    scan.metrics = {
        "latency_ms_per_100k_words": (
            round(duration_ms * 100_000 / scan.word_count) if scan.word_count else None
        ),
        "cost_usd_per_100k_words": 0.0,
        "finding_count": len(findings) if scan.status == "ready" else 0,
        "detector_version": DETECTOR_VERSION,
    }


async def get_continuity_scan(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    scan_id: uuid.UUID,
) -> ContinuityScan:
    scan = (
        await db.execute(
            select(ContinuityScan)
            .options(
                selectinload(ContinuityScan.findings)
                .selectinload(ContinuityFinding.evidence)
                .selectinload(ContinuityFindingEvidence.observation)
            )
            .where(ContinuityScan.id == scan_id, ContinuityScan.book_id == book_id)
        )
    ).scalar_one_or_none()
    if scan is None:
        raise HTTPException(404, "Continuity scan not found.")
    return scan


async def list_continuity_findings(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    status: str | None = None,
    category: str | None = None,
    include_stale: bool = True,
) -> list[ContinuityFinding]:
    latest_full_scan = (
        await db.execute(
            select(ContinuityScan)
            .where(
                ContinuityScan.book_id == book_id,
                ContinuityScan.scope == "full_book",
                ContinuityScan.status == "ready",
            )
            .order_by(ContinuityScan.created_at.desc(), ContinuityScan.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    query = (
        select(ContinuityFinding)
        .join(ContinuityScan, ContinuityScan.id == ContinuityFinding.scan_id)
        .options(
            selectinload(ContinuityFinding.evidence).selectinload(
                ContinuityFindingEvidence.observation
            )
        )
        .where(
            ContinuityFinding.book_id == book_id,
            ContinuityFinding.status != "rechecked",
            ContinuityScan.status == "ready",
        )
    )
    if latest_full_scan is not None:
        query = query.where(
            or_(
                ContinuityFinding.scan_id == latest_full_scan.id,
                and_(
                    ContinuityScan.scope == "targeted",
                    ContinuityScan.created_at >= latest_full_scan.created_at,
                ),
            )
        )
    else:
        latest_scan_id = (
            await db.execute(
                select(ContinuityScan.id)
                .where(
                    ContinuityScan.book_id == book_id,
                    ContinuityScan.status == "ready",
                )
                .order_by(ContinuityScan.created_at.desc(), ContinuityScan.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest_scan_id is None:
            return []
        query = query.where(ContinuityFinding.scan_id == latest_scan_id)
    if status:
        query = query.where(ContinuityFinding.status == status)
    if category:
        query = query.where(ContinuityFinding.category == category)
    if not include_stale:
        query = query.where(ContinuityFinding.is_stale.is_(False))
    return list(
        (
            await db.execute(
                query.order_by(
                    ContinuityFinding.is_stale,
                    ContinuityFinding.created_at.desc(),
                )
            )
        )
        .scalars()
        .unique()
        .all()
    )


async def apply_continuity_finding_decision(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    finding_id: uuid.UUID,
    user_id: uuid.UUID,
    decision: str,
    action: str | None,
    reason: str | None,
) -> ContinuityFinding:
    finding = (
        await db.execute(
            select(ContinuityFinding)
            .options(
                selectinload(ContinuityFinding.evidence).selectinload(
                    ContinuityFindingEvidence.observation
                )
            )
            .where(
                ContinuityFinding.id == finding_id,
                ContinuityFinding.book_id == book_id,
            )
        )
    ).scalar_one_or_none()
    if finding is None:
        raise HTTPException(404, "Continuity finding not found.")
    if finding.is_stale:
        raise HTTPException(409, "Stale continuity findings must be rechecked before review.")
    if action == "added_to_revision_plan" and decision != "accepted":
        raise HTTPException(422, "Only accepted findings can be added to the revision plan.")

    if decision == "accepted" and action is None and finding.action == "added_to_revision_plan":
        action = finding.action

    now = datetime.now(UTC)
    finding.decision = decision
    finding.action = action
    finding.reason = reason
    finding.decided_by_user_id = user_id
    finding.decided_at = now
    finding.status = decision
    finding.resolved_at = now if decision == "resolved" else None
    finding.updated_at = now
    if decision == "accepted" and action == "added_to_revision_plan":
        await _create_revision_task_for_finding(
            db,
            finding=finding,
            user_id=user_id,
            now=now,
        )
    elif decision in {"dismissed", "intentional", "resolved"}:
        await _sync_revision_task_for_decision(
            db,
            finding=finding,
            user_id=user_id,
            decision=decision,
            action=action,
            reason=reason,
            now=now,
        )
    await db.flush()
    return finding


async def _create_revision_task_for_finding(
    db: AsyncSession,
    *,
    finding: ContinuityFinding,
    user_id: uuid.UUID,
    now: datetime,
) -> None:
    """Create one durable, idempotent revision task for an accepted finding."""

    book = (
        await db.execute(
            select(Book)
            .where(
                Book.id == finding.book_id,
                Book.user_id == user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if book is None:
        raise HTTPException(404, "Book not found.")

    workspace = writer_workspace.normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    finding_id = str(finding.id)
    task_id = f"continuity-task:{finding_id}"
    now_text = now.isoformat().replace("+00:00", "Z")

    board = writer_workspace._normalize_revision_board(workspace.get("revision_board"))
    board_items = {
        str(item.get("item_id")): item
        for item in board.get("items") or []
        if isinstance(item, dict) and item.get("item_id")
    }
    board_items[finding_id] = {
        **board_items.get(finding_id, {}),
        "item_id": finding_id,
        "status": "task_created",
        "assigned_version_id": board_items.get(finding_id, {}).get("assigned_version_id"),
        "task_id": task_id,
        "updated_at": now_text,
        "decision": "accepted",
        "action": "added_to_revision_plan",
        "reason": finding.reason,
        "source_content_versions": {
            str(key): int(value)
            for key, value in (finding.content_versions or {}).items()
            if str(key).isdigit() and isinstance(value, (int, float))
        },
        "finding_snapshot": {
            "id": finding_id,
            "category": finding.category,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "title": finding.title,
            "explanation": finding.explanation,
            "recommendation": finding.recommendation,
            "subject_type": finding.subject_type,
            "subject_id": finding.subject_id,
            "subject_label": finding.subject_label,
        },
    }
    board["items"] = list(board_items.values())
    board["last_generated_at"] = now_text
    workspace["revision_board"] = board

    calendar_by_id = {
        str(item.get("id")): item
        for item in workspace.get("goal_calendar") or []
        if isinstance(item, dict) and item.get("id")
    }
    calendar_by_id[task_id] = {
        **calendar_by_id.get(task_id, {}),
        "id": task_id,
        "title": finding.title,
        "due_date": now.date().isoformat(),
        "quota_value": 1,
        "quota_unit": "tasks",
        "completed": bool(calendar_by_id.get(task_id, {}).get("completed", False)),
    }
    workspace["goal_calendar"] = list(calendar_by_id.values())
    workspace["activation"] = {
        "completed_at": now_text,
        "completion_action": "added_to_revision_plan",
        "completed_finding_id": finding_id,
    }
    book.writer_workspace = workspace


async def _sync_revision_task_for_decision(
    db: AsyncSession,
    *,
    finding: ContinuityFinding,
    user_id: uuid.UUID,
    decision: str,
    action: str | None,
    reason: str | None,
    now: datetime,
) -> None:
    """Close an existing task when its source finding leaves the accepted state."""

    book = (
        await db.execute(
            select(Book)
            .where(
                Book.id == finding.book_id,
                Book.user_id == user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if book is None:
        raise HTTPException(404, "Book not found.")
    workspace = writer_workspace.normalize_writer_workspace(
        book.writer_workspace if isinstance(book.writer_workspace, dict) else None
    )
    board = writer_workspace._normalize_revision_board(workspace.get("revision_board"))
    finding_id = str(finding.id)
    board_item = next(
        (item for item in board.get("items") or [] if str(item.get("item_id")) == finding_id),
        None,
    )
    if board_item is None or not board_item.get("task_id"):
        return

    now_text = now.isoformat().replace("+00:00", "Z")
    board_item["status"] = "fixed" if decision == "resolved" else "ignored"
    board_item["decision"] = decision
    board_item["action"] = action
    board_item["reason"] = reason
    board_item["updated_at"] = now_text
    board["last_generated_at"] = now_text
    workspace["revision_board"] = board

    task_id = str(board_item["task_id"])
    for task in workspace.get("goal_calendar") or []:
        if str(task.get("id")) == task_id:
            task["completed"] = True
            break
    book.writer_workspace = workspace


async def recheck_continuity_finding(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    finding_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ContinuityScan:
    finding = (
        await db.execute(
            select(ContinuityFinding)
            .options(
                selectinload(ContinuityFinding.evidence).selectinload(
                    ContinuityFindingEvidence.observation
                )
            )
            .where(
                ContinuityFinding.id == finding_id,
                ContinuityFinding.book_id == book_id,
            )
        )
    ).scalar_one_or_none()
    if finding is None:
        raise HTTPException(404, "Continuity finding not found.")
    chapter_numbers = sorted(
        {link.observation.chapter_number for link in finding.evidence if link.observation}
    )
    scan = await create_and_run_continuity_scan(
        db,
        book_id=book_id,
        user_id=user_id,
        scope="targeted",
        chapter_numbers=chapter_numbers,
    )
    if scan.status == "ready":
        finding.is_stale = True
        finding.status = "rechecked"
        await db.commit()
    return scan


async def get_canon_facts(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> list[ContinuityObservation]:
    latest_scan = (
        await db.execute(
            select(ContinuityScan)
            .where(
                ContinuityScan.book_id == book_id,
                ContinuityScan.status == "ready",
                ContinuityScan.scope == "full_book",
            )
            .order_by(ContinuityScan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_scan is None:
        return []
    observations = list(
        (
            await db.execute(
                select(ContinuityObservation)
                .where(ContinuityObservation.scan_id == latest_scan.id)
                .order_by(
                    ContinuityObservation.subject_label,
                    ContinuityObservation.predicate,
                    ContinuityObservation.chapter_number,
                )
            )
        )
        .scalars()
        .all()
    )
    current_versions = await _current_chapter_versions(
        db,
        book_id=book_id,
        chapter_numbers=[
            int(number) for number in (latest_scan.chapter_versions or {}) if str(number).isdigit()
        ],
    )
    return [
        observation
        for observation in observations
        if current_versions.get(str(observation.chapter_number)) == observation.content_version
    ]


async def mark_continuity_findings_stale(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    content_version: int,
) -> int:
    scans = list(
        (
            await db.execute(
                select(ContinuityScan).where(
                    ContinuityScan.book_id == book_id,
                    ContinuityScan.status == "ready",
                )
            )
        )
        .scalars()
        .all()
    )
    affected_scans = [
        scan
        for scan in scans
        if (scan.chapter_versions or {}).get(str(chapter_number)) is not None
        and int((scan.chapter_versions or {})[str(chapter_number)]) != int(content_version)
    ]
    if not affected_scans:
        return 0
    affected_scan_ids = {scan.id for scan in affected_scans}
    for scan in affected_scans:
        scan.continuity_status = "stale"

    findings = list(
        (
            await db.execute(
                select(ContinuityFinding).where(
                    ContinuityFinding.scan_id.in_(affected_scan_ids),
                    ContinuityFinding.is_stale.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    stale_count = 0
    for finding in findings:
        if not _finding_depends_on_chapter(finding, chapter_number):
            continue
        finding.is_stale = True
        stale_count += 1
    return stale_count


def _finding_depends_on_chapter(
    finding: ContinuityFinding,
    chapter_number: int,
) -> bool:
    if str(chapter_number) in (finding.content_versions or {}):
        return True
    checked_range = (finding.coverage or {}).get("checked_chapter_range")
    return (
        isinstance(checked_range, list)
        and len(checked_range) == 2
        and all(isinstance(number, int) for number in checked_range)
        and checked_range[0] <= chapter_number <= checked_range[1]
    )


async def _supersede_prior_full_scans(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
) -> None:
    prior_scans = list(
        (
            await db.execute(
                select(ContinuityScan).where(
                    ContinuityScan.book_id == scan.book_id,
                    ContinuityScan.scope == "full_book",
                    ContinuityScan.id != scan.id,
                    ContinuityScan.status == "ready",
                    or_(
                        ContinuityScan.created_at < scan.created_at,
                        and_(
                            ContinuityScan.created_at == scan.created_at,
                            ContinuityScan.id < scan.id,
                        ),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if not prior_scans:
        return
    prior_scan_ids = {item.id for item in prior_scans}
    for prior_scan in prior_scans:
        prior_scan.continuity_status = "stale"
    prior_findings = list(
        (
            await db.execute(
                select(ContinuityFinding).where(
                    ContinuityFinding.scan_id.in_(prior_scan_ids),
                    ContinuityFinding.is_stale.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    for finding in prior_findings:
        finding.is_stale = True


async def _claim_full_scan_authority(
    db: AsyncSession,
    *,
    scan: ContinuityScan,
    findings: list[ContinuityFinding],
) -> bool:
    # Serialize only the inexpensive authority decision. Observation collection and
    # detection remain concurrent, while the second finisher sees the first
    # finisher's committed state before deciding which result is authoritative.
    await db.execute(select(Book.id).where(Book.id == scan.book_id).with_for_update())
    newer_scan_exists = bool(
        await db.scalar(
            select(ContinuityScan.id)
            .where(
                ContinuityScan.book_id == scan.book_id,
                ContinuityScan.scope == "full_book",
                ContinuityScan.id != scan.id,
                ContinuityScan.status == "ready",
                or_(
                    ContinuityScan.created_at > scan.created_at,
                    and_(
                        ContinuityScan.created_at == scan.created_at,
                        ContinuityScan.id > scan.id,
                    ),
                ),
            )
            .limit(1)
        )
    )
    if newer_scan_exists:
        for finding in findings:
            finding.is_stale = True
        return False
    await _supersede_prior_full_scans(db, scan=scan)
    return True


def continuity_scan_payload(scan: ContinuityScan) -> dict[str, Any]:
    findings = [continuity_finding_payload(finding) for finding in scan.findings]
    return {
        "id": scan.id,
        "book_id": scan.book_id,
        "scope": scan.scope,
        "status": scan.status,
        "continuity_status": scan.continuity_status,
        "detector_version": scan.detector_version,
        "chapter_versions": scan.chapter_versions or {},
        "coverage": scan.coverage or {},
        "metrics": scan.metrics or {},
        "word_count": scan.word_count,
        "duration_ms": scan.duration_ms,
        "cost_usd": float(scan.cost_usd) if scan.cost_usd is not None else None,
        "error_detail": scan.error_detail,
        "finding_count": len(findings),
        "stale_finding_count": sum(1 for finding in scan.findings if finding.is_stale),
        "findings": findings,
        "started_at": scan.started_at,
        "completed_at": scan.completed_at,
        "created_at": scan.created_at,
    }


def continuity_finding_payload(finding: ContinuityFinding) -> dict[str, Any]:
    evidence = [
        {
            "observation_id": link.observation.id,
            "role": link.role,
            "evidence_order": link.evidence_order,
            "subject_type": link.observation.subject_type,
            "subject_id": link.observation.subject_id,
            "subject_label": link.observation.subject_label,
            "predicate": link.observation.predicate,
            "display_value": link.observation.display_value,
            "chapter_number": link.observation.chapter_number,
            "content_version": link.observation.content_version,
            "excerpt": link.observation.evidence_excerpt,
            "confidence": link.observation.confidence,
        }
        for link in sorted(finding.evidence, key=lambda item: item.evidence_order)
    ]
    return {
        "id": finding.id,
        "scan_id": finding.scan_id,
        "book_id": finding.book_id,
        "category": finding.category,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "status": finding.status,
        "title": finding.title,
        "explanation": finding.explanation,
        "recommendation": finding.recommendation,
        "subject_type": finding.subject_type,
        "subject_id": finding.subject_id,
        "subject_label": finding.subject_label,
        "detector_version": finding.detector_version,
        "content_versions": finding.content_versions or {},
        "coverage": finding.coverage or {},
        "is_stale": finding.is_stale,
        "decision": finding.decision,
        "action": finding.action,
        "reason": finding.reason,
        "evidence": evidence,
        "created_at": finding.created_at,
        "updated_at": finding.updated_at,
    }


async def _current_chapter_versions(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_numbers: list[int],
) -> dict[str, int]:
    if not chapter_numbers:
        return {}
    rows = (
        await db.execute(
            select(Chapter.number, Chapter.content_version).where(
                Chapter.book_id == book_id,
                Chapter.number.in_(chapter_numbers),
            )
        )
    ).all()
    return {str(number): version for number, version in rows}


def _continuity_status(
    *,
    findings: list[ContinuityFinding],
    coverage: dict[str, Any],
) -> str:
    if findings:
        return "issues_found"
    if coverage.get("missing_chapter_numbers"):
        return "insufficient_evidence"
    if coverage.get("chapters_analyzed", 0) > 0 and coverage.get("observation_count", 0) > 0:
        return "clean"
    return "insufficient_evidence"


async def _dependent_chapter_numbers(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    requested_chapters: list[int],
) -> list[int]:
    """Expand targeted edits to prior/later state evidence for affected identities."""
    if not requested_chapters:
        return []
    character_ids = set(
        (
            await db.execute(
                select(CharacterState.character_id)
                .join(Character, Character.id == CharacterState.character_id)
                .where(
                    Character.book_id == book_id,
                    CharacterState.at_chapter.in_(requested_chapters),
                )
            )
        )
        .scalars()
        .all()
    )
    dependent = set(requested_chapters)
    if character_ids:
        dependent.update(
            (
                await db.execute(
                    select(CharacterState.at_chapter).where(
                        CharacterState.character_id.in_(character_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
    return sorted(int(number) for number in dependent if int(number) > 0)
