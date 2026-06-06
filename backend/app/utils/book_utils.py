"""
Book utility helpers — DB query wrappers, cover management, progress
computation, manuscript parsing, and chapter number utilities extracted
from the books route.
"""
from __future__ import annotations

import asyncio
import bisect
import hashlib
import io
import json
import os
import re
import statistics
import uuid
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import bleach  # type: ignore[import-untyped]
from bleach.css_sanitizer import CSSSanitizer
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.config import settings
from app.core.security import create_asset_token
from app.core.storage import download_book, get_presigned_url, upload_binary, upload_text
from app.models.book import (
    Book,
    BookCollaborator,
    BookNote,
    Chapter,
    ChapterMedia,
    ChapterVersion,
    Dialogue,
    ManuscriptAnnotation,
    NoteBacklink,
    NoteLink,
    NoteSeriesLink,
    NoteTag,
    NovelScene,
    VaultNote,
    VaultNoteSource,
    SceneVersion,
    Scene,
    Series,
    SeriesBook,
)
from app.models.beta_read import BetaReadAssignment, BetaReadAssignmentState
from app.models.character import Character, CharacterState, CharacterVoiceProfile
from app.models.character import (
    CharacterCandidate,
    CharacterMention,
    CharacterRelationshipCandidate,
    CharacterSuppression,
)
from app.models.intelligence import (
    BookChunk,
    ChapterSummary,
    CharacterRelationship,
    PlotThread,
    QuoteEntry,
    WikiEntry,
    WorldBuildingDocument,
    WorldGapAnalysis,
    WorldNote,
)
from app.models.progress import ReadingProgress
from app.models.tag import CustomTag
from app.models.user import User
from app.utils.intelligence_utils import (
    compute_voice_metrics,
    extract_dialogue_samples_by_character,
    score_voice_match,
)
from app.utils.plot_thread_utils import (
    derive_plot_thread_status,
    is_plot_thread_closed,
    is_plot_thread_open,
)
from app.utils.tag_utils import (
    ENTITY_TYPE_CHAPTER,
    ENTITY_TYPE_NOTE,
    ENTITY_TYPE_SCENE,
    get_custom_tags_for_entity,
    list_custom_tags_for_entity_ids,
)
from app.utils.upload_security_utils import validate_zip_archive_safety
from app.schemas.books import (
    BookOut,
    BookCollaboratorOut,
    BookProcessingOut,
    ChapterConsistencyReport,
    ChapterReportCharacter,
    CollaborationPermissions,
    CollaborationScope,
    SeriesOut,
    SeriesBibleCanonEntryOut,
    SeriesBibleCharacterOut,
    SeriesBibleEpisodeOut,
    SeriesBibleOut,
    SeriesBiblePlotThreadOut,
    SeriesBibleRelationshipOut,
    StoryHealthOut,
)

if TYPE_CHECKING:
    pass


MANUSCRIPT_ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "h1",
    "h2",
    "h3",
    "blockquote",
    "ul",
    "ol",
    "li",
    "span",
    "div",
    "img",
    "mark",
    "hr",
    "a",
]
MANUSCRIPT_ALLOWED_ATTRIBUTES = {
    "p": ["style", "class", "data-text-align"],
    "div": ["style", "class", "data-text-align", "data-scene-break", "data-page-break"],
    "span": ["style", "class", "data-mention"],
    "h1": ["style", "class", "data-text-align"],
    "h2": ["style", "class", "data-text-align"],
    "h3": ["style", "class", "data-text-align"],
    "blockquote": ["style", "class", "data-text-align"],
    "ul": ["style", "class", "data-type"],
    "ol": ["style", "class"],
    "li": ["style", "class", "data-type", "data-checked"],
    "img": ["src", "alt", "title", "width", "height"],
    "a": ["href", "target", "rel"],
    "mark": ["style", "class"],
}
MANUSCRIPT_ALLOWED_STYLES = ["text-align", "color", "background-color", "font-family", "font-size", "line-height", "margin-bottom", "text-indent"]
MANUSCRIPT_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel", "data"]
WIKI_LINK_RE = re.compile(r"\[\[([^\[\]\n]+)\]\]")
WIKI_REFERENCE_RE = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")
WIKI_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9/_-]*)")
VAULT_NOTE_SOURCES = {
    VaultNoteSource.CHARACTER_BIBLE.value,
    VaultNoteSource.USER_NOTES.value,
}
MANUSCRIPT_ANNOTATION_STATUSES = {"open", "resolved"}
MANUSCRIPT_ANNOTATION_VISIBILITIES = {"shared", "private"}
MANUSCRIPT_ANNOTATION_CATEGORIES = {
    "general",
    "continuity",
    "character",
    "worldbuilding",
    "pacing",
    "line_edit",
    "theme",
}
CHAPTER_TITLE_MIN_WORDS = 1
CHAPTER_TITLE_MAX_WORDS = 4
CHAPTER_TITLE_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
CHAPTER_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
REVISION_KEYWORD_STOPWORDS = CHAPTER_TITLE_STOPWORDS | {
    "all",
    "also",
    "aide",
    "ailleurs",
    "almost",
    "already",
    "another",
    "anything",
    "apr",
    "are",
    "around",
    "asked",
    "auteur",
    "auteurs",
    "been",
    "being",
    "but",
    "can",
    "cannot",
    "could",
    "did",
    "does",
    "done",
    "down",
    "else",
    "even",
    "every",
    "find",
    "from",
    "get",
    "got",
    "had",
    "has",
    "have",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "into",
    "just",
    "learns",
    "made",
    "make",
    "more",
    "most",
    "much",
    "need",
    "needs",
    "not",
    "now",
    "off",
    "one",
    "only",
    "open",
    "our",
    "out",
    "over",
    "own",
    "said",
    "same",
    "says",
    "she",
    "should",
    "some",
    "still",
    "than",
    "that",
    "them",
    "then",
    "these",
    "they",
    "this",
    "those",
    "told",
    "too",
    "under",
    "very",
    "wait",
    "was",
    "way",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "would",
    "your",
}

BLEACH_EMPTY_TAGS: Any = frozenset()


def _clean_text(value: object | None) -> str:
    return str(bleach.clean(str(value or "").strip(), tags=BLEACH_EMPTY_TAGS, strip=True))


def _clean_optional_text(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    return cleaned or None


def _count_words(text: str) -> int:
    cleaned = " ".join((text or "").split()).strip()
    return len(cleaned.split()) if cleaned else 0


def _chapter_title_word_count(title: str | None) -> int:
    return len(CHAPTER_TITLE_WORD_RE.findall(title or ""))


def normalize_chapter_title(title: str | None) -> str | None:
    cleaned = _clean_optional_text(" ".join(str(title or "").split()).strip())
    if cleaned is None:
        return None
    word_count = _chapter_title_word_count(cleaned)
    if word_count < CHAPTER_TITLE_MIN_WORDS or word_count > CHAPTER_TITLE_MAX_WORDS:
        raise HTTPException(
            400,
            f"Chapter title must be between {CHAPTER_TITLE_MIN_WORDS} and {CHAPTER_TITLE_MAX_WORDS} words.",
        )
    return cleaned


def chapter_title_is_placeholder(title: str | None, *, chapter_number: int | None = None) -> bool:
    cleaned = " ".join(str(title or "").split()).strip().lower()
    if not cleaned:
        return True
    if chapter_number is not None and cleaned == f"chapter {chapter_number}".lower():
        return True
    return bool(
        re.fullmatch(
            r"(chapter|part|section|scene|act|book|episode|volume)\s+([0-9]+|[ivxlcdm]+|[a-z])",
            cleaned,
        )
    )


def build_chapter_title_from_summary(
    summary: str | None,
    *,
    key_events: list[dict[str, Any]] | None = None,
) -> str | None:
    candidates: list[str] = []
    for event in key_events or []:
        if not isinstance(event, dict):
            continue
        event_title = _clean_optional_text(str(event.get("event_title") or event.get("event") or "").strip())
        if event_title:
            candidates.append(event_title)
    cleaned_summary = _clean_optional_text(summary)
    if cleaned_summary:
        first_sentence = re.split(r"(?<=[.!?])\s+", cleaned_summary, maxsplit=1)[0].strip()
        if first_sentence:
            candidates.append(first_sentence)
        candidates.append(cleaned_summary)

    for candidate in candidates:
        words = CHAPTER_TITLE_WORD_RE.findall(candidate)
        if not words:
            continue
        meaningful_words = [word for word in words if word.lower() not in CHAPTER_TITLE_STOPWORDS]
        selected_words = (meaningful_words or words)[:CHAPTER_TITLE_MAX_WORDS]
        generated = " ".join(word.capitalize() for word in selected_words).strip()
        if generated:
            return generated
    return None


DEFAULT_WRITING_TEMPLATES = [
    {
        "id": "chapter-three-act",
        "kind": "chapter",
        "title": "Chapter Three-Beat",
        "description": "Open with pressure, pivot in the middle, end on a story-moving turn.",
        "content": (
            "Opening beat\n"
            "- What changes immediately in this chapter?\n\n"
            "Middle escalation\n"
            "- What complication or reversal raises the cost?\n\n"
            "Closing turn\n"
            "- What question, threat, or choice launches the next chapter?"
        ),
    },
    {
        "id": "scene-goal-conflict-disaster",
        "kind": "scene",
        "title": "Scene Goal / Conflict / Disaster",
        "description": "Classic scene structure for momentum and tension.",
        "content": (
            "Goal\n"
            "- What does the point-of-view character want right now?\n\n"
            "Conflict\n"
            "- Who or what blocks them?\n\n"
            "Disaster / turn\n"
            "- What goes wrong, changes, or costs more than expected?"
        ),
    },
    {
        "id": "story-five-pivots",
        "kind": "story",
        "title": "Story Five Pivots",
        "description": "A compact scaffold for act structure and turning points.",
        "content": (
            "Setup promise\n"
            "- What emotional and plot promise does the story make?\n\n"
            "Inciting shift\n"
            "- What forces the protagonist out of stasis?\n\n"
            "Midpoint change\n"
            "- What truth, reveal, or victory changes the meaning of the conflict?\n\n"
            "Dark turn\n"
            "- What loss or collapse strips away the easy path?\n\n"
            "Climax and aftermath\n"
            "- What final choice resolves the central pressure?"
        ),
    },
]

DEFAULT_WRITER_WORKSPACE = {
    "word_count_goals": {
        "chapter_target": 2500,
        "book_target": 80000,
        "session_target": 1000,
    },
    "goal_calendar": [],
    "corkboard_cards": [],
    "templates": DEFAULT_WRITING_TEMPLATES,
    "publishing": {
        "active_preset": "standard_manuscript",
        "trim_size": "6x9",
        "include_title_page": True,
        "mirror_margins": True,
    },
    "editor_preferences": {
        "font_family": "Times New Roman",
        "font_size": 12,
        "line_height": 1.8,
        "manuscript_width": "standard",
        "show_page_guides": True,
        "focus_mode": False,
        "default_scene_separator": "asterisks",
    },
    "reading_themes": {
        "active_theme": "light",
        "allow_dark_mode": True,
    },
    "typewriter_mode": {
        "enabled": False,
        "center_offset_px": 160,
    },
    "manuscript_layout": {
        "margins": "standard",
        "page_size": "letter",
        "orientation": "portrait",
        "show_headers": True,
        "show_footers": True,
        "page_numbering": True,
        "different_first_page": True,
    },
    "structure_tree": [],
    "manuscript_front_matter": {
        "author_name": "",
        "pen_name": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_address": "",
        "title": "",
        "subtitle": "",
        "header_last_name": "",
        "header_title": "",
        "approximate_word_count_override": None,
        "dedication": "",
        "acknowledgments": "",
        "epigraph": "",
        "prologue": "",
        "include_dedication": False,
        "include_acknowledgments": False,
        "include_epigraph": False,
        "include_prologue": False,
    },
    "revision_board": {
        "items": [],
        "last_generated_at": None,
    },
    "revision_recent_edits": [],
    "reprocess": {
        "auto_reprocess_enabled": True,
        "pending_chapters": [],
    },
    "processing": None,
}


@dataclass(slots=True)
class BookRenderContext:
    progress_by_book_id: dict[uuid.UUID, ReadingProgress]
    total_words_by_book_id: dict[uuid.UUID, int]
    cover_url_by_book_id: dict[uuid.UUID, str | None]

BOOK_WORK_TYPES = {"novel", "screenplay", "other"}
UPLOAD_EXTENSION_TO_FORMAT = {
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
TEXT_ONLY_UPLOAD_FORMATS = {"docx", "doc", "txt", "md"}
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
SCENE_METADATA_UI_FIELDS = {"pov", "timeline", "location", "tags", "mood", "status_note", "anchors", "bookmarks", "summary"}
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
REVISION_THIRD_PERSON_MARKERS = {"he", "she", "they", "him", "her", "them", "his", "hers", "their", "theirs"}
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


def resolve_upload_format_and_work_type(filename: str, explicit_work_type: str | None = None) -> tuple[str, str]:
    format_name = detect_upload_format(filename)
    if not format_name:
        raise HTTPException(400, f"Unsupported upload format: {filename}")

    inferred_work_type = infer_work_type_from_filename(filename)
    work_type = normalize_book_work_type(explicit_work_type, default=inferred_work_type or "novel")

    if work_type == "screenplay" and format_name not in SCREENPLAY_INPUT_FORMATS:
        raise HTTPException(400, "Screenplay uploads support PDF, Fountain, TXT, and Markdown files.")

    if work_type != "screenplay" and format_name == "fountain":
        work_type = "screenplay"

    if work_type != "screenplay" and format_name not in {"pdf", "epub", *TEXT_ONLY_UPLOAD_FORMATS}:
        raise HTTPException(400, f"Unsupported upload format: {filename}")

    return format_name, work_type


def upload_filename_for_format(format_name: str) -> str:
    extension = FORMAT_TO_UPLOAD_EXTENSION.get(" ".join((format_name or "").split()).strip().lower(), ".txt")
    return f"upload{extension}"


def story_unit_name(book_or_work_type: Book | str | None, *, plural: bool = False, lowercase: bool = False) -> str:
    work_type = book_or_work_type.work_type if isinstance(book_or_work_type, Book) else str(book_or_work_type or "")
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
) -> str:
    if not number:
        return fallback
    label = "Sc." if short and story_unit_name(book_or_work_type, lowercase=True) == "scene" else None
    if label is None:
        label = "Ch." if short else story_unit_name(book_or_work_type, lowercase=lowercase)
    return f"{label} {number}"


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
}

_CHAPTER_KIND_ALIASES: dict[str, str] = {
    "acknowledgements": "acknowledgments",
    "contents": "toc",
    "table_of_contents": "toc",
}

_SUPPORTED_CHAPTER_KINDS = frozenset(_CHAPTER_KIND_LABELS)


def chapter_kind_label(chapter_kind: str | None, number: int | None = None) -> str:
    if not chapter_kind or chapter_kind == "chapter":
        if number is not None:
            return f"Chapter {number}"
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


def _normalize_processing_timestamp(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    raw = " ".join(str(value).strip().split())
    if not raw:
        return None
    normalized = raw
    if len(normalized) >= 20 and normalized[10] == " ":
        normalized = f"{normalized[:10]}T{normalized[11:]}"
    if re.search(r"[+-]\d{2}$", normalized):
        normalized = f"{normalized}:00"
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return normalized


def _normalize_processing_state(raw: dict | None) -> dict | None:
    source = raw if isinstance(raw, dict) else {}

    status = " ".join(str(source.get("status") or "").split()).strip() or None
    stage = " ".join(str(source.get("stage") or "").split()).strip() or None
    progress_pct = source.get("progress_pct")
    chapters_completed = source.get("chapters_completed")
    chapters_total = source.get("chapters_total")
    eta_seconds = source.get("eta_seconds")
    queue_wait_ms = source.get("queue_wait_ms")
    last_chapter_number = source.get("last_chapter_number")
    last_chapter_title = " ".join(str(source.get("last_chapter_title") or "").split()).strip() or None
    started_at = source.get("started_at")
    updated_at = source.get("updated_at")
    last_error = " ".join(str(source.get("last_error") or "").split()).strip() or None
    parser_diagnostics = source.get("parser_diagnostics") if isinstance(source.get("parser_diagnostics"), dict) else None
    is_fully_ready = bool(source.get("is_fully_ready", False))
    retry_actions = [
        " ".join(str(item).split()).strip()
        for item in (source.get("retry_actions") or [])
        if " ".join(str(item).split()).strip()
    ]
    raw_pipeline = source.get("pipeline") if isinstance(source.get("pipeline"), dict) else {}

    payload: dict[str, Any] = {}
    if status:
        payload["status"] = status
    if stage:
        payload["stage"] = stage
    if isinstance(progress_pct, (int, float)):
        payload["progress_pct"] = float(progress_pct)
    if isinstance(chapters_completed, (int, float)) and int(chapters_completed) >= 0:
        payload["chapters_completed"] = int(chapters_completed)
    if isinstance(chapters_total, (int, float)) and int(chapters_total) >= 0:
        payload["chapters_total"] = int(chapters_total)
    if isinstance(eta_seconds, (int, float)) and int(eta_seconds) >= 0:
        payload["eta_seconds"] = int(eta_seconds)
    if isinstance(queue_wait_ms, (int, float)) and int(queue_wait_ms) >= 0:
        payload["queue_wait_ms"] = int(queue_wait_ms)
    if isinstance(last_chapter_number, (int, float)) and int(last_chapter_number) >= 0:
        payload["last_chapter_number"] = int(last_chapter_number)
    if last_chapter_title:
        payload["last_chapter_title"] = last_chapter_title
    if started_at:
        payload["started_at"] = _normalize_processing_timestamp(started_at)
    if updated_at:
        payload["updated_at"] = _normalize_processing_timestamp(updated_at)
    if last_error:
        payload["last_error"] = last_error
    if parser_diagnostics:
        payload["parser_diagnostics"] = parser_diagnostics
    payload["is_fully_ready"] = is_fully_ready
    if retry_actions:
        payload["retry_actions"] = retry_actions
    if raw_pipeline:
        pipeline: dict[str, Any] = {}
        for key in ("extraction", "analysis"):
            stage = raw_pipeline.get(key) if isinstance(raw_pipeline.get(key), dict) else None
            if not stage:
                continue
            normalized_stage: dict[str, Any] = {}
            normalized_status = " ".join(str(stage.get("status") or "").split()).strip() or None
            if normalized_status:
                normalized_stage["status"] = normalized_status
            completed = stage.get("completed_chapters")
            if isinstance(completed, (int, float)) and int(completed) >= 0:
                normalized_stage["completed_chapters"] = int(completed)
            total = stage.get("total_chapters")
            if isinstance(total, (int, float)) and int(total) >= 0:
                normalized_stage["total_chapters"] = int(total)
            stage_updated = stage.get("updated_at")
            if stage_updated:
                normalized_stage["updated_at"] = _normalize_processing_timestamp(stage_updated)
            stage_eta = stage.get("eta_seconds")
            if isinstance(stage_eta, (int, float)) and int(stage_eta) >= 0:
                normalized_stage["eta_seconds"] = int(stage_eta)
            stage_error = " ".join(str(stage.get("last_error") or "").split()).strip() or None
            if stage_error:
                normalized_stage["last_error"] = stage_error
            failed_chapters = stage.get("failed_chapters")
            if isinstance(failed_chapters, list):
                normalized_stage["failed_chapters"] = [
                    int(item)
                    for item in failed_chapters
                    if isinstance(item, (int, float)) and int(item) > 0
                ]
            if normalized_stage:
                pipeline[key] = normalized_stage
        if pipeline:
            payload["pipeline"] = pipeline

    return payload or None


def normalize_reprocess_metadata(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    payload = json.loads(json.dumps(source, default=str))
    payload["auto_reprocess_enabled"] = bool(source.get("auto_reprocess_enabled", True))
    pending_chapters = sorted({
        int(item)
        for item in (source.get("pending_chapters") or [])
        if isinstance(item, (int, float)) and int(item) > 0
    })
    payload["pending_chapters"] = pending_chapters
    for key in (
        "last_mode_changed_at",
        "last_manual_chapter_started_at",
        "last_manual_chapter_number",
    ):
        value = source.get(key)
        if value is None or value == "":
            payload.pop(key, None)
        elif key == "last_manual_chapter_number" and isinstance(value, (int, float)):
            payload[key] = int(value)
        else:
            payload[key] = str(value).strip()
    return payload


def _derive_front_matter_defaults(raw: dict | None = None, *, title: str = "", author: str = "") -> dict[str, Any]:
    payload = json.loads(json.dumps(DEFAULT_WRITER_WORKSPACE["manuscript_front_matter"]))
    source = raw if isinstance(raw, dict) else {}

    payload["author_name"] = " ".join(str(source.get("author_name") or author or "").split()).strip()
    payload["pen_name"] = " ".join(str(source.get("pen_name") or "").split()).strip()
    payload["contact_email"] = " ".join(str(source.get("contact_email") or "").split()).strip()
    payload["contact_phone"] = " ".join(str(source.get("contact_phone") or "").split()).strip()
    payload["contact_address"] = str(source.get("contact_address") or "").strip()
    payload["title"] = " ".join(str(source.get("title") or title or "").split()).strip()
    payload["subtitle"] = " ".join(str(source.get("subtitle") or "").split()).strip()

    header_last_name = " ".join(str(source.get("header_last_name") or "").split()).strip()
    if not header_last_name:
        fallback_name = payload["pen_name"] or payload["author_name"]
        header_last_name = fallback_name.split()[-1] if fallback_name else ""
    payload["header_last_name"] = header_last_name
    payload["header_title"] = " ".join(str(source.get("header_title") or payload["title"] or "").split()).strip()

    override = source.get("approximate_word_count_override")
    payload["approximate_word_count_override"] = int(override) if isinstance(override, (int, float)) and int(override) > 0 else None

    for key in ("dedication", "acknowledgments", "epigraph", "prologue"):
        payload[key] = str(source.get(key) or "").strip()
    for key in ("include_dedication", "include_acknowledgments", "include_epigraph", "include_prologue"):
        payload[key] = bool(source.get(key, False))

    return payload


def _normalize_revision_board(raw: dict | None) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    items: list[dict[str, Any]] = []
    seen_item_ids: set[str] = set()
    for item in source.get("items") or []:
        if not isinstance(item, dict):
            continue
        item_id = " ".join(str(item.get("item_id") or "").split()).strip()
        if not item_id or item_id in seen_item_ids:
            continue
        seen_item_ids.add(item_id)
        status = " ".join(str(item.get("status") or "pending").split()).strip().lower() or "pending"
        if status not in REVISION_ITEM_STATUSES:
            status = "pending"
        assigned_version_id = " ".join(str(item.get("assigned_version_id") or "").split()).strip() or None
        task_id = " ".join(str(item.get("task_id") or "").split()).strip() or None
        updated_at = " ".join(str(item.get("updated_at") or "").split()).strip() or None
        items.append(
            {
                "item_id": item_id,
                "status": status,
                "assigned_version_id": assigned_version_id,
                "task_id": task_id,
                "updated_at": updated_at,
            }
        )
    return {
        "items": items,
        "last_generated_at": " ".join(str(source.get("last_generated_at") or "").split()).strip() or None,
    }


def _normalize_revision_recent_edits(raw: object) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        edit_id = " ".join(str(item.get("id") or "").split()).strip() or str(uuid.uuid4())
        kind = " ".join(str(item.get("kind") or "").split()).strip().lower() or "chapter"
        if kind not in {"chapter", "scene", "scene_deleted", "scene_reordered"}:
            kind = "chapter"
        chapter_number = item.get("chapter_number")
        edits.append(
            {
                "id": edit_id,
                "kind": kind,
                "chapter_number": int(chapter_number) if isinstance(chapter_number, (int, float)) and int(chapter_number) > 0 else None,
                "scene_id": " ".join(str(item.get("scene_id") or "").split()).strip() or None,
                "scene_title": " ".join(str(item.get("scene_title") or "").split()).strip() or None,
                "unit_label": " ".join(str(item.get("unit_label") or "").split()).strip() or None,
                "before_text": str(item.get("before_text") or "").strip(),
                "after_text": str(item.get("after_text") or "").strip(),
                "updated_at": " ".join(str(item.get("updated_at") or "").split()).strip() or None,
                "source_version_id": " ".join(str(item.get("source_version_id") or "").split()).strip() or None,
            }
        )
    edits.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return edits[:MAX_REVISION_RECENT_EDITS]


def _append_recent_revision_edit(
    book: Book,
    *,
    kind: str,
    chapter_number: int | None,
    before_text: str,
    after_text: str,
    scene_id: str | None = None,
    scene_title: str | None = None,
    source_version_id: str | None = None,
) -> None:
    workspace = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
    existing = _normalize_revision_recent_edits((book.writer_workspace or {}).get("revision_recent_edits") if isinstance(book.writer_workspace, dict) else [])
    unit_label = (
        f"Scene \"{scene_title}\""
        if kind.startswith("scene") and scene_title
        else story_unit_label(book, chapter_number, fallback="manuscript change")
    )
    next_edit = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "chapter_number": chapter_number,
        "scene_id": scene_id,
        "scene_title": scene_title,
        "unit_label": unit_label,
        "before_text": (before_text or "").strip(),
        "after_text": (after_text or "").strip(),
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source_version_id": source_version_id,
    }
    deduped = [
        item
        for item in existing
        if not (
            item.get("kind") == next_edit["kind"]
            and item.get("chapter_number") == next_edit["chapter_number"]
            and item.get("scene_id") == next_edit["scene_id"]
        )
    ]
    workspace["revision_recent_edits"] = [next_edit, *deduped][:MAX_REVISION_RECENT_EDITS]
    book.writer_workspace = workspace


def touch_public_book_updated_at(book: Book, *, changed_at: datetime | None = None) -> None:
    book.public_updated_at = changed_at or datetime.now(UTC)


def normalize_writer_workspace(raw: dict | None) -> dict:
    payload = json.loads(json.dumps(DEFAULT_WRITER_WORKSPACE))
    source = raw if isinstance(raw, dict) else {}

    goals = source.get("word_count_goals")
    if isinstance(goals, dict):
        for key in ("chapter_target", "book_target", "session_target"):
            value = goals.get(key)
            payload["word_count_goals"][key] = int(value) if isinstance(value, (int, float)) and int(value) > 0 else None

    calendar_items: list[dict[str, Any]] = []
    for item in source.get("goal_calendar") or []:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split()).strip()
        due_date = " ".join(str(item.get("due_date") or "").split()).strip()
        if not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
            continue
        quota_value = item.get("quota_value")
        quota_unit = " ".join(str(item.get("quota_unit") or "").split()).strip() or None
        calendar_items.append(
            {
                "id": str(item.get("id") or uuid.uuid4()),
                "title": title,
                "due_date": due_date,
                "quota_value": int(quota_value) if isinstance(quota_value, (int, float)) and int(quota_value) > 0 else None,
                "quota_unit": quota_unit,
                "completed": bool(item.get("completed", False)),
            }
        )
    payload["goal_calendar"] = calendar_items

    cards: list[dict[str, Any]] = []
    for card in source.get("corkboard_cards") or []:
        if not isinstance(card, dict):
            continue
        title = " ".join(str(card.get("title") or "").split()).strip()
        if not title:
            continue
        chapter_number = card.get("chapter_number")
        cards.append(
            {
                "id": str(card.get("id") or uuid.uuid4()),
                "title": title,
                "description": str(card.get("description") or "").strip(),
                "status": " ".join(str(card.get("status") or "planned").split()).strip() or "planned",
                "lane": " ".join(str(card.get("lane") or "ideas").split()).strip() or "ideas",
                "chapter_number": int(chapter_number) if isinstance(chapter_number, (int, float)) and int(chapter_number) > 0 else None,
                "template_id": " ".join(str(card.get("template_id") or "").split()).strip() or None,
            }
        )
    payload["corkboard_cards"] = cards

    templates: list[dict[str, str]] = []
    for template in source.get("templates") or DEFAULT_WRITING_TEMPLATES:
        if not isinstance(template, dict):
            continue
        template_id = " ".join(str(template.get("id") or "").split()).strip()
        kind = " ".join(str(template.get("kind") or "").split()).strip()
        title = " ".join(str(template.get("title") or "").split()).strip()
        content = str(template.get("content") or "").strip()
        if not template_id or not kind or not title or not content:
            continue
        templates.append(
            {
                "id": template_id,
                "kind": kind,
                "title": title,
                "description": " ".join(str(template.get("description") or "").split()).strip(),
                "content": content,
            }
        )
    payload["templates"] = templates or json.loads(json.dumps(DEFAULT_WRITING_TEMPLATES))

    publishing = source.get("publishing")
    if isinstance(publishing, dict):
        payload["publishing"] = {
            "active_preset": " ".join(str(publishing.get("active_preset") or "standard_manuscript").split()).strip() or "standard_manuscript",
            "trim_size": " ".join(str(publishing.get("trim_size") or "6x9").split()).strip() or "6x9",
            "include_title_page": bool(publishing.get("include_title_page", True)),
            "mirror_margins": bool(publishing.get("mirror_margins", True)),
        }

    editor_preferences = source.get("editor_preferences")
    if isinstance(editor_preferences, dict):
        payload["editor_preferences"] = {
            "font_family": " ".join(str(editor_preferences.get("font_family") or "Times New Roman").split()).strip() or "Times New Roman",
            "font_size": int(editor_preferences.get("font_size")) if isinstance(editor_preferences.get("font_size"), (int, float)) and 8 <= int(editor_preferences.get("font_size")) <= 36 else 12,
            "line_height": float(editor_preferences.get("line_height")) if isinstance(editor_preferences.get("line_height"), (int, float)) and 1 <= float(editor_preferences.get("line_height")) <= 3 else 1.8,
            "manuscript_width": " ".join(str(editor_preferences.get("manuscript_width") or "standard").split()).strip() or "standard",
            "show_page_guides": bool(editor_preferences.get("show_page_guides", True)),
            "focus_mode": bool(editor_preferences.get("focus_mode", False)),
            "default_scene_separator": " ".join(str(editor_preferences.get("default_scene_separator") or "asterisks").split()).strip() or "asterisks",
        }

    reading_themes = source.get("reading_themes")
    if isinstance(reading_themes, dict):
        payload["reading_themes"] = {
            "active_theme": " ".join(str(reading_themes.get("active_theme") or "light").split()).strip() or "light",
            "allow_dark_mode": bool(reading_themes.get("allow_dark_mode", True)),
        }

    typewriter_mode = source.get("typewriter_mode")
    if isinstance(typewriter_mode, dict):
        payload["typewriter_mode"] = {
            "enabled": bool(typewriter_mode.get("enabled", False)),
            "center_offset_px": int(typewriter_mode.get("center_offset_px")) if isinstance(typewriter_mode.get("center_offset_px"), (int, float)) else 160,
        }

    manuscript_layout = source.get("manuscript_layout")
    if isinstance(manuscript_layout, dict):
        payload["manuscript_layout"] = {
            "margins": " ".join(str(manuscript_layout.get("margins") or "standard").split()).strip() or "standard",
            "page_size": " ".join(str(manuscript_layout.get("page_size") or "letter").split()).strip() or "letter",
            "orientation": " ".join(str(manuscript_layout.get("orientation") or "portrait").split()).strip() or "portrait",
            "show_headers": bool(manuscript_layout.get("show_headers", True)),
            "show_footers": bool(manuscript_layout.get("show_footers", True)),
            "page_numbering": bool(manuscript_layout.get("page_numbering", True)),
            "different_first_page": bool(manuscript_layout.get("different_first_page", True)),
        }

    structure_tree = source.get("structure_tree")
    if isinstance(structure_tree, list):
        payload["structure_tree"] = json.loads(json.dumps(structure_tree))

    payload["manuscript_front_matter"] = _derive_front_matter_defaults(source.get("manuscript_front_matter"))
    payload["revision_board"] = _normalize_revision_board(source.get("revision_board"))
    payload["revision_recent_edits"] = _normalize_revision_recent_edits(source.get("revision_recent_edits") or [])
    payload["processing"] = _normalize_processing_state(source.get("processing")) if isinstance(source.get("processing"), dict) else None
    payload["reprocess"] = normalize_reprocess_metadata(source.get("reprocess") if isinstance(source.get("reprocess"), dict) else None)

    return payload


def build_writer_workspace_payload(book: Book) -> dict:
    payload = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
    payload["manuscript_front_matter"] = _derive_front_matter_defaults(
        payload.get("manuscript_front_matter"),
        title=book.title or "",
        author=book.author or "",
    )
    return payload


def build_book_processing_payload(book: Book) -> dict[str, Any] | None:
    workspace = normalize_writer_workspace(book.writer_workspace if isinstance(book.writer_workspace, dict) else None)
    processing = workspace.get("processing")
    if not isinstance(processing, dict) or not processing:
        return None
    return BookProcessingOut.model_validate(processing).model_dump(mode="json")


def _stable_revision_item_id(*parts: object) -> str:
    payload = "||".join(" ".join(str(part or "").split()).strip().lower() for part in parts)
    return f"rev-{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"


