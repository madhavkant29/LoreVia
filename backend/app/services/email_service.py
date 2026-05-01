from typing import Any, cast

import resend

from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY


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


async def send_processing_complete(email: str, book_title: str) -> None:
    _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": f"Your book is ready - {book_title}",
        "html": f"""
        <h2>LoreVia - Processing Complete</h2>
        <p><strong>{book_title}</strong> has been processed.</p>
        <p>Characters, relationships, and chapter summaries are ready.</p>
        <p><a href="{settings.APP_URL.rstrip('/')}/library">Open your library</a></p>
        """,
    })


async def send_processing_complete_with_stats(
    email: str,
    *,
    book_title: str,
    character_count: int,
    relationship_count: int,
    plot_thread_count: int,
    continuity_issue_count: int,
) -> None:
    _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": f"Your book is ready - {book_title}",
        "html": f"""
        <h2>LoreVia - Processing Complete</h2>
        <p><strong>{book_title}</strong> has been processed.</p>
        <p>
          We found <strong>{character_count} characters</strong>,
          mapped <strong>{relationship_count} relationships</strong>,
          identified <strong>{plot_thread_count} plot threads</strong>,
          and flagged <strong>{continuity_issue_count} continuity issues</strong>.
        </p>
        <p><a href="{settings.APP_URL.rstrip('/')}/library">Open your library</a></p>
        """,
    })


async def send_subscription_confirmation(email: str, plan: str) -> None:
    _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": f"Welcome to LoreVia {plan.title()}",
        "html": f"""
        <h2>You're now on LoreVia {plan.title()}</h2>
        <p>Enjoy unlimited books, relationship graphs, semantic search, and more.</p>
        <p><a href="{settings.APP_URL.rstrip('/')}/library">Start reading</a></p>
        """,
    })


async def send_onboarding_email(email: str) -> None:
    _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": "Welcome to LoreVia",
        "html": f"""
        <h2>Welcome to LoreVia</h2>
        <p>Your reading workspace is ready. Upload a book, track characters, and keep your place across long fiction and series.</p>
        <p>Need help, found a bug, or want to send feedback? Reach us at <a href="mailto:{settings.SUPPORT_EMAIL}">{settings.SUPPORT_EMAIL}</a>.</p>
        <p><a href="{settings.APP_URL.rstrip('/')}/library">Open your library</a></p>
        """,
    })


async def send_password_reset_email(email: str, token: str) -> None:
    reset_url = f"{settings.APP_URL.rstrip('/')}/reset-password/{token}"
    _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": "Reset your LoreVia password",
        "html": f"""
        <h2>Reset your LoreVia password</h2>
        <p>Use the link below to choose a new password. This link expires in 1 hour.</p>
        <p><a href="{reset_url}">Reset password</a></p>
        <p>If you did not request this, you can ignore this email.</p>
        """,
    })


async def send_new_characters_detected_email(
    email: str,
    book_title: str,
    chapter_number: int,
    character_names: list[str],
) -> None:
    if not character_names:
        return

    preview = ", ".join(character_names[:6])
    extra_count = max(0, len(character_names) - 6)
    suffix = f", and {extra_count} more" if extra_count else ""
    plural = "character" if len(character_names) == 1 else "characters"

    _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": f"{len(character_names)} new {plural} detected in your latest upload",
        "html": f"""
        <h2>New character alert for {book_title}</h2>
        <p>
          LoreVia detected <strong>{len(character_names)} new {plural}</strong>
          in Chapter {chapter_number}.
        </p>
        <p>{preview}{suffix}</p>
        <p><a href="{settings.APP_URL.rstrip('/')}/library">Open LoreVia to review their extracted profiles</a></p>
        """,
    })


async def deliver_password_reset_email(email: str, token: str) -> tuple[bool, str]:
    reset_url = f"{settings.APP_URL.rstrip('/')}/reset-password/{token}"
    delivered = _send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": "Reset your LoreVia password",
        "html": f"""
        <h2>Reset your LoreVia password</h2>
        <p>Use the link below to choose a new password. This link expires in 1 hour.</p>
        <p><a href="{reset_url}">Reset password</a></p>
        <p>If you did not request this, you can ignore this email.</p>
        """,
    })
    return delivered, reset_url
