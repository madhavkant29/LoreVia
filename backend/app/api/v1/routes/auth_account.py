from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.v1.routes.auth_shared import (
    _build_user_out,
    _record_login_activity,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AccountDeletionBody,
    AccountDeletionOut,
    DailyWordGoalBody,
    MessagingPermissionBody,
    TierLimitsOut,
    UserOut,
)
from app.schemas.user import (
    UserBookUiPreferenceOut,
    UserBookUiPreferencePatch,
    UserUiPreferenceExportOut,
    UserUiPreferenceImportBody,
    UserUiPreferenceImportOut,
    UserUiPreferenceOut,
    UserUiPreferencePatch,
)
from app.services.privacy_service import build_user_data_export, request_account_deletion
from app.services.user_ui_preferences_service import (
    PreferenceConflictError,
    PreferenceValidationError,
    export_user_ui_preferences,
    get_or_create_user_book_ui_preference,
    get_or_create_user_ui_preference,
    import_user_ui_preferences,
    patch_user_book_ui_preference,
    patch_user_ui_preference,
    serialize_user_book_ui_preference,
    serialize_user_ui_preference,
)
from app.utils.auth_cookies import clear_auth_cookies, get_device_cookie
from app.utils.auth_utils import next_token_version
from app.utils.cookie_utils import auth_cookie_secure

router = APIRouter()


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.token_version = next_token_version(current_user)
    await db.commit()
    clear_auth_cookies(response)
    response.set_cookie(
        key="lorevia_session_dead",
        value="1",
        max_age=30,
        path="/",
        secure=auth_cookie_secure(),
        samesite="lax",
    )
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _record_login_activity(db, current_user, device_id=get_device_cookie(request))
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


@router.get("/me/data-export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await build_user_data_export(db, current_user)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="lorevia-data-export.zip"'},
    )


@router.get("/me/ui-preferences", response_model=UserUiPreferenceOut)
async def get_my_ui_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await get_or_create_user_ui_preference(db, current_user)
    await db.commit()
    await db.refresh(preference)
    return serialize_user_ui_preference(preference)


@router.patch("/me/ui-preferences", response_model=UserUiPreferenceOut)
async def update_my_ui_preferences(
    body: UserUiPreferencePatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        preference = await patch_user_ui_preference(db, current_user, body)
    except PreferenceConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=jsonable_encoder(
                {
                    "detail": "Preference revision conflict.",
                    "latest_revision": exc.conflict.latest_revision,
                    "latest": exc.conflict.latest,
                }
            ),
        )
    except PreferenceValidationError as exc:
        raise HTTPException(400, str(exc))
    await db.commit()
    await db.refresh(preference)
    return serialize_user_ui_preference(preference)


