"""Synthetic regression cases for source-matched prose outlines."""

import json
import tempfile
import uuid
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document
from ebooklib import epub
from fastapi import HTTPException

from app.parsers.text_parser import parse_text_structure
from app.services.upload_preview_service import (
    accept_upload_structure_plan,
    import_word_totals,
    upload_preview_cache_key,
)
from app.utils.books.imports import (
    build_import_preview,
    parse_book_upload_for_ingestion,
    parse_structured_prose_upload,
)
from app.utils.books.structure_plan import (
    build_structure_plan,
    materialize_structure_plan,
    validate_structure_plan,
)


def _synthetic_plan():
    manuscript = (
        "Author's Note\n"
        "This invented manuscript began as a map of the harbor.\n\n"
        "Chronology\n"
        "Year One: the lamps were lit. Year Two: the bridge closed.\n\n"
        "Part I\n"
        "At the edge of the harbor, Mara watched the signal fade.\n\n"
        "Chapter 1\n"
        "Mara found the first key in the old tower. She carried it home.\n\n"
        "Chapter 2\n"
        "The archivist opened the door and saw the tide arriving.\n\n"
        "Mara heard the bell from the quay.\n\n"
        "Part II\n\n"
        "Chapter 1\n"
        "At sunrise, Mara returned the key and crossed the bridge.\n"
    )
    return build_structure_plan(
        manuscript.encode(), parse_text_structure(manuscript, language="en")
    )


def test_nested_parts_keep_source_order_and_local_numbering():
    plan = _synthetic_plan()
    sections = plan["sections"]
    assert [section["type"] for section in sections] == [
        "notes",
        "chronology",
        "part",
        "part_opening",
        "chapter",
        "chapter",
        "part",
        "chapter",
    ]
    chapters = materialize_structure_plan(plan)
    assert [chapter["number"] for chapter in chapters] == [1, 2, 3, 4, 5, 6]
    assert [
        chapter["source_number"] for chapter in chapters if chapter["section_type"] == "chapter"
    ] == [1, 2, 1]
    assert chapters[0]["include_in_analysis"] is False
    assert chapters[1]["include_in_analysis"] is False
    assert chapters[2]["section_type"] == "part_opening"
    assert chapters[-1]["parent_part_id"] == sections[-2]["id"]
    assert "".join(plan["blocks"])


def test_copyright_opening_stays_readable_but_is_excluded_from_story_analysis():
    body = "Mara crossed the harbor gate before sunrise. " * 8
    source = (
        "HARBOR LIGHTS\n\nBy Ada Writer\n\nCopyright 2026 Ada Writer. All rights reserved."
        f"\n\nPart One\n\nI\n\n{body}\n\nII\n\n{body}"
    )

    plan = build_structure_plan(source.encode(), parse_text_structure(source, language="en"))
    chapters = materialize_structure_plan(plan)

    assert chapters[0]["title"] == "Opening material"
    assert chapters[0]["section_type"] == "title_page"
    assert chapters[0]["include_in_analysis"] is False
    assert [row["section_type"] for row in chapters[1:]] == ["chapter", "chapter"]


def test_boundary_move_preserves_every_block_once():
    detected = _synthetic_plan()
    proposed = deepcopy(detected)
    first = next(
        i for i, section in enumerate(proposed["sections"]) if section["type"] == "chapter"
    )
    left = proposed["sections"][first]
    right = proposed["sections"][first + 1]
    assert (
        right["end_block"] - right["start_block"] > 1 or left["end_block"] - left["start_block"] > 1
    )
    if right["end_block"] - right["start_block"] > 1:
        left["end_block"] += 1
        right["start_block"] += 1
    else:
        left["end_block"] -= 1
        right["start_block"] -= 1
    accepted = validate_structure_plan(proposed, detected)
    materialized = materialize_structure_plan(accepted)
    assert "\n\n".join(chapter["text"] for chapter in materialized) == "\n\n".join(
        detected["blocks"]
    )


@pytest.mark.parametrize("corruption", ["stale", "gap", "overlap", "fake_toc", "no_readable"])
def test_rejects_stale_or_lossy_outline(corruption):
    detected = _synthetic_plan()
    proposed = deepcopy(detected)
    if corruption == "stale":
        proposed["source_sha256"] = "different source"
    elif corruption in {"gap", "overlap"}:
        chapter = next(section for section in proposed["sections"] if section["type"] == "chapter")
        chapter["start_block"] += 1 if corruption == "gap" else -1
    elif corruption == "fake_toc":
        chapter = next(section for section in proposed["sections"] if section["type"] == "chapter")
        chapter["type"] = "toc"
    else:
        proposed["sections"] = [
            {
                **proposed["sections"][0],
                "type": "toc",
                "start_block": 0,
                "end_block": len(detected["blocks"]),
            }
        ]
    with pytest.raises(HTTPException):
        validate_structure_plan(proposed, detected)


