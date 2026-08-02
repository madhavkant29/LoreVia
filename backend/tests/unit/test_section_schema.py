import uuid

import pytest
from pydantic import ValidationError

from app.schemas.section import (
    ImportPreview,
    ImportWarning,
    LanguageDetection,
    SectionMeta,
)

# ── SectionMeta ─────────────────────────────────────────────────────────────


def test_section_meta_defaults():
    s = SectionMeta(type="chapter", title="Chapter 1")
    assert s.type == "chapter"
    assert s.title == "Chapter 1"
    assert isinstance(s.id, str)
    assert len(s.id) == 32
    assert uuid.UUID(s.id)  # valid hex UUID
    assert s.number is None
    assert s.start_page is None
    assert s.end_page is None
    assert s.confidence == 1.0
    assert s.include_in_analysis is True


def test_section_meta_explicit():
    s = SectionMeta(
        id="abc123",
        type="toc",
        title="Table of Contents",
        number=0,
        start_page=1,
        end_page=3,
        confidence=0.5,
        include_in_analysis=False,
    )
    assert s.id == "abc123"
    assert s.type == "toc"
    assert s.include_in_analysis is False


def test_section_meta_invalid_type():
    with pytest.raises(ValidationError):
        SectionMeta(type="invalid", title="x")


def test_section_meta_confidence_out_of_range():
    with pytest.raises(ValidationError):
        SectionMeta(type="chapter", title="x", confidence=1.5)
    with pytest.raises(ValidationError):
        SectionMeta(type="chapter", title="x", confidence=-0.1)


def test_from_heading_chapter():
    s = SectionMeta.from_heading("Chapter 1: The Beginning", "chapter", number=1, confidence=0.9)
    assert s.type == "chapter"
    assert s.title == "Chapter 1: The Beginning"
    assert s.number == 1
    assert s.confidence == 0.9
    assert s.include_in_analysis is True


def test_from_heading_toc_excluded():
    s = SectionMeta.from_heading("Table of Contents", "toc")
    assert s.type == "toc"
    assert s.include_in_analysis is False


def test_from_heading_acknowledgements_excluded():
    s = SectionMeta.from_heading("Acknowledgements", "acknowledgements")
    assert s.include_in_analysis is False


def test_from_heading_glossary_excluded():
    s = SectionMeta.from_heading("Glossary", "glossary")
    assert s.include_in_analysis is False


def test_from_heading_copyright_excluded():
    s = SectionMeta.from_heading("Copyright", "copyright")
    assert s.include_in_analysis is False


def test_from_heading_dedication_excluded():
    s = SectionMeta.from_heading("Dedication", "dedication")
    assert s.include_in_analysis is False


def test_from_heading_notes_excluded():
    s = SectionMeta.from_heading("Author Notes", "notes")
    assert s.include_in_analysis is False


def test_from_heading_title_page_excluded():
    s = SectionMeta.from_heading("Title Page", "title_page")
    assert s.include_in_analysis is False


def test_from_heading_prologue_included():
    s = SectionMeta.from_heading("Prologue", "prologue")
    assert s.include_in_analysis is True


def test_from_heading_epilogue_included():
    s = SectionMeta.from_heading("Epilogue", "epilogue")
    assert s.include_in_analysis is True


def test_from_heading_interlude_included():
    s = SectionMeta.from_heading("Interlude", "interlude")
    assert s.include_in_analysis is True


def test_from_heading_preface_optional_included():
    s = SectionMeta.from_heading("Preface", "preface")
    assert s.include_in_analysis is True  # included by default, user may toggle


def test_from_heading_foreword_optional_included():
    s = SectionMeta.from_heading("Foreword", "foreword")
    assert s.include_in_analysis is True


def test_from_heading_unknown_included():
    s = SectionMeta.from_heading("Puzzling Thing", "unknown")
    assert s.include_in_analysis is True


# ── LanguageDetection ───────────────────────────────────────────────────────


def test_language_detection_defaults():
    ld = LanguageDetection()
    assert ld.detected == "en"
    assert ld.confidence == 0.0
    assert ld.candidates == []


def test_language_detection_explicit():
    ld = LanguageDetection(
        detected="fr",
        confidence=0.92,
        candidates=[{"language": "fr", "score": 0.5}],
    )
    assert ld.detected == "fr"
    assert ld.confidence == 0.92
    assert len(ld.candidates) == 1


# ── ImportWarning ───────────────────────────────────────────────────────────


def test_import_warning_defaults():
    w = ImportWarning(message="Test warning")
    assert w.message == "Test warning"
    assert w.severity == "warning"


def test_import_warning_severity():
    w = ImportWarning(message="Info", severity="info")
    assert w.severity == "info"


def test_import_warning_invalid_severity():
    with pytest.raises(ValidationError):
        ImportWarning(message="x", severity="critical")


# ── ImportPreview ───────────────────────────────────────────────────────────


