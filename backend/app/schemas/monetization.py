from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PointLedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entry_type: str
    source_type: str
    source_id: str | None = None
    points_delta: int
    expires_at: datetime | None = None
    metadata_json: dict = Field(default_factory=dict)
    created_at: datetime


class PointsBalanceOut(BaseModel):
    balance: int


class PointSpendOfferOut(BaseModel):
    code: str
    action: str
    title: str
    description: str
    points_cost: int
    units: int
    eligible: bool
    reason: str | None = None


class PointSpendOffersOut(BaseModel):
    offers: list[PointSpendOfferOut]


class ReferralOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    referral_code: str
    status: str
    qualified_at: datetime | None = None
    rewarded_at: datetime | None = None
    created_at: datetime


class ReferralSummaryOut(BaseModel):
    referral_code: str
    referral_url: str | None = None
    points_balance: int
    rewards: list[ReferralOut]


class ApplyReferralBody(BaseModel):
    referral_code: str = Field(..., min_length=3, max_length=64)


class SpendPointsBody(BaseModel):
    offer_code: str = Field(..., min_length=3, max_length=64)


class SpendPointsOut(BaseModel):
    balance: int
    purchased_units_today: int
    offer: PointSpendOfferOut
    confirmation_message: str


class RewardedAdStatusOut(BaseModel):
    enabled: bool
    provider: str
    reward_points: int
    daily_cap: int
    claims_used_today: int
    claims_remaining_today: int
    session_ttl_seconds: int
    min_grant_seconds: int
    reason: str | None = None


class StartRewardedAdSessionBody(BaseModel):
    placement: str = Field(..., min_length=2, max_length=64)


class StartRewardedAdSessionOut(BaseModel):
    session_token: str
    provider: str
    reward_points: int
    ad_unit_path: str
    expires_at: datetime
    claims_remaining_today: int


class ResolveRewardedAdSessionBody(BaseModel):
    session_token: str = Field(..., min_length=16, max_length=128)
    outcome: str = Field(..., min_length=4, max_length=32)
    reward_type: str | None = Field(default=None, max_length=64)
    reward_amount: int | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None, max_length=240)


class ResolveRewardedAdSessionOut(BaseModel):
    status: str
    balance: int
    reward_points_granted: int
    claims_remaining_today: int
    confirmation_message: str
