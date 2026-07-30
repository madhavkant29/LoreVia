import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_optional_current_user
from app.api.deps.rate_limit import rate_limit_public_report
from app.core.database import get_db
from app.models.book import Book
from app.models.intelligence import Notification
from app.models.moderation import ContentReport
from app.models.user import User
from app.schemas.public import ContentReportCreateBody, ContentReportOut
from app.utils.client_identity import trusted_client_ip
from app.utils.public.moderation import (
    add_moderation_action,
    copyright_report_requires_temporary_hold,
    ensure_public_content_report_not_duplicate,
    ensure_report_type_supported,
    invalidate_public_book_caches,
    validate_public_content_report_target,
)
from app.utils.public.requests import (
    hash_text,
)
from app.utils.public_utils import (
    MODERATION_STATUS_HIDDEN,
    MODERATION_STATUS_REPORTED,
    PUBLIC_STATUS_HIDDEN,
    REPORT_STATUS_CONTENT_HIDDEN,
    REPORT_STATUS_OPEN,
    REPORT_TYPE_COPYRIGHT,
)

router = APIRouter()


@router.post(
    "/content",
    response_model=ContentReportOut,
    status_code=201,
    dependencies=[Depends(rate_limit_public_report)],
)
async def create_content_report(
    body: ContentReportCreateBody,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_current_user),
):
    report_type = ensure_report_type_supported(body.report_type)
    book = await db.get(Book, body.book_id)
    reported_content_url = validate_public_content_report_target(book, body.reported_content_url)
    if report_type == REPORT_TYPE_COPYRIGHT and not body.reporter_email:
        raise HTTPException(400, "Copyright reports must include a reporter email.")
    reporter_ip_hash = hash_text(trusted_client_ip(request))
    await ensure_public_content_report_not_duplicate(
        db,
        book_id=book.id,
        report_type=report_type,
        reporter_ip_hash=reporter_ip_hash,
    )

    report = ContentReport(
        reporter_user_id=current_user.id if current_user is not None else None,
        reporter_email=body.reporter_email,
        reporter_ip_hash=reporter_ip_hash,
        reported_book_id=book.id,
        reported_author_user_id=book.user_id,
        report_type=report_type,
        status=REPORT_STATUS_OPEN,
        reason=body.reason.strip(),
        details=(body.details or "").strip() or None,
        copyright_owner_name=(body.copyright_owner_name or "").strip() or None,
        copyright_work_description=(body.copyright_work_description or "").strip() or None,
        copyright_original_url=(body.copyright_original_url or "").strip() or None,
        reported_content_url=reported_content_url,
    )
    db.add(report)
    await db.flush()
    await add_moderation_action(
        db,
        action_type="report_created",
        actor_user_id=current_user.id if current_user is not None else None,
        target_user_id=book.user_id,
        book_id=book.id,
        report_id=report.id,
        previous_status=str(getattr(book, "moderation_status", "") or "") or None,
        new_status=MODERATION_STATUS_REPORTED,
        reason=report.reason,
        metadata={"report_type": report_type},
    )

    should_hide = (
        report_type == REPORT_TYPE_COPYRIGHT
        and await copyright_report_requires_temporary_hold(db, book_id=book.id)
    )
    if should_hide:
        book.moderation_status = MODERATION_STATUS_HIDDEN
        book.public_status = PUBLIC_STATUS_HIDDEN
        book.is_public = False
        book.takedown_reason = body.reason.strip()
        report.status = REPORT_STATUS_CONTENT_HIDDEN
        await add_moderation_action(
            db,
            action_type="book_hidden",
            actor_user_id=current_user.id if current_user is not None else None,
            target_user_id=book.user_id,
            book_id=book.id,
            report_id=report.id,
            previous_status=MODERATION_STATUS_REPORTED,
            new_status=MODERATION_STATUS_HIDDEN,
            reason="Book temporarily hidden after three distinct copyright reporters within 24 hours.",
        )
    else:
        book.moderation_status = MODERATION_STATUS_REPORTED

    admin_ids = (await db.execute(select(User.id).where(User.tier == "admin"))).scalars().all()
    for admin_id in admin_ids:
        db.add(
            Notification(
                user_id=admin_id,
                book_id=book.id,
                kind="content_report_created",
                title="New public book report",
                body="A public book was reported and may need moderation review.",
                data={
                    "report_id": str(report.id),
                    "book_id": str(book.id),
                    "report_type": report_type,
                },
            )
        )

    await db.commit()
    if should_hide:
        await invalidate_public_book_caches(book)
    return ContentReportOut(
        id=str(report.id),
        status=report.status,
        report_type=report.report_type,
        reported_book_id=str(report.reported_book_id),
        created_at=report.created_at,
        message="Thank you. We will review this report and may remove or restrict the content if it violates our policies.",
    )
