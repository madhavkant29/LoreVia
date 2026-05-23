from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmailPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    product_updates: bool
    marketing: bool
    unsubscribed_all: bool
    unsubscribed_at: datetime | None = None


class EmailPreferenceUpdateBody(BaseModel):
    product_updates: bool
    marketing: bool


class EmailPreferenceTokenViewOut(EmailPreferenceOut):
    preferences_url: str | None = None


class EmailUnsubscribeBody(BaseModel):
    token: str


class EmailUnsubscribeOut(BaseModel):
    ok: bool = True
    email: str
    product_updates: bool
    marketing: bool
    unsubscribed_all: bool