def test_uncertain_region_is_flat_analyzed_and_warned_without_downgrading_confident_chapter():
    parsed = [
        {"title": "Chapter 1", "section_type": "chapter", "text": "Mara entered the tower."},
        {
            "title": "Uncertain leaf",
            "section_type": "unknown",
            "text": "A detached slip recorded the tide.",
        },
        {"title": "Chapter 2", "section_type": "chapter", "text": "Mara returned home."},
    ]
    plan = build_structure_plan(b"source", parsed)
    sections = plan["sections"]
    assert [section["type"] for section in sections] == ["chapter", "unknown", "chapter"]
    assert sections[1]["include_in_analysis"] is True
    assert sections[1]["warnings"]
    assert not sections[0]["warnings"]
    assert not sections[2]["warnings"]


def test_short_ambiguous_boundary_falls_back_only_for_that_region():
    manuscript = (
        "Chapter 1\nMara opened the harbor door.\n\n"
        "Chapter 2\nA brief fragment\n\n"
        "Chapter 3\nMara found the chart and returned to the lighthouse."
    )
    plan = build_structure_plan(
        manuscript.encode(), parse_text_structure(manuscript, language="en")
    )
    assert [section["type"] for section in plan["sections"]] == ["chapter", "unknown", "chapter"]
    assert plan["sections"][1]["warnings"]


def test_contents_entries_are_metadata_not_story_chapters():
    source = (
        b"Contents\nChapter 1 ........ 3\nChapter 2 ........ 9\n\n"
        b"Chapter 1\nMara watched the lighthouse while her brother carried a sealed letter.\n\n"
        b"Chapter 2\nThe brother returned at dawn, opened the letter, and called for Mara."
    )
    parsed = parse_structured_prose_upload(format_name="txt", raw=source, filename="harbor.txt")
    plan = parsed["structure_plan"]
    assert plan["sections"][0]["type"] == "toc"
    assert "Chapter 1 ........ 3" in "\n".join(next(iter(plan["toc_entries"].values())))
    assert [chapter["title"] for chapter in parsed["chapters"]] == ["Chapter 1", "Chapter 2"]
    assert sum(chapter["include_in_analysis"] for chapter in parsed["chapters"]) == 2
    preview = build_import_preview(format_name="txt", work_type="novel", raw=source)
    readable, analyzed = import_word_totals(preview)
    assert (
        readable == analyzed == sum(len(chapter["text"].split()) for chapter in parsed["chapters"])
    )
    assert preview["total_words"] == readable


def test_import_word_totals_exclude_supplemental_sections_from_processing():
    plan = _synthetic_plan()
    preview = {"parser_version": plan["parser_version"], "sections": plan["sections"]}
    readable, analyzed = import_word_totals(preview)
    assert readable > analyzed > 0
    assert analyzed == sum(
        section["word_count"] for section in plan["sections"] if section["include_in_analysis"]
    )


def test_preview_cache_separates_parser_context_for_the_same_source():
    user_id = uuid.uuid4()
    text_key = upload_preview_cache_key(user_id, b"Chapter 1", "txt", "novel")
    script_key = upload_preview_cache_key(user_id, b"Chapter 1", "txt", "screenplay")
    assert text_key != script_key


def test_scrivener_folder_becomes_part_without_losing_child_text():
    project = b"""<ScrivenerProject><Binder><BinderItem UUID="draft" Type="DraftFolder"><Title>Manuscript</Title><Children><BinderItem UUID="part" Type="Folder"><Title>Part I</Title><Children><BinderItem UUID="chapter" Type="Text"><Title>Chapter 1</Title></BinderItem></Children></BinderItem></Children></BinderItem></Binder></ScrivenerProject>"""
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("Harbor.scriv/Harbor.scrivx", project)
        archive.writestr(
            "Harbor.scriv/Files/Data/chapter/content.txt", "Mara carried the chart to the harbor."
        )
    parsed = parse_structured_prose_upload(
        format_name="scrivener", raw=output.getvalue(), filename="Harbor.scrivzip"
    )
    assert [section["type"] for section in parsed["structure_plan"]["sections"]] == [
        "part",
        "chapter",
    ]
    assert parsed["chapters"][0]["text"] == "Mara carried the chart to the harbor."
    assert parsed["chapters"][0]["parent_part_id"] == parsed["structure_plan"]["sections"][0]["id"]


