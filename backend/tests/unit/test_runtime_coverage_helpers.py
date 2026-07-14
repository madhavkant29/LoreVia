from __future__ import annotations

import hashlib
import importlib
import uuid
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.engine.analysis import plot_tracker, recall, summariser
from app.engine.intelligence import predictor
from app.engine.world.integration_mapper import detect_integration_opportunities
from app.models.beta_read import BetaReadAssignmentState, BetaReadScopeKind
from app.schemas.book import BookOut, BookStatusOut, BookUpload
from app.schemas.public import PublicBookManualIn, PublicChapterIn
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.services import character_service
from app.utils import (
    advisor_utils,
    beta_read_policy_utils,
    beta_read_progress_utils,
    beta_read_utils,
    export_utils,
    intelligence_utils,
    public_utils,
    reader_utils,
    world_building_serialization_utils,
    world_building_story_utils,
    world_building_utils,
)
from app.utils.books import (
    book_text,
    chapter_titles,
    character_cards,
    collaboration,
    collaboration_access,
    continuity,
    manuscript,
    normalization,
    notes,
    processing,
    revision_analysis,
    revision_decisions,
    scene_metadata,
    scene_ordering,
    scene_serialization,
    story_health,
    vault,
    writer_workspace,
)
from app.utils.books import (
    imports as book_imports,
)
from app.utils.index_format import format_index
from app.utils.public import (
    catalog,
    content,
    forum_engagement,
    forum_foundation,
    moderation,
    ranking_constants,
    ranking_core,
    requests,
    serialization,
)


@pytest.mark.parametrize(
    ("number", "style", "expected"),
    [
        (3, "arabic", "3"),
        (9, "roman-upper", "IX"),
        (58, "roman-lower", "lviii"),
        (27, "alpha-upper", "AA"),
        (28, "alpha-lower", "ab"),
        (0, "roman-upper", "0"),
        (0, "alpha-lower", "0"),
    ],
)
def test_format_index_supports_runtime_numbering_styles(number, style, expected):
    assert format_index(number, style) == expected


def test_format_index_rejects_unknown_style():
    with pytest.raises(ValueError, match="Unknown index format"):
        format_index(1, "chapterish")


def test_public_forum_request_parsing_helpers_and_image_validation():
    form = {
        "headline": "  Beta readers wanted  ",
        "allow_contact_requests": "on",
        "desired_beta_reader_count": "3",
        "empty": "",
    }

    assert requests.hash_text("  reader  ") == hashlib.sha256(b"reader").hexdigest()
    assert requests.hash_text("   ") is None
    assert requests._form_text(form, "headline") == "  Beta readers wanted  "
    assert requests._form_text(form, "missing", "fallback") == "fallback"
    assert requests._form_bool(form, "allow_contact_requests") is True
    assert requests._form_bool({}, "missing", True) is True
    assert requests._form_int(form, "desired_beta_reader_count") == 3
    assert requests._form_int(form, "empty") is None

    with pytest.raises(HTTPException) as invalid_number:
        requests._form_int({"desired_beta_reader_count": "many"}, "desired_beta_reader_count")
    assert invalid_number.value.status_code == 422

    with pytest.raises(HTTPException) as invalid_json:
        requests._json_payload_dict(["not", "object"])
    assert invalid_json.value.status_code == 422


@pytest.mark.asyncio
async def test_public_forum_image_helpers_accept_supported_magic_and_reject_bad_uploads():
    png_upload = SimpleNamespace(filename="../cover.png")
    chunks = [b"\x89PNG image bytes", b""]

    async def read_png(size):
        return chunks.pop(0)

    seek_calls: list[int] = []

    async def seek_png(offset):
        seek_calls.append(offset)

    png_upload.read = read_png
    png_upload.seek = seek_png

    raw, suffix, mime = await requests._read_public_forum_image(png_upload)

    assert raw.startswith(b"\x89PNG")
    assert suffix == "png"
    assert mime == "image/png"
    assert seek_calls == [0]
    assert requests._safe_forum_image_filename(png_upload, suffix) == "cover.png"

    bad_upload = SimpleNamespace(filename="bad.txt")
    bad_chunks = [b"plain text", b""]

    async def read_bad(size):
        return bad_chunks.pop(0)

    async def seek_bad(offset):
        return None

    bad_upload.read = read_bad
    bad_upload.seek = seek_bad

    with pytest.raises(HTTPException) as invalid_image:
        await requests._read_public_forum_image(bad_upload)
    assert invalid_image.value.status_code == 400


def test_public_visibility_forum_and_ranking_helpers(monkeypatch):
    owner_id = uuid.uuid4()
    book = SimpleNamespace(
        user_id=owner_id,
        is_public=True,
        source_kind=public_utils.USER_PUBLIC_SHARE_SOURCE_KIND,
        public_share_status=public_utils.PUBLIC_SHARE_STATUS_APPROVED,
        public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
        moderation_status=public_utils.MODERATION_STATUS_CLEAN,
        hidden_at=None,
        archived_at=None,
        mode="author",
        title="Novel",
        genre="Fantasy",
        public_description="A public beta novel.",
    )

    assert serialization.can_view_public_book(book) is True
    assert (
        serialization.can_owner_or_admin_view_hidden_book(SimpleNamespace(id=owner_id), book)
        is True
    )
    assert serialization.public_visibility_notice(
        SimpleNamespace(public_status="pending_review", moderation_status="clean")
    ) == ("This book is waiting for review before it can appear publicly.")
    assert serialization.normalize_public_analytics_event_type(" BOOK_VIEW ") == "book_view"
    assert (
        forum_foundation.public_forum_discoverability_score(
            average_rating=0.8,
            rating_count=20,
            positive_rating_count=4,
            negative_rating_count=1,
            interest_count=30,
        )
        == 207.0
    )
    assert forum_foundation.reputation_trust_level(-12) == "Low trust"
    assert forum_foundation.reputation_trust_level(4) == "New member"
    assert forum_foundation.reputation_trust_level(24) == "Trusted"
    assert forum_foundation.reputation_trust_level(25) == "Highly trusted"
    assert forum_foundation._normalize_forum_status(None) == forum_foundation.FORUM_POST_OPEN
    assert (
        forum_foundation._normalize_forum_thread_type("GENERAL")
        == forum_foundation.FORUM_THREAD_TYPE_GENERAL
    )
    assert (
        forum_foundation._normalize_forum_comment_reaction(" Like ")
        == forum_foundation.FORUM_COMMENT_REACTION_LIKE
    )
    assert forum_foundation._reaction_delta("like", "dislike") == (-1, 1, -2)
    assert forum_foundation._book_is_forum_eligible(book) is True
    assert (
        forum_foundation._forum_post_thread_type(SimpleNamespace(thread_type="general"))
        == "general"
    )
    assert forum_foundation._is_general_forum_post(SimpleNamespace(thread_type="general")) is True
    forum_foundation._validate_forum_book_metadata(book)

    monkeypatch.setattr(settings, "PUBLIC_FORUM_STATUS", "beta", raising=False)
    assert forum_foundation.get_public_forum_status() == "beta"
    with pytest.raises(HTTPException) as write_disabled:
        forum_foundation.ensure_public_forum_write_enabled()
    assert write_disabled.value.status_code == 403

    with pytest.raises(HTTPException):
        forum_foundation._normalize_forum_status("closed-ish")
    with pytest.raises(HTTPException):
        forum_foundation._validate_forum_book_metadata(
            SimpleNamespace(title="", genre="Fantasy", public_description="Desc")
        )


def test_annotation_vault_and_scene_workspace_helpers():
    user_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    book_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    annotation = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        book_id=book_id,
        chapter_number=2,
        category="continuity",
        status="open",
        visibility="shared",
        quote="amber light",
        comment="Check color",
        anchor_context_before="patient",
        anchor_context_after="filled",
        start_offset=10,
        end_offset=21,
        resolved_at=None,
        created_at=created_at,
        updated_at=created_at,
    )
    book = SimpleNamespace(id=book_id, title="Novel", user_id=owner_id)

    assert notes._annotation_category("Line edit") == "line_edit"
    assert notes._annotation_status(None) == "open"
    assert notes._annotation_visibility("PRIVATE") == "private"
    assert (
        notes._annotation_actor_label(SimpleNamespace(username="", email="reader@example.com"))
        == "reader"
    )
    serialized = notes._serialize_manuscript_annotation(
        annotation,
        book=book,
        chapter_title="The Gate",
        actor_user_id=owner_id,
        created_by_label="reader",
    )
    assert serialized["can_edit"] is True
    assert serialized["chapter_title"] == "The Gate"

    with pytest.raises(HTTPException):
        notes._annotation_category("invented")
    with pytest.raises(HTTPException):
        notes._annotation_status("stale")
    with pytest.raises(HTTPException):
        notes._annotation_visibility("team")

    assert vault.normalize_vault_note_source(" user_notes ") == "user_notes"
    assert vault.normalize_vault_note_path(r" Characters\\Mara.md ") == "Characters/Mara.md"
    assert vault.vault_note_title("Characters/Mara.md") == "Mara"
    assert vault.vault_note_folder("Characters/Mara.md") == "Characters"
    assert vault.extract_wiki_references("See [[Mara|the guard]] and ![[Gate#Lore]]") == [
        {"target": "Mara", "alias": "the guard", "link_type": "reference"},
        {"target": "Gate", "alias": "Gate", "link_type": "embed"},
    ]
    assert vault.extract_wiki_tags("#Magic #magic #Gate_Lore") == ["magic", "gate-lore"]
    graph = vault.build_vault_graph(
        [
            {"path": "Characters/Mara.md", "content": "[[Gate|the gate]] #hero"},
            {"path": "World/Gate.md", "content": "[[Mara]]"},
        ]
    )
    assert {node["id"] for node in graph["nodes"]} == {"Characters/Mara.md", "World/Gate.md"}
    assert graph["edges"][0]["label"] == "the gate"

    scene_text = """
    ## Scene 7 - Gate opens

    POV: Mara
    Characters:
    - Mara
    - Theo
    Mood:
    - tense
    Conflict: The lock resists her.
    ---

    Mara turned the brass key.
    """
    metadata = scene_metadata.extract_scene_metadata(scene_text)
    assert metadata["pov"] == "Mara"
    assert metadata["characters"] == ["Mara", "Theo"]
    assert (
        scene_metadata.normalize_scene_metadata(
            {"tags": "key, gate", "summary": "Location: North Gate"}, description="Fallback"
        )["location"]
        == "North Gate"
    )
    assert (
        scene_metadata.build_novel_scene_path(chapter_number=3, sort_order=2, title="Gate Opens!")
        == "scenes/chapter-03/002-gate-opens.md"
    )
    assert (
        scene_metadata.strip_scene_planning_block(scene_text, title="Gate opens")
        == "Mara turned the brass key."
    )
    imported = scene_metadata.build_scene_chapter_import_text(
        {
            "title": "Gate opens",
            "body": scene_text,
            "metadata": metadata,
        },
        scene_number=7,
    )
    assert "## Scene 7 - Gate opens" in imported
    assert "POV: Mara" in imported
    assert (
        scene_metadata.chapter_body_needs_scene_workspace_fallback("III", chapter_number=3) is True
    )
    assert (
        scene_metadata.strip_scene_metadata_from_manuscript_text(imported)
        == "Mara turned the brass key."
    )


def test_detect_integration_opportunities_flags_lightly_used_elements():
    opportunities = detect_integration_opportunities(
        [
            {
                "name": "Moon Court",
                "element_type": "culture",
                "usage_count": 1,
                "chapter_number": 4,
            },
            {"name": "Storm Roads", "usage_count": 2},
            {"name": "  ", "usage_count": 1},
        ]
    )

    assert opportunities == [
        {
            "id": "integration-moon-court",
            "element_name": "Moon Court",
            "element_type": "culture",
            "description": "Moon Court appears lightly in the extracted manuscript and may need stronger story integration.",
            "suggestions": [
                "Anchor Moon Court to a character decision or conflict beat.",
                "Reference Moon Court earlier so later appearances feel earned.",
            ],
            "target_chapter": 4,
            "priority": 5,
        }
    ]


def test_schema_models_validate_runtime_payloads():
    book_id = uuid.uuid4()
    user_id = uuid.uuid4()
    created_at = datetime.now(UTC)

    assert BookUpload(title="Novel", genre="Fantasy", author="A Writer").title == "Novel"
    assert BookStatusOut(status="ready", total_chapters=12).total_chunks is None
    assert (
        BookOut(
            id=book_id,
            title="Novel",
            author=None,
            genre=None,
            format="txt",
            status="ready",
            total_chapters=12,
            created_at=created_at,
        ).id
        == book_id
    )
    assert (
        UserCreate(email="reader@example.com", password="long-enough").email == "reader@example.com"
    )
    assert UserLogin(email="reader@example.com", password="secret").password == "secret"
    assert (
        UserOut(
            id=user_id,
            email="reader@example.com",
            username=None,
            tier="free",
            reading_mode="casual",
            daily_word_goal=1000,
            today_word_count=0,
            last_login_at=None,
            login_streak_days=0,
            longest_login_streak_days=0,
            created_at=created_at,
        ).login_activity_dates
        == []
    )

    with pytest.raises(ValidationError):
        BookUpload(title="")


