"""Saved-chapter voice review jobs are authorized, durable, and source-bound."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes.advisor import voice_chapter
from app.models.book import Book, Chapter
from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.services import voice_chapter_review_jobs_service, voice_chapter_review_service
from app.services.voice_chapter_review_jobs_service import (
    claim_voice_chapter_job,
    find_latest_voice_chapter_job,
    start_voice_chapter_job,
    update_voice_chapter_job,
    voice_chapter_resume_candidates,
)
from app.utils.voice_chapter_review_utils import voice_chapter_fingerprint


@pytest.mark.asyncio
async def test_chapter_review_start_reuses_job_and_reports_progress(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Glass Harbor",
        format="manual",
        work_type="novel",
        s3_key="books/glass-harbor.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=2, s3_key="chapters/glass-harbor-2")
    db.add(chapter)
    await db.commit()
    source = 'Mara said, "I will return before dawn."'

    async def load(_db, *, book_id, chapter_number):
        assert book_id == book.id and chapter_number == 2
        return chapter, source, voice_chapter_fingerprint(source)

    monkeypatch.setattr(voice_chapter, "load_saved_voice_chapter", load)
    enqueued = []
    monkeypatch.setattr(
        voice_chapter.review_voice_chapter_task,
        "apply_async",
        lambda **kwargs: enqueued.append(kwargs),
    )
    path = f"/api/v1/intelligence/{book.id}/advisor/voice-chapters"
    first = await client.post(path, json={"chapter_number": 2}, headers=auth_headers)
    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    again = await client.post(path, json={"chapter_number": 2}, headers=auth_headers)
    assert again.status_code == 202
    assert again.json()["job_id"] == first.json()["job_id"]
    assert len(enqueued) == 1
    job_id = uuid.UUID(first.json()["job_id"])
    status = await client.get(f"{path}/jobs/{job_id}", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["result"] is None
    assert "source_fingerprint" not in status.text
    assert (await client.get(f"{path}/latest?chapter_number=2", headers=auth_headers)).json()[
        "job_id"
    ] == str(job_id)
    assert (
        await client.get(f"{path}/jobs/{uuid.uuid4()}", headers=auth_headers)
    ).status_code == 404
    assert (await client.get(f"{path}/jobs/{job_id}")).status_code == 401

    job = await find_latest_voice_chapter_job(
        db, book_id=book.id, user_id=user_id, chapter_number=2
    )
    assert job is not None
    job.status = "running"
    job.result_json = {
        **job.result_json,
        "_execution_id": "worker-1",
        "plan": {"work": [{"key": "one"}, {"key": "two"}]},
    }
    await db.commit()
    assert await update_voice_chapter_job(
        db,
        job_id=job_id,
        execution_id="worker-1",
        state_changes={"completed": {"one": {"review": {"issues": []}}}},
    )
    progress = await client.get(f"{path}/jobs/{job_id}", headers=auth_headers)
    assert progress.json()["progress"] == {"completed": 1, "total": 2}
    assert progress.json()["result"] is None
    assert "worker-1" not in progress.text
    job.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    assert (await client.get(f"{path}/jobs/{job_id}", headers=auth_headers)).status_code == 404
    job.expires_at = datetime.now(UTC) + timedelta(days=7)
    await db.commit()


@pytest.mark.asyncio
async def test_duplicate_delivery_cannot_resume_manual_quota_pause(db, client, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Manual quota pause",
        format="manual",
        work_type="novel",
        s3_key="books/manual-quota.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()
    fingerprint = voice_chapter_fingerprint("unchanged source")
    job, _ = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=user_id,
        chapter_number=1,
        source_fingerprint=fingerprint,
    )
    job.status = "paused"
    job.result_json = {**job.result_json, "next_resume_at": None}
    await db.commit()

    assert await claim_voice_chapter_job(db, job_id=job.id, execution_id="duplicate") is None
    await db.refresh(job)
    assert job.status == "paused"

    retried, enqueue = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=user_id,
        chapter_number=1,
        source_fingerprint=fingerprint,
        retry_paused=True,
    )
    assert enqueue and retried.id == job.id
    assert await claim_voice_chapter_job(db, job_id=job.id, execution_id="manual-retry")
    future = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    assert await update_voice_chapter_job(
        db,
        job_id=job.id,
        execution_id="manual-retry",
        status="paused",
        state_changes={"next_resume_at": future},
    )
    assert await claim_voice_chapter_job(db, job_id=job.id, execution_id="too-early") is None
    job.result_json = {
        **job.result_json,
        "next_resume_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    }
    await db.commit()
    assert await claim_voice_chapter_job(db, job_id=job.id, execution_id="due-retry")


@pytest.mark.asyncio
async def test_configuration_error_fails_without_scheduling_ai_capacity_retry(
    db, client, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Configuration failure",
        format="manual",
        work_type="novel",
        s3_key="books/voice-config.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=1, s3_key="chapters/voice-config-1")
    db.add(chapter)
    await db.commit()
    source = 'Mara said, "Take the north road before nightfall."'
    fingerprint = voice_chapter_fingerprint(source)
    job, _ = await start_voice_chapter_job(
        db, book_id=book.id, user_id=user_id, chapter_number=1, source_fingerprint=fingerprint
    )

    async def access(*_args, **_kwargs):
        return book, None, None

    async def load(*_args, **_kwargs):
        return chapter, source, fingerprint

    async def characters(*_args, **_kwargs):
        return [{"id": uuid.uuid4(), "name": "Mara", "aliases": []}]

    async def version(*_args, **_kwargs):
        return 1

    async def review(**_kwargs):
        raise HTTPException(503, detail={"kind": "llm_configuration"})

    monkeypatch.setattr(voice_chapter_review_service, "get_book_with_ai_scan_access", access)
    monkeypatch.setattr(voice_chapter_review_service, "load_saved_voice_chapter", load)
    monkeypatch.setattr(voice_chapter_review_service, "load_voice_review_characters", characters)
    monkeypatch.setattr(voice_chapter_review_service, "get_book_cache_version", version)
    monkeypatch.setattr(voice_chapter_review_service, "run_voice_consistency_review", review)

    claimed = await claim_voice_chapter_job(db, job_id=job.id, execution_id="config")
    assert claimed is not None
    assert (
        await voice_chapter_review_service.process_voice_chapter_job(
            db, job=claimed, execution_id="config"
        )
        == "failed"
    )
    await db.refresh(job)
    assert job.status == "failed"
    assert job.result_json.get("next_resume_at") is None
    assert "contact support" in job.error_detail.lower()


@pytest.mark.asyncio
async def test_completed_voice_review_is_hidden_after_source_changes(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Changing chapter",
        format="manual",
        work_type="novel",
        s3_key="books/changing-chapter.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=1, s3_key="chapters/changing-1")
    db.add(chapter)
    await db.commit()
    original = 'Mara said, "Wait here."'
    job, _ = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=user_id,
        chapter_number=1,
        source_fingerprint=voice_chapter_fingerprint(original),
    )
    job.status = "complete"
    job.result_json = {**job.result_json, "result": {"status": "complete", "voices": []}}
    await db.commit()

    async def changed(_db, *, book_id, chapter_number):
        return chapter, "Changed source", voice_chapter_fingerprint("Changed source")

    monkeypatch.setattr(voice_chapter_review_jobs_service, "load_saved_voice_chapter", changed)
    status = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/voice-chapters/jobs/{job.id}",
        headers=auth_headers,
    )
    assert status.status_code == 200
    assert status.json()["status"] == "failed"
    assert status.json()["result"] is None
    assert "chapter changed" in status.json()["error"].lower()


@pytest.mark.asyncio
async def test_explicit_refresh_creates_one_new_job_after_completed_review(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Review again",
        format="manual",
        work_type="novel",
        s3_key="books/review-again.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=1, s3_key="chapters/review-again-1")
    db.add(chapter)
    await db.commit()
    source = 'Mara said, "I remember the harbor."'

    async def load(_db, *, book_id, chapter_number):
        return chapter, source, voice_chapter_fingerprint(source)

    monkeypatch.setattr(voice_chapter, "load_saved_voice_chapter", load)
    enqueued = []
    monkeypatch.setattr(
        voice_chapter.review_voice_chapter_task,
        "apply_async",
        lambda **kwargs: enqueued.append(kwargs),
    )
    path = f"/api/v1/intelligence/{book.id}/advisor/voice-chapters"
    initial = await client.post(path, json={"chapter_number": 1}, headers=auth_headers)
    assert initial.status_code == 202
    first_id = uuid.UUID(initial.json()["job_id"])
    first_job = await db.get(AdvisorJob, first_id)
    first_job.status = "complete"
    first_job.result_json = {**first_job.result_json, "result": {"status": "complete"}}
    await db.commit()

    reused = await client.post(path, json={"chapter_number": 1}, headers=auth_headers)
    assert reused.status_code == 200
    assert reused.json()["job_id"] == str(first_id)

    refreshed = await client.post(
        path, json={"chapter_number": 1, "force_refresh": True}, headers=auth_headers
    )
    assert refreshed.status_code == 202
    assert refreshed.json()["job_id"] != str(first_id)
    duplicate = await client.post(
        path, json={"chapter_number": 1, "force_refresh": True}, headers=auth_headers
    )
    assert duplicate.json()["job_id"] == refreshed.json()["job_id"]
    assert len(enqueued) == 2


@pytest.mark.asyncio
async def test_capacity_pause_resumes_only_unfinished_voice_sections(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Checkpointed voices",
        format="manual",
        work_type="novel",
        s3_key="books/checkpointed.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=2, s3_key="chapters/checkpointed-2")
    db.add(chapter)
    await db.commit()
    source = 'Mara said, "Keep the lantern lit." Lina said, "I will watch the gate."'
    fingerprint = voice_chapter_fingerprint(source)
    job, _ = await start_voice_chapter_job(
        db, book_id=book.id, user_id=user_id, chapter_number=2, source_fingerprint=fingerprint
    )
    mara_id, lina_id = uuid.uuid4(), uuid.uuid4()

    async def access(*_args, **_kwargs):
        return book, None, None

    async def load(*_args, **_kwargs):
        return chapter, source, fingerprint

    async def characters(*_args, **_kwargs):
        return [
            {"id": mara_id, "name": "Mara", "aliases": []},
            {"id": lina_id, "name": "Lina", "aliases": []},
        ]

    async def version(*_args, **_kwargs):
        return 1

    calls = []
    capacity_busy = True

    async def review(*, body, **_kwargs):
        nonlocal capacity_busy
        calls.append(body.character_id)
        if body.character_id == lina_id and capacity_busy:
            capacity_busy = False
            raise HTTPException(503, detail={"kind": "llm_provider"})
        return {
            "review": {"status": "complete", "issues": []},
            "warnings": [],
            "retrieved_passages": [{"excerpt": "baseline source is not needed in the checkpoint"}],
            "coverage": {
                "total_characters": len(body.text),
                "processed_ranges": [{"start": 0, "end": len(body.text)}],
                "compared_ranges": [{"start": 0, "end": len(body.text)}],
            },
        }

    monkeypatch.setattr(voice_chapter_review_service, "get_book_with_ai_scan_access", access)
    monkeypatch.setattr(voice_chapter_review_service, "load_saved_voice_chapter", load)
    monkeypatch.setattr(voice_chapter_review_service, "load_voice_review_characters", characters)
    monkeypatch.setattr(voice_chapter_review_service, "get_book_cache_version", version)
    monkeypatch.setattr(voice_chapter_review_service, "run_voice_consistency_review", review)

    claimed = await claim_voice_chapter_job(db, job_id=job.id, execution_id="first")
    assert claimed is not None
    assert (
        await voice_chapter_review_service.process_voice_chapter_job(
            db, job=claimed, execution_id="first"
        )
        == "paused"
    )
    await db.refresh(job)
    assert len(job.result_json["completed"]) == 1
    assert all("retrieved_passages" not in value for value in job.result_json["completed"].values())
    assert job.result_json["next_resume_at"]
    job.expires_at = datetime.now(UTC) + timedelta(hours=1)
    await db.commit()

    retried, enqueue = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=user_id,
        chapter_number=2,
        source_fingerprint=fingerprint,
        retry_paused=True,
    )
    assert enqueue is True and retried.id == job.id
    claimed = await claim_voice_chapter_job(db, job_id=job.id, execution_id="second")
    assert claimed is not None
    assert (
        await voice_chapter_review_service.process_voice_chapter_job(
            db, job=claimed, execution_id="second"
        )
        == "complete"
    )
    await db.refresh(job)
    assert job.status == "complete"
    assert job.expires_at > datetime.now(UTC) + timedelta(days=6)
    assert len(job.result_json["completed"]) == 2
    assert calls == [mara_id, lina_id, lina_id]


@pytest.mark.asyncio
async def test_long_voice_review_yields_and_resumes_from_checkpoint(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Long voice review",
        format="manual",
        work_type="novel",
        s3_key="books/long-voice.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=2, s3_key="chapters/long-voice-2")
    db.add(chapter)
    await db.commit()
    source = 'Mara said, "Take the north road." Lina said, "I will take the south road."'
    fingerprint = voice_chapter_fingerprint(source)
    job, _ = await start_voice_chapter_job(
        db, book_id=book.id, user_id=user_id, chapter_number=2, source_fingerprint=fingerprint
    )
    mara_id, lina_id = uuid.uuid4(), uuid.uuid4()

    async def access(*_args, **_kwargs):
        return book, None, None

    async def load(*_args, **_kwargs):
        return chapter, source, fingerprint

    async def characters(*_args, **_kwargs):
        return [
            {"id": mara_id, "name": "Mara", "aliases": []},
            {"id": lina_id, "name": "Lina", "aliases": []},
        ]

    async def version(*_args, **_kwargs):
        return 1

    clock = [0.0]
    calls = []

    async def review(*, body, **_kwargs):
        calls.append(body.character_id)
        if len(calls) == 1:
            clock[0] = 721.0
        return {
            "review": {"status": "complete", "issues": []},
            "warnings": [],
            "coverage": {
                "total_characters": len(body.text),
                "processed_ranges": [{"start": 0, "end": len(body.text)}],
                "compared_ranges": [{"start": 0, "end": len(body.text)}],
            },
        }

    monkeypatch.setattr(voice_chapter_review_service, "get_book_with_ai_scan_access", access)
    monkeypatch.setattr(voice_chapter_review_service, "load_saved_voice_chapter", load)
    monkeypatch.setattr(voice_chapter_review_service, "load_voice_review_characters", characters)
    monkeypatch.setattr(voice_chapter_review_service, "get_book_cache_version", version)
    monkeypatch.setattr(voice_chapter_review_service, "run_voice_consistency_review", review)
    monkeypatch.setattr(voice_chapter_review_service, "monotonic", lambda: clock[0])

    claimed = await claim_voice_chapter_job(db, job_id=job.id, execution_id="slice-one")
    assert claimed is not None
    assert (
        await voice_chapter_review_service.process_voice_chapter_job(
            db, job=claimed, execution_id="slice-one"
        )
        == "paused"
    )
    await db.refresh(job)
    assert job.error_code == "continuing"
    assert len(job.result_json["completed"]) == 1
    assert job.result_json["next_resume_at"]

    clock[0] = 0.0
    retried, enqueue = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=user_id,
        chapter_number=2,
        source_fingerprint=fingerprint,
        retry_paused=True,
    )
    assert enqueue and retried.id == job.id
    claimed = await claim_voice_chapter_job(db, job_id=job.id, execution_id="slice-two")
    assert claimed is not None
    assert (
        await voice_chapter_review_service.process_voice_chapter_job(
            db, job=claimed, execution_id="slice-two"
        )
        == "complete"
    )
    assert calls == [mara_id, lina_id]


@pytest.mark.asyncio
async def test_chapter_review_does_not_expose_chapters_outside_collaborator_scope(
    client, db, auth_headers, monkeypatch
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Restricted chapter",
        format="manual",
        work_type="novel",
        s3_key="books/restricted.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()
    collaborator = SimpleNamespace(
        role="editor",
        scope={"chapter_start": 1, "chapter_end": 1},
        permissions={"can_view_selected_chapters_only": True},
    )

    async def restricted_access(*_args, **_kwargs):
        return book, collaborator, None

    monkeypatch.setattr(voice_chapter, "get_book_with_ai_scan_access", restricted_access)
    path = f"/api/v1/intelligence/{book.id}/advisor/voice-chapters"
    assert (
        await client.post(path, json={"chapter_number": 2}, headers=auth_headers)
    ).status_code == 403
    assert (
        await client.get(f"{path}/latest?chapter_number=2", headers=auth_headers)
    ).status_code == 403
    job, _ = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=user_id,
        chapter_number=2,
        source_fingerprint=voice_chapter_fingerprint("restricted source"),
    )
    assert (await client.get(f"{path}/jobs/{job.id}", headers=auth_headers)).status_code == 403


@pytest.mark.asyncio
async def test_collaborator_chapter_review_bills_book_owner(db, client, auth_headers, monkeypatch):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    owner_id = uuid.UUID(me.json()["id"])
    collaborator_user = User(email=f"voice-{uuid.uuid4()}@example.test", password_hash="test")
    db.add(collaborator_user)
    book = Book(
        user_id=owner_id,
        title="Owner billed voices",
        format="manual",
        work_type="novel",
        s3_key="books/owner-billed.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(book_id=book.id, number=2, s3_key="chapters/owner-billed-2")
    db.add(chapter)
    await db.commit()
    source = 'Mara said, "I checked the north gate."'
    fingerprint = voice_chapter_fingerprint(source)
    job, _ = await start_voice_chapter_job(
        db,
        book_id=book.id,
        user_id=collaborator_user.id,
        chapter_number=2,
        source_fingerprint=fingerprint,
    )

    async def access(*_args, **_kwargs):
        return book, SimpleNamespace(role="editor", scope={}, permissions={}), None

    async def load(*_args, **_kwargs):
        return chapter, source, fingerprint

    async def characters(*_args, **_kwargs):
        return [{"id": uuid.uuid4(), "name": "Mara", "aliases": []}]

    async def version(*_args, **_kwargs):
        return 1

    billed = []

    async def review(*, body, current_user, **_kwargs):
        billed.append(current_user.id)
        return {
            "review": {"status": "insufficient_evidence", "issues": []},
            "warnings": [],
            "coverage": {
                "processed_ranges": [],
                "compared_ranges": [],
                "total_characters": len(body.text),
            },
        }

    monkeypatch.setattr(voice_chapter_review_service, "get_book_with_ai_scan_access", access)
    monkeypatch.setattr(voice_chapter_review_service, "load_saved_voice_chapter", load)
    monkeypatch.setattr(voice_chapter_review_service, "load_voice_review_characters", characters)
    monkeypatch.setattr(voice_chapter_review_service, "get_book_cache_version", version)
    monkeypatch.setattr(voice_chapter_review_service, "run_voice_consistency_review", review)
    claimed = await claim_voice_chapter_job(db, job_id=job.id, execution_id="collaborator")
    assert claimed is not None
    assert (
        await voice_chapter_review_service.process_voice_chapter_job(
            db, job=claimed, execution_id="collaborator"
        )
        == "complete"
    )
    assert billed == [owner_id]


@pytest.mark.asyncio
async def test_manual_capacity_pause_does_not_starve_due_resume(db, client, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Resume ordering",
        format="manual",
        work_type="novel",
        s3_key="books/resume-ordering.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    now = datetime.now(UTC)
    manual = AdvisorJob(
        user_id=user_id,
        book_id=book.id,
        scope="book_voice_chapter",
        status="paused",
        result_json={"chapter_number": 1, "next_resume_at": None},
        expires_at=now + timedelta(days=7),
        updated_at=now - timedelta(days=1),
    )
    due = AdvisorJob(
        user_id=user_id,
        book_id=book.id,
        scope="book_voice_chapter",
        status="paused",
        result_json={
            "chapter_number": 2,
            "next_resume_at": (now - timedelta(minutes=1)).isoformat(),
        },
        expires_at=now + timedelta(days=7),
        updated_at=now - timedelta(minutes=10),
    )
    db.add_all([manual, due])
    await db.commit()
    rows = (await db.scalars(voice_chapter_resume_candidates(now, limit=1))).all()
    assert [item.id for item in rows] == [due.id]
