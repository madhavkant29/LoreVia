import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.deps.rate_limit import rate_limit_continuity_checker
from app.main import _lazy_api_app, app
from app.models.book import Book, Chapter
from app.models.character import Character, CharacterMention, CharacterState
from app.models.intelligence import BookChunk, ChapterSummary, ContinuityScan
from app.models.operations import AiQualityEvent
from app.services.continuity.scan_service import _claim_full_scan_authority
from app.utils.books.manuscript import persist_editor_chapter_content


@pytest.mark.asyncio
async def test_chapter_reports_distinguish_an_unreviewed_chapter_from_a_completed_editorial_pass(
    client, db, auth_headers
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Review coverage",
        format="manual",
        work_type="novel",
        s3_key="books/review-coverage.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    first = Chapter(
        book_id=book.id, number=1, title="Opening", s3_key="chapters/review-coverage/1.txt"
    )
    second = Chapter(
        book_id=book.id, number=2, title="Departure", s3_key="chapters/review-coverage/2.txt"
    )
    db.add_all([first, second])
    await db.flush()
    db.add(
        ChapterSummary(
            chapter_id=second.id,
            mode="editorial_note",
            content=json.dumps(
                [
                    {
                        "issue": "The departure has no decision beat.",
                        "evidence": "Mara left the harbor.",
                        "suggestion": "Show the choice that sends her away.",
                    }
                ]
            ),
        )
    )
    await db.commit()

    response = await client.get(f"/api/v1/books/{book.id}/chapter-reports", headers=auth_headers)

    assert response.status_code == 200
    assert [report["chapter_number"] for report in response.json()] == [2, 1]
    assert response.json()[0]["editorial_concerns"][0]["evidence"] == "Mara left the harbor."
    assert response.json()[1]["editorial_concerns"] is None
    newest = await client.get(
        f"/api/v1/books/{book.id}/chapter-reports?limit=1", headers=auth_headers
    )
    older = await client.get(
        f"/api/v1/books/{book.id}/chapter-reports?limit=1&before_chapter=2",
        headers=auth_headers,
    )
    assert [item["chapter_number"] for item in newest.json()] == [2]
    assert [item["chapter_number"] for item in older.json()] == [1]
    no_more = await client.get(
        f"/api/v1/books/{book.id}/chapter-reports?limit=1&before_chapter=1",
        headers=auth_headers,
    )
    invalid_cursor = await client.get(
        f"/api/v1/books/{book.id}/chapter-reports?before_chapter=0",
        headers=auth_headers,
    )
    assert no_more.json() == []
    assert invalid_cursor.status_code == 422


