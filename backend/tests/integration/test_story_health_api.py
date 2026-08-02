import uuid

import pytest

from app.models.book import Book, Chapter
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.intelligence import PlotThread, WikiEntry, WorldBuildingDocument, WorldGapAnalysis


@pytest.mark.asyncio
async def test_story_health_endpoint_returns_dynamic_book_metrics(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    book = Book(
        user_id=user_id,
        title="Signal Fire",
        format="manual",
        work_type="novel",
        s3_key="books/signal-fire.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()

    db.add_all(
        [
            Chapter(
                book_id=book.id,
                number=1,
                title="Arrival",
                s3_key="chapters/1.txt",
                word_count=1800,
                processed=True,
            ),
            Chapter(
                book_id=book.id,
                number=2,
                title="Crossroads",
                s3_key="chapters/2.txt",
                word_count=2100,
                processed=True,
            ),
            Chapter(
                book_id=book.id,
                number=3,
                title="Ashfall",
                s3_key="chapters/3.txt",
                word_count=1700,
                processed=True,
            ),
        ]
    )
    protagonist = Character(
        book_id=book.id,
        name="Mira",
        role="mc",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=24,
        trait_state={"eyes": {"value": "green", "confidence": 0.9, "type": "objective"}},
        personality_tags=["resolute"],
        motivations=["Protect the city"],
        arc_summary="Learns to trust the council again.",
    )
    db.add(protagonist)
    await db.flush()
    db.add(
        CharacterState(
            character_id=protagonist.id,
            at_chapter=2,
            trait_snapshot={"eyes": {"value": "green", "confidence": 0.9}},
            arc_note="Still hiding what she knows.",
        )
    )
    db.add(
        CharacterVoiceProfile(
            book_id=book.id,
            character_id=protagonist.id,
            sample_dialogue_count=6,
            sample_word_count=84,
            dominant_markers={"questions": 2},
            signature_phrases=["Keep the signal burning"],
        )
    )
    db.add(
        PlotThread(
            book_id=book.id,
            title="The missing beacon",
            status="ongoing",
            introduced_at=1,
            importance=8,
            character_ids=["Mira"],
        )
    )
    db.add(
        WikiEntry(
            book_id=book.id,
            entry_type="location",
            name="North Gate",
            description="The city entrance.",
            first_mention=1,
        )
    )
    db.add(
        WorldBuildingDocument(
            book_id=book.id,
            title="City charter",
            s3_key="world/charter.txt",
            word_count=900,
            is_active=True,
        )
    )
    db.add(
        WorldGapAnalysis(
            book_id=book.id,
            analysis_mode="gap_scan",
            priority_gaps=[],
            consistency_flags=[],
        )
    )
    await db.commit()

    response = await client.get(f"/api/v1/books/{book.id}/story-health", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert 0 <= payload["score"] <= 100
    assert payload["status"]
    assert payload["summary"]
    assert len(payload["metrics"]) == 7
    labels = [item["label"] for item in payload["metrics"]]
    assert labels == [
        "Continuity",
        "Character consistency",
        "Timeline clarity",
        "Plot thread closure",
        "Worldbuilding consistency",
        "Pacing",
        "Dialogue/voice consistency",
    ]
    assert all(0 <= item["score"] <= 100 for item in payload["metrics"])
    assert payload["score"] < 100
    assert all(item["score"] < 100 for item in payload["metrics"])
    world_metric = next(
        item for item in payload["metrics"] if item["label"] == "Worldbuilding consistency"
    )
    assert "0 cached world-analysis issues" not in world_metric["detail"]
