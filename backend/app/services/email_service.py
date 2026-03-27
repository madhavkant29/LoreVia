import resend
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY


async def send_processing_complete(email: str, book_title: str) -> None:
    resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": f"Your book is ready — {book_title}",
        "html": f"""
        <h2>LoreVia — Processing Complete</h2>
        <p><strong>{book_title}</strong> has been processed.</p>
        <p>Characters, relationships, and chapter summaries are ready.</p>
        <p><a href="https://lorevia.app/library">Open your library →</a></p>
        """,
    })


async def send_subscription_confirmation(email: str, plan: str) -> None:
    resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": email,
        "subject": f"Welcome to LoreVia {plan.title()}",
        "html": f"""
        <h2>You're now on LoreVia {plan.title()}</h2>
        <p>Enjoy unlimited books, relationship graphs, semantic search, and more.</p>
        <p><a href="https://lorevia.app/library">Start reading →</a></p>
        """,
    })