@pytest.mark.asyncio
async def test_predict_returns_theories_from_tracked_completion(monkeypatch):
    close_calls = 0

    class FakeClient:
        async def close(self):
            nonlocal close_calls
            close_calls += 1

    async def fake_semantic_search(*args, **kwargs):
        return [{"text": "Mira hid the key in chapter two."}]

    async def fake_chat_completion(**kwargs):
        assert kwargs["feature"] == "prediction"
        assert "Mira hid the key" in kwargs["messages"][1]["content"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"theories":[{"theory":"Mira will recover the key","confidence":0.8}]}'
                    )
                )
            ]
        )

    monkeypatch.setattr(predictor, "get_client", lambda: FakeClient())
    monkeypatch.setattr(predictor, "semantic_search", fake_semantic_search)
    monkeypatch.setattr(predictor, "create_tracked_chat_completion", fake_chat_completion)

    theories = await predictor.predict(
        db=SimpleNamespace(),
        book_id=uuid.uuid4(),
        question="Where is the key?",
        current_chapter=3,
        user_id=uuid.uuid4(),
    )

    assert theories == [{"theory": "Mira will recover the key", "confidence": 0.8}]
    assert close_calls == 1


@pytest.mark.asyncio
async def test_predict_returns_empty_list_for_malformed_model_json(monkeypatch):
    class FakeClient:
        async def close(self):
            pass

    async def fake_semantic_search(*args, **kwargs):
        return [{"text": "Context"}]

    async def fake_chat_completion(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
        )

    monkeypatch.setattr(predictor, "get_client", lambda: FakeClient())
    monkeypatch.setattr(predictor, "semantic_search", fake_semantic_search)
    monkeypatch.setattr(predictor, "create_tracked_chat_completion", fake_chat_completion)

    assert await predictor.predict(SimpleNamespace(), uuid.uuid4(), "Question?", 1) == []


def test_low_level_schema_modules_import_cleanly():
    assert importlib.import_module("app.schemas.book").BookUpload is BookUpload
    assert importlib.import_module("app.schemas.user").UserOut is UserOut


def test_summary_derivation_uses_detailed_events_and_sentence_fallback():
    derived = summariser.derive_summary_modes_from_detailed(
        {
            "content": "Mira found the gate. Joren broke the seal. The city woke. Rain began.",
            "key_events": [
                {"event_title": "Gate opens", "description": "Mira opens the ash gate"},
                {"event": "Seal breaks", "impact": "Joren breaks the old seal"},
            ],
        }
    )

    assert (
        derived["short"]["content"] == "Mira found the gate. Joren broke the seal. The city woke."
    )
    assert derived["key_points"]["content"].splitlines() == [
        "1. Gate opens: Mira opens the ash gate.",
        "2. Seal breaks: Joren breaks the old seal.",
    ]

    fallback = summariser.derive_summary_modes_from_detailed(
        {"content": "One. Two. Three. Four. Five. Six."}
    )
    assert fallback["key_points"]["content"].splitlines() == [
        "1. One.",
        "2. Two.",
        "3. Three.",
        "4. Four.",
        "5. Five.",
    ]


@pytest.mark.asyncio
async def test_generate_summary_normalizes_detailed_json_and_plain_modes(monkeypatch):
    async def fake_complete_with_fallback(**kwargs):
        if kwargs["response_format"]:
            return """```json
            {
              "summary": "Mira opens the gate.",
              "key_events": ["Gate opens", {"event": "Seal breaks", "impact": "The ward fails"}],
              "char_changes": [{"character": "Mira", "description": "Accepts leadership", "impact_score": 7}],
              "clues": [{"clue": "Ash key"}],
              "themes": [{"theme": "burden"}]
            }
            ```"""
        return "Plain chapter summary"

    monkeypatch.setattr(summariser, "complete_with_fallback", fake_complete_with_fallback)

    detailed = await summariser.generate_summary("chapter text", "detailed", "Ash Gate")
    short = await summariser.generate_summary("chapter text", "short", "Ash Gate")

    assert detailed["content"] == "Mira opens the gate."
    assert detailed["key_events"][0]["event_title"] == "Gate opens"
    assert detailed["key_events"][1]["description"] == "The ward fails"
    assert detailed["char_changes"][0]["growth_direction"] == "neutral"
    assert short == {
        "content": "Plain chapter summary",
        "key_events": None,
        "char_changes": None,
        "clues": None,
        "themes": None,
    }


@pytest.mark.asyncio
async def test_extract_plot_threads_strips_json_fences_and_marks_chapter(monkeypatch):
    async def fake_complete_with_fallback(**kwargs):
        assert kwargs["usage_feature"] == "plot_thread_extraction"
        assert kwargs["usage_metadata"] == {"chapter_number": 5}
        return """```json
        {"threads":[{"title":"The ash key","status":"introduced"}]}
        ```"""

    monkeypatch.setattr(plot_tracker, "complete_with_fallback", fake_complete_with_fallback)

    assert await plot_tracker.extract_plot_threads("chapter text", 5) == [
        {"title": "The ash key", "status": "introduced", "introduced_at": 5}
    ]


