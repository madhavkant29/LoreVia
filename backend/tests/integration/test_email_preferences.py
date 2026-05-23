import uuid

import pytest

from app.models.user import User
from app.utils.email_utils import build_email_preference_links


@pytest.mark.asyncio
async def test_authenticated_email_preferences_can_be_loaded_and_updated(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])
    user = await db.get(User, user_id)
    assert user is not None

    get_response = await client.get("/api/v1/email/preferences", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["email"] == user.email
    assert get_response.json()["product_updates"] is True
    assert get_response.json()["marketing"] is True

    update_response = await client.post(
        "/api/v1/email/preferences",
        headers=auth_headers,
        json={"product_updates": False, "marketing": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["product_updates"] is False
    assert update_response.json()["marketing"] is True
    assert update_response.json()["unsubscribed_all"] is False


@pytest.mark.asyncio
async def test_token_based_email_preferences_lookup_returns_promotional_state(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None

    links = await build_email_preference_links(user)
    token = links.preferences_url.split("token=", 1)[1]

    response = await client.get(f"/api/v1/email/preferences?token={token}")
    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert response.json()["product_updates"] is True
    assert response.json()["marketing"] is True


@pytest.mark.asyncio
async def test_one_click_unsubscribe_immediately_suppresses_promotional_email(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user = await db.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None

    links = await build_email_preference_links(user)
    token = links.unsubscribe_url.split("token=", 1)[1]

    response = await client.post(f"/api/v1/email/unsubscribe?token={token}")
    assert response.status_code == 200
    assert response.json()["product_updates"] is False
    assert response.json()["marketing"] is False
    assert response.json()["unsubscribed_all"] is True

    updated = await client.get("/api/v1/email/preferences", headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["product_updates"] is False
    assert updated.json()["marketing"] is False
    assert updated.json()["unsubscribed_all"] is True
