import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.user import SubscriptionEvent, User


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:24],
            "password": "StrongPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
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


@pytest.mark.asyncio
async def test_admin_subscription_metrics_reports_trial_conversion_and_post_cancel_churn(client, db):
    headers, user_id = await _register_user(client, f"admin-subscription-metrics-{uuid.uuid4().hex[:8]}@lorevia.app")
    admin_user = await db.get(User, user_id)
    assert admin_user is not None
    admin_user.tier = "admin"
    await db.commit()

    cohort_start = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    converted_user = User(
        email=f"metrics-converted-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"metricsconv{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=cohort_start,
    )
    churned_user = User(
        email=f"metrics-churned-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"metricschurn{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=1),
    )
    reactivated_user = User(
        email=f"metrics-reactivated-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"metricsreact{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        created_at=cohort_start + timedelta(days=2),
    )
    db.add_all([converted_user, churned_user, reactivated_user])
    await db.flush()

    db.add_all(
        [
            SubscriptionEvent(
                user_id=converted_user.id,
                event_type="subscription_activated",
                source="paddle",
                source_event_id=f"evt-convert-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="active",
                occurred_at=cohort_start + timedelta(days=4),
            ),
            SubscriptionEvent(
                user_id=churned_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id=f"evt-churn-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="canceled",
                occurred_at=cohort_start + timedelta(days=5),
            ),
            SubscriptionEvent(
                user_id=reactivated_user.id,
                event_type="subscription_canceled",
                source="paddle",
                source_event_id=f"evt-cancel-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="canceled",
                occurred_at=cohort_start + timedelta(days=5),
            ),
            SubscriptionEvent(
                user_id=reactivated_user.id,
                event_type="subscription_activated",
                source="paddle",
                source_event_id=f"evt-reactivate-{uuid.uuid4().hex}",
                plan="author_monthly",
                status="active",
                occurred_at=cohort_start + timedelta(days=10),
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        "/api/v1/admin/subscription-metrics?start_date=2026-05-01&end_date=2026-05-31&reactivation_window_days=3",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "cohort_start": "2026-05-01",
        "cohort_end": "2026-05-31",
        "trial_starts": 3,
        "trial_to_paid_conversions": 2,
        "trial_to_paid_rate": 66.67,
        "cancellation_events": 2,
        "resolved_cancellation_events": 2,
        "unresolved_cancellation_events": 0,
        "reactivated_after_cancellation": 0,
        "churned_after_cancellation": 2,
        "post_cancel_churn_rate": 100.0,
        "reactivation_window_days": 3,
    }