@pytest.mark.asyncio
async def test_extract_plot_threads_returns_empty_list_on_model_or_json_errors(monkeypatch):
    async def malformed_complete(**kwargs):
        return "not json"

    monkeypatch.setattr(plot_tracker, "complete_with_fallback", malformed_complete)
    assert await plot_tracker.extract_plot_threads("chapter text", 1) == []

    async def failing_complete(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(plot_tracker, "complete_with_fallback", failing_complete)
    assert await plot_tracker.extract_plot_threads("chapter text", 1) == []


@pytest.mark.asyncio
async def test_generate_recall_builds_limited_context_and_polishes_response(monkeypatch):
    async def fake_complete_with_fallback(**kwargs):
        assert kwargs["usage_feature"] == "reader_recall"
        assert "Mira, Joren, Vale, Sera, Ash" in kwargs["user"]
        assert "Sixth name" not in kwargs["user"]
        assert "Gate mystery, Old debt, Missing crown" in kwargs["user"]
        assert "Fourth thread" not in kwargs["user"]
        return "Previously on: As we dive back in, Mira remembers the gate."

    monkeypatch.setattr(recall, "complete_with_fallback", fake_complete_with_fallback)

    result = await recall.generate_recall(
        "The Ember Gate",
        8,
        "The gate opened.",
        ["Mira", "Joren", "Vale", "Sera", "Ash", "Sixth name"],
        ["Gate mystery", "Old debt", "Missing crown", "Fourth thread"],
    )

    assert result == "Mira remembers the gate."


@pytest.mark.asyncio
async def test_character_service_uses_cache_and_populates_character_profile(monkeypatch):
    character_id = uuid.uuid4()
    cache: dict[str, dict] = {}
    set_calls: list[tuple[str, dict, int]] = []

    async def fake_cache_get(key):
        return cache.get(key)

    async def fake_cache_set(key, value, ttl):
        set_calls.append((key, value, ttl))
        cache[key] = value

    monkeypatch.setattr(character_service, "cache_get", fake_cache_get)
    monkeypatch.setattr(character_service, "cache_set", fake_cache_set)
    monkeypatch.setattr(
        character_service, "key_character_profile", lambda value: f"profile:{value}"
    )
    monkeypatch.setattr(character_service.settings, "REDIS_TTL_CHARACTER_PROFILE", 123)

    class FakeDb:
        def __init__(self):
            self.get_calls = 0

        async def get(self, model, requested_id):
            self.get_calls += 1
            assert requested_id == character_id
            return SimpleNamespace(
                id=character_id,
                name="Mira",
                aliases=None,
                trait_state={"brave": True},
                personality_tags=["stubborn"],
                motivations=["save the gate"],
                fears=[],
                archetype="guardian",
                arc_summary="Learns trust.",
            )

    db = FakeDb()

    profile = await character_service.get_character_cached(db, character_id)
    cached_profile = await character_service.get_character_cached(db, character_id)

    assert profile == cached_profile
    assert profile["aliases"] == []
    assert profile["name"] == "Mira"
    assert db.get_calls == 1
    assert set_calls == [(f"profile:{character_id}", profile, 123)]


@pytest.mark.asyncio
async def test_character_service_returns_spoiler_free_state_or_character_fallback():
    character_id = uuid.uuid4()

    class ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar(self):
            return self.value

    class StateDb:
        async def execute(self, statement):
            return ScalarResult(
                SimpleNamespace(
                    trait_snapshot={"wounded": True},
                    at_chapter=4,
                    arc_note="Hides the wound.",
                )
            )

        async def get(self, model, requested_id):
            raise AssertionError("character fallback should not be queried when a state exists")

    assert await character_service.get_spoiler_free_state(StateDb(), character_id, 6) == {
        "trait_state": {"wounded": True},
        "at_chapter": 4,
        "arc_note": "Hides the wound.",
    }

    class FallbackDb:
        async def execute(self, statement):
            return ScalarResult(None)

        async def get(self, model, requested_id):
            return SimpleNamespace(trait_state={"curious": True})

    assert await character_service.get_spoiler_free_state(FallbackDb(), character_id, 1) == {
        "trait_state": {"curious": True},
        "at_chapter": 0,
    }


def test_public_utils_validate_visibility_rankings_and_forum_signals(monkeypatch):
    book_id = uuid.uuid4()
    visible_book = SimpleNamespace(
        id=book_id,
        is_public=True,
        public_status="published",
        moderation_status="reported",
        hidden_at=None,
        archived_at=None,
        source_kind="public_demo",
        public_share_status="approved",
        public_slug="ember-gate",
    )
    hidden_book = SimpleNamespace(
        id=uuid.uuid4(),
        is_public=True,
        public_status="hidden",
        moderation_status="clean",
        hidden_at=None,
        archived_at=None,
    )

    monkeypatch.setattr(settings, "APP_URL", "https://www.getlorevia.com")

    assert serialization.normalize_public_analytics_event_type(" BOOK_VIEW ") == "book_view"
    assert serialization.can_view_public_book(visible_book) is True
    assert serialization.can_view_public_book(hidden_book) is False
    assert serialization.public_visibility_notice(hidden_book) == (
        "This book is currently hidden from public view due to a policy or copyright report."
    )
    assert (
        moderation.validate_public_content_report_target(
            visible_book,
            "https://getlorevia.com/public/ember-gate",
        )
        == "https://getlorevia.com/public/ember-gate"
    )
    assert (
        moderation.ensure_content_source_allowed_for_user(SimpleNamespace(), " user_original ")
        == "user_original"
    )
    assert moderation.ensure_report_type_supported("SPAM") == "spam"
    assert ranking_core.normalize_public_ranking_key("top_rated") == "top_rated"
    assert ranking_core.normalize_public_ranking_window("weekly") == "weekly"
    assert (
        ranking_core.public_ranking_window_start(
            time_window="all_time",
            now=datetime(2026, 1, 10, tzinfo=UTC),
        )
        is None
    )
    assert ranking_core.public_ranking_window_start(
        time_window="weekly",
        now=datetime(2026, 1, 10, tzinfo=UTC),
    ) == datetime(2026, 1, 3, tzinfo=UTC)
    assert (
        ranking_core.public_ranking_label(ranking_key="top_rated", time_window="weekly")
        == "Top rated this week"
    )
    metadata = ranking_core.build_public_ranking_metadata(
        surface="creator_uploads",
        ranking_key="most_popular",
        time_window="monthly",
        position=2,
        score=12.5,
    )
    assert metadata.label == "Most popular this month"
    assert metadata.supporting_note.startswith("Weighted by recent reader activity")
    assert (
        forum_foundation.public_forum_discoverability_score(
            average_rating=4.2,
            rating_count=20,
            positive_rating_count=3,
            negative_rating_count=1,
            interest_count=30,
        )
        == 535.0
    )
    assert forum_foundation.reputation_trust_level(-12) == "Low trust"
    assert forum_foundation.reputation_trust_level(8) == "Trusted"
    assert forum_foundation.reputation_trust_level(30) == "Highly trusted"
    assert forum_foundation._reaction_delta("like", "dislike") == (-1, 1, -2)
    assert (
        forum_engagement.forum_post_is_publicly_interactive(SimpleNamespace(status=" open "))
        is True
    )
    assert (
        forum_engagement.forum_post_is_publicly_interactive(SimpleNamespace(status="closed"))
        is False
    )

    with pytest.raises(HTTPException):
        serialization.normalize_public_analytics_event_type("unknown")
    with pytest.raises(HTTPException):
        moderation.ensure_content_source_allowed_for_user(SimpleNamespace(), "licensed")
    with pytest.raises(HTTPException):
        moderation.validate_public_content_report_target(
            visible_book,
            "https://evil.example/public/ember-gate",
        )


def test_public_utils_form_slug_forum_and_ranking_helpers(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_MODE_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_FORUM_STATUS", "public")
    monkeypatch.setattr(settings, "API_V1_PREFIX", "/api/v1")
    monkeypatch.setattr(requests, "get_presigned_url", lambda storage_key: None)
    monkeypatch.setattr(
        requests,
        "create_asset_token",
        lambda subject, resource, expires_minutes: f"token:{subject}:{resource}:{expires_minutes}",
    )

    assert content.normalize_public_slug("  The Ember Gate!! ") == "the-ember-gate"
    with pytest.raises(HTTPException):
        content.normalize_public_slug("no")

    assert requests.hash_text(" reader ") == requests.hash_text("reader")
    assert requests.hash_text("   ") is None
    request = SimpleNamespace(
        headers={
            "x-forwarded-for": "203.0.113.5, 10.0.0.2",
            "x-lorevia-edge-verified": "1",
            "user-agent": " Test   Agent ",
        },
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert requests.build_public_visitor_fingerprint(request) == requests.hash_text(
        "203.0.113.5|test agent"
    )
    assert requests.build_public_visitor_fingerprint(None) is None

    form = {
        "title": "  Story  ",
        "enabled": "yes",
        "count": "7",
        "upload": SimpleNamespace(filename="cover.png"),
        "empty_upload": SimpleNamespace(filename=""),
    }
    assert requests._form_text(form, "title") == "  Story  "
    assert requests._form_text(form, "missing", "fallback") == "fallback"
    assert requests._form_bool(form, "enabled") is True
    assert requests._form_bool({}, "enabled", True) is True
    assert requests._form_int(form, "count") == 7
    assert requests._form_upload(form, "upload").filename == "cover.png"
    assert requests._form_upload(form, "empty_upload") is None
    assert requests._json_payload_dict({"ok": True}) == {"ok": True}
    with pytest.raises(HTTPException):
        requests._form_int({"count": "bad"}, "count")
    with pytest.raises(HTTPException):
        requests._json_payload_dict(["not", "a", "dict"])

    upload = SimpleNamespace(filename="../unsafe name.png")
    assert requests._safe_forum_image_filename(upload, "jpg") == "unsafe name.jpg"
    image_url = requests.public_forum_image_url(
        storage_key="forum/image.jpg",
        owner_user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        target_kind="post",
        target_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
    )
    assert image_url == (
        "/api/v1/public/forum/posts/00000000-0000-0000-0000-000000000002/image?"
        "token=token:00000000-0000-0000-0000-000000000001:"
        "public-forum-post-image:00000000-0000-0000-0000-000000000002:120"
    )
    assert (
        requests.public_forum_image_url(
            storage_key=None,
            owner_user_id=uuid.uuid4(),
            target_kind="post",
            target_id=uuid.uuid4(),
        )
        is None
    )

    user_id = uuid.uuid4()
    book_id = uuid.uuid4()
    published_at = datetime(2026, 1, 1, tzinfo=UTC)
    updated_at = datetime(2026, 1, 12, tzinfo=UTC)
    book = SimpleNamespace(
        id=book_id,
        user_id=user_id,
        title="The Ember Gate",
        author="A Writer",
        genre="Fantasy",
        format="manual",
        work_type="novel",
        status="ready",
        is_public=True,
        source_kind=public_utils.USER_PUBLIC_SHARE_SOURCE_KIND,
        public_status=public_utils.PUBLIC_STATUS_PUBLISHED,
        moderation_status=public_utils.MODERATION_STATUS_CLEAN,
        public_share_status=public_utils.PUBLIC_SHARE_STATUS_APPROVED,
        public_slug="ember-gate",
        public_description="A city wakes under ash.",
        source_title="The Ember Gate",
        source_author="A Writer",
        source_public_domain_note=None,
        source_url=None,
        total_chapters=12,
        copyright_warning=False,
        created_at=published_at,
        published_at=published_at,
        public_updated_at=updated_at,
        hidden_at=None,
        archived_at=None,
        mode="author",
    )
    owner = SimpleNamespace(id=user_id)
    stranger = SimpleNamespace(id=uuid.uuid4())
    assert serialization.can_owner_or_admin_view_hidden_book(owner, book) is True
    assert serialization.can_owner_or_admin_view_hidden_book(stranger, book) is False
    assert serialization.public_catalog_kind(book) == public_utils.USER_PUBLIC_SHARE_SOURCE_KIND
    assert serialization.is_user_public_share_book(book) is True
    assert serialization.is_visible_creator_public_book(book) is True
    assert catalog.is_catalog_visible_public_book(book) is True
    assert serialization.get_public_share_status(book) == public_utils.PUBLIC_SHARE_STATUS_APPROVED

    book_out = serialization.build_public_book_out(
        book,
        author_username="emberwriter",
        active_forum_post_id="post-1",
    )
    assert book_out.creator_display_name == "emberwriter"
    assert book_out.active_forum_post_id == "post-1"
    assert ranking_core._search_matches_public_book(book_out, "ash") is True
    assert ranking_core._search_matches_public_book(book_out, "missing") is False

    assert ranking_core._safe_average([1, 2, 4]) == 2.33
    assert ranking_core._timestamp_score(updated_at) == updated_at.timestamp()
    assert ranking_core._timestamp_score(None) == 0.0
    assert ranking_core._book_public_activity_timestamp(book) == updated_at
    assert ranking_core._public_ranking_supporting_note(
        ranking_key=ranking_constants.PUBLIC_RANKING_MOST_COMPLEX,
        time_window=ranking_constants.PUBLIC_RANKING_WINDOW_MONTHLY,
    ).startswith("Weighted by LoreVia craft-analysis")
    assert (
        ranking_core._structural_ranking_is_eligible(
            book=book, window_start=datetime(2026, 1, 10, tzinfo=UTC)
        )
        is True
    )
    assert (
        ranking_core._structural_ranking_is_eligible(
            book=book, window_start=datetime(2026, 2, 1, tzinfo=UTC)
        )
        is False
    )

    craft_profile = {
        "complexity_score": 77.5,
        "visible_character_count": 18,
        "well_written_score": 82.0,
        "beginner_friendly_score": 66.0,
    }
    rating_stats = {
        "average_rating": 4.5,
        "rating_count": 10,
        "positive_rating_count": 7,
        "negative_rating_count": 1,
        "latest_rating_at": datetime(2026, 1, 11, tzinfo=UTC),
    }
    view_stats = {"book_view_count": 2, "unique_reader_count": 3, "chapter_view_count": 8}
    forum_stats = {
        "discussion_interest_count": 4,
        "discussion_comment_count": 5,
        "open_discussion_count": 1,
        "latest_activity_at": datetime(2026, 1, 12, tzinfo=UTC),
    }
    assert (
        ranking_core._compute_public_ranking_score(
            surface=ranking_constants.PUBLIC_RANKING_SURFACE_UPLOADS,
            ranking_key=ranking_constants.PUBLIC_RANKING_TOP_RATED,
            book=book,
            craft_profile=craft_profile,
            rating_stats=rating_stats,
            view_stats=view_stats,
            forum_stats=forum_stats,
            window_start=None,
        )[0]
        == 509.0
    )
    assert (
        ranking_core._compute_public_ranking_score(
            surface=ranking_constants.PUBLIC_RANKING_SURFACE_UPLOADS,
            ranking_key=ranking_constants.PUBLIC_RANKING_MOST_POPULAR,
            book=book,
            craft_profile=craft_profile,
            rating_stats=rating_stats,
            view_stats=view_stats,
            forum_stats=forum_stats,
            window_start=None,
        )[0]
        == 134.0
    )
    assert (
        ranking_core._compute_public_ranking_score(
            surface=ranking_constants.PUBLIC_RANKING_SURFACE_UPLOADS,
            ranking_key=ranking_constants.PUBLIC_RANKING_BIG_CAST,
            book=book,
            craft_profile=craft_profile,
            rating_stats=rating_stats,
            view_stats=view_stats,
            forum_stats=forum_stats,
            window_start=None,
        )[0]
        == 18.0
    )
    assert (
        ranking_core._compute_public_ranking_score(
            surface=ranking_constants.PUBLIC_RANKING_SURFACE_UPLOADS,
            ranking_key=ranking_constants.PUBLIC_RANKING_RECENTLY_UPDATED,
            book=book,
            craft_profile=craft_profile,
            rating_stats=rating_stats,
            view_stats=view_stats,
            forum_stats=forum_stats,
            window_start=datetime(2026, 1, 10, tzinfo=UTC),
        )[0]
        == updated_at.timestamp()
    )

    assert forum_foundation.get_public_forum_status() == "public"
    forum_foundation.ensure_public_forum_read_enabled()
    forum_foundation.ensure_public_forum_write_enabled()
    monkeypatch.setattr(settings, "PUBLIC_FORUM_STATUS", "beta")
    forum_foundation.ensure_public_forum_read_enabled()
    with pytest.raises(HTTPException):
        forum_foundation.ensure_public_forum_write_enabled()
    monkeypatch.setattr(settings, "PUBLIC_FORUM_STATUS", "bad")
    with pytest.raises(HTTPException):
        forum_foundation.get_public_forum_status()
    monkeypatch.setattr(settings, "PUBLIC_FORUM_STATUS", "public")

    assert (
        forum_foundation._normalize_forum_status(" closed ") == forum_foundation.FORUM_POST_CLOSED
    )
    assert (
        forum_foundation._normalize_forum_thread_type(None)
        == forum_foundation.FORUM_THREAD_TYPE_NOVEL
    )
    assert (
        forum_foundation._normalize_forum_comment_reaction(" LIKE ")
        == forum_foundation.FORUM_COMMENT_REACTION_LIKE
    )
    assert forum_foundation._reaction_score("like") == 1
    assert forum_foundation._reaction_score("dislike") == -1
    with pytest.raises(HTTPException):
        forum_foundation._normalize_forum_status("archived")
    with pytest.raises(HTTPException):
        forum_foundation._normalize_forum_thread_type("review")
    with pytest.raises(HTTPException):
        forum_foundation._normalize_forum_comment_reaction("heart")

    private_book = SimpleNamespace(
        is_public=False,
        mode="author",
        hidden_at=None,
        archived_at=None,
        public_status="draft",
        moderation_status="clean",
    )
    reader_book = SimpleNamespace(
        is_public=False,
        mode="reader",
        hidden_at=None,
        archived_at=None,
        public_status="draft",
        moderation_status="clean",
    )
    hidden_public_book = SimpleNamespace(
        is_public=True,
        mode="author",
        hidden_at=None,
        archived_at=None,
        public_status="hidden",
        moderation_status="clean",
    )
    assert forum_foundation._book_is_forum_eligible(private_book) is True
    assert forum_foundation._book_is_forum_eligible(reader_book) is False
    assert forum_foundation._book_is_forum_eligible(hidden_public_book) is False
    assert (
        forum_foundation._forum_post_thread_type(SimpleNamespace(thread_type="general"))
        == "general"
    )
    assert forum_foundation._is_general_forum_post(SimpleNamespace(thread_type="general")) is True
    forum_foundation._validate_forum_book_metadata(book)
    with pytest.raises(HTTPException):
        forum_foundation._validate_forum_book_metadata(
            SimpleNamespace(title="", genre="Fantasy", public_description="Desc")
        )
    assert forum_foundation._normalize_public_forum_pagination(0, 1000) == (
        1,
        forum_foundation.MAX_PUBLIC_FORUM_PAGE_SIZE,
    )


def test_advisor_utils_normalize_modes_mentions_and_structured_results(monkeypatch):
    monkeypatch.setattr(advisor_utils, "classify_world_intent", lambda message: "story_integration")

    assert (
        advisor_utils.detect_advisor_world_mode(
            "Does this world rule contradict the canon?", "consistency"
        )
        == "gap_detection"
    )
    assert (
        advisor_utils.detect_advisor_world_mode("How can I integrate this kingdom lore?", "general")
        == "story_integration"
    )
    assert advisor_utils.detect_advisor_world_mode("What should Mira do next?", "general") is None
    assert (
        advisor_utils.advisor_retrieval_settings("general", "gap_detection")[0]
        == advisor_utils.settings.ADVISOR_CONTINUITY_SEARCH_CHUNKS
    )
    assert advisor_utils.normalize_whats_the_word_result(
        '{"word":"Luminous","gloss":"  softly bright  "}'
    ) == {
        "word": "luminous",
        "gloss": "softly bright",
    }
    assert advisor_utils.normalize_whats_the_word_result("storm-lit")["word"] == "storm-lit"
    assert (
        advisor_utils.classify_intent_fast("There is a contradiction in chapter seven")
        == "plothole"
    )

    character_rows = [
        {"name": "Mira Vale", "aliases": ["Mira"], "first_chapter": 1},
        {"name": "Joren", "aliases": [], "first_chapter": 2},
    ]
    mentions = advisor_utils.identify_character_mentions(
        "Mira's choice makes Mira Vale doubt Joren.", character_rows
    )
    assert [item["name"] for item in mentions] == ["Mira Vale", "Joren"]

    context = advisor_utils.build_character_voice_context(
        [
            {
                "name": "Mira",
                "first_chapter": 1,
                "role": "protagonist",
                "arc_summary": "Learns to lead.",
                "personality_tags": ["guarded", "precise"],
                "motivations": ["save the gate"],
                "fears": ["failure"],
                "trait_state": {"eyes": {"value": "gray"}, "hair": "black"},
            }
        ]
    )
    assert "Mira (first chapter 1, role protagonist)" in context
    assert "eyes=gray" in context
    assert advisor_utils.build_character_voice_context([]).startswith("No obvious named characters")

    voice = advisor_utils.normalize_voice_consistency_result(
        '{"issues":[{"character_name":" Mira ","title":" Drift ","description":" too casual ","severity":"minor"}],"overall_verdict":" usable "}'
    )
    assert voice["issues"][0]["character_name"] == "Mira"
    assert voice["overall_verdict"] == "usable"
    assert (
        advisor_utils.normalize_voice_consistency_result("not json")["overall_verdict"]
        == "not json"
    )

    editorial = advisor_utils.normalize_editorial_review_result(
        '{"continuity_issues":[{"title":"Gate","description":"Mismatch"}],'
        '"insertion_opportunities":[{"title":"Seed","problem":"Late reveal","what_to_add":"Mention key","why_here":"Before payoff","target_chapter":2}],'
        '"grammar_issues":[{"original":"bad","issue":"tense","fix":"better"}],'
        '"formatting_notes":[" extra   space "],'
        '"thematic_fit":{"score":"strong","notes":"fits"},'
        '"overall_verdict":"revise"}'
    )
    assert editorial["continuity_issues"][0]["title"] == "Gate"
    assert editorial["insertion_opportunities"][0]["target_chapter"] == 2
    assert editorial["grammar_issues"][0]["fix"] == "better"

    assert advisor_utils.normalize_synopsis_result(
        '{"synopsis":" A tale ","focus_points":["gate"," debt "]}', "low"
    ) == {
        "spoiler_level": "low",
        "synopsis": "A tale",
        "focus_points": ["gate", "debt"],
    }
    assert advisor_utils.normalize_prose_tighten_result(
        '{"tightened_text":"The gate opened.","rationale":["Trimmed"]}',
        "The gate slowly opened.",
    ) == {
        "tightened_text": "The gate opened.",
        "rationale": ["Trimmed"],
        "changed": True,
    }
    proactive = advisor_utils.normalize_proactive_scan_result(
        '{"findings":[{"title":"Seed relic","description":"The relic appears late","action_label":"Ask","ask_prompt":"Where can I seed it?","chapter_ref":3}],'
        '"overall_note":"One issue"}'
    )
    assert proactive["findings"][0]["chapter_ref"] == 3


def test_advisor_utils_result_fallbacks_and_continuity_report_exports():
    assert advisor_utils.classify_intent_fast("") == "general"
    assert (
        advisor_utils.classify_intent_fast("Where can I add foreshadowing for the dagger?")
        == "opportunity"
    )
    assert (
        advisor_utils.classify_intent_fast("Make this paragraph tighter and less wordy.")
        == "general"
    )

    mixed_voice = advisor_utils.normalize_voice_consistency_result(
        '{"issues":["skip",{"character_name":"","title":"Missing name","description":"skip"},'
        '{"character_name":"Joren","title":"Formal drift","description":"The line is too modern."}],'
        '"overall_verdict":""}'
    )
    assert mixed_voice["issues"][0]["character_name"] == "Joren"
    assert mixed_voice["issues"][0]["title"] == "Formal drift"
    assert mixed_voice["issues"][0]["severity"] == "moderate"
    assert mixed_voice["issues"][0]["evidence"] == ""
    assert mixed_voice["issues"][0]["intentionality_prompt"] == ""
    assert mixed_voice["overall_verdict"] == "Voice consistency review could not be parsed."

    assert (
        advisor_utils.normalize_editorial_review_result("plain review")["overall_verdict"]
        == "plain review"
    )
    filtered_editorial = advisor_utils.normalize_editorial_review_result(
        '{"continuity_issues":["skip",{"title":"","description":"missing"},'
        '{"title":"Gate","description":"Mismatch","suggestion":"Seed earlier"}],'
        '"insertion_opportunities":[{"title":"Bad","problem":"x","what_to_add":"y","why_here":"z","target_chapter":0},'
        '{"title":"Seed key","problem":"Late key","what_to_add":"Mention ash","why_here":"Before reveal","target_chapter":4}],'
        '"grammar_issues":[{"original":"","issue":"bad","fix":"skip"},{"original":"was","issue":"tense","fix":"is"}],'
        '"formatting_notes":[" "," indent dialogue "],'
        '"thematic_fit":null,'
        '"overall_verdict":""}'
    )
    assert [item["title"] for item in filtered_editorial["continuity_issues"]] == ["Gate"]
    assert [item["title"] for item in filtered_editorial["insertion_opportunities"]] == ["Seed key"]
    assert filtered_editorial["grammar_issues"] == [
        {"original": "was", "issue": "tense", "fix": "is"}
    ]
    assert filtered_editorial["formatting_notes"] == ["indent dialogue"]
    assert filtered_editorial["overall_verdict"] == "Editorial review could not be parsed."

    assert advisor_utils.normalize_synopsis_result("Loose synopsis text", "medium") == {
        "spoiler_level": "medium",
        "synopsis": "Loose synopsis text",
        "focus_points": ["premise", "tone", "main conflict"],
    }
    assert advisor_utils.normalize_synopsis_result('{"synopsis":"","focus_points":[]}', "high")[
        "focus_points"
    ] == [
        "premise",
        "tone",
        "main conflict",
    ]

    assert advisor_utils.normalize_prose_tighten_result("bad json", " Original text ") == {
        "tightened_text": "Original text",
        "rationale": ["LoreVia could not safely tighten this selection yet."],
        "changed": False,
    }
    assert (
        advisor_utils.normalize_prose_tighten_result(
            '{"tightened_text":"","rationale":[]}', "Original"
        )["changed"]
        is False
    )
    assert advisor_utils.normalize_prose_tighten_result(
        '{"tightened_text":"Original","rationale":[]}', "Original"
    ) == {
        "tightened_text": "Original",
        "rationale": ["Trimmed repetition and sharpened sentence flow."],
        "changed": False,
    }

    assert (
        advisor_utils.normalize_proactive_scan_result("plain scan")["overall_note"] == "plain scan"
    )
    scan = advisor_utils.normalize_proactive_scan_result(
        '{"findings":["skip",{"title":"No action","description":"skip"},'
        '{"title":"Bad chapter","description":"Ref is invalid","action_label":"Ask","ask_prompt":"What now?","chapter_ref":"2"}],'
        '"overall_note":""}'
    )
    assert scan == {
        "findings": [
            {
                "severity": "info",
                "type": "future_direction",
                "title": "Bad chapter",
                "description": "Ref is invalid",
                "chapter_ref": None,
                "action_label": "Ask",
                "ask_prompt": "What now?",
            }
        ],
        "overall_note": "Proactive continuity scan could not be parsed.",
    }

    assert (
        advisor_utils.normalize_series_continuity_result("series text")["overall_verdict"]
        == "series text"
    )
    series = advisor_utils.normalize_series_continuity_result(
        '{"continuity_issues":["skip",{"title":"","description":"skip"},'
        '{"title":"Trait shift","description":"Mira changes without setup","source_book":" Book One "}],'
        '"cross_book_opportunities":[{"title":""},'
        '{"title":"Echo the oath","description":"Connect the vow","earlier_book":"Book One","what_to_add":"Name the vow"}],'
        '"thematic_fit":{"score":"strong","notes":" aligns "},'
        '"overall_verdict":" works "}'
    )
    assert series["continuity_issues"][0]["type"] == "cross_book_conflict"
    assert series["continuity_issues"][0]["source_book"] == "Book One"
    assert series["cross_book_opportunities"][0]["title"] == "Echo the oath"
    assert series["thematic_fit"] == {"score": "strong", "notes": "aligns"}
    assert series["overall_verdict"] == "works"

    markdown = advisor_utils.build_continuity_report_markdown(
        title="The Ember Gate",
        chapter_num=7,
        review={
            "overall_verdict": "Revise before drafting chapter eight.",
            "thematic_fit": {"score": "strong", "notes": "The oath motif lands."},
            "continuity_issues": [
                {
                    "title": "Gate memory",
                    "severity": "minor",
                    "type": "event_conflict",
                    "description": "The gate is described as new twice.",
                    "suggestion": "Clarify that this is Mira's first view.",
                }
            ],
            "insertion_opportunities": [
                {
                    "title": "Seed ash key",
                    "target_chapter": 3,
                    "problem": "The key arrives late.",
                    "what_to_add": "Mention ash marks.",
                    "why_here": "The market scene has room.",
                }
            ],
            "grammar_issues": [{"issue": "tense", "original": "was", "fix": "is"}],
            "formatting_notes": ["Indent dialogue consistently."],
        },
        retrieved_passages=[
            {"chapter_num": 2, "chapter_title": "Market", "excerpt": "Mira sees ash."}
        ],
        open_threads=[{"title": "Missing oath", "description": "The vow needs payoff."}],
    )
    assert "# LoreVia Continuity Review Report" in markdown
    assert "### Gate memory" in markdown
    assert "Formatting notes:" in markdown
    assert "Chapter 2" in markdown and "Market" in markdown

    empty_markdown = advisor_utils.build_continuity_report_markdown(
        title="The Ember Gate",
        chapter_num=None,
        review={},
        retrieved_passages=[],
        open_threads=[],
    )
    assert "No continuity conflicts were identified." in empty_markdown
    assert "No insertion opportunities were identified." in empty_markdown
    assert "- No forgotten-thread warnings were active" in empty_markdown
    assert "- No passages were attached to this review." in empty_markdown

    pdf = advisor_utils.build_continuity_report_pdf(markdown, title="The Ember Gate", chapter_num=7)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_intelligence_utils_extract_voice_metrics_and_score_matches():
    assert (
        intelligence_utils.flatten_key_events({"a": ["First", "Second"], "b": "Third"})
        == "First; Second; Third"
    )

    rows = [
        {"name": "Mira", "aliases": ["Captain Vale"]},
        {"name": "", "aliases": []},
    ]
    assert intelligence_utils.build_character_name_candidates(rows)[0]["name_candidates"] == [
        "Mira",
        "Captain Vale",
    ]

    samples = intelligence_utils.extract_dialogue_samples_by_character(
        'Mira whispered, "I can\'t stop now." Joren said, "Perhaps we shall wait?"',
        [
            {"name": "Mira", "aliases": []},
            {"name": "Joren", "aliases": []},
        ],
    )
    assert samples["Mira"] == ["I can't stop now."]
    assert samples["Joren"] == ["Perhaps we shall wait?"]

    mira_metrics = intelligence_utils.compute_voice_metrics(samples["Mira"] + ["I can't stop now."])
    joren_metrics = intelligence_utils.compute_voice_metrics(samples["Joren"])
    assert mira_metrics["sample_dialogue_count"] == 2
    assert mira_metrics["contraction_rate_x1000"] > 0
    assert mira_metrics["signature_phrases"] == ["i can't", "stop now"]
    assert intelligence_utils.compute_voice_metrics([])["sample_dialogue_count"] == 0

    merged = intelligence_utils.merge_voice_profile_metrics(mira_metrics, joren_metrics)
    assert merged["sample_dialogue_count"] == 3
    assert (
        merged["sample_word_count"]
        == mira_metrics["sample_word_count"] + joren_metrics["sample_word_count"]
    )

    score, signals = intelligence_utils.score_voice_match(mira_metrics, joren_metrics)
    assert 0 <= score <= 100
    assert isinstance(signals, list)
    assert intelligence_utils.score_voice_match({}, joren_metrics)[0] == 0


def test_reader_utils_timeline_graph_summary_and_media_helpers():
    assert reader_utils.normalize_timeline_label("  Mira   Vale ") == "mira vale"
    assert reader_utils.is_valid_timeline_character("Mira Vale", "mc", [], "Lead character") is True
    assert reader_utils.is_valid_timeline_character("the castle", None, [], None) is False
    assert (
        reader_utils.timeline_character_detail("Mira", "mc", [], None)
        == "Major character becomes part of the story."
    )
    assert (
        reader_utils.timeline_character_detail("Ash", None, ["The Ash"], None)
        == "Also referred to as The Ash."
    )
    assert reader_utils.dedupe_timeline_events(
        [
            {"chapter_number": 1, "kind": "event", "title": "Gate opens"},
            {"chapter_number": 1, "kind": "event", "title": " gate opens "},
            {"chapter_number": 2, "kind": "event", "title": "Gate opens"},
        ]
    ) == [
        {"chapter_number": 1, "kind": "event", "title": "Gate opens"},
        {"chapter_number": 2, "kind": "event", "title": "Gate opens"},
    ]
    assert reader_utils.timeline_plot_thread_span(None, None, {3, 4, 5}) == (3, 5)
    assert reader_utils.timeline_plot_thread_span(9, None, {3, 4, 5}) is None
    assert reader_utils.timeline_plot_thread_span(1, 2, {3, 4, 5}) is None

    char = SimpleNamespace(
        id=uuid.uuid4(),
        name="Mira Vale",
        role="mc",
        aliases=["Mira"],
        arc_summary="Learns command.",
        personality_tags=["precise"],
        motivations=["protect the gate"],
        fears=[],
        archetype="guardian",
        trait_state={"eyes": "gray"},
        is_manual=False,
        graph_visibility=None,
        first_chapter=1,
    )
    hidden_char = SimpleNamespace(
        id=uuid.uuid4(),
        name="",
        role=None,
        aliases=[],
        arc_summary=None,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
        graph_visibility=None,
        first_chapter=99,
    )
    assert reader_utils.relationship_node_description(
        char, {"hair": "black"}, ["Trusts Joren."]
    ) == ("guardian Learns command. Disposition: precise. Wants: protect the gate. Trusts Joren.")
    assert (
        reader_utils.graph_character_visibility_analysis(char, relationship_count=2)["visible"]
        is True
    )
    assert reader_utils.graph_character_visibility_analysis(hidden_char)["reasons"] == [
        "missing_name"
    ]
    assert reader_utils.character_evidence_score(char)[0] >= 6

    duplicate = SimpleNamespace(
        id=uuid.uuid4(),
        name="Captain Vale",
        role=None,
        aliases=["Mira Vale"],
        arc_summary=None,
        personality_tags=[],
        motivations=[],
        fears=[],
        archetype=None,
        trait_state={},
        is_manual=False,
        graph_visibility=None,
        first_chapter=2,
    )
    canonical, id_map = reader_utils.collapse_graph_characters([char, duplicate])
    assert len(canonical) == 1
    assert id_map[str(duplicate.id)] == str(char.id)

    summary = reader_utils.normalize_summary_response(
        " The gate opens. ",
        ["Gate opens", {"event": "Ward breaks", "impact": "Danger rises"}],
        [{"character": "Mira", "description": "Leads"}],
        [{"clue": "ash key"}],
    )
    assert summary["content"] == " The gate opens. "
    assert summary["key_events"][1]["impact"] == "Danger rises"
    assert reader_utils.strip_json_fence('```json\n{"ok": true}\n```') == '{"ok": true}'
    assert reader_utils.chapter_analysis_status(None) is None
    assert reader_utils.chapter_source_integrity(None) is None
    assert (
        reader_utils.serialize_inline_images(
            [
                {"marker": "[[IMAGE:1]]", "bytes": b"abc", "content_type": "image/png"},
                {"marker": "", "bytes": b"skip"},
            ]
        )[0]["content_base64"]
        == "YWJj"
    )
    assert reader_utils.extract_media_markers("A [[IMAGE:1]] and [[IMAGE:2]]") == [
        "[[IMAGE:1]]",
        "[[IMAGE:2]]",
    ]
    assert reader_utils.merge_media_items(
        [{"marker": "[[IMAGE:1]]", "sort_order": 2}],
        [{"marker": "[[IMAGE:2]]", "sort_order": 1}, {"marker": "[[IMAGE:1]]", "sort_order": 0}],
    ) == [
        {"marker": "[[IMAGE:2]]", "sort_order": 1},
        {"marker": "[[IMAGE:1]]", "sort_order": 2},
    ]
    assert reader_utils.timeline_relationship_detail("Mira", "Joren", "ally", None)[1] == (
        "Their ally dynamic shifts here."
    )
    assert reader_utils.build_timeline_track_payload([{"n": 1}], [], [], [], [])["chapters"] == [
        {"n": 1}
    ]


def test_beta_read_utils_validate_scope_rating_state_and_penalties(monkeypatch):
    monkeypatch.setattr(beta_read_utils.settings, "BETA_READ_MIN_WINDOW_DAYS", 3)
    monkeypatch.setattr(beta_read_utils.settings, "BETA_READ_MAX_WINDOW_DAYS", 30)

    assert beta_read_utils.ensure_timezone(datetime(2026, 1, 1)).tzinfo is not None
    assert beta_read_utils.validate_beta_read_window(7) == 7
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_window(2)
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_window(31)

    book = SimpleNamespace(total_chapters=10)
    assert beta_read_utils.validate_beta_read_scope(
        book,
        scope_kind=BetaReadScopeKind.FULL_BOOK.value,
        chapter_start=None,
        chapter_end=None,
        section_label=None,
    ) == (BetaReadScopeKind.FULL_BOOK.value, None, None, None)
    assert beta_read_utils.validate_beta_read_scope(
        book,
        scope_kind=BetaReadScopeKind.SECTION.value,
        chapter_start=2,
        chapter_end=5,
        section_label="  Act Two  ",
    ) == (BetaReadScopeKind.SECTION.value, 2, 5, "Act Two")
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            book, scope_kind="bad", chapter_start=1, chapter_end=2, section_label=None
        )
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            book,
            scope_kind=BetaReadScopeKind.CHAPTER_RANGE.value,
            chapter_start=9,
            chapter_end=12,
            section_label=None,
        )

    assignment = SimpleNamespace(
        scope_kind=BetaReadScopeKind.CHAPTER_RANGE.value,
        chapter_start=2,
        chapter_end=20,
        submission_metadata={"legacy": True},
        submitted_progress_pct=80,
        submitted_chapters_total=5,
        submitted_chapters_read_count=4,
        submitted_comment_count=3,
        submitted_feedback_item_count=2,
        submitted_answer_count=1,
        final_rating=4.5,
        submitted_rating_sentiment="positive",
        submitted_before_deadline=True,
        late_feedback=False,
        state=BetaReadAssignmentState.ACTIVE.value,
        expires_at=datetime(2026, 1, 10, tzinfo=UTC),
        revoked_at=None,
        revoked_reason=None,
        started_at=None,
        completed_at=None,
        submitted_at=None,
        disqualified_at=None,
        disqualified_reason=None,
        missed_at=None,
    )
    assert beta_read_utils.assignment_scope_bounds(assignment, 12) == (2, 12)
    assert beta_read_utils.normalize_beta_read_questions([" First? ", "first?", "", "Second?"]) == [
        "First?",
        "Second?",
    ]
    assert beta_read_utils.normalize_feedback_kind("scene reaction") == "scene_reaction"
    assert beta_read_utils.normalize_author_feedback_item_status("task created") == "task_created"
    assert beta_read_utils.normalize_beta_read_rating(4.5) == 4.5
    assert beta_read_utils.beta_read_rating_sentiment(4.5) == "positive"
    assert beta_read_utils.beta_read_rating_sentiment(3) == "neutral"
    assert beta_read_utils.beta_read_rating_sentiment(1) == "negative"
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_questions(["x" * 301])
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_feedback_kind("other")
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_author_feedback_item_status("missing")
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_rating(4.25)

    metadata = beta_read_utils.beta_feedback_item_author_metadata(
        SimpleNamespace(
            metadata_json={
                "author_status": "resolved",
                "author_task_id": " task-1 ",
                "author_updated_at": "2026-01-01T00:00:00Z",
            }
        )
    )
    assert metadata["author_status"] == "resolved"
    assert metadata["author_task_id"] == "task-1"

    snapshot = beta_read_utils.beta_submission_snapshot(assignment)
    assert snapshot["progress_pct"] == 80.0
    beta_read_utils.apply_beta_submission_snapshot(
        assignment, {"progress_pct": 100, "late_feedback": True}
    )
    assert assignment.submitted_progress_pct == 100.0
    assert assignment.late_feedback is True

    now = datetime(2026, 1, 5, tzinfo=UTC)
    assert beta_read_policy_utils.submission_is_late(assignment, now=now) is False
    beta_read_utils.assert_valid_beta_transition(
        BetaReadAssignmentState.ACTIVE.value,
        BetaReadAssignmentState.IN_PROGRESS.value,
    )
    with pytest.raises(HTTPException):
        beta_read_utils.assert_valid_beta_transition(
            BetaReadAssignmentState.ACTIVE.value,
            BetaReadAssignmentState.SUBMITTED.value,
        )
    beta_read_utils.set_beta_assignment_state(
        assignment,
        BetaReadAssignmentState.REVOKED.value,
        now=now,
        revoked_reason="author_cancelled",
    )
    assert assignment.state == BetaReadAssignmentState.REVOKED.value
    assert assignment.revoked_reason == "author_cancelled"
    assert beta_read_policy_utils.beta_view_bucket(assignment, now=now) == "missed"


def test_book_utils_runtime_normalizers_and_workspace_helpers():
    assert book_text._normalize_unicode_replacements("A\u2014B\u2026") == "A--B..."
    assert book_text._clean_text("<b>Mira</b>") == "Mira"
    assert book_text._clean_optional_text("  ") is None
    assert chapter_titles._count_words("one  two\nthree") == 3
    assert chapter_titles.normalize_chapter_title(" The Gate ") == "The Gate"
    assert chapter_titles.chapter_title_is_placeholder("Chapter IX") is True
    assert chapter_titles.chapter_title_is_placeholder("The Ash Gate", chapter_number=3) is False
    assert (
        chapter_titles.build_chapter_title_from_summary(
            "The ash gate opens under the city.",
            key_events=[{"event_title": "Ward breaks below"}],
        )
        == "Ward Breaks Below"
    )
    with pytest.raises(HTTPException):
        chapter_titles.normalize_chapter_title("one two three four five")

    assert normalization.normalize_book_work_type(" SCREENPLAY ") == "screenplay"
    assert normalization.normalize_book_work_type(None, default="other") == "other"
    with pytest.raises(HTTPException):
        normalization.normalize_book_work_type("unknown", default="other")
    assert normalization.detect_upload_format("draft.FOUNTAIN") == "fountain"
    assert normalization.infer_work_type_from_filename("draft.fountain") == "screenplay"
    assert normalization.resolve_upload_format_and_work_type("novel.docx", None) == (
        "docx",
        "novel",
    )
    assert normalization.resolve_upload_format_and_work_type("script.pdf", "screenplay") == (
        "pdf",
        "screenplay",
    )
    with pytest.raises(HTTPException):
        normalization.resolve_upload_format_and_work_type("novel.docx", "screenplay")
    assert normalization.upload_filename_for_format("txt") == "upload.txt"
    assert normalization.story_unit_name("screenplay", plural=True, lowercase=True) == "scenes"
    assert normalization.story_unit_label("screenplay", 4, index_format="roman-upper") == "Scene IV"
    assert normalization.chapter_kind_label("part", 2) == "Part"
    assert normalization.normalize_chapter_kind(" ACT ") == "chapter"

    assert processing.normalize_processing_timestamp(datetime(2026, 1, 1, tzinfo=UTC)).startswith(
        "2026-01-01"
    )
    assert (
        processing.normalize_public_processing_stage("ready", None, is_fully_ready=True) == "ready"
    )
    assert processing.normalize_public_processing_stage("processing", "extracting") == "extracting"
    assert processing.processing_retry_available("failed", None, [], "boom") is True
    assert processing.normalize_reprocess_metadata(
        {
            "auto_reprocess_enabled": True,
            "pending_chapters": ["1", 2, "bad", 2],
            "last_manual_chapter_number": "4",
        }
    )["pending_chapters"] == [2]

    workspace = writer_workspace.normalize_writer_workspace(
        {
            "word_count_goals": {
                "book_target": "90000",
                "chapter_target": "bad",
                "session_target": 1200,
            },
            "goal_calendar": [
                {
                    "id": "g1",
                    "title": " Draft midpoint ",
                    "due_date": "2026-06-15",
                    "quota_value": "500",
                    "quota_unit": "words",
                },
                {"title": "", "due_date": "bad"},
            ],
            "revision_board": {"items": [{"item_id": "a", "status": "fixed"}]},
        }
    )
    assert workspace["word_count_goals"]["book_target"] is None
    assert workspace["word_count_goals"]["chapter_target"] is None
    assert workspace["word_count_goals"]["session_target"] == 1200
    assert workspace["goal_calendar"][0]["title"] == "Draft midpoint"
    assert workspace["revision_board"]["items"][0]["status"] == "fixed"

    assert (
        story_health.estimate_readability("Short sentence. Another short sentence.")["words"] == 5
    )
    assert collaboration.normalize_collaboration_email(" USER@Example.COM ") == "user@example.com"
    assert collaboration.normalize_collaboration_role("co_writer") == "co_writer"
    with pytest.raises(HTTPException):
        collaboration.normalize_collaboration_role("co writer")
    assert collaboration.collaboration_role_workspace_shell("reader_only") == "reader"
    assert vault.normalize_vault_note_source("character_bible") == "character_bible"
    assert vault.normalize_vault_note_path(" Folder / Note.md ") == "Folder/Note.md"
    assert vault.vault_note_title("Folder/Note.md") == "Note"
    assert vault.vault_note_folder("Folder/Note.md") == "Folder"
    assert vault.extract_wiki_links("See [[Mira Vale|Mira]] and [[Joren]].") == [
        {"target": "Mira Vale", "alias": "Mira"},
        {"target": "Joren", "alias": "Joren"},
    ]
    assert vault.extract_wiki_tags("#World/City #bad") == ["world/city", "bad"]


def test_book_utils_revision_vault_scene_and_collaboration_branches():
    state_map = revision_decisions._revision_board_state_map(
        {
            "revision_board": {
                "items": [
                    {
                        "item_id": "rev-1",
                        "status": "fixed",
                        "assigned_version_id": "v1",
                        "task_id": "task-9",
                    },
                    {"item_id": "", "status": "ignored"},
                    "bad",
                ]
            }
        }
    )
    overlay = revision_decisions._overlay_revision_state(
        {"id": "rev-1", "status": "pending", "assigned_version_id": None, "task_id": None},
        state_map,
    )
    assert overlay["status"] == "fixed"
    assert overlay["assigned_version_id"] == "v1"
    assert (
        revision_analysis._severity_from_text("This contradiction breaks earlier evidence")
        == "high"
    )
    assert revision_analysis._severity_from_text("A subtle inconsistent reference") == "medium"
    assert revision_analysis._flatten_summary_points({"a": [" one ", {"nested": "two"}]}) == [
        "one",
        "{'nested': 'two'}",
    ]

    before = "Mira carries the ash key through the gate. Joren watches."
    after = "Joren carries the glass map through the tower."
    summary, terms = revision_analysis._build_revision_change_summary(
        before_text=before,
        after_text=after,
        unit_label="Chapter 2",
        character_names={"Mira", "Joren"},
        thread_terms={"ash key"},
        world_terms={"gate"},
    )
    assert "removed or weakened" in summary
    assert "ash key" in terms
    assert (
        revision_analysis._describe_narration_shift(
            {
                "pov_mode": "first-person",
                "avg_sentence_length": 8,
                "exclamation_rate": 0,
                "semicolon_rate": 0,
            },
            {
                "pov_mode": "third-person",
                "avg_sentence_length": 8,
                "exclamation_rate": 0,
                "semicolon_rate": 0,
            },
        )
        == "Narration shifts from first-person anchoring into third-person anchoring."
    )
    assert (
        revision_analysis._describe_narration_shift(
            {
                "pov_mode": "mixed",
                "avg_sentence_length": 4,
                "exclamation_rate": 0,
                "semicolon_rate": 0,
            },
            {
                "pov_mode": "mixed",
                "avg_sentence_length": 15,
                "exclamation_rate": 0,
                "semicolon_rate": 0,
            },
        )
        == "Narration suddenly becomes much denser or much shorter than the surrounding chapters."
    )

    timeline = revision_analysis._build_knowledge_timeline(
        knowledge_matrix=[
            {
                "fact": "Ash key exists",
                "entries": [
                    {"character_name": "Mira", "chapter_learned": 2, "source": "summary"},
                    {"character_name": "Joren", "chapter_learned": None, "source": "unknown"},
                ],
                "warning": "Joren never learned it",
            }
        ],
        chapter_numbers=[1, 2, 3],
    )
    assert timeline[0]["rows"][0]["cells"] == [
        {"chapter_number": 1, "state": "unknown"},
        {"chapter_number": 2, "state": "learned"},
        {"chapter_number": 3, "state": "known"},
    ]

    items = [
        {
            "category": "confusion",
            "title": "Lore term unclear",
            "description": "world magic term lacks setup",
        },
        {
            "category": "voice",
            "title": "Chemistry weak",
            "description": "relationship emotion falls flat",
        },
    ]
    genre_checks = revision_analysis._select_genre_checks("Epic Fantasy Romance", items)
    assert [check["label"] for check in genre_checks] == ["Fantasy", "Romance", "Epic Series"]
    assert genre_checks[0]["findings"][0]["title"] == "Lore term unclear"

    graph = vault.build_vault_graph(
        [
            {"path": "Characters/Mira.md", "content": "Links to [[Ash Gate|the gate]] #Cast"},
            {"path": "Places/Ash Gate.md", "content": "Backlink to [[Mira]]."},
            {"path": "Loose.md", "content": "[[Missing]] [[Ash Gate|the gate]]"},
        ]
    )
    assert {node["title"]: node["folder"] for node in graph["nodes"]}["Mira"] == "Characters"
    assert {edge["source"] for edge in graph["edges"]} == {
        "Characters/Mira.md",
        "Places/Ash Gate.md",
        "Loose.md",
    }
    assert vault.extract_wiki_references("![[Scene One#Beat|Opening]] [[Target]]") == [
        {"target": "Scene One", "alias": "Opening", "link_type": "embed"},
        {"target": "Target", "alias": "Target", "link_type": "reference"},
    ]
    with pytest.raises(HTTPException):
        vault.normalize_vault_note_path("../bad.md")
    with pytest.raises(HTTPException):
        vault.normalize_vault_note_source("drafts")

    assert notes._annotation_category(None) == "general"
    assert notes._annotation_status(None) == "open"
    assert notes._annotation_visibility(None) == "shared"
    assert (
        notes._annotation_actor_label(SimpleNamespace(username="", email="writer@example.com"))
        == "writer"
    )
    with pytest.raises(HTTPException):
        notes._annotation_category("not-a-real-category")
    with pytest.raises(HTTPException):
        notes._annotation_status("closed")
    with pytest.raises(HTTPException):
        notes._annotation_visibility("public")

    scope = collaboration.normalize_collaboration_scope({"chapter_start": "2", "chapter_end": "4"})
    assert scope["chapter_start"] == 2
    assert scope["chapter_end"] == 4
    permissions = collaboration.normalize_collaboration_permissions(
        {"can_export": True},
        role="commenter",
        scope=scope,
    )
    assert permissions["can_comment"] is True
    assert permissions["can_export"] is True
    assert permissions["can_view_selected_chapters_only"] is True
    collaborator = SimpleNamespace(
        role="editor",
        scope={"chapter_start": 2, "chapter_end": 4, "character_bible": True},
        permissions={"can_export": True, "can_comment": True},
    )
    payload = collaboration.collaboration_scope_payload(collaborator)
    assert payload["character_bible"] is True
    assert collaboration_access.collaboration_allows_chapter(collaborator, 3) is True
    assert collaboration_access.collaboration_allows_chapter(collaborator, 5) is False
    assert collaboration_access.collaboration_can_export(collaborator) is True
    with pytest.raises(HTTPException):
        collaboration.normalize_collaboration_email("bad")
    with pytest.raises(HTTPException):
        collaboration.normalize_collaboration_scope({"chapter_start": 5, "chapter_end": 2})

    scene_text = """## Scene 1 - Gate opens

POV: Mira
Location: Ash Gate
Characters:
- Mira
- Joren
Goals:
- Open the lock
Conflict: The ward resists.
Summary: The team reaches the threshold.
---

Mira raises the ash key."""
    metadata = scene_metadata.extract_scene_metadata(scene_text)
    assert metadata["characters"] == ["Mira", "Joren"]
    assert metadata["goals"] == ["Open the lock"]
    normalized_metadata = scene_metadata.normalize_scene_metadata(
        {"tags": [" Gate ", "Gate"], "mood": "tense", "summary": "Location: Tower"},
        description="Fallback summary",
    )
    assert normalized_metadata["tags"] == ["Gate"]
    assert normalized_metadata["mood"] == ["tense"]
    assert normalized_metadata["location"] == "Tower"
    assert (
        scene_metadata.build_novel_scene_path(chapter_number=3, sort_order=7, title="Gate Opens!")
        == "scenes/chapter-03/007-gate-opens.md"
    )
    assert (
        scene_metadata.build_novel_scene_path(chapter_number=None, sort_order=1, title="")
        == "scenes/unassigned/001-scene.md"
    )
    stripped_planning = scene_metadata.strip_scene_planning_block(scene_text, title="Gate opens")
    assert "POV:" not in stripped_planning
    assert stripped_planning.endswith("Mira raises the ash key.")
    import_text = scene_metadata.build_scene_chapter_import_text(
        {
            "title": "Gate opens",
            "description": "A threshold scene",
            "body": scene_text,
            "metadata": metadata,
        },
        scene_number=2,
    )
    assert "## Scene 2 - Gate opens" in import_text
    assert "Characters:\n- Mira\n- Joren" in import_text
    assert import_text.endswith("Mira raises the ash key.")
    assert (
        scene_metadata.build_workspace_chapter_text_from_scenes(
            [
                {
                    "title": "Gate opens",
                    "description": "A threshold scene",
                    "body": scene_text,
                    "metadata": metadata,
                },
                SimpleNamespace(
                    title="Aftermath", description=None, body="They cross.", scene_metadata={}
                ),
            ]
        ).count("***")
        == 1
    )
    assert (
        scene_metadata.chapter_body_needs_scene_workspace_fallback("III", chapter_number=3) is True
    )
    assert (
        scene_metadata.chapter_body_needs_scene_workspace_fallback(
            "A real scene unfolds here.", chapter_number=3
        )
        is False
    )
    stripped = scene_metadata.strip_scene_metadata_from_manuscript_text(
        scene_text + "\n\n***\n\nSecond body."
    )
    assert "POV:" not in stripped
    assert stripped.endswith("Mira raises the ash key.\n\n***\n\nSecond body.")
    candidates = scene_metadata.extract_novel_scene_candidates(
        text="# Opening\nMira enters.\n\n***\n\nJoren follows.",
        chapter_number=4,
        source="unit",
    )
    assert [candidate["title"] for candidate in candidates] == ["Opening", "Joren follows."]
    assert candidates[0]["status"] == "assigned"
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())
    assert scene_ordering.normalize_scene_reorder_ids([first_id, second_id]) == [
        uuid.UUID(first_id),
        uuid.UUID(second_id),
    ]
    with pytest.raises(HTTPException):
        scene_ordering.normalize_scene_reorder_ids([first_id, first_id])
    scenes = [SimpleNamespace(sort_order=10), SimpleNamespace(sort_order=20)]
    scene_ordering._apply_sequential_scene_sort_order(scenes)
    assert [scene.sort_order for scene in scenes] == [1, 2]
    scene_out = scene_serialization._scene_out(
        SimpleNamespace(
            id=uuid.uuid4(),
            book_id=uuid.uuid4(),
            chapter_id=None,
            chapter_number=None,
            title="Loose scene",
            description="A loose scene",
            body="Body",
            html_body="<p>Body</p>",
            scene_metadata={"tags": ["draft"]},
            path="scenes/unassigned/001-loose-scene.md",
            status="unassigned",
            sort_order=1,
            source="manual",
            origin_chapter_number=None,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        tags=["draft", "important"],
    )
    assert scene_out["metadata"]["tags"] == ["draft", "important"]


def test_runtime_public_beta_export_and_import_helpers_cover_edge_branches(monkeypatch):
    now = datetime(2026, 1, 10, tzinfo=UTC)
    owner_id = uuid.uuid4()
    book_id = uuid.uuid4()
    public_book = SimpleNamespace(
        id=book_id,
        user_id=owner_id,
        is_public=True,
        hidden_at=None,
        archived_at=None,
        public_status="published",
        moderation_status="reported",
        source_kind="user_public_share",
        public_share_status="approved",
        public_slug="lantern-gate",
        title="Lantern Gate",
        author="A Writer",
        genre="Fantasy",
        public_description="A public draft.",
        format="manual",
        work_type="novel",
        status="ready",
        content_source_type="user_original",
        source_title=None,
        source_author=None,
        source_public_domain_note=None,
        source_url=None,
        total_chapters=4,
        copyright_warning=False,
        created_at=now,
        published_at=now,
        public_updated_at=now,
    )

    assert serialization.can_view_public_book(public_book) is True
    public_book.public_status = "pending_review"
    assert serialization.can_view_public_book(public_book) is False
    assert "waiting for review" in serialization.public_visibility_notice(public_book)
    public_book.public_status = "published"
    public_book.moderation_status = "under_review"
    assert "hidden from public view" in serialization.public_visibility_notice(public_book)
    public_book.moderation_status = "clean"
    assert (
        serialization.can_owner_or_admin_view_hidden_book(SimpleNamespace(id=owner_id), public_book)
        is True
    )
    assert (
        serialization.public_catalog_kind(public_book) == public_utils.USER_PUBLIC_SHARE_SOURCE_KIND
    )
    assert (
        serialization.get_public_share_status(public_book)
        == public_utils.PUBLIC_SHARE_STATUS_APPROVED
    )

    monkeypatch.setattr(settings, "APP_URL", "https://www.lorevia.example")
    assert (
        moderation.validate_public_content_report_target(
            public_book,
            f"https://lorevia.example/books/{public_book.public_slug}",
        )
        == f"https://lorevia.example/books/{public_book.public_slug}"
    )
    with pytest.raises(HTTPException):
        moderation.validate_public_content_report_target(
            public_book, "https://evil.example/books/lantern-gate"
        )
    with pytest.raises(HTTPException):
        moderation.ensure_content_source_allowed_for_user(SimpleNamespace(), "licensed")
    with pytest.raises(HTTPException):
        moderation.ensure_report_type_supported("bad")

    public_out = serialization.build_public_book_out(
        public_book, author_username="mira", active_forum_post_id="post-1"
    )
    assert public_out.creator_display_name == "mira"
    assert public_out.active_forum_post_id == "post-1"
    metadata = ranking_core.build_public_ranking_metadata(
        surface=ranking_constants.PUBLIC_RANKING_SURFACE_BETA,
        ranking_key=ranking_constants.PUBLIC_RANKING_MOST_POPULAR,
        time_window=ranking_constants.PUBLIC_RANKING_WINDOW_WEEKLY,
        position=2,
        score=8.5,
        primary_timestamp=now,
    )
    assert metadata.label == "Most popular this week"
    assert "reader activity" in metadata.supporting_note
    assert ranking_core.public_ranking_window_start(time_window="all_time", now=now) is None
    with pytest.raises(HTTPException):
        ranking_core.normalize_public_ranking_key("unknown")

    beta_book = SimpleNamespace(total_chapters=8)
    assert beta_read_utils.validate_beta_read_scope(
        beta_book,
        scope_kind="section",
        chapter_start=2,
        chapter_end=4,
        section_label=" Act Two ",
    ) == ("section", 2, 4, "Act Two")
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            beta_book, scope_kind="bad", chapter_start=None, chapter_end=None, section_label=None
        )
    questions = beta_read_utils.normalize_beta_read_questions(
        ["What confused you?", " what confused you? ", "", "Favorite beat?"]
    )
    assert questions == ["What confused you?", "Favorite beat?"]
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_rating(4.25)
    assert beta_read_utils.normalize_beta_read_rating("4.5") == 4.5
    assert beta_read_utils.beta_read_rating_sentiment(4.5) == "positive"

    assignment = SimpleNamespace(
        scope_kind="chapter_range",
        chapter_start=2,
        chapter_end=20,
        starts_at=now + timedelta(days=1),
        expires_at=now + timedelta(days=7),
        state=BetaReadAssignmentState.ACTIVE.value,
        submission_metadata={"note": "old"},
        submitted_progress_pct=75,
        submitted_chapters_total=4,
        submitted_chapters_read_count=3,
        submitted_comment_count=2,
        submitted_feedback_item_count=1,
        submitted_answer_count=1,
        final_rating=4.5,
        submitted_rating_sentiment="positive",
        submitted_before_deadline=True,
        late_feedback=False,
    )
    assert beta_read_utils.assignment_scope_bounds(assignment, 8) == (2, 8)
    snapshot = beta_read_utils.beta_submission_snapshot(assignment)
    assert snapshot["progress_pct"] == 75.0
    beta_read_utils.apply_beta_submission_snapshot(
        assignment, {"progress_pct": 100, "late_feedback": True}
    )
    assert assignment.submitted_progress_pct == 100
    assert assignment.late_feedback is True
    assert beta_read_policy_utils.beta_view_bucket(assignment, now=now) == "scheduled"
    assert beta_read_policy_utils.beta_status_label(assignment, now=now) == "Scheduled"
    assert beta_read_utils.beta_primary_action(assignment, now=now) == "View"
    beta_read_utils.set_beta_assignment_state(
        assignment, BetaReadAssignmentState.REVOKED.value, now=now, revoked_reason="scope_changed"
    )
    assert assignment.revoked_reason == "scope_changed"
    user = SimpleNamespace(consecutive_missed_beta_reads=2)
    assert "2 beta reads" in beta_read_utils.penalty_warning_for_user(user)

    assert export_utils.export_filename_base(" A/B: Draft! ", fallback="book") == "AB-Draft"
    assert export_utils.export_font_label("old_style") == "Standard Serif"
    assert "LoreVia Font Notice" in export_utils.export_font_notice("garamond")
    chapters = [
        {"number": 1, "title": "Prologue", "text": "First paragraph.\n\n***\n\nSecond paragraph."},
        {"number": 2, "title": "Chapter 2", "text": "Two words"},
    ]
    front = export_utils._manuscript_front_matter(
        "Lantern Gate",
        chapters,
        {
            "pen_name": "M. Vale",
            "header_title": "",
            "include_epigraph": True,
            "epigraph": "A line.",
        },
    )
    assert front["display_author"] == "M. Vale"
    assert front["header_last_name"] == "Vale"
    assert export_utils._approx_word_count_label(249) == "Approx. 200 words"
    assert export_utils._chapter_body_blocks(chapters[0]["text"]) == [
        ("paragraph", "First paragraph."),
        ("scene_break", "***"),
        ("paragraph", "Second paragraph."),
    ]
    assert export_utils._chapter_heading_lines(chapters[0], "roman-upper") == ("Prologue", None)
    assert export_utils._manuscript_toc_label(chapters[1], "roman-upper") == "Chapter II: Chapter 2"
    assert export_utils._scene_heading_lines(
        {"chapter_number": 3, "title": "Gate opens"}, 2, "alpha-upper"
    ) == (
        "Scene #2 (Chapter C)",
        "Gate opens",
    )

    long_text = " ".join(["word"] * 6)
    normalized = book_imports.normalize_imported_chapters(
        [
            {
                "title": " Long Chapter ",
                "text": long_text,
                "html": "<p>Long Chapter</p>",
                "images": [{"marker": "[[IMAGE:one]]"}, {"marker": "[[IMAGE:two]]"}],
            }
        ],
        chapter_number=None,
        start_number=5,
        replace_existing=False,
        chunk_long_documents=True,
    )
    assert normalized[0]["number"] == 5
    assert normalized[0]["title"] == "Long Chapter"
    assert book_imports._filter_import_images_for_text(
        "Text [[IMAGE:one]]", normalized[0]["images"]
    ) == [{"marker": "[[IMAGE:one]]"}]
    assert len(book_imports.split_long_document("one two", max_words=10)) == 1
    assert continuity.as_bool(" yes ") is True


