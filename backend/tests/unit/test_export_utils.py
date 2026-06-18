"""Unit tests for character bible export formatting."""

from io import BytesIO
import uuid
from zipfile import ZipFile

from docx import Document
import reportlab.platypus
import pytest

from app.models.book import Book, Chapter
from app.models.character import Character
from app.models.intelligence import CharacterRelationship, ChapterSummary, PlotThread, WikiEntry
from app.models.user import User
from app.utils.export_utils import (
    EXPORT_ATTRIBUTION,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    character_bible_docx,
    character_bible_markdown,
    character_bible_pdf,
    export_filename_base,
    export_font_notice,
    manuscript_epub_compiled,
    manuscript_epub,
    manuscript_docx,
    manuscript_pdf,
    manuscript_pdf_compiled,
    manuscript_vault_zip,
    novel_docx,
    novel_epub_compiled,
    novel_pdf_compiled,
    _chapter_body_blocks,
    build_character_bible_vault_context,
)


def _build_book() -> Book:
    return Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Atlas",
        format="pdf",
        work_type="novel",
        s3_key="books/atlas.pdf",
        status="ready",
        total_chapters=120,
    )


def _build_characters(book: Book) -> list[Character]:
    return [
        Character(
            id=uuid.uuid4(),
            book_id=book.id,
            name=f"Character {index}",
            first_chapter=1,
            last_seen_chapter=100,
            mention_count=10,
            trait_state={},
        )
        for index in range(40)
    ]


def test_character_bible_markdown_appends_attribution_once():
    book = _build_book()
    characters = _build_characters(book)[:1]

    markdown, _ = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries={},
        thread_summaries={},
    )

    text = markdown.decode("utf-8")

    assert text.rstrip().endswith(EXPORT_ATTRIBUTION)
    assert text.count(EXPORT_ATTRIBUTION) == 1


def test_export_filename_base_falls_back_cleanly():
    assert export_filename_base("Atlas Draft") == "Atlas-Draft"
    assert export_filename_base("   ", fallback="character-bible") == "character-bible"


def test_character_bible_docx_writes_attribution_to_document_footer():
    book = _build_book()
    characters = _build_characters(book)[:1]
    markdown, _ = character_bible_markdown(
        book=book,
        characters=characters,
        rel_summaries={},
        thread_summaries={},
    )

    raw = character_bible_docx(markdown=markdown, title="Atlas - Character Bible")
    doc = Document(BytesIO(raw))

    assert doc.core_properties.title == "Atlas - Character Bible"
    assert doc.core_properties.author == "LoreVia"
    assert doc.core_properties.subject == "Character Bible"
    assert any(
        EXPORT_ATTRIBUTION in paragraph.text
        for section in doc.sections
        for paragraph in section.footer.paragraphs
    )


def test_character_bible_docx_applies_selected_safe_font():
    raw = character_bible_docx(markdown=b"# Atlas\n\n### Iris\n\n- Lead", title="Atlas - Character Bible", font_family="eb-garamond")
    doc = Document(BytesIO(raw))

    assert doc.styles["Normal"].font.name == "EB Garamond"


def test_character_bible_pdf_draws_footer_on_every_page(monkeypatch):
    captured: dict[str, object] = {}
    original_template = reportlab.platypus.SimpleDocTemplate

    class FakeCanvas:
        def __init__(self):
            self.drawn: list[str] = []
            self.metadata: dict[str, str] = {}

        def saveState(self) -> None:
            return None

        def restoreState(self) -> None:
            return None

        def setFont(self, *_args) -> None:
            return None

        def setTitle(self, value: str) -> None:
            self.metadata["title"] = value

        def setAuthor(self, value: str) -> None:
            self.metadata["author"] = value

        def setSubject(self, value: str) -> None:
            self.metadata["subject"] = value

        def setCreator(self, value: str) -> None:
            self.metadata["creator"] = value

        def drawCentredString(self, _x, _y, text: str) -> None:
            self.drawn.append(text)

    class FakeDoc:
        def __init__(self, buffer, **kwargs):
            self.buffer = buffer
            self.pagesize = kwargs["pagesize"]

        def build(self, story, onFirstPage=None, onLaterPages=None):
            captured["story"] = story
            captured["onFirstPage"] = onFirstPage
            captured["onLaterPages"] = onLaterPages
            canvas = FakeCanvas()
            if onFirstPage is not None:
                onFirstPage(canvas, self)
            if onLaterPages is not None:
                onLaterPages(canvas, self)
            captured["drawn"] = canvas.drawn
            captured["metadata"] = canvas.metadata

    monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", FakeDoc)
    try:
        book = _build_book()
        markdown, _ = character_bible_markdown(
            book=book,
            characters=_build_characters(book),
            rel_summaries={},
            thread_summaries={},
        )

        character_bible_pdf(markdown=markdown, title="Atlas - Character Bible")
    finally:
        monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", original_template)

    assert callable(captured["onFirstPage"])
    assert callable(captured["onLaterPages"])
    assert captured["drawn"] == [EXPORT_ATTRIBUTION, EXPORT_ATTRIBUTION]
    assert captured["metadata"] == {
        "title": "Atlas - Character Bible",
        "author": "LoreVia",
        "subject": "Character Bible",
        "creator": "LoreVia",
    }


