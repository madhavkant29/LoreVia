from app.utils.export_novel_structure_utils import (
    _back_matter_sections,
    _chapter_inline_segments,
    _chapter_media_items,
    _front_matter_sections,
    _image_extension,
    _novel_front_matter,
    normalize_novel_image_placement,
)


def test_normalize_novel_image_placement_defaults_unknown_values():
    assert normalize_novel_image_placement(" inline ") == "inline"
    assert normalize_novel_image_placement("plates") == "plates"
    assert normalize_novel_image_placement("bad") == "end"


def test_novel_front_matter_merges_novel_and_epub_metadata():
    front = _novel_front_matter(
        "Atlas",
        [{"title": "One", "text": "Opening"}],
        {"author_name": "Mira Vale"},
        "Preface text",
        {
            "dedication": "For readers",
            "acknowledgments": "Thanks",
            "about_author": "Bio",
        },
        {"publisher": "LoreVia Press", "language": "en-US", "isbn": "123"},
    )

    assert front["title"] == "Atlas"
    assert front["preface"] == "Preface text"
    assert front["dedication"] == "For readers"
    assert front["acknowledgements"] == "Thanks"
    assert front["about_author"] == "Bio"
    assert front["publisher"] == "LoreVia Press"
    assert front["language"] == "en-US"
    assert front["isbn"] == "123"


def test_front_and_back_matter_sections_skip_empty_entries():
    front = {
        "copyright_page": "Copyright",
        "dedication": "",
        "preface": "Preface",
        "acknowledgements": "Thanks",
        "about_author": "",
        "series_book_list": "Book two",
    }

    assert [section["key"] for section in _front_matter_sections(front)] == [
        "copyright_page",
        "preface",
    ]
    assert [section["key"] for section in _back_matter_sections(front)] == [
        "acknowledgements",
        "series_book_list",
    ]


def test_chapter_inline_segments_extracts_marker_images_and_unmatched_media():
    inline = {"marker": "[[IMAGE:one]]", "raw": b"1", "content_type": "image/png"}
    unmatched = {"marker": "[[IMAGE:two]]", "raw": b"2", "content_type": "image/jpeg"}
    ignored = {"marker": "[[IMAGE:none]]"}

    segments, unmatched_media = _chapter_inline_segments(
        {
            "text": "Before [[IMAGE:one]] after",
            "media": [inline, unmatched, ignored],
        }
    )

    assert segments == [
        {"kind": "text", "text": "Before "},
        {"kind": "image", "media": inline},
        {"kind": "text", "text": " after"},
    ]
    assert unmatched_media == [unmatched]
    assert _chapter_media_items({"media": [inline, ignored]}) == [inline]


def test_image_extension_normalizes_common_content_types():
    assert _image_extension("image/jpeg; charset=binary") == "jpg"
    assert _image_extension("image/webp") == "webp"
    assert _image_extension(None, fallback="bin") == "bin"
