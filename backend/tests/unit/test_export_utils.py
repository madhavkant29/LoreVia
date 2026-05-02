"""Unit tests for character bible export formatting."""

from io import BytesIO
import uuid

from docx import Document
import reportlab.platypus

from app.models.book import Book
from app.models.character import Character
from app.utils.export_utils import (
    EXPORT_ATTRIBUTION,
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
    character_bible_docx,
    character_bible_markdown,
    character_bible_pdf,
    manuscript_docx,
    manuscript_obsidian_vault_zip,
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

    assert any(
        EXPORT_ATTRIBUTION in paragraph.text
        for section in doc.sections
        for paragraph in section.footer.paragraphs
    )


def test_character_bible_pdf_draws_footer_on_every_page(monkeypatch):
    captured: dict[str, object] = {}
    original_template = reportlab.platypus.SimpleDocTemplate

    class FakeCanvas:
        def __init__(self):
            self.drawn: list[str] = []

        def saveState(self) -> None:
            return None

        def restoreState(self) -> None:
            return None

        def setFont(self, *_args) -> None:
            return None

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
        "motivations": [],
        "fears": [],
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
    assert "Introduced in Scene 1, resolved in Scene 6" in markdown_text
    assert "Scene 2 to Scene 8" in markdown_text

    pdf_bytes = character_card_pdf(payload)
    assert pdf_bytes.startswith(b"%PDF")

    doc = Document(BytesIO(character_card_docx(payload)))
    doc_text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    table_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)

    assert "Scene 1" in table_text
    assert "Scene 8" in table_text
    assert "Introduced in Scene 1, resolved in Scene 6" in doc_text
    assert "Scene 2 to Scene 8" in table_text


def test_manuscript_docx_uses_front_matter_for_title_page():
    raw = manuscript_docx(
        title="Atlas",
        chapters=[{"number": 1, "title": "Opening", "text": "First paragraph.\n\n#\n\nSecond paragraph."}],
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

    assert "Atlas Rising" in text
    assert "A. Writer" in text
    assert "writer@example.com" in text
    assert "Chapter 1" in text


def test_manuscript_obsidian_vault_zip_creates_expected_folders():
    raw = manuscript_obsidian_vault_zip(
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