@pytest.mark.asyncio
async def test_chapter_reports_return_a_grounded_question_separately_from_a_problem(
    client, db, auth_headers
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Revision question coverage",
        format="manual",
        work_type="novel",
        s3_key="books/revision-question-coverage.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Departure",
        s3_key="chapters/revision-question-coverage/1.txt",
    )
    db.add(chapter)
    await db.flush()
    db.add(
        ChapterSummary(
            chapter_id=chapter.id,
            mode="editorial_note",
            content=json.dumps(
                {
                    "concerns": [],
                    "revision_question": {
                        "question": "What does Mara hope the departure will change?",
                        "evidence": "Mara left the harbor at dawn.",
                    },
                }
            ),
        )
    )
    await db.commit()

    response = await client.get(f"/api/v1/books/{book.id}/chapter-reports", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["editorial_concerns"] == []
    assert response.json()[0]["revision_question"] == {
        "question": "What does Mara hope the departure will change?",
        "evidence": "Mara left the harbor at dawn.",
    }


@pytest.mark.asyncio
async def test_continuity_scan_routes_enforce_the_continuity_quota(client, auth_headers):
    api_app = await _lazy_api_app.ensure_app()
    calls = 0

    async def reject_exhausted_quota() -> None:
        nonlocal calls
        calls += 1
        raise HTTPException(status_code=429, detail="Continuity checker daily limit reached")

    root_override = app.dependency_overrides.get(rate_limit_continuity_checker)
    api_override = api_app.dependency_overrides.get(rate_limit_continuity_checker)
    app.dependency_overrides[rate_limit_continuity_checker] = reject_exhausted_quota
    api_app.dependency_overrides[rate_limit_continuity_checker] = reject_exhausted_quota
    book_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    try:
        create_response = await client.post(
            f"/api/v1/books/{book_id}/continuity-scans",
            headers=auth_headers,
            json={"scope": "full_book", "chapter_numbers": []},
        )
        recheck_response = await client.post(
            f"/api/v1/books/{book_id}/continuity-findings/{finding_id}/recheck",
            headers=auth_headers,
        )
    finally:
        if root_override is None:
            app.dependency_overrides.pop(rate_limit_continuity_checker, None)
        else:
            app.dependency_overrides[rate_limit_continuity_checker] = root_override
        if api_override is None:
            api_app.dependency_overrides.pop(rate_limit_continuity_checker, None)
        else:
            api_app.dependency_overrides[rate_limit_continuity_checker] = api_override

    assert create_response.status_code == 429
    assert recheck_response.status_code == 429
    assert calls == 2


@pytest.mark.asyncio
async def test_continuity_scan_workflow_returns_cited_finding_and_records_decision(
    client,
    db,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="The Glass Harbor",
        format="manual",
        work_type="novel",
        s3_key="books/glass-harbor.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter_one = Chapter(
        book_id=book.id,
        number=1,
        title="Arrival",
        s3_key="chapters/1.txt",
        word_count=10,
        content_version=1,
        processed=True,
    )
    chapter_three = Chapter(
        book_id=book.id,
        number=3,
        title="Return",
        s3_key="chapters/3.txt",
        word_count=10,
        content_version=2,
        processed=True,
    )
    db.add_all([chapter_one, chapter_three])
    character = Character(
        book_id=book.id,
        name="Ilya",
        first_chapter=1,
        last_seen_chapter=3,
        mention_count=4,
        trait_state={"eyes": {"value": "green", "confidence": 0.95}},
    )
    db.add(character)
    await db.flush()
    db.add_all(
        [
            CharacterState(
                character_id=character.id,
                at_chapter=1,
                trait_snapshot={"eyes": {"value": "blue", "confidence": 0.96}},
                observed_trait_keys=["eyes"],
            ),
            CharacterState(
                character_id=character.id,
                at_chapter=3,
                trait_snapshot={"eyes": {"value": "green", "confidence": 0.96}},
                observed_trait_keys=["eyes"],
            ),
            CharacterMention(
                book_id=book.id,
                chapter_number=1,
                raw_name="Ilya",
                normalized_name="ilya",
                mention_text="Ilya's blue eyes caught the harbor light.",
                matched_character_id=character.id,
                resolver_status="resolved",
            ),
            CharacterMention(
                book_id=book.id,
                chapter_number=3,
                raw_name="Ilya",
                normalized_name="ilya",
                mention_text="Ilya's green eyes caught the harbor light.",
                matched_character_id=character.id,
                resolver_status="resolved",
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_one.id,
                chunk_index=0,
                text="Ilya's blue eyes caught the harbor light.",
                token_count=9,
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_three.id,
                chunk_index=0,
                text="Ilya's green eyes caught the harbor light.",
                token_count=9,
            ),
        ]
    )
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/continuity-scans",
        headers=auth_headers,
        json={"scope": "full_book", "chapter_numbers": []},
    )

    assert response.status_code == 200
    scan = response.json()
    assert scan["status"] == "ready"
    assert scan["continuity_status"] == "issues_found"
    assert scan["coverage"]["citation_coverage"] == 1.0
    assert scan["metrics"]["cost_usd_per_100k_words"] == 0.0
    assert scan["finding_count"] == 1
    finding = scan["findings"][0]
    assert finding["category"] == "character_state"
    assert [item["chapter_number"] for item in finding["evidence"]] == [1, 3]
    assert all(item["excerpt"] for item in finding["evidence"])

    decision_response = await client.patch(
        f"/api/v1/books/{book.id}/continuity-findings/{finding['id']}",
        headers=auth_headers,
        json={"decision": "intentional", "reason": "intentional"},
    )

    assert decision_response.status_code == 200
    assert decision_response.json()["status"] == "intentional"
    quality_event = (
        await db.execute(
            select(AiQualityEvent).where(
                AiQualityEvent.entity_type == "continuity_finding",
                AiQualityEvent.entity_id == finding["id"],
            )
        )
    ).scalar_one()
    assert quality_event.outcome == "intentional_change"

    facts_response = await client.get(
        f"/api/v1/books/{book.id}/canon/facts",
        headers=auth_headers,
    )
    assert facts_response.status_code == 200
    assert {item["display_value"] for item in facts_response.json()} >= {"blue", "green"}

    for _ in range(2):
        task_response = await client.patch(
            f"/api/v1/books/{book.id}/continuity-findings/{finding['id']}",
            headers=auth_headers,
            json={
                "decision": "accepted",
                "action": "added_to_revision_plan",
            },
        )
        assert task_response.status_code == 200
    await db.refresh(book)
    task_id = f"continuity-task:{finding['id']}"
    task_items = [item for item in book.writer_workspace["goal_calendar"] if item["id"] == task_id]
    assert len(task_items) == 1
    assert task_items[0]["title"] == finding["title"]
    assert task_items[0]["quota_value"] == 1
    assert task_items[0]["quota_unit"] == "tasks"
    assert task_items[0]["completed"] is False
    revision_item = next(
        item
        for item in book.writer_workspace["revision_board"]["items"]
        if item["item_id"] == finding["id"]
    )
    assert revision_item["status"] == "task_created"
    assert revision_item["task_id"] == task_id

    resolved_response = await client.patch(
        f"/api/v1/books/{book.id}/continuity-findings/{finding['id']}",
        headers=auth_headers,
        json={
            "decision": "resolved",
            "action": "manuscript_edit",
            "reason": "fixed",
        },
    )
    assert resolved_response.status_code == 200
    await db.refresh(book)
    resolved_task = next(
        item for item in book.writer_workspace["goal_calendar"] if item["id"] == task_id
    )
    assert resolved_task["completed"] is True
    resolved_revision_item = next(
        item
        for item in book.writer_workspace["revision_board"]["items"]
        if item["item_id"] == finding["id"]
    )
    assert resolved_revision_item["status"] == "fixed"
    assert resolved_revision_item["decision"] == "resolved"

    db.add(
        ContinuityScan(
            book_id=book.id,
            user_id=user_id,
            scope="full_book",
            status="failed",
            continuity_status="insufficient_evidence",
            detector_version="test-failure",
            created_at=datetime.now(UTC) + timedelta(seconds=1),
            completed_at=datetime.now(UTC) + timedelta(seconds=1),
            error_detail="temporary detector outage",
        )
    )
    await db.commit()
    findings_after_failure = await client.get(
        f"/api/v1/books/{book.id}/continuity-findings",
        headers=auth_headers,
    )
    assert findings_after_failure.status_code == 200
    assert finding["id"] in {item["id"] for item in findings_after_failure.json()}

    await persist_editor_chapter_content(
        db,
        book,
        chapter_number=3,
        title="Return",
        text="Ilya's amber eyes caught the harbor light.",
        html=None,
        content_version=3,
    )
    await db.commit()
    stale_response = await client.get(
        f"/api/v1/books/{book.id}/continuity-findings",
        headers=auth_headers,
    )
    stale_finding = next(item for item in stale_response.json() if item["id"] == finding["id"])
    assert stale_finding["is_stale"] is True
    assert stale_finding["decision"] == "resolved"
    stale_decision_response = await client.patch(
        f"/api/v1/books/{book.id}/continuity-findings/{finding['id']}",
        headers=auth_headers,
        json={"decision": "dismissed", "reason": "not_relevant"},
    )
    assert stale_decision_response.status_code == 409
    stale_scan_response = await client.get(
        f"/api/v1/books/{book.id}/continuity-scans/{scan['id']}",
        headers=auth_headers,
    )
    assert stale_scan_response.status_code == 200
    assert stale_scan_response.json()["continuity_status"] == "stale"

    current_facts_response = await client.get(
        f"/api/v1/books/{book.id}/canon/facts",
        headers=auth_headers,
    )
    current_fact_values = {item["display_value"] for item in current_facts_response.json()}
    assert "blue" in current_fact_values
    assert "green" not in current_fact_values


