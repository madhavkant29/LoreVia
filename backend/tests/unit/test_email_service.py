import pytest

from app.services import email_service
from app.utils.trial_email_utils import FIRST_MANUSCRIPT_NUDGE, TRIAL_EMAIL_ENDING


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

    delivered, verification_url = await email_service.deliver_verification_email(
        "reader@example.com", "abc123"
    )

    assert delivered is True
    assert verification_url == "https://getlorevia.com/verify-email?token=abc123"
    assert captured[0]["subject"] == "Verify your LoreVia email address"
    assert "localhost" not in captured[0]["html"]
    assert "Verify your email address" in captured[0]["html"]
    assert "expires in 24 hours" in captured[0]["html"]
    assert "support@getlorevia.com" in captured[0]["html"]


@pytest.mark.asyncio
async def test_send_onboarding_email_renders_long_form_LoreVia_copy_without_promotional_gating(
    monkeypatch,
):
    captured: list[dict] = []

    monkeypatch.setattr(
        "app.core.config.settings.APP_URL", "https://getlorevia.com/", raising=False
    )
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    await email_service.send_onboarding_email("reader@example.com")

    html = captured[0]["html"]
    assert captured[0]["subject"] == "Welcome to LoreVia"
    assert "Your workspace is ready" in html
    assert (
        "readers and writers who need a more dependable way to keep track of long stories" in html
    )
    assert "Open your library" in html
    assert "support@getlorevia.com" in html
    assert "You're receiving this because you signed up for LoreVia." not in html
    assert "Manage email preferences" not in html
    assert "headers" not in captured[0]