def test_character_card_exports_use_scene_language_for_screenplays():
    payload = {
        "book_title": "Pilot",
        "work_type": "screenplay",
        "character_id": "char-1",
        "name": "Maya",
        "aliases": ["M. Stone"],
        "role": "lead",
        "status": "Active",
        "description": "Lead investigator.",
        "first_appearance": 1,
        "last_appearance": 8,
        "mentions_count": 22,
        "personality_tags": [],
        "goal": "Find the missing witness.",
        "motivations": [],
        "fears": [],
        "lie_they_believe": "She cannot rely on anyone else.",
        "backstory_wound": "She lost a prior witness under her watch.",
        "arc_type": "positive change",
        "arc_summary": None,
        "growth_events": [{"chapter_number": 3, "event_title": "Refuses the order"}],
        "relationships": [
            {"name": "Eli", "type": "ally", "description": "Trusted partner", "from_chapter": 2, "to_chapter": 8}
        ],
        "plot_threads": [
            {"title": "Missing witness", "status": "open", "introduced_at": 1, "resolved_at": 6, "note": None}
        ],
        "continuity_watch": [],
        "filename_base": "maya",
    }

    markdown, _ = character_card_markdown(payload)
    markdown_text = markdown.decode("utf-8")

    assert "First appearance: Scene 1" in markdown_text
    assert "Last appearance: Scene 8" in markdown_text
    assert "## Goal" in markdown_text
    assert "Find the missing witness." in markdown_text
    assert "Introduced in Scene 1, resolved in Scene 6" in markdown_text
    assert "Scene 2 to Scene 8" in markdown_text

    pdf_bytes = character_card_pdf(payload)
    assert pdf_bytes.startswith(b"%PDF")

    doc = Document(BytesIO(character_card_docx(payload)))
    doc_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)

    assert doc.core_properties.title == "Pilot - Maya Character Card"
    assert doc.core_properties.author == "LoreVia"
    assert doc.core_properties.subject == "Character Card"
    assert "Scene 1" in table_text
    assert "Scene 8" in table_text
    assert "Find the missing witness." in doc_text
    assert "Introduced in Scene 1, resolved in Scene 6" in doc_text
    assert "Scene 2 to Scene 8" in table_text


def test_manuscript_docx_uses_front_matter_for_title_page():
    raw = manuscript_docx(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph.\n\n#\n\nSecond paragraph."}],
        scenes=[],
        front_matter={
            "author_name": "A. Writer",
            "contact_email": "writer@example.com",
            "title": "Atlas Rising",
            "header_last_name": "Writer",
            "header_title": "Atlas Rising",
        },
    )
    doc = Document(BytesIO(raw))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

    assert doc.core_properties.title == "Atlas Rising"
    assert doc.core_properties.author == "A. Writer"
    assert doc.core_properties.subject == "Manuscript"
    assert "Atlas Rising" in text
    assert "A. Writer" in text
    assert "writer@example.com" in text
    assert "Chapter 1" in text
    assert "Table of Contents" not in text


