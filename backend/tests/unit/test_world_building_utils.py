import pytest

from app.engine.world.extractor import extract_world_elements_from_text
from app.models.book import Book, Chapter, Series, SeriesBook
from app.models.character import Character
from app.models.intelligence import WorldCanonicalIdentity, WorldElement
from app.models.user import User
from app.utils.books.manuscript import (
    serialize_manuscript_content,
)
from app.utils.world_building_utils import (
    _claims_contradict,
    build_world_logic_response,
    classify_world_intent,
    detect_integration_analysis,
    detect_series_world_analysis,
    detect_world_gaps,
    ingest_world_elements_from_chapter,
    save_canon_override,
)
from app.utils.world_building_document_workflow_utils import create_world_building_documents
from app.utils.world_building_wiki_utils import generate_wiki_from_manuscript


def test_classify_world_intent_prefers_integration_for_story_use_queries():
    assert (
        classify_world_intent("How can I use the northern kingdom better?") == "story_integration"
    )
    assert classify_world_intent("What gaps am I missing in the magic system?") == "gap_detection"


@pytest.mark.asyncio
async def test_detect_world_gap_and_integration_payloads(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_workflow_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(email="world-utils@lorevia.app", username="worldutils", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id, title="World Test", format="pdf", s3_key="world/test.pdf", status="ready"
    )
    db.add(book)
    await db.flush()
    db.add(
        WorldElement(
            book_id=book.id,
            source_scope="story",
            element_type="geography",
            name="Northreach",
            description="Northreach is a desert capital built around a dry salt basin.",
            usage_count=3,
            analysis_metadata={"chapter_number": 2, "chapter_title": "Salt Market"},
        )
    )
    await db.flush()
    await create_world_building_documents(
        db,
        book=book,
        user_id=user.id,
        documents=[
            {
                "title": "World Bible",
                "source_name": "world-bible.txt",
                "text": "Northreach is a frozen capital ringed by ice gates.\n\nThe Ember Rite is the kingdom's winter ritual.",
                "html": None,
            }
        ],
    )
    await db.commit()

    gap_payload = await detect_world_gaps(db, book)
    integration_payload = await detect_integration_analysis(db, book)

    assert gap_payload["mode"] == "gap_detection"
    assert any(group["key"] == "story_conflicts" for group in gap_payload["gap_groups"])
    assert any(
        item["title"].startswith("Northreach conflicts") for item in gap_payload["priority_gaps"]
    )
    assert integration_payload["mode"] == "story_integration"
    assert any(
        item["element_name"] == "The Ember Rite"
        for item in integration_payload["integration_opportunities"]
    )


@pytest.mark.asyncio
async def test_detect_series_world_analysis_checks_lore_across_books(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_workflow_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(
        email="world-series-utils@lorevia.app", username="worldseriesutils", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    series = Series(user_id=user.id, name="The Northreach Cycle")
    db.add(series)
    await db.flush()
    first_book = Book(
        user_id=user.id,
        title="Ice Gates",
        format="pdf",
        s3_key="series/ice.pdf",
        status="ready",
        primary_series_id=series.id,
    )
    second_book = Book(
        user_id=user.id,
        title="Glass Market",
        format="pdf",
        s3_key="series/glass.pdf",
        status="ready",
        primary_series_id=series.id,
    )
    db.add_all([first_book, second_book])
    await db.flush()
    db.add_all(
        [
            SeriesBook(series_id=series.id, book_id=first_book.id, position=1),
            SeriesBook(series_id=series.id, book_id=second_book.id, position=2),
        ]
    )

    story_key = f"chapters/{second_book.id}/1.txt"
    stored[story_key] = serialize_manuscript_content(
        "Northreach is a desert capital where the market roads bake under glass heat.",
        "<p>Northreach is a desert capital where the market roads bake under glass heat.</p>",
    ).encode("utf-8")
    db.add(
        Chapter(
            book_id=second_book.id,
            number=1,
            title="Salt Market",
            s3_key=story_key,
            word_count=11,
            processed=True,
        )
    )
    await create_world_building_documents(
        db,
        book=first_book,
        user_id=user.id,
        documents=[
            {
                "title": "Series Bible",
                "source_name": "series-bible.txt",
                "text": "Northreach is a frozen capital ringed by ice gates.",
                "html": None,
            }
        ],
    )
    await db.commit()

    payload = await detect_series_world_analysis(db, series.id)

    assert payload["book_count"] == 2
    assert payload["gap_analysis"]["mode"] == "series_gap_detection"
    assert any(
        item["title"].startswith("Northreach conflicts")
        for item in payload["gap_analysis"]["priority_gaps"]
    )
    assert any(
        flag["title"] == "Conflicting definition for Northreach"
        for flag in payload["gap_analysis"]["consistency_flags"]
    )


@pytest.mark.asyncio
async def test_generate_wiki_and_world_logic_response(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_workflow_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(email="wiki-utils@lorevia.app", username="wikiutils", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id, title="Wiki Test", format="pdf", s3_key="wiki/test.pdf", status="ready"
    )
    db.add(book)
    await db.flush()
    db.add(
        WorldElement(
            book_id=book.id,
            source_scope="story",
            element_type="kingdom",
            name="Aurelia",
            description="Aurelia is a river kingdom ruled by merchant houses.",
            usage_count=4,
            analysis_metadata={"chapter_number": 1, "chapter_title": "River Gate"},
        )
    )
    await db.flush()
    await create_world_building_documents(
        db,
        book=book,
        user_id=user.id,
        documents=[
            {
                "title": "Lore Notes",
                "source_name": "lore.txt",
                "text": "Aurelia is a river kingdom ruled by merchant houses.\nThe Salt Tribunal controls river tolls.",
                "html": None,
            }
        ],
    )
    await db.commit()

    entries = await generate_wiki_from_manuscript(db, book)
    logic = await build_world_logic_response(
        db, book, "How would Aurelia react to a trade blockade?", "story_integration"
    )

    assert any(entry.name == "Aurelia" for entry in entries)
    assert logic["mode"] == "story_integration"
    assert logic["simulation_steps"]
    assert any(citation["name"] == "Aurelia" for citation in logic["citations"])


def test_extract_world_elements_filters_common_sentence_starters_and_title_fragments():
    text = (
        "This manuscript is a living atlas. They had almost no rest.\n"
        "Crime and Punishment is set in Saint Petersburg.\n"
        "Svidrigailov walks the canals at dawn."
    )

    names = {item["name"] for item in extract_world_elements_from_text(text)}

    assert "This" not in names
    assert "They" not in names
    assert "Crime" not in names
    assert "Punishment" not in names
    assert "Saint Petersburg" in names
    assert "Svidrigailov" in names


def test_extract_world_elements_emits_exact_sentence_and_match_offsets():
    text = "Northreach is not a frozen capital. Saint Petersburg glows at dusk."

    items = extract_world_elements_from_text(text)
    northreach = next(item for item in items if item["name"] == "Northreach")
    provenance = northreach["provenance"]

    assert provenance["excerpt"] == "Northreach is not a frozen capital."
    assert provenance["match_start"] == 0
    assert provenance["match_end"] == len("Northreach")
    assert provenance["sentence_start"] == 0
    assert provenance["sentence_end"] == len("Northreach is not a frozen capital.")


def test_extract_world_elements_marks_negated_claims():
    text = "Northreach is not a frozen capital."

    items = extract_world_elements_from_text(text)
    northreach = next(item for item in items if item["name"] == "Northreach")
    claims_by_attribute = {claim["attribute"]: claim for claim in northreach["claims"]}

    assert claims_by_attribute["occupation"]["value"] == "frozen capital"
    assert claims_by_attribute["occupation"]["negated"] is True
    assert claims_by_attribute["climate"]["value"] == "frozen"
    assert claims_by_attribute["climate"]["negated"] is True


def test_extract_world_elements_keeps_single_mention_chapter_places_with_descriptive_context():
    items = extract_world_elements_from_text(
        "Northreach is a desert capital where the market roads bake under glass heat.",
        chapter_number=1,
    )

    northreach = next(item for item in items if item["name"] == "Northreach")
    assert northreach["element_type"] == "place"


def test_extract_worldbuilding_labeled_sections_for_core_lore_types():
    text = """
    # Countries
    - Aurelia: a river kingdom ruled by merchant houses.
    - Glass Empire: a desert nation built around mirror roads.

    Races: sunborn, Moon Kin
    Areas: The Ashen Wastes, Northreach Province
    Magic System: Aetherbinding converts memory into fire.
    Political Systems: Imperial Senate elects the emperor.
    Laws: Blood Tithe: illegal outside temple sanction.
    Currency: Sun Marks: used for border tolls.
    Travel Constraints: River Crossing: takes three days in winter.
    Power Limits: Embercasting: only once per day.
    """

    items = extract_world_elements_from_text(text)
    by_name = {item["name"]: item for item in items}

    assert by_name["Aurelia"]["element_type"] == "country"
    assert by_name["Glass Empire"]["element_type"] == "country"
    assert by_name["Sunborn"]["element_type"] == "race"
    assert by_name["Moon Kin"]["element_type"] == "race"
    assert by_name["The Ashen Wastes"]["element_type"] == "region"
    assert by_name["Northreach Province"]["element_type"] == "region"
    assert by_name["Aetherbinding"]["element_type"] == "magic_system"
    assert by_name["Aetherbinding"]["provenance"]["narrative_mode"] == "worldbuilding_note"
    assert by_name["Imperial Senate"]["element_type"] == "politics"
    assert by_name["Blood Tithe"]["element_type"] == "law"
    assert by_name["Sun Marks"]["element_type"] == "currency"
    assert by_name["River Crossing"]["element_type"] == "travel_rule"
    assert by_name["Embercasting"]["element_type"] == "power_limit"


def test_extract_world_elements_builds_rule_claims_for_magic_and_geography():
    text = (
        "Magic requires blood sacrifice. "
        "Vael is north of the river. "
        "The journey to Vael takes three days."
    )

    items = extract_world_elements_from_text(text)
    by_name = {item["name"]: item for item in items}

    magic_claims = {claim["attribute"]: claim for claim in by_name["Magic System"]["claims"]}
    vael_claims = {claim["attribute"]: claim for claim in by_name["Vael"]["claims"]}
    travel_claims = {claim["attribute"]: claim for claim in by_name["Travel Constraints"]["claims"]}

    assert magic_claims["requirement"]["value"] == "blood sacrifice"
    assert vael_claims["relative_position"]["value"] == "north of the river"
    assert travel_claims["travel_time"]["value"] == "3 days"


def test_claim_contradiction_detects_negation_flip():
    assert _claims_contradict(
        {"attribute": "occupation", "value": "doctor", "confidence": 0.8, "negated": False},
        {"attribute": "occupation", "value": "doctor", "confidence": 0.8, "negated": True},
    )


@pytest.mark.asyncio
async def test_detect_world_gaps_matches_transliteration_variants_without_false_missing_items(
    db, monkeypatch
):
    user = User(email="world-alias@lorevia.app", username="worldalias", password_hash="hash")
    db.add(user)
    await db.flush()

    book = Book(
        user_id=user.id, title="Alias Test", format="pdf", s3_key="world/alias.pdf", status="ready"
    )
    db.add(book)
    await db.flush()

    db.add(
        WorldElement(
            book_id=book.id,
            source_scope="story",
            element_type="culture",
            name="Dounia",
            description="Dounia pleads with Raskolnikov in a tense family exchange.",
            usage_count=3,
            analysis_metadata={"chapter_number": 2, "chapter_title": "Family Visit"},
        )
    )
    await db.flush()

    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_workflow_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    await create_world_building_documents(
        db,
        book=book,
        user_id=user.id,
        documents=[
            {
                "title": "World Bible",
                "source_name": "world-bible.txt",
                "text": "Dunya is Raskolnikov's sister and a central family obligation in the novel.",
                "html": None,
            }
        ],
    )
    await db.commit()

    gap_payload = await detect_world_gaps(db, book)

    missing_in_story = gap_payload["gap_categories"].get("missing_in_story", [])
    missing_in_world = gap_payload["gap_categories"].get("missing_in_world", [])

    assert not any(item["title"].startswith("Dunya is missing") for item in missing_in_story)
    assert not any(item["title"].startswith("Dounia appears") for item in missing_in_world)


@pytest.mark.asyncio
async def test_detect_world_gaps_surfaces_internal_magic_rule_conflicts(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(
        email="world-magic-conflict@lorevia.app",
        username="worldmagicconflict",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Magic Conflict",
        format="pdf",
        s3_key="story/magic.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    chapter_two_key = f"chapters/{book.id}/2.txt"
    chapter_fifteen_key = f"chapters/{book.id}/15.txt"
    stored[chapter_two_key] = serialize_manuscript_content(
        "Magic requires blood sacrifice.",
        "<p>Magic requires blood sacrifice.</p>",
    ).encode("utf-8")
    stored[chapter_fifteen_key] = serialize_manuscript_content(
        "Mira casts magic without blood sacrifice.",
        "<p>Mira casts magic without blood sacrifice.</p>",
    ).encode("utf-8")
    db.add_all(
        [
            Chapter(
                book_id=book.id,
                number=2,
                title="The Price",
                s3_key=chapter_two_key,
                word_count=4,
                processed=True,
            ),
            Chapter(
                book_id=book.id,
                number=15,
                title="The Shortcut",
                s3_key=chapter_fifteen_key,
                word_count=6,
                processed=True,
            ),
        ]
    )
    await db.commit()

    payload = await detect_world_gaps(db, book)
    story_conflicts = next(
        group for group in payload["gap_groups"] if group["key"] == "story_conflicts"
    )
    magic_conflict = next(
        item for item in story_conflicts["items"] if item["canonical_name"] == "Magic System"
    )

    assert "requires blood sacrifice" in magic_conflict["description"]
    assert "without blood sacrifice" in magic_conflict["description"]
    assert "Chapter 2" in magic_conflict["description"]
    assert "Chapter 15" in magic_conflict["description"]


@pytest.mark.asyncio
async def test_detect_world_gaps_surfaces_internal_geography_conflicts(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(
        email="world-geo-conflict@lorevia.app", username="worldgeoconflict", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Geography Conflict",
        format="pdf",
        s3_key="story/geo.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    chapter_six_key = f"chapters/{book.id}/6.txt"
    chapter_twenty_one_key = f"chapters/{book.id}/21.txt"
    stored[chapter_six_key] = serialize_manuscript_content(
        "Vael is north of the river.",
        "<p>Vael is north of the river.</p>",
    ).encode("utf-8")
    stored[chapter_twenty_one_key] = serialize_manuscript_content(
        "Vael is south of the river.",
        "<p>Vael is south of the river.</p>",
    ).encode("utf-8")
    db.add_all(
        [
            Chapter(
                book_id=book.id,
                number=6,
                title="North Bank",
                s3_key=chapter_six_key,
                word_count=6,
                processed=True,
            ),
            Chapter(
                book_id=book.id,
                number=21,
                title="South Bank",
                s3_key=chapter_twenty_one_key,
                word_count=6,
                processed=True,
            ),
        ]
    )
    await db.commit()

    payload = await detect_world_gaps(db, book)
    story_conflicts = next(
        group for group in payload["gap_groups"] if group["key"] == "story_conflicts"
    )
    vael_conflict = next(
        item for item in story_conflicts["items"] if item["canonical_name"] == "Vael"
    )

    assert "north of the river" in vael_conflict["description"]
    assert "south of the river" in vael_conflict["description"]
    assert "Chapter 6" in vael_conflict["description"]
    assert "Chapter 21" in vael_conflict["description"]


@pytest.mark.asyncio
async def test_detect_world_gaps_uses_character_aliases_as_canonical_identity(db, monkeypatch):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_workflow_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(
        email="world-character@lorevia.app", username="worldcharacter", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Character Alias Test",
        format="pdf",
        s3_key="world/character-alias.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    db.add(
        Character(
            book_id=book.id,
            name="Rodion Raskolnikov",
            aliases=["Rodya", "Rodion Romanovitch"],
            first_chapter=1,
            mention_count=8,
            arc_summary="Rodion struggles with guilt after a violent act.",
        )
    )
    db.add(
        WorldElement(
            book_id=book.id,
            source_scope="story",
            element_type="character",
            name="Rodya",
            description="Rodya wrestles with the consequences of his crime.",
            usage_count=4,
            analysis_metadata={
                "chapter_number": 1,
                "chapter_title": "Fever Dream",
                "presence_score": 0.8,
            },
        )
    )
    await db.flush()

    await create_world_building_documents(
        db,
        book=book,
        user_id=user.id,
        documents=[
            {
                "title": "World Bible",
                "source_name": "world-bible.txt",
                "text": "Rodion Romanovitch is a former law student consumed by pride and guilt.",
                "html": None,
            }
        ],
    )
    await db.commit()

    gap_payload = await detect_world_gaps(db, book)
    missing_in_story = gap_payload["gap_categories"].get("missing_in_story", [])
    missing_in_world = gap_payload["gap_categories"].get("missing_in_world", [])

    assert not any("Rodion" in item["title"] for item in missing_in_story)
    assert not any("Rodya" in item["title"] for item in missing_in_world)


@pytest.mark.asyncio
async def test_save_canon_override_persists_alias_merges(db):
    user = User(email="world-override@lorevia.app", username="worldoverride", password_hash="hash")
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Override Test",
        format="pdf",
        s3_key="world/override.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    identity = await save_canon_override(
        db,
        user_id=user.id,
        book=book,
        canonical_name="Sofya Semyonovna",
        aliases=["Sonia", "Sonya"],
        entity_type="character",
        notes="Use the full canonical form in world docs.",
    )
    await db.commit()

    stored_identity = await db.get(WorldCanonicalIdentity, identity.id)
    assert stored_identity is not None
    assert stored_identity.canonical_name == "Sofya Semyonovna"
    assert stored_identity.entity_type == "character"
    assert "Sonia" in (stored_identity.aliases or [])
    assert "Sonya" in (stored_identity.aliases or [])
    assert stored_identity.source == "author_override"


@pytest.mark.asyncio
async def test_detect_world_gaps_adds_coverage_watchlist_when_no_hard_conflicts_exist(
    db, monkeypatch
):
    stored: dict[str, bytes] = {}

    def fake_upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        stored[key] = raw
        return key

    def fake_download_book(key: str) -> bytes:
        return stored[key]

    monkeypatch.setattr("app.core.storage.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.core.storage.download_book", fake_download_book)
    monkeypatch.setattr("app.utils.world_building_document_workflow_utils.upload_binary", fake_upload_binary)
    monkeypatch.setattr("app.utils.world_building_document_utils.download_book", fake_download_book)
    monkeypatch.setattr(
        "app.utils.world_building_candidate_record_utils.download_book", fake_download_book
    )

    user = User(
        email="world-watchlist@lorevia.app", username="worldwatchlist", password_hash="hash"
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Coverage Watchlist",
        format="pdf",
        s3_key="story/watchlist.pdf",
        status="ready",
    )
    db.add(book)
    await db.flush()

    chapter_key = f"chapters/{book.id}/1.txt"
    stored[chapter_key] = serialize_manuscript_content(
        "Northreach is a desert capital. Travelers cross the Glass Road using Salt Marks.",
        "<p>Northreach is a desert capital. Travelers cross the Glass Road using Salt Marks.</p>",
    ).encode("utf-8")
    db.add(
        Chapter(
            book_id=book.id,
            number=1,
            title="Road Toll",
            s3_key=chapter_key,
            word_count=12,
            processed=True,
        )
    )

    await create_world_building_documents(
        db,
        book=book,
        user_id=user.id,
        documents=[
            {
                "title": "Lean World Notes",
                "source_name": "lean-world-notes.txt",
                "text": (
                    "Countries: Northreach: desert capital.\n"
                    "Travel Constraints: Glass Road: three-day caravan route.\n"
                    "Currency: Salt Marks: market scrip."
                ),
                "html": None,
            }
        ],
    )
    await db.commit()

    payload = await detect_world_gaps(db, book)
    total_review_targets = len(payload["priority_gaps"]) + len(payload["consistency_flags"])
    coverage_group = next(
        (group for group in payload["gap_groups"] if group["key"] == "coverage_watchlist"), None
    )

    assert total_review_targets >= 3
    if coverage_group is not None:
        assert coverage_group["items"]
        assert any(
            "needs a clearer canon note" in item["title"]
            or "needs one more story anchor" in item["title"]
            for item in coverage_group["items"]
        )


@pytest.mark.asyncio
async def test_ingest_world_elements_creates_then_merges_story_evidence(db, monkeypatch):
    user = User(
        email="world-ingest@lorevia.app",
        username="worldingest",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="World Ingest",
        format="txt",
        s3_key="world/ingest.txt",
        status="ready",
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=3,
        title="Ice Gate",
        s3_key="chapters/world-ingest/3.txt",
    )
    db.add(chapter)
    db.add(
        WorldCanonicalIdentity(
            book_id=book.id,
            canonical_name="Northreach",
            aliases=["North Reach"],
            entity_type="location",
            source="author",
            confidence=1.0,
        )
    )
    await db.commit()

    candidates = [
        {
            "name": "North Reach",
            "canonical_name": "Northreach",
            "element_type": "geography",
            "description": "A frozen capital behind an ice gate.",
            "usage_count": 2,
            "aliases": ["North Reach"],
            "confidence": 0.91,
            "provenance": [{"chapter_number": 3}],
            "claims": [{"subject": "Northreach", "predicate": "climate", "value": "frozen"}],
            "chapter_numbers": [3],
            "presence_score": 0.8,
            "narrative_modes": ["description"],
            "source_excerpt": "North Reach glittered with ice.",
            "author_override": True,
        }
    ]
    monkeypatch.setattr(
        "app.utils.world_building_utils.extract_world_elements_from_text",
        lambda *_args, **_kwargs: candidates,
    )

    created = await ingest_world_elements_from_chapter(
        db,
        book=book,
        chapter=chapter,
        chapter_text="North Reach glittered with ice.",
    )
    assert len(created) == 1
    assert created[0].name == "Northreach"
    assert created[0].usage_count == 2

    candidates[0] = {
        **candidates[0],
        "description": "A frozen capital behind an ice gate, ruled by the winter court.",
        "usage_count": 1,
        "aliases": ["The Northern Reach"],
        "chapter_numbers": [3, 4],
        "confidence": 0.97,
    }
    merged = await ingest_world_elements_from_chapter(
        db,
        book=book,
        chapter=chapter,
        chapter_text="The winter court rules Northreach.",
    )
    assert merged[0].id == created[0].id
    assert merged[0].usage_count == 3
    assert merged[0].analysis_metadata["confidence"] == 0.97
    assert 3 in merged[0].analysis_metadata["chapter_numbers"]
    assert merged[0].analysis_metadata["canonical_name"] == "Northreach"
