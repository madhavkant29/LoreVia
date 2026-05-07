from io import BytesIO
import uuid

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.models.book import Book
from app.models.character import Character, CharacterState
from app.models.intelligence import CharacterRelationship


def _register_user_payload(image_size: tuple[int, int] = (120, 180)) -> bytes:
    image = Image.new("RGB", image_size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 18, image_size[0] - 12, image_size[1] - 18), fill=(55, 84, 136))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token
    username = email.split("@")[0][:32]
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "TestPass123!@#", "accepted_terms": True},
    )
    assert response.status_code == 201
    token = create_access_token(str(response.json()["id"]))
    assert token
    me_response = await client.get("/api/v1/auth/me", headers={"Cookie": f"lorevia_access_token={token}"})
    assert me_response.status_code == 200
    return {"Cookie": f"lorevia_access_token={token}"}, uuid.UUID(me_response.json()["id"])


@pytest.mark.asyncio
async def test_manual_cover_upload_returns_original_cover_without_processing_metadata(client, db):
    headers, _ = await _register_user(client, "cover-owner@lorevia.app")

    response = await client.post(
        "/api/v1/books/upload",
        headers=headers,
        files={
            "file": ("manual-cover.pdf", b"%PDF-1.4 test payload", "application/pdf"),
            "cover_file": ("manual-cover.png", _register_user_payload(), "image/png"),
        },
        data={
            "title": "Covered Book",
            "auto_extract_cover": "false",
        },
    )

    assert response.status_code == 202
    book_id = response.json()["book_id"]

    book_response = await client.get(f"/api/v1/books/{book_id}", headers=headers)
    assert book_response.status_code == 200
    payload = book_response.json()

    assert payload["cover_url"]
    assert payload["cover_url"].startswith("/api/v1/books/")
    assert "cover_processed_url" not in payload
    assert "cover_processed_at" not in payload
    assert "cover_edge_colors" not in payload
    assert "cover_crop_bounds" not in payload


@pytest.mark.asyncio
async def test_merge_characters_endpoint_merges_duplicate_records(client, db):
    headers, user_id = await _register_user(client, "merge-owner@lorevia.app")

    book = Book(
        user_id=user_id,
        title="Merge Test",
        format="pdf",
        s3_key="books/merge-test.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    primary = Character(
        book_id=book.id,
        name="Meme Oshino",
        aliases=["Meme"],
        role="mentor",
        first_chapter=1,
        mention_count=4,
    )
    secondary = Character(
        book_id=book.id,
        name="Mister Oshino",
        aliases=["Mr. Oshino"],
        role="mentor",
        first_chapter=3,
        mention_count=2,
    )
    db.add_all([primary, secondary])
    await db.flush()

    db.add(CharacterState(character_id=secondary.id, at_chapter=3, trait_snapshot={"eyes": {"value": "gray", "confidence": 0.9}}))
    db.add(
        CharacterRelationship(
            book_id=book.id,
            character_a_id=secondary.id,
            character_b_id=primary.id,
            rel_type="mentor",
            from_chapter=3,
        )
    )
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/characters/merge",
        headers=headers,
        json={"primary_id": str(primary.id), "secondary_id": str(secondary.id)},
    )

    assert response.status_code == 200
    assert response.json()["merged"] == str(primary.id)

    merged = await db.get(Character, primary.id)
    deleted = await db.get(Character, secondary.id)
    states = (await db.execute(select(CharacterState).where(CharacterState.character_id == primary.id))).scalars().all()
    relationships = (await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book.id))).scalars().all()

    assert merged is not None
    assert deleted is None
    assert "Mister Oshino" in (merged.aliases or [])
    assert merged.mention_count == 6
    assert len(states) == 1
    assert relationships == []


@pytest.mark.asyncio
async def test_delete_character_endpoint_removes_false_positive(client, db):
    headers, user_id = await _register_user(client, "delete-owner@lorevia.app")

    book = Book(
        user_id=user_id,
        title="Delete Test",
        format="pdf",
        s3_key="books/delete-test.pdf",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()

    false_positive = Character(
        book_id=book.id,
        name="Stairs",
        aliases=[],
        role="background",
        first_chapter=1,
        mention_count=1,
    )
    db.add(false_positive)
    await db.commit()

    response = await client.delete(
        f"/api/v1/books/{book.id}/characters/{false_positive.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["deleted"] == str(false_positive.id)
    assert await db.get(Character, false_positive.id) is None