def test_manuscript_docx_adds_toc_field_when_requested():
    raw = manuscript_docx(
        title="Atlas",
        chapters=[
            {"number": 1, "title": "Opening", "text": "First paragraph."},
            {"number": 2, "title": "Chapter 2", "text": "Second paragraph."},
        ],
        scenes=[],
        include_toc=True,
    )
    doc = Document(BytesIO(raw))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

    with ZipFile(BytesIO(raw)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "Table of Contents" in text
    assert "Update this table in Word to refresh page numbers." in text
    assert r"TOC \f \h \z" in document_xml
    assert 'TC "Chapter 1: Opening" \\l 1' in document_xml
    assert 'TC "Chapter 2" \\l 1' in document_xml


def test_manuscript_docx_applies_selected_old_style_font():
    raw = manuscript_docx(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph."}],
        scenes=[],
        font_family="italian-old-style",
    )
    doc = Document(BytesIO(raw))

    assert doc.styles["Normal"].font.name == "Iowan Old Style"


def test_chapter_body_blocks_preserve_paragraph_lines_and_scene_break_variants():
    blocks = _chapter_body_blocks(
        "First line.\nSecond line.\n\n* * *\n\nThird paragraph.\n\n---\n\nFourth paragraph.\n\n~~~\n\nFifth paragraph."
    )

    assert blocks == [
        ("paragraph", "First line.\nSecond line."),
        ("scene_break", "***"),
        ("paragraph", "Third paragraph."),
        ("scene_break", "***"),
        ("paragraph", "Fourth paragraph."),
        ("scene_break", "***"),
        ("paragraph", "Fifth paragraph."),
    ]


def test_chapter_body_blocks_handle_blank_input():
    assert _chapter_body_blocks("") == []
    assert _chapter_body_blocks(" \n \n ") == []


def test_manuscript_docx_includes_special_headings_manual_scenes_and_end_marker():
    raw = manuscript_docx(
        title="Atlas",
        chapters=[
            {"number": 1, "title": "Prologue", "text": "Opening paragraph.\n\n#\n\nSecond beat."},
            {"number": 2, "title": "Chapter 1", "text": "Main chapter text."},
            {"number": 3, "title": "Epilogue", "text": "Closing paragraph."},
        ],
        scenes=[
            {
                "title": "Lantern Walk",
                "body": "Standalone scene body.",
                "chapter_number": 2,
                "source": "manual",
            }
        ],
        front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
    )

    doc = Document(BytesIO(raw))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

    assert "Prologue" in text
    assert "Epilogue" in text
    assert "Scene #1 (Chapter 2)" in text
    assert "Lantern Walk" in text
    assert "***" in text
    assert "THE END" in text


def test_manuscript_docx_resets_indentation_after_scene_break_and_preserves_line_breaks():
    raw = manuscript_docx(
        title="Atlas",
        chapters=[
            {
                "number": 1,
                "title": "Opening",
                "text": "First paragraph.\nWrapped line.\n\n---\n\nSecond paragraph after break.\nStill same paragraph.\n\nThird paragraph.",
            }
        ],
        scenes=[],
        front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
    )

    doc = Document(BytesIO(raw))
    prose_paragraphs = [paragraph for paragraph in doc.paragraphs if paragraph.text in {
        "First paragraph.\nWrapped line.",
        "***",
        "Second paragraph after break.\nStill same paragraph.",
        "Third paragraph.",
    }]

    assert [paragraph.text for paragraph in prose_paragraphs] == [
        "First paragraph.\nWrapped line.",
        "***",
        "Second paragraph after break.\nStill same paragraph.",
        "Third paragraph.",
    ]
    assert prose_paragraphs[0].paragraph_format.first_line_indent.inches == 0
    assert prose_paragraphs[2].paragraph_format.first_line_indent.inches == 0
    assert prose_paragraphs[3].paragraph_format.first_line_indent.inches == 0.5


def test_manuscript_pdf_compiled_preserves_scene_break_order(monkeypatch):
    captured: dict[str, object] = {}
    original_template = reportlab.platypus.SimpleDocTemplate

    class FakeCanvas:
        def saveState(self) -> None:
            return None

        def restoreState(self) -> None:
            return None

        def setFont(self, *_args) -> None:
            return None

        def setTitle(self, _value: str) -> None:
            return None

        def setAuthor(self, _value: str) -> None:
            return None

        def setSubject(self, _value: str) -> None:
            return None

        def setCreator(self, _value: str) -> None:
            return None

        def drawRightString(self, *_args) -> None:
            return None

        def getPageNumber(self) -> int:
            return 1

    class FakeDoc:
        def __init__(self, buffer, **kwargs):
            self.buffer = buffer
            self.pagesize = kwargs["pagesize"]
            self.rightMargin = kwargs["rightMargin"]

        def build(self, story, onFirstPage=None, onLaterPages=None):
            captured["story"] = story
            if onFirstPage is not None:
                onFirstPage(FakeCanvas(), self)
            if onLaterPages is not None:
                onLaterPages(FakeCanvas(), self)

    monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", FakeDoc)
    try:
        manuscript_pdf_compiled(
            title="Atlas",
            chapters=[{"number": 1, "title": "Opening", "text": "First paragraph.\nLine two.\n\n~~~\n\nSecond paragraph.\n\nThird paragraph."}],
            scenes=[],
            front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
        )
    finally:
        monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", original_template)

    story = captured["story"]
    paragraph_text = [item.getPlainText() for item in story if hasattr(item, "getPlainText")]

    assert "First paragraph.Line two." in paragraph_text
    assert "***" in paragraph_text
    assert "Second paragraph." in paragraph_text
    assert "Third paragraph." in paragraph_text
    assert paragraph_text.index("***") > paragraph_text.index("First paragraph.Line two.")
    assert paragraph_text.index("Second paragraph.") > paragraph_text.index("***")


def test_manuscript_pdf_compiled_adds_toc_entries_when_requested(monkeypatch):
    captured: dict[str, object] = {}
    original_template = reportlab.platypus.SimpleDocTemplate

    class FakeCanvas:
        def saveState(self) -> None:
            return None

        def restoreState(self) -> None:
            return None

        def setFont(self, *_args) -> None:
            return None

        def setTitle(self, _value: str) -> None:
            return None

        def setAuthor(self, _value: str) -> None:
            return None

        def setSubject(self, _value: str) -> None:
            return None

        def setCreator(self, _value: str) -> None:
            return None

        def drawRightString(self, *_args) -> None:
            return None

        def getPageNumber(self) -> int:
            return 7

    class FakeDoc:
        def __init__(self, buffer, **kwargs):
            self.buffer = buffer
            self.page = 7
            self.pagesize = kwargs["pagesize"]
            self.rightMargin = kwargs["rightMargin"]

        def notify(self, kind, data) -> None:
            captured.setdefault("notifications", []).append((kind, data))

        def multiBuild(self, story, onFirstPage=None, onLaterPages=None):
            captured["method"] = "multiBuild"
            captured["story"] = story
            if onFirstPage is not None:
                onFirstPage(FakeCanvas(), self)
            for item in story:
                self.afterFlowable(item)

    monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", FakeDoc)
    try:
        manuscript_pdf_compiled(
            title="Atlas",
            chapters=[
                {"number": 1, "title": "Opening", "text": "First paragraph."},
                {"number": 2, "title": "Chapter 2", "text": "Second paragraph."},
            ],
            scenes=[],
            include_toc=True,
        )
    finally:
        monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", original_template)

    story = captured["story"]
    paragraph_text = [item.getPlainText() for item in story if hasattr(item, "getPlainText")]

    assert captured["method"] == "multiBuild"
    assert "Table of Contents" in paragraph_text
    assert ("TOCEntry", (0, "Chapter 1: Opening", 7)) in captured["notifications"]
    assert ("TOCEntry", (0, "Chapter 2", 7)) in captured["notifications"]


def test_manuscript_epub_compiled_preserves_scene_breaks_and_line_breaks():
    raw = manuscript_epub_compiled(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph.\nLine two.\n\n#\n\nSecond paragraph.\n\nThird paragraph."}],
        scenes=[],
        front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
    )

    with ZipFile(BytesIO(raw)) as archive:
        chapter_html = archive.read("EPUB/chapter-1.xhtml").decode("utf-8")

    assert '<p class="first-paragraph">First paragraph.<br/>Line two.</p>' in chapter_html
    assert '<p class="scene-break">***</p>' in chapter_html
    assert '<p class="first-paragraph">Second paragraph.</p>' in chapter_html
    assert "<p>Third paragraph.</p>" in chapter_html


def test_manuscript_epub_compiled_declares_selected_font_stack():
    raw = manuscript_epub_compiled(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph."}],
        scenes=[],
        font_family="eb-garamond",
    )

    with ZipFile(BytesIO(raw)) as archive:
        stylesheet = archive.read("EPUB/styles/main.css").decode("utf-8")

    assert '"EB Garamond", Garamond' in stylesheet
    assert "SIL Open Font License" in export_font_notice("eb-garamond")


def test_manuscript_pdf_renders_html_and_fallback_chapters_with_metadata():
    raw = manuscript_pdf(
        title="Atlas Draft",
        chapters=[
            {
                "number": 1,
                "title": "Opening",
                "html": (
                    "<h1>Part One</h1><p>The &amp; gate opened.</p>"
                    "<blockquote>A warning.</blockquote><ul><li>First clue</li></ul>"
                    "<ol><li>Second clue</li></ol><script>alert('no')</script>"
                ),
                "text": "ignored",
            },
            {"number": 2, "title": "Chapter 2", "html": None, "text": "Fallback line.\n\nLast line."},
        ],
        preset="trade_paperback",
        font_family="eb-garamond",
    )

    assert raw.startswith(b"%PDF")
    assert b"Atlas Draft" in raw
    assert b"LoreVia" in raw


def test_manuscript_epub_builds_navigation_styles_and_sanitized_chapters():
    raw = manuscript_epub(
        title=" Atlas Draft ",
        chapters=[
            {
                "number": 1,
                "title": "Opening",
                "html": "<p>Nora crossed the gate.</p><script>alert('no')</script>",
                "text": "ignored",
            },
            {"number": 2, "title": "", "html": None, "text": "Fallback chapter."},
        ],
        preset="large_print",
        font_family="eb-garamond",
    )

    with ZipFile(BytesIO(raw)) as archive:
        names = set(archive.namelist())
        first = archive.read("EPUB/chapter-1.xhtml").decode("utf-8")
        second = archive.read("EPUB/chapter-2.xhtml").decode("utf-8")
        styles = archive.read("EPUB/styles/main.css").decode("utf-8")

    assert "EPUB/nav.xhtml" in names
    assert "Opening" in first
    assert "Nora crossed the gate." in first
    assert "<script" not in first
    assert "Chapter 2" in second
    assert "Fallback chapter." in second
    assert '"EB Garamond", Garamond' in styles


def test_novel_docx_includes_cover_toc_preface_chapters_and_end_marker():
    raw = novel_docx(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph.\n\n#\n\nSecond paragraph."}],
        front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
        preface="Before the voyage.\n\nA note to readers.",
        novel_front_matter={
            "dedication": "For the first readers.",
            "copyright_page": "Copyright 2026",
            "about_author": "A. Writer lives near the sea.",
        },
        preset="large_print",
    )

    doc = Document(BytesIO(raw))
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)

    assert doc.core_properties.title == "Atlas Rising"
    assert doc.core_properties.author == "A. Writer"
    assert doc.core_properties.subject == "Novel"
    assert "Table of Contents" in text
    assert "Update this table in Word" in text
    assert "Copyright" in text
    assert "For the first readers." in text
    assert "Preface" in text
    assert "Before the voyage." in text
    assert "Chapter 1" in text
    assert "***" in text
    assert "THE END" in text
    assert "About the Author" in text
    assert doc.styles["Normal"].font.name == "Georgia"