def _revision_board_state_map(workspace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    board = workspace.get("revision_board") if isinstance(workspace.get("revision_board"), dict) else {}
    items = board.get("items") if isinstance(board, dict) else []
    state_map: dict[str, dict[str, Any]] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            continue
        state_map[item_id] = item
    return state_map


def _overlay_revision_state(item: dict[str, Any], state_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = dict(item)
    state = state_map.get(str(item.get("id") or ""))
    if not isinstance(state, dict):
        state = {}
    payload["status"] = str(state.get("status") or payload.get("status") or "pending")
    payload["assigned_version_id"] = str(state.get("assigned_version_id") or "").strip() or payload.get("assigned_version_id")
    payload["task_id"] = str(state.get("task_id") or "").strip() or payload.get("task_id")
    return payload


def _make_revision_action_item(
    *,
    category: str,
    title: str,
    description: str,
    severity: str,
    chapter_ref: int | None = None,
    source_label: str | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    return {
        "id": _stable_revision_item_id(category, chapter_ref or 0, title, description[:160]),
        "category": category,
        "title": title,
        "description": description,
        "severity": severity,
        "chapter_ref": chapter_ref,
        "source_label": source_label,
        "recommendation": recommendation,
        "status": "pending",
        "assigned_version_id": None,
        "task_id": None,
    }


def _severity_from_text(text: str, *, high_threshold: int = 2) -> str:
    lowered = text.lower()
    hits = sum(
        1
        for marker in ("contradiction", "impossible", "no evidence", "break", "unforeshadowed", "no earlier", "inconsistent")
        if marker in lowered
    )
    if hits >= high_threshold:
        return "high"
    if hits >= 1:
        return "medium"
    return "low"


def _flatten_summary_points(value: object) -> list[str]:
    if isinstance(value, list):
        return [" ".join(str(item).split()).strip() for item in value if " ".join(str(item).split()).strip()]
    if isinstance(value, dict):
        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_flatten_summary_points(nested))
        return flattened
    if value:
        cleaned = " ".join(str(value).split()).strip()
        return [cleaned] if cleaned else []
    return []


def _scene_keyword_set(text: str, *, character_names: set[str], thread_terms: set[str]) -> set[str]:
    lowered = (text or "").lower()
    tokens = {
        token.lower().strip("'-")
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or "")
    }
    tokens = {
        token
        for token in tokens
        if len(token) > 2 and token not in REVISION_KEYWORD_STOPWORDS and not token.endswith("'")
    }
    tokens |= {name.lower() for name in character_names if name.lower() in lowered}
    tokens |= {term.lower() for term in thread_terms if term.lower() in lowered}
    return tokens


def _extract_chapter_text(raw: bytes | str) -> str:
    try:
        payload = deserialize_manuscript_content(raw)
        return str(payload.get("text") or "").strip()
    except Exception:
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="ignore").strip()
        return str(raw).strip()


async def _load_chapter_texts(chapters: list[Chapter]) -> dict[int, str]:
    loaded: dict[int, str] = {}
    for chapter in chapters:
        if not chapter.s3_key:
            loaded[chapter.number] = ""
            continue
        try:
            raw = await asyncio.to_thread(download_book, chapter.s3_key)
        except Exception:
            loaded[chapter.number] = ""
            continue
        loaded[chapter.number] = _extract_chapter_text(raw)
    return loaded


def _strip_dialogue_for_narration(text: str) -> str:
    return re.sub(r"\"[^\"]*\"", " ", text or "")


def _build_narration_signature(text: str) -> dict[str, float | int | str]:
    narration = _strip_dialogue_for_narration(text)
    words = re.findall(r"[A-Za-z']+", narration)
    lower_words = [word.lower() for word in words]
    sentences = [part.strip() for part in re.split(r"[.!?]+", narration) if part.strip()]
    total_words = max(1, len(words))
    first_person_hits = sum(1 for word in lower_words if word in REVISION_FIRST_PERSON_MARKERS)
    third_person_hits = sum(1 for word in lower_words if word in REVISION_THIRD_PERSON_MARKERS)
    avg_sentence_length = (
        sum(len(re.findall(r"[A-Za-z']+", sentence)) for sentence in sentences) / max(1, len(sentences))
        if sentences
        else 0.0
    )
    if first_person_hits >= max(3, third_person_hits * 2):
        pov_mode = "first-person"
    elif third_person_hits >= max(3, first_person_hits * 2):
        pov_mode = "third-person"
    else:
        pov_mode = "mixed"
    return {
        "pov_mode": pov_mode,
        "avg_sentence_length": round(avg_sentence_length, 2),
        "exclamation_rate": round(narration.count("!") / total_words, 4),
        "semicolon_rate": round(narration.count(";") / total_words, 4),
        "first_person_hits": first_person_hits,
        "third_person_hits": third_person_hits,
    }


def _describe_narration_shift(previous: dict[str, float | int | str], current: dict[str, float | int | str]) -> str | None:
    previous_mode = str(previous.get("pov_mode") or "mixed")
    current_mode = str(current.get("pov_mode") or "mixed")
    if previous_mode != current_mode and "mixed" not in {previous_mode, current_mode}:
        return f"Narration shifts from {previous_mode} anchoring into {current_mode} anchoring."
    sentence_delta = abs(float(current.get("avg_sentence_length") or 0.0) - float(previous.get("avg_sentence_length") or 0.0))
    exclamation_delta = abs(float(current.get("exclamation_rate") or 0.0) - float(previous.get("exclamation_rate") or 0.0))
    semicolon_delta = abs(float(current.get("semicolon_rate") or 0.0) - float(previous.get("semicolon_rate") or 0.0))
    if sentence_delta >= 6:
        return "Narration suddenly becomes much denser or much shorter than the surrounding chapters."
    if exclamation_delta >= 0.025 or semicolon_delta >= 0.018:
        return "Narrative tone markers jump sharply compared with the surrounding chapters."
    return None


async def _load_version_text(version: ChapterVersion) -> str:
    if not version.s3_key:
        return ""
    try:
        raw = await asyncio.to_thread(download_book, version.s3_key)
    except Exception:
        return ""
    return _extract_chapter_text(raw)


def _split_revision_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _build_revision_change_summary(
    *,
    before_text: str,
    after_text: str,
    unit_label: str,
    character_names: set[str],
    thread_terms: set[str],
    world_terms: set[str],
) -> tuple[str, list[str]]:
    before_terms = _scene_keyword_set(before_text, character_names=character_names, thread_terms=thread_terms | world_terms)
    after_terms = _scene_keyword_set(after_text, character_names=character_names, thread_terms=thread_terms | world_terms)
    removed_terms = [term for term in sorted(before_terms - after_terms) if len(term) > 2][:4]
    added_terms = [term for term in sorted(after_terms - before_terms) if len(term) > 2][:4]
    if removed_terms:
        return (f"You changed {unit_label}: removed or weakened {', '.join(removed_terms)}.", removed_terms)
    if added_terms:
        return (f"You changed {unit_label}: introduced or emphasized {', '.join(added_terms)}.", added_terms)
    before_sentences = _split_revision_sentences(before_text)
    after_sentences = _split_revision_sentences(after_text)
    if before_sentences and before_sentences != after_sentences:
        return (f"You changed {unit_label}: the scene logic and wording shifted enough to re-check downstream assumptions.", [])
    return (f"You changed {unit_label}.", [])


def _build_knowledge_timeline(
    *,
    knowledge_matrix: list[dict[str, Any]],
    chapter_numbers: list[int],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for fact in knowledge_matrix:
        rows: list[dict[str, Any]] = []
        for entry in fact.get("entries") or []:
            chapter_learned = entry.get("chapter_learned")
            cells: list[dict[str, Any]] = []
            for chapter_number in chapter_numbers:
                state = "unknown"
                if isinstance(chapter_learned, int):
                    if chapter_learned == chapter_number:
                        state = "learned"
                    elif chapter_learned < chapter_number:
                        state = "known"
                cells.append({"chapter_number": chapter_number, "state": state})
            rows.append(
                {
                    "character_name": entry.get("character_name"),
                    "chapter_learned": chapter_learned,
                    "source": entry.get("source"),
                    "cells": cells,
                }
            )
        timeline.append(
            {
                "fact": fact.get("fact"),
                "rows": rows,
                "warning": fact.get("warning"),
            }
        )
    return timeline


def _revision_item_text(item: Mapping[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "").strip().lower()
        for field in ("title", "description", "recommendation", "source_label", "category")
    )


def _genre_match_score(normalized_genre: str, item: Mapping[str, Any]) -> int:
    category = str(item.get("category") or "").strip().lower()
    haystack = _revision_item_text(item)
    score = 0

    if "fantasy" in normalized_genre or "historical" in normalized_genre or "epic" in normalized_genre:
        if category == "confusion":
            score += 3
        if category == "impact":
            score += 2
        if any(marker in haystack for marker in ("lore", "world", "setting", "faction", "term", "kingdom", "magic", "era", "politic")):
            score += 3
    if "sci-fi" in normalized_genre or "science fiction" in normalized_genre or "litrpg" in normalized_genre:
        if category in {"confusion", "impact"}:
            score += 3
        if any(marker in haystack for marker in ("technology", "system", "science", "future", "colony", "rule", "power", "stat")):
            score += 3
    if "romance" in normalized_genre:
        if category == "voice":
            score += 3
        if category in {"scene", "impact"}:
            score += 2
        if any(marker in haystack for marker in ("relationship", "emotion", "conflict", "payoff", "arc", "chemistry")):
            score += 3
    if "mystery" in normalized_genre or "thriller" in normalized_genre:
        if category == "impact":
            score += 3
        if category == "confusion":
            score += 2
        if any(marker in haystack for marker in ("clue", "timeline", "alibi", "reveal", "suspect", "evidence")):
            score += 3
    if "horror" in normalized_genre:
        if category == "voice":
            score += 3
        if category in {"impact", "scene"}:
            score += 2
        if any(marker in haystack for marker in ("threat", "dread", "ominous", "creature", "haunt", "fear")):
            score += 3
    if "young adult" in normalized_genre or normalized_genre == "ya":
        if category == "voice":
            score += 3
        if category == "scene":
            score += 2
        if any(marker in haystack for marker in ("voice", "emotion", "peer", "coming-of-age", "age")):
            score += 3
    if "web novel" in normalized_genre or "webnovel" in normalized_genre:
        if category in {"impact", "confusion"}:
            score += 2
        if any(marker in haystack for marker in ("recap", "reintroduction", "arc", "power", "cast")):
            score += 3

    return score


def _select_genre_findings(normalized_genre: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = [
        (_genre_match_score(normalized_genre, item), index, item)
        for index, item in enumerate(items)
    ]
    ranked = [entry for entry in ranked if entry[0] > 0]
    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    return [dict(item) for _, _, item in ranked[:3]]


def _select_genre_checks(genre: str | None, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = " ".join((genre or "").split()).strip().lower()
    if not normalized:
        return []
    selected: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for key, config in REVISION_GENRE_CHECKS.items():
        if key not in normalized:
            continue
        label = str(config["label"])
        if label in seen_labels:
            continue
        seen_labels.add(label)
        selected.append(
            {
                "genre": normalized,
                "label": label,
                "checks": list(config["checks"]),
                "rationale": f"LoreVia is weighting revision checks toward the story promises and failure modes that usually matter most in {label.lower()} manuscripts.",
                "findings": _select_genre_findings(normalized, items),
            }
        )
    return selected[:3]


def _build_knowledge_matrix(
    *,
    plot_threads: list[PlotThread],
    characters: list[Character],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    knowledge_facts: list[dict[str, Any]] = []
    surfaced_items: list[dict[str, Any]] = []
    character_names: list[str] = []
    seen_names: set[str] = set()
    for character in characters:
        normalized_name = " ".join(str(character.name or "").split()).strip()
        if not normalized_name or normalized_name.lower() in seen_names:
            continue
        seen_names.add(normalized_name.lower())
        character_names.append(normalized_name)

    for thread in plot_threads:
        related_names = [str(name).strip() for name in (thread.character_ids or []) if str(name).strip()]
        if not related_names and thread.description:
            related_names = [name for name in character_names if name.lower() in thread.description.lower()]
        related_lookup = {name.lower() for name in related_names}
        entries = [
            {
                "character_name": name,
                "chapter_learned": thread.introduced_at,
                "source": f"Tracked through the \"{thread.title}\" thread",
            }
            for name in character_names
            if name.lower() in related_lookup
        ]
        unknown_names = [name for name in character_names if name.lower() not in related_lookup]
        entries.extend(
            {
                "character_name": name,
                "chapter_learned": None,
                "source": "No earlier evidence surfaced yet",
            }
            for name in unknown_names
        )
        warning = None
        if unknown_names:
            unknown_preview = ", ".join(unknown_names[:3])
            if len(unknown_names) > 3:
                unknown_preview = f"{unknown_preview}, and {len(unknown_names) - 3} more"
            warning = f"LoreVia has no clear evidence yet that {unknown_preview} learned this before later story beats could depend on it."
            surfaced_items.append(
                _make_revision_action_item(
                    category="knowledge",
                    title=f"Knowledge dependency around \"{thread.title}\"",
                    description=warning,
                    severity="medium" if (thread.importance or 0) < 8 else "high",
                    chapter_ref=thread.last_mentioned_at or thread.introduced_at,
                    source_label="Character knowledge state",
                    recommendation="Either plant the knowledge transfer earlier or keep later dialogue from assuming it happened off-page.",
                )
            )
        knowledge_facts.append(
            {
                "fact": thread.title,
                "chapter_ref": thread.introduced_at,
                "entries": entries,
                "warning": warning,
            }
        )
    return knowledge_facts, surfaced_items


def _build_revision_plan(
    *,
    change_impacts: list[dict[str, Any]],
    voice_alerts: list[dict[str, Any]],
    scene_advice: list[dict[str, Any]],
    confusion_map: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "title": "Pass 1: Fix story logic",
            "summary": "Resolve the items most likely to create downstream contradictions or broken assumptions.",
            "items": change_impacts[:3],
        },
        {
            "title": "Pass 2: Strengthen character arcs",
            "summary": "Tighten voice, knowledge transfer, and emotional cause-and-effect before polishing prose.",
            "items": voice_alerts[:2],
        },
        {
            "title": "Pass 3: Clarity and pacing cleanup",
            "summary": "Trim duplicate scene work and smooth places where readers are likely to get lost.",
            "items": [*scene_advice[:2], *confusion_map[:2]][:3],
        },
    ]


async def build_revision_intelligence_payload(db: AsyncSession, book: Book) -> dict[str, Any]:
    workspace = build_writer_workspace_payload(book)
    revision_state_map = _revision_board_state_map(workspace)
    recent_edits = _normalize_revision_recent_edits(workspace.get("revision_recent_edits") or [])
    chapters = (
        await db.execute(select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc()))
    ).scalars().all()
    characters = (
        await db.execute(select(Character).where(Character.book_id == book.id).order_by(Character.mention_count.desc(), Character.name))
    ).scalars().all()
    plot_threads = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book.id)
            .order_by(PlotThread.importance.desc(), PlotThread.introduced_at.asc())
        )
    ).scalars().all()
    chapter_summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events, ChapterSummary.clues)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all()
    scenes = (
        await db.execute(select(NovelScene).where(NovelScene.book_id == book.id).order_by(NovelScene.chapter_number.asc(), NovelScene.sort_order.asc()))
    ).scalars().all()
    wiki_entries = (
        await db.execute(select(WikiEntry).where(WikiEntry.book_id == book.id).order_by(WikiEntry.first_mention.asc(), WikiEntry.name.asc()))
    ).scalars().all()
    voice_profiles = (
        await db.execute(select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id))
    ).scalars().all()
    chapter_reports = await list_chapter_consistency_reports(db, book, limit=6)
    chapter_versions = (
        await db.execute(
            select(ChapterVersion)
            .where(ChapterVersion.book_id == book.id)
            .order_by(ChapterVersion.chapter_number.asc(), ChapterVersion.created_at.desc())
        )
    ).scalars().all()

    major_characters = [character for character in characters if (character.mention_count or 0) >= 3][:5] or list(characters[:3])
    character_name_set = {character.name for character in major_characters}
    thread_terms = {thread.title for thread in plot_threads[:6]}
    world_terms = {entry.name for entry in wiki_entries[:8]}
    scenes_by_chapter: dict[int, list[NovelScene]] = {}
    for scene in scenes:
        if scene.chapter_number is None:
            continue
        scenes_by_chapter.setdefault(scene.chapter_number, []).append(scene)

    change_impacts: list[dict[str, Any]] = []
    recent_edit_label = None
    all_chapter_texts = await _load_chapter_texts(list(chapters)) if recent_edits else {}
    for edit in recent_edits[:2]:
        chapter_number = edit.get("chapter_number")
        before_text = str(edit.get("before_text") or "")
        after_text = str(edit.get("after_text") or "")
        unit_label = str(edit.get("unit_label") or story_unit_label(book, chapter_number, fallback="manuscript change"))
        change_summary, focus_terms = _build_revision_change_summary(
            before_text=before_text,
            after_text=after_text,
            unit_label=unit_label,
            character_names=character_name_set,
            thread_terms=thread_terms,
            world_terms=world_terms,
        )
        if recent_edit_label is None:
            recent_edit_label = change_summary
        change_impacts.append(
            _make_revision_action_item(
                category="impact",
                title=unit_label,
                description=change_summary,
                severity="medium",
                chapter_ref=chapter_number,
                source_label="Manuscript change impact analysis",
                recommendation="Scan later chapters that still rely on this setup before you lock the revision.",
            )
        )
        search_terms = focus_terms or sorted(
            _scene_keyword_set(before_text, character_names=character_name_set, thread_terms=thread_terms | world_terms)
        )[:4]
        if not isinstance(chapter_number, int) or chapter_number <= 0 or not search_terms:
            continue
        downstream_hits = 0
        for chapter in chapters:
            if chapter.number <= chapter_number:
                continue
            chapter_text = all_chapter_texts.get(chapter.number, "").lower()
            overlaps = [term for term in search_terms if term.lower() in chapter_text]
            if not overlaps:
                continue
            change_impacts.append(
                _make_revision_action_item(
                    category="impact",
                    title=f"Chapter {chapter.number} still depends on {', '.join(overlaps[:2])}",
                    description=(
                        f"After the change in {unit_label}, LoreVia still finds downstream reliance on {', '.join(overlaps[:2])} in Chapter {chapter.number}."
                    ),
                    severity="high" if downstream_hits == 0 else "medium",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Manuscript change impact analysis",
                    recommendation="Either restore the setup earlier or revise this later chapter so the dependency is re-earned on the page.",
                )
            )
            downstream_hits += 1
            if downstream_hits >= 2:
                break
        if downstream_hits == 0:
            for thread in plot_threads:
                if not isinstance(thread.last_mentioned_at, int) or thread.last_mentioned_at <= chapter_number:
                    continue
                haystack = " ".join(filter(None, [thread.title, thread.description or "", thread.note or ""])).lower()
                overlaps = [term for term in search_terms if term.lower() in haystack]
                if not overlaps:
                    continue
                change_impacts.append(
                    _make_revision_action_item(
                        category="impact",
                        title=f"Downstream thread may need re-foreshadowing: {thread.title}",
                        description=(
                            f"The edit in {unit_label} removed or weakened {', '.join(overlaps[:2])}, but the \"{thread.title}\" thread still pays off later."
                        ),
                        severity="high" if (thread.importance or 0) >= 8 else "medium",
                        chapter_ref=thread.last_mentioned_at,
                        source_label="Plot thread tracker",
                        recommendation="Reintroduce this setup before the payoff lands, or soften the later assumption.",
                    )
                )
                break
    for report in chapter_reports:
        for flag in report.continuity_flags[:2]:
            change_impacts.append(
                _make_revision_action_item(
                    category="impact",
                    title=f"Chapter {report.chapter_number} assumption may break later payoff",
                    description=flag,
                    severity=_severity_from_text(flag),
                    chapter_ref=report.chapter_number,
                    source_label=report.chapter_title or "Continuity scan",
                    recommendation="Trace where the assumption is re-used in later chapters and either restore the setup or revise the downstream reference.",
                )
            )

    for thread in plot_threads[:4]:
        if not thread.introduced_at:
            continue
        last_touch = thread.last_mentioned_at or thread.introduced_at
        if last_touch <= thread.introduced_at:
            continue
        change_impacts.append(
            _make_revision_action_item(
                category="impact",
                title=f"Downstream logic still depends on \"{thread.title}\"",
                description=(
                    f"This thread was introduced in chapter {thread.introduced_at} and is still active by chapter {last_touch}. "
                    f"Revising its setup could ripple into later payoffs. {(thread.description or '').strip()}".strip()
                ),
                severity="high" if (thread.importance or 0) >= 8 else "medium",
                chapter_ref=last_touch,
                source_label="Plot thread tracker",
                recommendation="Check the last payoff scene that references this thread before you finalize any rewrite to its setup.",
            )
        )

    knowledge_matrix, knowledge_items = _build_knowledge_matrix(plot_threads=plot_threads, characters=characters)
    change_impacts.extend(knowledge_items)

    scene_advice: list[dict[str, Any]] = []
    for left, right in zip(scenes, scenes[1:]):
        if left.chapter_number is None or right.chapter_number is None:
            continue
        if right.chapter_number - left.chapter_number > 1:
            continue
        left_text = " ".join(filter(None, [left.title, left.description, left.body]))
        right_text = " ".join(filter(None, [right.title, right.description, right.body]))
        overlap = _scene_keyword_set(left_text, character_names=character_name_set, thread_terms=thread_terms) & _scene_keyword_set(
            right_text,
            character_names=character_name_set,
            thread_terms=thread_terms,
        )
        if len(overlap) >= 2:
            scene_advice.append(
                _make_revision_action_item(
                    category="scene",
                    title=f"Scenes in Chapters {left.chapter_number} and {right.chapter_number} may be doing duplicate work",
                    description=(
                        f"These scenes share the same story pressure around {', '.join(sorted(list(overlap))[:3])}. "
                        "LoreVia sees a possible merge or compression opportunity."
                    ),
                    severity="medium",
                    chapter_ref=right.chapter_number,
                    source_label="Scene cut / merge advisor",
                    recommendation="Keep the strongest emotional beat and fold the duplicate exposition or delay beat into one scene.",
                )
            )
            break

    for scene in scenes[:6]:
        scene_text = " ".join(filter(None, [scene.title, scene.description, scene.body]))
        keyword_hits = len(_scene_keyword_set(scene_text, character_names=character_name_set, thread_terms=thread_terms))
        if _count_words(scene.body or "") < 90 or keyword_hits <= 2:
            scene_advice.append(
                _make_revision_action_item(
                    category="scene",
                    title=f"Scene \"{scene.title}\" may be low-impact right now",
                    description=(
                        "LoreVia could not find a strong tie from this scene into major plot threads, major character arc movement, or later payoff scaffolding."
                    ),
                    severity="low",
                    chapter_ref=scene.chapter_number,
                    source_label="Scene cut / merge advisor",
                    recommendation="Cut it, compress it, or add a stronger consequence that changes what later chapters can assume.",
                )
            )
            break

    confusion_map: list[dict[str, Any]] = []
    chapter_texts = await _load_chapter_texts(list(chapters[:6]))
    for chapter in chapters[:6]:
        chapter_text = chapter_texts.get(chapter.number, "")
        introduced_characters = [character.name for character in characters if character.first_chapter == chapter.number]
        introduced_terms = [entry.name for entry in wiki_entries if entry.first_mention == chapter.number]
        pronoun_count = len(re.findall(r"\b(?:he|she|they|them|his|her|their)\b", chapter_text.lower()))
        scene_break_count = len(SCENE_BREAK_LINE_RE.findall(chapter_text))
        transition_hits = sum(1 for marker in REVISION_TRANSITION_MARKERS if marker in chapter_text.lower())
        motivation_hits = sum(1 for marker in REVISION_MOTIVATION_MARKERS if re.search(rf"\b{re.escape(marker)}\b", chapter_text.lower()))
        density_score = (len(introduced_characters) * 2) + (len(introduced_terms) * 2) + (1 if pronoun_count >= 12 else 0)
        signals: list[str] = []
        if introduced_characters:
            signals.append(f"{len(introduced_characters)} named characters arrive here")
        if introduced_terms:
            signals.append(f"{len(introduced_terms)} lore terms appear here")
        if pronoun_count >= 12:
            signals.append("pronoun density is high relative to stable anchors")
        if density_score >= 5:
            confusion_map.append(
                _make_revision_action_item(
                    category="confusion",
                    title=f"Reader confusion risk in Chapter {chapter.number}",
                    description="; ".join(signals).strip().capitalize() + ".",
                    severity="high" if density_score >= 8 else "medium",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Reader confusion map",
                    recommendation="Delay some names or terms until the immediate scene goal is clear, or restate the anchor the reader should hold onto first.",
                )
            )
        chapter_scenes = scenes_by_chapter.get(chapter.number, [])
        pov_values = {
            " ".join(str((scene.scene_metadata or {}).get("pov") or "").split()).strip()
            for scene in chapter_scenes
            if isinstance(scene.scene_metadata, dict)
        }
        pov_values.discard("")
        if len(pov_values) >= 2:
            confusion_map.append(
                _make_revision_action_item(
                    category="confusion",
                    title=f"POV anchoring may blur in Chapter {chapter.number}",
                    description=f"LoreVia found multiple scene POV anchors here: {', '.join(sorted(pov_values)[:3])}. Readers may need a stronger reset between them.",
                    severity="medium",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Reader confusion map",
                    recommendation="Add a cleaner POV handoff signal or restate the immediate scene objective when the perspective changes.",
                )
            )
        if scene_break_count > 0 and transition_hits == 0:
            confusion_map.append(
                _make_revision_action_item(
                    category="confusion",
                    title=f"Scene transition may feel abrupt in Chapter {chapter.number}",
                    description="Scene breaks appear without much transition language, so the reader may feel dropped into the next beat without enough context.",
                    severity="medium",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Reader confusion map",
                    recommendation="Add a short bridge line that re-anchors time, place, or who now holds the scene goal.",
                )
            )
        if _count_words(chapter_text) >= 140 and motivation_hits == 0:
            confusion_map.append(
                _make_revision_action_item(
                    category="confusion",
                    title=f"Motivation gap may weaken Chapter {chapter.number}",
                    description="LoreVia sees scene movement here, but not a strong on-page reminder of what the point-of-view character is trying to accomplish.",
                    severity="low",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Reader confusion map",
                    recommendation="Restate the immediate want, fear, or decision after the turn so the reader keeps hold of the chapter's causal spine.",
                )
            )

    voice_alerts: list[dict[str, Any]] = []
    character_rows = [{"id": str(character.id), "name": character.name, "aliases": character.aliases or []} for character in characters]
    profiles_by_character_id = {str(profile.character_id): profile for profile in voice_profiles}
    sampled_voice_chapters = chapters[-3:] if len(chapters) >= 3 else chapters
    missing_voice_chapters = [chapter for chapter in sampled_voice_chapters if chapter.number not in chapter_texts]
    if missing_voice_chapters:
        chapter_texts.update(await _load_chapter_texts(missing_voice_chapters))
    narration_signatures = [(chapter.number, _build_narration_signature(chapter_texts.get(chapter.number, ""))) for chapter in sampled_voice_chapters]
    for index, chapter in enumerate(sampled_voice_chapters):
        chapter_text = chapter_texts.get(chapter.number)
        if chapter_text is None:
            chapter_text = (await _load_chapter_texts([chapter])).get(chapter.number, "")
        attributed_dialogue = extract_dialogue_samples_by_character(chapter_text, character_rows)
        for character in major_characters[:3]:
            profile = profiles_by_character_id.get(str(character.id))
            if profile is None:
                continue
            samples = attributed_dialogue.get(character.name, [])
            sample_metrics = compute_voice_metrics(samples)
            if int(sample_metrics.get("sample_dialogue_count") or 0) <= 0:
                continue
            profile_payload = {
                "sample_dialogue_count": profile.sample_dialogue_count,
                "avg_sentence_length": profile.avg_sentence_length or 0,
                "formality_score_x1000": profile.formality_score_x1000 or 0,
                "contraction_rate_x1000": profile.contraction_rate_x1000 or 0,
                "question_rate_x1000": profile.question_rate_x1000 or 0,
                "exclamation_rate_x1000": profile.exclamation_rate_x1000 or 0,
                "ellipsis_rate_x1000": profile.ellipsis_rate_x1000 or 0,
                "dash_rate_x1000": profile.dash_rate_x1000 or 0,
                "lexical_complexity_x1000": profile.lexical_complexity_x1000 or 0,
                "emotional_intensity_x1000": profile.emotional_intensity_x1000 or 0,
            }
            match_score, signals = score_voice_match(profile_payload, sample_metrics)
            if match_score >= 70:
                continue
            drift_label = "voice drifts"
            if any("vocabulary complexity" in signal or "formality" in signal for signal in signals):
                drift_label = "vocabulary drifts"
            voice_alerts.append(
                _make_revision_action_item(
                    category="voice",
                    title=f"{character.name}'s {drift_label} in Chapter {chapter.number}",
                    description=(
                        f"Match score dropped to {match_score}/100. "
                        + ("; ".join(signals[:2]) if signals else "Dialogue cadence feels off against the established baseline.")
                    ),
                    severity="high" if match_score < 55 else "medium",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Voice consistency checker",
                    recommendation="Let the scene carry less exposition through this character, or rewrite the dialogue back toward their established rhythm and vocabulary.",
                )
            )
            break
        if index > 0:
            previous_number, previous_signature = narration_signatures[index - 1]
            current_signature = narration_signatures[index][1]
            narration_shift = _describe_narration_shift(previous_signature, current_signature)
            if narration_shift:
                voice_alerts.append(
                    _make_revision_action_item(
                        category="voice",
                        title=f"POV narration inconsistency in Chapter {chapter.number}",
                        description=f"{narration_shift} The surrounding comparison chapter is Chapter {previous_number}.",
                        severity="medium",
                        chapter_ref=chapter.number,
                        source_label=chapter.title or "Voice consistency checker",
                        recommendation="Re-anchor the narration to the established distance, pronoun mode, and interiority style for this point of view.",
                    )
                )
                break
        normalized_genre = " ".join((book.genre or "").split()).strip().lower()
        if any(marker in chapter_text.lower() for marker in MODERN_VOICE_MARKERS) and ("historical" in normalized_genre or "fantasy" in normalized_genre):
            voice_alerts.append(
                _make_revision_action_item(
                    category="voice",
                    title=f"Setting voice drift in Chapter {chapter.number}",
                    description="Modern conversational markers appear in a setting that reads as historical or secondary-world fantasy.",
                    severity="medium",
                    chapter_ref=chapter.number,
                    source_label=chapter.title or "Voice consistency checker",
                    recommendation="Swap the modern phrasing for diction that matches the manuscript's established setting voice.",
                )
            )
            break
    versions_by_chapter: dict[int, list[ChapterVersion]] = {}
    for version in chapter_versions:
        versions_by_chapter.setdefault(version.chapter_number, []).append(version)
    for chapter_number, versions in versions_by_chapter.items():
        if len(versions) < 2:
            continue
        latest_text = await _load_version_text(versions[0])
        previous_text = await _load_version_text(versions[1])
        if not latest_text or not previous_text:
            continue
        tone_shift = _describe_narration_shift(_build_narration_signature(previous_text), _build_narration_signature(latest_text))
        if tone_shift:
            voice_alerts.append(
                _make_revision_action_item(
                    category="voice",
                    title=f"Draft tone shifted between versions of Chapter {chapter_number}",
                    description=tone_shift,
                    severity="medium",
                    chapter_ref=chapter_number,
                    source_label="Voice consistency checker",
                    recommendation="Compare the latest snapshot against the prior saved version and decide whether the tonal shift was intentional.",
                )
            )
            break

    change_impacts = change_impacts[:6]
    scene_advice = scene_advice[:3]
    confusion_map = confusion_map[:3]
    voice_alerts = voice_alerts[:3]

    revision_plan = _build_revision_plan(
        change_impacts=change_impacts,
        voice_alerts=voice_alerts,
        scene_advice=scene_advice,
        confusion_map=confusion_map,
    )

    surfaced_lists = [change_impacts, scene_advice, confusion_map, voice_alerts]
    for collection in surfaced_lists:
        for index, item in enumerate(collection):
            collection[index] = _overlay_revision_state(item, revision_state_map)
    for revision_pass in revision_plan:
        revision_pass["items"] = [_overlay_revision_state(item, revision_state_map) for item in revision_pass["items"]]

    all_items_by_id: dict[str, dict[str, Any]] = {}
    for collection in [*surfaced_lists, *[revision_pass["items"] for revision_pass in revision_plan]]:
        for item in collection:
            all_items_by_id[str(item["id"])] = item

    active_items = [item for item in all_items_by_id.values() if item.get("status") not in {"fixed", "ignored"}]
    high_items = [item for item in active_items if item.get("severity") == "high"]
    task_ready_items = [item for item in active_items if item.get("status") != "task_created"]
    hero_message = (
        f"{len(high_items)} downstream logic risk{'s' if len(high_items) != 1 else ''} need attention first."
        if high_items
        else f"{len(active_items)} revision item{'s' if len(active_items) != 1 else ''} are worth a structured pass."
    )

    if not knowledge_matrix and chapter_summary_rows:
        fallback_character_names = [character.name for character in characters if str(character.name or "").strip()]
        for chapter_number, _, key_events, clues in chapter_summary_rows:
            facts = [*_flatten_summary_points(clues), *_flatten_summary_points(key_events)]
            if not facts:
                continue
            knowledge_matrix.append(
                {
                    "fact": facts[0],
                    "chapter_ref": chapter_number,
                    "entries": [
                        {
                            "character_name": name,
                            "chapter_learned": chapter_number if index == 0 else None,
                            "source": "Chapter summary evidence" if index == 0 else "No earlier evidence surfaced yet",
                        }
                        for index, name in enumerate(fallback_character_names)
                    ],
                    "warning": None,
                }
            )
    chapter_columns = [chapter.number for chapter in chapters]
    knowledge_timeline = _build_knowledge_timeline(knowledge_matrix=knowledge_matrix, chapter_numbers=chapter_columns)

    return {
        "tagline": "Know what your edit breaks before your readers do.",
        "summary": {
            "hero_message": hero_message,
            "active_item_count": len(active_items),
            "high_severity_count": len(high_items),
            "task_ready_count": len(task_ready_items),
            "recent_edit_label": recent_edit_label,
        },
        "change_impacts": change_impacts,
        "genre_checks": _select_genre_checks(book.genre, active_items),
        "revision_plan": revision_plan,
        "knowledge_matrix": knowledge_matrix[:3],
        "knowledge_timeline": knowledge_timeline,
        "scene_advice": scene_advice,
        "confusion_map": confusion_map,
        "voice_alerts": voice_alerts,
    }


