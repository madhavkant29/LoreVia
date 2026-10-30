import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import Request
from openai import APIConnectionError

from app.services import advisor_proactive_scan_service


@pytest.mark.asyncio
async def test_bounded_scan_groups_covers_all_items_with_two_parallel_calls():
    active = 0
    peak = 0
    started = asyncio.Event()
    release = asyncio.Event()
    progress: list[int] = []

    async def scan_one(index, group):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if peak == 2:
            started.set()
        try:
            await release.wait()
            return group * 2
        finally:
            active -= 1

    async def on_complete(index, _result):
        progress.append(index)

    task = asyncio.create_task(
        advisor_proactive_scan_service.run_bounded_scan_groups(
            [(index, index) for index in range(5)],
            scan_one=scan_one,
            on_complete=on_complete,
            concurrency=2,
        )
    )
    await asyncio.wait_for(started.wait(), timeout=2)
    assert peak == 2
    release.set()
    result = await asyncio.wait_for(task, timeout=2)

    assert result == [(index, index * 2) for index in range(5)]
    assert sorted(progress) == list(range(5))
    assert active == 0


@pytest.mark.asyncio
async def test_bounded_scan_groups_cancels_peers_after_unexpected_error():
    peer_cancelled = asyncio.Event()

    async def scan_one(index, _group):
        if index == 0:
            await asyncio.sleep(0)
            raise RuntimeError("unexpected_scan_error")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            peer_cancelled.set()
            raise

    async def on_complete(_index, _result):
        raise AssertionError("No group should finish successfully")

    with pytest.raises(RuntimeError, match="unexpected_scan_error"):
        await advisor_proactive_scan_service.run_bounded_scan_groups(
            [(0, "first"), (1, "second")],
            scan_one=scan_one,
            on_complete=on_complete,
        )
    assert peer_cancelled.is_set()


def test_bounded_scan_groups_rejects_nonpositive_concurrency():
    async def scan_one(_index, _group):
        return None

    async def on_complete(_index, _result):
        return None

    with pytest.raises(ValueError, match="invalid_advisor_scan_concurrency"):
        asyncio.run(
            advisor_proactive_scan_service.run_bounded_scan_groups(
                [], scan_one=scan_one, on_complete=on_complete, concurrency=0
            )
        )


@pytest.mark.asyncio
async def test_proactive_scan_uses_group_sized_output_budget(monkeypatch):
    budgets: list[int] = []

    async def fake_completion(**kwargs):
        budgets.append(kwargs["max_tokens"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content='{"findings":[],"overall_note":"No supported checks."}'
                    ),
                )
            ]
        )

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )

    await advisor_proactive_scan_service.request_proactive_scan_result(
        client=object(),
        db=object(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        model="test-model",
        messages=[],
        source_blocks=[f"Evidence {index}" for index in range(20)],
    )

    assert budgets == [6144]


@pytest.mark.asyncio
async def test_proactive_scan_retries_short_slot_contention_before_scanning(monkeypatch):
    calls = 0
    delays = []

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(
                429, "LLM capacity is temporarily busy.", headers={"Retry-After": "5"}
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content='{"findings":[],"overall_note":"No supported checks."}'
                    ),
                )
            ]
        )

    async def record_delay(seconds):
        delays.append(seconds)

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )
    monkeypatch.setattr(advisor_proactive_scan_service.asyncio, "sleep", record_delay)

    result = await advisor_proactive_scan_service.request_proactive_scan_result(
        client=object(),
        db=object(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        model="test-model",
        messages=[],
        source_blocks=[],
    )

    assert result["findings"] == []
    assert calls == 2
    assert delays == [5]


@pytest.mark.asyncio
async def test_proactive_scan_monthly_budget_denial_is_not_retried(monkeypatch):
    calls = 0

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        raise HTTPException(429, {"kind": "llm_budget", "message": "Monthly AI capacity reached."})

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )

    with pytest.raises(HTTPException) as raised:
        await advisor_proactive_scan_service.request_proactive_scan_result(
            client=object(),
            db=object(),
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            model="test-model",
            messages=[],
            source_blocks=[],
        )

    assert raised.value.detail["kind"] == "llm_budget"
    assert calls == 1