def test_book_utils_continuity_flag_helpers_detect_trait_changes():
    character_id = uuid.uuid4()
    previous = SimpleNamespace(
        character_id=character_id,
        at_chapter=2,
        trait_snapshot={"eyes": {"value": "green"}, "hair": "black"},
    )
    current = SimpleNamespace(
        character_id=character_id,
        at_chapter=5,
        trait_snapshot={"eyes": {"value": "blue"}, "hair": "black"},
    )

    chapter_numbers, states = continuity._map_chapter_consistency_state_history([previous])
    assert chapter_numbers == [2]
    assert continuity._latest_state_before_chapter(chapter_numbers, states, 5) is previous
    assert continuity._latest_state_before_chapter(chapter_numbers, states, 1) is None
    flags = continuity._detect_continuity_flags_from_rows(
        work_type="novel",
        chapter_number=5,
        rows=[(current, "Mara")],
        prior_states_by_character={character_id: (chapter_numbers, states)},
    )
    assert flags == ["Mara: eye description changed from 'green' to 'blue' since chapter 2."]
    assert character_cards._trait_value({"value": "  silver "}) == "silver"
    assert character_cards._trait_value(["bad"]) is None


def test_beta_read_validation_state_and_penalty_branches(monkeypatch):
    now = datetime(2026, 1, 10, tzinfo=UTC)
    book = SimpleNamespace(total_chapters=5)

    assert beta_read_utils.validate_beta_read_scope(
        book,
        scope_kind="full_book",
        chapter_start=None,
        chapter_end=None,
        section_label=None,
    ) == ("full_book", None, None, None)
    assert beta_read_utils.validate_beta_read_scope(
        book,
        scope_kind="chapter_range",
        chapter_start=2,
        chapter_end=4,
        section_label=None,
    ) == ("chapter_range", 2, 4, None)

    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            book, scope_kind="chapter_range", chapter_start=None, chapter_end=4, section_label=None
        )
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            book, scope_kind="chapter_range", chapter_start=4, chapter_end=2, section_label=None
        )
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            book, scope_kind="chapter_range", chapter_start=1, chapter_end=7, section_label=None
        )
    with pytest.raises(HTTPException):
        beta_read_utils.validate_beta_read_scope(
            book, scope_kind="section", chapter_start=1, chapter_end=2, section_label=" "
        )

    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_questions(["x" * 301])
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_questions([f"Question {index}?" for index in range(13)])
    assert beta_read_utils.normalize_feedback_kind(" Scene Reaction ") == "scene_reaction"
    assert beta_read_utils.normalize_author_feedback_item_status("task created") == "task_created"
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_feedback_kind("bad")
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_author_feedback_item_status("bad")
    assert beta_read_utils.beta_feedback_item_author_metadata(
        SimpleNamespace(
            metadata_json={
                "author_status": "resolved",
                "author_task_id": " task-1 ",
                "author_updated_at": "bad",
            }
        )
    ) == {"author_status": "resolved", "author_task_id": "task-1", "author_updated_at": None}

    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_rating(None)
    with pytest.raises(HTTPException):
        beta_read_utils.normalize_beta_read_rating(6)
    assert beta_read_utils.beta_read_rating_sentiment(3.0) == "neutral"
    assert beta_read_utils.beta_read_rating_sentiment(1.5) == "negative"
    assert beta_read_utils.beta_read_rating_sentiment(None) is None

    assignment = SimpleNamespace(
        state=BetaReadAssignmentState.ACTIVE.value,
        starts_at=now - timedelta(days=1),
        expires_at=now - timedelta(hours=1),
    )
    assert beta_read_policy_utils.submission_is_late(assignment, now) is True
    assert beta_read_policy_utils.beta_view_bucket(assignment, now=now) == "missed"
    assert beta_read_policy_utils.beta_status_label(assignment, now=now) == "Expired"
    assert beta_read_utils.beta_primary_action(assignment, now=now) == "View"
    with pytest.raises(HTTPException):
        beta_read_utils.assert_valid_beta_transition(
            BetaReadAssignmentState.ACTIVE.value, BetaReadAssignmentState.COMPLETED.value
        )

    scheduled = SimpleNamespace(
        state=BetaReadAssignmentState.ACTIVE.value,
        starts_at=now + timedelta(days=1),
        expires_at=now + timedelta(days=4),
    )
    assert beta_read_policy_utils.beta_view_bucket(scheduled, now=now) == "scheduled"
    assert beta_read_policy_utils.beta_status_label(scheduled, now=now) == "Scheduled"
    assert beta_read_utils.beta_primary_action(scheduled, now=now) == "View"

    for state, expected_label, expected_action, expected_bucket in [
        (BetaReadAssignmentState.ACTIVE.value, "Not started", "Start", "active"),
        (BetaReadAssignmentState.IN_PROGRESS.value, "In progress", "Continue", "active"),
        (
            BetaReadAssignmentState.READY_TO_SUBMIT.value,
            "Ready to submit",
            "Submit feedback",
            "active",
        ),
        (BetaReadAssignmentState.SUBMITTED.value, "Submitted", "View", "completed"),
        (BetaReadAssignmentState.COMPLETED.value, "Completed", "View", "completed"),
        (BetaReadAssignmentState.REVOKED.value, "Revoked", "View", "missed"),
        (BetaReadAssignmentState.DISQUALIFIED.value, "Disqualified", "View", "missed"),
        (BetaReadAssignmentState.EXPIRED.value, "Expired", "View", "missed"),
        (BetaReadAssignmentState.MISSED.value, "Missed", "View", "missed"),
    ]:
        item = SimpleNamespace(
            state=state,
            starts_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=1),
        )
        assert beta_read_policy_utils.beta_status_label(item, now=now) == expected_label
        assert beta_read_utils.beta_primary_action(item, now=now) == expected_action
        assert beta_read_policy_utils.beta_view_bucket(item, now=now) == expected_bucket
    unknown = SimpleNamespace(
        state="custom_state", starts_at=now, expires_at=now + timedelta(days=1)
    )
    assert beta_read_policy_utils.beta_status_label(unknown, now=now) == "Custom State"

    stateful = SimpleNamespace(state=BetaReadAssignmentState.ACTIVE.value)
    beta_read_utils.set_beta_assignment_state(
        stateful, BetaReadAssignmentState.EXPIRED.value, now=now
    )
    assert stateful.missed_reason == "deadline_expired"
    stateful = SimpleNamespace(state=BetaReadAssignmentState.SUBMITTED.value)
    beta_read_utils.set_beta_assignment_state(
        stateful, BetaReadAssignmentState.DISQUALIFIED.value, now=now
    )
    assert stateful.disqualified_reason == "submission_ineligible"
    stateful = SimpleNamespace(state=BetaReadAssignmentState.SUBMITTED.value)
    beta_read_utils.set_beta_assignment_state(
        stateful, BetaReadAssignmentState.COMPLETED.value, now=now
    )
    assert stateful.completed_at == now

    monkeypatch.setattr(beta_read_utils.settings, "BETA_READ_MISSED_PENALTY_THRESHOLD", 3)
    user = SimpleNamespace(
        consecutive_missed_beta_reads=0,
        beta_read_penalty_status=None,
        beta_read_penalty_required_at=None,
    )
    assert beta_read_utils.penalty_warning_for_user(user) is None
    beta_read_utils.apply_missed_beta_read_penalty(user, now=now)
    assert user.beta_read_penalty_status == beta_read_utils.PENALTY_STATUS_WARNING
    beta_read_utils.apply_missed_beta_read_penalty(user, now=now)
    assert user.beta_read_penalty_status == beta_read_utils.PENALTY_STATUS_STRONG_WARNING
    beta_read_utils.apply_missed_beta_read_penalty(user, now=now)
    assert user.beta_read_penalty_status == beta_read_utils.PENALTY_STATUS_PENALTY_REQUIRED
    beta_read_utils.reset_missed_beta_read_penalty(user)
    assert user.consecutive_missed_beta_reads == 0
    assert user.beta_read_penalty_status == beta_read_utils.PENALTY_STATUS_NONE