@pytest.mark.asyncio
async def test_edited_preview_reaches_worker_parser_unchanged():
    raw = b"Chapter 1\nMara crossed the bridge.\n\nChapter 2\nShe returned at dawn."
    preview = build_import_preview(format_name="txt", work_type="novel", raw=raw)
    edited = {
        "source_sha256": preview["source_sha256"],
        "content_sha256": preview["content_sha256"],
        "parser_version": preview["parser_version"],
        "sections": deepcopy(preview["sections"]),
    }
    edited["sections"][0]["title"] = "The bridge"
    accepted = accept_upload_structure_plan(preview=preview, raw=raw, submitted=json.dumps(edited))
    worker = await parse_book_upload_for_ingestion(
        format_name="txt",
        work_type="novel",
        raw=raw,
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
        filename="manuscript.txt",
        proposed_plan=accepted,
    )
    assert worker["chapters"][0]["title"] == "The bridge"
    assert worker["structure_plan"]["sections"][0]["id"] == preview["sections"][0]["id"]


def test_epub_spine_order_overrides_zip_item_order():
    book = epub.EpubBook()
    book.set_identifier("synthetic-harbor")
    book.set_title("Harbor")
    book.set_language("en")
    first = epub.EpubHtml(title="First", file_name="first.xhtml", lang="en")
    first.content = "<html><body><h1>Chapter 1</h1><p>Mara crossed the bridge.</p></body></html>"
    second = epub.EpubHtml(title="Second", file_name="second.xhtml", lang="en")
    second.content = "<html><body><h1>Chapter 2</h1><p>She returned at dawn.</p></body></html>"
    book.add_item(second)
    book.add_item(first)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", first, second]
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as temporary:
        path = Path(temporary.name)
    try:
        epub.write_epub(str(path), book)
        raw = path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
    parsed = parse_structured_prose_upload(format_name="epub", raw=raw, filename="Harbor.epub")
    assert [chapter["title"] for chapter in parsed["chapters"]] == ["Chapter 1", "Chapter 2"]
    assert [chapter["text"] for chapter in parsed["chapters"]] == [
        "Mara crossed the bridge.",
        "She returned at dawn.",
    ]
    first_chapter = next(
        section for section in parsed["structure_plan"]["sections"] if section["type"] == "chapter"
    )
    assert "first.xhtml" in first_chapter["source_location"]


def test_docx_heading_styles_preserve_part_and_chapter_hierarchy():
    document = Document()
    document.add_heading("Part I", level=1)
    document.add_paragraph("The harbor lights went out before Mara reached the quay.")
    document.add_heading("The First Signal", level=2)
    document.add_paragraph("Mara found a map beneath the lantern and carried it home.")
    buffer = BytesIO()
    document.save(buffer)

    parsed = parse_structured_prose_upload(
        format_name="docx", raw=buffer.getvalue(), filename="harbor.docx"
    )
    assert [section["type"] for section in parsed["structure_plan"]["sections"]] == [
        "part",
        "part_opening",
        "chapter",
    ]
    assert parsed["chapters"][1]["parent_part_id"] == parsed["structure_plan"]["sections"][0]["id"]
    assert "paragraph" in parsed["structure_plan"]["sections"][2]["source_location"]


def test_preview_acceptance_recomputes_boundary_details_and_excludes_corrected_notes():
    raw = (
        b"Chapter 1\nMara crossed the bridge.\n\n"
        b"The lamp went out.\n\n"
        b"Chapter 2\nShe returned at dawn."
    )
    preview = build_import_preview(format_name="txt", work_type="novel", raw=raw)
    edited = {
        "source_sha256": preview["source_sha256"],
        "content_sha256": preview["content_sha256"],
        "parser_version": preview["parser_version"],
        "sections": deepcopy(preview["sections"]),
    }
    assert len(edited["sections"]) == 2
    first, second = edited["sections"]
    first["end_block"] -= 1
    second["start_block"] -= 1
    second["type"] = "notes"
    second["include_in_analysis"] = True
    accepted = accept_upload_structure_plan(preview=preview, raw=raw, submitted=json.dumps(edited))
    assert accepted["sections"][0]["word_count"] == sum(
        preview["block_word_counts"][: first["end_block"]]
    )
    assert (
        accepted["sections"][1]["opening_excerpt"]
        == preview["block_openings"][second["start_block"]]
    )
    assert accepted["sections"][1]["include_in_analysis"] is False
