"""
Pydantic schemas for manuscript section structure and import preview.

These are computed-at-parse-time metadata schemas — NOT SQLAlchemy ORM models.
Section structures can be serialized and stored in Book.writer_workspace JSONB
until a dedicated import_structure column is added.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

# Matches heading_patterns.SectionType — keep in sync.
SectionTypeLiteral = Literal[
    "title_page",
    "copyright",
    "dedication",
    "toc",
    "foreword",
    "preface",
    "acknowledgements",
    "prologue",
    "part",
    "chapter",
    "interlude",
    "epilogue",
    "afterword",
    "appendix",
    "glossary",
    "notes",
    "unknown",
]

# Section types included in AI analysis by default.
_INCLUDE_BY_DEFAULT: frozenset[SectionTypeLiteral] = frozenset({
    "chapter",
    "prologue",
    "epilogue",
    "interlude",
})

# Section types excluded from AI analysis by default.
_EXCLUDE_BY_DEFAULT: frozenset[SectionTypeLiteral] = frozenset({
    "title_page",
    "copyright",
    "dedication",
    "toc",
    "acknowledgements",
    "glossary",
    "notes",
})

# Section types included by default but user may toggle off.
_OPTIONAL: frozenset[SectionTypeLiteral] = frozenset({
    "foreword",
    "preface",
    "afterword",
    "appendix",
    "part",
    "unknown",
})


def _default_include(type_: SectionTypeLiteral) -> bool:
    if type_ in _INCLUDE_BY_DEFAULT:
        return True
    if type_ in _OPTIONAL:
        return True
    return False


class SectionMeta(BaseModel):
    """Metadata for a single detected section within a manuscript."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: SectionTypeLiteral
    title: str = ""
    number: int | None = None
    start_page: int | None = None
    end_page: int | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    include_in_analysis: bool = True

    @classmethod
    def from_heading(
        cls,
        title: str,
        type_: SectionTypeLiteral,
        *,
        number: int | None = None,
        confidence: float = 1.0,
        start_page: int | None = None,
        end_page: int | None = None,
    ) -> SectionMeta:
        return cls(
            type=type_,
            title=title,
            number=number,
            confidence=confidence,
            include_in_analysis=_default_include(type_),
            start_page=start_page,
            end_page=end_page,
        )


class LanguageDetection(BaseModel):
    """Result of language detection during import."""

    detected: str = "en"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class ImportWarning(BaseModel):
    """Human-readable warning from the import parser."""

    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class ImportPreview(BaseModel):
    """Aggregate import preview shown to the user before confirming.

    Produced after parsing but before any DB writes or AI analysis.
    """

    detected_language: str = "en"
    language_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    title: str = ""
    author: str = ""
    sections: list[SectionMeta] = Field(default_factory=list)
    chapter_count: int = 0
    toc_detected: bool = False
    front_matter_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[ImportWarning] = Field(default_factory=list)
    raw_diagnostics: dict[str, Any] | None = None

    @property
    def analysis_sections(self) -> list[SectionMeta]:
        return [s for s in self.sections if s.include_in_analysis]

    @property
    def excluded_sections(self) -> list[SectionMeta]:
        return [s for s in self.sections if not s.include_in_analysis]

    def compute_confidence(self) -> float:
        """Recalculate overall import confidence from available signals.

        Factors: language confidence, section-type distribution, chapter count.
        """
        if not self.sections:
            return 0.0

        factors: list[float] = []

        # Language detection confidence (weight 0.3)
        factors.append(self.language_confidence * 0.3)

        # Section classification confidence: ratio of known vs unknown types
        unknown = sum(1 for s in self.sections if s.type == "unknown")
        if self.sections:
            known_ratio = 1.0 - (unknown / len(self.sections))
            factors.append(known_ratio * 0.3)
        else:
            factors.append(0.0)

        # Chapter coverage: minimum viable structure
        if self.chapter_count >= 3:
            factors.append(0.4)
        elif self.chapter_count >= 1:
            factors.append(0.2)
        else:
            factors.append(0.0)

        raw = sum(factors)
        # Penalise parse anomalies visible in diagnostics
        if self.raw_diagnostics and self.raw_diagnostics.get("anomalies"):
            anomaly_count = len(self.raw_diagnostics["anomalies"])
            raw = max(0.0, raw - (anomaly_count * 0.05))

        self.confidence = round(min(1.0, max(0.0, raw)), 4)
        return self.confidence

    def build_from_parser_diagnostics(
        self,
        diagnostics: dict[str, Any],
        *,
        sections: list[SectionMeta] | None = None,
    ) -> ImportPreview:
        """Populate preview fields from parser diagnostics dict."""
        self.detected_language = diagnostics.get("detected_language", "en")
        self.language_confidence = diagnostics.get("detected_language_confidence") or 0.0
        self.chapter_count = diagnostics.get("chapter_count", 0)
        self.toc_detected = diagnostics.get("toc_detected", False)
        self.front_matter_count = diagnostics.get("front_matter_count", 0)
        self.raw_diagnostics = diagnostics

        if sections is not None:
            self.sections = sections

        # Generate warnings from diagnostics
        warnings: list[ImportWarning] = []
        if self.toc_detected:
            warnings.append(ImportWarning(
                message="Table of contents detected and excluded from analysis.",
                severity="info",
            ))
        for anomaly in diagnostics.get("anomalies", []):
            warnings.append(ImportWarning(
                message=f"Parse anomaly detected: {anomaly}",
                severity="warning",
            ))
        if diagnostics.get("fallback_strategy"):
            warnings.append(ImportWarning(
                message=f"Parser used fallback: {diagnostics['fallback_strategy']}",
                severity="info",
            ))
        if self.language_confidence < 0.4:
            warnings.append(ImportWarning(
                message="Low confidence in language detection. Review may be needed.",
                severity="warning",
            ))
        self.warnings = warnings

        self.compute_confidence()
        if self.confidence < 0.4:
            warnings.append(ImportWarning(
                message="Low overall import confidence. Consider reviewing the structure or importing as a single manuscript.",
                severity="warning",
            ))

        return self
