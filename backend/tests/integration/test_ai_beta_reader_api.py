from __future__ import annotations

import copy
import uuid
from types import SimpleNamespace

import pytest

from app.core.security import create_access_token
from app.models.book import Book, BookCollaborator, Chapter
from app.models.intelligence import AdvisorJob
from app.models.user import User
from app.services.advisor_jobs_service import ADVISOR_SCOPE_BETA_READER
from app.services.beta_reader_analysis_service import beta_reader_request_payload
from app.utils.advisor_beta_reader_analysis_utils import (
    build_beta_reader_request_hash,
    build_chapter_source_fingerprint,
)


def _auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _user(db, email: str, tier: str = "author") -> User:
    user = User(
        email=email,
        username=email.split("@", 1)[0],
        password_hash="hashed",
        tier=tier,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _book_with_chapters(db, owner: User) -> tuple[Book, list[Chapter]]:
    book = Book(
        user_id=owner.id,
        title="The Echo House",
        author="A. Writer",
        format="manual",
        work_type="novel",
        s3_key="books/echo-house.txt",
        status="ready",
        mode="author",
        total_chapters=2,
    )
    db.add(book)
    await db.flush()
    chapters = [
        Chapter(
            book_id=book.id,
            number=number,
            title=f"Chapter {number}",
            s3_key=f"chapters/{number}.json",
            content_version=1,
            processed=True,
        )
        for number in (1, 2)
    ]
    db.add_all(chapters)
    await db.commit()
    return book, chapters


def _stored_report(chapters: list[Chapter]) -> dict:
    from app.schemas.advisor import BetaReaderAnalysisRequest

    body = BetaReaderAnalysisRequest(scope="chapter", chapter_number=1, checks=["repetition"])
    return {
        "report_id": "report-1",
        "scope": "chapter",
        "request_hash": build_beta_reader_request_hash(beta_reader_request_payload(body)),
        "source_fingerprint": build_chapter_source_fingerprint([chapters[0]]),
        "created_at": "2026-08-30T10:00:00Z",
        "is_stale": False,
        "checks": ["repetition"],
        "coverage": {
            "requested_chapters": [1],
            "analyzed_chapters": [1],
            "missing_chapters": [],
            "word_count": 800,
            "character_count": 2,
        },
        "overall_impression": "The chapter opens with a clear promise.",
        "strengths": ["The setting is immediate."],
        "reader_questions": ["Why does Mara avoid the door?"],
        "prioritized_revisions": ["Vary the repeated threshold image."],
        "overused_terms": [],
        "character_voices": [],
        "findings": [],
        "revision_candidates": [
            {
                "id": "candidate-1",
                "source_item_id": "term-1",
                "category": "repetition",
                "severity": "medium",
                "title": "Review repeated threshold image",
                "description": "The same image appears in quick succession.",
                "recommendation": "Keep the strongest use and vary the others.",
                "chapter_number": 1,
                "evidence": [{"chapter_number": 1, "excerpt": "She waited at the threshold."}],
            }
        ],
        "warnings": [],
    }


@pytest.mark.asyncio
async def test_ai_beta_reader_queues_jobs_and_enforces_job_ownership(client, db, monkeypatch):
    owner = await _user(db, "beta-owner@lorevia.test")
    stranger = await _user(db, "beta-stranger@lorevia.test")
    book, _ = await _book_with_chapters(db, owner)
    queued: list[dict] = []

    async def allow_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.routes.advisor.beta_reader.enforce_continuity_rate_limit",
        allow_rate_limit,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.beta_reader.generate_beta_reader_report_task",
        SimpleNamespace(apply_async=lambda *args, **kwargs: queued.append(kwargs)),
    )

    response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader",
        headers=_auth_headers(owner.id),
        json={"scope": "chapter", "chapter_number": 1},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["cached"] is False
    assert queued and queued[0]["kwargs"]["request_payload"]["checks"] == [
        "repetition",
        "voice",
        "reader_feedback",
    ]

    task_id = response.json()["task_id"]
    status_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/jobs/{task_id}",
        headers=_auth_headers(owner.id),
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"

    unrelated_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/jobs/{task_id}",
        headers=_auth_headers(stranger.id),
    )
    assert unrelated_response.status_code == 404


