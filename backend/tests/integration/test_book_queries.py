import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.character import Character, CharacterVoiceProfile
from app.models.intelligence import PlotThread, WorldElement


@pytest.mark.asyncio
async def test_book_detail_eager_loading(client, db):
    from app.core.security import create_access_token

    uid = str(uuid.uuid4())[:8]
    email = f"eager-{uid}@lorevia.app"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"eager{uid}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert r.status_code == 201
    user_id = uuid.UUID(r.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Eager Loading Test",
        format="txt",
        s3_key="eager.txt",
        status="ready",
        total_chapters=3,
    )
    db.add(book)
    await db.flush()

    for i in range(1, 4):
        db.add(
            Character(
                id=uuid.uuid4(),
                book_id=book.id,
                name=f"Character {i}",
                role="supporting",
                first_chapter=i,
                mention_count=10 - i,
            )
        )
    for i in range(1, 4):
        db.add(
            Chapter(
                id=uuid.uuid4(),
                book_id=book.id,
                number=i,
                title=f"Chapter {i}",
                s3_key=f"chapters/{book.id}/{i}.json",
                processed=True,
                word_count=1000,
            )
        )
    for i in range(1, 4):
        db.add(
            PlotThread(
                id=uuid.uuid4(),
                book_id=book.id,
                title=f"Thread {i}",
                status="introduced",
                introduced_at=i,
                importance=5 + i,
            )
        )
    await db.commit()

    original_execute = db.execute
    call_count = [0]

    async def counting_execute(*args, **kwargs):
        call_count[0] += 1
        return await original_execute(*args, **kwargs)

    db.execute = counting_execute

    response = await client.get(f"/api/v1/books/{book.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Eager Loading Test"

    assert call_count[0] <= 5, (
        f"Expected <= 5 execute calls but got {call_count[0]}. "
        f"Selectinload should reduce DB round-trips."
    )


@pytest.mark.asyncio
async def test_book_characters_eager_loading(client, db):
    from app.core.security import create_access_token

    uid = str(uuid.uuid4())[:8]
    email = f"char-eager-{uid}@lorevia.app"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"char{uid}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert r.status_code == 201
    user_id = uuid.UUID(r.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Char Eager Test",
        format="txt",
        s3_key="char_eager.txt",
        status="ready",
        mode="author",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()

    char = Character(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Voice Test Char",
        aliases=["Mara"],
        role="protagonist",
        first_chapter=1,
        mention_count=5,
    )
    db.add(char)
    db.add(
        CharacterVoiceProfile(
            id=uuid.uuid4(),
            book_id=book.id,
            character_id=char.id,
            sample_dialogue_count=10,
            avg_sentence_length=12,
        )
    )
    await db.commit()

    original_execute = db.execute
    call_count = [0]

    async def counting_execute(*args, **kwargs):
        call_count[0] += 1
        return await original_execute(*args, **kwargs)

    db.execute = counting_execute

    response = await client.get(f"/api/v1/books/{book.id}/characters", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Voice Test Char"

    assert call_count[0] <= 6, (
        f"Expected <= 6 execute calls but got {call_count[0]}. "
        f"Selectinload for Character.voice_profile should reduce DB round-trips."
    )

    db.expunge_all()
    sparse_response = await client.get(
        f"/api/v1/books/{book.id}/characters?fields=id,name", headers=headers
    )
    assert sparse_response.status_code == 200
    assert sparse_response.json() == [{"id": str(char.id), "name": "Voice Test Char"}]

    db.expunge_all()
    navigation_response = await client.get(
        f"/api/v1/books/{book.id}/characters?fields=id,name,aliases,status",
        headers=headers,
    )
    assert navigation_response.status_code == 200
    assert navigation_response.json() == [
        {
            "id": str(char.id),
            "name": "Voice Test Char",
            "aliases": ["Mara"],
            "status": "alive",
        }
    ]


@pytest.mark.asyncio
async def test_advisor_greeting_eager_loading(client, db):
    from app.core.security import create_access_token

    uid = str(uuid.uuid4())[:8]
    email = f"adv-eager-{uid}@lorevia.app"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"adv{uid}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert r.status_code == 201
    user_id = uuid.UUID(r.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Advisor Greeting Test",
        format="txt",
        s3_key="adv_greet.txt",
        status="ready",
        total_chapters=3,
    )
    db.add(book)
    await db.flush()

    for i in range(1, 4):
        db.add(
            Character(
                id=uuid.uuid4(),
                book_id=book.id,
                name=f"Adv Char {i}",
                role="supporting",
                first_chapter=i,
            )
        )
    for i in range(1, 3):
        db.add(
            PlotThread(
                id=uuid.uuid4(),
                book_id=book.id,
                title=f"Adv Thread {i}",
                status="introduced",
                introduced_at=i,
            )
        )
    await db.commit()

    original_execute = db.execute
    call_count = [0]

    async def counting_execute(*args, **kwargs):
        call_count[0] += 1
        return await original_execute(*args, **kwargs)

    db.execute = counting_execute

    response = await client.get(f"/api/v1/intelligence/{book.id}/advisor/greeting", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["characters"] == 3
    assert data["stats"]["plot_threads"] == 2

    assert call_count[0] <= 3, (
        f"Expected <= 3 execute calls but got {call_count[0]}. "
        f"Selectinload for Book.characters and Book.plot_threads should reduce DB round-trips "
        f"by eliminating separate COUNT queries."
    )


@pytest.mark.asyncio
async def test_emotional_arc_eager_loading(client, db):
    from app.core.security import create_access_token

    uid = str(uuid.uuid4())[:8]
    email = f"emo-eager-{uid}@lorevia.app"
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": f"emo{uid}",
            "password": "SecurePass456!@#",
            "accepted_terms": True,
            "device_id": f"device-{uuid.uuid4().hex}",
        },
    )
    assert r.status_code == 201
    user_id = uuid.UUID(r.json()["id"])
    token = create_access_token(str(user_id))
    headers = {"Authorization": f"Bearer {token}"}

    book = Book(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Emotional Arc Test",
        format="txt",
        s3_key="emo_arc.txt",
        status="ready",
        total_chapters=3,
    )
    db.add(book)
    await db.flush()

    for i in range(1, 4):
        db.add(
            Character(
                id=uuid.uuid4(),
                book_id=book.id,
                name=f"Emo Char {i}",
                role="supporting",
                first_chapter=i,
                mention_count=10 - i,
                growth_events=[{"event_title": f"Growth {i}", "chapter_number": i}],
            )
        )
    await db.commit()

    original_execute = db.execute
    call_count = [0]

    async def counting_execute(*args, **kwargs):
        call_count[0] += 1
        return await original_execute(*args, **kwargs)

    db.execute = counting_execute

    response = await client.get(f"/api/v1/books/{book.id}/emotional-arc", headers=headers)
    assert response.status_code == 200

    assert call_count[0] <= 3, (
        f"Expected <= 3 execute calls but got {call_count[0]}. "
        f"Selectinload for Book.characters should eliminate the separate character query."
    )