def test_novel_pdf_compiled_adds_preface_and_chapter_toc_entries(monkeypatch):
    captured: dict[str, object] = {}
    original_template = reportlab.platypus.SimpleDocTemplate

    class FakeCanvas:
        def __init__(self):
            self.bookmarks: list[str] = []
            self.outlines: list[tuple[str, str, int, bool]] = []

        def saveState(self) -> None:
            return None

        def restoreState(self) -> None:
            return None

        def setFont(self, *_args) -> None:
            return None

        def setTitle(self, _value: str) -> None:
            return None

        def setAuthor(self, _value: str) -> None:
            return None

        def setSubject(self, _value: str) -> None:
            return None

        def setCreator(self, _value: str) -> None:
            return None

        def drawRightString(self, *_args) -> None:
            return None

        def drawCentredString(self, *_args) -> None:
            return None

        def drawImage(self, *_args, **_kwargs) -> None:
            return None

        def getPageNumber(self) -> int:
            return 9

        def bookmarkPage(self, key: str) -> None:
            self.bookmarks.append(key)

        def addOutlineEntry(self, title: str, key: str, level: int = 0, closed: bool = False) -> None:
            self.outlines.append((title, key, level, closed))

    class FakeDoc:
        def __init__(self, buffer, **kwargs):
            self.buffer = buffer
            self.page = 9
            self.pagesize = kwargs["pagesize"]
            self.rightMargin = kwargs["rightMargin"]

        def notify(self, kind, data) -> None:
            captured.setdefault("notifications", []).append((kind, data))

        def multiBuild(self, story, onFirstPage=None, onLaterPages=None):
            captured["story"] = story
            self.canv = FakeCanvas()
            if onFirstPage is not None:
                onFirstPage(self.canv, self)
            for item in story:
                self.afterFlowable(item)
            captured["bookmarks"] = self.canv.bookmarks
            captured["outlines"] = self.canv.outlines

    monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", FakeDoc)
    try:
        novel_pdf_compiled(
            title="Atlas",
            chapters=[{"number": 1, "title": "Opening", "text": "First paragraph."}],
            front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
            preface="Before the voyage.",
            novel_front_matter={"dedication": "For readers."},
        )
    finally:
        monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", original_template)

    paragraph_text = [item.getPlainText() for item in captured["story"] if hasattr(item, "getPlainText")]

    assert "Table of Contents" in paragraph_text
    assert "Dedication" in paragraph_text
    assert "Preface" in paragraph_text
    assert "Before the voyage." in paragraph_text
    assert ("TOCEntry", (0, "Preface", 9, "novel-preface")) in captured["notifications"]
    assert ("TOCEntry", (0, "Chapter 1: Opening", 9, "chapter-1")) in captured["notifications"]
    assert "novel-preface" in captured["bookmarks"]
    assert ("Chapter 1: Opening", "chapter-1", 0, False) in captured["outlines"]


