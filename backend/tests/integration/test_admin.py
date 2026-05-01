import uuid

import pytest

from app.models.user import User


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": email.split("@")[0][:24], "password": "StrongPass123!@#", "accepted_terms": True},
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={token}"})
    assert me.status_code == 200
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_admin_queue_depth_reports_redis_lengths(client, db, monkeypatch):
    headers, user_id = await _register_user(client, f"admin-queue-depth-{uuid.uuid4().hex[:8]}@lorevia.app")
    user = await db.get(User, user_id)
    assert user is not None
    user.tier = "admin"
    await db.commit()

    class FakeRedis:
        async def get(self, key: str):
            return None

        async def set(self, key: str, value, ex=None, nx=False):
            return True

        async def exists(self, *keys):
            return 0

        async def incr(self, key: str):
            return 1

        async def llen(self, key: str) -> int:
            return {
                "extraction": 7,
                "analysis": 3,
                "embedding": 11,
                "intelligence": 2,
            }[key]

    fake_redis = FakeRedis()
    monkeypatch.setattr("app.core.redis._redis", fake_redis, raising=False)

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr("app.core.redis.get_redis", fake_get_redis, raising=False)

    response = await client.get("/api/v1/admin/queue-depth", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "extraction": 7,
        "analysis": 3,
        "embedding": 11,
        "intelligence": 2,
    }