def estimate_readability(text: str) -> dict[str, Any]:
    cleaned = " ".join((text or "").replace("\r", "\n").split())
    paragraphs = len([part for part in re.split(r"\n{2,}", text or "") if part.strip()]) or (1 if cleaned else 0)
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    sentences = [part for part in re.split(r"[.!?]+", text or "") if part.strip()]
    word_count = len(words)
    sentence_count = len(sentences) or (1 if word_count else 0)
    syllables = sum(_estimate_syllables(word) for word in words)
    average_sentence_length = round(word_count / sentence_count, 2) if sentence_count else 0.0
    reading_ease = 206.835 - (1.015 * average_sentence_length) - (84.6 * ((syllables / word_count) if word_count else 0))
    grade_level = 0.39 * average_sentence_length + 11.8 * ((syllables / word_count) if word_count else 0) - 15.59

    if reading_ease >= 80:
        label = "Very easy"
    elif reading_ease >= 65:
        label = "Easy"
    elif reading_ease >= 50:
        label = "Balanced"
    elif reading_ease >= 35:
        label = "Demanding"
    else:
        label = "Dense"

    return {
        "words": word_count,
        "sentences": sentence_count,
        "paragraphs": paragraphs,
        "average_sentence_length": round(average_sentence_length, 2),
        "reading_ease": round(reading_ease, 2),
        "grade_level": round(max(0.0, grade_level), 2),
        "label": label,
    }


def _clamp_score(value: float, *, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _story_health_status(score: int) -> tuple[str, str]:
    if score >= 85:
        return "Excellent", "Story signals look strong across character, world, plot, and pacing."
    if score >= 70:
        return "Good", "Overall story health looks solid, with a few areas worth refining."
    if score >= 55:
        return "Fair", "The draft has momentum, but a couple of craft systems need attention."
    return "Needs Attention", "Several story systems are under strain, so this is a good moment for a focused revision pass."


async def build_story_health_payload(db: AsyncSession, book: Book) -> StoryHealthOut:
    from app.utils.character_utils import is_displayable_character

    characters = (
        await db.execute(select(Character).where(Character.book_id == book.id).order_by(Character.mention_count.desc(), Character.name))
    ).scalars().all()
    visible_characters = [character for character in characters if is_displayable_character(character)]

    relationships = (
        await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id == book.id))
    ).scalars().all()
    relationship_counts: dict[uuid.UUID, int] = {}
    for relationship in relationships:
        relationship_counts[relationship.character_a_id] = relationship_counts.get(relationship.character_a_id, 0) + 1
        relationship_counts[relationship.character_b_id] = relationship_counts.get(relationship.character_b_id, 0) + 1

    major_characters = [
        character
        for character in visible_characters
        if (character.mention_count or 0) >= 6 or character.role in {"mc", "sc"}
    ]
    if not major_characters:
        major_characters = visible_characters[: max(1, min(3, len(visible_characters)))]

    character_scores: list[float] = []
    for character in visible_characters:
        evidence_points = 0
        if character.role:
            evidence_points += 1
        if character.arc_summary:
            evidence_points += 1
        if character.personality_tags or character.archetype or character.trait_state:
            evidence_points += 1
        if character.motivations or character.fears:
            evidence_points += 1
        if character.growth_events:
            evidence_points += 1
        if relationship_counts.get(character.id, 0) > 0:
            evidence_points += 1
        character_scores.append((evidence_points / 6) * 100)

    state_rows = (
        await db.execute(
            select(CharacterState.character_id, func.count(CharacterState.id))
            .join(Character, Character.id == CharacterState.character_id)
            .where(Character.book_id == book.id)
            .group_by(CharacterState.character_id)
        )
    ).all()
    state_counts = {character_id: int(count or 0) for character_id, count in state_rows}
    major_with_states = sum(1 for character in major_characters if state_counts.get(character.id, 0) > 0)
    state_coverage = (major_with_states / len(major_characters)) if major_characters else 0.0

    character_score = _clamp_score(
        (statistics.fmean(character_scores) if character_scores else 0) * 0.78 + (state_coverage * 22),
        minimum=0,
        maximum=100,
    )
    character_detail = (
        f"{len(visible_characters)} visible profiles scored from role, arc, trait, motive, growth, and relationship coverage; "
        f"{major_with_states}/{len(major_characters) or 1} major characters have tracked state snapshots."
    )

    chapter_reports = await list_chapter_consistency_reports(db, book, limit=6)
    continuity_issue_count = sum(len(report.continuity_flags) for report in chapter_reports)
    continuity_score = _clamp_score(
        95
        - (continuity_issue_count * 10)
        - (max(0, len(major_characters) - major_with_states) * 4)
        + min(len(chapter_reports) * 2, 6),
        minimum=0,
        maximum=96,
    )
    continuity_detail = (
        f"{continuity_issue_count} recent continuity flags across {len(chapter_reports)} reports; "
        f"{major_with_states}/{len(major_characters) or 1} major characters are backed by state history. "
        "Even when no acute break is logged, keep pressure-testing chapter-to-chapter state drift and role labeling."
    )

    plot_threads = (
        await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))
    ).scalars().all()
    resolved_threads = sum(1 for thread in plot_threads if derive_plot_thread_status(
        thread.status,
        introduced_at=thread.introduced_at,
        last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
        resolved_at=thread.resolved_at,
        current_chapter=book.total_chapters,
    ) == "resolved")
    abandoned_threads = sum(1 for thread in plot_threads if derive_plot_thread_status(
        thread.status,
        introduced_at=thread.introduced_at,
        last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
        resolved_at=thread.resolved_at,
        current_chapter=book.total_chapters,
    ) == "abandoned")
    open_threads = sum(1 for thread in plot_threads if is_plot_thread_open(derive_plot_thread_status(
        thread.status,
        introduced_at=thread.introduced_at,
        last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
        resolved_at=thread.resolved_at,
        current_chapter=book.total_chapters,
    )))
    total_threads = len(plot_threads)
    anchored_threads = sum(1 for thread in plot_threads if thread.introduced_at is not None)
    chronology_conflicts = sum(
        1 for thread in plot_threads if thread.introduced_at is not None and thread.resolved_at is not None and thread.resolved_at < thread.introduced_at
    )
    stale_open_threads = sum(
        1
        for thread in plot_threads
        if is_plot_thread_open(derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=book.total_chapters,
        ))
        and (thread.last_mentioned_at or thread.introduced_at) is not None
        and (book.total_chapters or 0) - int(thread.last_mentioned_at or thread.introduced_at or 0) >= 8
    )
    timeline_score = _clamp_score(
        58
        + (((anchored_threads / total_threads) if total_threads else 1.0) * 22)
        + ((((book.total_chapters or 0) - min(continuity_issue_count, book.total_chapters or 0)) / (book.total_chapters or 1)) * 20 if (book.total_chapters or 0) > 0 else 10)
        - (continuity_issue_count * 4)
        - (chronology_conflicts * 12),
        minimum=0,
        maximum=96,
    )
    timeline_detail = (
        f"{anchored_threads}/{total_threads or 1} plot threads have chapter anchors, with {chronology_conflicts} chronology conflicts "
        f"and {continuity_issue_count} recent continuity flags. "
        "Timeline clarity should still be stress-tested for implied travel time, off-page gaps, and stale open beats."
    )

    plot_score = _clamp_score(
        52
        + (((resolved_threads / total_threads) if total_threads else 1.0) * 30)
        + min(total_threads * 2, 12)
        - (stale_open_threads * 7)
        - (abandoned_threads * 5)
        - max(0, open_threads - resolved_threads) * 2,
        minimum=0,
        maximum=96,
    )
    plot_detail = (
        f"{resolved_threads}/{total_threads or 1} plot threads resolved, {open_threads} still open, "
        f"and {stale_open_threads} have been hanging open for 8+ chapters."
    )

    wiki_count = (
        await db.scalar(select(func.count(WikiEntry.id)).where(WikiEntry.book_id == book.id))
    ) or 0
    world_document_count = (
        await db.scalar(
            select(func.count(WorldBuildingDocument.id)).where(
                WorldBuildingDocument.book_id == book.id,
                WorldBuildingDocument.is_active.is_(True),
                WorldBuildingDocument.archived_at.is_(None),
            )
        )
    ) or 0
    latest_world_gap_analysis = (
        await db.execute(
            select(WorldGapAnalysis)
            .where(WorldGapAnalysis.book_id == book.id)
            .order_by(WorldGapAnalysis.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    priority_gaps = len(latest_world_gap_analysis.priority_gaps or []) if latest_world_gap_analysis else 0
    consistency_flags = len(latest_world_gap_analysis.consistency_flags or []) if latest_world_gap_analysis else 0
    world_score = _clamp_score(
        58 + min(world_document_count * 8, 24) + min(wiki_count * 2, 18) - (priority_gaps * 7) - (consistency_flags * 6),
        minimum=0,
        maximum=96,
    )
    world_issue_count = priority_gaps + consistency_flags
    world_detail = (
        f"{world_document_count} active world documents and {wiki_count} wiki entries. "
        + (
            f"{world_issue_count} cached world-analysis issue{'s' if world_issue_count != 1 else ''} are already on the board. "
            if world_issue_count
            else "The world-analysis review queue still needs a fresh pass so LoreVia can surface more contradiction and coverage targets. "
        )
        + "Lore coverage still benefits from ongoing contradiction hunts and missing-rule checks."
    )

    voice_profiles = (
        await db.execute(select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id))
    ).scalars().all()
    voice_profiles_by_character = {profile.character_id: profile for profile in voice_profiles}
    major_with_voice = sum(
        1
        for character in major_characters
        if (voice_profiles_by_character.get(character.id).sample_dialogue_count if voice_profiles_by_character.get(character.id) else 0) >= 3
    )
    voice_marker_profiles = sum(
        1
        for profile in voice_profiles
        if (profile.signature_phrases and len(profile.signature_phrases) > 0)
        or (profile.dominant_markers and len(profile.dominant_markers) > 0)
    )
    dialogue_score = _clamp_score(
        44
        + (((major_with_voice / len(major_characters)) if major_characters else 0.0) * 36)
        + (((voice_marker_profiles / len(voice_profiles)) if voice_profiles else 0.0) * 20)
        + min(sum(profile.sample_dialogue_count for profile in voice_profiles), 20),
        minimum=0,
        maximum=96,
    )
    dialogue_detail = (
        f"{major_with_voice}/{len(major_characters) or 1} major characters have reusable voice samples; "
        f"{voice_marker_profiles}/{len(voice_profiles) or 1} voice profiles include markers or signature phrases. "
        "Voice review should still keep looking for flattening, over-shared phrasing, and missing contrast."
    )

    chapter_word_counts = [
        int(word_count)
        for word_count in (
            await db.execute(
                select(Chapter.word_count)
                .where(Chapter.book_id == book.id, Chapter.word_count.is_not(None), Chapter.word_count > 0)
                .order_by(Chapter.number.asc())
            )
        ).scalars().all()
    ]
    if len(chapter_word_counts) >= 2:
        mean_word_count = statistics.fmean(chapter_word_counts)
        stdev_word_count = statistics.pstdev(chapter_word_counts) if len(chapter_word_counts) > 1 else 0.0
        coefficient_of_variation = (stdev_word_count / mean_word_count) if mean_word_count else 1.0
        median_word_count = statistics.median(chapter_word_counts)
        outlier_count = sum(
            1
            for word_count in chapter_word_counts
            if word_count < median_word_count * 0.6 or word_count > median_word_count * 1.6
        )
        outlier_rate = outlier_count / len(chapter_word_counts)
        pacing_score = _clamp_score(
            100 - (coefficient_of_variation * 85) - (outlier_rate * 35),
            minimum=0,
            maximum=96,
        )
        pacing_detail = f"{len(chapter_word_counts)} chapter word counts measured; {outlier_count} pacing outliers against a {int(round(median_word_count))}-word median."
    elif len(chapter_word_counts) == 1:
        pacing_score = 65
        pacing_detail = "Only one chapter has a persisted word count, so pacing is based on limited manuscript data."
    else:
        pacing_score = 0
        pacing_detail = "No persisted chapter word counts are available yet for pacing analysis."

    overall_score = _clamp_score(
        statistics.fmean([continuity_score, character_score, timeline_score, plot_score, world_score, pacing_score, dialogue_score]),
        minimum=0,
        maximum=94,
    )
    status, summary = _story_health_status(overall_score)
    return StoryHealthOut(
        score=overall_score,
        status=status,
        summary=summary,
        metrics=[
            {"label": "Continuity", "score": continuity_score, "detail": continuity_detail},
            {"label": "Character consistency", "score": character_score, "detail": character_detail},
            {"label": "Timeline clarity", "score": timeline_score, "detail": timeline_detail},
            {"label": "Plot thread closure", "score": plot_score, "detail": plot_detail},
            {"label": "Worldbuilding consistency", "score": world_score, "detail": world_detail},
            {"label": "Pacing", "score": pacing_score, "detail": pacing_detail},
            {"label": "Dialogue/voice consistency", "score": dialogue_score, "detail": dialogue_detail},
        ],
    )


def _estimate_syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 1
    groups = re.findall(r"[aeiouy]+", cleaned)
    syllables = len(groups)
    if cleaned.endswith("e") and syllables > 1:
        syllables -= 1
    return max(1, syllables)


# ─── Ownership guards ─────────────────────────────────────────────────────────

COLLABORATION_ROLES = {
    "viewer",
    "commenter",
    "editor",
    "beta_reader",
    "developmental_editor",
    "coauthor",
    "reader_only",
    "co_writer",
}
COLLABORATION_DEFAULT_SCOPE = {
    "chapter_start": None,
    "chapter_end": None,
    "character_bible": False,
    "continuity_report": False,
    "reader_confusion_report": False,
}
COLLABORATION_DEFAULT_PERMISSIONS = {
    "can_edit_manuscript": False,
    "can_view_story_bible": False,
    "can_run_ai_scans": False,
    "can_export": False,
    "can_comment": False,
    "can_view_selected_chapters_only": True,
}
COLLABORATION_ROLE_DEFAULT_PERMISSIONS = {
    "viewer": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_view_selected_chapters_only": True,
    },
    "reader_only": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_view_selected_chapters_only": True,
    },
    "commenter": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_comment": True,
        "can_view_selected_chapters_only": True,
    },
    "beta_reader": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_comment": True,
        "can_view_selected_chapters_only": True,
    },
    "editor": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
    "developmental_editor": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
    "coauthor": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
    "co_writer": {
        **COLLABORATION_DEFAULT_PERMISSIONS,
        "can_edit_manuscript": True,
        "can_view_story_bible": True,
        "can_run_ai_scans": True,
        "can_export": True,
        "can_comment": True,
        "can_view_selected_chapters_only": False,
    },
}
COLLABORATION_READER_SHELL_ROLES = {"viewer", "reader_only", "commenter", "beta_reader"}
COLLABORATION_AUTHOR_SHELL_ROLES = {"editor", "developmental_editor", "coauthor", "co_writer"}
READER_VISIBLE_FEATURES = (
    "overview",
    "read",
    "chapters",
    "recaps",
    "search",
    "timeline",
    "feedback",
)


@dataclass(slots=True)
class BookAccessContext:
    access_class: str
    workspace_shell: str
    can_switch_workspace_mode: bool
    can_edit_manuscript: bool
    can_comment: bool
    can_export: bool
    can_view_story_bible: bool
    can_run_ai_scans: bool
    visible_reader_features: tuple[str, ...]
    collaboration_role: str | None
    collaboration_scope: dict | None
    collaboration_permissions: dict | None


def normalize_collaboration_email(email: str) -> str:
    cleaned = str(email or "").strip().lower()
    if not cleaned or "@" not in cleaned or len(cleaned) > 320:
        raise HTTPException(400, "Valid collaborator email is required")
    return cleaned


def normalize_collaboration_role(role: str) -> str:
    cleaned = str(role or "").strip().lower()
    if cleaned not in COLLABORATION_ROLES:
        raise HTTPException(400, "Invalid collaborator role")
    return cleaned


def collaboration_role_workspace_shell(role: str) -> str:
    normalized_role = normalize_collaboration_role(role)
    if normalized_role in COLLABORATION_READER_SHELL_ROLES:
        return "reader"
    return "author"


