import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@lorevia.app", "username": "new", "password": "TestPass123!@#", "accepted_terms": True},
    )
    if r.status_code != 201:
        print(f"Registration failed: {r.status_code} - {r.text}")
    assert r.status_code == 201
    set_cookie_headers = r.headers.get_list("set-cookie")
    assert any("lorevia_access_token=" in header for header in set_cookie_headers)
    assert any("lorevia_refresh_token=" in header for header in set_cookie_headers)
    assert any("httponly" in header.lower() and "samesite=lax" in header.lower() for header in set_cookie_headers)

    r2 = await client.post("/api/v1/auth/login", json={"email": "new@lorevia.app", "password": "TestPass123!@#"})
    assert r2.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_refresh_and_logout_use_cookies(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "cookie@lorevia.app", "username": "cookie", "password": "CookiePass123!@#", "accepted_terms": True},
    )

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    refresh_cookies = refreshed.headers.get_list("set-cookie")
    assert any("lorevia_access_token=" in header for header in refresh_cookies)
    assert any("lorevia_refresh_token=" in header for header in refresh_cookies)

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    after_logout = await client.get("/api/v1/auth/me")
    assert after_logout.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_valid_token(client, auth_headers):
    r = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tier"] in {"free", "pro"}


@pytest.mark.asyncio
async def test_set_reading_mode(client, auth_headers):
    r = await client.patch("/api/v1/auth/me/reading-mode?mode=analyst", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["reading_mode"] == "analyst"