def test_novel_pdf_compiled_draws_cover_as_full_page(monkeypatch):
    captured: dict[str, object] = {}
    original_template = reportlab.platypus.SimpleDocTemplate

    class FakeCanvas:
        def saveState(self) -> None:
            return None

        def restoreState(self) -> None:
            return None

        def setFont(self, *_args) -> None:
            return None

        def setTitle(self, _value: str) -> None:
            return None

        def setAuthor(self, _value: str) -> None:
            return None

        def setSubject(self, _value: str) -> None:
            return None

        def setCreator(self, _value: str) -> None:
            return None

        def drawCentredString(self, *_args) -> None:
            return None

        def getPageNumber(self) -> int:
            return 1

        def drawImage(self, _reader, x, y, *, width, height, **_kwargs) -> None:
            captured["cover_draw"] = {"x": x, "y": y, "width": width, "height": height}

    class FakeDoc:
        def __init__(self, buffer, **kwargs):
            self.buffer = buffer
            self.page = 1
            self.pagesize = kwargs["pagesize"]
            self.rightMargin = kwargs["rightMargin"]
            captured["pagesize"] = self.pagesize

        def multiBuild(self, story, onFirstPage=None, onLaterPages=None):
            captured["story"] = story
            if onFirstPage is not None:
                onFirstPage(FakeCanvas(), self)

    monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", FakeDoc)
    try:
        novel_pdf_compiled(
            title="Atlas",
            chapters=[{"number": 1, "title": "Opening", "text": "First paragraph."}],
            front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
        )
    finally:
        monkeypatch.setattr(reportlab.platypus, "SimpleDocTemplate", original_template)

    cover_draw = captured["cover_draw"]
    page_width, page_height = captured["pagesize"]
    assert cover_draw["x"] <= 0
    assert cover_draw["y"] <= 0
    assert cover_draw["width"] >= page_width
    assert cover_draw["height"] >= page_height


