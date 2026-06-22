"""Unit coverage for admin principal and platform service operations."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.user import AdminPrincipal, User
from app.services import admin_service


class FakeScalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def all(self):
        return list(self.value)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return FakeScalars(self.value)

    def scalar(self):
        return self.value


class FakeDB:
    def __init__(self, *results, user=None):
        self.results = list(results)
        self.user = user
        self.added = []
        self.commits = 0
        self.flushes = 0

    async def execute(self, _statement):
        return FakeResult(self.results.pop(0))

    def add(self, value):
        self.added.append(value)

    async def get(self, model, _item_id):
        assert model is User
        return self.user

    async def flush(self):
        self.flushes += 1
        value = self.added[-1]
        if value.id is None:
            value.id = uuid.uuid4()
        if getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(UTC)

    async def commit(self):
        self.commits += 1


def test_normalize_and_check_admin_scopes():
    assert admin_service.normalize_admin_scopes(
        [" SUPER_ADMIN ", "billing_admin", "billing_admin"]
    ) == ["billing_admin", "super_admin"]
    with pytest.raises(ValueError, match="Invalid admin scopes"):
        admin_service.normalize_admin_scopes(["unknown"])
    assert admin_service.principal_scope_snapshot(None) == []
    assert admin_service.principal_has_scope(None, "billing_admin") is False

    active = SimpleNamespace(status="active", is_owner=False, scopes=["billing_admin"])
    owner = SimpleNamespace(status="active", is_owner=True, scopes=[])
    revoked = SimpleNamespace(status="revoked", is_owner=True, scopes=["super_admin"])
    assert admin_service.principal_has_scope(active, "billing_admin") is True
    assert admin_service.principal_has_scope(owner, "moderation_admin") is True
    assert admin_service.principal_scope_snapshot(revoked) == []


@pytest.mark.asyncio
async def test_grant_admin_principal_creates_and_reactivates_records():
    target = SimpleNamespace(id=uuid.uuid4())
    actor_id = uuid.uuid4()
    create_db = FakeDB(None)
    created = await admin_service.grant_admin_principal(
        create_db,
        target_user=target,
        granted_by_user_id=actor_id,
        scopes=["billing_admin"],
        is_owner=False,
        reason="  Billing coverage  ",
    )
    assert isinstance(created, AdminPrincipal)
    assert created.status == "active" and created.scopes == ["billing_admin"]
    assert created.grant_reason == "Billing coverage"
    assert create_db.added == [created]

    existing = SimpleNamespace(
        status="revoked",
        is_owner=False,
        scopes=[],
        grant_reason=None,
        revoke_reason="old",
        revoked_by_user_id=uuid.uuid4(),
        revoked_at=datetime.now(UTC),
        granted_by_user_id=None,
        updated_at=None,
    )
    updated = await admin_service.grant_admin_principal(
        FakeDB(existing),
        target_user=target,
        granted_by_user_id=actor_id,
        scopes=["super_admin"],
        is_owner=True,
        reason="Restore owner",
    )
    assert updated is existing
    assert existing.status == "active" and existing.is_owner is True
    assert existing.scopes == ["super_admin"]
    assert existing.revoke_reason is None and existing.revoked_at is None
    assert existing.updated_at.tzinfo is UTC


@pytest.mark.asyncio
async def test_revoke_admin_principal_updates_user_token_version(monkeypatch):
    user = SimpleNamespace(token_version=4)
    principal = SimpleNamespace(
        user_id=uuid.uuid4(),
        status="active",
        revoke_reason=None,
        revoked_by_user_id=None,
        revoked_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(admin_service, "next_token_version", lambda value: value.token_version + 1)
    await admin_service.revoke_admin_principal(
        FakeDB(user=user),
        principal=principal,
        revoked_by_user_id=uuid.uuid4(),
        reason="  Access removed  ",
    )
    assert principal.status == "revoked" and principal.revoke_reason == "Access removed"
    assert principal.revoked_at.tzinfo is UTC and user.token_version == 5


@pytest.mark.asyncio
async def test_get_platform_metrics_counts_records_and_reports_redis_memory(monkeypatch):
    class Redis:
        async def info(self, section):
            assert section == "memory"
            return {"used_memory": 3 * 1024 * 1024 + 512 * 1024}

    async def get_redis():
        return Redis()

    monkeypatch.setattr("app.core.redis.get_redis", get_redis)
    result = await admin_service.get_platform_metrics(FakeDB(10, 8, 30, 120, 40))
    assert result == {
        "users": 10,
        "books": 8,
        "characters": 30,
        "chunks_indexed": 120,
        "summaries_cached": 40,
        "redis_memory_mb": 3.5,
    }


@pytest.mark.asyncio
async def test_apply_creator_strike_records_moderation_and_audit(monkeypatch):
    db = FakeDB()
    calls = []

    async def serious_count(_db, *, user_id):
        return 2

    async def moderation(_db, **kwargs):
        calls.append(("moderation", kwargs))

    async def audit(_db, **kwargs):
        calls.append(("audit", kwargs))

    monkeypatch.setattr(admin_service, "active_serious_strike_count", serious_count)
    monkeypatch.setattr(admin_service, "add_moderation_action", moderation)
    monkeypatch.setattr(admin_service, "record_admin_audit_event", audit)
    principal = SimpleNamespace(status="active", is_owner=False, scopes=["moderation_admin"])
    request = SimpleNamespace(
        state=SimpleNamespace(admin_principal=principal), headers={}, client=None
    )
    user_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    output = await admin_service.apply_creator_strike(
        db,
        user_id=user_id,
        book_id=None,
        report_id=None,
        strike_type="copyright",
        severity="serious",
        reason="Repeated infringement",
        admin_user_id=admin_id,
        request=request,
    )
    assert output.user_id == str(user_id) and output.severity == "serious"
    assert db.flushes == 1 and db.commits == 1
    assert [kind for kind, _ in calls] == ["moderation", "audit"]
    assert calls[0][1]["new_status"] == "serious_strikes:2"
    assert calls[1][1]["scopes_snapshot"] == ["moderation_admin"]
