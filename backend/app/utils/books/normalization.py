"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.models.book import (
    Book,
)
from app.utils.index_format import format_index

if TYPE_CHECKING:
    pass


BOOK_WORK_TYPES = {"novel", "screenplay", "other"}
UPLOAD_EXTENSION_TO_FORMAT = {
    ".scriv.zip": "scrivener",
    ".scrivzip": "scrivener",
    ".pdf": "pdf",
    ".epub": "epub",
    ".docx": "docx",
    ".doc": "doc",
    ".txt": "txt",
    ".md": "md",
    ".fountain": "fountain",
    ".screenplay": "fountain",
    ".script": "fountain",
}
FORMAT_TO_UPLOAD_EXTENSION = {
    "scrivener": ".scrivzip",
    "pdf": ".pdf",
    "epub": ".epub",
    "docx": ".docx",
    "doc": ".doc",
    "txt": ".txt",
    "md": ".md",
    "fountain": ".fountain",
}
SCREENPLAY_INFER_FORMATS = {"fountain"}
SCREENPLAY_INPUT_FORMATS = {"pdf", "fountain", "txt", "md"}
TEXT_ONLY_UPLOAD_FORMATS = {"docx", "doc", "txt", "md", "scrivener"}
SCENE_BREAK_LINE_RE = re.compile(r"^\s*(?:#(?:\s*#)*|\*\s*\*\s*\*)\s*$", re.MULTILINE)
SCENE_HEADING_LINE_RE = re.compile(r"^\s*#{1,3}(?:\s+(.*?))?\s*$")
SCENE_METADATA_LABELS = {
    "pov": "POV",
    "location": "Location",
    "time": "Time",
    "timeline": "Timeline",
    "characters": "Characters",
    "objects": "Objects",
    "goals": "Goals",
    "conflict": "Conflict",
    "plot_threads": "Plot Threads",
    "mood": "Mood",
}
SCENE_METADATA_ALIASES = {
    "point of view": "pov",
    "point-of-view": "pov",
    "pov character": "pov",
    "time/day": "time",
    "time of day": "time",
    "timeline marker": "timeline",
    "plot thread": "plot_threads",
    "plot threads": "plot_threads",
}
SCENE_METADATA_LIST_FIELDS = {"characters", "objects", "goals", "plot_threads", "mood"}
SCENE_METADATA_UI_FIELDS = {
    "pov",
    "timeline",
    "location",
    "tags",
    "mood",
    "status_note",
    "anchors",
    "bookmarks",
    "summary",
}
REVISION_ITEM_STATUSES = {"pending", "fixed", "ignored", "task_created"}
REVISION_GENRE_CHECKS = {
    "fantasy": {
        "label": "Fantasy",
        "checks": [
            "magic system consistency",
            "faction politics",
            "invented terms",
            "worldbuilding contradictions",
        ],
    },
    "sci-fi": {
        "label": "Sci-Fi",
        "checks": [
            "technology rule consistency",
            "future setting logic",
            "scientific consequence tracking",
            "faction or colony systems",
        ],
    },
    "science fiction": {
        "label": "Sci-Fi",
        "checks": [
            "technology rule consistency",
            "future setting logic",
            "scientific consequence tracking",
            "faction or colony systems",
        ],
    },
    "romance": {
        "label": "Romance",
        "checks": [
            "relationship escalation",
            "emotional reciprocity",
            "conflict-resolution rhythm",
            "payoff timing",
        ],
    },
    "mystery": {
        "label": "Mystery / Thriller",
        "checks": [
            "clue placement",
            "suspect timelines",
            "alibi consistency",
            "reveal fairness",
        ],
    },
    "thriller": {
        "label": "Mystery / Thriller",
        "checks": [
            "clue placement",
            "suspect timelines",
            "alibi consistency",
            "reveal fairness",
        ],
    },
    "litrpg": {
        "label": "LitRPG",
        "checks": [
            "power progression",
            "system rule continuity",
            "reward cadence",
            "stat escalation clarity",
        ],
    },
    "web novel": {
        "label": "Web Novels",
        "checks": [
            "recap support",
            "long-running arc tracking",
            "power progression",
            "character reintroduction",
        ],
    },
    "webnovel": {
        "label": "Web Novels",
        "checks": [
            "recap support",
            "long-running arc tracking",
            "power progression",
            "character reintroduction",
        ],
    },
    "historical": {
        "label": "Historical Fiction",
        "checks": [
            "era vocabulary fit",
            "social custom continuity",
            "political timeline accuracy",
            "material culture consistency",
        ],
    },
    "horror": {
        "label": "Horror",
        "checks": [
            "dread escalation",
            "threat visibility control",
            "rules of the haunting or creature",
            "payoff of ominous setup",
        ],
    },
    "young adult": {
        "label": "Young Adult",
        "checks": [
            "voice age fit",
            "emotional immediacy",
            "coming-of-age pivot clarity",
            "peer relationship continuity",
        ],
    },
    "ya": {
        "label": "Young Adult",
        "checks": [
            "voice age fit",
            "emotional immediacy",
            "coming-of-age pivot clarity",
            "peer relationship continuity",
        ],
    },
    "epic": {
        "label": "Epic Series",
        "checks": [
            "long-range arc tracking",
            "cast handoff clarity",
            "faction continuity",
            "promise-payoff bookkeeping",
        ],
    },
}
MODERN_VOICE_MARKERS = {
    "okay",
    "yeah",
    "gonna",
    "kinda",
    "sort of",
    "awesome",
    "you guys",
    "totally",
}
REVISION_TRANSITION_MARKERS = {
    "later",
    "meanwhile",
    "elsewhere",
    "suddenly",
    "afterward",
    "afterwards",
    "eventually",
    "by dawn",
    "at dawn",
    "that night",
    "next morning",
    "hours later",
}
REVISION_MOTIVATION_MARKERS = {
    "want",
    "wants",
    "wanted",
    "need",
    "needs",
    "needed",
    "decide",
    "decides",
    "decided",
    "plan",
    "plans",
    "planned",
    "must",
    "promise",
    "promises",
    "promised",
    "trying",
    "tries",
    "goal",
}
REVISION_FIRST_PERSON_MARKERS = {"i", "me", "my", "mine", "we", "us", "our", "ours"}
REVISION_THIRD_PERSON_MARKERS = {
    "he",
    "she",
    "they",
    "him",
    "her",
    "them",
    "his",
    "hers",
    "their",
    "theirs",
}
MAX_REVISION_RECENT_EDITS = 12


