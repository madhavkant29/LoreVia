import uuid

import pytest

from app.models.book import Book


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": email.split("@")[0][:24], "password": "StrongPass123!@#", "accepted_terms": True},
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    me = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={token}"})
    assert me.status_code == 200
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me.json()["id"])


@pytest.mark.asyncio
async def test_writer_workspace_goal_calendar_round_trip(client, db):
    headers, user_id = await _register_user(client, f"workspace-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="pdf", s3_key="planner.pdf", status="ready", mode="author")
    db.add(book)
    await db.commit()

    initial = await client.get(f"/api/v1/books/{book.id}/writer-workspace", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["goal_calendar"] == []

    payload = {
        "goal_calendar": [
            {
                "title": "Draft chapter 7",
                "due_date": "2026-05-12",
                "quota_value": 2500,
                "quota_unit": "words",
                "completed": False,
            }
        ]
    }

    updated = await client.put(f"/api/v1/books/{book.id}/writer-workspace", headers=headers, json=payload)
    assert updated.status_code == 200
    body = updated.json()
    assert len(body["goal_calendar"]) == 1
    assert body["goal_calendar"][0]["title"] == "Draft chapter 7"
    assert body["goal_calendar"][0]["due_date"] == "2026-05-12"
    assert body["goal_calendar"][0]["quota_value"] == 2500
    assert body["goal_calendar"][0]["quota_unit"] == "words"
    assert body["goal_calendar"][0]["completed"] is False


@pytest.mark.asyncio
async def test_scene_path_round_trip_accepts_nested_folders(client, db):
    headers, user_id = await _register_user(client, f"scene-path-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="pdf", s3_key="planner.pdf", status="ready", mode="author")
    db.add(book)
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/scenes",
        headers=headers,
        json={
            "title": "Rooftop Meeting",
            "description": "They finally compare notes.",
            "body": "The city hissed under the rain.",
            "chapter_number": 3,
            "path": "scenes/Act I/Rooftop Meetings/rooftop-meeting.md",
            "sort_order": 1,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["path"] == "scenes/Act I/Rooftop Meetings/rooftop-meeting.md"

    update_response = await client.put(
        f"/api/v1/books/{book.id}/scenes/{created['id']}",
        headers=headers,
        json={
            "title": "Rooftop Meeting",
            "description": "They finally compare notes.",
            "body": "The city hissed under the rain.",
            "chapter_number": 3,
            "path": "scenes/Act I/Encounters/Rooftop Meeting.md",
            "sort_order": 1,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["path"] == "scenes/Act I/Encounters/Rooftop Meeting.md"
