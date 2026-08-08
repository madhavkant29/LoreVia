from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.user import UserUiPreference
from app.schemas.user import (
    UiPreferenceOperation,
    UserUiPreferenceImportBody,
    UserUiPreferencePatch,
)
from app.services import user_ui_preferences_service as service


class FakeScalarResult:
    def __init__(self, rows=None):
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.added = []
        self.flushed = 0

    async def execute(self, _statement):
        return FakeScalarResult(self.rows)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed += 1


def user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.mark.asyncio
async def test_get_or_create_user_ui_preference_defaults_new_users_to_focused():
    db = FakeDb(rows=[])
    current_user = user()

    preference = await service.get_or_create_user_ui_preference(db, current_user)

    assert preference.user_id == current_user.id
    assert preference.complexity_mode == "focused"
    assert db.added == [preference]
    assert db.flushed == 1


@pytest.mark.asyncio
async def test_patch_user_ui_preference_applies_operations_and_increments_revision():
    current_user = user()
    preference = UserUiPreference(
        user_id=current_user.id,
        revision=3,
        complexity_mode="standard",
        dashboard_visibility_json={},
        dashboard_order_json=[],
        public_tool_visibility_json={},
        mobile_actions_json=[],
        guidance_dismissals_json={},
        recommendation_snoozes_json={},
    )
    db = FakeDb(rows=[preference])

    updated = await service.patch_user_ui_preference(
        db,
        current_user,
        UserUiPreferencePatch(
            base_revision=3,
            operations=[
                UiPreferenceOperation(op="set", path="/complexity_mode", value="power"),
                UiPreferenceOperation(
                    op="set",
                    path="/dashboard_visibility/dashboard.stats",
                    value="user_hidden",
                ),
                UiPreferenceOperation(
                    op="set",
                    path="/mobile_actions",
                    value=["dashboard.library", "dashboard.stats"],
                ),
            ],
        ),
    )

    assert updated is preference
    assert preference.revision == 4
    assert preference.complexity_mode == "power"
    assert preference.dashboard_visibility_json == {"dashboard.stats": "user_hidden"}
    assert preference.mobile_actions_json == ["dashboard.library", "dashboard.stats"]
    assert db.flushed == 1


@pytest.mark.asyncio
async def test_patch_user_ui_preference_reports_revision_conflict_with_latest_payload():
    current_user = user()
    preference = UserUiPreference(user_id=current_user.id, revision=4, complexity_mode="standard")

    with pytest.raises(service.PreferenceConflictError) as exc:
        await service.patch_user_ui_preference(
            FakeDb(rows=[preference]),
            current_user,
            UserUiPreferencePatch(
                base_revision=2,
                operations=[
                    UiPreferenceOperation(op="set", path="/complexity_mode", value="power"),
                ],
            ),
        )

    assert exc.value.conflict.latest_revision == 4
    assert exc.value.conflict.latest["revision"] == 4
    assert exc.value.conflict.latest["complexity_mode"] == "standard"


@pytest.mark.asyncio
async def test_patch_user_ui_preference_rejects_invalid_nested_visibility():
    current_user = user()
    preference = UserUiPreference(user_id=current_user.id, revision=1, complexity_mode="standard")

    with pytest.raises(service.PreferenceValidationError, match="invalid visibility"):
        await service.patch_user_ui_preference(
            FakeDb(rows=[preference]),
            current_user,
            UserUiPreferencePatch(
                base_revision=1,
                operations=[
                    UiPreferenceOperation(
                        op="set",
                        path="/dashboard_visibility/dashboard.stats",
                        value="gone",
                    ),
                ],
            ),
        )


@pytest.mark.asyncio
async def test_patch_user_ui_preference_accepts_nested_guidance_state():
    current_user = user()
    preference = UserUiPreference(user_id=current_user.id, revision=1, complexity_mode="standard")

    await service.patch_user_ui_preference(
        FakeDb(rows=[preference]),
        current_user,
        UserUiPreferencePatch(
            base_revision=1,
            operations=[
                UiPreferenceOperation(
                    op="set",
                    path="/guidance_dismissals/library",
                    value={"fingerprint": "empty", "dismissed_at": "2026-08-05T00:00:00Z"},
                ),
            ],
        ),
    )

    assert preference.guidance_dismissals_json["library"]["fingerprint"] == "empty"


def test_timeline_collapsed_sections_rejects_non_boolean_values():
    with pytest.raises(service.PreferenceValidationError, match="must be booleans"):
        service._normalize_book_field("timeline_collapsed_sections", {"drafts": "false"})


@pytest.mark.asyncio
async def test_import_replace_requires_explicit_confirmation():
    with pytest.raises(service.PreferenceValidationError, match="confirm_replace=true"):
        await service.import_user_ui_preferences(
            FakeDb(),
            user(),
            UserUiPreferenceImportBody(mode="replace", confirm_replace=False),
        )
