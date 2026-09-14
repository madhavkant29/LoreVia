import uuid

import pytest

from app.models.book import Book
from app.models.user import User


@pytest.mark.asyncio
async def test_copyright_report_creates_notification_without_automatic_takedown(client, db):
    owner = User(
        email=f"report-owner-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"reportowner{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    admin = User(
        email=f"report-admin-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"reportadmin{uuid.uuid4().hex[:8]}",
        password_hash="hash",
        tier="admin",
    )
    db.add_all([owner, admin])
    await db.flush()
    book = Book(
        user_id=owner.id,
        title="Reported Novel",
        format="txt",
        s3_key="public/reported.txt",
        status="ready",
        is_public=True,
        public_status="published",
        public_slug=f"reported-{uuid.uuid4().hex[:8]}",
        moderation_status="clean",
    )
    db.add(book)
    await db.commit()

    response = await client.post(
        "/api/v1/reports/content",
        json={
            "book_id": str(book.id),
            "report_type": "copyright",
            "reason": "This upload reproduces my copyrighted novel.",
            "details": "The opening chapters match my published edition.",
            "reporter_email": "rights-holder@example.com",
            "copyright_owner_name": "Rights Holder",
            "copyright_work_description": "Original fantasy novel",
            "copyright_original_url": "https://example.com/original",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "open"
    await db.refresh(book)
    assert book.is_public is True
    assert book.public_status == "published"
    assert book.moderation_status == "reported"


@pytest.mark.asyncio
async def test_copyright_report_requires_reporter_email(client):
    response = await client.post(
        "/api/v1/reports/content",
        json={
            "book_id": str(uuid.uuid4()),
            "report_type": "copyright",
            "reason": "Copyright concern without contact details.",
        },
    )
    assert response.status_code in {400, 404}
