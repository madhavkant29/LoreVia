from html import escape
from typing import Any, cast
from urllib.parse import urlparse

import resend
import requests
from resend.exceptions import ResendError
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.utils.email_utils import (
    EMAIL_CATEGORY_MARKETING,
    EMAIL_CATEGORY_PRODUCT_UPDATES,
    EMAIL_CATEGORY_TRANSACTIONAL,
    build_email_preference_links,
    can_send_email,
    get_or_create_email_preference,
)
from app.utils.logging.logger import get_logger
from app.utils.trial_email_utils import (
    FIRST_MANUSCRIPT_NUDGE,
    TRIAL_EMAIL_ENDED,
    TRIAL_EMAIL_ENDING,
    TRIAL_EMAIL_NUDGE,
    TRIAL_EMAIL_STARTED,
)

resend.api_key = settings.RESEND_API_KEY

_PUBLIC_APP_URL = "https://getlorevia.com"
_LOCAL_EMAIL_HOSTS = {"localhost", "127.0.0.1", "::1"}
EMAIL_DELIVERY_EXCEPTIONS = (ResendError, requests.RequestException, TimeoutError)
log = get_logger("lorevia.email")


def _mask_email_address(email: str) -> str:
    local_part, separator, domain = email.strip().partition("@")
    if not separator:
        return "[invalid-email]"
    if not local_part:
        return f"***@{domain}"
    if len(local_part) == 1:
        return f"{local_part}***@{domain}"
    return f"{local_part[0]}***{local_part[-1]}@{domain}"


def _send(payload: dict[str, Any]) -> bool:
    # Disable email sending in debug/test environments
    if settings.DEBUG:
        log.info(
            "email_send_skipped_debug",
            extra={
                "subject": str(payload.get("subject") or ""),
                "recipient": _mask_email_address(str(payload.get("to") or "")),
            },
        )
        return True

    try:
        response = resend.Emails.send(cast(Any, payload))
        log.info(
            "email_send_succeeded",
            extra={
                "subject": str(payload.get("subject") or ""),
                "recipient": _mask_email_address(str(payload.get("to") or "")),
                "provider_message_id": getattr(response, "id", None),
            },
        )
        return True
    except EMAIL_DELIVERY_EXCEPTIONS:
        # Email delivery should never block auth or reading flows.
        log.exception(
            "email_send_failed",
            extra={
                "subject": str(payload.get("subject") or ""),
                "recipient": _mask_email_address(str(payload.get("to") or "")),
            },
        )
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


def _plan_display_name(plan: str) -> str:
    normalized = " ".join(
        part for part in str(plan).replace("-", " ").replace("_", " ").split() if part
    )
    return normalized.title() if normalized else "Paid"


