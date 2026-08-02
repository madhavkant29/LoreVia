import sys
import uuid
from types import SimpleNamespace

import pytest

from app.core import llm
from app.engine.character import entity_filters
from app.engine.character import extractor as character_extractor
from app.engine.embeddings import embedder
from app.engine.world import extractor as world_extractor
from app.services import email_service
from app.services.character_identity.repair import CharacterIdentityRepairResult
from app.utils import reader_utils, social_utils


@pytest.mark.asyncio
async def test_embed_batch_splits_provider_requests_and_restores_order(monkeypatch):
    closed: list[bool] = []
    calls: list[list[str]] = []

    class Client:
        async def close(self):
            closed.append(True)

    async def create_embedding(**kwargs):
        calls.append(list(kwargs["input"]))
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[float(index), float(len(text))])
                for index, text in reversed(list(enumerate(kwargs["input"])))
            ]
        )

    monkeypatch.setattr(embedder, "get_client", lambda: Client())
    monkeypatch.setattr(embedder, "count_tokens", lambda text: 6)
    monkeypatch.setattr(embedder, "MAX_EMBED_BATCH_TOKENS", 10)
    monkeypatch.setattr(embedder, "create_tracked_embedding", create_embedding)

    vectors = await embedder.embed_batch(["first", "second", "third"])
    assert calls == [["first"], ["second"], ["third"]]
    assert vectors == [[0.0, 5.0], [0.0, 6.0], [0.0, 5.0]]
    assert closed == [True]

    closed.clear()
    assert await embedder.embed_batch([]) == []
    assert closed == [True]


@pytest.mark.asyncio
async def test_gemini_completion_handles_text_candidates_and_json_fallback(monkeypatch):
    class Config:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_types = SimpleNamespace(GenerateContentConfig=Config)
    monkeypatch.setitem(sys.modules, "google.generativeai", SimpleNamespace(types=fake_types))
    monkeypatch.setattr(
        llm, "_get_gemini_client", lambda: SimpleNamespace(models=SimpleNamespace())
    )

    async def direct_text(fn):
        return SimpleNamespace(text="  direct answer  ", candidates=[])

    monkeypatch.setattr(llm, "_run_blocking", direct_text)
    assert (
        await llm._complete_with_gemini(
            system="system",
            user="user",
            model="gemini",
            temperature=0.2,
            max_tokens=40,
            want_json=False,
        )
        == "direct answer"
    )

    async def candidate_text(fn):
        part = SimpleNamespace(text="candidate answer")
        return SimpleNamespace(
            text="", candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))]
        )

    monkeypatch.setattr(llm, "_run_blocking", candidate_text)
    assert (
        await llm._complete_with_gemini(
            system="system",
            user="user",
            model="gemini",
            temperature=0.2,
            max_tokens=40,
            want_json=False,
        )
        == "candidate answer"
    )

    async def empty(fn):
        return SimpleNamespace(text="", candidates=[])

    monkeypatch.setattr(llm, "_run_blocking", empty)
    assert (
        await llm._complete_with_gemini(
            system="system",
            user="user",
            model="gemini",
            temperature=0.2,
            max_tokens=40,
            want_json=True,
        )
        == "{}"
    )


def test_character_identity_repair_payload_populates_compatibility_fields():
    result = CharacterIdentityRepairResult(
        book_id=str(uuid.uuid4()),
        dry_run=True,
        planned_merges=[("primary", "secondary")],
        planned_suppressions=["noise-id"],
    )
    payload = result.to_payload()
    assert payload["merged_pairs"] == [("primary", "secondary")]
    assert payload["planned_demotions"] == ["noise-id"]
    assert payload["allow_merge_safe_pairs"] is True
    assert payload["unresolved_relationship_deltas"] == {}


def test_known_character_prompt_block_formats_roster_and_skips_invalid_rows():
    payload = character_extractor._known_character_prompt_block(
        [
            "invalid",
            {"name": ""},
            {
                "name": " Mara Vale ",
                "aliases": ["Mara", ""],
                "role": " protagonist ",
                "summary": "Defends the northern gate.",
                "is_manual": True,
            },
        ]
    )
    assert "Mara Vale [manual anchor]" in payload
    assert "aliases: Mara" in payload
    assert "role: protagonist" in payload
    assert character_extractor._known_character_prompt_block([]) == ""


def test_contextual_entity_label_scores_exact_prefix_and_overlap(monkeypatch):
    entities = [
        SimpleNamespace(text="Mara", label_="PERSON"),
        SimpleNamespace(text="Mara Vale", label_="ORG"),
        SimpleNamespace(text="Vale Guard", label_="GROUP"),
    ]
    monkeypatch.setattr(
        entity_filters, "_get_nlp", lambda: lambda _text: SimpleNamespace(ents=entities)
    )
    assert entity_filters.contextual_ner_entity_label("Mara Vale arrived", "Mara Vale") == "ORG"
    assert entity_filters.contextual_ner_entity_label("Mara arrived", "Mara V") == "PERSON"
    assert entity_filters.contextual_ner_entity_label("", "Mara") is None


