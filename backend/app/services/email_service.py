from html import escape
from typing import Any, cast
from urllib.parse import urlparse

import resend

from app.core.config import settings
from app.utils.trial_email_utils import (
    TRIAL_EMAIL_ENDED,
    TRIAL_EMAIL_ENDING,
    TRIAL_EMAIL_NUDGE,
    TRIAL_EMAIL_STARTED,
)

resend.api_key = settings.RESEND_API_KEY

_PUBLIC_APP_URL = "https://getlorevia.com"
_LOCAL_EMAIL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _send(payload: dict[str, Any]) -> bool:
    # Disable email sending in debug/test environments
    if settings.DEBUG:
        return True

    try:
        resend.Emails.send(cast(Any, payload))
        return True
    except Exception:
        # Email delivery should never block auth or reading flows.
        return False


def _canonical_app_url() -> str:
    raw_value = (settings.APP_URL or "").strip()
    if not raw_value:
        return _PUBLIC_APP_URL

    candidate = raw_value if "://" in raw_value else f"https://{raw_value}"
    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower()

    if hostname in _LOCAL_EMAIL_HOSTS and not settings.DEBUG:
        return _PUBLIC_APP_URL

    if not parsed.scheme or not parsed.netloc:
        return _PUBLIC_APP_URL

    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _app_link(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{_canonical_app_url()}{normalized_path}"


def _button_html(label: str, url: str) -> str:
    safe_label = escape(label)
    safe_url = escape(url, quote=True)
    return (
        f'<a href="{safe_url}" '
        "style=\"display:inline-block;border-radius:999px;background:#101828;color:#f8fafc;"
        "padding:14px 22px;font-size:15px;font-weight:700;line-height:1;text-decoration:none;"
        "box-shadow:0 12px 30px rgba(16,24,40,0.18);\">"
        f"{safe_label}</a>"
    )


def _paragraph(text: str) -> str:
    return f"<p style=\"margin:0 0 16px;color:#344054;font-size:16px;line-height:1.75;\">{text}</p>"


def _support_footer() -> str:
    support_email = escape(settings.SUPPORT_EMAIL)
    app_url = escape(_canonical_app_url(), quote=True)
    return (
        "<div style=\"margin-top:32px;padding-top:24px;border-top:1px solid #e4e7ec;\">"
        "<p style=\"margin:0 0 10px;color:#475467;font-size:14px;line-height:1.7;\">"
        "Need help, want to report a bug, or have feedback on your workflow? "
        f"Reply to this email or reach us at <a href=\"mailto:{support_email}\" "
        f"style=\"color:#0f766e;text-decoration:none;\">{support_email}</a>."
        "</p>"
        "<p style=\"margin:0;color:#667085;font-size:13px;line-height:1.7;\">"
        f"LoreVia helps you keep track of characters, relationships, summaries, and story continuity across long fiction and series. "
        f"<a href=\"{app_url}\" style=\"color:#0f766e;text-decoration:none;\">Open LoreVia</a> anytime."
        "</p>"
        "</div>"
    )


def _render_email(
    *,
    preheader: str,
    eyebrow: str,
    heading: str,
    body_html: str,
    cta_label: str,
    cta_url: str,
    closing_html: str | None = None,
) -> str:
    safe_preheader = escape(preheader)
    safe_eyebrow = escape(eyebrow.upper())
    safe_heading = escape(heading)
    safe_cta_url = escape(cta_url, quote=True)
    closing_section = (
        f"<div style=\"margin-top:20px;\">{closing_html}</div>" if closing_html else ""
    )

    return f"""
    <html>
      <body style="margin:0;padding:0;background:#f5f7fb;font-family:Inter,Segoe UI,Helvetica,Arial,sans-serif;">
        <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
          {safe_preheader}
        </div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb;padding:24px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border:1px solid #eaecf0;border-radius:28px;overflow:hidden;box-shadow:0 24px 60px rgba(16,24,40,0.08);">
                <tr>
                  <td style="padding:40px 40px 28px;background:linear-gradient(135deg,#effcf6 0%,#f8fafc 55%,#ecfeff 100%);border-bottom:1px solid #e4e7ec;">
                    <p style="margin:0 0 14px;color:#0f766e;font-size:12px;font-weight:800;letter-spacing:0.18em;">{safe_eyebrow}</p>
                    <h1 style="margin:0;color:#101828;font-size:31px;line-height:1.2;font-weight:800;">{safe_heading}</h1>
                  </td>
                </tr>
                <tr>
                  <td style="padding:36px 40px 40px;">
                    {body_html}
                    <div style="margin-top:28px;margin-bottom:18px;">
                      {_button_html(cta_label, cta_url)}
                    </div>
                    <p style="margin:0;color:#667085;font-size:13px;line-height:1.7;">
                      Button not working? Copy and paste this link into your browser:
                      <a href="{safe_cta_url}" style="color:#0f766e;text-decoration:none;word-break:break-all;">{safe_cta_url}</a>
                    </p>
                    {closing_section}
                    {_support_footer()}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def _render_stats_grid(stats: list[tuple[str, str]]) -> str:
    cards: list[str] = []
    for value, label in stats:
        cards.append(
            "<td style=\"padding:0 8px 12px;vertical-align:top;\">"
            "<div style=\"min-width:120px;padding:16px 18px;border-radius:20px;background:#f8fafc;border:1px solid #e4e7ec;\">"
            f"<div style=\"margin:0 0 6px;color:#101828;font-size:24px;font-weight:800;line-height:1;\">{escape(value)}</div>"
            f"<div style=\"margin:0;color:#667085;font-size:13px;line-height:1.5;\">{escape(label)}</div>"
            "</div>"
            "</td>"
        )
    return "<table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" style=\"margin:8px -8px 10px;\"><tr>" + "".join(cards) + "</tr></table>"


async def send_processing_complete_with_stats(
    email: str,
    *,
    book_title: str,
    character_count: int,
    relationship_count: int,
    plot_thread_count: int,
    continuity_issue_count: int,
) -> None:
    library_url = _app_link("/library")
    safe_title = escape(book_title)
    stats_html = _render_stats_grid(
        [
            (str(character_count), "characters tracked"),
            (str(relationship_count), "relationships mapped"),
            (str(plot_thread_count), "plot threads found"),
            (str(continuity_issue_count), "continuity flags"),
        ]
    )
    body_html = "".join(
        [
            _paragraph(f"<strong>{safe_title}</strong> is fully processed and ready to explore inside LoreVia."),
            _paragraph(
                "Your workspace is now populated with the people, connections, and story structure you'll want close at hand while you read, revise, or cross-check details."
            ),
            stats_html,
            _paragraph(
                "Open the library to jump back into the book, review extracted profiles, and keep moving without losing the thread."
            ),
        ]
    )
    closing_html = _paragraph("Thanks for reading with LoreVia. We've got your place from here.")
    _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": f"{book_title} is ready in LoreVia",
            "html": _render_email(
                preheader=f"{book_title} is ready with characters, relationships, and story structure waiting for you.",
                eyebrow="Processing complete",
                heading=f"{book_title} is ready",
                body_html=body_html,
                cta_label="Open your library",
                cta_url=library_url,
                closing_html=closing_html,
            ),
        }
    )


async def send_subscription_confirmation(email: str, plan: str) -> None:
    library_url = _app_link("/library")
    plan_name = escape(plan.title())
    body_html = "".join(
        [
            _paragraph(f"You've unlocked <strong>LoreVia {plan_name}</strong>."),
            _paragraph(
                "Your account now has access to a more powerful reading and story-analysis workspace, with deeper continuity support, stronger intelligence tools, and more room to stay in flow."
            ),
            _paragraph(
                "The best next step is simple: head back into your library, upload the book or manuscript you care about most, and let LoreVia do the heavy lifting."
            ),
        ]
    )
    closing_html = _paragraph("We're excited to help you do more with every chapter.")
    _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": f"LoreVia {plan.title()} is now active",
            "html": _render_email(
                preheader=f"Your LoreVia {plan.title()} plan is active and ready to use.",
                eyebrow="Plan activated",
                heading=f"Your LoreVia {plan.title()} plan is live",
                body_html=body_html,
                cta_label="Go to your library",
                cta_url=library_url,
                closing_html=closing_html,
            ),
        }
    )


async def send_onboarding_email(email: str) -> None:
    library_url = _app_link("/library")
    body_html = "".join(
        [
            _paragraph(
                "Your LoreVia workspace is ready. Whether you're keeping up with a dense fantasy series, tracking a mystery with too many moving parts, or revisiting your own manuscript, this is where everything starts to stay organized."
            ),
            _paragraph(
                "Upload a book, open an existing project, or continue where you left off. LoreVia is built to help you remember who matters, what changed, and where the story is heading without breaking your reading momentum."
            ),
            _paragraph(
                "Over time, your library becomes a dependable story workspace: character profiles, relationship context, chapter-level memory, and continuity support all in one place."
            ),
        ]
    )
    closing_html = _paragraph("When you're ready, your library is the best first step.")
    _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": "Your LoreVia workspace is ready",
            "html": _render_email(
                preheader="Open LoreVia and start building a better reading workspace.",
                eyebrow="Welcome to LoreVia",
                heading="Your reading workspace is ready",
                body_html=body_html,
                cta_label="Open your library",
                cta_url=library_url,
                closing_html=closing_html,
            ),
        }
    )


async def send_trial_email(email: str, email_type: str) -> bool:
    pricing_url = _app_link("/pricing")
    library_url = _app_link("/library")
    templates = {
        TRIAL_EMAIL_STARTED: {
            "subject": "Your LoreVia trial starts now",
            "preheader": "Start with the book or manuscript you care about most.",
            "eyebrow": "Trial started",
            "heading": "Your trial is live",
            "body": [
                "You now have time to explore LoreVia the way it's meant to feel: fast, organized, and surprisingly easy to return to when a story gets complicated.",
                "Start with a current read or an active draft. Once it's in your workspace, LoreVia can help you track characters, relationships, summaries, and continuity details without asking you to hold everything in your head.",
                "The fastest way to understand the product is to use it on something you already care about.",
            ],
            "cta_label": "Open your library",
            "cta_url": library_url,
            "closing": "Your trial is the best time to build a workspace around a real story, not a demo.",
        },
        TRIAL_EMAIL_NUDGE: {
            "subject": "A quick nudge from LoreVia",
            "preheader": "Try LoreVia on a real book or manuscript today.",
            "eyebrow": "Trial check-in",
            "heading": "See LoreVia on your real story",
            "body": [
                "If you've been meaning to try LoreVia properly, this is the moment to drop in a chapter, a full book, or the manuscript you keep coming back to.",
                "The value shows up when the names, relationships, and story threads are your own. That's when the workspace starts to feel less like a tool and more like reading support you can trust.",
                "Even one upload is enough to see the difference.",
            ],
            "cta_label": "Try LoreVia now",
            "cta_url": library_url,
            "closing": "You do not need a perfect setup. One real story is enough to get the feel.",
        },
        TRIAL_EMAIL_ENDING: {
            "subject": "Your LoreVia trial ends tomorrow",
            "preheader": "Keep your full workspace and higher limits without interruption.",
            "eyebrow": "Trial ending",
            "heading": "Your trial ends tomorrow",
            "body": [
                "You're close to the end of your trial window.",
                "If LoreVia has become part of how you keep track of a story, this is the right time to keep your momentum going. Upgrading preserves the deeper reading intelligence, stronger author workflows, and higher limits that make the workspace feel seamless.",
                "If you still want a final pass through your library before deciding, now is a good time to do it.",
            ],
            "cta_label": "See plans",
            "cta_url": pricing_url,
            "closing": "If you have questions before upgrading, just reply and we'll help.",
        },
        TRIAL_EMAIL_ENDED: {
            "subject": "Your LoreVia trial has ended",
            "preheader": "Upgrade to restore full access and keep your workspace moving.",
            "eyebrow": "Trial ended",
            "heading": "Your trial has ended",
            "body": [
                "Your trial window has wrapped up, but your LoreVia workspace is still here waiting for you.",
                "Upgrading brings back the full experience: deeper summaries, stronger search, richer continuity support, and the higher-usage workflows that make LoreVia useful on long and demanding projects.",
                "When you're ready to continue, your next step is just one click away.",
            ],
            "cta_label": "Upgrade LoreVia",
            "cta_url": pricing_url,
            "closing": "We'd love to have you back inside the full workspace.",
        },
    }
    template = templates[email_type]
    body_html = "".join(_paragraph(paragraph) for paragraph in template["body"])
    closing_html = _paragraph(template["closing"])
    return _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": template["subject"],
            "html": _render_email(
                preheader=template["preheader"],
                eyebrow=template["eyebrow"],
                heading=template["heading"],
                body_html=body_html,
                cta_label=template["cta_label"],
                cta_url=template["cta_url"],
                closing_html=closing_html,
            ),
        }
    )


async def deliver_verification_email(email: str, token: str) -> tuple[bool, str]:
    verification_url = f"{_app_link('/verify-email')}?token={token}"
    body_html = "".join(
        [
            _paragraph(
                "Confirm your email address to finish setting up your LoreVia account and keep your sign-in secure."
            ),
            _paragraph(
                "This quick step makes sure your workspace, uploads, and account recovery all stay tied to the right inbox from the start."
            ),
            _paragraph("For security, this verification link expires in 24 hours."),
        ]
    )
    closing_html = _paragraph("If you did not create a LoreVia account, you can safely ignore this email.")
    delivered = _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": "Verify your LoreVia email",
            "html": _render_email(
                preheader="Verify your email to finish setting up LoreVia.",
                eyebrow="Account security",
                heading="Verify your email address",
                body_html=body_html,
                cta_label="Verify email",
                cta_url=verification_url,
                closing_html=closing_html,
            ),
        }
    )
    return delivered, verification_url


async def send_new_characters_detected_email(
    email: str,
    book_title: str,
    chapter_number: int,
    character_names: list[str],
) -> None:
    if not character_names:
        return

    preview = ", ".join(escape(name) for name in character_names[:6])
    extra_count = max(0, len(character_names) - 6)
    suffix = f", and {extra_count} more" if extra_count else ""
    plural = "character" if len(character_names) == 1 else "characters"
    safe_title = escape(book_title)
    library_url = _app_link("/library")
    body_html = "".join(
        [
            _paragraph(
                f"LoreVia detected <strong>{len(character_names)} new {plural}</strong> while processing <strong>{safe_title}</strong>, Chapter {chapter_number}."
            ),
            _paragraph(
                f"New names spotted in this upload: <strong>{preview}{suffix}</strong>."
            ),
            _paragraph(
                "Open the workspace to review extracted profiles, confirm details, and keep your cast list clean as the story expands."
            ),
        ]
    )
    closing_html = _paragraph("Useful story memory is often built one chapter at a time. We'll keep watching for you.")
    _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": f"{len(character_names)} new {plural} found in {book_title}",
            "html": _render_email(
                preheader=f"New {plural} were detected in your latest LoreVia upload.",
                eyebrow="Character update",
                heading="New characters spotted",
                body_html=body_html,
                cta_label="Review in LoreVia",
                cta_url=library_url,
                closing_html=closing_html,
            ),
        }
    )


async def deliver_password_reset_email(email: str, token: str) -> tuple[bool, str]:
    reset_url = f"{_app_link('/reset-password')}?token={token}"
    body_html = "".join(
        [
            _paragraph(
                "We received a request to reset your LoreVia password."
            ),
            _paragraph(
                "Use the secure link below to choose a new password and get back into your workspace. For security, this link expires in 1 hour."
            ),
            _paragraph(
                "If you did not request this change, you can ignore this email and your current password will continue to work."
            ),
        ]
    )
    closing_html = _paragraph("If you need a hand regaining access, reply to this email and we'll help.")
    delivered = _send(
        {
            "from": settings.EMAIL_FROM,
            "to": email,
            "subject": "Reset your LoreVia password",
            "html": _render_email(
                preheader="Use this secure link to reset your LoreVia password.",
                eyebrow="Password reset",
                heading="Reset your password",
                body_html=body_html,
                cta_label="Choose a new password",
                cta_url=reset_url,
                closing_html=closing_html,
            ),
        }
    )
    return delivered, reset_url