def _api_link(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{_canonical_app_url()}{settings.API_V1_PREFIX}{normalized_path}"


def _button_html(label: str, url: str) -> str:
    safe_label = escape(label)
    safe_url = escape(url, quote=True)
    return (
        f'<a href="{safe_url}" '
        'style="display:inline-block;border-radius:999px;background:linear-gradient(135deg,#0f766e 0%,#115e59 100%);'
        "color:#f8fafc;padding:14px 22px;font-size:15px;font-weight:700;line-height:1;text-decoration:none;"
        'box-shadow:0 14px 34px rgba(15,118,110,0.24);border:1px solid rgba(255,255,255,0.18);">'
        f"{safe_label}</a>"
    )


def _paragraph(text: str) -> str:
    return f'<p style="margin:0 0 16px;color:#344054;font-size:16px;line-height:1.75;">{text}</p>'


def _list_panel(title: str, items: list[str]) -> str:
    safe_title = escape(title)
    rows = "".join(
        (
            '<li style="margin:0 0 10px;color:#344054;font-size:15px;line-height:1.7;">'
            f"{escape(item)}"
            "</li>"
        )
        for item in items
    )
    return (
        '<div style="margin:10px 0 22px;padding:18px 20px;border-radius:22px;'
        'background:linear-gradient(180deg,#f8fafc 0%,#f3f7fb 100%);border:1px solid #e4e7ec;">'
        f'<p style="margin:0 0 12px;color:#101828;font-size:13px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">{safe_title}</p>'
        f'<ul style="margin:0;padding-left:20px;">{rows}</ul>'
        "</div>"
    )


def _support_footer() -> str:
    support_email = escape(settings.SUPPORT_EMAIL)
    app_url = escape(_canonical_app_url(), quote=True)
    return (
        '<div style="margin-top:28px;padding:22px 22px 20px;border-radius:22px;'
        'background:linear-gradient(180deg,#f8fafc 0%,#f2f7fb 100%);border:1px solid #e4e7ec;">'
        '<p style="margin:0 0 10px;color:#101828;font-size:14px;font-weight:700;line-height:1.7;">'
        "Need help?"
        "</p>"
        '<p style="margin:0 0 10px;color:#475467;font-size:14px;line-height:1.7;">'
        "Need help with your account, uploads, billing, or workspace? "
        f'Reply to this email or reach us at <a href="mailto:{support_email}" '
        f'style="color:#0f766e;text-decoration:none;">{support_email}</a>.'
        "</p>"
        '<p style="margin:0 0 10px;color:#667085;font-size:13px;line-height:1.7;">'
        "LoreVia helps readers and writers keep track of characters, relationships, summaries, continuity details, and story context across long-form fiction."
        "</p>"
        '<p style="margin:0;color:#667085;font-size:13px;line-height:1.7;">'
        f'<a href="{app_url}" style="color:#0f766e;text-decoration:none;">Open LoreVia</a>'
        "</p>"
        "</div>"
    )


def _promotional_footer(
    *,
    unsubscribe_url: str,
    preferences_url: str,
    include_unsubscribe_button: bool,
) -> str:
    safe_unsubscribe_url = escape(unsubscribe_url, quote=True)
    safe_preferences_url = escape(preferences_url, quote=True)
    mailing_address = escape((settings.BUSINESS_MAILING_ADDRESS or "").strip())
    button_html = (
        f'<div style="margin:18px 0 14px;">{_button_html("Unsubscribe", unsubscribe_url)}</div>'
        if include_unsubscribe_button
        else ""
    )
    return (
        '<div style="margin-top:24px;padding:22px 22px 20px;border-radius:22px;'
        'background:linear-gradient(180deg,#fffaf0 0%,#fff6e8 100%);border:1px solid #f2e4c2;">'
        '<p style="margin:0 0 10px;color:#7a2e0e;font-size:13px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">Email preferences</p>'
        '<p style="margin:0 0 12px;color:#475467;font-size:14px;line-height:1.7;">'
        "You're receiving this because you signed up for LoreVia."
        "</p>"
        f"{button_html}"
        '<p style="margin:0 0 10px;color:#475467;font-size:14px;line-height:1.7;">'
        f'Unsubscribe from these emails: <a href="{safe_unsubscribe_url}" style="color:#0f766e;text-decoration:none;word-break:break-all;">{safe_unsubscribe_url}</a>'
        "</p>"
        '<p style="margin:0 0 12px;color:#475467;font-size:14px;line-height:1.7;">'
        f'Manage email preferences: <a href="{safe_preferences_url}" style="color:#0f766e;text-decoration:none;word-break:break-all;">{safe_preferences_url}</a>'
        "</p>"
        '<p style="margin:0;color:#667085;font-size:13px;line-height:1.7;white-space:pre-line;">'
        f"LoreVia\n{mailing_address}"
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
    closing_section = f'<div style="margin-top:20px;">{closing_html}</div>' if closing_html else ""

    return f"""
    <html>
      <body style="margin:0;padding:0;background:#eef3f8;font-family:Inter,Segoe UI,Helvetica,Arial,sans-serif;">
        <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
          {safe_preheader}
        </div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:linear-gradient(180deg,#eef3f8 0%,#f8fafc 100%);padding:32px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;background:#ffffff;border:1px solid #dfe7ef;border-radius:32px;overflow:hidden;box-shadow:0 28px 70px rgba(16,24,40,0.10);">
                <tr>
                  <td style="padding:24px 40px 0;background:#ffffff;">
                    <div style="display:inline-block;padding:8px 14px;border-radius:999px;background:#ecfdf3;border:1px solid #abefc6;color:#067647;font-size:12px;font-weight:800;letter-spacing:0.16em;text-transform:uppercase;">
                      LoreVia
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:24px 40px 28px;background:linear-gradient(135deg,#effcf6 0%,#f8fafc 50%,#ecfeff 100%);border-bottom:1px solid #e4e7ec;">
                    <p style="margin:0 0 14px;color:#0f766e;font-size:12px;font-weight:800;letter-spacing:0.18em;">{safe_eyebrow}</p>
                    <h1 style="margin:0;color:#101828;font-size:31px;line-height:1.2;font-weight:800;">{safe_heading}</h1>
                    <p style="margin:14px 0 0;color:#475467;font-size:15px;line-height:1.7;">
                      Clear account updates for readers and writers using LoreVia to manage long-form story context.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:36px 40px 40px;">
                    <div style="padding:28px;border-radius:26px;background:linear-gradient(180deg,#ffffff 0%,#f8fbff 100%);border:1px solid #edf2f7;">
                      {body_html}
                    </div>
                    <div style="margin-top:24px;padding:20px 22px;border-radius:24px;background:linear-gradient(180deg,#f0fdf9 0%,#ecfeff 100%);border:1px solid #ccfbf1;">
                      <p style="margin:0 0 14px;color:#0f172a;font-size:14px;font-weight:700;line-height:1.6;">
                        Ready for the next step?
                      </p>
                      <div style="margin:0 0 16px;">
                        {_button_html(cta_label, cta_url)}
                      </div>
                      <p style="margin:0;color:#475467;font-size:13px;line-height:1.7;">
                        Button not working? Copy and paste this link into your browser:
                        <a href="{safe_cta_url}" style="color:#0f766e;text-decoration:none;word-break:break-all;">{safe_cta_url}</a>
                      </p>
                    </div>
                    {closing_section}
                    <!-- PROMOTIONAL_FOOTER -->
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


def _inject_promotional_footer(html: str, footer_html: str) -> str:
    marker = "<!-- PROMOTIONAL_FOOTER -->"
    if marker in html:
        return html.replace(marker, footer_html)
    if "</body>" in html:
        return html.replace("</body>", footer_html + "</body>")
    return html + footer_html


async def _resolve_promotional_context(
    *,
    email: str,
    category: str,
) -> dict[str, Any] | None:
    if category == EMAIL_CATEGORY_TRANSACTIONAL:
        return {"allowed": True}

    if not (settings.BUSINESS_MAILING_ADDRESS or "").strip():
        log.warning(
            "promotional_email_suppressed_missing_business_mailing_address",
            extra={
                "category": category,
                "recipient": _mask_email_address(email),
            },
        )
        return None

    normalized_email = email.strip().lower()
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(func.lower(User.email) == normalized_email))
        ).scalar_one_or_none()
        if user is None:
            log.warning(
                "promotional_email_suppressed_missing_user",
                extra={
                    "category": category,
                    "recipient": _mask_email_address(normalized_email),
                },
            )
            return None
        preference = await get_or_create_email_preference(db, user=user, email=normalized_email)
        await db.commit()
        await db.refresh(preference)
        if not can_send_email(preference, category):
            log.info(
                "promotional_email_suppressed_by_preferences",
                extra={
                    "category": category,
                    "recipient": _mask_email_address(normalized_email),
                },
            )
            return None
        links = await build_email_preference_links(user)
        return {
            "allowed": True,
            "unsubscribe_url": links.unsubscribe_url,
            "preferences_url": links.preferences_url,
            "browser_unsubscribe_url": getattr(links, "browser_unsubscribe_url", links.unsubscribe_url),
        }


async def _send_categorized_email(
    *,
    email: str,
    subject: str,
    html: str,
    category: str,
) -> bool:
    payload: dict[str, Any] = {
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": subject,
        "html": html,
    }

    if category != EMAIL_CATEGORY_TRANSACTIONAL:
        context = await _resolve_promotional_context(email=email, category=category)
        if not context or not context.get("allowed"):
            return False
        unsubscribe_url = str(context["unsubscribe_url"])
        browser_unsubscribe_url = str(context.get("browser_unsubscribe_url") or unsubscribe_url)
        preferences_url = str(context["preferences_url"])
        include_unsubscribe_button = category == EMAIL_CATEGORY_MARKETING
        payload["html"] = _inject_promotional_footer(
            html,
            _promotional_footer(
                unsubscribe_url=browser_unsubscribe_url,
                preferences_url=preferences_url,
                include_unsubscribe_button=include_unsubscribe_button,
            ),
        )
        payload["headers"] = {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    else:
        payload["html"] = html.replace("<!-- PROMOTIONAL_FOOTER -->", "")

    return _send(payload)


def _render_stats_grid(stats: list[tuple[str, str]]) -> str:
    cards: list[str] = []
    for value, label in stats:
        cards.append(
            '<td style="padding:0 8px 12px;vertical-align:top;">'
            '<div style="min-width:120px;padding:16px 18px;border-radius:20px;background:#f8fafc;border:1px solid #e4e7ec;">'
            f'<div style="margin:0 0 6px;color:#101828;font-size:24px;font-weight:800;line-height:1;">{escape(value)}</div>'
            f'<div style="margin:0;color:#667085;font-size:13px;line-height:1.5;">{escape(label)}</div>'
            "</div>"
            "</td>"
        )
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" style="margin:8px -8px 10px;"><tr>'
        + "".join(cards)
        + "</tr></table>"
    )


def _trial_email_category(email_type: str) -> str:
    if email_type in {TRIAL_EMAIL_STARTED, TRIAL_EMAIL_ENDING, TRIAL_EMAIL_ENDED}:
        return EMAIL_CATEGORY_TRANSACTIONAL
    return EMAIL_CATEGORY_PRODUCT_UPDATES


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
            _paragraph(
                f"<strong>{safe_title}</strong> has finished processing and is now ready inside LoreVia."
            ),
            _paragraph(
                "LoreVia has analyzed the manuscript structure and prepared the core story context your workspace needs: characters, relationships, plot threads, and continuity signals. This gives you a more reliable starting point for reviewing the book, asking grounded questions, and keeping track of details across chapters."
            ),
            _paragraph(
                "You can now open the project to inspect what was extracted, refine any details that need correction, and continue reading or revising with the story memory already in place."
            ),
            stats_html,
            _paragraph(
                "The numbers below are not meant to be final editorial judgments. They are a structured snapshot of what LoreVia found so you can review the material faster and decide what matters."
            ),
        ]
    )
    closing_html = _paragraph(
        "Your project is ready. Open your library when you want to continue from the processed version."
    )
    await _send_categorized_email(
        email=email,
        subject=f"{book_title} is ready in LoreVia",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader=f"{book_title} has finished processing with characters, relationships, plot threads, and continuity signals prepared.",
            eyebrow="Processing complete",
            heading=f"{book_title} is ready",
            body_html=body_html,
            cta_label="Open your library",
            cta_url=library_url,
            closing_html=closing_html,
        ),
    )


async def send_subscription_confirmation(email: str, plan: str) -> None:
    library_url = _app_link("/library")
    plan_label = _plan_display_name(plan)
    plan_name = escape(plan_label)
    body_html = "".join(
        [
            _paragraph(f"Your <strong>LoreVia {plan_name}</strong> subscription is now active."),
            _paragraph(
                "Your account has been updated with the access, capacity, and workspace features included in your plan. You can continue using LoreVia for manuscript analysis, character tracking, continuity review, chapter-level recall, and grounded story questions without interrupting your current workflow."
            ),
            _list_panel(
                "What you can do now",
                [
                    "Return to the project you were already reading, drafting, or revising.",
                    "Use the higher-capacity workspace features tied to your active plan.",
                    "Keep tracking long-form story context without restarting your workflow.",
                ],
            ),
            _paragraph(
                "The best next step is to return to your library and continue with the project you care about most. If you are working on a draft, you can use LoreVia to review character consistency, track relationship changes, and keep long-form story context easier to manage."
            ),
            _paragraph(
                "If this subscription was not expected, or if you need help with billing, account access, or plan details, reply to this email and we will help you review it."
            ),
        ]
    )
    closing_html = _paragraph(
        "Thank you for using LoreVia as part of your reading and writing workflow."
    )
    await _send_categorized_email(
        email=email,
        subject=f"LoreVia {plan_label} is now active",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader=f"Your LoreVia {plan_label} subscription is active and ready to use.",
            eyebrow="Plan activated",
            heading=f"Your LoreVia {plan_label} plan is live",
            body_html=body_html,
            cta_label="Go to your library",
            cta_url=library_url,
            closing_html=closing_html,
        ),
    )


async def send_subscription_cancellation(email: str, plan: str) -> None:
    pricing_url = _app_link("/pricing")
    plan_label = _plan_display_name(plan)
    plan_name = escape(plan_label)
    body_html = "".join(
        [
            _paragraph(
                f"Your <strong>LoreVia {plan_name}</strong> subscription is no longer active."
            ),
            _paragraph(
                "This means the paid plan connected to this subscription has ended, and future billing for this subscription should be stopped unless you start a new paid plan later."
            ),
            _list_panel(
                "What this means now",
                [
                    "Your account will follow the access level of your current plan state going forward.",
                    "If you want paid access again, you can restart from the pricing page at any time.",
                    "If this cancellation looks unexpected, reply to this email so billing can be reviewed.",
                ],
            ),
            _paragraph(
                "If you were actively using LoreVia for drafting, revision, continuity review, or long-form reading, you can restart whenever the workspace becomes useful again. Your best next step is to review the available plans and choose one only if it matches how you actually work."
            ),
            _paragraph(
                "If you canceled intentionally, no further action is required right now. If you need help with invoices, account access, or restarting service later, reply to this email and support can help."
            ),
        ]
    )
    closing_html = _paragraph("Thanks for having used LoreVia in your reading or writing workflow.")
    await _send_categorized_email(
        email=email,
        subject=f"Your LoreVia {plan_label} subscription has ended",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader=f"Your LoreVia {plan_label} subscription is no longer active.",
            eyebrow="Subscription ended",
            heading="Your paid plan has been canceled",
            body_html=body_html,
            cta_label="Review plans",
            cta_url=pricing_url,
            closing_html=closing_html,
        ),
    )


async def send_onboarding_email(email: str) -> None:
    library_url = _app_link("/library")
    body_html = "".join(
        [
            _paragraph("Welcome to LoreVia. Your workspace is ready."),
            _paragraph(
                "LoreVia is built for readers and writers who need a more dependable way to keep track of long stories. Instead of manually maintaining scattered notes, you can use LoreVia to organize characters, relationships, summaries, continuity details, and story context in one place."
            ),
            _paragraph(
                "To get the most value, start with one real book, manuscript, or draft. Once the project is inside LoreVia, the system can begin building useful context around the people, events, and threads that matter to that story."
            ),
            _paragraph(
                "After processing, you can review extracted character profiles, revisit chapter-level summaries, ask grounded questions, and use the workspace as a memory layer for the story."
            ),
            _paragraph(
                "You do not need to set everything up perfectly on day one. Add one project, review the results, and let your workspace become more useful as you continue."
            ),
        ]
    )
    closing_html = _paragraph("Your library is the best place to begin.")
    await _send_categorized_email(
        email=email,
        subject="Welcome to LoreVia",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader="Your LoreVia workspace is ready. Start by adding one book, manuscript, or draft.",
            eyebrow="Welcome to LoreVia",
            heading="Your workspace is ready",
            body_html=body_html,
            cta_label="Open your library",
            cta_url=library_url,
            closing_html=closing_html,
        ),
    )


async def send_trial_email(email: str, email_type: str) -> bool:
    pricing_url = _app_link("/pricing")
    library_url = _app_link("/library")
    templates = {
        TRIAL_EMAIL_STARTED: {
            "subject": "Your LoreVia trial has started",
            "preheader": "Start your trial with one real manuscript, book, or draft.",
            "eyebrow": "Trial started",
            "heading": "Your LoreVia trial is now active",
            "body": [
                "Your LoreVia trial has started, and your workspace is ready to use.",
                "The most useful way to evaluate LoreVia is to test it on a real project. Upload a manuscript, draft, or book that you already care about so you can see how the workspace handles actual story structure, character context, relationship changes, and continuity details.",
                "LoreVia is designed to help with the parts of long-form fiction that become difficult to hold in memory: who changed, what happened earlier, which relationships matter, and where the story may be contradicting itself.",
                "During the trial, try opening a processed project, reviewing the character profiles, checking chapter summaries, and asking questions that would normally require searching through the text manually.",
                "You do not need to migrate your whole writing process immediately. One serious project is enough to understand whether LoreVia fits your workflow.",
            ],
            "cta_label": "Open your library",
            "cta_url": library_url,
            "closing": "Start with real material. That is where LoreVia becomes easiest to judge.",
        },
        FIRST_MANUSCRIPT_NUDGE: {
            "subject": "Add your first manuscript to LoreVia",
            "preheader": "One real project is enough to start seeing how LoreVia works.",
            "eyebrow": "Getting started",
            "heading": "Bring your first project into LoreVia",
            "body": [
                "It looks like your LoreVia workspace may still be waiting for its first manuscript or book.",
                "Adding one real project is the fastest way to understand the product. Once LoreVia has actual story material to work with, it can begin preparing character context, relationship information, chapter-level memory, and continuity signals.",
                "You do not need a polished final draft. A working manuscript, an early draft, or a book you are actively reading is enough. LoreVia is meant to support real reading and writing workflows, not just clean demo files.",
                "After upload and processing, you can review what LoreVia extracted, correct anything that needs adjustment, and start using the workspace as a structured memory layer for the story.",
                "If you are evaluating LoreVia for writing, choose the project where continuity, character tracking, or long-term recall is currently causing the most friction.",
            ],
            "cta_label": "Upload your first manuscript",
            "cta_url": library_url,
            "closing": "A meaningful trial starts when LoreVia has a real story to work with.",
        },
        TRIAL_EMAIL_NUDGE: {
            "subject": "A practical next step for your LoreVia trial",
            "preheader": "Use your trial on a real story before the trial window closes.",
            "eyebrow": "Trial check-in",
            "heading": "Try LoreVia on the project that matters most",
            "body": [
                "This is a good moment to give your LoreVia trial a practical test.",
                "If you have already uploaded a project, open it again and review the parts that would normally take time to reconstruct manually: character details, relationship context, chapter summaries, and continuity notes.",
                "If you have not uploaded anything yet, choose one manuscript, draft, or book and add it to your library. LoreVia is most useful when it is working with the same material you are actively reading, revising, or planning.",
                "A strong trial does not require a complicated setup. Try a few grounded questions, inspect the extracted profiles, and see whether the workspace helps you move through the story with less friction.",
                "The goal is simple: determine whether LoreVia saves you time and gives you a clearer memory of your story world.",
            ],
            "cta_label": "Continue your trial",
            "cta_url": library_url,
            "closing": "One focused session with a real project will tell you more than a generic walkthrough.",
        },
        TRIAL_EMAIL_ENDING: {
            "subject": "Your LoreVia trial ends tomorrow",
            "preheader": "Review your workspace and choose whether to continue with a paid plan.",
            "eyebrow": "Trial ending",
            "heading": "Your trial ends tomorrow",
            "body": [
                "Your LoreVia trial is scheduled to end tomorrow.",
                "Before it ends, it is worth reviewing the project you tested most seriously. Check whether LoreVia helped you keep track of characters, relationships, chapter context, continuity details, or story questions that would otherwise require manual searching.",
                "If LoreVia has become useful for your reading or writing workflow, upgrading will keep the higher-capacity workspace available without disrupting your current projects.",
                "A paid plan is most valuable if you are using LoreVia for active drafting, revision, long-form reading, series tracking, or continuity-heavy work where losing context costs time.",
                "You can review the available plans and choose the one that matches your usage.",
            ],
            "cta_label": "Review plans",
            "cta_url": pricing_url,
            "closing": "If the workspace is helping you work with stories more clearly, this is the right time to continue.",
        },
        TRIAL_EMAIL_ENDED: {
            "subject": "Your LoreVia trial has ended",
            "preheader": "Your workspace is still here when you are ready to continue.",
            "eyebrow": "Trial ended",
            "heading": "Your trial has ended",
            "body": [
                "Your LoreVia trial has ended.",
                "Your workspace and project context may still be available, but continued access to the full paid workflow depends on your plan status. If you want to keep using LoreVia for manuscript analysis, continuity review, character tracking, and grounded story questions, you can continue by choosing a paid plan.",
                "If you tested LoreVia with a real project, you already have the best signal: whether it helped you understand, remember, or review the story faster than your usual process.",
                "Upgrading is mainly useful when LoreVia has become part of an active workflow, for example, when you are revising a draft, managing a large cast, checking continuity, or reading a long series with many moving parts.",
                "When you are ready, you can reopen your workspace and continue from there.",
            ],
            "cta_label": "Continue with LoreVia",
            "cta_url": pricing_url,
            "closing": "Your story workspace is ready when you want to keep going.",
        },
    }
    template = templates[email_type]
    body_html = "".join(_paragraph(paragraph) for paragraph in template["body"])
    closing_html = _paragraph(template["closing"])
    return await _send_categorized_email(
        email=email,
        subject=template["subject"],
        category=_trial_email_category(email_type),
        html=_render_email(
            preheader=template["preheader"],
            eyebrow=template["eyebrow"],
            heading=template["heading"],
            body_html=body_html,
            cta_label=template["cta_label"],
            cta_url=template["cta_url"],
            closing_html=closing_html,
        ),
    )


async def send_usage_limit_upgrade_offer_email(
    email: str,
    *,
    focus_area: str,
) -> bool:
    pricing_url = _app_link("/pricing")
    focus = escape(focus_area)
    body_html = "".join(
        [
            _paragraph(
                f"You have reached LoreVia's current <strong>{focus}</strong> limits multiple times in a short period."
            ),
            _paragraph(
                "That usually means LoreVia is no longer just something you are trying casually. It may already be part of how you read, revise, analyze, or manage long-form story material."
            ),
            _paragraph(
                "When you are working with a real manuscript or a large book, interruptions can break momentum. A higher plan gives you more capacity so you can continue asking questions, reviewing story context, and working through continuity details with fewer pauses."
            ),
            _paragraph(
                "Upgrading is not necessary for everyone. It makes sense if you are actively using LoreVia for serious reading, drafting, revision, series tracking, or manuscript analysis."
            ),
            _paragraph(
                "You can review the available plans and choose the one that matches your actual usage."
            ),
        ]
    )
    closing_html = _paragraph(
        "If LoreVia is becoming a regular part of your workflow, the paid plans are designed for that pace."
    )
    return await _send_categorized_email(
        email=email,
        subject="More capacity for your LoreVia workspace",
        category=EMAIL_CATEGORY_MARKETING,
        html=_render_email(
            preheader="You have been using LoreVia actively. A higher plan can give you more room to continue.",
            eyebrow="Upgrade option",
            heading="You may be ready for more capacity",
            body_html=body_html,
            cta_label="Review plans",
            cta_url=pricing_url,
            closing_html=closing_html,
        ),
    )


async def send_feature_launch_email(
    email: str,
    *,
    feature_name: str,
    feature_url: str,
    summary: str,
    benefit_lines: list[str] | None = None,
) -> bool:
    safe_summary = escape(summary)
    safe_feature_name = escape(feature_name)
    body_sections = [
        _paragraph(f"We have released <strong>{safe_feature_name}</strong> in LoreVia."),
        _paragraph(safe_summary),
        _paragraph(
            "This update is intended to make LoreVia more useful in real reading and writing workflows, especially when you are working with long stories, complex casts, evolving relationships, or continuity-heavy projects."
        ),
    ]
    if benefit_lines:
        body_sections.append(_paragraph("Here is what this update can help with:"))
        for line in benefit_lines:
            body_sections.append(_paragraph(escape(line)))
    body_sections.append(
        _paragraph(
            "You can open LoreVia to try the feature in your own workspace. As always, the most useful test is to use it on a real project rather than a sample file."
        )
    )
    body_sections.append(
        _paragraph(
            "If you notice anything confusing, incomplete, or slower than expected, reply to this email. Product feedback from real projects is especially useful while LoreVia continues to improve."
        )
    )
    return await _send_categorized_email(
        email=email,
        subject=f"New in LoreVia: {feature_name}",
        category=EMAIL_CATEGORY_PRODUCT_UPDATES,
        html=_render_email(
            preheader=f"{feature_name} is now available in your LoreVia workspace.",
            eyebrow="Product update",
            heading=f"Introducing {feature_name}",
            body_html="".join(body_sections),
            cta_label="See what's new",
            cta_url=feature_url,
            closing_html=_paragraph(
                "We are continuing to build LoreVia as a serious working environment for long-form fiction."
            ),
        ),
    )


async def deliver_verification_email(email: str, token: str) -> tuple[bool, str]:
    verification_url = f"{_app_link('/verify-email')}?token={token}"
    body_html = "".join(
        [
            _paragraph(
                "Please verify your email address to finish setting up your LoreVia account."
            ),
            _paragraph(
                "Verification helps make sure your workspace, uploads, account notifications, and recovery options are connected to the correct inbox."
            ),
            _paragraph(
                "Click the button below to confirm your email address. For security, this verification link expires in 24 hours."
            ),
            _paragraph(
                "If the button does not work, copy the link shown below the button and paste it into your browser."
            ),
            _paragraph(
                "If you did not create a LoreVia account, you can safely ignore this email. No action is needed."
            ),
        ]
    )
    closing_html = _paragraph("Thanks for helping keep your LoreVia account secure.")
    delivered = await _send_categorized_email(
        email=email,
        subject="Verify your LoreVia email address",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader="Confirm your email address to finish setting up your LoreVia account.",
            eyebrow="Account security",
            heading="Verify your email address",
            body_html=body_html,
            cta_label="Verify email",
            cta_url=verification_url,
            closing_html=closing_html,
        ),
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
                f"New names identified in this chapter: <strong>{preview}{suffix}</strong>."
            ),
            _paragraph(
                "This update helps keep your cast list current as the story expands. New character detection is especially useful in long manuscripts, multi-POV stories, mysteries, fantasy worlds, and series where small introductions can become important later."
            ),
            _paragraph(
                "Open the project to review the detected characters, confirm whether they should be tracked, and clean up any aliases, duplicates, or minor mentions that do not need full profiles."
            ),
            _paragraph(
                "Keeping this information accurate now will make later summaries, relationship tracking, and continuity checks more reliable."
            ),
        ]
    )
    closing_html = _paragraph(
        "LoreVia will continue watching for new story context as your project grows."
    )
    await _send_categorized_email(
        email=email,
        subject=f"{len(character_names)} new {plural} detected in {book_title}",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader=f"LoreVia found new {plural} while processing Chapter {chapter_number}.",
            eyebrow="Character update",
            heading="New characters spotted",
            body_html=body_html,
            cta_label="Review in LoreVia",
            cta_url=library_url,
            closing_html=closing_html,
        ),
    )


async def deliver_password_reset_email(email: str, token: str) -> tuple[bool, str]:
    reset_url = f"{_app_link('/reset-password')}?token={token}"
    body_html = "".join(
        [
            _paragraph("We received a request to reset the password for your LoreVia account."),
            _paragraph(
                "Use the secure link below to choose a new password and regain access to your workspace. For security, this link expires in 1 hour."
            ),
            _paragraph(
                "If you requested this reset, click the button and follow the instructions on the password reset page."
            ),
            _paragraph(
                "If you did not request a password reset, you can ignore this email. Your current password will remain unchanged."
            ),
            _paragraph(
                "For additional safety, avoid forwarding this email or sharing the reset link with anyone."
            ),
        ]
    )
    closing_html = _paragraph(
        "If you are having trouble accessing your account, reply to this email and we will help."
    )
    delivered = await _send_categorized_email(
        email=email,
        subject="Reset your LoreVia password",
        category=EMAIL_CATEGORY_TRANSACTIONAL,
        html=_render_email(
            preheader="Use this secure link to reset your LoreVia password. The link expires in 1 hour.",
            eyebrow="Password reset",
            heading="Reset your password",
            body_html=body_html,
            cta_label="Choose a new password",
            cta_url=reset_url,
            closing_html=closing_html,
        ),
    )
    return delivered, reset_url