@router.get(
    "/me/ui-preferences/books/{book_id}",
    response_model=UserBookUiPreferenceOut,
)
async def get_my_book_ui_preferences(
    book_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    preference = await get_or_create_user_book_ui_preference(db, current_user, book_id)
    await db.commit()
    await db.refresh(preference)
    return serialize_user_book_ui_preference(preference)


@router.patch(
    "/me/ui-preferences/books/{book_id}",
    response_model=UserBookUiPreferenceOut,
)
async def update_my_book_ui_preferences(
    book_id: uuid.UUID,
    body: UserBookUiPreferencePatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        preference = await patch_user_book_ui_preference(db, current_user, book_id, body)
    except PreferenceConflictError as exc:
        return JSONResponse(
            status_code=409,
            content=jsonable_encoder(
                {
                    "detail": "Preference revision conflict.",
                    "latest_revision": exc.conflict.latest_revision,
                    "latest": exc.conflict.latest,
                }
            ),
        )
    except PreferenceValidationError as exc:
        raise HTTPException(400, str(exc))
    await db.commit()
    await db.refresh(preference)
    return serialize_user_book_ui_preference(preference)


@router.get("/me/ui-preferences/export", response_model=UserUiPreferenceExportOut)
async def export_my_ui_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await export_user_ui_preferences(db, current_user)
    await db.commit()
    return payload


@router.post("/me/ui-preferences/import", response_model=UserUiPreferenceImportOut)
async def import_my_ui_preferences(
    body: UserUiPreferenceImportBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await import_user_ui_preferences(db, current_user, body)
    except PreferenceValidationError as exc:
        raise HTTPException(400, str(exc))
    await db.commit()
    return result


@router.delete("/me", response_model=AccountDeletionOut)
async def delete_my_account(
    body: AccountDeletionBody,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    request, provider_followup_required = await request_account_deletion(
        db,
        current_user,
        confirmation_text=body.confirmation_text,
        password=body.password,
    )
    clear_auth_cookies(response)
    response.set_cookie(
        key="lorevia_session_dead",
        value="1",
        max_age=30,
        path="/",
        secure=auth_cookie_secure(),
        samesite="lax",
    )
    return AccountDeletionOut(
        deletion_status=current_user.deletion_status,
        scheduled_for=request.scheduled_for,
        provider_followup_required=provider_followup_required,
    )


@router.patch("/me/reading-mode", response_model=UserOut)
async def set_reading_mode(
    mode: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if mode not in ("casual", "analyst", "speed"):
        raise HTTPException(400, "Invalid mode")
    current_user.reading_mode = mode
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


@router.patch("/me/daily-word-goal", response_model=UserOut)
async def set_daily_word_goal(
    body: DailyWordGoalBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.daily_word_goal = body.daily_word_goal
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


@router.patch("/me/messaging-permission", response_model=UserOut)
async def set_messaging_permission(
    body: MessagingPermissionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.messaging_permission = body.messaging_permission
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


@router.get("/tier-limits", response_model=TierLimitsOut)
async def get_tier_limits():
    """Return configured tier limits from backend config."""
    return TierLimitsOut(
        free_max_books=settings.FREE_MAX_BOOKS,
        author_max_uploads=settings.AUTHOR_MAX_UPLOADS,
        architect_uploads_unlimited=True,
        free_total_token_budget=settings.FREE_TOTAL_TOKEN_BUDGET,
        free_search_per_day=settings.FREE_SEARCH_PER_DAY,
        free_summary_per_hour=settings.FREE_SUMMARY_PER_HOUR,
        free_prediction_per_day=settings.FREE_PREDICTION_PER_DAY,
        free_recall_per_day=settings.FREE_RECALL_PER_DAY,
        author_prediction_per_day=settings.AUTHOR_PREDICTION_PER_DAY,
        architect_prediction_per_day=settings.ARCHITECT_PREDICTION_PER_DAY,
        trial_high_cost_turns_per_day=settings.TRIAL_HIGH_COST_TURNS_PER_DAY,
        author_high_cost_turns_per_day=settings.AUTHOR_HIGH_COST_TURNS_PER_DAY,
        architect_high_cost_turns_per_day=settings.ARCHITECT_HIGH_COST_TURNS_PER_DAY,
        free_advisor_per_day=settings.FREE_ADVISOR_PER_DAY,
        free_advisor_per_week=settings.FREE_ADVISOR_PER_WEEK,
        free_advisor_per_month=settings.FREE_ADVISOR_PER_MONTH,
        free_continuity_per_day=settings.FREE_CONTINUITY_PER_DAY,
        author_advisor_per_day=settings.AUTHOR_ADVISOR_PER_DAY,
        author_advisor_per_week=settings.AUTHOR_ADVISOR_PER_WEEK,
        author_advisor_per_month=settings.AUTHOR_ADVISOR_PER_MONTH,
        architect_advisor_per_day=settings.ARCHITECT_ADVISOR_PER_DAY,
        architect_advisor_per_week=settings.ARCHITECT_ADVISOR_PER_WEEK,
        architect_advisor_per_month=settings.ARCHITECT_ADVISOR_PER_MONTH,
        free_continuity_per_minute=settings.FREE_CONTINUITY_PER_MINUTE,
        author_continuity_per_minute=settings.AUTHOR_CONTINUITY_PER_MINUTE,
        architect_continuity_per_minute=settings.ARCHITECT_CONTINUITY_PER_MINUTE,
    )


@router.patch("/me/username", response_model=UserOut)
async def set_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the current user's public username."""

    username = (username or "").strip().lower()
    if not username or len(username) < 3 or len(username) > 32:
        raise HTTPException(400, "Username must be 3-32 characters")

    if not all(c.isalnum() or c in "_-" for c in username):
        raise HTTPException(
            400, "Username can only contain letters, numbers, underscores, and hyphens"
        )

    existing = (
        await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    ).scalar()
    if existing and existing.id != current_user.id:
        raise HTTPException(400, "Username already taken")

    current_user.username = username
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)