@pytest.mark.asyncio
async def test_send_subscription_cancellation_uses_transactional_copy_and_pricing_cta(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    await email_service.send_subscription_cancellation("reader@example.com", "author")

    html = captured[0]["html"]
    assert captured[0]["subject"] == "Your LoreVia Author subscription has ended"
    assert "Your paid plan has been canceled" in html
    assert "future billing for this subscription should be stopped" in html
    assert "Review plans" in html
    assert "https://getlorevia.com/pricing" in html
    assert "Manage email preferences" not in html
    assert "headers" not in captured[0]


@pytest.mark.asyncio
async def test_deliver_password_reset_email_uses_query_token_and_security_language(monkeypatch):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered, reset_url = await email_service.deliver_password_reset_email(
        "reader@example.com", "reset-token"
    )

    html = captured[0]["html"]
    assert delivered is True
    assert reset_url == "https://getlorevia.com/reset-password?token=reset-token"
    assert captured[0]["subject"] == "Reset your LoreVia password"
    assert "expires in 1 hour" in html
    assert "choose a new password and regain access to your workspace" in html
    assert "If you did not request a password reset" in html


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
    assert (
        "<strong>The Atlas</strong> has finished processing and is now ready inside LoreVia."
        in html
    )
    assert "characters, relationships, plot threads, and continuity signals" in html
    assert "12" in html
    assert "characters tracked" in html
    assert "7" in html
    assert "relationships mapped" in html
    assert "Open your library" in html


@pytest.mark.asyncio
async def test_send_trial_email_uses_pricing_cta_for_trial_ending_without_promotional_gating(
    monkeypatch,
):
    captured: list[dict] = []

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered = await email_service.send_trial_email("reader@example.com", TRIAL_EMAIL_ENDING)

    html = captured[0]["html"]
    assert delivered is True
    assert captured[0]["subject"] == "Your LoreVia trial ends tomorrow"
    assert "Review plans" in html
    assert "https://getlorevia.com/pricing" in html
    assert "If the workspace is helping you work with stories more clearly" in html
    assert "Manage email preferences" not in html
    assert "headers" not in captured[0]


@pytest.mark.asyncio
async def test_send_trial_email_first_manuscript_nudge_uses_professional_company_copy(monkeypatch):
    captured: list[dict] = []

    async def _fake_promotional_context(**_kwargs):
        return {
            "allowed": True,
            "unsubscribe_url": "https://getlorevia.com/api/v1/email/unsubscribe?token=abc",
            "preferences_url": "https://getlorevia.com/api/v1/email/preferences?token=def",
        }

    monkeypatch.setattr("app.core.config.settings.APP_URL", "https://getlorevia.com", raising=False)
    monkeypatch.setattr(
        "app.core.config.settings.BUSINESS_MAILING_ADDRESS", "123 Story Lane", raising=False
    )
    monkeypatch.setattr(email_service, "_resolve_promotional_context", _fake_promotional_context)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered = await email_service.send_trial_email("reader@example.com", FIRST_MANUSCRIPT_NUDGE)

    html = captured[0]["html"]
    assert delivered is True
    assert captured[0]["subject"] == "Add your first manuscript to LoreVia"
    assert "Bring your first project into LoreVia" in html
    assert "A meaningful trial starts when LoreVia has a real story to work with." in html
    assert "Upload your first manuscript" in html


@pytest.mark.asyncio
async def test_send_categorized_email_adds_visible_unsubscribe_button_for_marketing(monkeypatch):
    captured: list[dict] = []

    async def _fake_promotional_context(**_kwargs):
        return {
            "allowed": True,
            "unsubscribe_url": "https://getlorevia.com/api/v1/email/unsubscribe?token=abc",
            "preferences_url": "https://getlorevia.com/api/v1/email/preferences?token=def",
        }

    monkeypatch.setattr(
        "app.core.config.settings.BUSINESS_MAILING_ADDRESS", "123 Story Lane", raising=False
    )
    monkeypatch.setattr(email_service, "_resolve_promotional_context", _fake_promotional_context)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered = await email_service._send_categorized_email(
        email="reader@example.com",
        subject="LoreVia offer",
        html="<html><body><p>Hello</p></body></html>",
        category="marketing",
    )

    assert delivered is True
    assert "Unsubscribe" in captured[0]["html"]
    assert "Manage email preferences" in captured[0]["html"]
    assert (
        captured[0]["headers"]["List-Unsubscribe"]
        == "<https://getlorevia.com/api/v1/email/unsubscribe?token=abc>"
    )


@pytest.mark.asyncio
async def test_send_feature_launch_email_uses_professional_product_language(monkeypatch):
    captured: list[dict] = []

    async def _fake_promotional_context(**_kwargs):
        return {
            "allowed": True,
            "unsubscribe_url": "https://getlorevia.com/api/v1/email/unsubscribe?token=abc",
            "preferences_url": "https://getlorevia.com/api/v1/email/preferences?token=def",
        }

    monkeypatch.setattr(
        "app.core.config.settings.BUSINESS_MAILING_ADDRESS", "123 Story Lane", raising=False
    )
    monkeypatch.setattr(email_service, "_resolve_promotional_context", _fake_promotional_context)
    monkeypatch.setattr(email_service, "_send", lambda payload: captured.append(payload) or True)

    delivered = await email_service.send_feature_launch_email(
        "reader@example.com",
        feature_name="Revision Command Center",
        feature_url="https://getlorevia.com/revision-command-center",
        summary="A new workflow for tracking revision risks before they spread across the manuscript.",
        benefit_lines=["See downstream effects earlier.", "Keep revision context in one place."],
    )

    html = captured[0]["html"]
    assert delivered is True
    assert captured[0]["subject"] == "New in LoreVia: Revision Command Center"
    assert "We have released <strong>Revision Command Center</strong> in LoreVia." in html
    assert (
        "This update is intended to make LoreVia more useful in real reading and writing workflows"
        in html
    )


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
    assert captured[0]["subject"] == "7 new characters detected in Moon Archive"
    assert "Aoi, Ren, Mira, Seth, Ivo, Lena, and 1 more" in html
    assert "Review in LoreVia" in html
    assert "Chapter 8" in html
    assert "Keeping this information accurate now will make later summaries" in html
