import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    r = await client.post("/api/v1/auth/register", json={"email": "new@lorevia.app", "password": "TestPass123!@#", "accepted_terms": True})
    if r.status_code != 201:
        print(f"Registration failed: {r.status_code} - {r.text}")
    assert r.status_code == 201
    assert "access_token" in r.json()

    r2 = await client.post("/api/v1/auth/login", json={"email": "new@lorevia.app", "password": "TestPass123!@#"})
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_valid_token(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tier"] == "free"


@pytest.mark.asyncio
async def test_set_reading_mode(client, auth_headers):
    r = await client.patch("/api/v1/auth/me/reading-mode?mode=analyst", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["reading_mode"] == "analyst"
