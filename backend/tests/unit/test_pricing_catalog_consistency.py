from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.utils.billing_utils import (
    BACKEND_PRICING_CATALOG_PATH,
    PLAN_DISPLAY_NAMES,
    PLAN_PRICE_ID_ENV_KEYS,
    PLAN_PRICES_USD,
    SHARED_PRICING_CATALOG_PATH,
    VALID_PAID_PLAN_CODES,
)


def _load_shared_pricing_catalog() -> dict[str, list[dict[str, object]]]:
    return json.loads(SHARED_PRICING_CATALOG_PATH.read_text(encoding="utf-8"))


def test_shared_pricing_catalog_matches_backend_constants():
    assert SHARED_PRICING_CATALOG_PATH == BACKEND_PRICING_CATALOG_PATH
    assert BACKEND_PRICING_CATALOG_PATH.parts[-3:] == ("app", "data", "pricing-catalog.json")
    catalog = _load_shared_pricing_catalog()
    tiers = catalog["tiers"]
    plans = {str(plan["code"]): plan for plan in catalog["plans"]}
    free_tier = next(tier for tier in tiers if tier["name"] == "Free")
    paid_tiers = [tier for tier in tiers if tier["access"] == "paid"]

    assert free_tier["price_monthly"] == 0
    assert free_tier["price_annual"] == 0
    assert free_tier["monthly_code"] is None
    assert free_tier["annual_code"] is None

    assert [tier["name"] for tier in paid_tiers] == ["Author", "Architect"]
    assert (
        {tier["monthly_code"] for tier in paid_tiers} | {tier["annual_code"] for tier in paid_tiers}
    ) <= VALID_PAID_PLAN_CODES

    for tier in paid_tiers:
        monthly_code = tier["monthly_code"]
        annual_code = tier["annual_code"]
        assert isinstance(monthly_code, str)
        assert isinstance(annual_code, str)

        assert PLAN_DISPLAY_NAMES[monthly_code] == tier["name"]
        assert PLAN_DISPLAY_NAMES[annual_code] == tier["name"]
        assert PLAN_PRICES_USD[monthly_code] == tier["price_monthly"]
        assert PLAN_PRICES_USD[annual_code] == tier["price_annual"]
        assert plans[monthly_code]["checkout_enabled"] is True
        assert plans[annual_code]["checkout_enabled"] is True


def test_shared_pricing_catalog_has_current_subscription_prices():
    assert PLAN_PRICES_USD == {
        "author_monthly": 19,
        "author_annual": 190,
        "architect_monthly": 39,
        "architect_annual": 390,
    }


def test_shared_pricing_catalog_tracks_price_id_env_keys():
    catalog = _load_shared_pricing_catalog()
    plans = {str(plan["code"]): plan for plan in catalog["plans"]}

    assert "reader_monthly" not in plans
    assert "reader_annual" not in plans
    assert PLAN_PRICE_ID_ENV_KEYS["author_monthly"] == plans["author_monthly"]["price_id_env_keys"]
    assert (
        PLAN_PRICE_ID_ENV_KEYS["architect_annual"] == plans["architect_annual"]["price_id_env_keys"]
    )


def test_frontend_pricing_catalog_is_generated_from_backend_source():
    repo_root = Path(__file__).resolve().parents[3]
    frontend_catalog_path = (
        repo_root / "frontend" / "src" / "lib" / "billing" / "pricing-catalog.json"
    )
    if not frontend_catalog_path.exists():
        pytest.skip("Frontend catalog is not copied into the backend-only Docker image.")

    assert json.loads(frontend_catalog_path.read_text(encoding="utf-8")) == json.loads(
        BACKEND_PRICING_CATALOG_PATH.read_text(encoding="utf-8")
    )