def build_book_access_context(
    book: Book,
    *,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    if collaborator is None:
        workspace_shell = "author" if (book.mode or "reader") == "author" else "reader"
        return BookAccessContext(
            access_class="owner",
            workspace_shell=workspace_shell,
            can_switch_workspace_mode=True,
            can_edit_manuscript=True,
            can_comment=True,
            can_export=True,
            can_view_story_bible=True,
            can_run_ai_scans=True,
            visible_reader_features=READER_VISIBLE_FEATURES,
            collaboration_role=None,
            collaboration_scope=None,
            collaboration_permissions=None,
        )

    scope = collaboration_scope_payload(collaborator)
    permissions = collaboration_permissions_payload(collaborator, role=collaborator.role, scope=scope)
    workspace_shell = collaboration_role_workspace_shell(collaborator.role)
    return BookAccessContext(
        access_class="reader_collaborator" if workspace_shell == "reader" else "author_collaborator",
        workspace_shell=workspace_shell,
        can_switch_workspace_mode=False,
        can_edit_manuscript=permissions["can_edit_manuscript"],
        can_comment=permissions["can_comment"],
        can_export=permissions["can_export"],
        can_view_story_bible=permissions["can_view_story_bible"],
        can_run_ai_scans=permissions["can_run_ai_scans"],
        visible_reader_features=READER_VISIBLE_FEATURES,
        collaboration_role=collaborator.role,
        collaboration_scope=scope,
        collaboration_permissions=permissions,
    )


def _collaboration_permissions_for_role(collaborator: BookCollaborator) -> dict:
    scope = collaboration_scope_payload(collaborator)
    return collaboration_permissions_payload(collaborator, role=collaborator.role, scope=scope)


def collaboration_scope_payload(raw_scope: Any) -> dict:
    source = raw_scope
    if hasattr(raw_scope, "scope") and not isinstance(raw_scope, (dict, CollaborationScope)):
        source = getattr(raw_scope, "scope")
    scope = normalize_collaboration_scope(source)
    if hasattr(raw_scope, "scope_chapter_start"):
        scope["chapter_start"] = getattr(raw_scope, "scope_chapter_start")
    if hasattr(raw_scope, "scope_chapter_end"):
        scope["chapter_end"] = getattr(raw_scope, "scope_chapter_end")
    if hasattr(raw_scope, "scope_character_bible"):
        scope["character_bible"] = bool(getattr(raw_scope, "scope_character_bible"))
    if hasattr(raw_scope, "scope_continuity_report"):
        scope["continuity_report"] = bool(getattr(raw_scope, "scope_continuity_report"))
    if hasattr(raw_scope, "scope_reader_confusion_report"):
        scope["reader_confusion_report"] = bool(getattr(raw_scope, "scope_reader_confusion_report"))
    return normalize_collaboration_scope(scope)


def normalize_collaboration_scope(raw_scope: dict | CollaborationScope | None) -> dict:
    source = raw_scope.model_dump() if isinstance(raw_scope, CollaborationScope) else dict(raw_scope or {})
    scope = dict(COLLABORATION_DEFAULT_SCOPE)
    scope.update({key: source.get(key) for key in scope if key in source})

    chapter_start = scope.get("chapter_start")
    chapter_end = scope.get("chapter_end")
    if chapter_start is not None:
        chapter_start = int(chapter_start)
        if chapter_start < 1:
            raise HTTPException(400, "chapter_start must be at least 1")
    if chapter_end is not None:
        chapter_end = int(chapter_end)
        if chapter_end < 1:
            raise HTTPException(400, "chapter_end must be at least 1")
    if chapter_start is not None and chapter_end is not None and chapter_end < chapter_start:
        raise HTTPException(400, "chapter_end cannot be earlier than chapter_start")

    scope["chapter_start"] = chapter_start
    scope["chapter_end"] = chapter_end
    scope["character_bible"] = bool(scope.get("character_bible"))
    scope["continuity_report"] = bool(scope.get("continuity_report"))
    scope["reader_confusion_report"] = bool(scope.get("reader_confusion_report"))
    return scope


def collaboration_scope_model(scope: dict | None) -> CollaborationScope:
    return CollaborationScope(**collaboration_scope_payload(scope))


def normalize_collaboration_permissions(
    raw_permissions: dict | CollaborationPermissions | None,
    *,
    role: str,
    scope: dict | CollaborationScope | None = None,
) -> dict:
    normalized_role = normalize_collaboration_role(role)
    source = raw_permissions.model_dump() if isinstance(raw_permissions, CollaborationPermissions) else dict(raw_permissions or {})
    permissions = dict(COLLABORATION_ROLE_DEFAULT_PERMISSIONS[normalized_role])
    permissions.update({key: source.get(key) for key in permissions if key in source})
    normalized_scope = normalize_collaboration_scope(scope)
    if "can_view_selected_chapters_only" not in source and (
        normalized_scope.get("chapter_start") is not None or normalized_scope.get("chapter_end") is not None
    ):
        permissions["can_view_selected_chapters_only"] = True
    for key in permissions:
        permissions[key] = bool(permissions.get(key))
    return permissions


def collaboration_permissions_payload(
    raw_permissions: Any,
    *,
    role: str,
    scope: Any = None,
) -> dict:
    source = raw_permissions
    if hasattr(raw_permissions, "permissions") and not isinstance(raw_permissions, (dict, CollaborationPermissions)):
        source = getattr(raw_permissions, "permissions")
    normalized_scope = collaboration_scope_payload(scope)
    permissions = normalize_collaboration_permissions(source, role=role, scope=normalized_scope)
    if hasattr(raw_permissions, "permission_can_edit_manuscript"):
        permissions["can_edit_manuscript"] = bool(getattr(raw_permissions, "permission_can_edit_manuscript"))
    if hasattr(raw_permissions, "permission_can_view_story_bible"):
        permissions["can_view_story_bible"] = bool(getattr(raw_permissions, "permission_can_view_story_bible"))
    if hasattr(raw_permissions, "permission_can_run_ai_scans"):
        permissions["can_run_ai_scans"] = bool(getattr(raw_permissions, "permission_can_run_ai_scans"))
    if hasattr(raw_permissions, "permission_can_export"):
        permissions["can_export"] = bool(getattr(raw_permissions, "permission_can_export"))
    if hasattr(raw_permissions, "permission_can_comment"):
        permissions["can_comment"] = bool(getattr(raw_permissions, "permission_can_comment"))
    if hasattr(raw_permissions, "permission_can_view_selected_chapters_only"):
        permissions["can_view_selected_chapters_only"] = bool(getattr(raw_permissions, "permission_can_view_selected_chapters_only"))
    return normalize_collaboration_permissions(permissions, role=role, scope=normalized_scope)


def collaboration_permissions_model(
    permissions: dict | None,
    *,
    role: str,
    scope: dict | None,
) -> CollaborationPermissions:
    return CollaborationPermissions(
        **collaboration_permissions_payload(permissions, role=role, scope=scope)
    )


def apply_collaboration_scope(collaborator: BookCollaborator, scope: dict) -> None:
    normalized_scope = normalize_collaboration_scope(scope)
    collaborator.scope = normalized_scope
    collaborator.scope_chapter_start = normalized_scope["chapter_start"]
    collaborator.scope_chapter_end = normalized_scope["chapter_end"]
    collaborator.scope_character_bible = normalized_scope["character_bible"]
    collaborator.scope_continuity_report = normalized_scope["continuity_report"]
    collaborator.scope_reader_confusion_report = normalized_scope["reader_confusion_report"]


def apply_collaboration_permissions(
    collaborator: BookCollaborator,
    permissions: dict,
    *,
    role: str,
    scope: dict,
) -> None:
    normalized_permissions = normalize_collaboration_permissions(permissions, role=role, scope=scope)
    collaborator.permissions = normalized_permissions
    collaborator.permission_can_edit_manuscript = normalized_permissions["can_edit_manuscript"]
    collaborator.permission_can_view_story_bible = normalized_permissions["can_view_story_bible"]
    collaborator.permission_can_run_ai_scans = normalized_permissions["can_run_ai_scans"]
    collaborator.permission_can_export = normalized_permissions["can_export"]
    collaborator.permission_can_comment = normalized_permissions["can_comment"]
    collaborator.permission_can_view_selected_chapters_only = normalized_permissions["can_view_selected_chapters_only"]


def serialize_book_collaborator(collaborator: BookCollaborator) -> BookCollaboratorOut:
    scope = collaboration_scope_payload(collaborator)
    return BookCollaboratorOut(
        id=str(collaborator.id),
        book_id=str(collaborator.book_id),
        email=collaborator.email,
        display_name=collaborator.display_name,
        role=collaborator.role,
        scope=collaboration_scope_model(scope),
        permissions=collaboration_permissions_model(
            collaborator,
            role=collaborator.role,
            scope=scope,
        ),
        invite_status=collaborator.invite_status,
        invited_at=collaborator.invited_at,
        updated_at=collaborator.updated_at,
    )


def collaboration_allows_chapter(collaborator: BookCollaborator | None, chapter_number: int) -> bool:
    if collaborator is None:
        return True
    scope = collaboration_scope_payload(collaborator)
    permissions = collaboration_permissions_payload(collaborator, role=collaborator.role, scope=scope)
    if not permissions["can_view_selected_chapters_only"]:
        return True
    chapter_start = scope.get("chapter_start")
    chapter_end = scope.get("chapter_end")
    if chapter_start is not None and chapter_number < chapter_start:
        return False
    if chapter_end is not None and chapter_number > chapter_end:
        return False
    return True


def collaboration_can_comment(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_comment"]


def collaboration_can_edit(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_edit_manuscript"]


def collaboration_can_export(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_export"]


def collaboration_can_copy_manuscript(book: Book, collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    if bool(book.is_public):
        return True
    return collaboration_can_edit(collaborator)


def collaboration_can_view_story_bible(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_view_story_bible"]


def collaboration_can_run_ai_scans(collaborator: BookCollaborator | None) -> bool:
    if collaborator is None:
        return True
    return _collaboration_permissions_for_role(collaborator)["can_run_ai_scans"]


def collaboration_has_resource(collaborator: BookCollaborator | None, resource: str) -> bool:
    if collaborator is None:
        return True
    scope = collaboration_scope_payload(collaborator)
    if not bool(scope.get(resource)):
        return False
    if resource == "character_bible":
        return collaboration_can_view_story_bible(collaborator)
    if resource in {"continuity_report", "reader_confusion_report"}:
        return collaboration_can_run_ai_scans(collaborator)
    return True


async def find_active_book_collaboration(
    db: AsyncSession,
    book_id: uuid.UUID,
    user: User,
) -> BookCollaborator | None:
    email = normalize_collaboration_email(user.email)
    collaborator = (
        await db.execute(
            select(BookCollaborator).where(
                BookCollaborator.book_id == book_id,
                BookCollaborator.email == email,
                BookCollaborator.invite_status == "active",
            )
        )
    ).scalar_one_or_none()
    if collaborator is None or collaborator.role != "beta_reader":
        return collaborator

    latest_assignment = (
        await db.execute(
            select(BetaReadAssignment)
            .where(
                BetaReadAssignment.book_id == book_id,
                BetaReadAssignment.reader_email == email,
            )
            .order_by(BetaReadAssignment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_assignment is None:
        return collaborator

    current = datetime.now(UTC)
    if latest_assignment.state in {
        BetaReadAssignmentState.REVOKED.value,
        BetaReadAssignmentState.DISQUALIFIED.value,
    }:
        return None
    if latest_assignment.state == BetaReadAssignmentState.MISSED.value:
        if latest_assignment.missed_reason == "deadline_expired" and settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY:
            return collaborator
        return None
    if (
        latest_assignment.state in {
            BetaReadAssignmentState.ACTIVE.value,
            BetaReadAssignmentState.IN_PROGRESS.value,
            BetaReadAssignmentState.READY_TO_SUBMIT.value,
            BetaReadAssignmentState.EXPIRED.value,
        }
        and latest_assignment.expires_at
        and latest_assignment.expires_at <= current
        and not settings.BETA_READ_KEEP_READ_ONLY_AFTER_EXPIRY
    ):
        return None
    return collaborator


async def get_book_with_collaboration_access(
    db: AsyncSession,
    book_id: uuid.UUID,
    user: User,
    *,
    options: tuple | None = None,
) -> tuple[Book, BookCollaborator | None]:
    if options:
        result = await db.execute(
            select(Book).where(Book.id == book_id).options(*options)
        )
        book = result.scalars().first()
    else:
        book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    if book.user_id == user.id:
        return book, None
    collaborator = await find_active_book_collaboration(db, book_id, user)
    if collaborator:
        return book, collaborator
    raise HTTPException(404, "Book not found")


def require_book_owner_access(
    book: Book,
    user: User,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    if collaborator is not None or book.user_id != user.id:
        raise HTTPException(403, "Only the book owner can use this route.")
    return build_book_access_context(book, user_id=user.id, collaborator=None)


def assert_editor_project_not_rebuilding(book: Book) -> None:
    if getattr(book, "is_editor_project", False):
        from app.services.editor_project_service import get_rebuild_run_id

        if get_rebuild_run_id(book) is not None:
            raise HTTPException(409, "Cannot edit the manuscript while reprocessing is in progress.")


def require_author_shell_access(
    book: Book,
    user: User,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    access = build_book_access_context(book, user_id=user.id, collaborator=collaborator)
    if access.workspace_shell != "author":
        raise HTTPException(403, "This share is limited to the reader workspace.")
    return access


def require_reader_shell_access(
    book: Book,
    user: User,
    collaborator: BookCollaborator | None = None,
) -> BookAccessContext:
    access = build_book_access_context(book, user_id=user.id, collaborator=collaborator)
    if access.workspace_shell != "reader":
        raise HTTPException(403, "This route is only available in the reader workspace.")
    return access


def require_collaboration_chapter_access(
    collaborator: BookCollaborator | None,
    chapter_number: int,
) -> None:
    if not collaboration_allows_chapter(collaborator, chapter_number):
        raise HTTPException(403, "This share does not include that chapter.")


async def list_book_collaborators(db: AsyncSession, book: Book) -> list[BookCollaboratorOut]:
    rows = (
        await db.execute(
            select(BookCollaborator)
            .where(BookCollaborator.book_id == book.id)
            .order_by(BookCollaborator.invited_at.desc())
        )
    ).scalars().all()
    return [serialize_book_collaborator(row) for row in rows]


async def create_book_collaborator(
    db: AsyncSession,
    book: Book,
    *,
    email: str,
    role: str,
    scope: CollaborationScope,
    permissions: CollaborationPermissions | None = None,
    display_name: str | None = None,
) -> BookCollaboratorOut:
    normalized_email = normalize_collaboration_email(email)
    normalized_role = normalize_collaboration_role(role)
    normalized_scope = normalize_collaboration_scope(scope)
    normalized_permissions = normalize_collaboration_permissions(
        permissions,
        role=normalized_role,
        scope=normalized_scope,
    )
    invited_user = (
        await db.execute(select(User).where(User.email == normalized_email))
    ).scalar_one_or_none()
    collaborator = (
        await db.execute(
            select(BookCollaborator).where(
                BookCollaborator.book_id == book.id,
                BookCollaborator.email == normalized_email,
            )
        )
    ).scalar_one_or_none()
    if collaborator is None:
        collaborator = BookCollaborator(book_id=book.id, email=normalized_email)
        db.add(collaborator)
    collaborator.display_name = str(display_name or "").strip() or None
    collaborator.role = normalized_role
    apply_collaboration_scope(collaborator, normalized_scope)
    apply_collaboration_permissions(
        collaborator,
        normalized_permissions,
        role=normalized_role,
        scope=normalized_scope,
    )
    collaborator.invite_status = "active"
    collaborator.invited_user_id = invited_user.id if invited_user else None
    await db.commit()
    await db.refresh(collaborator)
    return serialize_book_collaborator(collaborator)


async def update_book_collaborator(
    db: AsyncSession,
    book: Book,
    collaboration_id: uuid.UUID,
    *,
    role: str | None = None,
    scope: CollaborationScope | None = None,
    permissions: CollaborationPermissions | None = None,
    display_name: str | None = None,
    invite_status: str | None = None,
) -> BookCollaboratorOut:
    collaborator = await db.get(BookCollaborator, collaboration_id)
    if not collaborator or collaborator.book_id != book.id:
        raise HTTPException(404, "Collaborator not found")
    next_role = collaborator.role
    if role is not None:
        next_role = normalize_collaboration_role(role)
        collaborator.role = next_role
    next_scope = collaborator.scope
    if scope is not None:
        next_scope = normalize_collaboration_scope(scope)
        apply_collaboration_scope(collaborator, next_scope)
    if permissions is not None or role is not None or scope is not None:
        apply_collaboration_permissions(
            collaborator,
            permissions if permissions is not None else collaborator.permissions,
            role=next_role,
            scope=next_scope,
        )
    if display_name is not None:
        collaborator.display_name = str(display_name or "").strip() or None
    if invite_status is not None:
        if invite_status not in {"active", "revoked"}:
            raise HTTPException(400, "Invalid invite status")
        collaborator.invite_status = invite_status
    await db.commit()
    await db.refresh(collaborator)
    return serialize_book_collaborator(collaborator)


async def delete_book_collaborator(db: AsyncSession, book: Book, collaboration_id: uuid.UUID) -> None:
    collaborator = await db.get(BookCollaborator, collaboration_id)
    if not collaborator or collaborator.book_id != book.id:
        raise HTTPException(404, "Collaborator not found")
    await db.delete(collaborator)
    await db.commit()


async def get_owned_book(
    db: AsyncSession,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    options: tuple | None = None,
) -> Book:
    if options:
        result = await db.execute(
            select(Book).where(Book.id == book_id, Book.user_id == user_id).options(*options)
        )
        book = result.scalars().first()
    else:
        book = await db.get(Book, book_id)
    if not book or book.user_id != user_id:
        raise HTTPException(404, "Book not found")
    return book


async def get_owned_series(db: AsyncSession, series_id: uuid.UUID, user_id: uuid.UUID) -> Series:
    series = await db.get(Series, series_id)
    if not series or series.user_id != user_id:
        raise HTTPException(404, "Series not found")
    return series


async def list_book_notes(
    db: AsyncSession,
    book: Book,
    *,
    collaborator: BookCollaborator | None = None,
) -> list[dict]:
    rows = list((
        await db.execute(
            select(BookNote, Chapter.title)
            .outerjoin(
                Chapter,
                (Chapter.book_id == BookNote.book_id) & (Chapter.number == BookNote.chapter_number),
            )
            .where(BookNote.book_id == book.id)
            .order_by(BookNote.chapter_number.asc().nullsfirst(), BookNote.updated_at.desc())
        )
    ).all())
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_NOTE,
        entity_ids=[note.id for note, _chapter_title in rows],
        book_id=book.id,
    )
    notes = [
        {
            "id": str(note.id),
            "book_id": str(book.id),
            "book_title": book.title,
            "chapter_number": note.chapter_number,
            "chapter_title": chapter_title,
            "title": note.title,
            "body": note.body,
            "tags": tags_by_note.get(note.id, []),
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note, chapter_title in rows
    ]
    if collaborator is None:
        return notes
    return [
        note for note in notes
        if note["chapter_number"] is None or collaboration_allows_chapter(collaborator, int(note["chapter_number"]))
    ]


async def list_user_notes(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    rows = list((
        await db.execute(
            select(BookNote, Book.title, Chapter.title)
            .join(Book, Book.id == BookNote.book_id)
            .outerjoin(
                Chapter,
                (Chapter.book_id == BookNote.book_id) & (Chapter.number == BookNote.chapter_number),
            )
            .where(BookNote.user_id == user_id)
            .order_by(BookNote.updated_at.desc())
        )
    ).all())
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_NOTE,
        entity_ids=[note.id for note, _book_title, _chapter_title in rows],
    )
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "book_title": book_title,
            "chapter_number": note.chapter_number,
            "chapter_title": chapter_title,
            "title": note.title,
            "body": note.body,
            "tags": tags_by_note.get(note.id, []),
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note, book_title, chapter_title in rows
    ]


def _annotation_category(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if not normalized:
        return "general"
    if normalized not in MANUSCRIPT_ANNOTATION_CATEGORIES:
        raise HTTPException(400, "Invalid annotation category")
    return normalized


def _annotation_status(value: str | None) -> str:
    normalized = str(value or "open").strip().lower()
    if normalized not in MANUSCRIPT_ANNOTATION_STATUSES:
        raise HTTPException(400, "Invalid annotation status")
    return normalized


def _annotation_visibility(value: str | None) -> str:
    normalized = str(value or "shared").strip().lower()
    if normalized not in MANUSCRIPT_ANNOTATION_VISIBILITIES:
        raise HTTPException(400, "Invalid annotation visibility")
    return normalized


def _annotation_actor_label(user: User) -> str:
    username = " ".join(str(user.username or "").split()).strip()
    if username:
        return username
    email_name = str(user.email or "").split("@", 1)[0].strip()
    return email_name or "Reviewer"


def _can_edit_annotation(annotation: ManuscriptAnnotation, *, actor_user_id: uuid.UUID, book_owner_id: uuid.UUID) -> bool:
    return annotation.user_id == actor_user_id or book_owner_id == actor_user_id


def _serialize_manuscript_annotation(
    annotation: ManuscriptAnnotation,
    *,
    book: Book,
    chapter_title: str | None,
    actor_user_id: uuid.UUID,
    created_by_label: str,
) -> dict[str, Any]:
    return {
        "id": str(annotation.id),
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": annotation.chapter_number,
        "chapter_title": chapter_title,
        "category": annotation.category,
        "status": annotation.status,
        "visibility": annotation.visibility,
        "quote": annotation.quote,
        "comment": annotation.comment,
        "anchor_context_before": annotation.anchor_context_before,
        "anchor_context_after": annotation.anchor_context_after,
        "start_offset": annotation.start_offset,
        "end_offset": annotation.end_offset,
        "created_by_user_id": str(annotation.user_id),
        "created_by_label": created_by_label,
        "can_edit": _can_edit_annotation(annotation, actor_user_id=actor_user_id, book_owner_id=book.user_id),
        "resolved_at": annotation.resolved_at,
        "created_at": annotation.created_at,
        "updated_at": annotation.updated_at,
    }


async def list_manuscript_annotations(
    db: AsyncSession,
    *,
    book: Book,
    actor: User,
    collaborator: BookCollaborator | None = None,
    chapter_number: int | None = None,
) -> list[dict[str, Any]]:
    query = (
        select(ManuscriptAnnotation, Chapter.title, User.username, User.email)
        .join(User, User.id == ManuscriptAnnotation.user_id)
        .outerjoin(
            Chapter,
            (Chapter.book_id == ManuscriptAnnotation.book_id) & (Chapter.number == ManuscriptAnnotation.chapter_number),
        )
        .where(ManuscriptAnnotation.book_id == book.id)
        .order_by(
            ManuscriptAnnotation.chapter_number.asc(),
            ManuscriptAnnotation.status.asc(),
            ManuscriptAnnotation.updated_at.desc(),
        )
    )
    if chapter_number is not None:
        query = query.where(ManuscriptAnnotation.chapter_number == chapter_number)

    rows = (await db.execute(query)).all()
    payload: list[dict[str, Any]] = []
    for annotation, chapter_title, username, email in rows:
        if collaborator is not None and not collaboration_allows_chapter(collaborator, annotation.chapter_number):
            continue
        if annotation.visibility == "private" and annotation.user_id != actor.id:
            continue
        payload.append(
            _serialize_manuscript_annotation(
                annotation,
                book=book,
                chapter_title=chapter_title,
                actor_user_id=actor.id,
                created_by_label=" ".join(str(username or "").split()).strip() or str(email or "").split("@", 1)[0] or "Reviewer",
            )
        )
    return payload


async def save_manuscript_annotation(
    db: AsyncSession,
    *,
    book: Book,
    actor: User,
    annotation_id: str | None,
    chapter_number: int | None,
    category: str | None,
    status: str | None,
    visibility: str | None,
    quote: str | None,
    comment: str | None,
    anchor_context_before: str | None,
    anchor_context_after: str | None,
    start_offset: int | None,
    end_offset: int | None,
) -> dict[str, Any]:
    annotation: ManuscriptAnnotation | None = None
    if annotation_id:
        try:
            parsed_annotation_id = uuid.UUID(annotation_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid annotation id") from exc
        annotation = await db.get(ManuscriptAnnotation, parsed_annotation_id)
        if not annotation or annotation.book_id != book.id:
            raise HTTPException(404, "Annotation not found")
        if not _can_edit_annotation(annotation, actor_user_id=actor.id, book_owner_id=book.user_id):
            raise HTTPException(403, "You cannot edit this annotation.")
    else:
        annotation = ManuscriptAnnotation(
            user_id=actor.id,
            book_id=book.id,
        )
        db.add(annotation)

    normalized_chapter_number = chapter_number if chapter_number is not None else annotation.chapter_number
    if normalized_chapter_number is None or normalized_chapter_number < 1:
        raise HTTPException(400, "Annotation chapter is required")

    normalized_quote = _clean_text(quote if quote is not None else annotation.quote)
    normalized_comment = _clean_text(comment if comment is not None else annotation.comment)
    if not normalized_quote:
        raise HTTPException(400, "Annotation quote is required")
    if not normalized_comment:
        raise HTTPException(400, "Annotation comment is required")

    normalized_start_offset = start_offset if start_offset is not None else annotation.start_offset
    normalized_end_offset = end_offset if end_offset is not None else annotation.end_offset
    if normalized_start_offset is not None and normalized_end_offset is not None and normalized_end_offset < normalized_start_offset:
        raise HTTPException(400, "Annotation offsets are invalid")

    annotation.chapter_number = normalized_chapter_number
    annotation.category = _annotation_category(category if category is not None else annotation.category)
    annotation.status = _annotation_status(status if status is not None else annotation.status)
    annotation.visibility = _annotation_visibility(visibility if visibility is not None else annotation.visibility)
    annotation.quote = normalized_quote
    annotation.comment = normalized_comment
    annotation.anchor_context_before = _clean_optional_text(anchor_context_before if anchor_context_before is not None else annotation.anchor_context_before)
    annotation.anchor_context_after = _clean_optional_text(anchor_context_after if anchor_context_after is not None else annotation.anchor_context_after)
    annotation.start_offset = normalized_start_offset
    annotation.end_offset = normalized_end_offset
    annotation.resolved_at = datetime.now(UTC) if annotation.status == "resolved" else None

    await db.commit()
    await db.refresh(annotation)

    chapter_title = (
        await db.execute(
            select(Chapter.title).where(Chapter.book_id == book.id, Chapter.number == annotation.chapter_number)
        )
    ).scalar_one_or_none()
    creator = actor if annotation.user_id == actor.id else await db.get(User, annotation.user_id)
    return _serialize_manuscript_annotation(
        annotation,
        book=book,
        chapter_title=chapter_title,
        actor_user_id=actor.id,
        created_by_label=_annotation_actor_label(creator or actor),
    )


async def delete_manuscript_annotation(
    db: AsyncSession,
    *,
    book: Book,
    actor: User,
    annotation_id: uuid.UUID,
) -> None:
    annotation = await db.get(ManuscriptAnnotation, annotation_id)
    if not annotation or annotation.book_id != book.id:
        raise HTTPException(404, "Annotation not found")
    if not _can_edit_annotation(annotation, actor_user_id=actor.id, book_owner_id=book.user_id):
        raise HTTPException(403, "You cannot delete this annotation.")
    await db.delete(annotation)
    await db.commit()


async def list_vault_bible_notes(db: AsyncSession, book: Book, user_id: uuid.UUID) -> list[dict]:
    rows = (
        await db.execute(
            select(VaultNote)
            .where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.source == VaultNoteSource.CHARACTER_BIBLE.value,
            )
            .order_by(VaultNote.path.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "path": note.path,
            "source": note.source,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note in rows
    ]


async def load_vault_note_overrides(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    *,
    source: str = VaultNoteSource.CHARACTER_BIBLE.value,
) -> dict[str, str]:
    normalized_source = normalize_vault_note_source(source)
    rows = (
        await db.execute(
            select(VaultNote.path, VaultNote.content)
            .where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.source == normalized_source,
            )
        )
    ).all()
    return {path: content for path, content in rows}


def normalize_vault_note_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    if normalized not in VAULT_NOTE_SOURCES:
        raise HTTPException(400, "Invalid vault note source")
    return normalized


def normalize_vault_note_path(path: str) -> str:
    normalized_path = (path or "").replace("\\", "/").strip().strip("/")
    if not normalized_path:
        raise HTTPException(400, "Path is required")
    segments = [segment.strip() for segment in normalized_path.split("/") if segment.strip()]
    if not segments or any(segment in {".", ".."} for segment in segments):
        raise HTTPException(400, "Invalid path")
    return "/".join(segments)


def vault_note_title(path: str) -> str:
    filename = path.replace("\\", "/").split("/")[-1]
    return os.path.splitext(filename)[0].strip() or filename.strip()


def vault_note_folder(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "/" not in normalized:
        return "Root"
    return normalized.rsplit("/", 1)[0] or "Root"


def extract_wiki_links(markdown: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for reference in extract_wiki_references(markdown):
        target = reference["target"]
        alias = reference["alias"]
        if not target:
            continue
        links.append({"target": target, "alias": alias or target})
    return links


def extract_wiki_references(markdown: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for embed_prefix, raw_value in WIKI_REFERENCE_RE.findall(markdown or ""):
        raw_target, _, raw_alias = raw_value.partition("|")
        target = raw_target.split("#", 1)[0].strip()
        alias = raw_alias.strip() or target
        if not target:
            continue
        references.append(
            {
                "target": target,
                "alias": alias,
                "link_type": "embed" if embed_prefix == "!" else "reference",
            }
        )
    return references


def extract_wiki_tags(markdown: str) -> list[str]:
    tags: list[str] = []
    for match in WIKI_TAG_RE.findall(markdown or ""):
        cleaned = normalize_wiki_tag(match)
        if cleaned:
            tags.append(cleaned)
    return list(dict.fromkeys(tags))


def normalize_wiki_tag(tag: str) -> str:
    cleaned = " ".join((tag or "").replace("_", "-").split()).strip()
    cleaned = cleaned.strip("#")
    return cleaned.lower()


def build_vault_graph(notes: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    notes_by_path = {note["path"]: note for note in notes}
    title_to_path: dict[str, str] = {}
    for path in sorted(notes_by_path):
        title_to_path.setdefault(vault_note_title(path).lower(), path)

    nodes: list[dict[str, str | int]] = []
    link_counts = {path: 0 for path in notes_by_path}
    edges: list[dict[str, str | None]] = []
    edge_keys: set[tuple[str, str, str | None]] = set()

    for path, note in notes_by_path.items():
        for link in extract_wiki_links(str(note.get("content") or "")):
            target_path = title_to_path.get(link["target"].lower())
            if not target_path:
                continue
            link_counts[path] += 1
            edge_key = (path, target_path, link["alias"])
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append({"source": path, "target": target_path, "label": link["alias"]})

    for path in sorted(notes_by_path):
        nodes.append(
            {
                "id": path,
                "path": path,
                "title": vault_note_title(path),
                "folder": vault_note_folder(path),
                "link_count": link_counts[path],
            }
        )

    return {"nodes": nodes, "edges": edges}


async def _load_vault_scope_notes(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str,
) -> tuple[list[VaultNote], dict[uuid.UUID, Book]]:
    normalized_source = normalize_vault_note_source(source)
    scoped_books = {book.id: book}
    if book.primary_series_id:
        series_book_rows = (
            await db.execute(
                select(Book)
                .join(SeriesBook, SeriesBook.book_id == Book.id)
                .where(SeriesBook.series_id == book.primary_series_id, Book.user_id == user_id)
            )
        ).scalars().all()
        for row in series_book_rows:
            scoped_books[row.id] = row

    notes = (
        await db.execute(
            select(VaultNote)
            .where(
                VaultNote.user_id == user_id,
                VaultNote.source == normalized_source,
                VaultNote.book_id.in_(list(scoped_books)),
            )
            .order_by(VaultNote.book_id.asc(), VaultNote.path.asc())
        )
    ).scalars().all()
    notes = list(notes)
    return notes, scoped_books


def _normalize_vault_note_path_key(path: str) -> str:
    return normalize_vault_note_path(path).lower()


def _resolve_vault_reference(reference: str, *, notes_by_path: dict[str, VaultNote], notes_by_title: dict[str, VaultNote]) -> VaultNote | None:
    normalized_path = reference.replace("\\", "/").strip().lower()
    if normalized_path.endswith(".md"):
        normalized_path = normalized_path[:-3]

    for path_key, note in notes_by_path.items():
        candidate_path = path_key.lower()
        if candidate_path.endswith(".md"):
            candidate_path = candidate_path[:-3]
        if candidate_path == normalized_path:
            return note

    title_key = vault_note_title(reference).lower()
    return notes_by_title.get(title_key)


async def _get_vault_note_by_path(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> VaultNote:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path).lower()
    note = (
        await db.execute(
            select(VaultNote).where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.source == normalized_source,
                func.lower(VaultNote.path) == normalized_path,
            )
        )
    ).scalars().first()
    if note is None:
        raise HTTPException(404, "Note not found")
    return note


def _serialize_vault_note_link(link: NoteLink, source_path: str, target_path: str) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "book_id": str(link.book_id),
        "source_note_id": str(link.source_note_id),
        "source_note_path": source_path,
        "target_note_id": str(link.target_note_id),
        "target_note_path": target_path,
        "link_type": link.link_type,
        "target_label": getattr(link, "target_label", None),
        "created_at": link.created_at,
    }


def _serialize_vault_note_tag(tag: NoteTag, note_path: str) -> dict[str, Any]:
    return {
        "id": str(tag.id),
        "book_id": str(tag.book_id),
        "note_id": str(tag.note_id),
        "note_path": note_path,
        "tag_name": tag.tag_name,
        "created_at": tag.created_at,
    }


def _serialize_vault_note_series_link(
    link: NoteSeriesLink,
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "series_id": str(link.series_id),
        "source_book_id": str(link.source_book_id),
        "target_book_id": str(link.target_book_id),
        "source_note_id": str(link.source_note_id),
        "source_note_path": source_path,
        "target_note_id": str(link.target_note_id),
        "target_note_path": target_path,
        "link_type": link.link_type,
        "created_at": link.created_at,
    }


async def sync_vault_note_relations(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> dict[str, int]:
    normalized_source = normalize_vault_note_source(source)
    if normalized_source != VaultNoteSource.USER_NOTES.value:
        return {"links": 0, "backlinks": 0, "tags": 0, "series_links": 0}

    notes, scoped_books = await _load_vault_scope_notes(db, book=book, user_id=user_id, source=normalized_source)
    scoped_book_ids = list(scoped_books)

    for table in (NoteLink, NoteBacklink, NoteTag):
        await db.execute(
            delete(table).where(
                table.user_id == user_id,
                table.book_id.in_(scoped_book_ids),
            )
        )
    await db.execute(
        delete(NoteSeriesLink).where(
            NoteSeriesLink.user_id == user_id,
            NoteSeriesLink.source_book_id.in_(scoped_book_ids),
        )
    )
    await db.flush()

    notes_by_path = {note.path.lower(): note for note in notes}
    notes_by_title: dict[str, VaultNote] = {}
    for note in notes:
        notes_by_title.setdefault(vault_note_title(note.path).lower(), note)

    links_created = 0
    backlinks_created = 0
    tags_created = 0
    series_links_created = 0

    for note in notes:
        references = extract_wiki_references(note.content)
        note_tags = extract_wiki_tags(note.content)

        for tag_name in note_tags:
            db.add(
                NoteTag(
                    user_id=user_id,
                    book_id=note.book_id,
                    note_id=note.id,
                    tag_name=tag_name,
                )
            )
            tags_created += 1

        for reference in references:
            target_note = _resolve_vault_reference(reference["target"], notes_by_path=notes_by_path, notes_by_title=notes_by_title)
            if target_note is None or target_note.id == note.id:
                continue

            db.add(
                NoteLink(
                    user_id=user_id,
                    book_id=note.book_id,
                    source_note_id=note.id,
                    target_note_id=target_note.id,
                    link_type=reference["link_type"],
                    target_label=reference["alias"],
                )
            )
            db.add(
                NoteBacklink(
                    user_id=user_id,
                    book_id=target_note.book_id,
                    source_note_id=note.id,
                    target_note_id=target_note.id,
                    link_type=reference["link_type"],
                )
            )
            links_created += 1
            backlinks_created += 1

            if note.book_id != target_note.book_id and book.primary_series_id and target_note.book_id in scoped_books:
                db.add(
                    NoteSeriesLink(
                        user_id=user_id,
                        series_id=book.primary_series_id,
                        source_book_id=note.book_id,
                        target_book_id=target_note.book_id,
                        source_note_id=note.id,
                        target_note_id=target_note.id,
                        link_type=reference["link_type"],
                    )
                )
                series_links_created += 1

    await db.flush()
    await db.commit()
    return {
        "links": links_created,
        "backlinks": backlinks_created,
        "tags": tags_created,
        "series_links": series_links_created,
    }


async def list_vault_note_links(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(VaultNote)
    target_note = aliased(VaultNote)
    rows = (
        await db.execute(
            select(NoteLink, source_note.path, target_note.path)
            .join(source_note, NoteLink.source_note_id == source_note.id)
            .join(target_note, NoteLink.target_note_id == target_note.id)
            .where(
                NoteLink.user_id == user_id,
                NoteLink.book_id == book.id,
                NoteLink.source_note_id == note.id,
            )
            .order_by(NoteLink.created_at.asc())
        )
    ).all()
    return [_serialize_vault_note_link(link, source_path, target_path) for link, source_path, target_path in rows]


async def list_vault_note_backlinks(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(VaultNote)
    target_note = aliased(VaultNote)
    rows = (
        await db.execute(
            select(NoteBacklink, source_note.path, target_note.path)
            .join(source_note, NoteBacklink.source_note_id == source_note.id)
            .join(target_note, NoteBacklink.target_note_id == target_note.id)
            .where(
                NoteBacklink.user_id == user_id,
                NoteBacklink.book_id == book.id,
                NoteBacklink.target_note_id == note.id,
            )
            .order_by(NoteBacklink.created_at.asc())
        )
    ).all()
    return [_serialize_vault_note_link(link, source_path, target_path) for link, source_path, target_path in rows]


async def list_vault_note_tags(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    rows = (
        await db.execute(
            select(NoteTag, VaultNote.path)
            .join(VaultNote, NoteTag.note_id == VaultNote.id)
            .where(
                NoteTag.user_id == user_id,
                NoteTag.book_id == book.id,
                NoteTag.note_id == note.id,
            )
            .order_by(NoteTag.tag_name.asc())
        )
    ).all()
    return [_serialize_vault_note_tag(tag, note_path) for tag, note_path in rows]


async def list_vault_note_series_links(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> list[dict[str, Any]]:
    note = await _get_vault_note_by_path(db, book=book, user_id=user_id, path=path)
    source_note = aliased(VaultNote)
    target_note = aliased(VaultNote)
    rows = (
        await db.execute(
            select(NoteSeriesLink, source_note.path, target_note.path)
            .join(source_note, NoteSeriesLink.source_note_id == source_note.id)
            .join(target_note, NoteSeriesLink.target_note_id == target_note.id)
            .where(
                NoteSeriesLink.user_id == user_id,
                NoteSeriesLink.source_book_id == book.id,
                NoteSeriesLink.source_note_id == note.id,
            )
            .order_by(NoteSeriesLink.created_at.asc())
        )
    ).all()
    return [_serialize_vault_note_series_link(link, source_path, target_path) for link, source_path, target_path in rows]


async def list_vault_note_relations(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "links": await list_vault_note_links(db, book=book, user_id=user_id, path=path),
        "backlinks": await list_vault_note_backlinks(db, book=book, user_id=user_id, path=path),
        "tags": await list_vault_note_tags(db, book=book, user_id=user_id, path=path),
        "series_links": await list_vault_note_series_links(db, book=book, user_id=user_id, path=path),
    }


async def list_vault_notes(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> list[dict]:
    normalized_source = normalize_vault_note_source(source)
    rows = (
        await db.execute(
            select(VaultNote)
            .where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.source == normalized_source,
            )
            .order_by(VaultNote.path.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(note.id),
            "book_id": str(note.book_id),
            "path": note.path,
            "source": note.source,
            "content": note.content,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }
        for note in rows
    ]


async def save_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    content: str,
    source: str = VaultNoteSource.CHARACTER_BIBLE.value,
    sync_relations: bool = True,
) -> dict:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path)
    normalized_content = content.replace("\r\n", "\n")

    note: VaultNote | None = (
        await db.execute(
            select(VaultNote).where(
                VaultNote.book_id == book.id,
                VaultNote.user_id == user_id,
                VaultNote.path == normalized_path,
                VaultNote.source == normalized_source,
            )
        )
    ).scalars().first()

    if note is None:
        note = VaultNote(
            user_id=user_id,
            book_id=book.id,
            path=normalized_path,
            source=normalized_source,
            content=normalized_content,
        )
        db.add(note)
    else:
        note_any = cast(Any, note)
        note_any.path = normalized_path
        note_any.source = normalized_source
        note_any.content = normalized_content

    await db.commit()
    await db.refresh(note)
    if sync_relations and normalized_source == VaultNoteSource.USER_NOTES.value:
        await sync_vault_note_relations(db, book=book, user_id=user_id, source=normalized_source)
    return {
        "path": note.path,
        "source": note.source,
        "content": note.content,
        "persisted": True,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def delete_vault_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    path: str,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> None:
    normalized_source = normalize_vault_note_source(source)
    normalized_path = normalize_vault_note_path(path)
    deleted = await db.execute(
        delete(VaultNote).where(
            VaultNote.book_id == book.id,
            VaultNote.user_id == user_id,
            VaultNote.path == normalized_path,
            VaultNote.source == normalized_source,
        )
    )
    if not deleted.rowcount:
        raise HTTPException(404, "Note not found")
    await db.commit()
    if normalized_source == VaultNoteSource.USER_NOTES.value:
        await sync_vault_note_relations(db, book=book, user_id=user_id, source=normalized_source)


async def import_vault_notes_zip(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    archive_bytes: bytes,
    source: str = VaultNoteSource.USER_NOTES.value,
) -> list[dict]:
    normalized_source = normalize_vault_note_source(source)
    if not archive_bytes:
        raise HTTPException(400, "ZIP file is empty")

    validate_zip_archive_safety(
        archive_bytes,
        max_entries=settings.UPLOAD_ARCHIVE_MAX_ENTRIES,
        max_total_uncompressed_bytes=settings.UPLOAD_ARCHIVE_MAX_UNCOMPRESSED_BYTES,
        max_compression_ratio=settings.UPLOAD_ARCHIVE_MAX_COMPRESSION_RATIO,
        label="ZIP file",
    )

    imported: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            for member in members:
                if member.filename.startswith("__MACOSX/"):
                    continue
                if not member.filename.lower().endswith(".md"):
                    continue
                normalized_path = normalize_vault_note_path(member.filename)
                content = archive.read(member).decode("utf-8")
                imported.append(
                    await save_vault_note(
                        db,
                        book=book,
                        user_id=user_id,
                        path=normalized_path,
                        content=content,
                        source=normalized_source,
                        sync_relations=False,
                    )
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Invalid ZIP file") from exc
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "ZIP contains a non-UTF-8 markdown file") from exc

    if not imported:
        raise HTTPException(400, "ZIP did not contain any markdown notes")
    if normalized_source == VaultNoteSource.USER_NOTES.value:
        await sync_vault_note_relations(db, book=book, user_id=user_id, source=normalized_source)
    return imported


def export_vault_notes_zip(*, notes: list[dict[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for note in sorted(notes, key=lambda item: item["path"]):
            archive.writestr(note["path"], str(note["content"] or "").replace("\r\n", "\n"))
    return buffer.getvalue()


async def save_book_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    note_id: str | None,
    chapter_number: int | None,
    title: str | None,
    body: str,
) -> dict:
    normalized_title = _clean_optional_text(" ".join((title or "").split()).strip())
    normalized_body = _clean_text(body)
    if not normalized_body:
        raise HTTPException(400, "Note body is required")

    if chapter_number is not None and chapter_number < 1:
        raise HTTPException(400, "Invalid chapter number")

    note: BookNote | None = None
    if note_id:
        try:
            parsed_note_id = uuid.UUID(note_id)
        except ValueError as exc:
            raise HTTPException(400, "Invalid note id") from exc
        note = await db.get(BookNote, parsed_note_id)
        if not note or note.user_id != user_id or note.book_id != book.id:
            raise HTTPException(404, "Note not found")
    else:
        note = BookNote(user_id=user_id, book_id=book.id)
        db.add(note)

    note_any = cast(Any, note)
    note_any.chapter_number = chapter_number
    note_any.title = normalized_title
    note_any.body = normalized_body
    await db.commit()
    await db.refresh(note)

    chapter_title = None
    if note.chapter_number is not None:
        chapter_title = (
            await db.execute(
                select(Chapter.title).where(Chapter.book_id == book.id, Chapter.number == note.chapter_number)
            )
        ).scalar_one_or_none()

    return {
        "id": str(note.id),
        "book_id": str(book.id),
        "book_title": book.title,
        "chapter_number": note.chapter_number,
        "chapter_title": chapter_title,
        "title": note.title,
        "body": note.body,
        "tags": await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_NOTE,
            entity_id=note.id,
            book_id=book.id,
        ),
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def delete_book_note(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    note_id: uuid.UUID,
) -> None:
    deleted = await db.execute(
        delete(BookNote).where(
            BookNote.id == note_id,
            BookNote.user_id == user_id,
            BookNote.book_id == book.id,
        )
    )
    if not deleted.rowcount:
        raise HTTPException(404, "Note not found")
    await db.commit()


async def resolve_owned_series_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    series_ids: list[str],
) -> list[Series]:
    cleaned_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()

    for raw in series_ids:
        value = (raw or "").strip()
        if not value:
            continue
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise HTTPException(400, "Invalid series id") from exc
        if parsed in seen:
            continue
        seen.add(parsed)
        cleaned_ids.append(parsed)

    if not cleaned_ids:
        return []

    rows = (
        await db.execute(
            select(Series).where(Series.user_id == user_id, Series.id.in_(cleaned_ids))
        )
    ).scalars().all()
    found = {series.id for series in rows}
    if len(found) != len(cleaned_ids):
        raise HTTPException(404, "Series not found")

    order = {series_id: index for index, series_id in enumerate(cleaned_ids)}
    return sorted(rows, key=lambda series: order[series.id])


async def refresh_screenplay_scene_rows(
    db: AsyncSession,
    *,
    book: Book,
    parsed_scenes: list[Any],
    starting_number: int = 1,
    replace_scene_numbers: set[int] | None = None,
) -> None:
    from app.utils.screenplay_utils import replace_book_scenes

    chapter_rows = (
        await db.execute(
            select(Chapter.number, Chapter.id).where(Chapter.book_id == book.id).order_by(Chapter.number)
        )
    ).all()
    chapter_ids_by_number = {int(number): chapter_id for number, chapter_id in chapter_rows}
    await replace_book_scenes(
        db,
        book=book,
        parsed_scenes=parsed_scenes,
        chapter_ids_by_number=chapter_ids_by_number,
        starting_number=starting_number,
        replace_scene_numbers=replace_scene_numbers,
    )


def _scene_slug(value: str, fallback: str = "scene") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned or fallback


def _scene_display_title(text: str, index: int) -> str:
    for line in (text or "").splitlines():
        cleaned = " ".join(line.split()).strip()
        if cleaned and not SCENE_BREAK_LINE_RE.match(cleaned):
            return cleaned[:80]
    return f"Scene {index}"


def _scene_folder_for_chapter(chapter_number: int | None) -> str:
    if isinstance(chapter_number, int) and chapter_number > 0:
        return f"scenes/chapter-{chapter_number:02d}"
    return "scenes/unassigned"


def build_novel_scene_path(*, chapter_number: int | None, sort_order: int, title: str) -> str:
    return f"{_scene_folder_for_chapter(chapter_number)}/{sort_order:03d}-{_scene_slug(title)}.md"


def _scene_metadata_key(label: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", label.strip().lower()).strip()
    if not normalized:
        return None
    alias = SCENE_METADATA_ALIASES.get(normalized)
    if alias:
        return alias
    key = normalized.replace(" ", "_")
    return key if key in SCENE_METADATA_LABELS else None


def _append_scene_metadata_value(metadata: dict[str, Any], key: str, value: str) -> None:
    cleaned = _clean_text(value)
    if not cleaned:
        return
    if key in SCENE_METADATA_LIST_FIELDS:
        values = metadata.setdefault(key, [])
        if isinstance(values, list) and cleaned not in values:
            values.append(cleaned)
        return
    metadata[key] = cleaned


def extract_scene_metadata(text: str, *, description: str | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    active_list_key: str | None = None
    for raw_line in (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        if not line or SCENE_BREAK_LINE_RE.match(line):
            active_list_key = None
            continue
        label_match = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", line)
        if label_match:
            key = _scene_metadata_key(label_match.group(1))
            if key is None:
                active_list_key = None
                continue
            value = label_match.group(2).strip()
            if value:
                _append_scene_metadata_value(metadata, key, value)
                active_list_key = None
            else:
                if key in SCENE_METADATA_LIST_FIELDS:
                    metadata.setdefault(key, [])
                active_list_key = key
            continue
        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        if bullet_match and active_list_key:
            _append_scene_metadata_value(metadata, active_list_key, bullet_match.group(1))
            continue
        active_list_key = None
    if description and "summary" not in metadata:
        metadata["summary"] = _clean_text(description)
    return {key: value for key, value in metadata.items() if value not in ("", [], None)}


def normalize_scene_metadata(metadata: dict[str, Any] | None, *, description: str | None = None) -> dict[str, Any]:
    base = extract_scene_metadata("", description=description)
    source = metadata if isinstance(metadata, dict) else {}
    normalized: dict[str, Any] = {}

    def _clean_list(values: object) -> list[str]:
        cleaned_values: list[str] = []
        if isinstance(values, list):
            for value in values:
                cleaned = _clean_text(value)
                if cleaned and cleaned not in cleaned_values:
                    cleaned_values.append(cleaned)
        elif values is not None:
            cleaned = _clean_text(values)
            if cleaned:
                cleaned_values.append(cleaned)
        return cleaned_values

    for key in SCENE_METADATA_UI_FIELDS:
        value = source.get(key)
        if key in {"tags", "mood", "anchors", "bookmarks"}:
            cleaned_list = _clean_list(value)
            if cleaned_list:
                normalized[key] = cleaned_list
            continue
        cleaned = _clean_optional_text(cast(str | None, value))
        if cleaned:
            normalized[key] = cleaned

    inferred = extract_scene_metadata(str(source.get("summary") or ""), description=description)
    merged = {**base, **inferred, **normalized}
    if description and "summary" not in merged:
        merged["summary"] = _clean_text(description)
    return {key: value for key, value in merged.items() if value not in ("", [], None)}


def _scene_title_line_matches(line: str, title: str) -> bool:
    cleaned = " ".join(line.split()).strip()
    if not cleaned:
        return False
    heading_match = SCENE_HEADING_LINE_RE.match(cleaned)
    if heading_match and heading_match.group(1):
        cleaned = heading_match.group(1).strip()
    title_cleaned = " ".join((title or "").split()).strip()
    return bool(title_cleaned and cleaned.lower() == title_cleaned.lower())


def strip_scene_planning_block(text: str, *, title: str | None = None) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        cleaned = lines[index].strip()
        if (
            (title and _scene_title_line_matches(cleaned, title))
            or re.match(r"^#{1,3}\s+Scene\b", cleaned, re.IGNORECASE)
        ):
            index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1

    consumed_metadata = False
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            if consumed_metadata:
                index += 1
                continue
            break
        if stripped == "---" and consumed_metadata:
            index += 1
            break
        if stripped == "---":
            index += 1
            continue
        label_match = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", stripped)
        if label_match and _scene_metadata_key(label_match.group(1)) is not None:
            consumed_metadata = True
            index += 1
            while index < len(lines):
                continuation = lines[index].strip()
                if not continuation:
                    index += 1
                    break
                next_label = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", continuation)
                if next_label and _scene_metadata_key(next_label.group(1)) is not None:
                    break
                if re.match(r"^[-*]\s+.+$", continuation):
                    index += 1
                    continue
                break
            continue
        break
    return "\n".join(lines[index:]).strip()


def build_scene_chapter_import_text(
    scene: dict[str, Any],
    *,
    scene_number: int,
    include_metadata: bool = True,
) -> str:
    title = _clean_text(scene.get("title")) or f"Scene {scene_number}"
    body = strip_scene_planning_block(str(scene.get("body") or ""), title=title)
    if not include_metadata:
        return body

    heading = title
    scene_label_match = re.match(r"^Scene\s+\d+\b", title, re.IGNORECASE)
    if not scene_label_match:
        heading = f"Scene {scene_number} - {title}"
    lines = [f"## {heading}", ""]
    metadata = scene.get("metadata") or scene.get("scene_metadata") or {}
    if not isinstance(metadata, dict) or not metadata:
        metadata = extract_scene_metadata(str(scene.get("body") or ""), description=cast(str | None, scene.get("description")))

    for key in ["pov", "location", "time", "timeline"]:
        value = metadata.get(key)
        if value:
            lines.append(f"{SCENE_METADATA_LABELS[key]}: {value}")
    if any(metadata.get(key) for key in ["pov", "location", "time", "timeline"]):
        lines.append("")
    for key in ["characters", "objects", "goals", "plot_threads", "mood"]:
        values = metadata.get(key)
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list) and values:
            lines.append(f"{SCENE_METADATA_LABELS[key]}:")
            for value in values:
                cleaned = _clean_text(value)
                if cleaned:
                    lines.append(f"- {cleaned}")
            lines.append("")
    conflict = metadata.get("conflict")
    if conflict:
        lines.extend(["Conflict:", f"- {_clean_text(conflict)}", ""])
    summary = metadata.get("summary")
    if summary:
        lines.extend(["Summary:", f"- {_clean_text(summary)}", ""])
    lines.extend(["---", "", body])
    return "\n".join(lines).strip()


def build_workspace_chapter_text_from_scenes(scenes: list[NovelScene | dict[str, Any]]) -> str:
    compiled_blocks: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        if isinstance(scene, dict):
            title = str(scene.get("title") or "").strip()
            body = str(scene.get("body") or "")
            scene_payload = {
                "title": title,
                "description": scene.get("description"),
                "body": body,
                "metadata": scene.get("metadata") or scene.get("scene_metadata") or {},
            }
        else:
            title = str(getattr(scene, "title", "") or "").strip()
            body = str(getattr(scene, "body", "") or "")
            scene_payload = {
                "title": title,
                "description": getattr(scene, "description", None),
                "body": body,
                "metadata": getattr(scene, "scene_metadata", None) or {},
            }
        compiled_block = build_scene_chapter_import_text(
            scene_payload,
            scene_number=index,
            include_metadata=True,
        )
        if compiled_block:
            compiled_blocks.append(compiled_block)
    return "\n\n***\n\n".join(compiled_blocks).strip()


def chapter_body_needs_scene_workspace_fallback(
    text: str | None,
    *,
    chapter_number: int,
    chapter_title: str | None = None,
) -> bool:
    normalized = " ".join((text or "").split()).strip()
    if not normalized:
        return True

    token = re.sub(r"[^a-z0-9]+", "", normalized.lower())
    if not token:
        return True

    placeholder_tokens = {
        str(chapter_number),
        f"chapter{chapter_number}",
    }
    if chapter_title:
        title_token = re.sub(r"[^a-z0-9]+", "", chapter_title.lower())
        if title_token:
            placeholder_tokens.add(title_token)

    roman_value = _romanize_chapter_number(chapter_number)
    if roman_value:
        placeholder_tokens.add(roman_value.lower())

    return _count_words(normalized) <= 3 and token in placeholder_tokens


def strip_scene_metadata_from_manuscript_text(text: str) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    output: list[str] = []

    def last_non_empty_output() -> str:
        for value in reversed(output):
            if value.strip():
                return value.strip()
        return ""

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if re.match(r"^#{1,3}\s+Scene\b", stripped, re.IGNORECASE):
            if any(line.strip() for line in output) and last_non_empty_output() != "***":
                output.extend(["", "***", ""])
            index += 1
            while index < len(lines) and not lines[index].strip():
                index += 1
            consumed_metadata = False
            while index < len(lines):
                current = lines[index].strip()
                if current == "---":
                    index += 1
                    if consumed_metadata:
                        break
                    continue
                label_match = re.match(r"^([A-Za-z][A-Za-z /_-]{1,32}):\s*(.*)$", current)
                if label_match and _scene_metadata_key(label_match.group(1)) is not None:
                    consumed_metadata = True
                    index += 1
                    continue
                if consumed_metadata and (not current or re.match(r"^[-*]\s+.+$", current)):
                    index += 1
                    continue
                break
            continue
        if SCENE_BREAK_LINE_RE.match(stripped):
            if any(line.strip() for line in output) and last_non_empty_output() != "***":
                output.extend(["", "***", ""])
            index += 1
            continue
        output.append(lines[index].rstrip())
        index += 1
    cleaned = "\n".join(output)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _romanize_chapter_number(chapter_number: int) -> str:
    if chapter_number <= 0 or chapter_number >= 4000:
        return ""
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    remaining = chapter_number
    parts: list[str] = []
    for value, symbol in numerals:
        while remaining >= value:
            parts.append(symbol)
            remaining -= value
    return "".join(parts)


def _split_scene_blocks(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    blocks: list[str] = []
    current: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.rstrip()
        if SCENE_BREAK_LINE_RE.match(line):
            if current and any(part.strip() for part in current):
                blocks.append("\n".join(current).strip())
                current = []
            continue
        heading_match = SCENE_HEADING_LINE_RE.match(line)
        if heading_match:
            if current and any(part.strip() for part in current):
                blocks.append("\n".join(current).strip())
                current = []
            if heading_match.group(1):
                current.append(line)
            continue
        current.append(line)
    if current and any(part.strip() for part in current):
        blocks.append("\n".join(current).strip())
    return blocks or [normalized]


def extract_novel_scene_candidates(
    *,
    text: str,
    chapter_number: int | None,
    source: str = "extracted",
) -> list[dict[str, Any]]:
    blocks = _split_scene_blocks(text)
    scenes: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines()]
        title = _scene_display_title(block, index)
        description = ""
        remaining_lines = lines
        if remaining_lines:
            first_line = " ".join(remaining_lines[0].split()).strip()
            heading_match = SCENE_HEADING_LINE_RE.match(first_line)
            if heading_match and heading_match.group(1):
                title = heading_match.group(1).strip() or title
                remaining_lines = remaining_lines[1:]
            elif len(first_line) <= 80:
                title = first_line or title
                remaining_lines = remaining_lines[1:]
        preview = " ".join(" ".join(line.split()) for line in remaining_lines if line.strip()).strip()
        if preview:
            description = preview[:180]
            if len(preview) > 180:
                description = description.rstrip() + "..."
        body = "\n".join(lines).strip()
        scene_metadata = extract_scene_metadata(body, description=description or None)
        scenes.append(
            {
                "chapter_number": chapter_number,
                "title": title,
                "description": description or None,
                "body": body,
                "html_body": manuscript_text_to_html(body),
                "metadata": scene_metadata,
                "status": "assigned" if chapter_number else "unassigned",
                "sort_order": index,
                "source": source,
                "origin_chapter_number": chapter_number,
                "path": build_novel_scene_path(chapter_number=chapter_number, sort_order=index, title=title),
            }
        )
    return scenes


def normalize_scene_reorder_ids(scene_ids: list[str]) -> list[uuid.UUID]:
    normalized_ids: list[uuid.UUID] = []
    seen_ids: set[uuid.UUID] = set()

    for raw_scene_id in scene_ids:
        cleaned_scene_id = " ".join(str(raw_scene_id or "").split()).strip()
        if not cleaned_scene_id:
            raise HTTPException(400, "Scene order contains an empty scene ID.")
        try:
            parsed_scene_id = uuid.UUID(cleaned_scene_id)
        except ValueError as exc:
            raise HTTPException(400, f"Invalid scene ID: {cleaned_scene_id}") from exc
        if parsed_scene_id in seen_ids:
            raise HTTPException(400, "Scene order contains duplicate scene IDs.")
        seen_ids.add(parsed_scene_id)
        normalized_ids.append(parsed_scene_id)

    return normalized_ids


def _apply_sequential_scene_sort_order(scenes: Sequence[NovelScene]) -> None:
    for index, scene in enumerate(scenes, start=1):
        scene.sort_order = index


async def _list_chapter_novel_scene_rows(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    exclude_scene_id: uuid.UUID | None = None,
    lock: bool = False,
) -> list[NovelScene]:
    stmt = (
        select(NovelScene)
        .where(
            NovelScene.book_id == book_id,
            NovelScene.chapter_number == chapter_number,
        )
        .order_by(
            NovelScene.sort_order.asc(),
            NovelScene.created_at.asc(),
            NovelScene.id.asc(),
        )
    )
    if exclude_scene_id is not None:
        stmt = stmt.where(NovelScene.id != exclude_scene_id)
    if lock:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalars().all()


async def normalize_chapter_novel_scene_order(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    exclude_scene_id: uuid.UUID | None = None,
    lock: bool = False,
) -> list[NovelScene]:
    scenes = await _list_chapter_novel_scene_rows(
        db,
        book_id=book_id,
        chapter_number=chapter_number,
        exclude_scene_id=exclude_scene_id,
        lock=lock,
    )
    _apply_sequential_scene_sort_order(scenes)
    return scenes


async def _increment_chapter_structure_versions(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_numbers: Sequence[int | None],
) -> dict[int, int]:
    normalized_numbers = sorted({
        int(chapter_number)
        for chapter_number in chapter_numbers
        if isinstance(chapter_number, int) and chapter_number > 0
    })
    if not normalized_numbers:
        return {}

    chapters = (
        await db.execute(
            select(Chapter)
            .where(
                Chapter.book_id == book_id,
                Chapter.number.in_(normalized_numbers),
            )
        )
    ).scalars().all()

    versions_by_number: dict[int, int] = {}
    for chapter in chapters:
        chapter.structure_version = int(chapter.structure_version or 0) + 1
        versions_by_number[int(chapter.number)] = int(chapter.structure_version)
    return versions_by_number


async def replace_chapter_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
    scenes: list[dict[str, Any]],
) -> None:
    await db.execute(
        delete(NovelScene).where(
            NovelScene.book_id == book.id,
            NovelScene.chapter_number == chapter_number,
        )
    )

    chapter, _chapter_created = await _ensure_syncable_chapter(
        db,
        book=book,
        chapter_number=chapter_number,
    )
    chapter_id = chapter.id
    for scene in scenes:
        db.add(
            NovelScene(
                book_id=book.id,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                title=str(scene["title"]),
                description=cast(str | None, scene.get("description")),
                body=str(scene["body"]),
                html_body=cast(str | None, scene.get("html_body")),
                scene_metadata=cast(dict | None, scene.get("metadata")) or {},
                path=str(scene["path"]),
                status=str(scene.get("status") or "assigned"),
                sort_order=int(scene.get("sort_order") or 0),
                source=str(scene.get("source") or "chapter_sync"),
                origin_chapter_number=chapter_number,
            )
        )
    await _increment_chapter_structure_versions(
        db,
        book_id=book.id,
        chapter_numbers=[chapter_number],
    )


def _scene_out(scene: NovelScene, *, tags: list[str] | None = None) -> dict[str, Any]:
    metadata = normalize_scene_metadata(cast(dict[str, Any] | None, scene.scene_metadata), description=scene.description)
    if tags:
        existing_tags = metadata.get("tags")
        if isinstance(existing_tags, list):
            metadata["tags"] = [*existing_tags, *[tag for tag in tags if tag not in existing_tags]]
        else:
            metadata["tags"] = tags
    return {
        "id": str(scene.id),
        "book_id": str(scene.book_id),
        "chapter_id": str(scene.chapter_id) if scene.chapter_id else None,
        "chapter_number": scene.chapter_number,
        "title": scene.title,
        "description": scene.description,
        "body": scene.body,
        "html_body": scene.html_body,
        "metadata": metadata,
        "path": scene.path,
        "status": scene.status,
        "sort_order": scene.sort_order,
        "source": scene.source,
        "origin_chapter_number": scene.origin_chapter_number,
        "tags": tags or [],
        "created_at": scene.created_at,
        "updated_at": scene.updated_at,
    }


def _scene_version_out(version: SceneVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "scene_id": str(version.scene_id) if version.scene_id else None,
        "chapter_number": version.chapter_number,
        "scene_title": version.scene_title,
        "scene_path": version.scene_path,
        "word_count": version.word_count,
        "note": version.note,
        "snapshot_kind": version.snapshot_kind,
        "created_at": version.created_at,
    }


def _chapter_storage_key(book_id: uuid.UUID, chapter_number: int) -> str:
    return f"chapters/{book_id}/{chapter_number}.txt"


async def _ensure_syncable_chapter(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
) -> tuple[Chapter, bool]:
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    if chapter is not None:
        if not chapter.s3_key:
            chapter.s3_key = _chapter_storage_key(book.id, chapter_number)
        if not chapter.title:
            chapter.title = f"Chapter {chapter_number}"
        await db.flush()
        return chapter, False

    chapter = Chapter(
        book_id=book.id,
        number=chapter_number,
        title=f"Chapter {chapter_number}",
        s3_key=_chapter_storage_key(book.id, chapter_number),
        content_version=1,
        word_count=0,
        processed=False,
    )
    db.add(chapter)
    await db.flush()
    return chapter, True


async def sync_chapter_content_from_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
    increment_content_version: bool = True,
) -> dict[str, Any]:
    from app.utils.advisor_utils import invalidate_advisor_caches_for_book

    chapter, chapter_created = await _ensure_syncable_chapter(
        db,
        book=book,
        chapter_number=chapter_number,
    )
    chapter_scenes = (
        await db.execute(
            select(NovelScene)
            .where(
                NovelScene.book_id == book.id,
                NovelScene.chapter_number == chapter_number,
                NovelScene.status != "archived",
            )
            .order_by(
                NovelScene.sort_order.asc(),
                NovelScene.created_at.asc(),
                NovelScene.id.asc(),
            )
        )
    ).scalars().all()
    next_text = build_workspace_chapter_text_from_scenes(list(chapter_scenes))
    next_html = clean_manuscript_html(manuscript_text_to_html(next_text)) if next_text else None
    previous_payload = {"text": "", "html": None}
    if chapter.s3_key:
        try:
            previous_payload = deserialize_manuscript_content(await asyncio.to_thread(download_book, chapter.s3_key))
        except Exception:
            previous_payload = {"text": "", "html": None}
    stored_key = await asyncio.to_thread(
        upload_text,
        chapter.s3_key or _chapter_storage_key(book.id, chapter_number),
        serialize_manuscript_content(next_text, next_html),
    )
    chapter.s3_key = stored_key
    chapter.word_count = _count_words(strip_scene_metadata_from_manuscript_text(next_text))
    previous_text = str(previous_payload.get("text") or "")
    previous_html = clean_manuscript_html(cast(str | None, previous_payload.get("html"))) if previous_payload.get("html") else None
    if (
        increment_content_version
        and not chapter_created
        and (
            previous_text != next_text
            or previous_html != next_html
        )
    ):
        chapter.content_version = int(chapter.content_version or 1) + 1
    if not chapter.title:
        chapter.title = f"Chapter {chapter_number}"
    content_changed = chapter_created or previous_text != next_text or previous_html != next_html
    if content_changed:
        touch_public_book_updated_at(book)
    await db.flush()
    if content_changed:
        await invalidate_advisor_caches_for_book(db, book_id=book.id)
    return {
        "chapter": chapter,
        "text": next_text,
        "html": next_html,
    }


async def list_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: BookCollaborator | None = None,
    chapter_number: int | None = None,
    status: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    stmt = select(NovelScene).where(NovelScene.book_id == book.id)
    if chapter_number is not None:
        stmt = stmt.where(NovelScene.chapter_number == chapter_number)
    if status:
        stmt = stmt.where(NovelScene.status == status)
    if query:
        like = f"%{' '.join(query.split()).strip()}%"
        stmt = stmt.where(
            NovelScene.title.ilike(like) | NovelScene.description.ilike(like) | NovelScene.body.ilike(like)
        )
    rows = list((
        await db.execute(
            stmt.order_by(
                NovelScene.chapter_number.is_(None),
                NovelScene.chapter_number.asc(),
                NovelScene.sort_order.asc(),
                NovelScene.created_at.asc(),
            )
        )
    ).scalars().all())
    tags_by_scene = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_SCENE,
        entity_ids=[scene.id for scene in rows],
        book_id=book.id,
    )
    scenes = [_scene_out(scene, tags=tags_by_scene.get(scene.id, [])) for scene in rows]
    if collaborator is None:
        return scenes
    return [
        scene
        for scene in scenes
        if scene["chapter_number"] is not None and collaboration_allows_chapter(collaborator, int(scene["chapter_number"]))
    ]


async def save_novel_scene(
    db: AsyncSession,
    *,
    book: Book,
    scene_id: uuid.UUID | None,
    title: str,
    description: str | None,
    body: str,
    html_body: str | None,
    chapter_number: int | None,
    status: str | None,
    sort_order: int | None,
    metadata: dict[str, Any] | None = None,
    path: str | None = None,
    skip_scene_version_snapshot: bool = False,
) -> dict[str, Any]:
    normalized_title = _clean_text(title)
    if not normalized_title:
        raise HTTPException(400, "Scene title is required")
    normalized_body = (body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized_body:
        raise HTTPException(400, "Scene body is required")
    normalized_description = _clean_optional_text(description)
    normalized_metadata = normalize_scene_metadata(metadata, description=normalized_description)
    inferred_metadata = extract_scene_metadata(normalized_body, description=normalized_description)
    normalized_metadata = {**inferred_metadata, **normalized_metadata}
    normalized_chapter_number = int(chapter_number) if isinstance(chapter_number, int) and chapter_number > 0 else None
    normalized_status = "assigned" if normalized_chapter_number else "unassigned"
    if status in {"assigned", "unassigned", "archived"}:
        normalized_status = status
    chapter_id = None
    if normalized_chapter_number:
        chapter_id = (
            await db.execute(
                select(Chapter.id).where(Chapter.book_id == book.id, Chapter.number == normalized_chapter_number)
            )
        ).scalar_one_or_none()
        if chapter_id is None:
            chapter, _chapter_created = await _ensure_syncable_chapter(
                db,
                book=book,
                chapter_number=normalized_chapter_number,
            )
            chapter_id = chapter.id

    scene = await db.get(NovelScene, scene_id) if scene_id else None
    if scene is not None and scene.book_id != book.id:
        raise HTTPException(404, "Scene not found")
    if (
        scene is not None
        and not skip_scene_version_snapshot
        and (
            scene.title != normalized_title
            or (scene.description or None) != normalized_description
            or scene.body != normalized_body
            or scene.chapter_number != normalized_chapter_number
        )
    ):
        await snapshot_scene_version(
            db,
            book,
            scene,
            note=f"Auto checkpoint before editing scene: {scene.title}",
            snapshot_kind="auto_checkpoint",
        )
    previous_body = scene.body if scene is not None else ""
    previous_title = scene.title if scene is not None else None
    previous_chapter_number = scene.chapter_number if scene is not None else None
    previous_sort_order = scene.sort_order if scene is not None else None
    snapshot_version_id: str | None = None
    snapshot_chapter_number = normalized_chapter_number or previous_chapter_number
    if isinstance(snapshot_chapter_number, int) and snapshot_chapter_number > 0:
        snapshot_chapter = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id, Chapter.number == snapshot_chapter_number)
            )
        ).scalar_one_or_none()
        if snapshot_chapter is not None:
            snapshot = await snapshot_chapter_version(
                db,
                book,
                snapshot_chapter,
                note=f"Scene workspace snapshot for Chapter {snapshot_chapter_number}",
                snapshot_kind="scene_workspace",
            )
            snapshot_version_id = str(snapshot.id) if snapshot is not None else None

    initial_sort_order = int(sort_order) if isinstance(sort_order, int) and sort_order > 0 else 1
    base_path = normalize_vault_note_path(path) if path else build_novel_scene_path(
        chapter_number=normalized_chapter_number if normalized_status == "assigned" else None,
        sort_order=initial_sort_order,
        title=normalized_title,
    )
    path = base_path
    suffix = 2
    while True:
        existing_path_scene = (
            await db.execute(
                select(NovelScene.id).where(
                    NovelScene.book_id == book.id,
                    NovelScene.path == path,
                )
            )
        ).scalar_one_or_none()
        if existing_path_scene is None or (scene is not None and existing_path_scene == scene.id):
            break
        if base_path.endswith(".md"):
            path = f"{base_path[:-3]}-{suffix}.md"
        else:
            path = f"{base_path}-{suffix}"
        suffix += 1
    if scene is None:
        scene = NovelScene(
            book_id=book.id,
            chapter_id=chapter_id,
            chapter_number=normalized_chapter_number,
            title=normalized_title,
            description=normalized_description,
            body=normalized_body,
            html_body=clean_manuscript_html(html_body) if html_body else manuscript_text_to_html(normalized_body),
            scene_metadata=normalized_metadata,
            path=path,
            status=normalized_status,
            sort_order=initial_sort_order,
            source="manual",
            origin_chapter_number=normalized_chapter_number,
        )
        db.add(scene)
        await db.flush()
    else:
        scene.chapter_id = chapter_id
        scene.chapter_number = normalized_chapter_number
        scene.title = normalized_title
        scene.description = normalized_description
        scene.body = normalized_body
        scene.html_body = clean_manuscript_html(html_body) if html_body else manuscript_text_to_html(normalized_body)
        scene.scene_metadata = normalized_metadata
        scene.path = path
        scene.status = normalized_status
        scene.sort_order = initial_sort_order if normalized_chapter_number is not None else 1
        await db.flush()

    touched_chapters: list[int | None] = []
    structure_changed = False
    requested_sort_order = int(sort_order) if isinstance(sort_order, int) and sort_order > 0 else None

    if normalized_chapter_number is not None:
        if scene_id is None or previous_chapter_number != normalized_chapter_number:
            requested_sort_order = None
        elif requested_sort_order is None and previous_sort_order is not None:
            requested_sort_order = previous_sort_order
        chapter_scenes = await _list_chapter_novel_scene_rows(
            db,
            book_id=book.id,
            chapter_number=normalized_chapter_number,
            exclude_scene_id=scene.id,
        )
        insert_position = requested_sort_order if requested_sort_order is not None else len(chapter_scenes) + 1
        insert_position = max(1, min(insert_position, len(chapter_scenes) + 1))
        chapter_scenes.insert(insert_position - 1, scene)
        _apply_sequential_scene_sort_order(chapter_scenes)
        touched_chapters.append(normalized_chapter_number)
        structure_changed = (
            scene_id is None
            or previous_chapter_number != normalized_chapter_number
            or (requested_sort_order is not None and requested_sort_order != previous_sort_order)
        )
    else:
        scene.sort_order = 1

    if previous_chapter_number is not None and previous_chapter_number != normalized_chapter_number:
        await normalize_chapter_novel_scene_order(
            db,
            book_id=book.id,
            chapter_number=previous_chapter_number,
        )
        touched_chapters.append(previous_chapter_number)
        structure_changed = True

    if structure_changed:
        await _increment_chapter_structure_versions(
            db,
            book_id=book.id,
            chapter_numbers=touched_chapters,
        )

    if scene_id is None:
        _append_recent_revision_edit(
            book,
            kind="scene",
            chapter_number=normalized_chapter_number,
            before_text="",
            after_text=normalized_body,
            scene_id=str(scene.id) if getattr(scene, "id", None) else None,
            scene_title=normalized_title,
            source_version_id=snapshot_version_id,
        )
    elif previous_body != normalized_body or previous_title != normalized_title or previous_chapter_number != normalized_chapter_number:
        _append_recent_revision_edit(
            book,
            kind="scene",
            chapter_number=normalized_chapter_number or previous_chapter_number,
            before_text=previous_body,
            after_text=normalized_body,
            scene_id=str(scene.id),
            scene_title=normalized_title,
            source_version_id=snapshot_version_id,
        )
    synced_chapters = sorted({
        int(chapter_number)
        for chapter_number in [previous_chapter_number, normalized_chapter_number]
        if isinstance(chapter_number, int) and chapter_number > 0
    })
    for synced_chapter_number in synced_chapters:
        await sync_chapter_content_from_novel_scenes(
            db,
            book=book,
            chapter_number=synced_chapter_number,
        )
    await db.commit()
    await db.refresh(scene)

    if not getattr(book, "is_editor_project", False):
        from app.workers.tasks.extraction_tasks import process_chapter_task

        for synced_chapter_number in synced_chapters:
            process_chapter_task.apply_async(
                kwargs={"book_id": str(book.id), "chapter_num": synced_chapter_number},
                queue="extraction",
                countdown=31,
            )

    return _scene_out(
        scene,
        tags=await get_custom_tags_for_entity(
            db,
            entity_type=ENTITY_TYPE_SCENE,
            entity_id=scene.id,
            book_id=book.id,
        ),
    )


async def delete_novel_scene(
    db: AsyncSession,
    *,
    book: Book,
    scene_id: uuid.UUID,
) -> None:
    scene = (
        await db.execute(select(NovelScene).where(NovelScene.book_id == book.id, NovelScene.id == scene_id))
    ).scalar_one_or_none()
    if scene is None:
        raise HTTPException(404, "Scene not found")
    await snapshot_scene_version(
        db,
        book,
        scene,
        note=f"Auto checkpoint before deleting scene: {scene.title}",
        snapshot_kind="pre_delete",
    )
    snapshot_version_id: str | None = None
    if isinstance(scene.chapter_number, int) and scene.chapter_number > 0:
        chapter = (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book.id, Chapter.number == scene.chapter_number)
            )
        ).scalar_one_or_none()
        if chapter is not None:
            snapshot = await snapshot_chapter_version(
                db,
                book,
                chapter,
                note=f"Scene delete snapshot for Chapter {scene.chapter_number}",
                snapshot_kind="scene_workspace",
            )
            snapshot_version_id = str(snapshot.id) if snapshot is not None else None
    _append_recent_revision_edit(
        book,
        kind="scene_deleted",
        chapter_number=scene.chapter_number,
        before_text=scene.body,
        after_text="",
        scene_id=str(scene.id),
        scene_title=scene.title,
        source_version_id=snapshot_version_id,
    )
    removed_chapter_number = scene.chapter_number
    await db.delete(scene)
    if isinstance(removed_chapter_number, int) and removed_chapter_number > 0:
        await normalize_chapter_novel_scene_order(
            db,
            book_id=book.id,
            chapter_number=removed_chapter_number,
        )
        await _increment_chapter_structure_versions(
            db,
            book_id=book.id,
            chapter_numbers=[removed_chapter_number],
        )
        await sync_chapter_content_from_novel_scenes(
            db,
            book=book,
            chapter_number=removed_chapter_number,
        )
    await db.commit()

    if isinstance(removed_chapter_number, int) and removed_chapter_number > 0:
        if not getattr(book, "is_editor_project", False):
            from app.workers.tasks.extraction_tasks import process_chapter_task

            process_chapter_task.apply_async(
                kwargs={"book_id": str(book.id), "chapter_num": removed_chapter_number},
                queue="extraction",
                countdown=31,
            )


async def reorder_chapter_novel_scenes(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
    scene_ids: list[str],
    expected_structure_version: int,
) -> dict[str, Any]:
    normalized_scene_ids = normalize_scene_reorder_ids(scene_ids)
    chapter = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.number == chapter_number)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")
    if int(chapter.structure_version or 0) != expected_structure_version:
        raise HTTPException(409, "Scene order changed elsewhere. Please refresh.")

    chapter_scenes = await _list_chapter_novel_scene_rows(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        lock=True,
    )
    chapter_scene_ids = [scene.id for scene in chapter_scenes]
    if len(normalized_scene_ids) != len(chapter_scene_ids):
        raise HTTPException(400, "Scene order must include every scene in the chapter.")
    if set(normalized_scene_ids) != set(chapter_scene_ids):
        raise HTTPException(400, "Scene order does not match the chapter scene set.")

    previous_order = [str(scene.id) for scene in chapter_scenes]
    scenes_by_id = {scene.id: scene for scene in chapter_scenes}
    reordered_scenes = [scenes_by_id[scene_id] for scene_id in normalized_scene_ids]
    _apply_sequential_scene_sort_order(reordered_scenes)
    for scene in reordered_scenes:
        scene.chapter_id = chapter.id
        scene.chapter_number = chapter.number
        scene.status = "assigned"

    await _increment_chapter_structure_versions(
        db,
        book_id=book.id,
        chapter_numbers=[chapter_number],
    )
    _append_recent_revision_edit(
        book,
        kind="scene_reordered",
        chapter_number=chapter_number,
        before_text="\n".join(previous_order),
        after_text="\n".join(str(scene.id) for scene in reordered_scenes),
    )
    await sync_chapter_content_from_novel_scenes(
        db,
        book=book,
        chapter_number=chapter_number,
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    if not getattr(book, "is_editor_project", False):
        from app.workers.tasks.extraction_tasks import process_chapter_task

        process_chapter_task.apply_async(
            kwargs={"book_id": str(book.id), "chapter_num": chapter_number},
            queue="extraction",
            countdown=31,
        )

    return {
        "chapter_number": chapter_number,
        "structure_version": int(chapter.structure_version or 0),
        "scenes": [
            {
                "id": str(scene.id),
                "title": scene.title,
                "sort_order": scene.sort_order,
            }
            for scene in reordered_scenes
        ],
    }


async def build_manuscript_workspace_tree(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
) -> dict[str, Any]:
    workspace = build_writer_workspace_payload(book)
    chapter_rows = list((
        await db.execute(
            select(Chapter.id, Chapter.number, Chapter.title, Chapter.structure_version)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).all())
    scenes = list((
        await db.execute(
            select(NovelScene).where(NovelScene.book_id == book.id).order_by(
                NovelScene.chapter_number.is_(None),
                NovelScene.chapter_number.asc(),
                NovelScene.sort_order.asc(),
                NovelScene.created_at.asc(),
            )
        )
    ).scalars().all())
    if collaborator is not None:
        chapter_rows = [
            (chapter_id, number, chapter_title, structure_version)
            for chapter_id, number, chapter_title, structure_version in chapter_rows
            if collaboration_allows_chapter(collaborator, int(number))
        ]
        scenes = [
            scene
            for scene in scenes
            if scene.chapter_number is not None and collaboration_allows_chapter(collaborator, int(scene.chapter_number))
        ]
    note_paths = [
        note["path"]
        for note in await list_vault_notes(
            db,
            book=book,
            user_id=user_id,
            source=VaultNoteSource.USER_NOTES.value,
        )
    ]
    tags_by_chapter = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_CHAPTER,
        entity_ids=[chapter_id for chapter_id, _number, _chapter_title, _structure_version in chapter_rows],
        book_id=book.id,
    )
    tags_by_scene = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_SCENE,
        entity_ids=[scene.id for scene in scenes],
        book_id=book.id,
    )
    scene_counts: dict[int, int] = {}
    grouped_scenes: dict[int | None, list[dict[str, Any]]] = {}
    for scene in scenes:
        grouped_scenes.setdefault(scene.chapter_number, []).append(_scene_out(scene, tags=tags_by_scene.get(scene.id, [])))
        if scene.chapter_number:
            scene_counts[scene.chapter_number] = scene_counts.get(scene.chapter_number, 0) + 1

    scene_groups: list[dict[str, Any]] = []
    if grouped_scenes.get(None):
        scene_groups.append(
            {
                "id": "unassigned-scenes",
                "label": "Unassigned Scenes",
                "chapter_number": None,
                "collapsed_by_default": True,
                "scenes": grouped_scenes[None],
            }
        )
    for chapter_id, chapter_number, chapter_title, structure_version in chapter_rows:
        scene_groups.append(
            {
                "id": f"chapter-scenes-{chapter_number}",
                "label": f"Chapter {chapter_number}: {chapter_title or f'Chapter {chapter_number}'}",
                "chapter_number": int(chapter_number),
                "structure_version": int(structure_version or 0),
                "collapsed_by_default": False,
                "scenes": grouped_scenes.get(int(chapter_number), []),
            }
        )

    chapter_title_by_number = {int(number): chapter_title for _chapter_id, number, chapter_title, _structure_version in chapter_rows}
    scene_breadcrumbs = {
        str(scene.id): [
            {"id": f"book-{book.id}", "label": book.title, "kind": "book"},
            {"id": f"chapter-{scene.chapter_number}", "label": f"Chapter {scene.chapter_number}: {chapter_title_by_number.get(int(scene.chapter_number or 0)) or f'Chapter {scene.chapter_number}'}", "kind": "chapter"},
            {"id": str(scene.id), "label": scene.title, "kind": "scene"},
        ]
        for scene in scenes
        if scene.chapter_number
    }

    configured_structure = workspace.get("structure_tree")
    if isinstance(configured_structure, list) and configured_structure:
        structure_tree = (
            _filter_workspace_structure_tree_for_collaborator(configured_structure, collaborator)
            if collaborator is not None
            else configured_structure
        )
    else:
        structure_tree = [{
            "id": f"book-{book.id}",
            "label": book.title,
            "kind": "book",
            "children": [
                {
                    "id": f"chapter-{int(number)}",
                    "label": chapter_title or f"Chapter {int(number)}",
                    "kind": "chapter",
                    "chapter_number": int(number),
                    "children": [
                        {
                            "id": str(scene.id),
                            "label": scene.title,
                            "kind": "scene",
                            "chapter_number": int(number),
                            "scene_id": str(scene.id),
                            "children": [],
                        }
                        for scene in scenes
                        if scene.chapter_number == int(number)
                    ],
                }
                for _chapter_id, number, chapter_title, _structure_version in chapter_rows
            ],
        }]

    return {
        "chapters": [
            {
                "chapter_number": int(number),
                "title": chapter_title,
                "scene_count": scene_counts.get(int(number), 0),
                "structure_version": int(structure_version or 0),
                "tags": tags_by_chapter.get(chapter_id, []),
            }
            for chapter_id, number, chapter_title, structure_version in chapter_rows
        ],
        "scene_groups": scene_groups,
        "note_paths": note_paths,
        "structure_tree": structure_tree,
        "scene_breadcrumbs": scene_breadcrumbs,
    }


def _filter_workspace_structure_tree_for_collaborator(
    nodes: list[dict[str, Any]],
    collaborator: BookCollaborator,
) -> list[dict[str, Any]]:
    filtered_nodes: list[dict[str, Any]] = []
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        node = dict(raw_node)
        chapter_number = node.get("chapter_number")
        if isinstance(chapter_number, int) and chapter_number > 0 and not collaboration_allows_chapter(collaborator, chapter_number):
            continue
        children = node.get("children")
        if isinstance(children, list):
            node["children"] = _filter_workspace_structure_tree_for_collaborator(children, collaborator)
        filtered_nodes.append(node)
    return filtered_nodes


def _compile_workspace_search_pattern(search_query: str, *, flags: int) -> re.Pattern[str]:
    if len(search_query) > settings.WORKSPACE_REGEX_MAX_PATTERN_LENGTH:
        raise HTTPException(400, "Search pattern is too long.")
    if re.search(r"\([^)]*[+*][^)]*\)[+*{]", search_query):
        raise HTTPException(400, "Search pattern contains unsafe nested repetition.")
    try:
        return re.compile(search_query, flags)
    except re.error as exc:
        raise HTTPException(400, f"Invalid search pattern: {exc}") from exc


def _workspace_excerpt(text: str, query: str, *, radius: int = 90) -> str:
    normalized_text = " ".join((text or "").split()).strip()
    if not normalized_text:
        return ""
    if not query:
        return normalized_text[:radius * 2]
    index = normalized_text.lower().find(query.lower())
    if index < 0:
        return normalized_text[:radius * 2]
    start = max(0, index - radius)
    end = min(len(normalized_text), index + len(query) + radius)
    excerpt = normalized_text[start:end]
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(normalized_text):
        excerpt = f"{excerpt}..."
    return excerpt


async def search_author_workspace(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    query: str,
    scopes: list[str],
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
    filters: dict[str, Any] | None = None,
    collaborator: BookCollaborator | None = None,
) -> list[dict[str, Any]]:
    search_query = " ".join((query or "").split()).strip()
    normalized_scopes = {scope for scope in scopes if scope in {"manuscript", "scenes", "notes"}} or {"manuscript", "scenes", "notes"}
    filter_payload = filters if isinstance(filters, dict) else {}
    chapter_filter = filter_payload.get("chapter_number")
    scene_id_filter = " ".join(str(filter_payload.get("scene_id") or "").split()).strip() or None
    pov_filter = " ".join(str(filter_payload.get("pov") or "").split()).strip().lower() or None
    location_filter = " ".join(str(filter_payload.get("location") or "").split()).strip().lower() or None
    tag_filters = {
        " ".join(str(tag or "").split()).strip().lower()
        for tag in (filter_payload.get("tags") or [])
        if " ".join(str(tag or "").split()).strip()
    }

    flags = 0 if case_sensitive else re.IGNORECASE
    pattern: re.Pattern[str] | None = None
    if regex and search_query:
        pattern = _compile_workspace_search_pattern(search_query, flags=flags)
    elif search_query and whole_word:
        pattern = re.compile(rf"\b{re.escape(search_query)}\b", flags)

    def _matches(value: str) -> bool:
        haystack = value or ""
        if not search_query:
            return True
        if pattern is not None:
            return bool(pattern.search(haystack))
        if case_sensitive:
            return search_query in haystack
        return search_query.lower() in haystack.lower()

    results: list[dict[str, Any]] = []

    if "scenes" in normalized_scopes:
        scene_rows = await list_novel_scenes(
            db,
            book=book,
            collaborator=collaborator,
            chapter_number=int(chapter_filter) if isinstance(chapter_filter, int) and chapter_filter > 0 else None,
            query=None,
        )
        for scene in scene_rows:
            metadata = scene.get("metadata") if isinstance(scene.get("metadata"), dict) else {}
            if scene_id_filter and str(scene.get("id")) != scene_id_filter:
                continue
            if pov_filter and str(metadata.get("pov") or "").strip().lower() != pov_filter:
                continue
            if location_filter and str(metadata.get("location") or "").strip().lower() != location_filter:
                continue
            scene_tags = {
                " ".join(str(tag or "").split()).strip().lower()
                for tag in (metadata.get("tags") or scene.get("tags") or [])
                if " ".join(str(tag or "").split()).strip()
            }
            if tag_filters and not tag_filters.issubset(scene_tags):
                continue
            searchable = "\n".join([str(scene.get("title") or ""), str(scene.get("description") or ""), str(scene.get("body") or "")])
            if not _matches(searchable):
                continue
            results.append({
                "scope": "scenes",
                "id": str(scene["id"]),
                "title": str(scene.get("title") or "Scene"),
                "excerpt": _workspace_excerpt(str(scene.get("body") or scene.get("description") or ""), search_query),
                "chapter_number": scene.get("chapter_number"),
                "scene_id": str(scene["id"]),
                "note_path": None,
                "rank": 3,
            })

    if "notes" in normalized_scopes and collaborator is None:
        notes = await list_vault_notes(
            db,
            book=book,
            user_id=user_id,
            source=VaultNoteSource.USER_NOTES.value,
        )
        for note in notes:
            path = str(note.get("path") or "")
            content = str(note.get("content") or "")
            if not _matches(f"{path}\n{content}"):
                continue
            results.append({
                "scope": "notes",
                "id": path,
                "title": vault_note_title(path),
                "excerpt": _workspace_excerpt(content, search_query),
                "chapter_number": None,
                "scene_id": None,
                "note_path": path,
                "rank": 2,
            })

    if "manuscript" in normalized_scopes:
        chapter_stmt = select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
        if isinstance(chapter_filter, int) and chapter_filter > 0:
            chapter_stmt = chapter_stmt.where(Chapter.number == int(chapter_filter))
        chapter_rows = list((await db.execute(chapter_stmt)).scalars().all())
        for chapter in chapter_rows:
            if collaborator is not None and not collaboration_allows_chapter(collaborator, int(chapter.number)):
                continue
            if not chapter.s3_key:
                continue
            try:
                stored = deserialize_manuscript_content(await asyncio.to_thread(download_book, chapter.s3_key))
            except Exception:
                continue
            text = str(stored.get("text") or "")
            title = chapter.title or f"Chapter {chapter.number}"
            if not _matches(f"{title}\n{text}"):
                continue
            results.append({
                "scope": "manuscript",
                "id": f"chapter-{chapter.number}",
                "title": title,
                "excerpt": _workspace_excerpt(text, search_query),
                "chapter_number": chapter.number,
                "scene_id": None,
                "note_path": None,
                "rank": 1,
            })

    results.sort(key=lambda item: (-float(item.get("rank") or 0), int(item.get("chapter_number") or 0), str(item.get("title") or "").lower()))
    return results


def _series_bible_key(value: str | None) -> str:
    return " ".join((value or "").split()).strip().lower()


async def build_series_bible_payload(
    db: AsyncSession,
    *,
    series: Series,
) -> SeriesBibleOut:
    membership_rows = (
        await db.execute(
            select(SeriesBook, Book)
            .join(Book, Book.id == SeriesBook.book_id)
            .where(SeriesBook.series_id == series.id, Book.hidden_at.is_(None))
            .order_by(SeriesBook.position.asc().nullslast(), Book.created_at.asc(), Book.title.asc())
        )
    ).all()

    if not membership_rows:
        return SeriesBibleOut(
            series_id=str(series.id),
            name=series.name,
            description=series.description,
            work_type="screenplay",
            episode_count=0,
            episodes=[],
            recurring_characters=[],
            recurring_relationships=[],
            unresolved_plot_threads=[],
            canon_entries=[],
            continuity_risks=[],
        )

    screenplay_rows = [(membership, book) for membership, book in membership_rows if book.work_type == "screenplay"]
    active_rows = screenplay_rows or membership_rows
    series_work_type = "screenplay" if screenplay_rows else (active_rows[0][1].work_type if active_rows else "novel")
    book_ids = [book.id for _, book in active_rows]

    scene_stats_rows = (
        await db.execute(
            select(Scene.book_id, func.count(Scene.id), func.coalesce(func.sum(Scene.word_count), 0))
            .where(Scene.book_id.in_(book_ids))
            .group_by(Scene.book_id)
        )
    ).all() if book_ids else []
    dialogue_stats_rows = (
        await db.execute(
            select(Scene.book_id, func.count(Dialogue.id))
            .join(Dialogue, Dialogue.scene_id == Scene.id)
            .where(Scene.book_id.in_(book_ids))
            .group_by(Scene.book_id)
        )
    ).all() if book_ids else []
    scene_stats_by_book = {
        book_id: {"total_scenes": int(total_scenes or 0), "total_words": int(total_words or 0)}
        for book_id, total_scenes, total_words in scene_stats_rows
    }
    dialogue_stats_by_book = {book_id: int(total_dialogue or 0) for book_id, total_dialogue in dialogue_stats_rows}

    episodes: list[SeriesBibleEpisodeOut] = []
    episode_lookup: dict[uuid.UUID, SeriesBibleEpisodeOut] = {}
    for membership, book in active_rows:
        scene_stats = scene_stats_by_book.get(book.id, {})
        episode = SeriesBibleEpisodeOut(
            book_id=str(book.id),
            title=book.title,
            episode_number=membership.position,
            format=book.format,
            work_type=book.work_type,
            total_scenes=int(scene_stats.get("total_scenes", book.total_chapters or 0) or 0),
            total_dialogue_lines=dialogue_stats_by_book.get(book.id, 0),
            total_words=int(scene_stats.get("total_words", 0) or 0),
            status=book.status,
        )
        episodes.append(episode)
        episode_lookup[book.id] = episode

    characters = (
        await db.execute(
            select(Character)
            .where(Character.book_id.in_(book_ids))
            .order_by(Character.book_id, Character.first_chapter, Character.name)
        )
    ).scalars().all() if book_ids else []
    relationships = (
        await db.execute(select(CharacterRelationship).where(CharacterRelationship.book_id.in_(book_ids)))
    ).scalars().all() if book_ids else []
    plot_threads = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id.in_(book_ids))
            .order_by(PlotThread.importance.desc(), PlotThread.title)
        )
    ).scalars().all() if book_ids else []
    wiki_entries = (
        await db.execute(
            select(WikiEntry)
            .where(WikiEntry.book_id.in_(book_ids))
            .order_by(WikiEntry.entry_type, WikiEntry.name)
        )
    ).scalars().all() if book_ids else []

    character_groups: dict[str, dict[str, Any]] = {}
    for character in characters:
        key = _series_bible_key(character.name)
        if not key:
            continue
        bucket = character_groups.setdefault(
            key,
            {
                "name": character.name,
                "episodes": set(),
                "mentions": 0,
                "first_episode": None,
                "last_episode": None,
            },
        )
        bucket["episodes"].add(character.book_id)
        bucket["mentions"] += int(character.mention_count or 0)
        episode = episode_lookup.get(character.book_id)
        if episode is not None and episode.episode_number is not None:
            if bucket["first_episode"] is None or episode.episode_number < bucket["first_episode"]:
                bucket["first_episode"] = episode.episode_number
            if bucket["last_episode"] is None or episode.episode_number > bucket["last_episode"]:
                bucket["last_episode"] = episode.episode_number

    recurring_characters = sorted(
        (
            SeriesBibleCharacterOut(
                name=bucket["name"],
                normalized_name=key,
                episode_count=len(bucket["episodes"]),
                total_mentions=int(bucket["mentions"]),
                first_episode=bucket["first_episode"],
                last_episode=bucket["last_episode"],
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (episode_lookup[item].episode_number or 10**6, episode_lookup[item].title.lower()),
                    )
                ],
            )
            for key, bucket in character_groups.items()
            if len(bucket["episodes"]) >= 2
        ),
        key=lambda item: (-item.episode_count, -item.total_mentions, item.name.lower()),
    )

    relationship_groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    continuity_risks: list[str] = []
    pair_type_tracker: dict[tuple[str, str], set[str]] = {}
    name_by_book_and_id = {(character.book_id, character.id): character.name for character in characters}
    for relationship in relationships:
        a_name = name_by_book_and_id.get((relationship.book_id, relationship.character_a_id), "Unknown")
        b_name = name_by_book_and_id.get((relationship.book_id, relationship.character_b_id), "Unknown")
        pair: tuple[str, str] = (min(a_name, b_name), max(a_name, b_name))
        relationship_type = " ".join(str(relationship.rel_type or "").split()).strip() or "unknown"
        pair_type_tracker.setdefault(pair, set()).add(relationship_type)
        key = (pair[0].lower(), pair[1].lower(), relationship_type)
        bucket = relationship_groups.setdefault(
            key,
            {
                "characters": [pair[0], pair[1]],
                "relationship_type": relationship_type,
                "episodes": set(),
                "note": relationship.description,
            },
        )
        bucket["episodes"].add(relationship.book_id)
        if not bucket.get("note") and relationship.description:
            bucket["note"] = relationship.description

    recurring_relationships = sorted(
        (
            SeriesBibleRelationshipOut(
                characters=bucket["characters"],
                relationship_type=bucket["relationship_type"],
                episode_count=len(bucket["episodes"]),
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (episode_lookup[item].episode_number or 10**6, episode_lookup[item].title.lower()),
                    )
                ],
                note=bucket.get("note"),
            )
            for bucket in relationship_groups.values()
            if len(bucket["episodes"]) >= 2
        ),
        key=lambda item: (-item.episode_count, item.characters[0].lower(), item.characters[1].lower(), item.relationship_type.lower()),
    )

    for pair, rel_types in pair_type_tracker.items():
        if len(rel_types) > 1:
            continuity_risks.append(
                f"{pair[0]} and {pair[1]} shift relationship labels across episodes: {', '.join(sorted(rel_types))}."
            )

    plot_thread_groups: dict[str, dict[str, Any]] = {}
    for thread in plot_threads:
        key = _series_bible_key(thread.title)
        if not key:
            continue
        bucket = plot_thread_groups.setdefault(
            key,
            {
                "title": thread.title,
                "episodes": set(),
                "statuses": set(),
                "note": thread.note,
            },
        )
        if not is_plot_thread_closed(thread.status):
            bucket["episodes"].add(thread.book_id)
        bucket["statuses"].add(thread.status)
        if not bucket.get("note") and thread.note:
            bucket["note"] = thread.note

    unresolved_plot_threads = sorted(
        (
            SeriesBiblePlotThreadOut(
                title=bucket["title"],
                status="developing" if "developing" in bucket["statuses"] or "ongoing" in bucket["statuses"] else sorted(bucket["statuses"])[0],
                episode_count=len(bucket["episodes"]),
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (episode_lookup[item].episode_number or 10**6, episode_lookup[item].title.lower()),
                    )
                ],
                note=bucket.get("note"),
            )
            for bucket in plot_thread_groups.values()
            if bucket["episodes"]
        ),
        key=lambda item: (-item.episode_count, item.title.lower()),
    )

    canon_groups: dict[tuple[str, str], dict[str, Any]] = {}
    description_tracker: dict[tuple[str, str], set[str]] = {}
    for entry in wiki_entries:
        key = (entry.entry_type, _series_bible_key(entry.name))
        if not key[1]:
            continue
        bucket = canon_groups.setdefault(
            key,
            {
                "name": entry.name,
                "entry_type": entry.entry_type,
                "episodes": set(),
                "description": entry.description,
            },
        )
        bucket["episodes"].add(entry.book_id)
        if not bucket.get("description") and entry.description:
            bucket["description"] = entry.description
        if entry.description:
            description_tracker.setdefault(key, set()).add(" ".join(entry.description.split()))

    canon_entries = sorted(
        (
            SeriesBibleCanonEntryOut(
                name=bucket["name"],
                entry_type=bucket["entry_type"],
                episode_count=len(bucket["episodes"]),
                episodes=[
                    episode_lookup[book_id]
                    for book_id in sorted(
                        bucket["episodes"],
                        key=lambda item: (episode_lookup[item].episode_number or 10**6, episode_lookup[item].title.lower()),
                    )
                ],
                description=bucket.get("description"),
            )
            for bucket in canon_groups.values()
        ),
        key=lambda item: (-item.episode_count, item.entry_type.lower(), item.name.lower()),
    )

    for key, descriptions in description_tracker.items():
        if len(descriptions) > 1:
            continuity_risks.append(
                f"{canon_groups[key]['name']} has differing {canon_groups[key]['entry_type']} descriptions across episodes."
            )

    role_tracker: dict[str, set[str]] = {}
    for character in characters:
        key = _series_bible_key(character.name)
        if not key or not character.role:
            continue
        role_tracker.setdefault(key, set()).add(character.role)
    for key, roles in role_tracker.items():
        if len(roles) > 1:
            display_name = character_groups.get(key, {}).get("name", key.title())
            continuity_risks.append(f"{display_name} shifts role labels across episodes: {', '.join(sorted(roles))}.")

    return SeriesBibleOut(
        series_id=str(series.id),
        name=series.name,
        description=series.description,
        work_type=series_work_type,
        episode_count=len(episodes),
        episodes=episodes,
        recurring_characters=recurring_characters[:12],
        recurring_relationships=recurring_relationships[:12],
        unresolved_plot_threads=unresolved_plot_threads[:12],
        canon_entries=canon_entries[:18],
        continuity_risks=list(dict.fromkeys(continuity_risks))[:12],
    )


# ─── BookOut construction ─────────────────────────────────────────────────────

async def preload_book_render_context(
    db: AsyncSession,
    *,
    books: Sequence[Book],
    user_id: uuid.UUID,
) -> BookRenderContext:
    unique_books = list(dict.fromkeys(books))
    if not unique_books:
        return BookRenderContext(
            progress_by_book_id={},
            total_words_by_book_id={},
            cover_url_by_book_id={},
        )

    for book in unique_books:
        await ensure_book_cover(db, book)

    book_ids = [book.id for book in unique_books]
    progress_rows = (
        await db.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == user_id,
                ReadingProgress.book_id.in_(book_ids),
            )
        )
    ).scalars().all()
    total_word_rows = (
        await db.execute(
            select(Chapter.book_id, func.coalesce(func.sum(Chapter.word_count), 0))
            .where(Chapter.book_id.in_(book_ids))
            .group_by(Chapter.book_id)
        )
    ).all()
    return BookRenderContext(
        progress_by_book_id={progress.book_id: progress for progress in progress_rows},
        total_words_by_book_id={book_id: int(total_words or 0) for book_id, total_words in total_word_rows},
        cover_url_by_book_id={book.id: cover_url_for_book(book) for book in unique_books},
    )


async def build_book_out_list(
    db: AsyncSession,
    *,
    books: Sequence[Book],
    user_id: uuid.UUID,
    collaborators_by_book_id: dict[uuid.UUID, BookCollaborator] | None = None,
) -> list[BookOut]:
    context = await preload_book_render_context(db, books=books, user_id=user_id)
    payloads: list[BookOut] = []
    for book in books:
        payloads.append(
            await book_out(
                db,
                book,
                user_id,
                collaborator=(collaborators_by_book_id or {}).get(book.id),
                context=context,
            )
        )
    return payloads


def _build_series_out_from_grouped_rows(
    *,
    series_rows: Sequence[Series],
    memberships_by_series_id: dict[uuid.UUID, list[tuple[SeriesBook, Book]]],
    book_payloads_by_id: dict[uuid.UUID, BookOut],
) -> list[SeriesOut]:
    output: list[SeriesOut] = []
    for series in series_rows:
        books: list[BookOut] = []
        for membership, book in memberships_by_series_id.get(series.id, []):
            enriched = book_payloads_by_id[book.id].model_copy(
                update={"marked_complete_in_series": membership.marked_complete}
            )
            books.append(enriched)
        output.append(
            SeriesOut(
                id=series.id,
                name=series.name,
                description=series.description,
                created_at=series.created_at,
                books=books,
            )
        )
    return output


async def build_series_out_list(
    db: AsyncSession,
    *,
    series_rows: Sequence[Series],
    membership_rows: Sequence[tuple[SeriesBook, Book]],
    user_id: uuid.UUID,
) -> list[SeriesOut]:
    ordered_books: list[Book] = []
    memberships_by_series_id: dict[uuid.UUID, list[tuple[SeriesBook, Book]]] = {}
    seen_book_ids: set[uuid.UUID] = set()
    for membership, book in membership_rows:
        memberships_by_series_id.setdefault(membership.series_id, []).append((membership, book))
        if book.id in seen_book_ids:
            continue
        seen_book_ids.add(book.id)
        ordered_books.append(book)
    book_payloads = await build_book_out_list(db, books=ordered_books, user_id=user_id)
    book_payloads_by_id = {payload.id: payload for payload in book_payloads}
    return _build_series_out_from_grouped_rows(
        series_rows=series_rows,
        memberships_by_series_id=memberships_by_series_id,
        book_payloads_by_id=book_payloads_by_id,
    )


async def build_single_series_out(
    db: AsyncSession,
    *,
    series: Series,
    user_id: uuid.UUID,
) -> SeriesOut:
    membership_rows = (
        await db.execute(
            select(SeriesBook, Book)
            .join(Book, Book.id == SeriesBook.book_id)
            .where(SeriesBook.series_id == series.id, Book.user_id == user_id)
            .order_by(SeriesBook.position, Book.created_at)
        )
    ).all()
    return (
        await build_series_out_list(
            db,
            series_rows=[series],
            membership_rows=membership_rows,
            user_id=user_id,
        )
    )[0]


async def book_out(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
    *,
    context: BookRenderContext | None = None,
    progress: ReadingProgress | None = None,
) -> BookOut:
    access = build_book_access_context(book, user_id=user_id, collaborator=collaborator)
    if context is None:
        await ensure_book_cover(db, book)
        if progress is None:
            progress = (
                await db.execute(
                    select(ReadingProgress).where(
                        ReadingProgress.book_id == book.id,
                        ReadingProgress.user_id == user_id,
                    )
                )
            ).scalars().first()
        total_words = (
            await db.scalar(
                select(func.coalesce(func.sum(Chapter.word_count), 0)).where(Chapter.book_id == book.id)
            )
        ) or 0
        cover_url = cover_url_for_book(book)
    else:
        progress = context.progress_by_book_id.get(book.id)
        total_words = context.total_words_by_book_id.get(book.id, 0)
        cover_url = context.cover_url_by_book_id.get(book.id)
    chapters_read_count = len(set(progress.chapters_read or [])) if progress else 0
    total = book.total_chapters or 0
    percent = round((chapters_read_count / total) * 100, 1) if total else 0.0
    chapters_left = max(total - chapters_read_count, 0) if total else None
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        genre=book.genre,
        format=book.format,
        work_type=book.work_type,
        status=book.status,
        mode=book.mode or "reader",
        workspace_shell=access.workspace_shell,
        access_class=access.access_class,
        can_switch_workspace_mode=access.can_switch_workspace_mode,
        source_kind=book.source_kind or "single_upload",
        preserve_chapter_numbers=bool(book.preserve_chapter_numbers),
        preserve_source_chapters=bool(book.preserve_source_chapters),
        cover_url=cover_url,
        total_chapters=book.total_chapters,
        total_tokens=book.total_tokens,
        total_words=int(total_words),
        is_truncated=book.is_truncated,
        primary_series_id=book.primary_series_id,
        series_name=book.series_name,
        series_order=book.series_order,
        is_public=book.is_public,
        public_status=getattr(book, "public_status", "draft"),
        public_slug=getattr(book, "public_slug", None),
        published_at=getattr(book, "published_at", None),
        public_updated_at=getattr(book, "public_updated_at", None),
        public_visibility=getattr(book, "public_visibility", "private"),
        rights_confirmation=bool(getattr(book, "rights_confirmation", False)),
        rights_confirmation_at=getattr(book, "rights_confirmation_at", None),
        content_source_type=getattr(book, "content_source_type", "user_original"),
        moderation_status=getattr(book, "moderation_status", "clean"),
        moderation_reason=getattr(book, "moderation_reason", None),
        takedown_reason=getattr(book, "takedown_reason", None),
        takedown_at=getattr(book, "takedown_at", None),
        public_upload_counted_at=getattr(book, "public_upload_counted_at", None),
        source_title=getattr(book, "source_title", None),
        source_author=getattr(book, "source_author", None),
        source_public_domain_note=getattr(book, "source_public_domain_note", None),
        source_url=getattr(book, "source_url", None),
        public_description=book.public_description,
        public_share_status=getattr(book, "public_share_status", None),
        public_share_requested_at=getattr(book, "public_share_requested_at", None),
        public_share_approved_at=getattr(book, "public_share_approved_at", None),
        copyright_warning=book.copyright_warning,
        is_editor_project=bool(getattr(book, "is_editor_project", False)),
        archived_at=book.archived_at,
        hidden_at=book.hidden_at,
        created_at=book.created_at,
        progress_pct=percent,
        chapters_read_count=chapters_read_count,
        chapters_left=chapters_left,
        processing=build_book_processing_payload(book),
        collaboration_role=access.collaboration_role,
        collaboration_scope=collaboration_scope_model(access.collaboration_scope) if access.collaboration_scope else None,
        collaboration_permissions=(
            collaboration_permissions_model(
                access.collaboration_permissions,
                role=access.collaboration_role or "viewer",
                scope=access.collaboration_scope,
            )
            if access.collaboration_permissions and access.collaboration_role
            else None
        ),
    )


# ─── Cover helpers ────────────────────────────────────────────────────────────

def cover_url_for_book(book: Book) -> str | None:
    if not book.cover_s3_key:
        return None
    presigned = get_presigned_url(book.cover_s3_key)
    if presigned:
        return presigned
    token = create_asset_token(str(book.user_id), f"book-cover:{book.id}", expires_minutes=120)
    return f"{settings.API_V1_PREFIX}/books/{book.id}/cover?token={token}"


def build_blank_cover_image(title: str, author: str | None = None) -> tuple[bytes, str]:
    image = Image.new("RGB", (1200, 1800), color=(248, 245, 238))
    draw = ImageDraw.Draw(image)

    def load_font(size: int) -> ImageFont.ImageFont:
        for candidate in ("DejaVuSans.ttf", "arial.ttf"):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    title_font = load_font(72)
    author_font = load_font(40)
    text_color = (28, 25, 23)
    accent_color = (79, 70, 229)
    max_text_width = 860

    def wrap_text(value: str, font: ImageFont.ImageFont) -> list[str]:
        words = [part for part in value.split() if part]
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if width <= max_text_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    normalized_title = " ".join((title or "").split()).strip() or "Untitled"
    normalized_author = " ".join((author or "").split()).strip()
    title_lines = wrap_text(normalized_title, title_font)[:5]
    if not title_lines:
        title_lines = ["Untitled"]
    author_line = normalized_author or "Unknown author"

    draw.rounded_rectangle((180, 220, 1020, 1540), radius=36, outline=accent_color, width=8, fill=(255, 255, 255))
    draw.rectangle((180, 220, 1020, 290), fill=accent_color)
    draw.text((600, 245), "LoreVia", font=author_font, fill=(255, 255, 255), anchor="mm")

    y = 520
    for line in title_lines:
        draw.text((600, y), line, font=title_font, fill=text_color, anchor="mm")
        y += 70

    draw.line((330, y + 30, 870, y + 30), fill=(203, 213, 225), width=3)
    draw.text((600, y + 110), author_line, font=author_font, fill=(68, 64, 60), anchor="mm")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"


async def ensure_book_cover(db: AsyncSession, book: Book) -> None:
    if book.format == "pdf" and not book.cover_s3_key and book.s3_key:
        from app.parsers.pdf_parser import extract_first_page_cover

        try:
            raw_book = await asyncio.to_thread(download_book, book.s3_key)
        except Exception:
            raw_book = None

        if raw_book:
            cover = await asyncio.to_thread(extract_first_page_cover, raw_book)
            if cover:
                cover_bytes, content_type = cover
                try:
                    book.cover_s3_key = await asyncio.to_thread(
                        upload_binary,
                        f"covers/{book.user_id}/{uuid.uuid4()}.png",
                        cover_bytes,
                        content_type,
                    )
                    await db.flush()
                except Exception:
                    return

    if not book.cover_s3_key:
        try:
            cover_bytes, content_type = await asyncio.to_thread(build_blank_cover_image, book.title, book.author)
            book.cover_s3_key = await asyncio.to_thread(
                upload_binary,
                f"covers/{book.user_id}/{uuid.uuid4()}.png",
                cover_bytes,
                content_type,
            )
            await db.flush()
        except Exception:
            return


# ─── Progress / word-count helpers ───────────────────────────────────────────

async def compute_words_read_for_book(
    db: AsyncSession,
    book: Book,
    progress: ReadingProgress | None,
    *,
    chapter_word_count_map: dict[tuple[uuid.UUID, int], int] | None = None,
    allow_content_fallback: bool = True,
) -> int:
    if progress is None:
        return 0

    read_chapters = sorted(set(progress.chapters_read or []))
    total_words = 0
    counted_chapters = set(read_chapters)

    for chapter_number in read_chapters:
        total_words += await chapter_word_count(
            db,
            book.id,
            chapter_number,
            chapter_word_count_map=chapter_word_count_map,
            allow_content_fallback=allow_content_fallback,
        )

    current_chapter = progress.current_chapter or 0
    if current_chapter > 0 and current_chapter not in counted_chapters:
        chapter_words = await chapter_word_count(
            db,
            book.id,
            current_chapter,
            chapter_word_count_map=chapter_word_count_map,
            allow_content_fallback=allow_content_fallback,
        )
        total_words += int(round(chapter_words * max(0.0, min(progress.scroll_pct or 0.0, 1.0))))

    return total_words


async def compute_words_read_for_books(
    db: AsyncSession,
    *,
    books: Sequence[Book],
    progress_rows: Sequence[ReadingProgress],
) -> dict[uuid.UUID, int]:
    if not books or not progress_rows:
        return {}

    relevant_numbers_by_book: dict[uuid.UUID, set[int]] = {}
    progress_by_book_id: dict[uuid.UUID, ReadingProgress] = {}
    for progress in progress_rows:
        progress_by_book_id[progress.book_id] = progress
        numbers = relevant_numbers_by_book.setdefault(progress.book_id, set())
        for chapter_number in progress.chapters_read or []:
            if chapter_number is not None:
                numbers.add(int(chapter_number))
        current_chapter = int(progress.current_chapter or 0)
        if current_chapter > 0:
            numbers.add(current_chapter)

    if not relevant_numbers_by_book:
        return {}

    chapter_rows = (
        await db.execute(
            select(Chapter.book_id, Chapter.number, Chapter.word_count).where(
                Chapter.book_id.in_(list(relevant_numbers_by_book.keys()))
            )
        )
    ).all()
    chapter_word_counts = {
        (book_id, int(chapter_number)): int(word_count or 0)
        for book_id, chapter_number, word_count in chapter_rows
        if chapter_number is not None
    }
    totals: dict[uuid.UUID, int] = {}
    for book in books:
        totals[book.id] = await compute_words_read_for_book(
            db,
            book,
            progress_by_book_id.get(book.id),
            chapter_word_count_map=chapter_word_counts,
            allow_content_fallback=False,
        )
    return totals


async def chapter_word_count(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_number: int,
    *,
    chapter_word_count_map: dict[tuple[uuid.UUID, int], int] | None = None,
    allow_content_fallback: bool = True,
) -> int:
    if chapter_word_count_map is not None:
        return int(chapter_word_count_map.get((book_id, chapter_number), 0))
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book_id, Chapter.number == chapter_number)
        )
    ).scalar()
    if chapter is None:
        return 0
    if chapter.word_count:
        return chapter.word_count
    if not chapter.s3_key or not allow_content_fallback:
        return 0
    try:
        stored = deserialize_manuscript_content(download_book(chapter.s3_key))
        text = clean_markdown_asterisks_str(str(stored.get("text") or ""))
    except Exception:
        return 0
    return len(text.replace("\r", " ").replace("\n", " ").split())


