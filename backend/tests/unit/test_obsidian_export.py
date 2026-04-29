"""Unit tests for the richer Obsidian bible export."""

import uuid

from app.models.book import Book
from app.models.character import Character
from app.utils.export_utils import character_bible_obsidian_manifest


def test_character_bible_obsidian_manifest_builds_linked_vault_structure():
    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Sample Story",
        format="pdf",
        s3_key="books/sample-story.pdf",
        status="ready",
    )
    aria = Character(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Aria",
        aliases=["Ari"],
        first_chapter=1,
        mention_count=4,
        trait_state={},
        personality_tags=["curious"],
        motivations=["protect Blaire"],
        fears=["losing Blaire"],
        arc_summary="Aria learns to trust Blaire.",
        growth_events=[{"chapter": 1, "event": "Met Blaire", "description": "Aria meets Blaire in the capital."}],
    )
    blaire = Character(
        id=uuid.uuid4(),
        book_id=book.id,
        name="Blaire",
        first_chapter=2,
        mention_count=3,
        trait_state={},
        personality_tags=["calm"],
        arc_summary="Blaire remains a steady ally.",
    )

    relationships = [
        {
            "character_a_id": aria.id,
            "character_b_id": blaire.id,
            "rel_type": "ally",
            "from_chapter": 2,
            "to_chapter": None,
            "description": "Aria trusts Blaire.",
        }
    ]
    plot_threads = [
        {
            "title": "The Hidden Map",
            "status": "ongoing",
            "importance": 8,
            "introduced_at": 3,
            "resolved_at": None,
            "note": "Aria and Blaire pursue the map.",
            "description": "A map points toward the capital.",
            "character_ids": ["Aria", "Blaire"],
        }
    ]
    wiki_entries = [
        {
            "entry_type": "location",
            "name": "The Capital",
            "description": "Aria and Blaire meet in the capital.",
            "first_mention": 1,
            "related_char_ids": [str(aria.id), str(blaire.id)],
        }
    ]
    chapter_rows = [
        {"number": 1, "title": "Arrival", "content": "Aria reaches the capital.", "key_events": []},
        {"number": 2, "title": "Alliance", "content": "Blaire joins the search.", "key_events": []},
    ]
    chapter_events = [
        {
            "chapter_number": 1,
            "title": "Aria arrives",
            "description": "Aria arrives in the capital with Blaire.",
            "importance": 9,
            "involved_characters": ["Aria", "Blaire"],
        },
        {
            "chapter_number": 2,
            "title": "Blaire joins",
            "description": "Blaire helps Aria.",
            "importance": 7,
            "involved_characters": ["Blaire"],
        },
    ]
    rel_summaries = {
        str(aria.id): ["Allies with Blaire."],
        str(blaire.id): ["Allies with Aria."],
    }
    thread_summaries = {
        str(aria.id): ["The Hidden Map [ongoing] — note: Aria and Blaire pursue the map."],
        str(blaire.id): ["The Hidden Map [ongoing] — note: Aria and Blaire pursue the map."],
    }

    root_folder, files = character_bible_obsidian_manifest(
        book=book,
        characters=[aria, blaire],
        relationships=relationships,
        plot_threads=plot_threads,
        wiki_entries=wiki_entries,
        chapter_rows=chapter_rows,
        chapter_events=chapter_events,
        rel_summaries=rel_summaries,
        thread_summaries=thread_summaries,
    )

    paths = {file["path"]: file["content"] for file in files}

    assert root_folder == "LoreVia Export - Sample-Story"
    assert f"{root_folder}/000 - Index.md" in paths
    assert f"{root_folder}/Characters/Aria.md" in paths
    assert f"{root_folder}/Characters/Blaire.md" in paths
    assert f"{root_folder}/Relationships/Relationship Map.md" in paths
    assert f"{root_folder}/Major Events/Aria-arrives.md" in paths
    assert f"{root_folder}/Major Events/Blaire-joins.md" in paths

    assert "[[Blaire]]" in paths[f"{root_folder}/Characters/Aria.md"]
    assert "[[Aria]]" in paths[f"{root_folder}/Characters/Blaire.md"]
    assert "Next: [[Blaire joins]]" in paths[f"{root_folder}/Major Events/Aria-arrives.md"]
    assert "Previous: [[Aria arrives]]" in paths[f"{root_folder}/Major Events/Blaire-joins.md"]
    assert "[[The Capital]]" in paths[f"{root_folder}/Wiki/Index.md"]
