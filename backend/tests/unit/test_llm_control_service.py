from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.user import LlmUsageEvent, ProcessingUsageEvent, User
from app.services import llm_control_service


class _SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return None


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.sorted_sets: dict[str, dict[str, int]] = {}

    async def exists(self, key):
        return key in self.values

    async def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        return True

    async def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(str(value))

    async def expire(self, *_args):
        return True

    async def zadd(self, key, values):
        self.sorted_sets.setdefault(key, {}).update(values)

    async def pexpire(self, *_args):
        return True

    async def eval(self, _script, key_count, *args):
        if key_count == 1:
            key, owner = args
            if self.values.get(key) == owner:
                self.values.pop(key, None)
                return 1
            return 0
        if key_count == 2:
            return [1, 0]
        raise NotImplementedError

    async def srem(self, key, value):
        self.sets.setdefault(key, set()).discard(str(value))


async def test_system_llm_rate_limit_uses_provider_scoped_global_budget(monkeypatch):
    captured: dict[str, object] = {}

    class RateRedis:
        async def eval(self, script, key_count, *args):
            captured.update({"script": script, "key_count": key_count, "args": args})
            return [1, 0]

    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(RateRedis()))

    await llm_control_service.enforce_system_llm_rate_limit(
        provider="google",
        model="gemini-2.5-flash",
        operation="chat",
        estimated_tokens=321,
    )

    assert captured["key_count"] == 1
    assert captured["args"][0] == "llm:system-rate:google:chat:gemini-2.5-flash"
    assert captured["args"][3] == 321


async def test_system_llm_rate_limit_fails_closed_when_capacity_is_exhausted(monkeypatch):
    class RateRedis:
        async def eval(self, *_args):
            return [0, 9]

    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(RateRedis()))

    with pytest.raises(HTTPException) as exc:
        await llm_control_service.enforce_system_llm_rate_limit(
            provider="google",
            model="gemini-2.5-flash",
            operation="chat",
            estimated_tokens=321,
        )

    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "9"}


async def test_rehydrate_llm_coordination_rebuilds_active_and_releases_stale(db, monkeypatch):
    await db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.status == "reserved"))
    await db.commit()

    user = User(
        email=f"rehydrate-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"rehydrate{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    now = datetime.now(UTC)
    active = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="advisor",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=120,
        total_tokens=120,
        created_at=now - timedelta(seconds=20),
    )
    stale = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="advisor",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=80,
        total_tokens=80,
        created_at=now - timedelta(hours=1),
    )
    db.add_all([active, stale])
    await db.commit()
    redis = _FakeRedis()
    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(redis))
    monkeypatch.setattr(llm_control_service, "AsyncSessionLocal", lambda: _SessionContext(db))

    result = await llm_control_service.rehydrate_llm_coordination_state(force=True)

    assert result == {"rehydrated": True, "active_reservations": 1, "stale_released": 1}
    assert active.reservation_id in redis.sets[f"llm:concurrency:{user.id}"]
    assert f"{active.reservation_id}|120" in redis.sorted_sets["llm:rate:chat"]
    await db.refresh(stale)
    assert stale.status == "failed"
    assert stale.total_tokens == 80