def test_import_preview_defaults():
    p = ImportPreview()
    assert p.detected_language == "en"
    assert p.language_confidence == 0.0
    assert p.title == ""
    assert p.author == ""
    assert p.sections == []
    assert p.chapter_count == 0
    assert p.toc_detected is False
    assert p.front_matter_count == 0
    assert p.confidence == 0.0
    assert p.warnings == []


def test_import_preview_analysis_sections():
    s1 = SectionMeta(type="chapter", title="Ch 1", include_in_analysis=True)
    s2 = SectionMeta(type="toc", title="TOC", include_in_analysis=False)
    s3 = SectionMeta(type="prologue", title="Prologue", include_in_analysis=True)
    p = ImportPreview(sections=[s1, s2, s3])
    assert len(p.analysis_sections) == 2
    assert s1 in p.analysis_sections
    assert s3 in p.analysis_sections


def test_import_preview_excluded_sections():
    s1 = SectionMeta(type="toc", title="TOC", include_in_analysis=False)
    s2 = SectionMeta(type="acknowledgements", title="Ack", include_in_analysis=False)
    s3 = SectionMeta(type="chapter", title="Ch 1", include_in_analysis=True)
    p = ImportPreview(sections=[s1, s2, s3])
    assert len(p.excluded_sections) == 2
    assert s1 in p.excluded_sections
    assert s2 in p.excluded_sections


def test_compute_confidence_no_sections():
    p = ImportPreview()
    assert p.compute_confidence() == 0.0


def test_compute_confidence_high():
    p = ImportPreview(
        detected_language="fr",
        language_confidence=0.9,
        chapter_count=34,
    )
    p.sections = [
        SectionMeta.from_heading(f"Chapitre {i}", "chapter", number=i) for i in range(1, 35)
    ]
    conf = p.compute_confidence()
    assert conf > 0.8


def test_compute_confidence_low():
    p = ImportPreview(
        detected_language="en",
        language_confidence=0.2,
        chapter_count=1,
    )
    p.sections = [
        SectionMeta.from_heading("Some text", "unknown"),
        SectionMeta.from_heading("More stuff", "unknown"),
    ]
    conf = p.compute_confidence()
    assert conf < 0.4


def test_compute_confidence_with_anomalies():
    p = ImportPreview(
        detected_language="en",
        language_confidence=0.8,
        chapter_count=10,
        raw_diagnostics={"anomalies": ["oversized_chapter_outlier", "heading_style_dropout"]},
    )
    p.sections = [SectionMeta.from_heading(f"Ch {i}", "chapter") for i in range(1, 11)]
    conf = p.compute_confidence()
    assert conf < 0.9  # penalised by anomalies


def test_build_from_parser_diagnostics():
    diagnostics = {
        "detected_language": "fr",
        "detected_language_confidence": 0.92,
        "chapter_count": 34,
        "toc_detected": True,
        "front_matter_count": 2,
        "anomalies": [],
        "fallback_strategy": None,
    }
    sections = [
        SectionMeta.from_heading("Table des matieres", "toc", number=0),
        SectionMeta.from_heading("Preface", "preface", number=0),
        SectionMeta.from_heading("Chapitre 1", "chapter", number=1),
        SectionMeta.from_heading("Chapitre 2", "chapter", number=2),
    ]
    p = ImportPreview()
    p.build_from_parser_diagnostics(diagnostics, sections=sections)

    assert p.detected_language == "fr"
    assert p.language_confidence == 0.92
    assert p.chapter_count == 34
    assert p.toc_detected is True
    assert p.front_matter_count == 2
    assert len(p.sections) == 4
    assert p.confidence > 0.0
    assert any(w.message.startswith("Table of contents") for w in p.warnings)


def test_build_from_parser_diagnostics_fallback_warning():
    diagnostics = {
        "detected_language": "en",
        "detected_language_confidence": 0.5,
        "chapter_count": 2,
        "toc_detected": False,
        "front_matter_count": 0,
        "anomalies": [],
        "fallback_strategy": "permissive_heading_retry",
    }
    p = ImportPreview()
    p.build_from_parser_diagnostics(diagnostics)

    assert any("fallback" in w.message.lower() for w in p.warnings)


def test_build_from_parser_diagnostics_low_language_confidence():
    diagnostics = {
        "detected_language": "en",
        "detected_language_confidence": 0.3,
        "chapter_count": 5,
        "toc_detected": False,
        "front_matter_count": 0,
        "anomalies": [],
        "fallback_strategy": None,
    }
    p = ImportPreview()
    p.build_from_parser_diagnostics(diagnostics)

    assert any("language" in w.message.lower() for w in p.warnings)


def test_build_from_parser_diagnostics_low_confidence():
    diagnostics = {
        "detected_language": "en",
        "detected_language_confidence": 0.2,
        "chapter_count": 1,
        "toc_detected": False,
        "front_matter_count": 0,
        "anomalies": ["oversized_chapter_outlier"],
        "fallback_strategy": None,
    }
    p = ImportPreview()
    p.build_from_parser_diagnostics(diagnostics)

    assert p.confidence < 0.4
    assert any("single manuscript" in w.message.lower() for w in p.warnings)
