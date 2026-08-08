import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str | None = None
    tier: str
    reading_mode: str
    daily_word_goal: int
    today_word_count: int
    last_login_at: datetime | None = None
    login_streak_days: int
    longest_login_streak_days: int
    login_activity_dates: list[date] = Field(default_factory=list)
    created_at: datetime


ComplexityModeLiteral = Literal["focused", "standard", "power"]
BookPresetLiteral = Literal["draft", "review", "story_bible", "share", "all"]
ToolAccessLiteral = Literal[
    "available",
    "plan_locked",
    "permission_denied",
    "processing_blocked",
]
ToolVisibilityLiteral = Literal[
    "visible",
    "preset_hidden",
    "user_hidden",
    "temporarily_revealed",
]
UiPreferenceOperationLiteral = Literal["set", "unset"]
UiPreferenceImportModeLiteral = Literal["merge", "replace"]


class UiPreferenceOperation(BaseModel):
    op: UiPreferenceOperationLiteral
    path: str = Field(..., min_length=1, max_length=160)
    value: Any = None


class UserUiPreferencePatch(BaseModel):
    base_revision: int = Field(..., ge=1)
    operations: list[UiPreferenceOperation] = Field(default_factory=list, max_length=100)


class UserBookUiPreferencePatch(UserUiPreferencePatch):
    pass


class UserUiPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_version: int
    revision: int
    complexity_mode: ComplexityModeLiteral
    dashboard_visibility: dict[str, ToolVisibilityLiteral | bool] = Field(default_factory=dict)
    dashboard_order: list[str] = Field(default_factory=list)
    public_tool_visibility: dict[str, ToolVisibilityLiteral | bool] = Field(default_factory=dict)
    density: str = "comfortable"
    reader_toolbar_density: str = "standard"
    locked_tool_presentation: str = "compact"
    default_workspace_shell: Literal["reader", "author"] = "reader"
    mobile_actions: list[str] = Field(default_factory=list)
    guidance_dismissals: dict[str, Any] = Field(default_factory=dict)
    recommendation_snoozes: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None


class UserBookUiPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    book_id: uuid.UUID
    schema_version: int
    revision: int
    book_preset: BookPresetLiteral
    advanced_tool_override: Literal["show", "hide"] | None = None
    hidden_book_tools: list[str] = Field(default_factory=list)
    overview_cards: dict[str, ToolVisibilityLiteral | bool] = Field(default_factory=dict)
    reader_actions: list[str] = Field(default_factory=list)
    mobile_actions: list[str] = Field(default_factory=list)
    panel_state: dict[str, Any] = Field(default_factory=dict)
    timeline_collapsed_sections: dict[str, bool] = Field(default_factory=dict)
    updated_at: datetime | None = None


class UserUiPreferenceExportOut(BaseModel):
    schema_version: int = 1
    global_preferences: UserUiPreferenceOut
    book_preferences: list[UserBookUiPreferenceOut] = Field(default_factory=list)


class UserUiPreferenceImportBody(BaseModel):
    mode: UiPreferenceImportModeLiteral = "merge"
    confirm_replace: bool = False
    global_preferences: dict[str, Any] | None = None
    book_preferences: list[dict[str, Any]] = Field(default_factory=list, max_length=500)


class UserUiPreferenceImportOut(BaseModel):
    imported: bool
    mode: UiPreferenceImportModeLiteral
    global_revision: int
    book_preferences_updated: int = 0