def clean_markdown_asterisks_str(text: str) -> str:
    """Remove asterisks for word counting only - does not strip markdown syntax for display."""
    if not text:
        return ""
    return text.replace("**", "").replace("*", "")


def markdown_to_html(markdown_text: str) -> str:
    """Convert markdown text to HTML using markdown-it-py."""
    if not markdown_text:
        return ""
    try:
        from markdown_it import MarkdownIt

        md = MarkdownIt()
        html = md.render(markdown_text)
        # Clean the HTML to ensure it only contains allowed tags
        return clean_manuscript_html(html)
    except ImportError:
        # Fallback if markdown-it-py is not installed
        # Basic conversion for common markdown elements
        lines = markdown_text.split("\n")
        html_parts = []
        in_paragraph = False

        for line in lines:
            line = line.strip()
            if not line:
                if in_paragraph:
                    html_parts.append("</p>")
                    in_paragraph = False
                continue

            # Headers
            if line.startswith("#"):
                if in_paragraph:
                    html_parts.append("</p>")
                    in_paragraph = False
                level = len(line) - len(line.lstrip("#"))
                if level <= 6:
                    content = line.lstrip("#").strip()
                    html_parts.append(f"<h{level}>{content}</h{level}>")
                else:
                    html_parts.append(f"<p>{line}</p>")
            # Lists
            elif line.startswith("- ") or line.startswith("* "):
                if in_paragraph:
                    html_parts.append("</p>")
                    in_paragraph = False
                content = line[2:].strip()
                html_parts.append(f"<li>{content}</li>")
            # Bold/italic
            else:
                if not in_paragraph:
                    html_parts.append("<p>")
                    in_paragraph = True
                # Simple bold/italic replacement
                line = line.replace("**", "<strong>").replace("*", "<em>")
                line = line.replace("<strong>", "<strong>", 1).replace("<em>", "<em>", 1)
                # Close tags (simplified)
                line = line.replace("<strong>", "<strong>", line.count("<strong>"))
                line = line.replace("<em>", "<em>", line.count("<em>"))
                html_parts.append(line)

        if in_paragraph:
            html_parts.append("</p>")

        return clean_manuscript_html("".join(html_parts))


