from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.user import User, UserBookUiPreference, UserUiPreference
from app.schemas.user import (
    UserBookUiPreferenceOut,
    UserBookUiPreferencePatch,
    UserUiPreferenceImportBody,
    UserUiPreferenceImportOut,
    UserUiPreferenceOut,
    UserUiPreferencePatch,
)
from app.utils.books.collaboration_access import get_book_with_collaboration_access

UI_PREFERENCE_SCHEMA_VERSION = 1
MAX_JSON_FIELD_BYTES = 16 * 1024
MAX_JSON_LIST_ITEMS = 500
MAX_JSON_OBJECT_KEYS = 500
MAX_TOOL_ID_LENGTH = 120
VALID_COMPLEXITY_MODES = {"focused", "standard", "power"}
VALID_BOOK_PRESETS = {"draft", "review", "story_bible", "share", "all"}
VALID_VISIBILITY_VALUES = {
    "visible",
    "user_hidden",
}
VALID_DENSITIES = {"comfortable", "compact", "dense"}
VALID_READER_TOOLBAR_DENSITIES = {"standard", "compact"}
VALID_LOCKED_TOOL_PRESENTATIONS = {"compact", "hidden"}
VALID_WORKSPACE_SHELLS = {"reader", "author"}
VALID_ADVANCED_OVERRIDES = {"show", "hide"}
JSON_PRIMITIVE_TYPES = (str, int, float, bool, type(None))


class PreferenceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PreferenceConflict:
    latest_revision: int
    latest: dict[str, Any]


class PreferenceConflictError(Exception):
    def __init__(self, conflict: PreferenceConflict) -> None:
        self.conflict = conflict


GLOBAL_DEFAULTS: dict[str, Any] = {
    "schema_version": UI_PREFERENCE_SCHEMA_VERSION,
    "revision": 1,
    "complexity_mode": "focused",
    "dashboard_visibility": {},
    "dashboard_order": [],
    "public_tool_visibility": {},
    "density": "comfortable",
    "reader_toolbar_density": "standard",
    "locked_tool_presentation": "compact",
    "default_workspace_shell": "reader",
    "mobile_actions": [],
    "guidance_dismissals": {},
    "recommendation_snoozes": {},
}

BOOK_DEFAULTS: dict[str, Any] = {
    "schema_version": UI_PREFERENCE_SCHEMA_VERSION,
    "revision": 1,
    "book_preset": "draft",
    "advanced_tool_override": None,
    "hidden_book_tools": [],
    "overview_cards": {},
    "reader_actions": [],
    "mobile_actions": [],
    "panel_state": {},
    "timeline_collapsed_sections": {},
}

GLOBAL_MODEL_FIELDS = {
    "complexity_mode": "complexity_mode",
    "dashboard_visibility": "dashboard_visibility_json",
    "dashboard_order": "dashboard_order_json",
    "public_tool_visibility": "public_tool_visibility_json",
    "density": "density",
    "reader_toolbar_density": "reader_toolbar_density",
    "locked_tool_presentation": "locked_tool_presentation",
    "default_workspace_shell": "default_workspace_shell",
    "mobile_actions": "mobile_actions_json",
    "guidance_dismissals": "guidance_dismissals_json",
    "recommendation_snoozes": "recommendation_snoozes_json",
}

BOOK_MODEL_FIELDS = {
    "book_preset": "book_preset",
    "advanced_tool_override": "advanced_tool_override",
    "hidden_book_tools": "hidden_book_tools_json",
    "overview_cards": "overview_cards_json",
    "reader_actions": "reader_actions_json",
    "mobile_actions": "mobile_actions_json",
    "panel_state": "panel_state_json",
    "timeline_collapsed_sections": "timeline_collapsed_sections_json",
}


def _json_size(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode())