def test_novel_epub_compiled_writes_preface_chapters_and_cover():
    raw = novel_epub_compiled(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph.\n\n---\n\nSecond paragraph."}],
        front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
        preface="Before the voyage.",
        novel_front_matter={
            "copyright_page": "Copyright 2026",
            "acknowledgements": "Thanks to early readers.",
        },
        epub_metadata={
            "publisher": "LoreVia Press",
            "language": "en-US",
            "isbn": "9780000000000",
            "description": "A blurb.",
            "series_name": "Atlas Cycle",
            "series_number": "1",
        },
        font_family="eb-garamond",
    )

    with ZipFile(BytesIO(raw)) as archive:
        names = set(archive.namelist())
        package = archive.read("EPUB/content.opf").decode("utf-8")
        copyright_html = archive.read("EPUB/copyright_page.xhtml").decode("utf-8")
        preface_html = archive.read("EPUB/preface.xhtml").decode("utf-8")
        chapter_html = archive.read("EPUB/chapter-1.xhtml").decode("utf-8")
        ending_html = archive.read("EPUB/the-end.xhtml").decode("utf-8")
        acknowledgements_html = archive.read("EPUB/acknowledgements.xhtml").decode("utf-8")
        stylesheet = archive.read("EPUB/styles/main.css").decode("utf-8")

    assert any(name.startswith("EPUB/cover.") for name in names)
    assert "LoreVia Press" in package
    assert "9780000000000" in package
    assert "<h1>Copyright</h1>" in copyright_html
    assert "<h1>Preface</h1>" in preface_html
    assert "Before the voyage." in preface_html
    assert '<p class="scene-break">***</p>' in chapter_html
    assert "THE END" in ending_html
    assert "Thanks to early readers." in acknowledgements_html
    assert '"EB Garamond", Garamond' in stylesheet