def manuscript_text_to_html(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        return "<p></p>"
    paragraphs = [segment.strip() for segment in cleaned.split("\n\n")]
    html_parts: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        lines = [_clean_text(line) for line in paragraph.split("\n")]
        html_parts.append(f"<p>{'<br>'.join(line for line in lines if line or len(lines) == 1)}</p>")
    return "".join(html_parts) or "<p></p>"


def clean_manuscript_html(html: str | None) -> str:
    cleaner = CSSSanitizer(allowed_css_properties=cast(Any, MANUSCRIPT_ALLOWED_STYLES))
    return str(bleach.clean(
        str(html or "").strip(),
        tags=cast(Any, MANUSCRIPT_ALLOWED_TAGS),
        attributes=cast(Any, MANUSCRIPT_ALLOWED_ATTRIBUTES),
        protocols=cast(Any, MANUSCRIPT_ALLOWED_PROTOCOLS),
        css_sanitizer=cast(Any, cleaner),
        strip=True,
    ))


def manuscript_html_to_text(html: str | None) -> str:
    from bs4 import BeautifulSoup

    cleaned_html = clean_manuscript_html(html)
    if not cleaned_html:
        return ""

    soup = BeautifulSoup(cleaned_html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")

    blocks: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "p", "blockquote", "li"]):
        text = node.get_text("\n", strip=False)
        normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
        if normalized:
            blocks.append(normalized)

    if not blocks:
        return soup.get_text("\n", strip=True)

    return "\n\n".join(blocks)