async def test_stale_reservation_retains_uncertain_cost(db, monkeypatch):
    await db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.status == "reserved"))
    user = User(
        email=f"stale-cost-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"stalecost{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    stale = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="processing",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=100,
        total_tokens=100,
        input_cost_usd=Decimal("0.10"),
        output_cost_usd=Decimal("0.15"),
        total_cost_usd=Decimal("0.25"),
        created_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(stale)
    await db.commit()
    redis = _FakeRedis()
    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(redis))
    monkeypatch.setattr(llm_control_service, "AsyncSessionLocal", lambda: _SessionContext(db))

    await llm_control_service.rehydrate_llm_coordination_state(force=True)

    await db.refresh(stale)
    assert stale.status == "failed"
    assert stale.total_cost_usd == Decimal("0.25000000")
    assert stale.metadata_json["cost_disposition"] == "uncertain_provider_attempt"


async def test_maintenance_settles_stale_reservations_without_redis_restart(db, monkeypatch):
    user = User(
        email=f"maintenance-stale-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"maintenancestale{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    now = datetime.now(UTC)
    stale = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="stale",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=400,
        total_tokens=400,
        total_cost_usd=Decimal("0.20"),
        created_at=now - timedelta(hours=1),
    )
    active = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="active",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=200,
        total_tokens=200,
        total_cost_usd=Decimal("0.10"),
        created_at=now - timedelta(minutes=5),
    )
    db.add_all([stale, active])
    await db.commit()
    redis = _FakeRedis()
    redis.sets[f"llm:concurrency:{user.id}"] = {
        str(stale.reservation_id),
        str(active.reservation_id),
    }
    monkeypatch.setattr(
        llm_control_service,
        "AsyncSessionLocal",
        async_sessionmaker(db.bind, expire_on_commit=False),
    )
    monkeypatch.setattr(
        llm_control_service,
        "get_redis",
        lambda: _async_value(redis),
    )

    settled = await llm_control_service.settle_stale_llm_reservations(now=now)

    await db.refresh(stale)
    await db.refresh(active)
    assert settled == 1
    assert stale.status == "failed"
    assert stale.total_tokens == 400
    assert stale.total_cost_usd == Decimal("0.20000000")
    assert stale.metadata_json["cost_disposition"] == "uncertain_provider_attempt"
    assert stale.metadata_json["stale_reservation"] is True
    assert active.status == "reserved"
    assert str(stale.reservation_id) not in redis.sets[f"llm:concurrency:{user.id}"]
    assert str(active.reservation_id) in redis.sets[f"llm:concurrency:{user.id}"]


async def _async_value(value):
    return value


async def test_redis_cleanup_failure_does_not_fail_completed_call(monkeypatch):
    class BrokenRedis:
        async def srem(self, *_args):
            raise RedisError("redis unavailable")

    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(BrokenRedis()))
    reservation = llm_control_service.LlmReservation(
        id=str(uuid.uuid4()), operation="chat", user_id=uuid.uuid4()
    )

    await llm_control_service._release_redis_concurrency(reservation)


async def test_redis_cleanup_unexpected_failure_propagates(monkeypatch):
    class BrokenRedis:
        async def srem(self, *_args):
            raise RuntimeError("programming error")

    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(BrokenRedis()))
    reservation = llm_control_service.LlmReservation(
        id=str(uuid.uuid4()), operation="chat", user_id=uuid.uuid4()
    )

    with pytest.raises(RuntimeError, match="programming error"):
        await llm_control_service._release_redis_concurrency(reservation)


