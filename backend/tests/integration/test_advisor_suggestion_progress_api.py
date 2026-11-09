"""HTTP contract for long-running Recommended Checks progress."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.book import Book
from app.models.intelligence import AdvisorSuggestionJob


@pytest.mark.asyncio
async def test_running_advisor_scan_exposes_group_progress_without_partial_report(
    client, db, auth_headers
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="The Glass Crossing",
        format="manual",
        work_type="novel",
        s3_key="books/glass-crossing.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    job = AdvisorSuggestionJob(
        user_id=user_id,
        book_id=book.id,
        status="running",
        result_json={"_execution_id": "worker-private", "_progress": {"completed": 2, "total": 21}},
    )
    db.add(job)
    await db.commit()

    response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/suggestions/jobs/{job.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": str(job.id),
        "status": "running",
        "result": None,
        "progress": {"completed": 2, "total": 21},
        "error": None,
    }
    assert "worker-private" not in response.text


@pytest.mark.asyncio
async def test_hard_killed_advisor_scan_status_unlocks_a_new_scan(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="The Locked Archive",
        format="manual",
        work_type="novel",
        s3_key="books/locked-archive.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    job = AdvisorSuggestionJob(
        user_id=user_id,
        book_id=book.id,
        status="running",
        result_json={
            "_execution_id": "killed-worker",
            "_started_at": (datetime.now(UTC) - timedelta(minutes=23)).isoformat(),
            "_progress": {"completed": 2, "total": 21},
        },
    )
    db.add(job)
    await db.commit()

    response = await client.get(
        f"/api/v1/intelligence/{book.id}/advisor/suggestions/jobs/{job.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert (
        response.json()["error"]
        == "The scan stopped before it finished. Refresh checks to try again."
    )
    assert response.json()["progress"] is None
