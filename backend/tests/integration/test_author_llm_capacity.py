from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.user import LlmUsageEvent, User
from app.utils.llm_usage_utils import assert_manual_reprocess_token_capacity


async def _author(db, label: str) -> User:
    user = User(
        email=f"capacity-{label}-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"capacity{label}{uuid.uuid4().hex[:8]}",
        password_hash="fake",
        tier="author",
    )
    db.add(user)
    await db.commit()
    return user


async def _run_mocked_processing_calls(
    db,
    *,
    user: User,
    total_tokens: int,
    call_count: int,
) -> int:
    base, remainder = divmod(total_tokens, call_count)
    for index in range(call_count):
        call_tokens = base + (1 if index < remainder else 0)
        await assert_manual_reprocess_token_capacity(
            db,
            user,
            estimated_tokens=call_tokens,
        )
        db.add(
            LlmUsageEvent(
                user_id=user.id,
                provider="openai",
                model="gpt-4o-mini",
                operation="chat",
                feature=f"mocked_processing_call_{index}",
                status="succeeded",
                total_tokens=call_tokens,
                metadata_json={"budget_class": "processing"},
            )
        )
        await db.commit()
    return int(
        await db.scalar(
            select(func.sum(LlmUsageEvent.total_tokens)).where(
                LlmUsageEvent.user_id == user.id,
            )
        )
        or 0
    )


@pytest.mark.parametrize("word_count", [40_000, 100_000])
async def test_author_manuscript_processing_exceeds_old_window_but_fits_new_cap(db, word_count):
    user = await _author(db, str(word_count))
    estimated_processing_tokens = word_count * 8

    consumed_tokens = await _run_mocked_processing_calls(
        db,
        user=user,
        total_tokens=estimated_processing_tokens,
        call_count=20,
    )
    caps = await assert_manual_reprocess_token_capacity(db, user, estimated_tokens=1)

    assert estimated_processing_tokens > 150_000
    assert consumed_tokens == estimated_processing_tokens
    assert caps.five_hour == 12_000_000
    assert caps.weekly == 12_000_000
    assert caps.monthly == 12_000_000


async def test_mocked_one_million_word_run_fits_twelve_million_token_safety_cap(db):
    user = await _author(db, "million")

    consumed_tokens = await _run_mocked_processing_calls(
        db,
        user=user,
        total_tokens=8_000_000,
        call_count=100,
    )
    caps = await assert_manual_reprocess_token_capacity(db, user, estimated_tokens=1)

    assert consumed_tokens == 8_000_000
    assert caps.five_hour == settings.AUTHOR_LLM_TOKENS_5H == 12_000_000