def _validate_tool_id(value: Any) -> str:
    tool_id = str(value or "").strip()
    if not tool_id:
        raise PreferenceValidationError("Preference keys must be non-empty.")
    if len(tool_id) > MAX_TOOL_ID_LENGTH:
        raise PreferenceValidationError("Preference key is too long.")
    if not all(char.isalnum() or char in "._:-/" for char in tool_id):
        raise PreferenceValidationError("Preference key contains unsupported characters.")
    return tool_id


def _validate_bounded_json(value: Any, field_name: str) -> Any:
    if _json_size(value) > MAX_JSON_FIELD_BYTES:
        raise PreferenceValidationError(f"{field_name} exceeds the maximum stored size.")
    if isinstance(value, dict) and len(value) > MAX_JSON_OBJECT_KEYS:
        raise PreferenceValidationError(f"{field_name} has too many entries.")
    if isinstance(value, list) and len(value) > MAX_JSON_LIST_ITEMS:
        raise PreferenceValidationError(f"{field_name} has too many entries.")
    return value


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise PreferenceValidationError(f"{field_name} must be a list.")
    result = [_validate_tool_id(item) for item in value]
    return _validate_bounded_json(list(dict.fromkeys(result)), field_name)


def _visibility_map(value: Any, field_name: str) -> dict[str, str | bool]:
    if not isinstance(value, dict):
        raise PreferenceValidationError(f"{field_name} must be an object.")
    result: dict[str, str | bool] = {}
    for key, raw_visibility in value.items():
        tool_id = _validate_tool_id(key)
        if isinstance(raw_visibility, bool):
            result[tool_id] = raw_visibility
        else:
            visibility = str(raw_visibility or "").strip()
            if visibility not in VALID_VISIBILITY_VALUES:
                raise PreferenceValidationError(f"{field_name} contains an invalid visibility.")
            result[tool_id] = visibility
    return _validate_bounded_json(result, field_name)


def _bool_map(value: Any, field_name: str) -> dict[str, bool]:
    if not isinstance(value, dict):
        raise PreferenceValidationError(f"{field_name} must be an object.")
    result: dict[str, bool] = {}
    for key, raw_value in value.items():
        if not isinstance(raw_value, bool):
            raise PreferenceValidationError(f"{field_name} values must be booleans.")
        result[_validate_tool_id(key)] = raw_value
    return _validate_bounded_json(result, field_name)


def _plain_json_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreferenceValidationError(f"{field_name} must be an object.")
    result: dict[str, Any] = {}
    for key, raw_value in value.items():
        result[_validate_tool_id(key)] = _normalize_json_value(raw_value, field_name)
    return _validate_bounded_json(result, field_name)


def _normalize_json_value(value: Any, field_name: str) -> Any:
    if isinstance(value, JSON_PRIMITIVE_TYPES):
        return value
    if isinstance(value, list):
        return [_normalize_json_value(item, field_name) for item in value[:MAX_JSON_LIST_ITEMS]]
    if isinstance(value, dict):
        return {
            str(key)[:MAX_TOOL_ID_LENGTH]: _normalize_json_value(item, field_name)
            for key, item in list(value.items())[:MAX_JSON_OBJECT_KEYS]
        }
    raise PreferenceValidationError(f"{field_name} contains unsupported JSON.")


def _enum_value(value: Any, valid_values: set[str], field_name: str) -> str:
    normalized = str(value or "").strip()
    if normalized not in valid_values:
        raise PreferenceValidationError(f"{field_name} is invalid.")
    return normalized


def _optional_enum_value(value: Any, valid_values: set[str], field_name: str) -> str | None:
    if value is None:
        return None
    return _enum_value(value, valid_values, field_name)


