from __future__ import annotations

import uuid

import pytest

from app.models.book import Book, BookNote, Chapter, NovelScene
from app.models.character import Character
from app.models.intelligence import PlotThread, WorldNote


@pytest.mark.asyncio
async def test_revision_tags_round_trip_across_revision_entities(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    book = Book(
        user_id=user_id,
        title="Revision Stack",
        genre="Fantasy",
        format="manual",
        work_type="novel",
        s3_key="books/revision-stack.txt",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="The First Pass",
        s3_key="chapters/revision-stack-1.txt",
        processed=True,
    )
    character = Character(
        book_id=book.id,
        name="Vera",
        role="mc",
        first_chapter=1,
        mention_count=3,
    )
    note = BookNote(
        user_id=user_id,
        book_id=book.id,
        chapter_number=1,
        title="Manuscript comment",
        body="Tighten the opening exchange.",
    )
    scene = NovelScene(
        book_id=book.id,
        title="Opening Clash",
        body="Vera meets the rival at the city gate.",
        chapter_number=1,
        path="scenes/chapter-01/opening-clash.md",
        status="assigned",
        sort_order=1,
        source="manual",
    )
    thread = PlotThread(
        book_id=book.id,
        title="Gate debt",
        status="developing",
        introduced_at=1,
        last_mentioned_at=1,
        importance=8,
        character_ids=["Vera"],
    )
    world_note = WorldNote(
        user_id=user_id,
        book_id=book.id,
        note_type="general_world",
        chapter_number=1,
        title="City walls",
        body="The eastern wall height needs a canon pass.",
        priority="medium",
        status="open",
    )
    db.add_all([chapter, character, note, scene, thread, world_note])
    await db.commit()

    chapter_tag = await client.put(
        f"/api/v1/books/{book.id}/revision-tags",
        headers=auth_headers,
        json={
            "entity_type": "chapter",
            "chapter_number": 1,
            "tags": ["Needs Rewrite", " final pass "],
        },
    )
    assert chapter_tag.status_code == 200
    assert sorted(chapter_tag.json()["tags"]) == ["final pass", "needs rewrite"]

    comment_tag = await client.put(
        f"/api/v1/books/{book.id}/revision-tags",
        headers=auth_headers,
        json={
            "entity_type": "comment",
            "entity_id": str(note.id),
            "tags": ["beta feedback", "Too Slow"],
        },
    )
    assert comment_tag.status_code == 200
    assert comment_tag.json()["tags"] == ["beta feedback", "too slow"]

    character_tag = await client.put(
        f"/api/v1/books/{book.id}/revision-tags",
        headers=auth_headers,
        json={"entity_type": "character", "entity_id": str(character.id), "tags": ["villain pov"]},
    )
    assert character_tag.status_code == 200

    scene_tag = await client.put(
        f"/api/v1/books/{book.id}/revision-tags",
        headers=auth_headers,
        json={
            "entity_type": "scene",
            "entity_id": str(scene.id),
            "tags": ["battle scene", "foreshadowing"],
        },
    )
    assert scene_tag.status_code == 200

    thread_tag = await client.put(
        f"/api/v1/books/{book.id}/revision-tags",
        headers=auth_headers,
        json={"entity_type": "plot_thread", "entity_id": str(thread.id), "tags": ["romance arc"]},
    )
    assert thread_tag.status_code == 200

    world_note_tag = await client.put(
        f"/api/v1/books/{book.id}/revision-tags",
        headers=auth_headers,
        json={
            "entity_type": "world_note",
            "entity_id": str(world_note.id),
            "tags": ["check continuity"],
        },
    )
    assert world_note_tag.status_code == 200

    chapter_list = await client.get(f"/api/v1/reader/{book.id}/chapters", headers=auth_headers)
    assert chapter_list.status_code == 200
    assert sorted(chapter_list.json()["chapters"][0]["tags"]) == ["final pass", "needs rewrite"]

    notes_response = await client.get(f"/api/v1/books/{book.id}/notes", headers=auth_headers)
    assert notes_response.status_code == 200
    assert notes_response.json()[0]["tags"] == ["beta feedback", "too slow"]

    characters_response = await client.get(
        f"/api/v1/books/{book.id}/characters", headers=auth_headers
    )
    assert characters_response.status_code == 200
    assert characters_response.json()[0]["tags"] == ["villain pov"]

    scenes_response = await client.get(f"/api/v1/books/{book.id}/scenes", headers=auth_headers)
    assert scenes_response.status_code == 200
    assert scenes_response.json()[0]["tags"] == ["battle scene", "foreshadowing"]

    threads_response = await client.get(
        f"/api/v1/reader/{book.id}/plot-threads", headers=auth_headers
    )
    assert threads_response.status_code == 200
    assert threads_response.json()[0]["tags"] == ["romance arc"]

    world_notes_response = await client.get(
        f"/api/v1/intelligence/{book.id}/world-building/notes", headers=auth_headers
    )
    assert world_notes_response.status_code == 200
    assert world_notes_response.json()[0]["tags"] == ["check continuity"]