@pytest.mark.asyncio
async def test_beta_read_progress_feedback_and_question_helpers(monkeypatch):
    book_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    reader_id = uuid.uuid4()
    author_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id, total_chapters=5)
    assignment = SimpleNamespace(
        id=assignment_id,
        book_id=book_id,
        author_user_id=author_id,
        reader_user_id=reader_id,
        scope_kind=BetaReadScopeKind.CHAPTER_RANGE.value,
        chapter_start=2,
        chapter_end=4,
        required_progress_pct=60,
        required_comment_count=5,
        required_feedback_item_count=4,
        state=BetaReadAssignmentState.ACTIVE.value,
    )
    progress = SimpleNamespace(chapters_read=[1, 2, 4, 5], current_chapter=4)

    class ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

        def scalar_one_or_none(self):
            return self.value

    class ProgressDb:
        def __init__(self):
            self.values = [2, 5, 1, 3, 2]

        async def get(self, model, requested_id):
            return book if requested_id == book_id else None

        async def execute(self, statement):
            return ScalarResult(self.values.pop(0))

    snapshot = await beta_read_utils._assignment_progress_snapshot(
        ProgressDb(),
        assignment=assignment,
        progress=progress,
    )
    assert snapshot["chapters_total"] == 3
    assert snapshot["chapters_read_count"] == 2
    assert snapshot["progress_pct"] == 66.7
    assert snapshot["comment_count"] == 5
    assert beta_read_utils._requirements_met(assignment, snapshot) is True
    assert beta_read_utils._requirements_met(assignment, {**snapshot, "comment_count": 4}) is False

    context_snapshot = beta_read_progress_utils._assignment_progress_snapshot_from_context(
        assignment,
        book=book,
        progress=SimpleNamespace(chapters_read=[], current_chapter=3),
        question_count=1,
        feedback_item_count=2,
        answer_count=1,
        note_comment_count=2,
        chapter_comment_count=1,
    )
    assert context_snapshot["chapters_read_count"] == 2
    assert context_snapshot["comment_count"] == 3

    async def fake_list_beta_read_questions(db, *, assignment_id):
        return [SimpleNamespace(prompt="Existing?"), *getattr(db, "added", [])]

    class QuestionDb:
        def __init__(self):
            self.added = []
            self.committed = False

        def add(self, question):
            self.added.append(question)

        async def commit(self):
            self.committed = True

    monkeypatch.setattr(beta_read_utils, "list_beta_read_questions", fake_list_beta_read_questions)
    question_db = QuestionDb()
    questions = await beta_read_utils.append_beta_read_questions(
        question_db,
        assignment=SimpleNamespace(
            id=assignment_id,
            book_id=book_id,
            author_user_id=author_id,
            state=BetaReadAssignmentState.IN_PROGRESS.value,
        ),
        questions=["Existing?", "New question?", " new question? ", "Another?"],
    )
    assert question_db.committed is True
    assert [question.prompt for question in question_db.added] == ["New question?", "Another?"]
    assert [question.prompt for question in questions][-2:] == ["New question?", "Another?"]
    with pytest.raises(HTTPException):
        await beta_read_utils.append_beta_read_questions(
            QuestionDb(),
            assignment=SimpleNamespace(
                id=assignment_id, state=BetaReadAssignmentState.MISSED.value
            ),
            questions=["Late?"],
        )

    scene_id = uuid.uuid4()
    question_id = uuid.uuid4()
    scene = SimpleNamespace(id=scene_id, book_id=book_id, chapter_number=3)
    question = SimpleNamespace(id=question_id, assignment_id=assignment_id)

    class LookupDb:
        async def get(self, model, requested_id):
            model_name = getattr(model, "__name__", "")
            if model_name == "NovelScene":
                return scene if requested_id == scene_id else None
            if model_name == "BetaReadQuestion":
                return question if requested_id == question_id else None
            if model_name == "Book":
                return book if requested_id == book_id else None
            return None

    assert (
        await beta_read_utils._resolve_feedback_scene(
            LookupDb(), assignment=assignment, scene_id=str(scene_id)
        )
        is scene
    )
    assert (
        await beta_read_utils._resolve_feedback_question(
            LookupDb(), assignment=assignment, question_id=str(question_id)
        )
        is question
    )
    with pytest.raises(HTTPException):
        await beta_read_utils._resolve_feedback_scene(
            LookupDb(), assignment=assignment, scene_id="not-a-uuid"
        )
    scene.chapter_number = 5
    with pytest.raises(HTTPException):
        await beta_read_utils._resolve_feedback_scene(
            LookupDb(), assignment=assignment, scene_id=str(scene_id)
        )

    feedback_item = SimpleNamespace(id=uuid.uuid4(), assignment_id=assignment_id, metadata_json={})

    class FeedbackDb:
        def __init__(self):
            self.committed = False
            self.refreshed = None

        async def execute(self, statement):
            return ScalarResult(feedback_item)

        async def commit(self):
            self.committed = True

        async def refresh(self, item):
            self.refreshed = item

    with pytest.raises(HTTPException):
        await beta_read_utils.update_beta_read_feedback_item_author_state(
            FeedbackDb(),
            assignment=assignment,
            feedback_item_id=feedback_item.id,
            author_status="task_created",
            author_task_id=None,
        )
    db = FeedbackDb()
    updated = await beta_read_utils.update_beta_read_feedback_item_author_state(
        db,
        assignment=assignment,
        feedback_item_id=feedback_item.id,
        author_status="resolved",
        author_task_id=" task-22 ",
    )
    assert updated.metadata_json["author_status"] == "resolved"
    assert updated.metadata_json["author_task_id"] == "task-22"
    assert db.committed is True and db.refreshed is feedback_item