def _normalize_global_field(field_name: str, value: Any) -> Any:
    if field_name == "complexity_mode":
        return _enum_value(value, VALID_COMPLEXITY_MODES, field_name)
    if field_name in {"dashboard_visibility", "public_tool_visibility"}:
        return _visibility_map(value, field_name)
    if field_name in {"dashboard_order", "mobile_actions"}:
        return _string_list(value, field_name)
    if field_name == "density":
        return _enum_value(value, VALID_DENSITIES, field_name)
    if field_name == "reader_toolbar_density":
        return _enum_value(value, VALID_READER_TOOLBAR_DENSITIES, field_name)
    if field_name == "locked_tool_presentation":
        return _enum_value(value, VALID_LOCKED_TOOL_PRESENTATIONS, field_name)
    if field_name == "default_workspace_shell":
        return _enum_value(value, VALID_WORKSPACE_SHELLS, field_name)
    if field_name in {"guidance_dismissals", "recommendation_snoozes"}:
        return _plain_json_object(value, field_name)
    raise PreferenceValidationError(f"{field_name} is not a writable preference.")


def _normalize_book_field(field_name: str, value: Any) -> Any:
    if field_name == "book_preset":
        return _enum_value(value, VALID_BOOK_PRESETS, field_name)
    if field_name == "advanced_tool_override":
        return _optional_enum_value(value, VALID_ADVANCED_OVERRIDES, field_name)
    if field_name in {"hidden_book_tools", "reader_actions", "mobile_actions"}:
        return _string_list(value, field_name)
    if field_name == "overview_cards":
        return _visibility_map(value, field_name)
    if field_name == "timeline_collapsed_sections":
        return _bool_map(value, field_name)
    if field_name == "panel_state":
        return _plain_json_object(value, field_name)
    raise PreferenceValidationError(f"{field_name} is not a writable preference.")


def _path_parts(path: str) -> list[str]:
    if not path.startswith("/"):
        raise PreferenceValidationError("Preference operation paths must start with '/'.")
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        raise PreferenceValidationError("Preference operation path is empty.")
    return parts


def _nested_value(field_name: str, raw_value: Any) -> Any:
    if field_name in {"dashboard_visibility", "public_tool_visibility", "overview_cards"}:
        if isinstance(raw_value, bool):
            return raw_value
        value = str(raw_value or "").strip()
        if value not in VALID_VISIBILITY_VALUES:
            raise PreferenceValidationError(f"{field_name} contains an invalid visibility.")
        return value
    if field_name == "timeline_collapsed_sections":
        if not isinstance(raw_value, bool):
            raise PreferenceValidationError(f"{field_name} values must be booleans.")
        return raw_value
    if field_name in {"guidance_dismissals", "recommendation_snoozes", "panel_state"}:
        return _normalize_json_value(raw_value, field_name)
    raise PreferenceValidationError(f"{field_name} does not support nested operations.")


def _apply_operations(
    payload: dict[str, Any],
    operations: list[Any],
    defaults: dict[str, Any],
    normalizer: Any,
) -> dict[str, Any]:
    next_payload = copy.deepcopy(payload)
    for operation in operations:
        parts = _path_parts(operation.path)
        field_name = parts[0]
        if field_name not in defaults or field_name in {"schema_version", "revision", "updated_at"}:
            raise PreferenceValidationError(f"{field_name} is not writable.")
        op = operation.op
        if len(parts) == 1:
            if op == "unset":
                next_payload[field_name] = copy.deepcopy(defaults[field_name])
            else:
                next_payload[field_name] = normalizer(field_name, operation.value)
            continue
        if len(parts) == 2 and isinstance(next_payload.get(field_name), dict):
            key = _validate_tool_id(parts[1])
            updated = dict(next_payload[field_name])
            if op == "unset":
                updated.pop(key, None)
            else:
                updated[key] = _nested_value(field_name, operation.value)
            next_payload[field_name] = normalizer(field_name, updated)
            continue
        raise PreferenceValidationError("Preference operation path is not supported.")
    return next_payload