@pytest.mark.asyncio
async def test_targeted_continuity_scan_requires_chapters(client, db, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Targeted Scan",
        format="manual",
        s3_key="books/targeted.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/continuity-scans",
        headers=auth_headers,
        json={"scope": "targeted", "chapter_numbers": []},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_newer_successful_full_scan_becomes_authoritative_without_pending_gap(
    client,
    db,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Concurrent Scans",
        format="manual",
        work_type="novel",
        s3_key="books/concurrent-scans.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    created_at = datetime.now(UTC)
    older = ContinuityScan(
        book_id=book.id,
        user_id=user_id,
        scope="full_book",
        status="ready",
        continuity_status="clean",
        detector_version="test",
        created_at=created_at,
    )
    newer = ContinuityScan(
        book_id=book.id,
        user_id=user_id,
        scope="full_book",
        status="queued",
        continuity_status="insufficient_evidence",
        detector_version="test",
        created_at=created_at + timedelta(seconds=1),
    )
    db.add_all([older, newer])
    await db.commit()

    assert await _claim_full_scan_authority(db, scan=older, findings=[]) is True
    assert older.continuity_status == "clean"
    await db.commit()

    newer.status = "ready"
    newer.continuity_status = "clean"
    await db.commit()
    assert await _claim_full_scan_authority(db, scan=newer, findings=[]) is True
    await db.commit()
    await db.refresh(older)
    assert older.continuity_status == "stale"

    older.continuity_status = "clean"
    assert await _claim_full_scan_authority(db, scan=older, findings=[]) is False


@pytest.mark.asyncio
async def test_clean_scan_becomes_stale_after_a_covered_chapter_edit(
    client,
    db,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    book = Book(
        user_id=user_id,
        title="Clean Then Edited",
        format="manual",
        s3_key="books/clean-edited.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="One",
        s3_key="chapters/clean-1.txt",
        word_count=5,
        content_version=1,
        processed=True,
    )
    db.add(chapter)
    character = Character(
        book_id=book.id,
        name="Mira",
        first_chapter=1,
        last_seen_chapter=1,
        mention_count=2,
        trait_state={},
    )
    db.add(character)
    await db.flush()
    db.add_all(
        [
            CharacterMention(
                book_id=book.id,
                chapter_number=1,
                raw_name="Mira",
                normalized_name="mira",
                mention_text="Mira entered the gate.",
                matched_character_id=character.id,
                resolver_status="resolved",
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter.id,
                chunk_index=0,
                text="Mira entered the gate.",
                token_count=5,
            ),
        ]
    )
    await db.commit()

    scan_response = await client.post(
        f"/api/v1/books/{book.id}/continuity-scans",
        headers=auth_headers,
        json={"scope": "full_book", "chapter_numbers": []},
    )
    assert scan_response.status_code == 200
    assert scan_response.json()["continuity_status"] == "clean"

    await persist_editor_chapter_content(
        db,
        book,
        chapter_number=1,
        title="One",
        text="Mira refused to enter the gate.",
        html=None,
        content_version=2,
    )
    await db.commit()

    stale_response = await client.get(
        f"/api/v1/books/{book.id}/continuity-scans/{scan_response.json()['id']}",
        headers=auth_headers,
    )
    assert stale_response.status_code == 200
    assert stale_response.json()["continuity_status"] == "stale"


@pytest.mark.asyncio
async def test_structured_summary_facts_feed_knowledge_continuity_detector(
    client,
    db,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Knowledge Order",
        format="manual",
        s3_key="books/knowledge-order.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter_two = Chapter(
        book_id=book.id,
        number=2,
        title="The Gate",
        s3_key="chapters/knowledge-2.txt",
        word_count=8,
        content_version=1,
        processed=True,
    )
    chapter_five = Chapter(
        book_id=book.id,
        number=5,
        title="The Lesson",
        s3_key="chapters/knowledge-5.txt",
        word_count=9,
        content_version=1,
        processed=True,
    )
    db.add_all([chapter_two, chapter_five])
    character = Character(
        book_id=book.id,
        name="Nora",
        first_chapter=2,
        last_seen_chapter=5,
        mention_count=4,
        trait_state={},
    )
    db.add(character)
    await db.flush()
    db.add_all(
        [
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_two.id,
                chunk_index=0,
                text="Nora cuts her royal palm and opens the moon gate.",
                token_count=10,
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter_five.id,
                chunk_index=0,
                text="The archivist tells Nora that royal blood opens the moon gate.",
                token_count=11,
            ),
            ChapterSummary(
                chapter_id=chapter_two.id,
                mode="detailed",
                content="Nora opens the gate.",
                key_events=[
                    {
                        "event_title": "Gate opens",
                        "description": "Nora opens the moon gate.",
                        "continuity_facts": [
                            {
                                "subject": "Nora",
                                "predicate": "knowledge.used",
                                "value": "royal blood opens the moon gate",
                                "fact_key": "royal blood opens moon gate",
                                "evidence": ("Nora cuts her royal palm and opens the moon gate."),
                            }
                        ],
                    }
                ],
            ),
            ChapterSummary(
                chapter_id=chapter_five.id,
                mode="detailed",
                content="Nora learns the rule.",
                key_events=[
                    {
                        "event_title": "Rule explained",
                        "description": "The archivist explains the moon gate.",
                        "continuity_facts": [
                            {
                                "subject": "Nora",
                                "predicate": "knowledge.acquired",
                                "value": "the moon gate opens with royal blood",
                                "fact_key": "royal blood opens moon gate",
                                "evidence": (
                                    "The archivist tells Nora that royal blood opens the moon gate."
                                ),
                            }
                        ],
                    }
                ],
            ),
        ]
    )
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/continuity-scans",
        headers=auth_headers,
        json={"scope": "full_book", "chapter_numbers": []},
    )

    assert response.status_code == 200
    knowledge_findings = [
        finding for finding in response.json()["findings"] if finding["category"] == "knowledge"
    ]
    assert len(knowledge_findings) == 1
    assert [evidence["chapter_number"] for evidence in knowledge_findings[0]["evidence"]] == [
        2,
        5,
    ]


@pytest.mark.asyncio
async def test_targeted_scan_waits_for_current_extraction_evidence(
    client,
    db,
    auth_headers,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Pending Extraction",
        format="manual",
        s3_key="books/pending-extraction.txt",
        status="processing",
        mode="author",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="Edited",
        s3_key="chapters/pending-1.txt",
        word_count=6,
        content_version=2,
        processed=False,
    )
    db.add(chapter)
    character = Character(
        book_id=book.id,
        name="Mira",
        first_chapter=1,
        last_seen_chapter=1,
        mention_count=2,
        trait_state={"eyes": {"value": "green", "confidence": 0.9}},
    )
    db.add(character)
    await db.flush()
    db.add_all(
        [
            CharacterState(
                character_id=character.id,
                at_chapter=1,
                trait_snapshot={"eyes": {"value": "green", "confidence": 0.9}},
                observed_trait_keys=["eyes"],
            ),
            BookChunk(
                book_id=book.id,
                chapter_id=chapter.id,
                chunk_index=0,
                text="Old extracted evidence says Mira has green eyes.",
                token_count=8,
            ),
        ]
    )
    await db.commit()

    response = await client.post(
        f"/api/v1/books/{book.id}/continuity-scans",
        headers=auth_headers,
        json={"scope": "targeted", "chapter_numbers": [1]},
    )

    assert response.status_code == 200
    scan = response.json()
    assert scan["status"] == "ready"
    assert scan["continuity_status"] == "insufficient_evidence"
    assert scan["coverage"]["chapters_analyzed"] == 0
    assert scan["coverage"]["missing_chapter_numbers"] == [1]
    assert scan["coverage"]["observation_count"] == 0


@pytest.mark.asyncio
async def test_continuity_scan_failure_is_persisted(
    client,
    db,
    auth_headers,
    monkeypatch,
):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    book = Book(
        user_id=uuid.UUID(me.json()["id"]),
        title="Failed Scan",
        format="manual",
        s3_key="books/failed-scan.txt",
        status="ready",
        mode="author",
    )
    db.add(book)
    await db.flush()
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="One",
            s3_key="chapters/failed-1.txt",
            word_count=4,
            content_version=1,
            processed=True,
        )
    )
    await db.commit()
    book_id = book.id

    async def fail_observation_collection(*_args, **_kwargs):
        raise RuntimeError("detector fixture failed")

    monkeypatch.setattr(
        "app.services.continuity.scan_service.collect_observations",
        fail_observation_collection,
    )

    response = await client.post(
        f"/api/v1/books/{book_id}/continuity-scans",
        headers=auth_headers,
        json={"scope": "full_book", "chapter_numbers": []},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["continuity_status"] == "insufficient_evidence"
    assert "detector fixture failed" in response.json()["error_detail"]

    findings_response = await client.get(
        f"/api/v1/books/{book_id}/continuity-findings",
        headers=auth_headers,
    )
    assert findings_response.status_code == 200
    assert findings_response.json() == []
