from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import BetaReadAssignment
from app.models.book import Book
from app.models.user import User
from app.schemas.beta_reads import BetaReadAssignmentDetailOut, BetaReadAssignmentOut
from app.utils.beta_read_access_utils import _reader_match_clause, sync_reader_identity_for_beta_reads
from app.utils.beta_read_feedback_utils import (
    _serialize_beta_read_feedback_items,
    _serialize_beta_read_questions,
    beta_feedback_summary,
)
from app.utils.beta_read_output_utils import (
    _build_beta_read_assignment_out_from_context,
    load_beta_assignment_render_context,
)
from app.utils.beta_read_policy_utils import READER_VISIBLE_STATES, utc_now
from app.utils.beta_read_lifecycle_utils import expire_beta_assignment_if_due


async def build_beta_read_assignment_out(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User | None = None,
    reader_user: User | None = None,
) -> BetaReadAssignmentOut:
    context = await load_beta_assignment_render_context(db, assignments=[assignment])
    return _build_beta_read_assignment_out_from_context(
        assignment,
        context=context,
        current_user=current_user,
        reader_user=reader_user,
    )


async def build_beta_read_assignment_detail_out(
    db: AsyncSession,
    *,
    assignment: BetaReadAssignment,
    current_user: User | None = None,
    reader_user: User | None = None,
) -> BetaReadAssignmentDetailOut:
    assignment_out = await build_beta_read_assignment_out(
        db,
        assignment=assignment,
        current_user=current_user,
        reader_user=reader_user,
    )
    return BetaReadAssignmentDetailOut(
        assignment=assignment_out,
        author_questions=await _serialize_beta_read_questions(db, assignment_id=assignment.id),
        feedback_items=await _serialize_beta_read_feedback_items(db, assignment_id=assignment.id),
        feedback_summary=await beta_feedback_summary(db, assignment_id=assignment.id),
    )


async def list_reader_beta_read_assignments(
    db: AsyncSession,
    *,
    current_user: User,
    bucket: str | None = None,
    upcoming_only: bool = False,
) -> list[BetaReadAssignmentOut]:
    await sync_reader_identity_for_beta_reads(db, current_user)
    now = utc_now()
    assignments = (
        (
            await db.execute(
                select(BetaReadAssignment)
                .where(
                    _reader_match_clause(current_user),
                    BetaReadAssignment.state.in_(list(READER_VISIBLE_STATES)),
                )
                .order_by(BetaReadAssignment.expires_at.asc(), BetaReadAssignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    changed = False
    for assignment in assignments:
        changed = await expire_beta_assignment_if_due(db, assignment=assignment, now=now) or changed
    context = await load_beta_assignment_render_context(db, assignments=assignments)
    items: list[BetaReadAssignmentOut] = []
    for assignment in assignments:
        item = _build_beta_read_assignment_out_from_context(
            assignment,
            context=context,
            current_user=current_user,
        )
        if upcoming_only and item.view_bucket not in {"active", "scheduled"}:
            continue
        if bucket and item.view_bucket != bucket:
            continue
        items.append(item)
    if changed:
        await db.commit()
    return items


async def list_book_beta_read_assignments(
    db: AsyncSession,
    *,
    book: Book,
    author_user_id: uuid.UUID,
) -> list[BetaReadAssignmentOut]:
    now = utc_now()
    assignments = (
        (
            await db.execute(
                select(BetaReadAssignment)
                .where(
                    BetaReadAssignment.book_id == book.id,
                    BetaReadAssignment.author_user_id == author_user_id,
                )
                .order_by(BetaReadAssignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    changed = False
    for assignment in assignments:
        changed = await expire_beta_assignment_if_due(db, assignment=assignment, now=now) or changed
    context = await load_beta_assignment_render_context(db, assignments=assignments)
    items: list[BetaReadAssignmentOut] = []
    for assignment in assignments:
        reader_user = (
            context.readers_by_id.get(assignment.reader_user_id)
            if assignment.reader_user_id
            else None
        )
        items.append(
            _build_beta_read_assignment_out_from_context(
                assignment,
                context=context,
                reader_user=reader_user,
            )
        )
    if changed:
        await db.commit()
    return items
