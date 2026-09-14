import io
import zipfile

import pytest
from fastapi import HTTPException

from app.utils.scrivener_utils import build_scrivener_archive, parse_scrivener_archive


def test_scrivener_export_round_trips_chapter_titles_and_text():
    archive = build_scrivener_archive(
        "River & Ash",
        [
            {"title": "Arrival", "text": "Nora crossed the river.\nA bell rang."},
            {"title": "The Gate", "text": "The gate was already open."},
        ],
    )

    parsed = parse_scrivener_archive(archive)

    assert [chapter["title"] for chapter in parsed] == ["Arrival", "The Gate"]
    assert "Nora crossed the river." in parsed[0]["text"]
    assert "The gate was already open." in parsed[1]["text"]


def test_scrivener_export_uses_a_project_and_data_files():
    archive = build_scrivener_archive("Draft", [{"title": "One", "text": "Text"}])

    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        names = package.namelist()

    assert any(name.endswith(".scrivx") for name in names)
    assert any(name.endswith("content.rtf") for name in names)


def test_scrivener_export_round_trips_unicode():
    chapters = [{"title": "Café", "text": "“Wait—what?” asked Renée. 🌙"}]

    parsed = parse_scrivener_archive(build_scrivener_archive("Moon Draft", chapters))

    assert parsed == [{"number": 1, **chapters[0]}]


def test_scrivener_import_rejects_oversized_expanded_documents():
    project = b"""<?xml version="1.0" encoding="utf-8"?>
    <ScrivenerProject><Binder><BinderItem Type="DraftFolder"><Children>
    <BinderItem UUID="CHAPTER-1" Type="Text"><Title>One</Title></BinderItem>
    </Children></BinderItem></Binder></ScrivenerProject>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Draft.scriv/Draft.scrivx", project)
        archive.writestr(
            "Draft.scriv/Files/Data/CHAPTER-1/content.rtf",
            b"x" * (16 * 1024 * 1024 + 1),
        )

    with pytest.raises(HTTPException) as exc_info:
        parse_scrivener_archive(output.getvalue())

    assert exc_info.value.status_code == 413


def test_scrivener_import_rejects_xml_entities():
    project = b"""<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE project [<!ENTITY external SYSTEM "file:///etc/passwd">]>
    <ScrivenerProject><Binder><BinderItem Type="DraftFolder"><Children>
    <BinderItem UUID="CHAPTER-1" Type="Text"><Title>&external;</Title></BinderItem>
    </Children></BinderItem></Binder></ScrivenerProject>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Draft.scriv/Draft.scrivx", project)
        archive.writestr("Draft.scriv/Files/Data/CHAPTER-1/content.txt", "Text")

    with pytest.raises(HTTPException) as exc_info:
        parse_scrivener_archive(output.getvalue())

    assert exc_info.value.status_code == 400
