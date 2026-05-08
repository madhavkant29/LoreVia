from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import PointLedgerEntry, Referral, User
from app.schemas.monetization import (
    ApplyReferralBody,
    PointLedgerEntryOut,
    PointsBalanceOut,
    ReferralSummaryOut,
)
from app.services.monetization_service import (
    create_referral_if_valid,
    ensure_referral_code,
    expire_due_points_for_user,
    point_balance,
)

router = APIRouter()


@router.get("/points", response_model=PointsBalanceOut)
async def get_points_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await expire_due_points_for_user(db, current_user.id)
    await db.commit()
    return PointsBalanceOut(balance=await point_balance(db, current_user.id))


@router.get("/points/ledger", response_model=list[PointLedgerEntryOut])
async def get_points_ledger(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await expire_due_points_for_user(db, current_user.id)
    await db.commit()
    entries = (
        await db.execute(
            select(PointLedgerEntry)
            .where(PointLedgerEntry.user_id == current_user.id)
            .order_by(PointLedgerEntry.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return entries


@router.get("/referrals", response_model=ReferralSummaryOut)
async def get_referrals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await expire_due_points_for_user(db, current_user.id)
    referral_code = await ensure_referral_code(db, current_user)
    rewards = (
        await db.execute(
            select(Referral)
            .where(Referral.referrer_user_id == current_user.id)
            .order_by(Referral.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    await db.commit()
    app_url = settings.APP_URL.rstrip("/")
    return ReferralSummaryOut(
        referral_code=referral_code,
        referral_url=f"{app_url}/register?ref={referral_code}",
        points_balance=await point_balance(db, current_user.id),
        rewards=rewards,
    )


@router.post("/referrals/apply", response_model=ReferralSummaryOut)
async def apply_referral(
    body: ApplyReferralBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    referral = await create_referral_if_valid(db, current_user, body.referral_code)
    if referral is None:
        raise HTTPException(400, "Invalid referral code.")
    await ensure_referral_code(db, current_user)
    await db.commit()
    await db.refresh(current_user)
    return await get_referrals(db, current_user)