def test_world_context_pos_label_uses_offsets_span_and_text_fallback(monkeypatch):
    class Doc(list):
        def char_span(self, start, end):
            return [SimpleNamespace(pos_="PROPN")]

    tokens = Doc(
        [
            SimpleNamespace(text="Northreach", idx=0, pos_="PROPN"),
            SimpleNamespace(text="stands", idx=11, pos_="VERB"),
        ]
    )
    monkeypatch.setattr(world_extractor, "_get_pos_nlp", lambda: lambda _text: tokens)
    assert (
        world_extractor._context_pos_label(
            "Northreach",
            "Northreach stands",
            provenance={"sentence_start": 10, "match_start": 10, "match_end": 20},
        )
        == "PROPN"
    )
    assert world_extractor._context_pos_label("stands", "Northreach stands") == "VERB"
    monkeypatch.setattr(world_extractor, "_get_pos_nlp", lambda: None)
    assert world_extractor._context_pos_label("Northreach", "Northreach stands") is None


@pytest.mark.asyncio
async def test_promotional_context_covers_transactional_missing_address_user_and_allowed(
    monkeypatch,
):
    assert await email_service._resolve_promotional_context(
        email="reader@example.com",
        category=email_service.EMAIL_CATEGORY_TRANSACTIONAL,
    ) == {"allowed": True}

    monkeypatch.setattr(email_service.settings, "BUSINESS_MAILING_ADDRESS", "", raising=False)
    assert (
        await email_service._resolve_promotional_context(
            email="reader@example.com",
            category="product_updates",
        )
        is None
    )

    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Session:
        def __init__(self, user):
            self.user = user

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def execute(self, _statement):
            return Result(self.user)

        async def commit(self):
            return None

        async def refresh(self, _value):
            return None

    user = SimpleNamespace(id=uuid.uuid4())
    preference = SimpleNamespace()

    async def preference_for(_db, **_kwargs):
        return preference

    async def links(_user):
        return SimpleNamespace(
            unsubscribe_url="https://example.com/unsubscribe",
            preferences_url="https://example.com/preferences",
        )

    monkeypatch.setattr(
        email_service.settings, "BUSINESS_MAILING_ADDRESS", "123 Main Street", raising=False
    )
    monkeypatch.setattr(email_service, "AsyncSessionLocal", lambda: Session(user))
    monkeypatch.setattr(email_service, "get_or_create_email_preference", preference_for)
    monkeypatch.setattr(email_service, "can_send_email", lambda *_args: True)
    monkeypatch.setattr(email_service, "build_email_preference_links", links)
    context = await email_service._resolve_promotional_context(
        email=" Reader@Example.com ",
        category="product_updates",
    )
    assert context["unsubscribe_url"].endswith("/unsubscribe")

    monkeypatch.setattr(email_service, "AsyncSessionLocal", lambda: Session(None))
    assert (
        await email_service._resolve_promotional_context(
            email="missing@example.com",
            category="product_updates",
        )
        is None
    )


@pytest.mark.asyncio
async def test_update_plot_thread_note_sanitizes_and_resolves(monkeypatch):
    thread = SimpleNamespace(
        id=uuid.uuid4(),
        book_id=uuid.uuid4(),
        title="Gate mystery",
        status="developing",
        note=None,
        edited_by_author=False,
        resolved_at=None,
        last_mentioned_at=8,
        introduced_at=2,
        importance=7,
        description=None,
        thread_type="mystery",
        mention_count=2,
        character_ids=[],
    )

    class Result:
        def scalar_one_or_none(self):
            return thread

    class Db:
        async def execute(self, _statement):
            return Result()

        async def commit(self):
            return None

        async def refresh(self, _value):
            return None

        async def scalar(self, _statement):
            return 10

    async def tags(*_args, **_kwargs):
        return []

    monkeypatch.setattr(reader_utils, "get_custom_tags_for_entity", tags)
    payload = await reader_utils.update_plot_thread_note(
        Db(),
        thread.book_id,
        thread.id,
        "  <b>Resolve</b> the gate  ",
        status="resolved",
    )
    assert thread.note == "Resolve the gate"
    assert thread.resolved_at == 8
    assert thread.edited_by_author is True
    assert payload["status"] == "resolved"


@pytest.mark.asyncio
async def test_list_relationships_groups_friends_and_pending_requests():
    current = SimpleNamespace(id=uuid.uuid4(), username="current")
    friend = SimpleNamespace(id=uuid.uuid4(), username="friend")
    incoming_user = SimpleNamespace(id=uuid.uuid4(), username="incoming")
    now = __import__("datetime").datetime.now(__import__("datetime").UTC)
    accepted = SimpleNamespace(
        id=uuid.uuid4(),
        requester_user_id=current.id,
        addressee_user_id=friend.id,
        status="accepted",
        created_at=now,
        updated_at=now,
        responded_at=now,
    )
    incoming = SimpleNamespace(
        id=uuid.uuid4(),
        requester_user_id=incoming_user.id,
        addressee_user_id=current.id,
        status="pending",
        created_at=now,
        updated_at=now,
        responded_at=None,
    )
    outgoing = SimpleNamespace(
        id=uuid.uuid4(),
        requester_user_id=current.id,
        addressee_user_id=incoming_user.id,
        status="pending",
        created_at=now,
        updated_at=now,
        responded_at=None,
    )

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [
                (accepted, current, friend),
                (incoming, incoming_user, current),
                (outgoing, current, incoming_user),
            ]

    class Db:
        async def execute(self, _statement):
            return Result()

    payload = await social_utils.list_relationships(Db(), current_user=current)
    assert payload.friends[0].username == "friend"
    assert payload.incoming_requests[0].id == incoming.id
    assert payload.outgoing_requests[0].id == outgoing.id