def _serialize_global_payload(preference: UserUiPreference) -> dict[str, Any]:
    return {
        "schema_version": int(preference.schema_version or UI_PREFERENCE_SCHEMA_VERSION),
        "revision": int(preference.revision or 1),
        "complexity_mode": _normalize_global_field(
            "complexity_mode", preference.complexity_mode or GLOBAL_DEFAULTS["complexity_mode"]
        ),
        "dashboard_visibility": _normalize_global_field(
            "dashboard_visibility", preference.dashboard_visibility_json or {}
        ),
        "dashboard_order": _normalize_global_field(
            "dashboard_order", preference.dashboard_order_json or []
        ),
        "public_tool_visibility": _normalize_global_field(
            "public_tool_visibility", preference.public_tool_visibility_json or {}
        ),
        "density": _normalize_global_field("density", preference.density or "comfortable"),
        "reader_toolbar_density": _normalize_global_field(
            "reader_toolbar_density", preference.reader_toolbar_density or "standard"
        ),
        "locked_tool_presentation": _normalize_global_field(
            "locked_tool_presentation", preference.locked_tool_presentation or "compact"
        ),
        "default_workspace_shell": _normalize_global_field(
            "default_workspace_shell", preference.default_workspace_shell or "reader"
        ),
        "mobile_actions": _normalize_global_field(
            "mobile_actions", preference.mobile_actions_json or []
        ),
        "guidance_dismissals": _normalize_global_field(
            "guidance_dismissals", preference.guidance_dismissals_json or {}
        ),
        "recommendation_snoozes": _normalize_global_field(
            "recommendation_snoozes", preference.recommendation_snoozes_json or {}
        ),
        "updated_at": preference.updated_at,
    }


def _serialize_book_payload(preference: UserBookUiPreference) -> dict[str, Any]:
    return {
        "book_id": preference.book_id,
        "schema_version": int(preference.schema_version or UI_PREFERENCE_SCHEMA_VERSION),
        "revision": int(preference.revision or 1),
        "book_preset": _normalize_book_field(
            "book_preset", preference.book_preset or BOOK_DEFAULTS["book_preset"]
        ),
        "advanced_tool_override": _normalize_book_field(
            "advanced_tool_override", preference.advanced_tool_override
        ),
        "hidden_book_tools": _normalize_book_field(
            "hidden_book_tools", preference.hidden_book_tools_json or []
        ),
        "overview_cards": _normalize_book_field(
            "overview_cards", preference.overview_cards_json or {}
        ),
        "reader_actions": _normalize_book_field(
            "reader_actions", preference.reader_actions_json or []
        ),
        "mobile_actions": _normalize_book_field(
            "mobile_actions", preference.mobile_actions_json or []
        ),
        "panel_state": _normalize_book_field("panel_state", preference.panel_state_json or {}),
        "timeline_collapsed_sections": _normalize_book_field(
            "timeline_collapsed_sections", preference.timeline_collapsed_sections_json or {}
        ),
        "updated_at": preference.updated_at,
    }


def serialize_user_ui_preference(preference: UserUiPreference) -> UserUiPreferenceOut:
    return UserUiPreferenceOut(**_serialize_global_payload(preference))


def serialize_user_book_ui_preference(
    preference: UserBookUiPreference,
) -> UserBookUiPreferenceOut:
    return UserBookUiPreferenceOut(**_serialize_book_payload(preference))


def _assign_global_payload(preference: UserUiPreference, payload: dict[str, Any]) -> None:
    for public_name, model_name in GLOBAL_MODEL_FIELDS.items():
        setattr(preference, model_name, payload[public_name])
    preference.schema_version = UI_PREFERENCE_SCHEMA_VERSION


def _assign_book_payload(preference: UserBookUiPreference, payload: dict[str, Any]) -> None:
    for public_name, model_name in BOOK_MODEL_FIELDS.items():
        setattr(preference, model_name, payload[public_name])
    preference.schema_version = UI_PREFERENCE_SCHEMA_VERSION


