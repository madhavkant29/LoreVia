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

    async def _fake_check_upload_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.check_upload_limit",
        _fake_check_upload_limit,
    )
    return headers, user_id


@pytest.mark.asyncio
async def test_empty_project_create_basic(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-basic-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={
            "title": "My New Novel",
            "genre": "Fantasy",
            "author": "Jane Doe",
            "work_type": "novel",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == "author"
    assert body["is_editor_project"] is True
    book_id = uuid.UUID(body["book_id"])

    from app.models.book import Book

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.title == "My New Novel"
    assert book.format == "manual"
    assert book.work_type == "novel"
    assert book.status == "ready"
    assert book.is_editor_project is True
    assert book.mode == "author"
    assert book.source_kind == "manual"
    assert book.s3_key is not None and book.s3_key != ""
    assert isinstance(book.writer_workspace, dict)
    assert book.writer_workspace.get("processing", {}).get("is_fully_ready") is True


@pytest.mark.asyncio
async def test_empty_project_create_screenplay(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-scr-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={
            "title": "My Screenplay",
            "work_type": "screenplay",
        },
    )

    assert response.status_code == 200
    body = response.json()
    book_id = uuid.UUID(body["book_id"])

    from app.models.book import Book

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.work_type == "screenplay"
    assert book.format == "manual"
    assert book.is_editor_project is True


@pytest.mark.asyncio
async def test_empty_project_title_required(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-title-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": ""},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_project_title_blank(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-blank-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": "   "},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_empty_project_title_too_short(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-short-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": ""},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_project_with_series(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-series-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from app.models.book import Series

    series = Series(user_id=user_id, name="The Dragon Cycle")
    db.add(series)
    await db.commit()
    await db.refresh(series)

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={
            "title": "Dragon Book One",
            "series_ids": [str(series.id)],
        },
    )

    assert response.status_code == 200
    body = response.json()
    book_id = uuid.UUID(body["book_id"])

    from app.models.book import Book

    book = await db.get(Book, book_id)
    assert book is not None
    assert book.primary_series_id == series.id
    assert book.series_name == series.name


@pytest.mark.asyncio
async def test_empty_project_requires_author_access(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-auth-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    from fastapi import HTTPException

    monkeypatch.setattr(
        "app.api.v1.routes.books.imports.require_author_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(403, "Requires Author plan")),
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": "Denied Project"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_empty_project_no_payload_returns_422(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-no-body-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_project_cache_invalidated(client, db, monkeypatch):
    headers, user_id = await _register_author(
        client, f"empty-cache-{uuid.uuid4().hex[:8]}@lorevia.app", monkeypatch
    )

    response = await client.post(
        "/api/v1/books/empty-project",
        headers=headers,
        json={"title": "Cache Test Book"},
    )

    assert response.status_code == 200
    body = response.json()
    book_id = body["book_id"]

    detail_response = await client.get(
        f"/api/v1/books/{book_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["is_editor_project"] is True
    assert detail["status"] == "ready"
