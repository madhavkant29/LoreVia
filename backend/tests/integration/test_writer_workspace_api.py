import uuid

import pytest
from sqlalchemy import select

from app.models.book import Book, BookCollaborator, Chapter, NovelScene
from app.models.intelligence import ChapterSummary
from app.models.progress import ReadingProgress
from app.utils.book_utils import deserialize_manuscript_content
from app.core.storage import download_book


async def _register_user(client, email: str) -> tuple[dict[str, str], uuid.UUID]:
    from app.core.security import create_access_token

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
async def test_book_overview_returns_critical_reader_payload(client, db):
    headers, user_id = await _register_user(client, f"overview-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(
        user_id=user_id,
        title="Overview Book",
        format="txt",
        s3_key="overview.txt",
        status="ready",
        mode="reader",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()

    chapter_one = Chapter(
        book_id=book.id,
        number=1,
        title="Arrival",
        s3_key="chapters/overview-1.txt",
        processed=True,
    )
    chapter_two = Chapter(
        book_id=book.id,
        number=2,
        title="Aftermath",
        s3_key="chapters/overview-2.txt",
        processed=False,
    )
    db.add_all([chapter_one, chapter_two])
    await db.flush()
    db.add(
        ChapterSummary(
            chapter_id=chapter_one.id,
            mode="short",
            content="Nora reaches the gate.",
            key_events=[{"event": "Nora reaches the gate.", "importance": 1}],
        )
    )
    db.add(
        ReadingProgress(
            user_id=user_id,
            book_id=book.id,
            current_chapter=1,
            scroll_pct=0.5,
            chapters_read=[1],
        )
    )
    await db.commit()

    response = await client.get(f"/api/v1/books/{book.id}/overview", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["book"]["id"] == str(book.id)
    assert payload["progress"]["current_chapter"] == 1
    assert payload["progress"]["chapters_read_count"] == 1
    assert payload["chapter_list"]["current_chapter"] == 1
    assert [chapter["number"] for chapter in payload["chapter_list"]["chapters"]] == [1, 2]
    assert payload["summary_collection"]["read_upto"] == 1
    assert payload["summary_collection"]["summaries"][0]["chapter_number"] == 1
    assert payload["summary_collection"]["summaries"][0]["content"] == "Nora reaches the gate."


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


@pytest.mark.asyncio
async def test_manuscript_import_syncs_chapter_scenes_and_reader_chapter_content(client, db, monkeypatch):
    headers, user_id = await _register_user(client, f"scene-sync-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="txt", s3_key="planner.txt", status="ready", mode="author")
    db.add(book)
    await db.commit()

    async def _fake_process_chapter(_db, _book, ch_data, queue_wait_ms=None):
        chapter = (
            await _db.execute(
                select(Chapter).where(Chapter.book_id == _book.id, Chapter.number == int(ch_data["number"]))
            )
        ).scalar_one_or_none()
        if chapter is None:
            _db.add(
                Chapter(
                    book_id=_book.id,
                    number=int(ch_data["number"]),
                    title=ch_data.get("title"),
                    s3_key=f"chapters/{_book.id}/{int(ch_data['number'])}.txt",
                    processed=True,
                )
            )
            await _db.flush()

    monkeypatch.setattr("app.api.v1.routes.books._process_chapter", _fake_process_chapter)

    import_response = await client.post(
        f"/api/v1/books/{book.id}/manuscript/import",
        headers=headers,
        data={
            "text": "Arrival at the docks.\n\n***\n\nThe captain blocked her path.",
            "title": "Chapter 1",
            "chapter_number": "1",
            "replace_existing": "true",
        },
    )

    assert import_response.status_code == 200
    scenes_response = await client.get(f"/api/v1/books/{book.id}/scenes?chapter_number=1", headers=headers)
    assert scenes_response.status_code == 200
    scenes = scenes_response.json()
    assert len(scenes) == 2
    assert [scene["title"] for scene in scenes] == ["Arrival at the docks.", "The captain blocked her path."]

    chapter_response = await client.get(f"/api/v1/reader/{book.id}/chapter/1", headers=headers)
    assert chapter_response.status_code == 200
    chapter_payload = chapter_response.json()
    assert chapter_payload["text_content"].startswith("## Scene 1 - Arrival at the docks.")
    assert "The captain blocked her path." in chapter_payload["text_content"]

    persisted_chapter = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id, Chapter.number == 1))
    ).scalar_one()
    stored = deserialize_manuscript_content(download_book(persisted_chapter.s3_key))
    assert "## Scene 1 - Arrival at the docks." in str(stored.get("text") or "")

    update_response = await client.put(
        f"/api/v1/books/{book.id}/scenes/{scenes[0]['id']}",
        headers=headers,
        json={
            "title": scenes[0]["title"],
            "description": scenes[0]["description"],
            "body": "POV: Mira\n\nThe boat scraped against the pier.",
            "chapter_number": 1,
            "status": "assigned",
            "sort_order": 1,
        },
    )

    assert update_response.status_code == 200
    updated_chapter_response = await client.get(f"/api/v1/reader/{book.id}/chapter/1", headers=headers)
    assert updated_chapter_response.status_code == 200
    updated_payload = updated_chapter_response.json()
    assert "POV: Mira" in updated_payload["text_content"]
    assert "The boat scraped against the pier." in updated_payload["text_content"]


