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
