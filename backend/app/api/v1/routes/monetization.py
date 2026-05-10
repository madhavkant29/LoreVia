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
    PointSpendOfferOut,
    PointSpendOffersOut,
    PointsBalanceOut,
    ReferralSummaryOut,
    ResolveRewardedAdSessionBody,
    ResolveRewardedAdSessionOut,
    RewardedAdStatusOut,
    StartRewardedAdSessionBody,
    StartRewardedAdSessionOut,
    SpendPointsBody,
    SpendPointsOut,
)
from app.services.monetization_service import (
    create_referral_if_valid,
    ensure_referral_code,
    expire_due_points_for_user,
    point_balance,
    point_spend_offers_for_user,
    resolve_rewarded_ad_session,
    rewarded_ad_status_for_user,
    start_rewarded_ad_session,
    spend_points_on_offer,
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


@router.get("/offers", response_model=PointSpendOffersOut)
async def get_point_spend_offers(
    current_user: User = Depends(get_current_user),
):
    offers = [PointSpendOfferOut(**offer) for offer in point_spend_offers_for_user(current_user)]
    return PointSpendOffersOut(offers=offers)


@router.get("/rewarded-ads/status", response_model=RewardedAdStatusOut)
async def get_rewarded_ad_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await rewarded_ad_status_for_user(db, current_user)
    await db.commit()
    return RewardedAdStatusOut(**payload)


@router.post("/rewarded-ads/session", response_model=StartRewardedAdSessionOut)
async def create_rewarded_ad_session(
    body: StartRewardedAdSessionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = await start_rewarded_ad_session(db, current_user, body.placement)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return StartRewardedAdSessionOut(**payload)


@router.post("/rewarded-ads/resolve", response_model=ResolveRewardedAdSessionOut)
async def finalize_rewarded_ad_session(
    body: ResolveRewardedAdSessionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = await resolve_rewarded_ad_session(
            db,
            current_user,
            session_token=body.session_token,
            outcome=body.outcome,
            reward_type=body.reward_type,
            reward_amount=body.reward_amount,
            error_message=body.error_message,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return ResolveRewardedAdSessionOut(**payload)


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


@router.post("/points/spend", response_model=SpendPointsOut)
async def spend_points(
    body: SpendPointsBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        payload = await spend_points_on_offer(db, current_user, body.offer_code)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    return SpendPointsOut(
        balance=payload["balance"],
        purchased_units_today=payload["purchased_units_today"],
        offer=PointSpendOfferOut(**payload["offer"]),
        confirmation_message=payload["confirmation_message"],
    )


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
