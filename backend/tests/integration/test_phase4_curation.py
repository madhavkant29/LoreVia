import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token


async def _register_author(client, email: str, monkeypatch) -> tuple[dict[str, str], uuid.UUID]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0][:24],
            "password": "StrongPass123!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.require_author_access",
        lambda *_args, **_kwargs: None,
    )

    monkeypatch.setattr(
        "app.services.character_relationship_service.require_author_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.manuscript.require_author_access",
        lambda *_args, **_kwargs: None,
    )
    return headers, user_id


@pytest.mark.asyncio
async def test_relationship_create_sets_edited_by_author(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"rel-cur-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book
    from app.models.character import Character
    from app.models.intelligence import CharacterRelationship

    book = Book(
        user_id=user_id,
        title="Curation Test",
        format="manual",
        s3_key="curation.txt",
        status="ready",
        mode="author",
        is_editor_project=True,
    )
    db.add(book)
    await db.commit()

    char_a = Character(book_id=book.id, name="Alice", first_chapter=1)
    char_b = Character(book_id=book.id, name="Bob", first_chapter=1)
    db.add_all([char_a, char_b])
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/relationships",
        headers=headers,
        json={
            "character_a_id": str(char_a.id),
            "character_b_id": str(char_b.id),
            "rel_type": "ally",
            "from_chapter": 1,
        },
    )

    assert response.status_code == 201
    created = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book.id,
            CharacterRelationship.edited_by_author.is_(True),
        )
    )
    rows = created.scalars().all()
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_relationship_update_sets_edited_by_author(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"rel-upd-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book
    from app.models.character import Character
    from app.models.intelligence import CharacterRelationship

    book = Book(
        user_id=user_id,
        title="Update Curation",
        format="manual",
        s3_key="update-cur.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()

    char_a = Character(book_id=book.id, name="Carol", first_chapter=1)
    char_b = Character(book_id=book.id, name="Dave", first_chapter=1)
    db.add_all([char_a, char_b])
    await db.commit()

    rel = CharacterRelationship(
        book_id=book.id,
        character_a_id=char_a.id,
        character_b_id=char_b.id,
        rel_type="neutral",
        from_chapter=1,
        edited_by_author=False,
    )
    db.add(rel)
    await db.commit()

    response = await client.put(
        f"/api/v1/books/{book.id}/relationships/{rel.id}",
        headers=headers,
        json={"rel_type": "enemy", "from_chapter": 1},
    )

    assert response.status_code == 200
    updated = await db.get(CharacterRelationship, rel.id)
    assert updated.edited_by_author is True


@pytest.mark.asyncio
async def test_write_lock_blocks_scene_create_during_rebuild(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"lock-sc-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, Chapter, NovelScene

    book_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    book = Book(
        id=book_id,
        user_id=user_id,
        title="Locked Book",
        format="manual",
        s3_key="locked.txt",
        status="ready",
        mode="author",
        is_editor_project=True,
        writer_workspace={"processing": {"rebuild_run_id": "active-run"}},
    )
    db.add(book)
    chapter = Chapter(
        id=chapter_id,
        book_id=book_id,
        number=1,
        title="Ch 1",
        s3_key="ch1.txt",
        word_count=5,
    )
    db.add(chapter)
    db.add(
        NovelScene(
            book_id=book_id,
            chapter_id=chapter_id,
            chapter_number=1,
            title="Existing",
            body="Body",
            path="/scenes/1",
            sort_order=1,
        )
    )
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book_id}/scenes",
        headers=headers,
        json={
            "title": "Scene 1",
            "body": "Scene body text.",
            "chapter_number": 1,
        },
    )

    assert response.status_code == 409
    assert "reprocessing" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_scene_create_allowed_when_not_rebuilding(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"nolock-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Book, Chapter, NovelScene

    book_id = uuid.uuid4()
    chapter_id = uuid.uuid4()
    book = Book(
        id=book_id,
        user_id=user_id,
        title="Unlocked Book",
        format="manual",
        s3_key="unlocked.txt",
        status="ready",
        mode="author",
        is_editor_project=True,
    )
    db.add(book)
    chapter = Chapter(
        id=chapter_id,
        book_id=book_id,
        number=1,
        title="Ch 1",
        s3_key="chapters/unlocked/1.txt",
        word_count=5,
    )
    db.add(chapter)
    db.add(
        NovelScene(
            book_id=book_id,
            chapter_id=chapter_id,
            chapter_number=1,
            title="Existing",
            body="Body",
            path="/scenes/1",
            sort_order=1,
        )
    )
    await db.commit()

    source_key = chapter.s3_key
    monkeypatch.setattr(
        "app.utils.books.scene_sync.download_book",
        lambda key: {source_key: b"Existing chapter source."}[key],
    )
    response = await client.post(
        f"/api/v1/books/{book_id}/scenes",
        headers=headers,
        json={
            "title": "Allowed Scene",
            "body": "Body content here.",
            "chapter_number": 1,
        },
    )

    assert response.status_code == 200