async def get_or_create_user_ui_preference(
    db: AsyncSession,
    user: User,
    *,
    default_mode: str = "focused",
    lock_for_update: bool = False,
) -> UserUiPreference:
    if lock_for_update:
        await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    preference = (
        await db.execute(select(UserUiPreference).where(UserUiPreference.user_id == user.id))
    ).scalar_one_or_none()
    if preference:
        return preference
    if not lock_for_update:
        await db.execute(select(User.id).where(User.id == user.id).with_for_update())
        preference = (
            await db.execute(select(UserUiPreference).where(UserUiPreference.user_id == user.id))
        ).scalar_one_or_none()
        if preference:
            return preference
    preference = UserUiPreference(
        user_id=user.id,
        complexity_mode=_enum_value(default_mode, VALID_COMPLEXITY_MODES, "complexity_mode"),
    )
    db.add(preference)
    await db.flush()
    return preference


async def get_or_create_user_book_ui_preference(
    db: AsyncSession,
    user: User,
    book_id: uuid.UUID,
    *,
    lock_for_update: bool = False,
) -> UserBookUiPreference:
    await get_book_with_collaboration_access(db, book_id, user)
    global_preference = await get_or_create_user_ui_preference(db, user)
    if lock_for_update:
        await db.execute(select(Book.id).where(Book.id == book_id).with_for_update())
    preference = (
        await db.execute(
            select(UserBookUiPreference).where(
                UserBookUiPreference.user_id == user.id,
                UserBookUiPreference.book_id == book_id,
            )
        )
    ).scalar_one_or_none()
    if preference:
        return preference
    if not lock_for_update:
        await db.execute(select(Book.id).where(Book.id == book_id).with_for_update())
        preference = (
            await db.execute(
                select(UserBookUiPreference).where(
                    UserBookUiPreference.user_id == user.id,
                    UserBookUiPreference.book_id == book_id,
                )
            )
        ).scalar_one_or_none()
        if preference:
            return preference
    default_preset = "draft" if global_preference.complexity_mode == "focused" else "all"
    preference = UserBookUiPreference(user_id=user.id, book_id=book_id, book_preset=default_preset)
    db.add(preference)
    await db.flush()
    return preference


async def patch_user_ui_preference(
    db: AsyncSession, user: User, body: UserUiPreferencePatch
) -> UserUiPreference:
    preference = await get_or_create_user_ui_preference(db, user, lock_for_update=True)
    if body.base_revision != int(preference.revision or 1):
        latest = serialize_user_ui_preference(preference).model_dump(mode="json")
        raise PreferenceConflictError(PreferenceConflict(int(preference.revision or 1), latest))
    if not body.operations:
        return preference
    payload = _serialize_global_payload(preference)
    updated = _apply_operations(payload, body.operations, GLOBAL_DEFAULTS, _normalize_global_field)
    _assign_global_payload(preference, updated)
    preference.revision = int(preference.revision or 1) + 1
    await db.flush()
    return preference


async def patch_user_book_ui_preference(
    db: AsyncSession,
    user: User,
    book_id: uuid.UUID,
    body: UserBookUiPreferencePatch,
) -> UserBookUiPreference:
    preference = await get_or_create_user_book_ui_preference(
        db, user, book_id, lock_for_update=True
    )
    if body.base_revision != int(preference.revision or 1):
        latest = serialize_user_book_ui_preference(preference).model_dump(mode="json")
        raise PreferenceConflictError(PreferenceConflict(int(preference.revision or 1), latest))
    if not body.operations:
        return preference
    payload = _serialize_book_payload(preference)
    updated = _apply_operations(payload, body.operations, BOOK_DEFAULTS, _normalize_book_field)
    _assign_book_payload(preference, updated)
    preference.revision = int(preference.revision or 1) + 1
    await db.flush()
    return preference


