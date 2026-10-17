from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.user import User
from app.services.billing_checkout_service import build_checkout_disclosure
from app.services.paddle_service import PaddlePriceQuote


def test_build_checkout_disclosure_requires_confirmation_during_active_trial():
    now = datetime(2026, 8, 30, tzinfo=UTC)
    user = User(
        email="trial@example.com",
        username="trial-user",
        password_hash="hashed",
        tier="free",
        created_at=now - timedelta(days=2),
    )

    disclosure = build_checkout_disclosure(user, "author_monthly", now=now)

    assert disclosure.trial_status == "active"
    assert disclosure.confirmation_required is True
    assert disclosure.charge_today == "$19.00 USD"
    assert disclosure.recurring_price == "$19.00 USD every month"
    assert disclosure.checkout_button_label == "Pay $19.00 USD now"
    assert disclosure.default_action_label == "Continue free trial"


def test_build_checkout_disclosure_does_not_require_trial_confirmation_after_expiry():
    now = datetime(2026, 8, 30, tzinfo=UTC)
    user = User(
        email="expired@example.com",
        username="expired-user",
        password_hash="hashed",
        tier="free",
        created_at=now - timedelta(days=11),
    )

    disclosure = build_checkout_disclosure(user, "architect_annual", now=now)

    assert disclosure.trial_status == "expired"
    assert disclosure.confirmation_required is False
    assert disclosure.charge_today == "$390.00 USD"
    assert disclosure.recurring_price == "$390.00 USD every year"
    assert disclosure.confirmation_text is None


def test_build_checkout_disclosure_uses_signed_paddle_total(monkeypatch):
    monkeypatch.setattr(
        "app.services.billing_checkout_service.settings.JWT_SECRET",
        "billing-checkout-quote-secret-value",
        raising=False,
    )
    user = User(
        id=uuid4(),
        email="localized@example.com",
        username="localized-user",
        password_hash="hashed",
        tier="free",
        created_at=datetime.now(UTC) - timedelta(days=11),
    )
    quote = PaddlePriceQuote(
        plan="author_monthly",
        price_id="pri_author_monthly",
        amount_minor="1900",
        currency_code="USD",
        formatted_total="$19.00 USD",
        country_code="US",
    )

    disclosure = build_checkout_disclosure(
        user,
        "author_monthly",
        price_quote=quote,
    )

    assert disclosure.charge_today == "$19.00 USD"
    assert disclosure.checkout_button_label == "Pay $19.00 USD now"
    assert disclosure.quote_token