def serialize_manuscript_content(text: str, html: str | None = None) -> str:
    normalized_text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized_html = clean_manuscript_html(html) if html else ""
    if not normalized_html and normalized_text:
        normalized_html = manuscript_text_to_html(normalized_text)
    if not normalized_html:
        return normalized_text
    normalized_text = manuscript_html_to_text(normalized_html) or normalized_text
    return json.dumps(
        {"format": "rich_text_v1", "html": normalized_html, "text": normalized_text},
        ensure_ascii=False,
    )


def deserialize_manuscript_content(raw: str | bytes | memoryview | None) -> dict[str, str | None]:
    if raw is None:
        return {"format": "plain_text", "text": "", "html": None}
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    raw_text: str = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
    trimmed = raw_text.strip()
    if not trimmed:
        return {"format": "plain_text", "text": "", "html": None}
    try:
        payload = json.loads(trimmed)
    except json.JSONDecodeError:
        return {"format": "plain_text", "text": raw_text, "html": manuscript_text_to_html(raw_text)}

    if isinstance(payload, dict) and payload.get("format") == "rich_text_v1":
        html = clean_manuscript_html(str(payload.get("html") or ""))
        text = manuscript_html_to_text(html) or str(payload.get("text") or "")
        return {"format": "rich_text_v1", "text": text, "html": html or manuscript_text_to_html(text)}

    return {"format": "plain_text", "text": raw_text, "html": manuscript_text_to_html(raw_text)}


async def persist_editor_chapter_content(
    db: AsyncSession,
    book: Book,
    *,
    chapter_number: int,
    title: str | None,
    text: str,
    html: str | None,
    description: str | None = None,
    chapter_kind: str | None = None,
    content_version: int = 1,
) -> Chapter:
    storage_key = f"chapters/{book.id}/{chapter_number}.txt"
    payload = serialize_manuscript_content(text, html)
    stored_key = await asyncio.to_thread(upload_text, storage_key, payload)
    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == chapter_number)
        )
    ).scalar_one_or_none()
    word_count = len(str(text or "").split()) if str(text or "").strip() else 0
    token_count = word_count
    if chapter is None:
        chapter = Chapter(
            book_id=book.id,
            number=chapter_number,
            title=title,
            description=description,
            chapter_kind=normalize_chapter_kind(chapter_kind),
            s3_key=stored_key,
            token_count=token_count,
            word_count=word_count,
            content_version=content_version,
            processed=False,
            analysis_state={},
        )
        db.add(chapter)
        await db.flush()
        return chapter

    chapter.title = title or chapter.title
    chapter.description = description or chapter.description
    chapter.chapter_kind = normalize_chapter_kind(chapter_kind)
    chapter.s3_key = stored_key
    chapter.token_count = token_count
    chapter.word_count = word_count
    chapter.content_version = content_version
    chapter.processed = False
    chapter.analysis_state = {}
    await db.flush()
    return chapter


def report_sentence(text: str | None) -> str:
    cleaned = clean_markdown_asterisks_str((text or "").strip())
    if not cleaned:
        return ""
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return lines[0] if lines else ""


# ─── Chapter number helpers ───────────────────────────────────────────────────

async def next_chapter_number(db: AsyncSession, book_id: uuid.UUID) -> int:
    current_max = await db.scalar(select(func.max(Chapter.number)).where(Chapter.book_id == book_id))
    return int(current_max or 0) + 1


# ─── Manuscript import helpers ────────────────────────────────────────────────

async def parse_import_upload(filename: str, raw: bytes, split_into_chapters: bool) -> list[dict]:
    lower = filename.lower()
    stem = os.path.splitext(os.path.basename(filename))[0] or "Imported chapter"
    if lower.endswith(".pdf"):
        from app.parsers.pdf_parser import parse_pdf
        chapters = await asyncio.to_thread(parse_pdf, raw)
        if split_into_chapters and chapters:
            return chapters
        merged_text = "\n\n".join((ch.get("text") or "").strip() for ch in chapters if ch.get("text"))
        return [{"title": stem, "text": merged_text or "", "number": 1}]
    if lower.endswith(".epub"):
        from app.parsers.epub_parser import parse_epub
        chapters = await asyncio.to_thread(parse_epub, raw)
        if split_into_chapters and chapters:
            return chapters
        merged_text = "\n\n".join((ch.get("text") or "").strip() for ch in chapters if ch.get("text"))
        return [{"title": stem, "text": merged_text or "", "number": 1}]
    if lower.endswith(".docx"):
        from io import BytesIO

        from docx import Document
        doc = Document(BytesIO(raw))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
        if split_into_chapters:
            from app.parsers.text_parser import parse_text_chapters
            return parse_text_chapters(text, title=stem)
        return [{"title": stem, "text": text, "number": 1}]
    if lower.endswith(".doc"):
        # Legacy .doc format requires additional system dependencies (antiword/textract)
        # For now, we'll attempt to use python-docx which may work for some .doc files
        # that are actually .docx with wrong extension
        try:
            from io import BytesIO

            from docx import Document
            doc = Document(BytesIO(raw))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
            return [{"title": stem, "text": text, "number": 1}]
        except Exception:
            raise HTTPException(
                400,
                "Legacy .doc files require additional system dependencies. Please convert to .docx format."
            )
    if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".fountain"):
        text = raw.decode("utf-8", errors="ignore")
        if lower.endswith(".md"):
            # Convert markdown to HTML for proper rendering
            html = markdown_to_html(text)
            if split_into_chapters:
                from app.parsers.text_parser import parse_text_chapters
                chapters = parse_text_chapters(text, title=stem)
                # Preserve HTML on chapters if possible
                return chapters
            return [{"title": stem, "text": text, "html": html, "number": 1}]
        if split_into_chapters:
            from app.parsers.text_parser import parse_text_chapters
            return parse_text_chapters(text, title=stem)
        return [{"title": stem, "text": text, "number": 1}]
    raise HTTPException(400, f"Unsupported manuscript import file: {filename}")


def _normalize_screenplay_character_name(name: str) -> str:
    tokens = [token for token in " ".join((name or "").split()).split(" ") if token]
    normalized_tokens: list[str] = []
    roman_numerals = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
    for token in tokens:
        stripped = token.strip()
        if not stripped:
            continue
        if stripped.upper() in roman_numerals or len(stripped) == 1:
            normalized_tokens.append(stripped.upper())
            continue
        normalized_tokens.append(stripped.title() if stripped.isupper() else stripped)
    return " ".join(normalized_tokens) or "Unknown"


def _build_screenplay_scene_chapters(scenes: list[Any]) -> list[dict[str, Any]]:
    from app.parsers.screenplay_parser import Action, extract_dialogue_from_scene

    chapters: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        action_lines = [
            " ".join((element.text or "").split()).strip()
            for element in getattr(scene, "elements", [])
            if isinstance(element, Action) and " ".join((element.text or "").split()).strip()
        ]
        dialogue_lines: list[str] = []
        for dialogue in extract_dialogue_from_scene(scene):
            speaker = _normalize_screenplay_character_name(str(dialogue.get("character_name") or "Unknown"))
            extension = " ".join(str(dialogue.get("character_extension") or "").split()).strip()
            parenthetical = " ".join(str(dialogue.get("parenthetical") or "").split()).strip()
            dialogue_text = " ".join(str(dialogue.get("dialogue_text") or "").split()).strip()
            if not dialogue_text:
                continue
            speaker_label = speaker
            if extension:
                speaker_label = f"{speaker_label} ({extension})"
            detail_parts = [f"({parenthetical})" if parenthetical else "", dialogue_text]
            dialogue_lines.append(f"{speaker_label}: {' '.join(part for part in detail_parts if part)}".strip())

        body_parts = [scene.text.strip()]
        if action_lines:
            body_parts.append("\n".join(action_lines))
        if dialogue_lines:
            body_parts.append("\n".join(dialogue_lines))
        chapter_text = "\n\n".join(part for part in body_parts if part).strip()
        chapters.append(
            {
                "number": index,
                "title": scene.text.strip() or f"Scene {index}",
                "description": "\n".join(action_lines).strip() or None,
                "text": chapter_text,
                "scene_heading": scene.text.strip() or f"Scene {index}",
                "scene_number": scene.scene_number,
                "dialogue_count": len(dialogue_lines),
            }
        )
    return chapters


async def parse_screenplay_upload(filename: str, raw: bytes) -> dict[str, Any]:
    """Parse screenplay files and return scene-aware ingestion payloads."""
    lower = filename.lower()
    stem = os.path.splitext(os.path.basename(filename))[0] or "Imported screenplay"

    if lower.endswith(".pdf"):
        from app.parsers.pdf_parser import parse_pdf

        parsed_pages = await asyncio.to_thread(parse_pdf, raw)
        source_text = "\n\n".join((chapter.get("text") or "").strip() for chapter in parsed_pages if chapter.get("text"))
    elif lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".fountain") or lower.endswith(".screenplay") or lower.endswith(".script"):
        source_text = raw.decode("utf-8", errors="ignore")
    else:
        raise HTTPException(400, f"Unsupported screenplay format: {filename}")

    from app.parsers.screenplay_parser import analyze_screenplay_stats, parse_screenplay

    scenes = await asyncio.to_thread(parse_screenplay, source_text)
    stats = await asyncio.to_thread(analyze_screenplay_stats, scenes)
    chapters = _build_screenplay_scene_chapters(scenes)
    if not chapters and source_text.strip():
        chapters = [{"number": 1, "title": stem, "text": source_text.strip(), "description": None}]

    return {
        "title": stem,
        "text": source_text,
        "chapters": chapters,
        "scenes": scenes,
        "stats": stats,
    }


def is_screenplay_file(filename: str) -> bool:
    """Check if file is likely a screenplay based on extension."""
    return infer_work_type_from_filename(filename) == "screenplay"


async def parse_book_upload_for_ingestion(
    *,
    format_name: str,
    work_type: str,
    raw: bytes,
    preserve_chapter_numbers: bool,
    preserve_source_chapters: bool,
    language: str | None = None,
) -> dict[str, Any]:
    if work_type == "screenplay":
        screenplay_payload = await parse_screenplay_upload(upload_filename_for_format(format_name), raw)
        return {
            "chapters": screenplay_payload["chapters"],
            "screenplay_payload": screenplay_payload,
            "parser_diagnostics": None,
            "detected_language": language or "en",
        }

    preserve_exact_structure = preserve_chapter_numbers or preserve_source_chapters

    if format_name == "pdf":
        from app.parsers.pdf_parser import parse_pdf_with_diagnostics

        chapters, parser_diagnostics = await asyncio.to_thread(
            parse_pdf_with_diagnostics,
            raw,
            split_large_chapters=not preserve_exact_structure,
            language=language,
        )
        return {
            "chapters": chapters,
            "screenplay_payload": None,
            "parser_diagnostics": parser_diagnostics,
            "detected_language": parser_diagnostics.get("detected_language", "en"),
        }

    if format_name == "epub":
        from app.parsers.epub_parser import parse_epub

        chapters = await asyncio.to_thread(
            parse_epub,
            raw,
            split_large_chapters=not preserve_exact_structure,
        )
        return {"chapters": chapters, "screenplay_payload": None, "parser_diagnostics": None, "detected_language": language or "en"}

    parsed = await parse_import_upload(upload_filename_for_format(format_name), raw, False)
    return {"chapters": parsed, "screenplay_payload": None, "parser_diagnostics": None, "detected_language": language or "en"}


def normalize_imported_chapters(
    chapters: list[dict],
    *,
    chapter_number: int | None,
    start_number: int,
    replace_existing: bool,
    chunk_long_documents: bool,
    preserve_exact_structure: bool = False,
) -> list[dict]:
    normalized: list[dict] = []
    running_number = start_number
    for chapter in chapters:
        text = (chapter.get("text") or "").strip()
        if not text:
            continue
        title = _clean_optional_text(" ".join(str(chapter.get("title") or "").split()).strip())
        description = _clean_optional_text(" ".join(str(chapter.get("description") or "").split()).strip())
        chapter_kind = normalize_chapter_kind(chapter.get("chapter_kind") or chapter.get("section_type"))
        html = clean_manuscript_html(chapter.get("html")) if chapter.get("html") else None
        images = list(chapter.get("images") or [])
        desired_number = chapter_number if replace_existing and chapter_number else running_number
        parts = split_long_document(text) if chunk_long_documents and not preserve_exact_structure else [text]
        for index, part in enumerate(parts, start=1):
            part_title = title
            if len(parts) > 1:
                base = title or f"Chapter {desired_number}"
                part_title = f"{base} (Part {index})"
            normalized.append({
                "number": desired_number,
                "title": part_title,
                "text": part,
                "html": html if len(parts) == 1 else manuscript_text_to_html(part),
                "description": description,
                "chapter_kind": chapter_kind if len(parts) == 1 else "chapter",
                "images": images if len(parts) == 1 else _filter_import_images_for_text(part, images),
                "scene_heading": chapter.get("scene_heading"),
                "scene_number": chapter.get("scene_number"),
                "dialogue_count": chapter.get("dialogue_count"),
            })
            desired_number += 1
        running_number = desired_number
    return normalized


def _filter_import_images_for_text(text: str, images: list[dict]) -> list[dict]:
    markers = {
        match.group(0)
        for match in re.finditer(r"\[\[IMAGE:[^\]]+\]\]", text or "")
    }
    if not markers:
        return []
    return [image for image in images if image.get("marker") in markers]


def split_long_document(text: str, max_words: int = 3500) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    parts: list[str] = []
    bucket: list[str] = []
    bucket_words = 0
    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        if bucket and bucket_words + paragraph_words > max_words:
            if bucket_words < 250 and paragraph_words >= max_words:
                bucket.append(paragraph)
                parts.append("\n\n".join(bucket))
                bucket = []
                bucket_words = 0
                continue
            parts.append("\n\n".join(bucket))
            bucket = []
            bucket_words = 0
        bucket.append(paragraph)
        bucket_words += paragraph_words
    if bucket:
        parts.append("\n\n".join(bucket))
    return parts or [text]


# ─── Import preview builder ──────────────────────────────────────────────

def build_import_preview(
    *,
    format_name: str,
    work_type: str,
    raw: bytes,
    language: str | None = None,
    preserve_chapter_numbers: bool = False,
    preserve_source_chapters: bool = False,
) -> dict[str, Any]:
    """Parse a manuscript file and return an ImportPreview dict for the frontend.

    Performs parsing and structure detection only — no DB writes, no Celery dispatch.
    This function is synchronous; callers should wrap in asyncio.to_thread() if needed.
    """
    from app.parsers.heading_patterns import classify_heading_type
    from app.schemas.section import ImportPreview, SectionMeta

    preview = ImportPreview()

    if work_type == "screenplay":
        # Screenplay parsing is async; caller must wrap this function in asyncio event loop
        # For now, handle screenplay by extracting text and treating as single chapter
        from app.parsers.screenplay_parser import parse_screenplay
        source_text = raw.decode("utf-8", errors="ignore")
        scenes = parse_screenplay(source_text)
        sections: list[SectionMeta] = []
        for i, scene in enumerate(scenes, start=1):
            scene_title = getattr(scene, "text", f"Scene {i}")
            sections.append(SectionMeta.from_heading(
                title=str(scene_title).strip() or f"Scene {i}",
                type_="chapter",
                number=i,
            ))
        preview.sections = sections
        preview.chapter_count = len(sections)
        preview.compute_confidence()
        return preview.model_dump()

    # Build sample text for language detection when not provided
    sample_text = ""
    if format_name == "pdf":
        import fitz
        doc = fitz.open(stream=raw, filetype="pdf")
        try:
            pages = min(doc.page_count, 3)
            for i in range(pages):
                sample_text += doc.load_page(i).get_text()
        finally:
            doc.close()
    elif format_name == "epub":
        from ebooklib import epub as epub_lib
        from io import BytesIO
        book = epub_lib.read_epub(BytesIO(raw))
        from bs4 import BeautifulSoup
        for item in book.get_items_of_type(9):  # ITEM_DOCUMENT
            content = item.get_content().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(content, "html.parser")
            sample_text += soup.get_text()
            if len(sample_text) > 5000:
                break
    elif format_name in ("docx", "doc"):
        from io import BytesIO
        from docx import Document
        doc = Document(BytesIO(raw))
        sample_text = "\n".join(
            paragraph.text for paragraph in doc.paragraphs[:30] if paragraph.text.strip()
        )
    elif format_name in ("txt", "md", "fountain"):
        sample_text = raw.decode("utf-8", errors="ignore")[:5000]

    # Auto-detect language if not provided
    if language is None and sample_text:
        from app.utils.language_utils import detect_language
        lang_result = detect_language(sample_text, max_chars=5000)
        language = lang_result["detected"]
        preview.language_confidence = lang_result["confidence"]
    preview.detected_language = language or "en"

    chapters: list[dict] = []
    diagnostics: dict[str, Any] | None = None

    preserve_exact = preserve_chapter_numbers or preserve_source_chapters

    if format_name == "pdf":
        from app.parsers.pdf_parser import parse_pdf_with_diagnostics
        chapters, diagnostics = parse_pdf_with_diagnostics(
            raw,
            split_large_chapters=not preserve_exact,
            language=language,
        )
    elif format_name == "epub":
        from app.parsers.epub_parser import parse_epub
        chapters = parse_epub(
            raw,
            split_large_chapters=not preserve_exact,
        )
    elif format_name in ("docx", "doc"):
        from io import BytesIO
        from docx import Document
        from app.parsers.text_parser import parse_text_chapters
        doc = Document(BytesIO(raw))
        text = "\n".join(
            paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()
        )
        chapters = parse_text_chapters(text, language=language)
    elif format_name in ("txt", "md", "fountain"):
        text = raw.decode("utf-8", errors="ignore")
        from app.parsers.text_parser import parse_text_chapters
        chapters = parse_text_chapters(text, language=language)
    else:
        raise ValueError(f"Unsupported format for preview: {format_name}")

    sections = []
    for ch in chapters:
        title = ch.get("title", "")
        stype = ch.get("section_type", "unknown")
        num = ch.get("number") or ch.get("source_number")
        confidence = 1.0 if classify_heading_type(title, language or "en")[0] != "unknown" else 0.5
        sections.append(SectionMeta.from_heading(
            title=title,
            type_=stype,
            number=num,
            confidence=confidence,
        ))

    preview.sections = sections

    if diagnostics:
        preview.build_from_parser_diagnostics(diagnostics, sections=sections)
    else:
        section_counts: dict[str, int] = {}
        for s in sections:
            section_counts[s.type] = section_counts.get(s.type, 0) + 1
        mini_diag = {
            "detected_language": preview.detected_language,
            "detected_language_confidence": preview.language_confidence,
            "chapter_count": len(chapters),
            "heading_count": len(sections),
            "toc_detected": section_counts.get("toc", 0) > 0,
            "front_matter_count": sum(
                v for k, v in section_counts.items()
                if k in ("preface", "foreword", "acknowledgements", "dedication")
            ),
            "anomalies": [],
            "fallback_strategy": None,
            "total_pages": 0,
        }
        preview.build_from_parser_diagnostics(mini_diag, sections=sections)

    return preview.model_dump()


# ─── Misc ─────────────────────────────────────────────────────────────────────

def as_bool(value: str | None) -> bool:
    return (str(value) if value else "").strip().lower() in {"1", "true", "yes", "on"}


def _map_chapter_consistency_state_history(
    states: Sequence[CharacterState],
) -> tuple[list[int], list[CharacterState]]:
    chapter_numbers = [int(state.at_chapter or 0) for state in states]
    return chapter_numbers, list(states)


def _latest_state_before_chapter(
    chapter_numbers: Sequence[int],
    states: Sequence[CharacterState],
    chapter_number: int,
) -> CharacterState | None:
    idx = bisect.bisect_left(chapter_numbers, chapter_number) - 1
    if idx < 0:
        return None
    return states[idx]


def _detect_continuity_flags_from_rows(
    *,
    work_type: str,
    chapter_number: int,
    rows: Sequence[tuple[CharacterState, str]],
    prior_states_by_character: dict[uuid.UUID, tuple[list[int], list[CharacterState]]],
) -> list[str]:
    if not rows:
        return []

    flags: list[str] = []
    watched_traits = {
        "eyes": "eye description",
        "hair": "hair description",
        "build": "build description",
        "age_descriptor": "age description",
        "distinguishing": "distinguishing feature",
    }

    for state, char_name in rows:
        state_history = prior_states_by_character.get(state.character_id)
        if state_history is None:
            continue
        previous = _latest_state_before_chapter(state_history[0], state_history[1], chapter_number)
        if previous is None:
            continue
        current_snapshot = state.trait_snapshot or {}
        previous_snapshot = previous.trait_snapshot or {}
        for trait_key, label in watched_traits.items():
            previous_value = _trait_value(previous_snapshot.get(trait_key))
            current_value = _trait_value(current_snapshot.get(trait_key))
            if previous_value and current_value and previous_value.lower() != current_value.lower():
                flags.append(
                    f"{char_name}: {label} changed from '{previous_value}' to '{current_value}' since {story_unit_label(work_type, previous.at_chapter, lowercase=True)}."
                )
                break

    return flags


async def _load_chapter_consistency_context(
    db: AsyncSession,
    book: Book,
    chapter_numbers: Sequence[int],
) -> dict[str, Any]:
    unique_chapter_numbers = sorted({int(number) for number in chapter_numbers if int(number) > 0})
    if not unique_chapter_numbers:
        return {
            "chapters_by_number": {},
            "summary_by_chapter_id": {},
            "new_characters_by_chapter": {},
            "names_by_id": {},
            "relationships_by_chapter": {},
            "opened_threads_by_chapter": {},
            "resolved_threads_by_chapter": {},
            "continuity_flags_by_chapter": {},
        }

    chapters = (
        await db.execute(
            select(Chapter)
            .where(Chapter.book_id == book.id, Chapter.number.in_(unique_chapter_numbers))
        )
    ).scalars().all()
    chapters_by_number = {int(chapter.number): chapter for chapter in chapters if chapter.number is not None}
    chapter_ids = [chapter.id for chapter in chapters]

    summary_rows = (
        await db.execute(
            select(ChapterSummary)
            .where(
                ChapterSummary.chapter_id.in_(chapter_ids),
                ChapterSummary.mode == "short",
            )
        )
    ).scalars().all() if chapter_ids else []
    summary_by_chapter_id = {summary.chapter_id: summary for summary in summary_rows}

    new_characters = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book.id, Character.first_chapter.in_(unique_chapter_numbers))
            .order_by(Character.first_chapter.asc(), Character.name)
        )
    ).scalars().all()
    new_characters_by_chapter: dict[int, list[Character]] = {}
    for character in new_characters:
        if character.first_chapter is None:
            continue
        new_characters_by_chapter.setdefault(int(character.first_chapter), []).append(character)

    character_names = (
        await db.execute(select(Character.id, Character.name).where(Character.book_id == book.id))
    ).all()
    names_by_id = {char_id: name for char_id, name in character_names}

    relationships = (
        await db.execute(
            select(CharacterRelationship)
            .where(
                CharacterRelationship.book_id == book.id,
                CharacterRelationship.from_chapter.in_(unique_chapter_numbers),
            )
        )
    ).scalars().all()
    relationships_by_chapter: dict[int, list[CharacterRelationship]] = {}
    for relationship in relationships:
        if relationship.from_chapter is None:
            continue
        relationships_by_chapter.setdefault(int(relationship.from_chapter), []).append(relationship)

    plot_threads = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book.id)
            .where(
                (PlotThread.introduced_at.in_(unique_chapter_numbers))
                | (PlotThread.resolved_at.in_(unique_chapter_numbers))
            )
            .order_by(PlotThread.importance.desc(), PlotThread.title)
        )
    ).scalars().all()
    opened_threads_by_chapter: dict[int, list[PlotThread]] = {}
    resolved_threads_by_chapter: dict[int, list[PlotThread]] = {}
    for thread in plot_threads:
        if thread.introduced_at is not None and int(thread.introduced_at) in unique_chapter_numbers:
            opened_threads_by_chapter.setdefault(int(thread.introduced_at), []).append(thread)
        if thread.resolved_at is not None and int(thread.resolved_at) in unique_chapter_numbers:
            resolved_threads_by_chapter.setdefault(int(thread.resolved_at), []).append(thread)

    continuity_state_rows = (
        await db.execute(
            select(CharacterState, Character.name)
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book.id,
                CharacterState.at_chapter.in_(unique_chapter_numbers),
            )
        )
    ).all()
    continuity_rows_by_chapter: dict[int, list[tuple[CharacterState, str]]] = {}
    tracked_character_ids = {
        state.character_id
        for state, _char_name in continuity_state_rows
        if state.character_id is not None
    }
    for state, char_name in continuity_state_rows:
        if state.at_chapter is None:
            continue
        continuity_rows_by_chapter.setdefault(int(state.at_chapter), []).append((state, char_name))

    max_chapter_number = max(unique_chapter_numbers)
    prior_states = (
        await db.execute(
            select(CharacterState)
            .where(
                CharacterState.character_id.in_(tracked_character_ids),
                CharacterState.at_chapter < max_chapter_number,
            )
            .order_by(CharacterState.character_id.asc(), CharacterState.at_chapter.asc())
        )
    ).scalars().all() if tracked_character_ids else []
    prior_states_by_character: dict[uuid.UUID, tuple[list[int], list[CharacterState]]] = {}
    grouped_states: dict[uuid.UUID, list[CharacterState]] = {}
    for state in prior_states:
        if state.character_id is None or state.at_chapter is None:
            continue
        grouped_states.setdefault(state.character_id, []).append(state)
    for character_id, states in grouped_states.items():
        prior_states_by_character[character_id] = _map_chapter_consistency_state_history(states)

    continuity_flags_by_chapter = {
        chapter_number: _detect_continuity_flags_from_rows(
            work_type=book.work_type or "novel",
            chapter_number=chapter_number,
            rows=rows,
            prior_states_by_character=prior_states_by_character,
        )
        for chapter_number, rows in continuity_rows_by_chapter.items()
    }

    return {
        "chapters_by_number": chapters_by_number,
        "summary_by_chapter_id": summary_by_chapter_id,
        "new_characters_by_chapter": new_characters_by_chapter,
        "names_by_id": names_by_id,
        "relationships_by_chapter": relationships_by_chapter,
        "opened_threads_by_chapter": opened_threads_by_chapter,
        "resolved_threads_by_chapter": resolved_threads_by_chapter,
        "continuity_flags_by_chapter": continuity_flags_by_chapter,
    }


