"""Integration tests for upload work type handling."""

import uuid

import pytest


async def _register_user(client, email: str) -> tuple[dict[str, str], str]:
    from app.core.security import create_access_token

    username = email.split("@")[0][:32]
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "TestPass123!@#", "accepted_terms": True},
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    return {"Cookie": f"lorevia_access_token={token}"}, str(response.json()["id"])


@pytest.mark.asyncio
async def test_upload_endpoint_accepts_explicit_screenplay_work_type_for_text_script(client, db):
    headers, _ = await _register_user(client, f"screenplay-explicit-{uuid.uuid4().hex[:8]}@lorevia.app")

    response = await client.post(
        "/api/v1/books/upload",
        headers=headers,
        files={"file": ("pilot.txt", b"INT. ROOM - DAY\n\nMAYA\nHello there.\n", "text/plain")},
        data={"title": "Pilot", "work_type": "screenplay", "mode": "author"},
    )

    assert response.status_code == 202
    book_id = response.json()["book_id"]

    detail = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["work_type"] == "screenplay"
    assert payload["format"] == "txt"


@pytest.mark.asyncio
async def test_upload_endpoint_infers_screenplay_from_fountain_extension(client, db):
    headers, _ = await _register_user(client, f"screenplay-inferred-{uuid.uuid4().hex[:8]}@lorevia.app")

    response = await client.post(
        "/api/v1/books/upload",
        headers=headers,
        files={"file": ("pilot.fountain", b"INT. ROOM - DAY\n\nMAYA\nHello there.\n", "text/plain")},
        data={"title": "Pilot"},
    )

    assert response.status_code == 202
    book_id = response.json()["book_id"]

    detail = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["work_type"] == "screenplay"
    assert payload["format"] == "fountain"