@pytest.mark.asyncio
async def test_ai_beta_reader_failed_job_returns_safe_error_code(client, db):
    owner = await _user(db, "failed-beta-owner@lorevia.test")
    book, _ = await _book_with_chapters(db, owner)
    job = AdvisorJob(
        user_id=owner.id,
        book_id=book.id,
        scope=ADVISOR_SCOPE_BETA_READER,
        status="failed",
        error_code="beta_reader_generation_failed",
        error_detail="internal provider timeout with manuscript context",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/jobs/{job.id}",
        headers=_auth_headers(owner.id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "beta_reader_generation_failed"
    assert "internal provider timeout" not in response.text


@pytest.mark.asyncio
async def test_first_impression_status_and_explicit_failed_retry(client, db, monkeypatch):
    owner = await _user(db, "first-read-owner@lorevia.test")
    stranger = await _user(db, "first-read-stranger@lorevia.test")
    book, _ = await _book_with_chapters(db, owner)
    book.writer_workspace = {
        "first_impression": {
            "status": "failed",
            "job_id": None,
            "report_id": None,
            "request_hash": "request-hash",
            "source_fingerprint": "source-fingerprint",
            "started_at": "2026-08-31T00:00:00Z",
            "completed_at": None,
            "error_code": "beta_reader_generation_failed",
        }
    }
    await db.commit()

    status_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/first-impression",
        headers=_auth_headers(owner.id),
    )
    assert status_response.status_code == 200
    assert status_response.json() == {
        "status": "failed",
        "task_id": None,
        "progress": None,
        "report": None,
        "error": "beta_reader_generation_failed",
        "can_retry": True,
    }

    stranger_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/first-impression",
        headers=_auth_headers(stranger.id),
    )
    assert stranger_response.status_code == 404

    queued: list[dict] = []
    monkeypatch.setattr(
        "app.workers.tasks.intelligence_tasks.generate_beta_reader_report_task.apply_async",
        lambda *args, **kwargs: queued.append(kwargs),
    )
    retry_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/first-impression/retry",
        headers=_auth_headers(owner.id),
    )
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "queued"
    assert queued[0]["kwargs"]["request_payload"] == {
        "scope": "full_book",
        "text": None,
        "chapter_number": None,
        "chapter_start": None,
        "chapter_end": None,
        "checks": ["reader_feedback"],
        "character_ids": [],
    }

    duplicate_retry = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/first-impression/retry",
        headers=_auth_headers(owner.id),
    )
    assert duplicate_retry.status_code == 409


@pytest.mark.asyncio
async def test_ai_beta_reader_cache_stale_reports_and_idempotent_revision_tasks(
    client, db, monkeypatch
):
    owner = await _user(db, "cached-beta-owner@lorevia.test")
    book, chapters = await _book_with_chapters(db, owner)
    report = _stored_report(chapters)
    book.writer_workspace = {"ai_beta_reader": {"reports": [report]}}
    await db.commit()

    async def allow_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.routes.advisor.beta_reader.enforce_continuity_rate_limit",
        allow_rate_limit,
    )

    cached_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader",
        headers=_auth_headers(owner.id),
        json={"scope": "chapter", "chapter_number": 1, "checks": ["repetition"]},
    )
    assert cached_response.status_code == 200
    assert cached_response.json()["cached"] is True
    assert cached_response.json()["task_id"] is None

    for expected_created in (True, False):
        task_response = await client.post(
            f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports/report-1/revision-candidates/candidate-1",
            headers=_auth_headers(owner.id),
        )
        assert task_response.status_code == 200
        assert task_response.json()["created"] is expected_created
        assert task_response.json()["task_id"] == "ai-beta-reader-task:candidate-1"

    chapters[0].content_version = 2
    await db.commit()
    reports_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports",
        headers=_auth_headers(owner.id),
    )
    assert reports_response.status_code == 200
    assert reports_response.json()["reports"][0]["is_stale"] is True
    await db.refresh(book)
    board_items = book.writer_workspace["revision_board"]["items"]
    created_item = next(
        item for item in board_items if item["item_id"] == "ai-beta-reader:candidate-1"
    )
    assert created_item["finding_snapshot"]["source_label"] == "AI Beta Reader"


