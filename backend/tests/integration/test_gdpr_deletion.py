import uuid
import zipfile
from io import BytesIO

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.book import (
    Book,
    BookForumComment,
    BookForumPost,
    Chapter,
    ChapterMedia,
    ChapterVersion,
    SceneVersion,
)
from app.models.intelligence import WorldBuildingDocument
from app.models.user import DataDeletionRequest, Subscription, User
from app.services.privacy_service import collect_book_storage_keys


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
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
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}, user_id


@pytest.mark.asyncio
async def test_data_export_returns_zip_with_account_and_book(client, db):
    headers, user_id = await _register_user(client, f"export-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(
        user_id=user_id,
        title="Export Book",
        format="txt",
        work_type="novel",
        s3_key="books/export.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add(
        Chapter(
            book_id=book.id, number=1, title="One", s3_key="chapters/export-1.json", processed=True
        )
    )
    await db.commit()

    response = await client.get("/api/v1/auth/me/data-export", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(response.content)) as exported:
        names = set(exported.namelist())
        assert "account.json" in names
        assert "books/index.json" in names
        assert f"books/{book.id}/chapters.json" in names


@pytest.mark.asyncio
async def test_collect_book_storage_keys_covers_project_artifact_types(db):
    user = User(
        email=f"keys-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"keys{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Storage Keys",
        format="txt",
        work_type="novel",
        s3_key="books/source.txt",
        cover_s3_key="covers/source.png",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=1, s3_key="chapters/1.json")
    db.add(chapter)
    await db.flush()
    post = BookForumPost(
        book_id=book.id,
        author_user_id=user.id,
        headline="Post",
        body="Body",
        image_s3_key="forum/post.png",
    )
    db.add(post)
    await db.flush()
    db.add_all(
        [
            ChapterVersion(
                book_id=book.id,
                chapter_id=chapter.id,
                chapter_number=1,
                s3_key="versions/chapter-1.json",
            ),
            SceneVersion(
                book_id=book.id,
                chapter_id=chapter.id,
                chapter_number=1,
                scene_title="A",
                s3_key="versions/scene-1.json",
            ),
            WorldBuildingDocument(book_id=book.id, title="World", s3_key="world/world.json"),
            ChapterMedia(
                book_id=book.id, chapter_id=chapter.id, marker="img1", storage_key="media/img1.png"
            ),
            BookForumComment(
                post_id=post.id,
                book_id=book.id,
                author_user_id=user.id,
                body="Comment",
                image_s3_key="forum/comment.png",
            ),
        ]
    )
    await db.commit()

    keys = await collect_book_storage_keys(db, book.id)

    assert {
        "books/source.txt",
        "covers/source.png",
        "chapters/1.json",
        "versions/chapter-1.json",
        "versions/scene-1.json",
        "world/world.json",
        "media/img1.png",
        "forum/post.png",
        "forum/comment.png",
    }.issubset(set(keys))


@pytest.mark.asyncio
async def test_permanent_book_delete_hides_and_queues_deletion(client, db):
    headers, user_id = await _register_user(
        client, f"book-delete-{uuid.uuid4().hex[:8]}@lorevia.app"
    )
    book = Book(
        user_id=user_id,
        title="Delete Book",
        format="txt",
        work_type="novel",
        s3_key="books/delete.txt",
        status="ready",
        mode="author",
        is_public=True,
        public_status="published",
    )
    db.add(book)
    await db.commit()

    response = await client.request(
        "DELETE",
        f"/api/v1/books/{book.id}/permanent",
        headers=headers,
        json={"confirmation_text": "DELETE BOOK"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["book_id"] == str(book.id)
    request = await db.get(DataDeletionRequest, uuid.UUID(payload["deletion_request_id"]))
    assert request is not None
    assert request.request_type == "book"
    await db.refresh(book)
    assert book.hidden_at is not None
    assert book.is_public is False


@pytest.mark.asyncio
async def test_account_deletion_queues_job_cancels_renewal_and_blocks_login(
    client, db, monkeypatch
):
    cancelled: list[str] = []

    async def fake_cancel(subscription_id: str):
        cancelled.append(subscription_id)
        return {"id": subscription_id}

    async def fake_supabase_delete(_supabase_auth_id):
        return {"configured": False, "deleted": False, "followup_required": False}

    monkeypatch.setattr(
        "app.services.privacy_service.cancel_subscription_at_period_end", fake_cancel
    )
    monkeypatch.setattr(
        "app.services.privacy_service.delete_supabase_auth_user", fake_supabase_delete
    )

    email = f"account-delete-{uuid.uuid4().hex[:8]}@lorevia.app"
    headers, user_id = await _register_user(client, email)
    user = await db.get(User, user_id)
    user.email_verified_at = user.created_at
    db.add(
        Subscription(
            user_id=user_id, paddle_sub_id="sub_period_end", plan="author_monthly", status="active"
        )
    )
    await db.commit()

    response = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers=headers,
        json={"confirmation_text": "DELETE MY ACCOUNT", "password": "StrongPass123!@#"},
    )

    assert response.status_code == 200
    assert cancelled == ["sub_period_end"]
    await db.refresh(user)
    assert user.deletion_status in {"pending_hard_delete", "provider_followup_required"}
    assert user.email.startswith("deleted+")
    assert user.token_version > 1
    request = (
        await db.execute(
            select(DataDeletionRequest).where(
                DataDeletionRequest.user_id == user_id,
                DataDeletionRequest.request_type == "account",
            )
        )
    ).scalar_one()
    assert request.scheduled_for is not None

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass123!@#",
            "device_id": f"device-{uuid.uuid4().hex[:24]}",
        },
    )
    assert login_response.status_code == 401