def test_manuscript_vault_zip_creates_expected_folders():
    raw = manuscript_vault_zip(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "Chapter text"}],
        scenes=[{"title": "Forest Ambush", "description": "Setup", "chapter_number": 1, "status": "assigned", "body": "Scene body"}],
        notes=[{"path": "story/idea.md", "content": "Remember this"}],
        front_matter={"title": "Atlas Rising", "author_name": "A. Writer"},
    )

    from zipfile import ZipFile

    with ZipFile(BytesIO(raw)) as archive:
        names = set(archive.namelist())

    assert any(name.endswith("/chapters/Chapter 01.md") for name in names)
    assert any(name.endswith("/scenes/chapter-01/Forest-Ambush.md") for name in names)
    assert any(name.endswith("/notes/story/idea.md") for name in names)
    assert any(name.endswith("/_meta/manuscript-front-matter.md") for name in names)
    assert any(name.endswith("/_meta/FONT-NOTICE.txt") for name in names)


@pytest.mark.asyncio
async def test_character_bible_vault_context_collects_relationships_threads_and_events(db):
    user = User(
        email=f"vault-context-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"vaultcontext{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Vault Context",
        format="txt",
        s3_key="books/vault-context.txt",
        status="ready",
        total_chapters=1,
    )
    db.add(book)
    await db.flush()
    chapter = Chapter(
        book_id=book.id,
        number=1,
        title="The Gate",
        description="Mara reaches the gate.",
        s3_key="chapters/vault-context/1.txt",
    )
    db.add(chapter)
    await db.flush()
    mara = Character(
        book_id=book.id,
        name="Mara",
        normalized_name="mara",
        first_chapter=1,
        mention_count=4,
        growth_events=[
            {
                "chapter_number": 1,
                "title": "Mara chooses the city",
                "description": "She stays to defend it.",
                "is_major": True,
                "importance": 9,
            }
        ],
    )
    jon = Character(
        book_id=book.id,
        name="Jon",
        normalized_name="jon",
        first_chapter=1,
        mention_count=3,
    )
    db.add_all([mara, jon])
    await db.flush()
    db.add_all(
        [
            CharacterRelationship(
                book_id=book.id,
                character_a_id=mara.id,
                character_b_id=jon.id,
                rel_type="allies",
                description="They defend the gate.",
                from_chapter=1,
            ),
            PlotThread(
                book_id=book.id,
                title="The gate siege",
                status="developing",
                introduced_at=1,
                importance=8,
                character_ids=["Mara"],
            ),
            WikiEntry(
                book_id=book.id,
                entry_type="location",
                name="Northreach",
                description="The frozen capital.",
                first_mention=1,
            ),
            ChapterSummary(
                chapter_id=chapter.id,
                mode="short",
                content="Mara and Jon defend the gate.",
                key_events=[
                    {
                        "event": "The siege begins",
                        "description": "Enemies surround Northreach.",
                        "importance": 8,
                        "involved_characters": ["Mara", "Jon"],
                    }
                ],
            ),
        ]
    )
    await db.commit()

    context = await build_character_bible_vault_context(db, book.id)

    assert context["book"].id == book.id
    assert len(context["characters"]) == 2
    assert context["rel_summaries"][str(mara.id)]
    assert context["thread_summaries"][str(mara.id)]
    assert any(event["title"] == "The siege begins" for event in context["chapter_events"])
    assert any(event["title"] == "Mara chooses the city" for event in context["chapter_events"])
