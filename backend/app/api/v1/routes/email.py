from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.email import (
    EmailPreferenceOut,
    EmailPreferenceTokenViewOut,
    EmailPreferenceUpdateBody,
    EmailUnsubscribeBody,
    EmailUnsubscribeOut,
)
from app.utils.auth_utils import normalize_email
from app.utils.email_utils import (
    consume_unsubscribe_token,
    get_email_preference_by_email,
    get_or_create_email_preference,
    resolve_preferences_token,
    unsubscribe_all_promotional_email,
    update_email_preferences,
)

router = APIRouter()


@router.get("/preferences", response_model=EmailPreferenceTokenViewOut)
async def get_email_preferences(
    response: Response,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if token:
        payload = await resolve_preferences_token(token)
        if not payload:
            raise HTTPException(400, "Invalid or expired preferences token")
        email = normalize_email(payload.get("email", ""))
        if not email:
            raise HTTPException(400, "Invalid or expired preferences token")
        user = (
            await db.execute(select(User).where(func.lower(User.email) == email))
        ).scalar_one_or_none()
        if user is None:
            raise HTTPException(404, "User not found")
        preference = await get_or_create_email_preference(db, user=user, email=email)
        await db.commit()
        await db.refresh(preference)
        return EmailPreferenceTokenViewOut.model_validate(preference)

    if current_user is None:
        raise HTTPException(401, "Authentication required")

    preference = await get_or_create_email_preference(db, user=current_user)
    await db.commit()
    await db.refresh(preference)
    return EmailPreferenceTokenViewOut.model_validate(preference)


@router.post("/preferences", response_model=EmailPreferenceOut)
async def save_email_preferences(
    body: EmailPreferenceUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = await update_email_preferences(
        db,
        user=current_user,
        product_updates=body.product_updates,
        marketing=body.marketing,
    )
    return EmailPreferenceOut.model_validate(updated)


@router.post("/unsubscribe", response_model=EmailUnsubscribeOut)
async def unsubscribe_email(
    body: EmailUnsubscribeBody | None = None,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    unsubscribe_token = token or (body.token if body else None)
    if not unsubscribe_token:
        raise HTTPException(400, "Unsubscribe token is required")

    payload = await consume_unsubscribe_token(unsubscribe_token)
    if not payload:
        raise HTTPException(400, "Invalid or expired unsubscribe token")

    email = normalize_email(payload.get("email", ""))
    if not email:
        raise HTTPException(400, "Invalid or expired unsubscribe token")

    user = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if user is None:
        preference = await get_email_preference_by_email(db, email)
        if preference is None:
            raise HTTPException(404, "User not found")
        raise HTTPException(400, "Unable to unsubscribe this email address")

    updated = await unsubscribe_all_promotional_email(db, user=user)
    return EmailUnsubscribeOut(
        email=updated.email,
        product_updates=updated.product_updates,
        marketing=updated.marketing,
        unsubscribed_all=updated.unsubscribed_all,
    )