def test_world_building_candidate_conflict_and_scoring_helpers():
    assert (
        world_building_utils.classify_world_intent("Where can I use the moon law?")
        == "story_integration"
    )
    assert (
        world_building_utils.classify_world_intent("What gaps contradict the canon?")
        == "gap_detection"
    )
    assert world_building_utils._dedupe_strings([" Moon Gate ", "moon gate", "", "River"]) == [
        "Moon Gate",
        "River",
    ]

    character_id = str(uuid.uuid4())
    resolved = world_building_utils._apply_character_and_override_resolution(
        [
            {
                "name": "Mira Vale",
                "description": "A captain from the moon gate.",
                "element_type": "person",
                "usage_count": 2,
                "confidence": 0.4,
                "aliases": ["Mira"],
                "claims": [{"attribute": "location", "value": "Moon Gate", "confidence": 0.7}],
                "provenance": {"excerpt": "Mira watches the gate.", "narrative_mode": "summary"},
                "chapter_number": 2,
            },
            {
                "name": "Moon Gate",
                "description": "A cold gate that requires ash.",
                "element_type": "place",
                "usage_count": 1,
                "confidence": 0.6,
                "aliases": ["Lunar Gate"],
                "claims": [{"attribute": "requirement", "value": "ash", "confidence": 0.6}],
                "chapter_number": 3,
            },
            {
                "name": "Lunar Gate",
                "description": "A longer description for the same gate.",
                "element_type": "place",
                "usage_count": 3,
                "confidence": 0.8,
                "aliases": ["Moon Gate"],
                "claims": [{"attribute": "requirement", "value": "silver", "confidence": 0.9}],
                "chapter_number": 4,
            },
        ],
        character_registry=[
            {
                "character_id": character_id,
                "canonical_name": "Mira Vale",
                "aliases": ["Mira"],
            }
        ],
        override_lookup={
            "moon gate": {
                "canonical_name": "Moon Gate",
                "aliases": ["Lunar Gate"],
                "entity_type": "place",
            }
        },
    )
    assert resolved[0]["canonical_name"] == "Moon Gate"
    assert resolved[0]["usage_count"] == 4
    assert resolved[0]["author_override"] is True
    assert any(
        item["canonical_name"] == "Mira Vale" and item["character_id"] == character_id
        for item in resolved
    )

    collapsed = world_building_story_utils.collapse_elements(
        [
            {
                "name": "Moon Gate",
                "aliases": ["Gate"],
                "usage_count": 1,
                "chapter_numbers": [2],
                "confidence": 0.5,
            },
            {
                "canonical_name": "Moon Gate",
                "aliases": ["Lunar Gate"],
                "usage_count": 2,
                "chapter_numbers": [3],
                "confidence": 0.7,
                "description": "The moon gate requires ash.",
                "claims": [{"attribute": "requirement", "value": "ash", "confidence": 0.7}],
            },
        ]
    )
    assert collapsed["moon gate"]["usage_count"] == 3
    assert collapsed["moon gate"]["chapter_numbers"] == [2, 3]

    assert world_building_serialization_utils.map_element_to_wiki_type("kingdom") == "location"
    assert world_building_serialization_utils.map_element_to_wiki_type("weapon") == "item"
    assert world_building_utils._world_names_equivalent("Moon-Gate", "moon gate") is True
    assert (
        world_building_utils._world_text_mentions_name("the moon gate opens", "Moon Gate") is True
    )
    assert (
        world_building_utils._should_surface_world_item(
            {"element_type": "place", "confidence": 0.4, "usage_count": 1}
        )
        is False
    )
    assert (
        world_building_utils._should_surface_world_item(
            {"element_type": "place", "confidence": 0.7, "usage_count": 1}
        )
        is True
    )
    assert (
        world_building_utils._should_surface_story_item(
            {
                "element_type": "place",
                "presence_score": 0.4,
                "usage_count": 3,
                "chapter_count": 2,
                "confidence": 0.7,
            }
        )
        is True
    )
    assert (
        world_building_utils._is_underintegrated_story_match(
            {"presence_score": 0.2, "usage_count": 4, "chapter_count": 2}
        )
        is True
    )
    assert (
        world_building_utils._claim_phrase({"attribute": "requirement", "value": "ash"})
        == "requires ash"
    )
    assert (
        world_building_utils._claim_phrase(
            {"attribute": "climate", "value": "cold", "negated": True}
        )
        == "is not cold"
    )
    assert (
        world_building_utils._claims_contradict(
            {"attribute": "travel_time", "value": "3 days"},
            {"attribute": "travel_time", "value": "5 days"},
        )
        is True
    )
    assert (
        world_building_utils._descriptions_conflict(
            "The realm is frozen and cold.", "The realm is desert hot."
        )
        is True
    )
    assert world_building_serialization_utils.filename_title("moon_gate-notes.md") == "Moon Gate Notes"

    world_item = {
        "name": "Moon Gate",
        "element_type": "place",
        "claims": [{"attribute": "requirement", "value": "ash", "confidence": 0.8}],
        "description": "Requires ash.",
        "world_document_id": "doc-1",
        "world_document_title": "Gate Notes",
        "provenance": [{"excerpt": "Gate requires ash."}],
    }
    story_item = {
        "name": "Moon Gate",
        "element_type": "place",
        "claims": [{"attribute": "requirement", "value": "silver", "confidence": 0.9}],
        "description": "Requires silver.",
        "chapter_number": 4,
        "chapter_title": "The Door",
        "provenance": [{"excerpt": "Gate requires silver."}],
    }
    conflict = world_building_utils._build_cross_source_conflict_detail(world_item, story_item)
    assert conflict is not None
    assert "ash" in conflict["description"]
    internal = world_building_utils._detect_internal_candidate_conflicts(
        [world_item, {**story_item, "world_document_id": "doc-2"}], source_kind="world"
    )
    assert internal and internal[0]["id"].startswith("story_conflicts-moon gate-world")