@pytest.mark.asyncio
async def test_proactive_scan_retries_connection_failure_and_preserves_valid_findings(monkeypatch):
    calls = 0

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise APIConnectionError(
                request=Request("POST", "https://api.openai.com/v1/chat/completions")
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=(
                            '{"findings":[{"title":"Changed route","description":"The route changed",'
                            '"evidence_excerpt":"The bridge remained open.","chapter_ref":2,'
                            '"action_label":"Check route","ask_prompt":"Which route was used?"}],'
                            '"overall_note":"One check."}'
                        )
                    ),
                )
            ]
        )

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )
    monkeypatch.setattr(advisor_proactive_scan_service.asyncio, "sleep", no_delay)

    result = await advisor_proactive_scan_service.request_proactive_scan_result(
        client=object(),
        db=object(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        model="test-model",
        messages=[{"role": "user", "content": "Review this evidence."}],
        source_blocks=["Chapter 2: The bridge remained open."],
    )

    assert calls == 2
    assert [finding["title"] for finding in result["findings"]] == ["Changed route"]


@pytest.mark.asyncio
async def test_proactive_scan_rejects_valid_json_marked_truncated_by_provider(monkeypatch):
    calls = 0

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length",
                    message=SimpleNamespace(content='{"findings":[],"overall_note":"No issues."}'),
                )
            ]
        )

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )
    monkeypatch.setattr(advisor_proactive_scan_service.asyncio, "sleep", no_delay)

    with pytest.raises(ValueError, match="llm_response_incomplete"):
        await advisor_proactive_scan_service.request_proactive_scan_result(
            client=object(),
            db=object(),
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            model="test-model",
            messages=[],
            source_blocks=[],
        )

    assert calls == 2


@pytest.mark.asyncio
async def test_proactive_scan_retries_malformed_response_but_does_not_cache_empty_success(
    monkeypatch,
):
    calls = 0

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="not json"))
            ]
        )

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )
    monkeypatch.setattr(advisor_proactive_scan_service.asyncio, "sleep", no_delay)

    with pytest.raises(ValueError, match="advisor_scan_invalid_json"):
        await advisor_proactive_scan_service.request_proactive_scan_result(
            client=object(),
            db=object(),
            user_id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            model="test-model",
            messages=[],
            source_blocks=[],
        )

    assert calls == 2


@pytest.mark.asyncio
async def test_proactive_scan_retries_then_returns_uncached_partial_verified_findings(monkeypatch):
    calls = 0
    mixed = (
        '{"findings":['
        '{"title":"Check route","description":"The route changed.",'
        '"evidence_excerpt":"The bridge remained open.","chapter_ref":2,'
        '"action_label":"Trace route","ask_prompt":"Where is the bridge?"},'
        '{"title":"Invented route","description":"An unsupported claim.",'
        '"evidence_excerpt":"A phantom road.","chapter_ref":2,'
        '"action_label":"Trace route","ask_prompt":"Where is the road?"}'
        '],"overall_note":"Two checks."}'
    )

    async def fake_completion(**_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=mixed))]
        )

    async def no_delay(_seconds):
        return None

    monkeypatch.setattr(
        advisor_proactive_scan_service, "create_tracked_chat_completion", fake_completion
    )
    monkeypatch.setattr(advisor_proactive_scan_service.asyncio, "sleep", no_delay)

    result = await advisor_proactive_scan_service.request_proactive_scan_result(
        client=object(),
        db=object(),
        user_id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        model="test-model",
        messages=[],
        source_blocks=["Chapter 2: The bridge remained open."],
    )

    assert calls == 2
    assert result["partial"] is True
    assert [finding["title"] for finding in result["findings"]] == ["Check route"]