async def test_reservation_returns_retryable_503_when_redis_is_unavailable(monkeypatch):
    async def _fail_rehydrate(*, force=False):
        raise RedisError("redis unavailable")

    monkeypatch.setattr(llm_control_service, "rehydrate_llm_coordination_state", _fail_rehydrate)

    with pytest.raises(HTTPException) as exc_info:
        await llm_control_service.reserve_llm_call(
            user_id=uuid.uuid4(),
            estimated_tokens=100,
            feature="advisor",
            operation="chat",
            model="gpt-4o-mini",
            book_id=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.headers == {"Retry-After": "2"}


async def test_reservation_rehydrate_unexpected_failure_propagates(monkeypatch):
    async def _fail_rehydrate(*, force=False):
        raise RuntimeError("programming error")

    monkeypatch.setattr(llm_control_service, "rehydrate_llm_coordination_state", _fail_rehydrate)

    with pytest.raises(RuntimeError, match="programming error"):
        await llm_control_service.reserve_llm_call(
            user_id=uuid.uuid4(),
            estimated_tokens=100,
            feature="advisor",
            operation="chat",
            model="gpt-4o-mini",
            book_id=None,
        )


async def test_cost_capacity_protects_unprocessed_words_and_releases_capacity(db):
    user = User(
        email=f"protected-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"protected{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()

    initial = await llm_control_service.summarize_llm_cost_capacity(
        db, user=user, budget_class="interactive"
    )
    assert initial.protected_processing_cost_usd == Decimal("2.50")
    assert initial.available_cost_usd == Decimal("1.30")

    processing_event = ProcessingUsageEvent(
        user_id=user.id,
        usage_kind="initial_ingestion",
        source_id=f"protected:{uuid.uuid4()}",
        word_count=400_000,
        status="reserved",
    )
    db.add(processing_event)
    await db.commit()

    reserved_only = await llm_control_service.summarize_llm_cost_capacity(
        db, user=user, budget_class="interactive"
    )
    assert reserved_only.protected_processing_cost_usd == Decimal("2.50")

    processing_event.status = "consumed"
    await db.commit()

    partially_processed = await llm_control_service.summarize_llm_cost_capacity(
        db, user=user, budget_class="interactive"
    )
    processing = await llm_control_service.summarize_llm_cost_capacity(
        db, user=user, budget_class="processing"
    )
    assert partially_processed.protected_processing_cost_usd == Decimal("1.500")
    assert partially_processed.available_cost_usd == Decimal("2.300")
    assert processing.protected_processing_cost_usd == Decimal("0")
    assert processing.available_cost_usd == Decimal("3.80")


async def test_protected_processing_capacity_uses_summary_month(db):
    user = User(
        email=f"protected-month-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"protectedmonth{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    db.add_all(
        [
            ProcessingUsageEvent(
                user_id=user.id,
                usage_kind="initial_ingestion",
                source_id=f"protected-month-old:{uuid.uuid4()}",
                word_count=900_000,
                status="consumed",
                reserved_at=datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC),
            ),
            ProcessingUsageEvent(
                user_id=user.id,
                usage_kind="initial_ingestion",
                source_id=f"protected-month-current:{uuid.uuid4()}",
                word_count=100_000,
                status="consumed",
                reserved_at=datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC),
            ),
        ]
    )
    await db.commit()

    summary = await llm_control_service.summarize_llm_cost_capacity(
        db,
        user=user,
        budget_class="interactive",
        now=datetime(2026, 9, 15, tzinfo=UTC),
    )

    assert summary.protected_processing_cost_usd == Decimal("2.250")
    assert summary.available_cost_usd == Decimal("1.550")


async def test_cost_capacity_uses_utc_calendar_month_and_resets(db, monkeypatch):
    user = User(
        email=f"month-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"month{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    db.add_all(
        [
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="gpt-4o-mini",
                operation="chat",
                feature="advisor",
                status="succeeded",
                total_cost_usd=Decimal("3.00"),
                created_at=datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC),
            ),
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="gpt-4o-mini",
                operation="chat",
                feature="advisor",
                status="succeeded",
                total_cost_usd=Decimal("0.50"),
                created_at=datetime(2026, 9, 1, tzinfo=UTC),
            ),
        ]
    )
    await db.commit()

    async def _no_protected_capacity(_db, _user, *, reserve_setting, now=None):
        assert reserve_setting == "AUTHOR_LLM_PROCESSING_RESERVE_USD"
        return Decimal("0")

    monkeypatch.setattr(
        llm_control_service, "_protected_processing_cost_usd", _no_protected_capacity
    )
    summary = await llm_control_service.summarize_llm_cost_capacity(
        db,
        user=user,
        budget_class="interactive",
        now=datetime(2026, 9, 15, tzinfo=UTC),
    )

    assert summary.committed_cost_usd == Decimal("0.50000000")
    assert summary.available_cost_usd == Decimal("3.30000000")
    assert summary.resets_at == datetime(2026, 10, 1, tzinfo=UTC)


async def test_processing_cost_efficiency_reports_and_flags_p95(db, caplog):
    users = []
    for label in ("low", "high"):
        user = User(
            email=f"efficiency-{label}-{uuid.uuid4().hex[:8]}@lorevia.app",
            username=f"efficiency{label}{uuid.uuid4().hex[:8]}",
            password_hash="fake",
            tier="author",
        )
        db.add(user)
        users.append(user)
    await db.flush()
    for user, cost in zip(users, (Decimal("0.10"), Decimal("0.30")), strict=True):
        db.add_all(
            [
                LlmUsageEvent(
                    user_id=user.id,
                    provider="openai",
                    model="gpt-4o-mini",
                    operation="chat",
                    feature="chapter_summary",
                    status="succeeded",
                    total_cost_usd=cost,
                    metadata_json={"budget_class": "processing"},
                ),
                ProcessingUsageEvent(
                    user_id=user.id,
                    usage_kind="initial_ingestion",
                    source_id=f"efficiency:{user.id}",
                    word_count=100_000,
                    status="consumed",
                ),
            ]
        )
    db.add(
        LlmUsageEvent(
            user_id=users[1].id,
            provider="openai",
            model="gpt-4o-mini",
            operation="chat",
            feature="advisor_message",
            status="succeeded",
            total_cost_usd=Decimal("1.00"),
            metadata_json={"budget_class": "interactive"},
        )
    )
    db.add(
        LlmUsageEvent(
            user_id=users[0].id,
            provider="openai",
            model="gpt-4o-mini",
            operation="chat",
            feature="chapter_summary_retry",
            status="failed",
            total_cost_usd=Decimal("0.05"),
            metadata_json={
                "budget_class": "processing",
                "cost_disposition": "uncertain_provider_attempt",
            },
        )
    )
    await db.commit()

    summary = await llm_control_service.summarize_monthly_processing_cost_efficiency(db)

    assert summary.p95_cost_per_100k_words_usd == 0.3
    assert summary.total_processing_cost_usd == 0.45
    assert summary.total_processed_words == 200_000
    assert summary.sampled_users == 2
    assert summary.exceeds_acceptance_threshold is True
    assert "llm_processing_cost_p95_exceeded" in caplog.text


async def test_provider_limit_caps_misconfigured_author_reservation_ceiling(db, monkeypatch):
    user = User(
        email=f"provider-limit-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"providerlimit{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.commit()
    monkeypatch.setattr(
        llm_control_service.settings,
        "AUTHOR_LLM_RESERVATION_CEILING_USD",
        5.0,
    )
    monkeypatch.setattr(
        llm_control_service.settings,
        "AUTHOR_LLM_PROVIDER_COST_LIMIT_USD",
        4.0,
    )

    summary = await llm_control_service.summarize_llm_cost_capacity(
        db,
        user=user,
        budget_class="processing",
    )

    assert summary.reservation_ceiling_usd == Decimal("4.0")
    assert summary.provider_cost_limit_usd == Decimal("4.0")
    assert summary.available_cost_usd == Decimal("4.0")


async def test_architect_cost_capacity_is_two_and_a_half_times_author(db):
    author = User(
        email=f"author-cost-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"authorcost{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    architect = User(
        email=f"architect-cost-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"architectcost{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="architect",
    )
    db.add_all([author, architect])
    await db.commit()

    author_summary = await llm_control_service.summarize_llm_cost_capacity(
        db,
        user=author,
        budget_class="processing",
    )
    architect_summary = await llm_control_service.summarize_llm_cost_capacity(
        db,
        user=architect,
        budget_class="processing",
    )

    assert author_summary.provider_cost_limit_usd == Decimal("4.0")
    assert architect_summary.provider_cost_limit_usd == Decimal("10.0")
    assert author_summary.reservation_ceiling_usd == Decimal("3.8")
    assert architect_summary.reservation_ceiling_usd == Decimal("9.5")
    assert architect_summary.available_cost_usd == Decimal("9.5")


async def test_concurrent_reservations_cannot_jointly_cross_author_ceiling(db, monkeypatch):
    user = User(
        email=f"cost-lock-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"costlock{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    db.add(
        LlmUsageEvent(
            user_id=user.id,
            provider="openai",
            model="gpt-4o-mini",
            operation="chat",
            feature="processing",
            status="succeeded",
            total_cost_usd=Decimal("3.79"),
        )
    )
    await db.commit()
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)
    redis = _FakeRedis()

    async def _ready(*, force=False):
        return {"rehydrated": False, "active_reservations": 0, "stale_released": 0}

    monkeypatch.setattr(llm_control_service, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(redis))
    monkeypatch.setattr(llm_control_service, "rehydrate_llm_coordination_state", _ready)

    async def reserve_once(label: str):
        try:
            return await llm_control_service.reserve_llm_call(
                user_id=user.id,
                estimated_prompt_tokens=500_000,
                estimated_completion_tokens=0,
                feature=f"chapter_embedding_{label}",
                operation="embedding",
                model="text-embedding-3-small",
                book_id=None,
                budget_class="processing",
            )
        except HTTPException as exc:
            return exc

    results = await asyncio.gather(reserve_once("a"), reserve_once("b"))

    assert sum(isinstance(item, llm_control_service.LlmReservation) for item in results) == 1
    blocked = next(item for item in results if isinstance(item, HTTPException))
    assert blocked.status_code == 429
    assert blocked.detail["kind"] == "llm_budget"
    committed = await db.scalar(
        select(func.sum(LlmUsageEvent.total_cost_usd)).where(LlmUsageEvent.user_id == user.id)
    )
    assert committed == Decimal("3.80000000")


async def test_author_rejects_model_used_for_wrong_operation_before_provider(db, monkeypatch):
    user = User(
        email=f"model-policy-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"modelpolicy{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.commit()
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)

    async def _ready(*, force=False):
        return {"rehydrated": False, "active_reservations": 0, "stale_released": 0}

    monkeypatch.setattr(llm_control_service, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(llm_control_service, "rehydrate_llm_coordination_state", _ready)

    with pytest.raises(HTTPException) as exc_info:
        await llm_control_service.reserve_llm_call(
            user_id=user.id,
            estimated_prompt_tokens=1_000,
            estimated_completion_tokens=100,
            feature="advisor",
            operation="chat",
            model="text-embedding-3-small",
            book_id=None,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["kind"] == "llm_configuration"


async def test_reservation_settlement_replaces_or_retains_upper_bound(db, monkeypatch):
    user = User(
        email=f"settle-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"settle{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    events = []
    for disposition in ("success", "uncertain", "released"):
        event = LlmUsageEvent(
            user_id=user.id,
            provider="openai",
            model="gpt-4o-mini",
            operation="chat",
            feature=disposition,
            reservation_id=str(uuid.uuid4()),
            status="reserved",
            estimated_tokens=10_000,
            total_tokens=10_000,
            input_cost_usd=Decimal("0.10"),
            output_cost_usd=Decimal("0.20"),
            total_cost_usd=Decimal("0.30"),
        )
        events.append(event)
    db.add_all(events)
    await db.commit()
    sessions = async_sessionmaker(db.bind, expire_on_commit=False)
    redis = _FakeRedis()
    monkeypatch.setattr(llm_control_service, "AsyncSessionLocal", sessions)
    monkeypatch.setattr(llm_control_service, "get_redis", lambda: _async_value(redis))

    reservations = [
        llm_control_service.LlmReservation(
            id=str(event.reservation_id),
            operation="chat",
            user_id=user.id,
            provider="openai",
            model="gpt-4o-mini",
            estimated_cost_usd=Decimal("0.30"),
        )
        for event in events
    ]
    await llm_control_service.finish_llm_reservation_counts(
        reservations[0], prompt_tokens=1_000, completion_tokens=100, total_tokens=1_100
    )
    await llm_control_service.fail_llm_reservation(reservations[1], provider_attempted=True)
    await llm_control_service.fail_llm_reservation(reservations[2], provider_attempted=False)

    for event in events:
        await db.refresh(event)
    assert events[0].status == "succeeded"
    assert events[0].total_cost_usd == Decimal("0.00021000")
    assert events[0].metadata_json["cost_disposition"] == "actual"
    assert events[1].status == "failed"
    assert events[1].total_tokens == 10_000
    assert events[1].total_cost_usd == Decimal("0.30000000")
    assert events[1].metadata_json["cost_disposition"] == "uncertain_provider_attempt"
    assert events[2].status == "failed"
    assert events[2].total_tokens == 0
    assert events[2].total_cost_usd == Decimal("0E-8")
    assert events[2].metadata_json["cost_disposition"] == "released_before_provider"


async def test_success_without_provider_usage_retains_upper_cost_and_tokens(db, monkeypatch):
    user = User(
        id=uuid.uuid4(),
        email=f"missing-usage-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"missingusage{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.flush()
    event = LlmUsageEvent(
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        operation="chat",
        feature="stream_without_usage",
        reservation_id=str(uuid.uuid4()),
        status="reserved",
        estimated_tokens=2_000,
        total_tokens=2_000,
        input_cost_usd=Decimal("0.10"),
        output_cost_usd=Decimal("0.20"),
        total_cost_usd=Decimal("0.30"),
    )
    db.add(event)
    await db.commit()
    monkeypatch.setattr(
        llm_control_service,
        "AsyncSessionLocal",
        async_sessionmaker(db.bind, expire_on_commit=False),
    )
    monkeypatch.setattr(
        llm_control_service,
        "get_redis",
        lambda: _async_value(_FakeRedis()),
    )
    reservation = llm_control_service.LlmReservation(
        id=str(event.reservation_id),
        operation="chat",
        user_id=user.id,
        provider="openai",
        model="gpt-4o-mini",
        estimated_cost_usd=Decimal("0.30"),
    )

    await llm_control_service.finish_llm_reservation(reservation, None)

    await db.refresh(event)
    assert event.status == "succeeded"
    assert event.total_tokens == 2_000
    assert event.total_cost_usd == Decimal("0.30000000")
    assert event.metadata_json["cost_disposition"] == "usage_missing_upper_bound"