@pytest.mark.asyncio
async def test_ai_beta_reader_collaboration_permissions_and_chapter_scope(client, db, monkeypatch):
    owner = await _user(db, "collaboration-owner@lorevia.test")
    allowed = await _user(db, "allowed-editor@lorevia.test", tier="free")
    beta_reader = await _user(db, "human-beta@lorevia.test", tier="free")
    revoked = await _user(db, "revoked-editor@lorevia.test", tier="free")
    book, chapters = await _book_with_chapters(db, owner)
    allowed_report = _stored_report(chapters)
    restricted_report = copy.deepcopy(allowed_report)
    restricted_report.update(
        {
            "report_id": "report-2",
            "request_hash": "restricted-request",
            "source_fingerprint": build_chapter_source_fingerprint([chapters[1]]),
        }
    )
    restricted_report["coverage"].update(
        {
            "requested_chapters": [2],
            "analyzed_chapters": [2],
        }
    )
    restricted_report["revision_candidates"][0].update(
        {
            "id": "candidate-2",
            "chapter_number": 2,
            "evidence": [{"chapter_number": 2, "excerpt": "The second door opened."}],
        }
    )
    book.writer_workspace = {"ai_beta_reader": {"reports": [restricted_report, allowed_report]}}
    db.add_all(
        [
            BookCollaborator(
                book_id=book.id,
                invited_user_id=allowed.id,
                email=allowed.email,
                role="developmental_editor",
                invite_status="active",
                scope={"chapter_start": 1, "chapter_end": 1},
                permissions={"can_run_ai_scans": True, "can_edit_manuscript": True},
                scope_chapter_start=1,
                scope_chapter_end=1,
                permission_can_run_ai_scans=True,
                permission_can_edit_manuscript=True,
                permission_can_view_selected_chapters_only=True,
            ),
            BookCollaborator(
                book_id=book.id,
                invited_user_id=beta_reader.id,
                email=beta_reader.email,
                role="beta_reader",
                invite_status="active",
                permissions={"can_run_ai_scans": False},
                permission_can_run_ai_scans=False,
            ),
            BookCollaborator(
                book_id=book.id,
                invited_user_id=revoked.id,
                email=revoked.email,
                role="developmental_editor",
                invite_status="revoked",
                permissions={"can_run_ai_scans": True},
                permission_can_run_ai_scans=True,
            ),
        ]
    )
    await db.commit()

    async def allow_rate_limit(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.api.v1.routes.advisor.beta_reader.enforce_continuity_rate_limit",
        allow_rate_limit,
    )
    monkeypatch.setattr(
        "app.api.v1.routes.advisor.beta_reader.generate_beta_reader_report_task",
        SimpleNamespace(apply_async=lambda *args, **kwargs: None),
    )

    allowed_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader",
        headers=_auth_headers(allowed.id),
        json={"scope": "chapter", "chapter_number": 1, "checks": ["repetition"]},
    )
    assert allowed_response.status_code == 200
    assert allowed_response.json()["cached"] is True

    restricted_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader",
        headers=_auth_headers(allowed.id),
        json={"scope": "full_book", "checks": ["repetition"]},
    )
    assert restricted_response.status_code == 403

    unscoped_passage_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader",
        headers=_auth_headers(allowed.id),
        json={"scope": "passage", "text": "A passage inside an unknown chapter."},
    )
    assert unscoped_passage_response.status_code == 403

    reports_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports",
        headers=_auth_headers(allowed.id),
    )
    assert reports_response.status_code == 200
    assert [item["report_id"] for item in reports_response.json()["reports"]] == ["report-1"]

    allowed_task_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports/report-1/revision-candidates/candidate-1",
        headers=_auth_headers(allowed.id),
    )
    assert allowed_task_response.status_code == 200

    restricted_task_response = await client.post(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports/report-2/revision-candidates/candidate-2",
        headers=_auth_headers(allowed.id),
    )
    assert restricted_task_response.status_code == 403

    beta_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports",
        headers=_auth_headers(beta_reader.id),
    )
    assert beta_response.status_code == 403

    revoked_response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/beta-reader/reports",
        headers=_auth_headers(revoked.id),
    )
    assert revoked_response.status_code == 404