async def export_user_ui_preferences(db: AsyncSession, user: User) -> dict[str, Any]:
    global_preference = await get_or_create_user_ui_preference(db, user)
    book_preferences = (
        (
            await db.execute(
                select(UserBookUiPreference)
                .where(UserBookUiPreference.user_id == user.id)
                .order_by(UserBookUiPreference.updated_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "schema_version": UI_PREFERENCE_SCHEMA_VERSION,
        "global_preferences": serialize_user_ui_preference(global_preference).model_dump(
            mode="json"
        ),
        "book_preferences": [
            serialize_user_book_ui_preference(preference).model_dump(mode="json")
            for preference in book_preferences
        ],
    }


def _merge_payload(
    current: dict[str, Any],
    incoming: dict[str, Any],
    defaults: dict[str, Any],
    normalizer: Any,
) -> dict[str, Any]:
    merged = copy.deepcopy(current)
    for key, value in incoming.items():
        if key in {"schema_version", "revision", "updated_at", "book_id"}:
            continue
        if key not in defaults:
            raise PreferenceValidationError(f"{key} is not a supported preference.")
        merged[key] = normalizer(key, value)
    return merged


async def import_user_ui_preferences(
    db: AsyncSession,
    user: User,
    body: UserUiPreferenceImportBody,
) -> UserUiPreferenceImportOut:
    if body.mode == "replace" and not body.confirm_replace:
        raise PreferenceValidationError("Replace imports require confirm_replace=true.")

    global_preference = await get_or_create_user_ui_preference(db, user)
    current_global = _serialize_global_payload(global_preference)
    incoming_global = body.global_preferences or {}
    if body.mode == "replace":
        next_global = _merge_payload(
            copy.deepcopy(GLOBAL_DEFAULTS),
            incoming_global,
            GLOBAL_DEFAULTS,
            _normalize_global_field,
        )
    else:
        next_global = _merge_payload(
            current_global, incoming_global, GLOBAL_DEFAULTS, _normalize_global_field
        )
    _assign_global_payload(global_preference, next_global)
    global_preference.revision = int(global_preference.revision or 1) + 1

    updated_books = 0
    imported_book_ids: set[uuid.UUID] = set()
    for raw_book_preference in body.book_preferences:
        raw_book_id = raw_book_preference.get("book_id")
        if not raw_book_id:
            raise PreferenceValidationError("Book preference imports require book_id.")
        try:
            book_id = uuid.UUID(str(raw_book_id))
        except ValueError:
            raise PreferenceValidationError("Book preference import contains invalid book_id.")
        try:
            await get_book_with_collaboration_access(db, book_id, user)
        except HTTPException:
            raise PreferenceValidationError("Book preference import contains an unknown book.")
        imported_book_ids.add(book_id)
        book_preference = await get_or_create_user_book_ui_preference(db, user, book_id)
        current_book = _serialize_book_payload(book_preference)
        if body.mode == "replace":
            next_book = _merge_payload(
                copy.deepcopy(BOOK_DEFAULTS),
                raw_book_preference,
                BOOK_DEFAULTS,
                _normalize_book_field,
            )
        else:
            next_book = _merge_payload(
                current_book, raw_book_preference, BOOK_DEFAULTS, _normalize_book_field
            )
        _assign_book_payload(book_preference, next_book)
        book_preference.revision = int(book_preference.revision or 1) + 1
        updated_books += 1

    if body.mode == "replace":
        stale_preferences = delete(UserBookUiPreference).where(
            UserBookUiPreference.user_id == user.id
        )
        if imported_book_ids:
            stale_preferences = stale_preferences.where(
                UserBookUiPreference.book_id.notin_(imported_book_ids)
            )
        await db.execute(stale_preferences)

    await db.flush()
    return UserUiPreferenceImportOut(
        imported=True,
        mode=body.mode,
        global_revision=int(global_preference.revision or 1),
        book_preferences_updated=updated_books,
    )
