import pytest

from app.models.book import Book
from app.models.character import Character
from app.models.user import User
from scripts.audit_character_bible_noise import build_noise_report


@pytest.mark.asyncio
async def test_noise_audit_report_finds_obvious_bogus_character_rows(db):
    user = User(email="audit-user@lorevia.app", username="audit-user", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id,
        title="Audit Test",
        format="pdf",
        s3_key="books/audit-test.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    db.add_all(
        [
            Character(
                book_id=book.id,
                name="Well",
                first_chapter=1,
                mention_count=1,
            ),
            Character(
                book_id=book.id,
                name="Gregor",
                first_chapter=1,
                mention_count=4,
                personality_tags=["anxious"],
                motivations=["protect his family"],
                arc_summary="A grounded central character.",
            ),
        ]
    )
    await db.commit()

    report = await build_noise_report(book.id)

    assert report["total_characters"] == 2
    assert report["noise_count"] == 1
    assert str(book.id) in report["books"]
    assert report["books"][str(book.id)][0]["name"] == "Well"
    assert report["books"][str(book.id)][0]["reasons"]
