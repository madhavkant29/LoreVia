import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.user import User
from app.services.event_linking_service import _normalize_major_event, link_summary_events


@pytest.mark.asyncio
async def test_link_summary_events_matches_characters_and_deduplicates(db):
    user = User(email="event-linking@lorevia.app", username="eventlinking", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Event Linking",
        format="pdf",
        s3_key="event-linking.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        id=uuid.uuid4(), book_id=book.id, number=5, title="Turn", s3_key="chapter-5.txt"
    )
    hero = Character(
        book_id=book.id, name="Asha", aliases=["Ash"], first_chapter=1, growth_events=[]
    )
    rival = Character(book_id=book.id, name="Bren", first_chapter=1, growth_events=[])
    db.add_all([chapter, hero, rival])
    await db.commit()

    payload = await link_summary_events(
        db,
        chapter=chapter,
        key_events=[
            {
                "event_title": "The betrayal",
                "description": "Asha uncovers Bren's deception.",
                "importance": 9,
                "involved_characters": ["Asha", "Bren"],
            }
        ],
        char_changes=[
            {
                "character": "Ash",
                "change": "Learns to trust her instincts",
                "impact_score": 7,
                "growth_direction": "positive",
                "is_major": True,
            }
        ],
    )

    assert payload["major_events"][0]["involved_characters"] == [str(hero.id), str(rival.id)]
    assert len(hero.growth_events or []) == 2
    assert any(event["event_title"] == "The betrayal" for event in hero.growth_events or [])

    await link_summary_events(
        db,
        chapter=chapter,
        key_events=[
            {
                "event_title": "The betrayal",
                "description": "Asha uncovers Bren's deception.",
                "importance": 9,
                "involved_characters": ["Asha", "Bren"],
            }
        ],
        char_changes=[],
    )
    betrayal_events = [
        event for event in (hero.growth_events or []) if event.get("event_title") == "The betrayal"
    ]
    assert len(betrayal_events) == 1


@pytest.mark.asyncio
async def test_link_summary_events_uses_resolver_context_for_family_role_reference(db):
    user = User(
        email="event-linking-family@lorevia.app",
        username="eventlinkingfamily",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Family Linking",
        format="pdf",
        s3_key="family-linking.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        id=uuid.uuid4(), book_id=book.id, number=3, title="Kitchen", s3_key="chapter-3.txt"
    )
    grete = Character(book_id=book.id, name="Grete", aliases=[], first_chapter=1, growth_events=[])
    gregor = Character(
        book_id=book.id, name="Gregor", aliases=[], first_chapter=1, growth_events=[]
    )
    db.add_all([chapter, grete, gregor])
    await db.commit()

    payload = await link_summary_events(
        db,
        chapter=chapter,
        key_events=[
            {
                "event_title": "A plea at the door",
                "description": "Grete, Gregor's sister, begs him to answer.",
                "importance": 7,
                "involved_characters": ["Gregor's sister", "Gregor"],
            }
        ],
        char_changes=[],
    )

    assert payload["major_events"][0]["involved_characters"] == [str(grete.id), str(gregor.id)]


def test_normalize_major_event_defaults_malformed_importance_but_propagates_unexpected_errors():
    assert (
        _normalize_major_event(
            {"event_title": "Odd score", "importance": object()},
            chapter_number=1,
            character_ids=[],
            character_names=[],
        )["importance"]
        == 5
    )

    class ExplodingImportance:
        def __int__(self):
            raise RuntimeError("unexpected conversion failure")

    with pytest.raises(RuntimeError, match="unexpected conversion failure"):
        _normalize_major_event(
            {"event_title": "Broken score", "importance": ExplodingImportance()},
            chapter_number=1,
            character_ids=[],
            character_names=[],
        )
