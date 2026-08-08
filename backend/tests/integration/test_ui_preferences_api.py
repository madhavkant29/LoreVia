from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.security import create_access_token
from app.models.book import Book, BookCollaborator
from app.models.user import User


async def _register_user(client) -> tuple[dict[str, str], uuid.UUID]:
    unique = uuid.uuid4().hex[:10]
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"ui-pref-{unique}@lorevia.app",
            "username": f"uipref{unique}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"ui-pref-device-{unique}",
        },
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    token = create_access_token(str(user_id))
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.mark.asyncio
async def test_ui_preferences_lifecycle_and_conflict_response(client):
    headers, _user_id = await _register_user(client)

    initial = await client.get("/api/v1/auth/me/ui-preferences", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["complexity_mode"] == "focused"
    assert initial.json()["revision"] == 1

    updated = await client.patch(
        "/api/v1/auth/me/ui-preferences",
        headers=headers,
        json={
            "base_revision": 1,
            "operations": [
                {"op": "set", "path": "/complexity_mode", "value": "standard"},
                {
                    "op": "set",
                    "path": "/dashboard_visibility/dashboard.stats",
                    "value": "user_hidden",
                },
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["complexity_mode"] == "standard"
    assert updated.json()["dashboard_visibility"]["dashboard.stats"] == "user_hidden"
    assert updated.json()["revision"] == 2

    conflict = await client.patch(
        "/api/v1/auth/me/ui-preferences",
        headers=headers,
        json={
            "base_revision": 1,
            "operations": [{"op": "set", "path": "/complexity_mode", "value": "power"}],
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["latest_revision"] == 2
    assert conflict.json()["latest"]["complexity_mode"] == "standard"


@pytest.mark.asyncio
async def test_concurrent_preference_patches_allow_one_revision_winner(client):
    headers, _user_id = await _register_user(client)
    initial = await client.get("/api/v1/auth/me/ui-preferences", headers=headers)
    assert initial.status_code == 200

    async def patch_mode(mode: str):
        return await client.patch(
            "/api/v1/auth/me/ui-preferences",
            headers=headers,
            json={
                "base_revision": initial.json()["revision"],
                "operations": [{"op": "set", "path": "/complexity_mode", "value": mode}],
            },
        )

    responses = await asyncio.gather(patch_mode("standard"), patch_mode("power"))
    assert sorted(response.status_code for response in responses) == [200, 409]
    latest = await client.get("/api/v1/auth/me/ui-preferences", headers=headers)
    assert latest.json()["revision"] == initial.json()["revision"] + 1


@pytest.mark.asyncio
async def test_book_ui_preferences_and_visibility_summary_are_owner_scoped(client, db):
    headers, user_id = await _register_user(client)
    book = Book(
        user_id=user_id,
        title="Preference Book",
        author="Author",
        genre="Fantasy",
        format="txt",
        s3_key="books/preference-book.txt",
        status="ready",
        mode="author",
        source_kind="manual",
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)

    initial = await client.get(
        f"/api/v1/auth/me/ui-preferences/books/{book.id}",
        headers=headers,
    )
    assert initial.status_code == 200
    assert initial.json()["book_preset"] == "draft"
    assert initial.json()["revision"] == 1

    updated = await client.patch(
        f"/api/v1/auth/me/ui-preferences/books/{book.id}",
        headers=headers,
        json={
            "base_revision": 1,
            "operations": [
                {"op": "set", "path": "/book_preset", "value": "review"},
                {"op": "set", "path": "/hidden_book_tools", "value": ["book.search"]},
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["book_preset"] == "review"
    assert updated.json()["hidden_book_tools"] == ["book.search"]
    assert updated.json()["revision"] == 2

    summary = await client.get(f"/api/v1/books/{book.id}/visibility-summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["book_id"] == str(book.id)
    assert summary.json()["badges"] == ["Private"]
    assert summary.json()["private_status"]["state"] == "private"

    other_headers, _other_user_id = await _register_user(client)
    denied = await client.get(
        f"/api/v1/auth/me/ui-preferences/books/{book.id}",
        headers=other_headers,
    )
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_visibility_summary_rejects_active_collaborators(client, db):
    owner_headers, owner_user_id = await _register_user(client)
    collaborator_headers, collaborator_user_id = await _register_user(client)
    collaborator_user = await db.get(User, collaborator_user_id)
    book = Book(
        user_id=owner_user_id,
        title="Owner Visibility",
        format="txt",
        s3_key="books/owner-visibility.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add(
        BookCollaborator(
            book_id=book.id,
            invited_user_id=collaborator_user_id,
            email=collaborator_user.email,
            role="viewer",
            invite_status="active",
        )
    )
    await db.commit()

    owner_response = await client.get(
        f"/api/v1/books/{book.id}/visibility-summary", headers=owner_headers
    )
    collaborator_response = await client.get(
        f"/api/v1/books/{book.id}/visibility-summary", headers=collaborator_headers
    )

    assert owner_response.status_code == 200
    assert collaborator_response.status_code == 403


@pytest.mark.asyncio
async def test_standard_users_get_all_preset_for_new_book_preferences(client, db):
    headers, user_id = await _register_user(client)
    current = await client.get("/api/v1/auth/me/ui-preferences", headers=headers)
    changed = await client.patch(
        "/api/v1/auth/me/ui-preferences",
        headers=headers,
        json={
            "base_revision": current.json()["revision"],
            "operations": [{"op": "set", "path": "/complexity_mode", "value": "standard"}],
        },
    )
    assert changed.status_code == 200
    book = Book(
        user_id=user_id,
        title="Existing User Book",
        format="txt",
        s3_key="books/existing-user-book.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)

    response = await client.get(f"/api/v1/auth/me/ui-preferences/books/{book.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["book_preset"] == "all"
