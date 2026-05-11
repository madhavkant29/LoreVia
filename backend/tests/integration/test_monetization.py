import uuid
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

import pytest
from sqlalchemy import select

from app.core.security import decode_token
from app.models.user import PointLedgerEntry, User
from app.services.monetization_service import purchased_overflow_units_for_action
from app.utils.auth_cookies import ACCESS_TOKEN_COOKIE_NAME
from app.utils.monetization_utils import (
    POINT_ACTION_SEARCH,
    POINT_ENTRY_GRANT,
    POINT_SOURCE_FIRST_BOOK,
    POINT_SOURCE_REWARDED_AD,
)


async def _current_user_from_auth_headers(db, auth_headers: dict[str, str]) -> User:
    cookie = SimpleCookie()
    cookie.load(auth_headers["Cookie"])
    token = cookie[ACCESS_TOKEN_COOKIE_NAME].value
    payload = decode_token(token)
    assert payload is not None
    user = await db.get(User, uuid.UUID(payload["sub"]))
    assert user is not None
    return user


@pytest.mark.asyncio
async def test_point_spend_offers_reflect_current_plan(client, auth_headers, db):
    user = await _current_user_from_auth_headers(db, auth_headers)
    user.created_at = datetime.now(UTC) - timedelta(days=30)
    await db.commit()

    response = await client.get("/api/v1/monetization/offers", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    offers = {offer["code"]: offer for offer in payload["offers"]}
    assert offers["search_pack_5"]["eligible"] is True
    assert offers["prediction_overflow_1"]["eligible"] is True
    assert offers["high_cost_overflow_1"]["eligible"] is False


@pytest.mark.asyncio
async def test_spending_points_creates_same_day_search_overflow(client, auth_headers, db):
    user = await _current_user_from_auth_headers(db, auth_headers)
    user.created_at = datetime.now(UTC) - timedelta(days=30)
    db.add(
        PointLedgerEntry(
            user_id=user.id,
            entry_type=POINT_ENTRY_GRANT,
            source_type=POINT_SOURCE_FIRST_BOOK,
            source_id="seed-grant",
            points_delta=25,
        )
    )
    await db.commit()

    response = await client.post(
        "/api/v1/monetization/points/spend",
        headers=auth_headers,
        json={"offer_code": "search_pack_5"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["balance"] == 22
    assert payload["offer"]["code"] == "search_pack_5"
    assert payload["purchased_units_today"] == 5

    purchased_units = await purchased_overflow_units_for_action(db, user.id, POINT_ACTION_SEARCH)
    assert purchased_units == 5


@pytest.mark.asyncio
async def test_rewarded_ad_status_reports_enabled_configuration(client, auth_headers, db, monkeypatch):
    _user = await _current_user_from_auth_headers(db, auth_headers)
    monkeypatch.setattr("app.core.config.settings.REWARDED_ADS_ENABLED", True, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_GPT_UNIT_PATH", "/1234567/lorevia/rewarded", raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_REWARD_POINTS", 3, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_DAILY_CAP", 8, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_SESSION_TTL_SECONDS", 900, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_MIN_GRANT_SECONDS", 0, raising=False)

    response = await client.get("/api/v1/monetization/rewarded-ads/status", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["provider"] == "google_publisher_tag"
    assert payload["reward_points"] == 3
    assert payload["daily_cap"] == 3
    assert payload["claims_remaining_today"] == 3


@pytest.mark.asyncio
async def test_rewarded_ad_session_grants_points_once(client, auth_headers, db, monkeypatch):
    user = await _current_user_from_auth_headers(db, auth_headers)
    monkeypatch.setattr("app.core.config.settings.REWARDED_ADS_ENABLED", True, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_GPT_UNIT_PATH", "/1234567/lorevia/rewarded", raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_REWARD_POINTS", 3, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_DAILY_CAP", 1, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_SESSION_TTL_SECONDS", 900, raising=False)
    monkeypatch.setattr("app.core.config.settings.REWARDED_AD_MIN_GRANT_SECONDS", 0, raising=False)

    start_response = await client.post(
        "/api/v1/monetization/rewarded-ads/session",
        headers=auth_headers,
        json={"placement": "points_wallet"},
    )

    assert start_response.status_code == 200
    session_payload = start_response.json()
    assert session_payload["reward_points"] == 3
    assert session_payload["ad_unit_path"] == "/1234567/lorevia/rewarded"

    resolve_response = await client.post(
        "/api/v1/monetization/rewarded-ads/resolve",
        headers=auth_headers,
        json={
            "session_token": session_payload["session_token"],
            "outcome": "rewarded",
            "reward_type": "points",
            "reward_amount": 1,
        },
    )

    assert resolve_response.status_code == 200
    resolve_payload = resolve_response.json()
    assert resolve_payload["status"] == "rewarded"
    assert resolve_payload["balance"] == 3
    assert resolve_payload["reward_points_granted"] == 3
    assert resolve_payload["claims_remaining_today"] == 0

    ledger_entries = (
        await db.execute(
            select(PointLedgerEntry).where(
                PointLedgerEntry.user_id == user.id,
                PointLedgerEntry.source_type == POINT_SOURCE_REWARDED_AD,
            )
        )
    ).scalars().all()
    assert len(ledger_entries) == 1
