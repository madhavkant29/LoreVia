import pytest

from app.utils.books.chapter_boundaries import (
    compare_saved_chapters_with_reparsed,
    split_saved_part_chapters,
)
from scripts.plan_saved_chapter_structure import (
    _compare_saved_to_reparsed_storage,
    _text_after_storage,
)


def test_saved_part_split_preserves_exact_source_order_and_words():
    body = "Mara crossed the harbor gate before sunrise. " * 8
    source = f"I\n\n{body}\r\n\r\nII\r\n\r\n{body}\r\n"

    chapters = split_saved_part_chapters("Part One", source)

    assert [item["title"] for item in chapters] == ["I", "II"]
    assert "".join(item["raw_section"] for item in chapters) == source
    assert [item["source_number"] for item in chapters] == [1, 2]
    assert all(item["text"].startswith("Mara crossed") for item in chapters)


def test_saved_part_split_preserves_final_end_and_trailing_author_matter():
    body = "Mara crossed the harbor gate before sunrise. " * 8
    source = (
        f"I\n\n{body}\n\nII\n\n{body}\n\nTHE END."
        "\n\nAbout the Author\n\nThe author grew up by the sea."
    )

    sections = split_saved_part_chapters("Part Two", source)

    assert [item["title"] for item in sections] == ["I", "II", "About the Author"]
    assert [item["source_number"] for item in sections] == [1, 2, None]
    assert sections[1]["text"].endswith("THE END.")
    assert sections[2]["text"] == "The author grew up by the sea."
    assert "".join(item["raw_section"] for item in sections) == source


@pytest.mark.parametrize(
    "source",
    [
        "I\n\nMara crossed the harbor gate before sunrise.",
        "I\n\nMara crossed the harbor gate before sunrise.\n\nIII\n\nMara returned.",
        "An introduction too long. " * 120
        + "\n\nI\n\n"
        + "Mara crossed the harbor gate before sunrise. " * 8
        + "\n\nII\n\n"
        + "Mara crossed the harbor gate before sunrise. " * 8,
    ],
)
def test_saved_part_split_rejects_ambiguous_boundaries(source):
    with pytest.raises(ValueError, match="saved_part_chapter_boundaries_ambiguous"):
        split_saved_part_chapters("Part One", source)


def test_reparsed_comparison_detects_missing_or_changed_chapter_without_text():
    body = "Mara crossed the harbor gate before sunrise. " * 8
    saved = [
        {"title": "Opening material", "text": "A note about the story."},
        {"title": "Part One — opening", "text": f"I\n\n{body}\n\nII\n\n{body}"},
    ]
    reparsed = [
        {"title": "Opening material", "text": "A note about the story."},
        {"title": "I", "text": body.strip()},
        {"title": "II", "text": body.strip()},
    ]

    assert all(
        row["content_preserved"] for row in compare_saved_chapters_with_reparsed(saved, reparsed)
    )
    reparsed[2]["text"] = "A changed chapter."
    comparisons = compare_saved_chapters_with_reparsed(saved, reparsed)
    assert comparisons[2]["content_preserved"] is False
    assert "text" not in comparisons[2]


def test_reparsed_comparison_reports_paragraph_repair_separately_from_word_changes():
    body = "Mara crossed the harbor gate.\n\nThe captain watched from the pier. " * 3
    saved = [{"title": "I", "text": body}]
    reparsed = [{"title": "I", "text": " ".join(body.split())}]

    result = compare_saved_chapters_with_reparsed(saved, reparsed)[0]

    assert result["content_preserved"] is True
    assert result["current_paragraphs"] > result["proposed_paragraphs"]


def test_reparsed_comparison_allows_pdf_line_wrap_joins_but_rejects_changed_words():
    saved = [{"title": "I", "text": "The sea-\n\nbird turned . Then it landed."}]
    reparsed = [{"title": "I", "text": "The seabird turned. Then it landed."}]

    result = compare_saved_chapters_with_reparsed(saved, reparsed)[0]

    assert result["content_preserved"] is True
    assert result["line_wrap_joins"] == 2

    reparsed[0]["text"] = "The seabird vanished. Then it landed."
    assert compare_saved_chapters_with_reparsed(saved, reparsed)[0]["content_preserved"] is False


def test_saved_pdf_plan_compares_the_text_that_storage_will_display():
    first = "Mara watched the sea\u2014the harbor was quiet. " * 8
    second = "She returned at dawn. " * 16
    raw = f"I\n\n{first}\n\nII\n\n{second}"
    saved = [{"title": "Part One \u2014 opening", "text": _text_after_storage(raw)}]
    proposed = [
        {"title": "I", "text": first.strip()},
        {"title": "II", "text": second.strip()},
    ]

    assert not all(
        row["content_preserved"] for row in compare_saved_chapters_with_reparsed(saved, proposed)
    )
    assert all(
        row["content_preserved"] for row in _compare_saved_to_reparsed_storage(saved, proposed)
    )

    proposed[1]["text"] = second.replace("returned", "disappeared")
    assert _compare_saved_to_reparsed_storage(saved, proposed)[1]["content_preserved"] is False
