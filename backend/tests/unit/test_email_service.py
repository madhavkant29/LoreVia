import pytest

from app.services import email_service
from app.utils.trial_email_utils import TRIAL_EMAIL_ENDING


def test_canonical_app_url_falls_back_to_public_domain_for_production_localhost(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)
    monkeypatch.setattr("app.core.config.settings.APP_URL", "http://localhost:3000/", raising=False)

    assert email_service._canonical_app_url() == "https://getlorevia.com"


def test_canonical_app_url_preserves_localhost_in_debug(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.DEBUG", True, raising=False)
    monkeypatch.setattr("app.core.config.settings.APP_URL", "http://localhost:3000/", raising=False)

    assert email_service._canonical_app_url() == "http://localhost:3000"


@pytest.mark.asyncio
async def test_deliver_verification_email_uses_public_safe_url_and_shared_copy(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.DEBUG", False, raising=False)
    monkeypatch.setattr("app.core.config.settings.APP_URL", "http://localhost:3000", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered, verification_url = await email_service.deliver_verification_email("reader@example.com", "abc123")

    assert delivered is True
    assert verification_url == "https://getlorevia.com/verify-email?token=abc123"
    assert captured[0]["subject"] == "Verify your LoreVia email"
    assert "localhost" not in captured[0]["html"]
    assert "Verify your email address" in captured[0]["html"]
    assert "expires in 24 hours" in captured[0]["html"]
    assert "support@getlorevia.com" in captured[0]["html"]


@pytest.mark.asyncio
async def test_send_onboarding_email_renders_long_form_lorevia_copy(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com/", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    await email_service.send_onboarding_email("reader@example.com")

    html = captured[0]["html"]
    assert captured[0]["subject"] == "Your LoreVia workspace is ready"
    assert "Your reading workspace is ready" in html
    assert "character profiles, relationship context, chapter-level memory, and continuity support" in html
    assert "Open your library" in html
    assert "support@getlorevia.com" in html


@pytest.mark.asyncio
async def test_deliver_password_reset_email_uses_query_token_and_security_language(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered, reset_url = await email_service.deliver_password_reset_email("reader@example.com", "reset-token")

    html = captured[0]["html"]
    assert delivered is True
    assert reset_url == "https://getlorevia.com/reset-password?token=reset-token"
    assert captured[0]["subject"] == "Reset your LoreVia password"
    assert "expires in 1 hour" in html
    assert "Choose a new password" in html
    assert "If you did not request this change" in html


@pytest.mark.asyncio
async def test_send_processing_complete_with_stats_renders_metrics_and_library_cta(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    await email_service.send_processing_complete_with_stats(
        "reader@example.com",
        book_title="The Atlas",
        character_count=12,
        relationship_count=7,
        plot_thread_count=4,
        continuity_issue_count=2,
    )

    html = captured[0]["html"]
    assert captured[0]["subject"] == "The Atlas is ready in LoreVia"
    assert "The Atlas is ready" in html
    assert "12" in html
    assert "characters tracked" in html
    assert "7" in html
    assert "relationships mapped" in html
    assert "Open your library" in html


@pytest.mark.asyncio
async def test_send_trial_email_uses_pricing_cta_for_trial_ending(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered = await email_service.send_trial_email("reader@example.com", TRIAL_EMAIL_ENDING)

    html = captured[0]["html"]
    assert delivered is True
    assert captured[0]["subject"] == "Your LoreVia trial ends tomorrow"
    assert "See plans" in html
    assert "https://getlorevia.com/pricing" in html
    assert "If you have questions before upgrading" in html


@pytest.mark.asyncio
async def test_send_new_characters_detected_email_lists_preview_and_review_cta(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    await email_service.send_new_characters_detected_email(
        "reader@example.com",
        "Moon Archive",
        8,
        ["Aoi", "Ren", "Mira", "Seth", "Ivo", "Lena", "Tarin"],
    )

    html = captured[0]["html"]
    assert captured[0]["subject"] == "7 new characters found in Moon Archive"
    assert "Aoi, Ren, Mira, Seth, Ivo, Lena, and 1 more" in html
    assert "Review in LoreVia" in html
    assert "Chapter 8" in html
