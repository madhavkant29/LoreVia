import uuid

import pytest

from app.models.book import Book, Chapter, NovelScene
from app.models.character import Character, CharacterVoiceProfile
from app.models.intelligence import ChapterSummary, PlotThread, WikiEntry
from app.utils.book_utils import serialize_manuscript_content


@pytest.mark.asyncio
async def test_revision_intelligence_endpoint_surfaces_revision_sections_and_persists_status(client, db, auth_headers, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    book = Book(
        user_id=user_id,
        title="Sky of Ash",
        genre="Epic Fantasy",
        format="manual",
        work_type="novel",
        s3_key="books/sky-of-ash.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()

    chapters = [
        Chapter(book_id=book.id, number=1, title="Ashfall", s3_key="chapters/1.txt", word_count=1700, processed=True),
        Chapter(book_id=book.id, number=2, title="The Ember Gate", s3_key="chapters/2.txt", word_count=1800, processed=True),
        Chapter(book_id=book.id, number=3, title="Council of Bells", s3_key="chapters/3.txt", word_count=1650, processed=True),
    ]
    db.add_all(chapters)
    await db.flush()

    nora = Character(
        book_id=book.id,
        name="Nora",
        role="mc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=24,
        personality_tags=["guarded", "direct"],
    )
    kael = Character(
        book_id=book.id,
        name="Kael",
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=12,
    )
    mira = Character(
        book_id=book.id,
        name="Mira",
        role="sc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=8,
    )
    db.add_all([nora, kael, mira])
    await db.flush()

    db.add(
        CharacterVoiceProfile(
            book_id=book.id,
            character_id=nora.id,
            sample_dialogue_count=10,
            sample_word_count=60,
            avg_sentence_length=4,
            contraction_rate_x1000=220,
            question_rate_x1000=40,
            exclamation_rate_x1000=0,
            ellipsis_rate_x1000=0,
            dash_rate_x1000=0,
            formality_score_x1000=20,
            lexical_complexity_x1000=500,
            emotional_intensity_x1000=90,
        )
    )
    db.add(
        PlotThread(
            book_id=book.id,
            title="Silver gate blood rule",
            description="Nora and Kael learn that the gate opens only for royal blood.",
            status="developing",
            introduced_at=1,
            last_mentioned_at=3,
            importance=9,
            character_ids=["Nora", "Kael"],
        )
    )
    db.add(
        WikiEntry(
            book_id=book.id,
            entry_type="faction",
            name="Ash Court",
            description="The ruling faction behind the bells.",
            first_mention=1,
        )
    )
    db.add(
        ChapterSummary(
            chapter_id=chapters[0].id,
            mode="detailed",
            content="Nora enters the city and hears the bells.",
            key_events=[{"event_title": "Gate entry", "description": "Nora reaches the city gate."}],
            clues=["The silver gate reacts to blood."],
        )
    )
    db.add_all(
        [
            NovelScene(
                book_id=book.id,
                chapter_id=chapters[1].id,
                chapter_number=2,
                title="Gate Approach",
                description="Nora and Kael debate the gate rules.",
                body="Nora and Kael reach the silver gate and argue about royal blood.",
                path="scenes/chapter-02/gate-approach.md",
                status="assigned",
                sort_order=1,
            ),
            NovelScene(
                book_id=book.id,
                chapter_id=chapters[2].id,
                chapter_number=3,
                title="Gate Delay",
                description="They revisit the same gate argument.",
                body="Kael repeats the gate warning while Nora stalls at the silver gate.",
                path="scenes/chapter-03/gate-delay.md",
                status="assigned",
                sort_order=1,
            ),
            NovelScene(
                book_id=book.id,
                chapter_id=chapters[2].id,
                chapter_number=3,
                title="Bell Corridor",
                description="A short walk through the corridor.",
                body="The corridor is quiet.",
                path="scenes/chapter-03/bell-corridor.md",
                status="assigned",
                sort_order=2,
            ),
        ]
    )
    await db.commit()

    chapter_payloads = {
        "chapters/1.txt": serialize_manuscript_content(
            "Nora met Kael and Mira in the Ash Court beside the silver gate. The Ember Archive, Bell Guard, North Watch, and River Council were all named before the bells stopped.",
            None,
        ),
        "chapters/2.txt": serialize_manuscript_content(
            '"I can\'t open it," Nora said. "We need blood." Kael whispered, "Then we wait."',
            None,
        ),
        "chapters/3.txt": serialize_manuscript_content(
            '"Indeed, the royal mechanism necessitates a ceremonial lineage," Nora said. "This is totally impossible otherwise."',
            None,
        ),
    }

    monkeypatch.setattr("app.utils.book_utils.download_book", lambda key: chapter_payloads[key])

    response = await client.get(f"/api/v1/books/{book.id}/revision-intelligence", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["tagline"] == "Know what your edit breaks before your readers do."
    assert payload["summary"]["active_item_count"] >= 1
    assert payload["genre_checks"][0]["label"] == "Fantasy"
    assert payload["revision_plan"][0]["title"] == "Pass 1: Fix story logic"
    assert payload["knowledge_matrix"][0]["fact"] == "Silver gate blood rule"
    assert payload["scene_advice"]
    assert payload["confusion_map"]
    assert payload["voice_alerts"]

    first_item_id = payload["change_impacts"][0]["id"]
    workspace_update = await client.put(
        f"/api/v1/books/{book.id}/writer-workspace",
        headers=auth_headers,
        json={
            "revision_board": {
                "items": [
                    {
                        "item_id": first_item_id,
                        "status": "fixed",
                    }
                ]
            }
        },
    )
    assert workspace_update.status_code == 200

    refreshed = await client.get(f"/api/v1/books/{book.id}/revision-intelligence", headers=auth_headers)
    assert refreshed.status_code == 200
    updated_item = next(item for item in refreshed.json()["change_impacts"] if item["id"] == first_item_id)
    assert updated_item["status"] == "fixed"