def normalize_book_work_type(value: str | None, *, default: str = "novel") -> str:
    normalized = " ".join((value or "").split()).strip().lower()
    if not normalized:
        return default
    if normalized not in BOOK_WORK_TYPES:
        raise HTTPException(400, "Invalid work_type")
    return normalized


def detect_upload_format(filename: str) -> str | None:
    lower = filename.lower().strip()
    for extension, format_name in UPLOAD_EXTENSION_TO_FORMAT.items():
        if lower.endswith(extension):
            return format_name
    return None


def is_screenplay_format(format_name: str | None) -> bool:
    normalized = " ".join((format_name or "").split()).strip().lower()
    return normalized in SCREENPLAY_INPUT_FORMATS or normalized == "screenplay"


def infer_work_type_from_filename(filename: str) -> str | None:
    format_name = detect_upload_format(filename)
    if format_name in SCREENPLAY_INFER_FORMATS:
        return "screenplay"
    lower = filename.lower()
    if "screenplay" in lower or "script" in lower:
        return "screenplay"
    return None


def resolve_upload_format_and_work_type(
    filename: str, explicit_work_type: str | None = None
) -> tuple[str, str]:
    format_name = detect_upload_format(filename)
    if not format_name:
        raise HTTPException(400, f"Unsupported upload format: {filename}")

    inferred_work_type = infer_work_type_from_filename(filename)
    work_type = normalize_book_work_type(explicit_work_type, default=inferred_work_type or "novel")

    if work_type == "screenplay" and format_name not in SCREENPLAY_INPUT_FORMATS:
        raise HTTPException(
            400, "Screenplay uploads support PDF, Fountain, TXT, and Markdown files."
        )

    if work_type != "screenplay" and format_name == "fountain":
        work_type = "screenplay"

    if work_type != "screenplay" and format_name not in {"pdf", "epub", *TEXT_ONLY_UPLOAD_FORMATS}:
        raise HTTPException(400, f"Unsupported upload format: {filename}")

    return format_name, work_type


def upload_filename_for_format(format_name: str) -> str:
    extension = FORMAT_TO_UPLOAD_EXTENSION.get(
        " ".join((format_name or "").split()).strip().lower(), ".txt"
    )
    return f"upload{extension}"


def story_unit_name(
    book_or_work_type: Book | str | None, *, plural: bool = False, lowercase: bool = False
) -> str:
    work_type = (
        book_or_work_type.work_type
        if isinstance(book_or_work_type, Book)
        else str(book_or_work_type or "")
    )
    base = "scene" if work_type == "screenplay" else "chapter"
    if not lowercase:
        base = base.title()
    if plural:
        return f"{base}s"
    return base


def story_unit_label(
    book_or_work_type: Book | str | None,
    number: int | None,
    *,
    fallback: str = "-",
    short: bool = False,
    lowercase: bool = False,
    index_format: str = "arabic",
) -> str:
    if not number:
        return fallback
    label = (
        "Sc." if short and story_unit_name(book_or_work_type, lowercase=True) == "scene" else None
    )
    if label is None:
        label = "Ch." if short else story_unit_name(book_or_work_type, lowercase=lowercase)
    return f"{label} {format_index(number, index_format)}"


_CHAPTER_KIND_LABELS: dict[str, str] = {
    "chapter": "",
    "preface": "Preface",
    "introduction": "Introduction",
    "foreword": "Foreword",
    "prologue": "Prologue",
    "epilogue": "Epilogue",
    "appendix": "Appendix",
    "acknowledgments": "Acknowledgments",
    "afterword": "Afterword",
    "dedication": "Dedication",
    "toc": "Table of Contents",
    "index": "Index",
    "title_page": "Title Page",
    "copyright": "Copyright",
    "notes": "Author’s Note",
    "glossary": "Glossary",
    "chronology": "Chronology",
    "part_opening": "Part Opening",
    "interlude": "Interlude",
    "unknown": "Section",
}

_CHAPTER_KIND_ALIASES: dict[str, str] = {
    "acknowledgements": "acknowledgments",
    "contents": "toc",
    "table_of_contents": "toc",
}

_SUPPORTED_CHAPTER_KINDS = frozenset(_CHAPTER_KIND_LABELS)


def chapter_kind_label(
    chapter_kind: str | None, number: int | None = None, index_format: str = "arabic"
) -> str:
    if not chapter_kind or chapter_kind == "chapter":
        if number is not None:
            return f"Chapter {format_index(number, index_format)}"
        return "Chapter"
    return _CHAPTER_KIND_LABELS.get(chapter_kind, chapter_kind.replace("_", " ").title())


def normalize_chapter_kind(value: str | None) -> str:
    if not value:
        return "chapter"
    normalized = "_".join(str(value).strip().lower().replace("-", "_").split())
    normalized = _CHAPTER_KIND_ALIASES.get(normalized, normalized)
    if normalized in _SUPPORTED_CHAPTER_KINDS:
        return normalized
    return "chapter"