async def build_chapter_consistency_report(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
) -> ChapterConsistencyReport:
    context = await _load_chapter_consistency_context(db, book, [chapter_number])
    chapter = context["chapters_by_number"].get(chapter_number)
    if chapter is None:
        raise HTTPException(404, "Chapter not found")

    short_summary = context["summary_by_chapter_id"].get(chapter.id)
    new_characters = context["new_characters_by_chapter"].get(chapter_number, [])
    names_by_id = context["names_by_id"]

    relationship_changes = []
    seen_relationships: set[tuple[str, str, str]] = set()
    rels = context["relationships_by_chapter"].get(chapter_number, [])
    for rel in rels:
        a_name = names_by_id.get(rel.character_a_id, "Unknown")
        b_name = names_by_id.get(rel.character_b_id, "Unknown")
        key = tuple(sorted((a_name, b_name)) + [rel.rel_type])
        if key in seen_relationships:
            continue
        seen_relationships.add(key)
        relationship_changes.append(
            f"{a_name} and {b_name}: {rel.rel_type.replace('_', ' ')}"
            + (f" — {rel.description}" if rel.description else "")
        )

    opened_threads = context["opened_threads_by_chapter"].get(chapter_number, [])
    resolved_threads = context["resolved_threads_by_chapter"].get(chapter_number, [])
    continuity_flags = context["continuity_flags_by_chapter"].get(chapter_number, [])
    summary_line = report_sentence(short_summary.content if short_summary else "")
    if not summary_line:
        summary_line = f"{story_unit_label(book, chapter_number)} was imported and analysed."

    additions = []
    if new_characters:
        additions.append(f"{len(new_characters)} new character{'s' if len(new_characters) != 1 else ''}")
    if relationship_changes:
        additions.append(f"{len(relationship_changes)} relationship shift{'s' if len(relationship_changes) != 1 else ''}")
    if opened_threads:
        additions.append(f"{len(opened_threads)} plot thread{'s' if len(opened_threads) != 1 else ''} opened")
    if resolved_threads:
        additions.append(f"{len(resolved_threads)} resolved")
    if continuity_flags:
        additions.append(f"{len(continuity_flags)} continuity flag{'s' if len(continuity_flags) != 1 else ''}")
    if additions:
        summary_line = f"{summary_line} This upload surfaced " + ", ".join(additions) + "."

    return ChapterConsistencyReport(
        chapter_number=chapter_number,
        chapter_title=chapter.title,
        summary=summary_line,
        new_characters=[
            ChapterReportCharacter(
                id=str(char.id),
                name=char.name,
                role=char.role,
                first_chapter=char.first_chapter,
                arc_summary=char.arc_summary,
            )
            for char in new_characters
        ],
        relationship_changes=list(dict.fromkeys(relationship_changes[:6])),
        plot_threads_opened=list(dict.fromkeys(thread.title for thread in opened_threads[:6])),
        plot_threads_resolved=list(dict.fromkeys(thread.title for thread in resolved_threads[:6])),
        continuity_flags=list(dict.fromkeys(continuity_flags[:6])),
    )


async def detect_chapter_continuity_flags(
    db: AsyncSession,
    book_id: uuid.UUID,
    chapter_number: int,
) -> list[str]:
    work_type = await db.scalar(select(Book.work_type).where(Book.id == book_id)) or "novel"
    rows = (
        await db.execute(
            select(CharacterState, Character.name)
            .join(Character, Character.id == CharacterState.character_id)
            .where(
                Character.book_id == book_id,
                CharacterState.at_chapter == chapter_number,
            )
        )
    ).all()
    tracked_character_ids = {
        state.character_id
        for state, _char_name in rows
        if state.character_id is not None
    }
    prior_states = (
        await db.execute(
            select(CharacterState)
            .where(
                CharacterState.character_id.in_(tracked_character_ids),
                CharacterState.at_chapter < chapter_number,
            )
            .order_by(CharacterState.character_id.asc(), CharacterState.at_chapter.asc())
        )
    ).scalars().all() if tracked_character_ids else []
    grouped_states: dict[uuid.UUID, list[CharacterState]] = {}
    for state in prior_states:
        if state.character_id is None or state.at_chapter is None:
            continue
        grouped_states.setdefault(state.character_id, []).append(state)
    prior_states_by_character = {
        character_id: _map_chapter_consistency_state_history(states)
        for character_id, states in grouped_states.items()
    }
    return _detect_continuity_flags_from_rows(
        work_type=work_type,
        chapter_number=chapter_number,
        rows=rows,
        prior_states_by_character=prior_states_by_character,
    )


def _trait_value(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("value")
        return value.strip() if isinstance(value, str) and value.strip() else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


# ─── Character card payload ───────────────────────────────────────────────────

async def build_character_card_payload(db: AsyncSession, book: Book, character: Character) -> dict:
    def _reference_keys() -> set[str]:
        keys = {" ".join((character.name or "").split()).strip().lower(), str(character.id).strip().lower()}
        keys.update(" ".join(str(alias or "").split()).strip().lower() for alias in (character.aliases or []))
        return {key for key in keys if key}

    reference_keys = _reference_keys()

    rels = (
        await db.execute(
            select(CharacterRelationship)
            .where(
                CharacterRelationship.book_id == book.id,
                (CharacterRelationship.character_a_id == character.id) | (CharacterRelationship.character_b_id == character.id),
            )
            .order_by(CharacterRelationship.from_chapter, CharacterRelationship.id)
        )
    ).scalars().all()

    other_ids = {
        rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        for rel in rels
    }
    others = (
        await db.execute(select(Character).where(Character.id.in_(other_ids)))
    ).scalars().all() if other_ids else []
    others_by_id = {other.id: other for other in others}
    counterpart_names = {other.id: other.name for other in others}

    from app.engine.character.profile_builder import build_description
    from app.utils.character_utils import build_character_arc_tracker, character_status

    relationship_rows = []
    for rel in rels:
        counterpart_id = rel.character_b_id if rel.character_a_id == character.id else rel.character_a_id
        counterpart = others_by_id.get(counterpart_id)
        relationship_rows.append(
            {
                "name": counterpart.name if counterpart else "Unknown character",
                "type": rel.rel_type.replace("_", " "),
                "description": rel.description,
                "sentiment": rel.sentiment,
                "from_chapter": rel.from_chapter,
                "to_chapter": rel.to_chapter,
            }
        )

    description = build_description(character.trait_state or {}, character.archetype)
    filename_source = " ".join(part for part in [book.title, character.name] if part).strip()
    safe_name = "".join(ch for ch in (filename_source or "character") if ch.isalnum() or ch in {" ", "-", "_"}).strip().replace(" ", "-") or "character"
    linked_threads = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book.id)
            .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
        )
    ).scalars().all()
    character_threads = [
        {
            "title": thread.title,
            "status": thread.status,
            "introduced_at": thread.introduced_at,
            "resolved_at": thread.resolved_at,
            "note": thread.note,
        }
        for thread in linked_threads
        if any(" ".join(str(item or "").split()).strip().lower() in reference_keys for item in (thread.character_ids or []))
    ]
    continuity_watch: list[str] = []
    if character.last_seen_chapter and book.total_chapters and book.total_chapters - character.last_seen_chapter >= 25:
        story_units = story_unit_name(book, plural=True, lowercase=True)
        continuity_watch.append(
            f"{character.name} has not appeared for {book.total_chapters - character.last_seen_chapter} {story_units}."
        )
    if character_threads:
        unresolved = [thread["title"] for thread in character_threads if not is_plot_thread_closed(thread["status"])]
        if unresolved:
            continuity_watch.append(f"Still tied to unresolved threads: {', '.join(unresolved[:3])}.")
    states = (
        await db.execute(
            select(CharacterState)
            .where(CharacterState.character_id == character.id)
            .order_by(CharacterState.at_chapter)
        )
    ).scalars().all()
    voice_profile = (
        await db.execute(
            select(CharacterVoiceProfile).where(CharacterVoiceProfile.character_id == character.id)
        )
    ).scalar_one_or_none()
    return {
        "book_title": book.title,
        "work_type": book.work_type,
        "character_id": str(character.id),
        "name": character.name,
        "aliases": character.aliases or [],
        "role": character.role,
        "status": character_status(character),
        "description": description,
        "first_appearance": character.first_chapter,
        "last_appearance": character.last_seen_chapter,
        "mentions_count": character.mention_count or 0,
        "personality_tags": character.personality_tags or [],
        "goal": character.goal,
        "motivations": character.motivations or [],
        "fears": character.fears or [],
        "lie_they_believe": character.lie_they_believe,
        "backstory_wound": character.backstory_wound,
        "arc_type": character.arc_type,
        "arc_summary": character.arc_summary,
        "growth_events": character.growth_events or [],
        "relationships": relationship_rows,
        "plot_threads": character_threads,
        "continuity_watch": continuity_watch,
        "arc_tracker": build_character_arc_tracker(
            character,
            states=list(states),
            relationships=list(rels),
            counterpart_names=counterpart_names,
            voice_profile=voice_profile,
            total_chapters=book.total_chapters,
        ),
        "filename_base": safe_name,
    }


async def list_chapter_consistency_reports(
    db: AsyncSession,
    book: Book,
    limit: int = 12,
) -> list[ChapterConsistencyReport]:
    chapter_numbers = (
        await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.desc())
            .limit(limit)
        )
    ).scalars().all()

    context = await _load_chapter_consistency_context(db, book, chapter_numbers)

    reports: list[ChapterConsistencyReport] = []
    for chapter_number in chapter_numbers:
        chapter = context["chapters_by_number"].get(chapter_number)
        if chapter is None:
            continue
        short_summary = context["summary_by_chapter_id"].get(chapter.id)
        new_characters = context["new_characters_by_chapter"].get(chapter_number, [])
        names_by_id = context["names_by_id"]
        relationship_changes: list[str] = []
        seen_relationships: set[tuple[str, str, str]] = set()
        for rel in context["relationships_by_chapter"].get(chapter_number, []):
            a_name = names_by_id.get(rel.character_a_id, "Unknown")
            b_name = names_by_id.get(rel.character_b_id, "Unknown")
            key = tuple(sorted((a_name, b_name)) + [rel.rel_type])
            if key in seen_relationships:
                continue
            seen_relationships.add(key)
            relationship_changes.append(
                f"{a_name} and {b_name}: {rel.rel_type.replace('_', ' ')}"
                + (f" â€” {rel.description}" if rel.description else "")
            )
        opened_threads = context["opened_threads_by_chapter"].get(chapter_number, [])
        resolved_threads = context["resolved_threads_by_chapter"].get(chapter_number, [])
        continuity_flags = context["continuity_flags_by_chapter"].get(chapter_number, [])
        summary_line = report_sentence(short_summary.content if short_summary else "")
        if not summary_line:
            summary_line = f"{story_unit_label(book, chapter_number)} was imported and analysed."
        additions = []
        if new_characters:
            additions.append(f"{len(new_characters)} new character{'s' if len(new_characters) != 1 else ''}")
        if relationship_changes:
            additions.append(f"{len(relationship_changes)} relationship shift{'s' if len(relationship_changes) != 1 else ''}")
        if opened_threads:
            additions.append(f"{len(opened_threads)} plot thread{'s' if len(opened_threads) != 1 else ''} opened")
        if resolved_threads:
            additions.append(f"{len(resolved_threads)} resolved")
        if continuity_flags:
            additions.append(f"{len(continuity_flags)} continuity flag{'s' if len(continuity_flags) != 1 else ''}")
        if additions:
            summary_line = f"{summary_line} This upload surfaced " + ", ".join(additions) + "."

        reports.append(
            ChapterConsistencyReport(
                chapter_number=chapter_number,
                chapter_title=chapter.title,
                summary=summary_line,
                new_characters=[
                    ChapterReportCharacter(
                        id=str(char.id),
                        name=char.name,
                        role=char.role,
                        first_chapter=char.first_chapter,
                        arc_summary=char.arc_summary,
                    )
                    for char in new_characters
                ],
                relationship_changes=list(dict.fromkeys(relationship_changes[:6])),
                plot_threads_opened=list(dict.fromkeys(thread.title for thread in opened_threads[:6])),
                plot_threads_resolved=list(dict.fromkeys(thread.title for thread in resolved_threads[:6])),
                continuity_flags=list(dict.fromkeys(continuity_flags[:6])),
            )
        )
    return reports


async def snapshot_chapter_version(
    db: AsyncSession,
    book: Book,
    chapter: Chapter,
    *,
    note: str,
    snapshot_kind: str = "manual",
    restored_from_version_id: uuid.UUID | None = None,
) -> ChapterVersion | None:
    if not chapter.s3_key:
        return None
    try:
        raw = await asyncio.to_thread(download_book, chapter.s3_key)
    except Exception:
        return None

    version_key = await asyncio.to_thread(
        upload_binary,
        f"versions/{book.user_id}/{book.id}/{chapter.number}/{uuid.uuid4()}.txt",
        raw,
        "text/plain; charset=utf-8",
    )
    version = ChapterVersion(
        book_id=book.id,
        chapter_id=chapter.id,
        chapter_number=chapter.number,
        title=chapter.title,
        s3_key=version_key,
        word_count=chapter.word_count,
        note=note,
        snapshot_kind=snapshot_kind,
        restored_from_version_id=restored_from_version_id,
    )
    db.add(version)
    await db.flush()
    return version


async def get_chapter_version_content(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(ChapterVersion).where(ChapterVersion.book_id == book.id, ChapterVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Chapter version not found")
    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = deserialize_manuscript_content(raw)
    return {
        "id": str(version.id),
        "chapter_number": version.chapter_number,
        "title": version.title,
        "word_count": version.word_count,
        "note": version.note,
        "snapshot_kind": version.snapshot_kind,
        "restore_status": version.restore_status,
        "restore_error": version.restore_error,
        "restore_task_id": version.restore_task_id,
        "restore_started_at": version.restore_started_at,
        "restore_completed_at": version.restore_completed_at,
        "created_at": version.created_at,
        "text": str(stored.get("text") or ""),
        "html": cast(str | None, stored.get("html")),
    }


async def purge_chapter_derived_content(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    chapter_id: uuid.UUID | None = None,
) -> None:
    from app.models.character import CharacterState, Character
    from app.models.intelligence import BookChunk, ChapterSummary, CharacterRelationship

    if chapter_id is not None:
        await db.execute(delete(BookChunk).where(BookChunk.chapter_id == chapter_id))
        await db.execute(delete(ChapterSummary).where(ChapterSummary.chapter_id == chapter_id))
    await db.execute(
        delete(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterState).where(
            CharacterState.character_id.in_(
                select(Character.id).where(Character.book_id == book_id)
            ),
            CharacterState.at_chapter == chapter_number,
        )
    )
    await db.execute(
        delete(NovelScene).where(
            NovelScene.book_id == book_id,
            NovelScene.chapter_number == chapter_number,
        )
    )


async def _recompute_character_chapter_aggregates(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    character_ids: set[uuid.UUID],
) -> None:
    if not character_ids:
        return

    characters = (
        await db.execute(
            select(Character).where(
                Character.book_id == book_id,
                Character.id.in_(character_ids),
            )
        )
    ).scalars().all()
    for character in characters:
        rows = (
            await db.execute(
                select(
                    func.min(CharacterMention.chapter_number),
                    func.max(CharacterMention.chapter_number),
                    func.count(CharacterMention.id),
                ).where(
                    CharacterMention.book_id == book_id,
                    CharacterMention.matched_character_id == character.id,
                )
            )
        ).one()
        first_chapter, last_seen_chapter, mention_count = rows
        character.mention_count = int(mention_count or 0)
        if first_chapter is not None:
            character.first_chapter = int(first_chapter)
            character.last_seen_chapter = int(last_seen_chapter) if last_seen_chapter is not None else None
        elif character.last_seen_chapter == character.first_chapter:
            character.last_seen_chapter = None


async def _repair_progress_after_chapter_delete(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    chapter_number: int,
    remaining_numbers: list[int],
) -> None:
    fallback_chapter = remaining_numbers[-1] if remaining_numbers else 1
    progress_rows = (
        await db.execute(select(ReadingProgress).where(ReadingProgress.book_id == book_id))
    ).scalars().all()
    remaining_set = set(remaining_numbers)
    for progress in progress_rows:
        progress.chapters_read = [
            number
            for number in sorted(set(progress.chapters_read or []))
            if number in remaining_set and number != chapter_number
        ]
        if not remaining_numbers:
            progress.current_chapter = 1
            progress.scroll_pct = 0.0
        elif progress.current_chapter not in remaining_set:
            previous = [number for number in remaining_numbers if number < chapter_number]
            progress.current_chapter = previous[-1] if previous else fallback_chapter


async def delete_chapter(
    db: AsyncSession,
    *,
    book: Book,
    chapter_number: int,
) -> None:
    if getattr(book, "is_editor_project", False):
        from app.services.editor_project_service import cancel_rebuild_for_manual_edit

        await cancel_rebuild_for_manual_edit(
            db,
            book,
            reason=f"Chapter {chapter_number} was removed while reprocessing was in progress.",
        )

    chapter = (
        await db.execute(
            select(Chapter).where(
                Chapter.book_id == book.id,
                Chapter.number == chapter_number,
            )
        )
    ).scalar_one_or_none()
    if chapter is None:
        raise HTTPException(404, "Chapter not found")

    affected_character_rows = (
        await db.execute(
            select(CharacterMention.matched_character_id).where(
                CharacterMention.book_id == book.id,
                CharacterMention.chapter_number == chapter_number,
                CharacterMention.matched_character_id.is_not(None),
            )
        )
    ).scalars().all()
    affected_character_ids = {
        character_id
        for character_id in affected_character_rows
        if isinstance(character_id, uuid.UUID)
    }

    snapshot = await snapshot_chapter_version(
        db,
        book,
        chapter,
        note=f"Auto checkpoint before deleting Chapter {chapter_number}",
        snapshot_kind="pre_delete",
    )
    snapshot_version_id = str(snapshot.id) if snapshot is not None else None
    _append_recent_revision_edit(
        book,
        kind="chapter",
        chapter_number=chapter_number,
        before_text=f"Deleted Chapter {chapter_number}: {chapter.title or ''}".strip(),
        after_text="",
        source_version_id=snapshot_version_id,
    )

    await db.execute(
        update(ChapterVersion)
        .where(ChapterVersion.book_id == book.id, ChapterVersion.chapter_id == chapter.id)
        .values(chapter_id=None)
    )
    scene_ids = (
        await db.execute(
            select(NovelScene.id).where(
                NovelScene.book_id == book.id,
                NovelScene.chapter_number == chapter_number,
            )
        )
    ).scalars().all()
    if scene_ids:
        await db.execute(
            update(SceneVersion)
            .where(
                SceneVersion.book_id == book.id,
                SceneVersion.scene_id.in_(scene_ids),
            )
            .values(scene_id=None, chapter_id=None)
        )
    await db.execute(
        update(SceneVersion)
        .where(SceneVersion.book_id == book.id, SceneVersion.chapter_id == chapter.id)
        .values(chapter_id=None)
    )
    await db.execute(delete(ChapterMedia).where(ChapterMedia.chapter_id == chapter.id))
    await purge_chapter_derived_content(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        chapter_id=chapter.id,
    )
    await db.execute(
        delete(ManuscriptAnnotation).where(
            ManuscriptAnnotation.book_id == book.id,
            ManuscriptAnnotation.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(BookNote).where(
            BookNote.book_id == book.id,
            BookNote.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(WorldNote).where(
            WorldNote.book_id == book.id,
            WorldNote.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(QuoteEntry).where(
            QuoteEntry.book_id == book.id,
            QuoteEntry.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterCandidate).where(
            CharacterCandidate.book_id == book.id,
            CharacterCandidate.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterMention).where(
            CharacterMention.book_id == book.id,
            CharacterMention.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterRelationshipCandidate).where(
            CharacterRelationshipCandidate.book_id == book.id,
            CharacterRelationshipCandidate.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CharacterSuppression).where(
            CharacterSuppression.book_id == book.id,
            CharacterSuppression.chapter_number == chapter_number,
        )
    )
    await db.execute(
        delete(CustomTag).where(
            CustomTag.book_id == book.id,
            CustomTag.entity_type == ENTITY_TYPE_CHAPTER,
            CustomTag.entity_id == chapter.id,
        )
    )
    await db.execute(delete(Chapter).where(Chapter.id == chapter.id))
    await db.flush()

    remaining_numbers = (
        await db.execute(
            select(Chapter.number)
            .where(Chapter.book_id == book.id)
            .order_by(Chapter.number.asc())
        )
    ).scalars().all()
    book.total_chapters = int(max(remaining_numbers)) if remaining_numbers else 0
    book.total_chunks = await db.scalar(
        select(func.count()).select_from(BookChunk).where(BookChunk.book_id == book.id)
    )
    await _repair_progress_after_chapter_delete(
        db,
        book_id=book.id,
        chapter_number=chapter_number,
        remaining_numbers=[int(number) for number in remaining_numbers],
    )
    await _recompute_character_chapter_aggregates(
        db,
        book_id=book.id,
        character_ids=affected_character_ids,
    )
    touch_public_book_updated_at(book)
    await db.commit()


async def restore_chapter_version(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(ChapterVersion).where(ChapterVersion.book_id == book.id, ChapterVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Chapter version not found")

    chapter = (
        await db.execute(
            select(Chapter).where(Chapter.book_id == book.id, Chapter.number == version.chapter_number)
        )
    ).scalar_one_or_none()
    if chapter is not None:
        await snapshot_chapter_version(
            db,
            book,
            chapter,
            note=f"Snapshot before restoring Chapter {chapter.number}",
            snapshot_kind="pre_restore",
            restored_from_version_id=version.id,
        )
        await purge_chapter_derived_content(db, book_id=book.id, chapter_number=chapter.number, chapter_id=chapter.id)
        await db.delete(chapter)
        await db.flush()

    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = deserialize_manuscript_content(raw)
    next_text = str(stored.get("text") or "")
    next_html = cast(str | None, stored.get("html"))
    replacement_key = await asyncio.to_thread(
        upload_binary,
        f"books/{book.user_id}/{book.id}/chapters/{version.chapter_number}/{uuid.uuid4()}.txt",
        serialize_manuscript_content(next_text, next_html).encode("utf-8"),
        "text/plain; charset=utf-8",
    )
    restored_chapter = Chapter(
        book_id=book.id,
        number=version.chapter_number,
        content_version=(int(chapter.content_version or 1) + 1) if chapter is not None else 1,
        title=version.title,
        s3_key=replacement_key,
        word_count=_count_words(next_text),
        processed=False,
    )
    db.add(restored_chapter)
    touch_public_book_updated_at(book)
    await db.commit()
    await db.refresh(restored_chapter)
    return {
        "chapter_number": restored_chapter.number,
        "title": restored_chapter.title,
        "text": next_text,
        "html": next_html,
    }


async def list_chapter_versions(
    db: AsyncSession,
    book: Book,
    chapter_number: int,
    limit: int = 12,
) -> list[dict]:
    versions = (
        await db.execute(
            select(ChapterVersion)
            .where(ChapterVersion.book_id == book.id, ChapterVersion.chapter_number == chapter_number)
            .order_by(ChapterVersion.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(version.id),
            "chapter_number": version.chapter_number,
            "title": version.title,
            "word_count": version.word_count,
            "note": version.note,
            "snapshot_kind": version.snapshot_kind,
            "restore_status": version.restore_status,
            "restore_error": version.restore_error,
            "restore_task_id": version.restore_task_id,
            "restore_started_at": version.restore_started_at,
            "restore_completed_at": version.restore_completed_at,
            "created_at": version.created_at,
        }
        for version in versions
    ]


async def snapshot_scene_version(
    db: AsyncSession,
    book: Book,
    scene: NovelScene,
    *,
    note: str,
    snapshot_kind: str = "manual",
    restored_from_version_id: uuid.UUID | None = None,
) -> SceneVersion | None:
    if not scene.title or not scene.body:
        return None

    version_key = await asyncio.to_thread(
        upload_binary,
        f"versions/{book.user_id}/{book.id}/scenes/{scene.id}/{uuid.uuid4()}.txt",
        serialize_manuscript_content(scene.body, scene.html_body).encode("utf-8"),
        "text/plain; charset=utf-8",
    )
    version = SceneVersion(
        book_id=book.id,
        scene_id=scene.id,
        chapter_id=scene.chapter_id,
        chapter_number=scene.chapter_number,
        scene_title=scene.title,
        scene_description=scene.description,
        scene_path=scene.path,
        s3_key=version_key,
        word_count=_count_words(scene.body),
        note=note,
        snapshot_kind=snapshot_kind,
        restored_from_version_id=restored_from_version_id,
    )
    db.add(version)
    await db.flush()
    return version


async def list_scene_versions(
    db: AsyncSession,
    book: Book,
    scene_id: uuid.UUID,
    limit: int = 12,
) -> list[dict[str, Any]]:
    versions = (
        await db.execute(
            select(SceneVersion)
            .where(SceneVersion.book_id == book.id, SceneVersion.scene_id == scene_id)
            .order_by(SceneVersion.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_scene_version_out(version) for version in versions]


async def get_scene_version_content(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(SceneVersion).where(SceneVersion.book_id == book.id, SceneVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Scene version not found")

    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = deserialize_manuscript_content(raw)
    return {
        **_scene_version_out(version),
        "description": version.scene_description,
        "body": str(stored.get("text") or ""),
        "html_body": cast(str | None, stored.get("html")),
    }


async def restore_scene_version(
    db: AsyncSession,
    *,
    book: Book,
    version_id: uuid.UUID,
) -> dict[str, Any]:
    version = (
        await db.execute(
            select(SceneVersion).where(SceneVersion.book_id == book.id, SceneVersion.id == version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(404, "Scene version not found")

    current_scene = await db.get(NovelScene, version.scene_id) if version.scene_id else None
    if current_scene is not None and current_scene.book_id != book.id:
        current_scene = None
    if current_scene is not None:
        await snapshot_scene_version(
            db,
            book,
            current_scene,
            note=f"Checkpoint before restoring scene: {current_scene.title}",
            snapshot_kind="pre_restore",
            restored_from_version_id=version.id,
        )

    raw = await asyncio.to_thread(download_book, version.s3_key)
    stored = deserialize_manuscript_content(raw)
    restored_scene = await save_novel_scene(
        db,
        book=book,
        scene_id=current_scene.id if current_scene is not None else None,
        title=version.scene_title,
        description=version.scene_description,
        body=str(stored.get("text") or ""),
        html_body=cast(str | None, stored.get("html")),
        chapter_number=version.chapter_number,
        status="assigned" if version.chapter_number else "unassigned",
        sort_order=current_scene.sort_order if current_scene is not None else None,
        metadata=None,
        path=version.scene_path,
        skip_scene_version_snapshot=True,
    )
    restored_scene_id = uuid.UUID(restored_scene["id"])
    versions = await list_scene_versions(db, book, restored_scene_id, 12)
    return {
        "scene": restored_scene,
        "versions": versions,
    }


def build_emotional_arc_payload(characters: list[Character]) -> dict[str, Any]:
    tracked: list[dict[str, Any]] = []
    latest_turning_points: list[str] = []
    direction_map = {
        "positive": 1.0,
        "up": 1.0,
        "growth": 0.8,
        "negative": -1.0,
        "down": -1.0,
        "collapse": -0.9,
        "setback": -0.7,
        "neutral": 0.0,
    }

    def direction_score(direction: str) -> float:
        normalized = " ".join((direction or "").split()).strip().lower()
        for key, score in direction_map.items():
            if key in normalized:
                return score
        return 0.0

    ordered_characters = sorted(
        characters,
        key=lambda item: (item.role not in {"mc", "sc"}, -(item.mention_count or 0), item.name.lower()),
    )
    for character in ordered_characters:
        raw_events = [item for item in (character.growth_events or []) if isinstance(item, dict)]
        if not raw_events:
            continue
        raw_events.sort(key=lambda item: int(item.get("chapter_number") or item.get("chapter") or 0))
        points: list[dict[str, Any]] = []
        trajectory_score = 0.0
        for event in raw_events:
            chapter_number = int(event.get("chapter_number") or event.get("chapter") or character.first_chapter or 0)
            if chapter_number <= 0:
                continue
            label = " ".join(str(event.get("event_title") or event.get("event") or "").split()).strip() or f"Chapter {chapter_number} shift"
            impact_score = int(event.get("impact_score") or event.get("importance") or 5)
            growth_direction = " ".join(str(event.get("growth_direction") or "neutral").split()).strip() or "neutral"
            sentiment = round(direction_score(growth_direction) * max(1, impact_score) / 10, 2)
            trajectory_score += sentiment
            points.append(
                {
                    "chapter_number": chapter_number,
                    "label": label,
                    "sentiment": sentiment,
                    "impact_score": impact_score,
                    "growth_direction": growth_direction,
                }
            )
        if not points:
            continue
        latest = points[-1]
        latest_turning_points.append(f"{character.name}: {latest['label']} (chapter {latest['chapter_number']})")
        tracked.append(
            {
                "character_id": str(character.id),
                "character_name": character.name,
                "role": character.role,
                "arc_summary": character.arc_summary,
                "trajectory_score": round(trajectory_score, 2),
                "points": points,
            }
        )

    tracked.sort(key=lambda item: (item["role"] not in {"mc", "sc"}, -abs(item["trajectory_score"]), item["character_name"].lower()))
    return {
        "focus_character_count": len(tracked),
        "latest_turning_points": latest_turning_points[:8],
        "characters": tracked[:10],
    }


async def build_prewriting_check(
    db: AsyncSession,
    book: Book,
    upcoming_chapter: int,
) -> dict:
    total_chapters = book.total_chapters or 0
    active_characters_rows = (
        await db.execute(
            select(Character)
            .where(Character.book_id == book.id, Character.last_seen_chapter.isnot(None))
            .order_by(Character.last_seen_chapter.desc(), Character.mention_count.desc(), Character.name)
            .limit(8)
        )
    ).scalars().all()
    active_characters = [
        {
            "id": str(char.id),
            "name": char.name,
            "role": char.role,
            "last_seen_chapter": char.last_seen_chapter,
            "arc_summary": char.arc_summary,
        }
        for char in active_characters_rows
    ]

    unresolved_threads_rows = (
        await db.execute(
            select(PlotThread)
            .where(PlotThread.book_id == book.id)
            .order_by(PlotThread.importance.desc(), PlotThread.introduced_at, PlotThread.title)
            .limit(8)
        )
    ).scalars().all()
    unresolved_threads = [
        {
            "id": str(thread.id),
            "title": thread.title,
            "status": derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=book.total_chapters,
            ),
            "introduced_at": thread.introduced_at,
            "note": thread.note,
        }
        for thread in unresolved_threads_rows
        if is_plot_thread_open(
            derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=book.total_chapters,
            )
        )
    ]

    recent_summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(Chapter.book_id == book.id, ChapterSummary.mode == "short")
            .order_by(Chapter.number.desc())
            .limit(3)
        )
    ).all()
    recent_events: list[dict] = []
    for chapter_number, chapter_title, key_events in recent_summary_rows:
        for event in (key_events or [])[:2]:
            if isinstance(event, dict) and event.get("event"):
                recent_events.append({
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "detail": str(event.get("event")).strip(),
                })
    alerts: list[dict] = []
    dormant_rows = (
        await db.execute(
            select(Character.name, Character.last_seen_chapter, Character.mention_count)
            .where(
                Character.book_id == book.id,
                Character.last_seen_chapter.isnot(None),
                Character.mention_count >= 6,
            )
            .order_by(Character.mention_count.desc(), Character.last_seen_chapter)
            .limit(6)
        )
    ).all()
    for name, last_seen_chapter, mention_count in dormant_rows:
        if last_seen_chapter and total_chapters and total_chapters - last_seen_chapter >= 40:
            alerts.append({
                "kind": "dormant_character",
                "title": f"{name} has been absent for {total_chapters - last_seen_chapter} chapters",
                "body": f"Readers may notice if {name} mattered earlier but never returns. Decide whether to revive, reference, or close that thread.",
                "chapter_ref": last_seen_chapter,
            })
    recent_report = await build_chapter_consistency_report(db, book, total_chapters) if total_chapters else None
    for flag in (recent_report.continuity_flags if recent_report else [])[:2]:
        alerts.append({
            "kind": "continuity_risk",
            "title": "Readers might notice a continuity wobble",
            "body": flag,
            "chapter_ref": recent_report.chapter_number if recent_report else None,
        })
    return {
        "upcoming_chapter": upcoming_chapter,
        "active_characters": active_characters,
        "unresolved_threads": unresolved_threads,
        "recent_events": recent_events[:6],
        "alerts": alerts[:4],
    }