@pytest.mark.asyncio
async def test_public_utils_manual_creation_request_parsing_and_image_helpers(monkeypatch):
    admin_user = SimpleNamespace(id=uuid.uuid4())
    book_id = uuid.uuid4()
    cache_deletes: list[str] = []
    dirty_profiles: list[str] = []
    uploaded_text: list[tuple[str, str]] = []

    monkeypatch.setattr(settings, "PUBLIC_MODE_ENABLED", True)
    monkeypatch.setattr(content, "upload_text", lambda key, text: uploaded_text.append((key, text)))
    monkeypatch.setattr(content, "count_tokens", lambda text: len(text.split()))

    async def fake_cache_del(key):
        cache_deletes.append(key)

    monkeypatch.setattr(content, "cache_del", fake_cache_del)

    async def fake_dirty_profile(user_id):
        dirty_profiles.append(user_id)

    monkeypatch.setattr(content, "mark_public_profile_cache_dirty", fake_dirty_profile)

    class ScalarResult:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalar_one(self):
            return self.value

    class FakeDb:
        def __init__(self):
            self.added = []
            self.existing = None
            self.book = None
            self.next_number = 3
            self.flush_count = 0

        async def execute(self, statement):
            return ScalarResult(self.existing if self.book is None else self.next_number)

        async def get(self, model, requested_id):
            return self.book if requested_id == book_id else None

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            self.flush_count += 1

    db = FakeDb()
    with pytest.raises(HTTPException):
        await content.create_public_demo_book(
            db,
            admin_user=admin_user,
            body=PublicBookManualIn(title="Empty", chapters=[]),
        )
    db.existing = uuid.uuid4()
    with pytest.raises(HTTPException):
        await content.create_public_demo_book(
            db,
            admin_user=admin_user,
            body=PublicBookManualIn(
                title="Duplicate", chapters=[PublicChapterIn(title="One", text="Words")]
            ),
        )
    db.existing = None
    book, created = await content.create_public_demo_book(
        db,
        admin_user=admin_user,
        body=PublicBookManualIn(
            title="Lantern Gate",
            author="A Writer",
            genre="Fantasy",
            description="Demo",
            chapters=[PublicChapterIn(title="One", text="First chapter")],
        ),
    )
    assert created.public_slug == "lantern-gate"
    assert book.total_chapters == 1
    assert uploaded_text
    assert dirty_profiles == [str(admin_user.id)]

    db.book = book
    db.book.id = book_id
    appended_book, appended = await content.append_public_demo_book_chapter(
        db,
        book_id=book_id,
        body=PublicChapterIn(title="Three", text="Third chapter"),
    )
    assert appended.chapter_number == 3
    assert appended_book.total_chapters == 3
    db.book = SimpleNamespace(is_public=False)
    with pytest.raises(HTTPException):
        await content.append_public_demo_book_chapter(
            db, book_id=book_id, body=PublicChapterIn(title="X", text="Y")
        )

    class FakeRequest:
        def __init__(self, content_type, payload):
            self.headers = {"content-type": content_type}
            self.payload = payload

        async def form(self):
            return self.payload

        async def json(self):
            return self.payload

    upload = SimpleNamespace(filename="cover.png")
    body, image = await requests.parse_public_forum_post_create_request(
        FakeRequest(
            "multipart/form-data",
            {
                "thread_type": "novel",
                "headline": "Need beta readers",
                "body": "This draft needs beta readers soon.",
                "desired_beta_reader_count": "4",
                "allow_contact_requests": "off",
                "image": upload,
            },
        )
    )
    assert body.desired_beta_reader_count == 4
    assert body.allow_contact_requests is False
    assert image is upload
    json_body, image = await requests.parse_public_forum_post_create_request(
        FakeRequest(
            "application/json",
            {"headline": "General thread", "body": "This is a long enough public forum post."},
        )
    )
    assert json_body.thread_type == "novel"
    assert image is None
    update_body, _ = await requests.parse_public_forum_post_update_request(
        FakeRequest(
            "multipart/form-data",
            {
                "headline": "Updated thread",
                "body": "This is a long enough updated forum post.",
                "status": "closed",
                "remove_image": "yes",
            },
        )
    )
    assert update_body.status == "closed"
    assert update_body.remove_image is True
    comment_body, _ = await requests.parse_public_forum_comment_create_request(
        FakeRequest("application/json", {"body": "This comment has enough detail."})
    )
    assert comment_body.body.startswith("This comment")
    for parser in (
        requests.parse_public_forum_post_create_request,
        requests.parse_public_forum_post_update_request,
        requests.parse_public_forum_comment_create_request,
    ):
        with pytest.raises(HTTPException):
            await parser(FakeRequest("application/json", ["bad"]))

    class FakeUpload:
        def __init__(self, chunks, filename="image.png"):
            self.chunks = list(chunks)
            self.filename = filename
            self.seek_calls = []

        async def read(self, size):
            return self.chunks.pop(0) if self.chunks else b""

        async def seek(self, offset):
            self.seek_calls.append(offset)

    raw, suffix, mime = await requests._read_public_forum_image(FakeUpload([b"\x89PNGimage-bytes"]))
    assert (suffix, mime, raw.startswith(b"\x89PNG")) == ("png", "image/png", True)
    with pytest.raises(HTTPException):
        await requests._read_public_forum_image(FakeUpload([b""]))
    with pytest.raises(HTTPException):
        await requests._read_public_forum_image(FakeUpload([b"not-an-image"]))
    with pytest.raises(HTTPException):
        await requests._read_public_forum_image(
            FakeUpload([b"x" * (public_utils.MAX_PUBLIC_FORUM_IMAGE_BYTES + 1)])
        )

    owner_id = uuid.uuid4()
    target_id = uuid.uuid4()
    image_target = SimpleNamespace(
        id=target_id,
        author_user_id=owner_id,
        image_s3_key="forum/post.png",
        image_content_type="image/png",
    )

    class ImageDb:
        async def get(self, model, requested_id):
            return image_target if requested_id == target_id else None

    monkeypatch.setattr(
        requests,
        "decode_token",
        lambda token: (
            {"type": "asset", "sub": str(owner_id), "res": f"public-forum-post-image:{target_id}"}
            if token == "good"
            else None
        ),
    )
    monkeypatch.setattr(requests, "download_book", lambda key: b"image")
    response = await requests.get_public_forum_image_response(
        ImageDb(), target_kind="post", target_id=target_id, token="good"
    )
    assert response.body == b"image"
    with pytest.raises(HTTPException):
        await requests.get_public_forum_image_response(
            ImageDb(), target_kind="bad", target_id=target_id, token="good"
        )
    with pytest.raises(HTTPException):
        await requests.get_public_forum_image_response(
            ImageDb(), target_kind="post", target_id=target_id, token="bad"
        )
