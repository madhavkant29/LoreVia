"""Integration tests for the Series Bible endpoint."""

import uuid

import pytest

from app.core.security import create_access_token
from app.models.book import Book, Dialogue, Scene, Series, SeriesBook
from app.models.character import Character
from app.models.intelligence import CharacterRelationship, PlotThread, WikiEntry
from app.models.user import User


def _auth_headers(user_id) -> dict[str, str]:
    token = create_access_token(str(user_id))
    assert token
    return {"Cookie": f"lorevia_access_token={token}"}


async def _build_series_bible_fixture(db):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"series-bible-{suffix}@lorevia.app",
        username=f"series-bible-{suffix}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()

    series = Series(
        user_id=user.id,
        name="Neon Nights",
        description="A citywide conspiracy series.",
    )
    db.add(series)
    await db.flush()

    pilot = Book(
        user_id=user.id,
        title="Pilot",
        format="fountain",
        work_type="screenplay",
        s3_key="books/pilot.fountain",
        status="ready",
    )
    finale = Book(
        user_id=user.id,
        title="Finale",
        format="pdf",
        work_type="screenplay",
        s3_key="books/finale.pdf",
        status="ready",
    )
    db.add_all([pilot, finale])
    await db.flush()

    db.add_all(
        [
            SeriesBook(series_id=series.id, book_id=pilot.id, position=1),
            SeriesBook(series_id=series.id, book_id=finale.id, position=2),
        ]
    )

    scene_one = Scene(
        book_id=pilot.id,
        number=1,
        heading="INT. CLUB - NIGHT",
        location="CLUB",
        time_of_day="NIGHT",
        word_count=120,
    )
    scene_two = Scene(
        book_id=finale.id,
        number=1,
        heading="EXT. ROOFTOP - NIGHT",
        location="ROOFTOP",
        time_of_day="NIGHT",
        word_count=150,
    )
    db.add_all([scene_one, scene_two])
    await db.flush()

    db.add_all(
        [
            Dialogue(
                scene_id=scene_one.id,
                character_name="MAYA",
                dialogue_text="We are out of time.",
                line_number=0,
                word_count=5,
            ),
            Dialogue(
                scene_id=scene_two.id,
                character_name="MAYA",
                dialogue_text="Then we finish it.",
                line_number=0,
                word_count=4,
            ),
        ]
    )

    maya_pilot = Character(
        book_id=pilot.id, name="MAYA", role="mc", first_chapter=1, mention_count=8
    )
    jon_pilot = Character(book_id=pilot.id, name="JON", role="sc", first_chapter=1, mention_count=4)
    maya_finale = Character(
        book_id=finale.id, name="Maya", role="mc", first_chapter=1, mention_count=9
    )
    jon_finale = Character(
        book_id=finale.id, name="Jon", role="sc", first_chapter=1, mention_count=5
    )
    db.add_all([maya_pilot, jon_pilot, maya_finale, jon_finale])
    await db.flush()

    db.add_all(
        [
            CharacterRelationship(
                book_id=pilot.id,
                character_a_id=maya_pilot.id,
                character_b_id=jon_pilot.id,
                rel_type="ally",
                description="They cover each other in the field.",
                from_chapter=1,
            ),
            CharacterRelationship(
                book_id=finale.id,
                character_a_id=maya_finale.id,
                character_b_id=jon_finale.id,
                rel_type="ally",
                description="They trust each other completely now.",
                from_chapter=1,
            ),
            PlotThread(
                book_id=pilot.id,
                title="The Blackout Conspiracy",
                status="ongoing",
                importance=9,
                introduced_at=1,
                note="The citywide grid attack begins.",
            ),
            PlotThread(
                book_id=finale.id,
                title="The Blackout Conspiracy",
                status="ongoing",
                importance=10,
                introduced_at=1,
                note="The conspiracy reaches its endgame.",
            ),
            WikiEntry(
                book_id=pilot.id,
                entry_type="location",
                name="The Grid",
                description="The aging electrical backbone under the city.",
                first_mention=1,
            ),
            WikiEntry(
                book_id=finale.id,
                entry_type="location",
                name="The Grid",
                description="A rebuilt electrical network underneath the city.",
                first_mention=1,
            ),
        ]
    )
    await db.commit()
    return user, series


@pytest.mark.asyncio
async def test_series_bible_endpoint_aggregates_recurring_screenplay_entities(client, db):
    user, series = await _build_series_bible_fixture(db)
    response = await client.get(
        f"/api/v1/books/series/{series.id}/bible",
        headers=_auth_headers(user.id),
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["series_id"] == str(series.id)
    assert payload["work_type"] == "screenplay"
    assert payload["episode_count"] == 2
    assert payload["episodes"][0]["episode_number"] == 1
    assert payload["episodes"][0]["total_scenes"] == 1
    assert payload["episodes"][0]["total_dialogue_lines"] == 1
    assert payload["recurring_characters"][0]["name"].lower() == "maya"
    assert payload["recurring_characters"][0]["episode_count"] == 2
    assert payload["recurring_relationships"][0]["relationship_type"] == "ally"
    assert payload["unresolved_plot_threads"][0]["title"] == "The Blackout Conspiracy"
    assert any(
        "The Grid has differing location descriptions across episodes." == item
        for item in payload["continuity_risks"]
    )


@pytest.mark.asyncio
async def test_series_list_endpoint_is_not_shadowed_by_book_lookup(client, db):
    """GET /books/series must reach the series router, not GET /books/{book_id}.

    Regression: core_router's dynamic /{book_id} route was registered before
    series_router, so the literal /series path failed UUID validation with 422.
    """
    user, series = await _build_series_bible_fixture(db)

    response = await client.get("/api/v1/books/series", headers=_auth_headers(user.id))

    assert response.status_code == 200, response.text
    payload = response.json()
    names = [item["name"] for item in payload["items"]]
    assert "Neon Nights" in names

