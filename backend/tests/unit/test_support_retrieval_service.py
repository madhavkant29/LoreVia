import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.support import SupportRecentMessage, SupportUiContext
from app.services import support_retrieval_service
from app.services.support_retrieval_service import (
    answer_support_question_ai,
    answer_support_question,
    load_support_corpus,
    rank_support_articles,
)


def test_support_corpus_loads_versioned_articles():
    version, articles = load_support_corpus()

    assert version == "2026-09-01"
    assert articles
    assert all(article.slug for article in articles)


def test_support_retrieval_ranks_route_and_error_context():
    ranked = rank_support_articles(
        "My chapter would not save and I saw a conflict",
        SupportUiContext(
            route="/book-1/manuscript",
            tool_id="book.manuscript",
            workspace_shell="author",
            error_code="version_conflict",
        ),
    )

    assert ranked[0][0].slug == "save-and-recover-a-chapter"


def test_support_answer_cites_sources_for_grounded_question():
    answer = answer_support_question(
        "Where is the Reading Writing workspace switch?",
        SupportUiContext(route="/book-1", workspace_shell="reader"),
    )

    assert not answer.declined
    assert answer.sources
    assert "workspace" in answer.answer.lower()


def test_support_answer_links_character_voice_questions_to_voice_area():
    book_id = uuid.uuid4()
    answer = answer_support_question(
        "How do I access character voice area?",
        SupportUiContext(route=f"/{book_id}", workspace_shell="author", book_id=book_id),
    )

    assert not answer.declined
    assert answer.actions[0].label == "Open Voice Consistency"
    assert answer.actions[0].href == f"/{book_id}/voice"


def test_support_answer_declines_low_confidence_question():
    answer = answer_support_question(
        "Which printer should I buy for watercolor paper?",
        SupportUiContext(route="/unrelated"),
    )

    assert answer.declined
    assert not answer.sources


@pytest.mark.asyncio
async def test_support_ai_uses_tracked_interactive_llm_call(monkeypatch):
    captured = {}

    async def tracked_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Open Voice Consistency from the Writing workspace for character voice review."
                    )
                )
            ]
        )

    monkeypatch.setattr(support_retrieval_service.settings, "SUPPORT_ASSISTANT_ENABLED", True)
    monkeypatch.setattr(support_retrieval_service.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(support_retrieval_service.settings, "OPENAI_INTEL_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(
        support_retrieval_service,
        "get_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace())),
    )
    monkeypatch.setattr(
        support_retrieval_service,
        "create_tracked_chat_completion",
        tracked_completion,
    )
    user = SimpleNamespace(id=uuid.uuid4())
    book_id = uuid.uuid4()

    answer = await answer_support_question_ai(
        SimpleNamespace(),
        message="How do I access character voice area?",
        context=SupportUiContext(route=f"/{book_id}", workspace_shell="author", book_id=book_id),
        current_user=user,
    )

    assert answer.answer.startswith("Open Voice Consistency")
    assert captured["feature"] == "support_assistant"
    assert captured["user_id"] == user.id
    assert captured["book_id"] == book_id
    assert captured["budget_class"] == "interactive"
    assert captured["metadata"]["budget_class"] == "interactive"
    assert captured["max_tokens"] == 220
    assert "Support guide excerpts" in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_support_ai_compacts_default_reply_and_uses_recent_context(monkeypatch):
    captured = {}

    async def tracked_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            "Open the Voice Consistency workspace from your project.\n"
                            "1. Open the project.\n"
                            "2. Choose Writing.\n"
                            "3. Select Voice Consistency.\n"
                            "4. Choose a character.\n"
                            "5. Run another review.\n\n"
                            "This extra paragraph should not be included."
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(support_retrieval_service.settings, "SUPPORT_ASSISTANT_ENABLED", True)
    monkeypatch.setattr(support_retrieval_service.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        support_retrieval_service,
        "get_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace())),
    )
    monkeypatch.setattr(
        support_retrieval_service,
        "create_tracked_chat_completion",
        tracked_completion,
    )
    book_id = uuid.uuid4()

    answer = await answer_support_question_ai(
        SimpleNamespace(),
        message="Where is it?",
        context=SupportUiContext(route=f"/{book_id}", workspace_shell="author", book_id=book_id),
        current_user=SimpleNamespace(id=uuid.uuid4()),
        recent_messages=[
            SupportRecentMessage(role="user", content="How do I access character voice area?"),
            SupportRecentMessage(role="assistant", content="Use Voice Consistency."),
        ],
    )

    assert "4. Choose a character." in answer.answer
    assert "5. Run another review." not in answer.answer
    assert "extra paragraph" not in answer.answer
    assert "character voice area" in captured["messages"][1]["content"]
    assert answer.actions[0].href == f"/{book_id}/voice"


@pytest.mark.asyncio
async def test_support_ai_still_charges_unrelated_questions_before_declining(monkeypatch):
    calls = 0

    async def tracked_completion(**_kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="I cannot verify that from LoreVia's support guides."))]
        )

    monkeypatch.setattr(support_retrieval_service.settings, "SUPPORT_ASSISTANT_ENABLED", True)
    monkeypatch.setattr(support_retrieval_service.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        support_retrieval_service,
        "get_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace())),
    )
    monkeypatch.setattr(
        support_retrieval_service,
        "create_tracked_chat_completion",
        tracked_completion,
    )

    answer = await answer_support_question_ai(
        SimpleNamespace(),
        message="Which printer should I buy for watercolor paper?",
        context=SupportUiContext(route="/unrelated"),
        current_user=SimpleNamespace(id=uuid.uuid4()),
    )

    assert calls == 1
    assert answer.declined
    assert not answer.sources
    assert not answer.actions


@pytest.mark.asyncio
async def test_support_ai_propagates_token_capacity_errors(monkeypatch):
    async def blocked_completion(**_kwargs):
        raise HTTPException(
            429,
            {
                "kind": "llm_tokens",
                "message": "Support Assistant token limit exceeded for the 5-hour window.",
            },
        )

    monkeypatch.setattr(support_retrieval_service.settings, "SUPPORT_ASSISTANT_ENABLED", True)
    monkeypatch.setattr(support_retrieval_service.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        support_retrieval_service,
        "get_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace())),
    )
    monkeypatch.setattr(
        support_retrieval_service,
        "create_tracked_chat_completion",
        blocked_completion,
    )

    with pytest.raises(HTTPException) as exc:
        await answer_support_question_ai(
            SimpleNamespace(),
            message="How do I access character voice area?",
            context=SupportUiContext(route=f"/{uuid.uuid4()}", workspace_shell="author"),
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )

    assert exc.value.status_code == 429
    assert exc.value.detail["kind"] == "llm_tokens"