@pytest.mark.asyncio
async def test_reorder_chapter_scenes_persists_sort_order_and_structure_version(client, db):
    headers, user_id = await _register_user(client, f"scene-order-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="pdf", s3_key="planner.pdf", status="ready", mode="author")
    db.add(book)
    await db.flush()

    chapter = Chapter(
        book_id=book.id,
        number=2,
        title="The Ember Gate",
        s3_key="chapters/2.txt",
        structure_version=4,
    )
    db.add(chapter)
    await db.flush()

    scenes = [
        NovelScene(
            book_id=book.id,
            chapter_id=chapter.id,
            chapter_number=2,
            title="Opening",
            body="Opening body",
            path="scenes/chapter-02/opening.md",
            status="assigned",
            sort_order=1,
            source="manual",
            origin_chapter_number=2,
        ),
        NovelScene(
            book_id=book.id,
            chapter_id=chapter.id,
            chapter_number=2,
            title="Market argument",
            body="Market body",
            path="scenes/chapter-02/market-argument.md",
            status="assigned",
            sort_order=2,
            source="manual",
            origin_chapter_number=2,
        ),
        NovelScene(
            book_id=book.id,
            chapter_id=chapter.id,
            chapter_number=2,
            title="Ambush",
            body="Ambush body",
            path="scenes/chapter-02/ambush.md",
            status="assigned",
            sort_order=3,
            source="manual",
            origin_chapter_number=2,
        ),
    ]
    db.add_all(scenes)
    await db.commit()

    response = await client.patch(
        f"/api/v1/books/{book.id}/chapters/2/scenes/order",
        headers=headers,
        json={
            "scene_ids": [str(scenes[2].id), str(scenes[0].id), str(scenes[1].id)],
            "expected_structure_version": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chapter_number"] == 2
    assert payload["structure_version"] == 5
    assert [scene["id"] for scene in payload["scenes"]] == [
        str(scenes[2].id),
        str(scenes[0].id),
        str(scenes[1].id),
    ]
    assert [scene["sort_order"] for scene in payload["scenes"]] == [1, 2, 3]

    book_id = book.id
    chapter_id = chapter.id
    expected_scene_ids = [str(scene.id) for scene in (scenes[2], scenes[0], scenes[1])]
    db.expire_all()
    persisted = (
        await db.execute(
            select(NovelScene)
            .where(NovelScene.book_id == book_id, NovelScene.chapter_number == 2)
            .order_by(NovelScene.sort_order.asc())
        )
    ).scalars().all()
    assert [str(scene.id) for scene in persisted] == expected_scene_ids

    refreshed_chapter = await db.get(Chapter, chapter_id)
    assert refreshed_chapter is not None
    assert refreshed_chapter.structure_version == 5
    stored = deserialize_manuscript_content(download_book(refreshed_chapter.s3_key))
    stored_text = str(stored.get("text") or "")
    assert stored_text.index("Ambush") < stored_text.index("Opening")
    assert stored_text.index("Opening") < stored_text.index("Market argument")


@pytest.mark.asyncio
async def test_reorder_chapter_scenes_rejects_stale_structure_versions(client, db):
    headers, user_id = await _register_user(client, f"scene-order-conflict-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="pdf", s3_key="planner.pdf", status="ready", mode="author")
    db.add(book)
    await db.flush()

    chapter = Chapter(
        book_id=book.id,
        number=2,
        title="The Ember Gate",
        s3_key="chapters/2.txt",
        structure_version=2,
    )
    db.add(chapter)
    await db.flush()

    scene = NovelScene(
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=2,
        title="Opening",
        body="Opening body",
        path="scenes/chapter-02/opening.md",
        status="assigned",
        sort_order=1,
        source="manual",
        origin_chapter_number=2,
    )
    db.add(scene)
    await db.commit()

    response = await client.patch(
        f"/api/v1/books/{book.id}/chapters/2/scenes/order",
        headers=headers,
        json={
            "scene_ids": [str(scene.id)],
            "expected_structure_version": 1,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Scene order changed elsewhere. Please refresh."


@pytest.mark.asyncio
async def test_manuscript_annotations_round_trip_and_resolve(client, db):
    headers, user_id = await _register_user(client, f"annotations-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="txt", s3_key="planner.txt", status="ready", mode="author")
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=2, title="The Ember Gate", s3_key="chapters/2.json"))
    await db.commit()

    create_response = await client.post(
        f"/api/v1/books/{book.id}/annotations",
        headers=headers,
        json={
            "chapter_number": 2,
            "category": "continuity",
            "visibility": "shared",
            "quote": "The bell cracked at dawn.",
            "comment": "Make this bell detail match chapter 1.",
            "anchor_context_before": "Nora waited.",
            "anchor_context_after": "Then the gate opened.",
            "start_offset": 12,
            "end_offset": 36,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "open"
    assert created["quote"] == "The bell cracked at dawn."
    assert created["can_edit"] is True

    list_response = await client.get(f"/api/v1/books/{book.id}/annotations", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    resolve_response = await client.post(
        f"/api/v1/books/{book.id}/annotations",
        headers=headers,
        json={
            "annotation_id": created["id"],
            "status": "resolved",
        },
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert resolve_response.json()["resolved_at"] is not None


@pytest.mark.asyncio
async def test_shared_manuscript_annotations_visible_to_scoped_collaborators_and_private_hidden(client, db):
    author_headers, author_user_id = await _register_user(client, f"author-ann-{uuid.uuid4().hex[:8]}@lorevia.app")
    collaborator_email = f"reviewer-ann-{uuid.uuid4().hex[:8]}@lorevia.app"
    collaborator_headers, collaborator_user_id = await _register_user(client, collaborator_email)

    book = Book(user_id=author_user_id, title="Planner", format="txt", s3_key="planner.txt", status="ready", mode="author")
    db.add(book)
    await db.flush()
    db.add(Chapter(book_id=book.id, number=2, title="The Ember Gate", s3_key="chapters/2.json"))
    db.add(
        BookCollaborator(
            book_id=book.id,
            invited_user_id=collaborator_user_id,
            email=collaborator_email,
            role="viewer",
            scope={
                "chapter_start": 1,
                "chapter_end": 3,
                "character_bible": False,
                "continuity_report": False,
                "reader_confusion_report": False,
            },
            permissions={
                "can_edit_manuscript": False,
                "can_view_story_bible": False,
                "can_run_ai_scans": False,
                "can_export": False,
                "can_comment": False,
                "can_view_selected_chapters_only": True,
            },
            scope_chapter_start=1,
            scope_chapter_end=3,
            scope_character_bible=False,
            scope_continuity_report=False,
            scope_reader_confusion_report=False,
            permission_can_edit_manuscript=False,
            permission_can_view_story_bible=False,
            permission_can_run_ai_scans=False,
            permission_can_export=False,
            permission_can_comment=False,
            permission_can_view_selected_chapters_only=True,
            invite_status="active",
        )
    )
    await db.commit()

    for visibility in ("shared", "private"):
        response = await client.post(
            f"/api/v1/books/{book.id}/annotations",
            headers=author_headers,
            json={
                "chapter_number": 2,
                "category": "general",
                "visibility": visibility,
                "quote": f"{visibility} quote",
                "comment": f"{visibility} comment",
            },
        )
        assert response.status_code == 200

    collaborator_list = await client.get(f"/api/v1/books/{book.id}/annotations", headers=collaborator_headers)
    assert collaborator_list.status_code == 200
    visible = collaborator_list.json()
    assert len(visible) == 1
    assert visible[0]["visibility"] == "shared"


@pytest.mark.asyncio
async def test_scene_version_history_can_snapshot_compare_and_restore(client, db):
    headers, user_id = await _register_user(client, f"scene-versions-{uuid.uuid4().hex[:8]}@lorevia.app")
    book = Book(user_id=user_id, title="Planner", format="txt", s3_key="planner.txt", status="ready", mode="author")
    db.add(book)
    await db.commit()

    created = await client.post(
        f"/api/v1/books/{book.id}/scenes",
        headers=headers,
        json={
            "title": "Rooftop Meeting",
            "description": "The first confrontation.",
            "body": "Rain cut silver lines across the roof.",
            "chapter_number": 2,
            "sort_order": 1,
        },
    )
    assert created.status_code == 200
    created_scene = created.json()

    manual_snapshot = await client.post(
        f"/api/v1/books/{book.id}/scenes/{created_scene['id']}/snapshot",
        headers=headers,
        params={"note": "Named rooftop draft"},
    )
    assert manual_snapshot.status_code == 200
    assert manual_snapshot.json()["note"] == "Named rooftop draft"
    assert manual_snapshot.json()["snapshot_kind"] == "manual"

    updated = await client.put(
        f"/api/v1/books/{book.id}/scenes/{created_scene['id']}",
        headers=headers,
        json={
            "title": "Rooftop Meeting Revised",
            "description": "The confrontation sharpens.",
            "body": "Rain cut silver lines across the roof while Mara held the key steady.",
            "chapter_number": 2,
            "sort_order": 1,
        },
    )
    assert updated.status_code == 200

    versions_response = await client.get(
        f"/api/v1/books/{book.id}/scenes/{created_scene['id']}/versions",
        headers=headers,
    )
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) >= 2
    assert {version["snapshot_kind"] for version in versions} >= {"manual", "auto_checkpoint"}

    auto_checkpoint = next(version for version in versions if version["snapshot_kind"] == "auto_checkpoint")
    detail_response = await client.get(
        f"/api/v1/books/{book.id}/scene-versions/{auto_checkpoint['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["scene_title"] == "Rooftop Meeting"
    assert detail["body"] == "Rain cut silver lines across the roof."

    restored_response = await client.post(
        f"/api/v1/books/{book.id}/scene-versions/{auto_checkpoint['id']}/restore",
        headers=headers,
    )
    assert restored_response.status_code == 200
    restored = restored_response.json()
    assert restored["scene"]["title"] == "Rooftop Meeting"
    assert restored["scene"]["body"] == "Rain cut silver lines across the roof."
    assert any(version["snapshot_kind"] == "pre_restore" for version in restored["versions"])
