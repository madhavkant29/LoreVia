from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SupportWorkspace = Literal["reader", "author"]


class SupportUiContext(BaseModel):
    """Strict allowlist of diagnostics that may leave the browser for support."""

    route: str = Field(default="/", max_length=300)
    tool_id: str | None = Field(default=None, max_length=100)
    workspace_shell: SupportWorkspace | None = None
    account_tier: str | None = Field(default=None, max_length=40)
    capability_flags: list[str] = Field(default_factory=list, max_length=30)
    processing_state: str | None = Field(default=None, max_length=80)
    save_state: str | None = Field(default=None, max_length=80)
    error_code: str | None = Field(default=None, max_length=80)
    request_id: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=60)
    device_class: Literal["desktop", "tablet", "mobile", "unknown"] = "unknown"
    book_id: uuid.UUID | None = None

    @field_validator("capability_flags")
    @classmethod
    def normalize_capability_flags(cls, values: list[str]) -> list[str]:
        return sorted({value.strip()[:80] for value in values if value.strip()})


class SupportRecentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class SupportChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    recent_messages: list[SupportRecentMessage] = Field(default_factory=list, max_length=10)
    context: SupportUiContext = Field(default_factory=SupportUiContext)


class SupportSourceOut(BaseModel):
    slug: str
    title: str
    summary: str
    url: str


class SupportActionOut(BaseModel):
    label: str
    href: str
    external: bool = False


class SupportAnswerOut(BaseModel):
    answer: str
    sources: list[SupportSourceOut] = Field(default_factory=list)
    actions: list[SupportActionOut] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    escalation_available: bool = True
    declined: bool = False


class SupportIncidentCreateBody(BaseModel):
    confirmed: Literal[True]
    category: Literal[
        "navigation",
        "chapter_save",
        "upload",
        "processing",
        "billing",
        "permissions",
        "account",
        "other",
    ] = "other"
    feature: str | None = Field(default=None, max_length=100)
    summary: str = Field(min_length=5, max_length=1000)
    context: SupportUiContext = Field(default_factory=SupportUiContext)


class SupportIncidentOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    category: str
    feature: str | None = None
    summary: str
    resolution: str | None = None
    created_at: datetime


class SupportConfigOut(BaseModel):
    assistant_enabled: bool
    community_url: str | None = None
    corpus_version: str
