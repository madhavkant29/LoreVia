"""Focused book imports workflows."""

from __future__ import annotations

import asyncio
import codecs
import os
import re
import uuid
import zipfile
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Chapter,
)
from app.utils.books import (
    book_text,
    manuscript,
    normalization,
)
from app.utils.books.structure_plan import (
    build_structure_plan,
    materialize_structure_plan,
    validate_structure_plan,
)


def report_sentence(text: str | None) -> str:
    cleaned = manuscript.clean_markdown_asterisks_str((text or "").strip())
    if not cleaned:
        return ""
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    return lines[0] if lines else ""


def require_extractable_manuscript_text(chapters: list[dict], format_name: str) -> None:
    """Reject image-only or empty document imports before they become empty chapters."""
    if any(
        re.sub(r"\[\[IMAGE:[^\]]+\]\]", "", str(chapter.get("text") or "")).strip()
        for chapter in chapters
    ):
        return
    raise HTTPException(
        400,
        f"No extractable text was found in this {format_name.upper()} file. Export a text-based copy or run OCR before importing.",
    )


def decode_manuscript_text(raw: bytes) -> str:
    """Decode common text-manuscript encodings without silently dropping bytes."""
    try:
        if raw.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
            text = raw.decode("utf-32")
        elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            text = raw.decode("utf-16")
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1252")
    except UnicodeError as exc:
        raise HTTPException(
            400,
            "This text file could not be decoded. Save it as UTF-8 and try again.",
        ) from exc
    if "\x00" in text:
        raise HTTPException(
            400,
            "This text file contains invalid control bytes. Save it as UTF-8 and try again.",
        )
    return text


# Document parsers raise many library-specific exception types for corrupt or
# malformed inputs. They all mean the same thing to an author: the file could
# not be read, so map them to one clear 400 response instead of leaking a 500.
try:  # pragma: no cover - python-docx is a hard dependency, import is defensive
    from docx.opc.exceptions import PackageNotFoundError
except ImportError:  # pragma: no cover
    PackageNotFoundError = ValueError

_UNREADABLE_DOCUMENT_EXCEPTIONS = (
    AttributeError,
    IndexError,
    KeyError,
    OSError,
    RuntimeError,
    ValueError,
    zipfile.BadZipFile,
    PackageNotFoundError,
)


def _unreadable_document_error(filename: str) -> HTTPException:
    label = filename if filename and filename not in {"preview", "this file"} else "this manuscript"
    return HTTPException(
        400,
        f"We couldn't read {label}. The file may be corrupted or partially "
        "saved. Try re-saving or re-exporting it, then upload it again.",
    )


def parse_document_or_400(parse: Any, raw: bytes, *, filename: str, **kwargs: Any) -> Any:
    """Run a synchronous parser, converting document errors into a 400."""
    try:
        return parse(raw, **kwargs)
    except _UNREADABLE_DOCUMENT_EXCEPTIONS as exc:
        raise _unreadable_document_error(filename) from exc


async def parse_document_or_400_async(
    parse: Any, raw: bytes, *, filename: str, **kwargs: Any
) -> Any:
    """Run a parser in a worker thread, converting document errors into a 400."""
    try:
        return await asyncio.to_thread(parse, raw, **kwargs)
    except _UNREADABLE_DOCUMENT_EXCEPTIONS as exc:
        raise _unreadable_document_error(filename) from exc


def _parse_docx_text(raw: bytes) -> str:
    from io import BytesIO

    from docx import Document
    from docx.table import Table

    doc = Document(BytesIO(raw))
    blocks: list[str] = []
    for item in doc.iter_inner_content():
        if isinstance(item, Table):
            for row in item.rows:
                cells = [" ".join(cell.text.split()) for cell in row.cells]
                row_text = " | ".join(cell for cell in cells if cell)
                if row_text:
                    blocks.append(row_text)
        elif item.text.strip():
            blocks.append(item.text.strip())
    text = "\n\n".join(blocks)
    return book_text._normalize_unicode_replacements(text)


def _sample_pdf_text(raw: bytes) -> str:
    import fitz

    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        pages = min(doc.page_count, 3)
        return "".join(doc.load_page(index).get_text() for index in range(pages))
    finally:
        doc.close()


def _sample_epub_text(raw: bytes) -> str:
    from io import BytesIO

    from bs4 import BeautifulSoup
    from ebooklib import epub as epub_lib

    book = epub_lib.read_epub(BytesIO(raw))
    sample_text = ""
    for item in book.get_items_of_type(9):  # ITEM_DOCUMENT
        soup = BeautifulSoup(item.get_content(), "html.parser")
        sample_text += soup.get_text()
        if len(sample_text) > 5000:
            break
    return sample_text


def parse_structured_prose_upload(
    *,
    format_name: str,
    raw: bytes,
    filename: str,
    proposed_plan: dict[str, Any] | None = None,
    language: str | None = None,
    include_block_context: bool = False,
) -> dict[str, Any]:
    """Use the same source-matched outline for preview and queued prose ingestion."""
    diagnostics: dict[str, Any] | None = None
    if format_name == "pdf":
        from app.parsers.pdf_parser import parse_pdf_structure

        parsed, diagnostics = parse_document_or_400(
            parse_pdf_structure, raw, filename=filename, language=language
        )
    elif format_name == "epub":
        from app.parsers.epub_parser import parse_epub_structure

        parsed = parse_document_or_400(parse_epub_structure, raw, filename=filename)
    elif format_name in {"docx", "doc"}:
        from app.parsers.docx_structure import parse_docx_structure

        parsed = parse_document_or_400(parse_docx_structure, raw, filename=filename)
    elif format_name in {"txt", "md"}:
        from app.parsers.text_parser import parse_text_structure

        source_text = decode_manuscript_text(raw)
        heading_language = language or (
            "en" if re.search(r"(?im)^\s*chapter\s+\d+\b", source_text) else None
        )
        parsed = parse_text_structure(
            source_text, language=heading_language, title=os.path.splitext(filename)[0]
        )
    elif format_name == "scrivener":
        from app.utils.scrivener_utils import parse_scrivener_archive

        parsed = parse_document_or_400(
            parse_scrivener_archive, raw, filename=filename, include_structure=True
        )
    else:
        raise ValueError(f"Unsupported format: {format_name}")
    require_extractable_manuscript_text(parsed, format_name)
    sample = " ".join(str(section.get("text") or "") for section in parsed)[:5000]
    detected_language = (
        language or (diagnostics.get("detected_language") if diagnostics else None) or "en"
    )
    if diagnostics is None and language is None:
        from app.utils.language_utils import detect_language

        detected_language = detect_language(sample)["detected"]
        if format_name in {"txt", "md"} and re.search(r"(?im)^\s*chapter\s+\d+\b", source_text):
            detected_language = "en"
    detected = build_structure_plan(raw, parsed, language=detected_language)
    plan = validate_structure_plan(proposed_plan, detected)
    chapters = materialize_structure_plan(plan)
    persisted_plan = {
        key: value
        for key, value in plan.items()
        if key not in {"blocks", "block_locations", "images_by_marker"}
    }
    persisted_plan["toc_entries"] = {
        section["id"]: plan["blocks"][section["start_block"] : section["end_block"]]
        for section in plan["sections"]
        if section["type"] == "toc"
    }
    persisted_plan["warnings"] = [
        {"message": warning, "section_id": section["id"], "severity": "warning"}
        for section in plan["sections"]
        for warning in section.get("warnings", [])
    ]
    result = {
        "chapters": chapters,
        "structure_plan": persisted_plan,
        "parser_diagnostics": diagnostics,
        "detected_language": detected_language,
        "block_count": len(detected["blocks"]),
    }
    if include_block_context:
        result.update(
            {
                "block_word_counts": [len(block.split()) for block in plan["blocks"]],
                "block_openings": [block[:180] for block in plan["blocks"]],
                "block_closings": [block[-180:] for block in plan["blocks"]],
                "block_locations": plan["block_locations"],
            }
        )
    return result


async def next_chapter_number(db: AsyncSession, book_id: uuid.UUID) -> int:
    current_max = await db.scalar(
        select(func.max(Chapter.number)).where(Chapter.book_id == book_id)
    )
    return int(current_max or 0) + 1


async def parse_import_upload(filename: str, raw: bytes, split_into_chapters: bool) -> list[dict]:
    lower = filename.lower()
    stem = os.path.splitext(os.path.basename(filename))[0] or "Imported chapter"
    if lower.endswith(".scrivzip") or lower.endswith(".scriv.zip"):
        from app.utils.scrivener_utils import parse_scrivener_archive

        chapters = await parse_document_or_400_async(
            parse_scrivener_archive, raw, filename=filename
        )
        if split_into_chapters:
            return chapters
        return [
            {
                "title": stem,
                "text": "\n\n".join(str(chapter.get("text") or "") for chapter in chapters),
                "number": 1,
            }
        ]
    if lower.endswith(".pdf"):
        from app.parsers.pdf_parser import parse_pdf

        chapters = await parse_document_or_400_async(
            parse_pdf, raw, filename=filename, split_large_chapters=False
        )
        require_extractable_manuscript_text(chapters, "pdf")
        if split_into_chapters and chapters:
            return chapters
        merged_text = "\n\n".join(
            (ch.get("text") or "").strip() for ch in chapters if ch.get("text")
        )
        return [{"title": stem, "text": merged_text or "", "number": 1}]
    if lower.endswith(".epub"):
        from app.parsers.epub_parser import parse_epub

        chapters = await parse_document_or_400_async(
            parse_epub, raw, filename=filename, split_large_chapters=False
        )
        require_extractable_manuscript_text(chapters, "epub")
        if split_into_chapters and chapters:
            return chapters
        merged_text = "\n\n".join(
            (ch.get("text") or "").strip() for ch in chapters if ch.get("text")
        )
        return [{"title": stem, "text": merged_text or "", "number": 1}]
    if lower.endswith(".docx"):
        text = parse_document_or_400(_parse_docx_text, raw, filename=filename)
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
            from docx.opc.exceptions import PackageNotFoundError

            doc = Document(BytesIO(raw))
            text = "\n".join(
                paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()
            )
            text = book_text._normalize_unicode_replacements(text)
            return [{"title": stem, "text": text, "number": 1}]
        except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError):
            raise HTTPException(
                400,
                "Legacy .doc files require additional system dependencies. Please convert to .docx format.",
            )
    if lower.endswith(".txt") or lower.endswith(".md") or lower.endswith(".fountain"):
        text = decode_manuscript_text(raw)
        text = book_text._normalize_unicode_replacements(text)
        if lower.endswith(".md"):
            # Convert markdown to HTML for proper rendering
            html = manuscript.markdown_to_html(text)
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
            speaker = _normalize_screenplay_character_name(
                str(dialogue.get("character_name") or "Unknown")
            )
            extension = " ".join(str(dialogue.get("character_extension") or "").split()).strip()
            parenthetical = " ".join(str(dialogue.get("parenthetical") or "").split()).strip()
            dialogue_text = " ".join(str(dialogue.get("dialogue_text") or "").split()).strip()
            if not dialogue_text:
                continue
            speaker_label = speaker
            if extension:
                speaker_label = f"{speaker_label} ({extension})"
            detail_parts = [f"({parenthetical})" if parenthetical else "", dialogue_text]
            dialogue_lines.append(
                f"{speaker_label}: {' '.join(part for part in detail_parts if part)}".strip()
            )

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

        parsed_pages = await parse_document_or_400_async(parse_pdf, raw, filename=filename)
        source_text = "\n\n".join(
            (chapter.get("text") or "").strip() for chapter in parsed_pages if chapter.get("text")
        )
    elif (
        lower.endswith(".txt")
        or lower.endswith(".md")
        or lower.endswith(".fountain")
        or lower.endswith(".screenplay")
        or lower.endswith(".script")
    ):
        source_text = decode_manuscript_text(raw)
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
    return normalization.infer_work_type_from_filename(filename) == "screenplay"


async def parse_book_upload_for_ingestion(
    *,
    format_name: str,
    work_type: str,
    raw: bytes,
    preserve_chapter_numbers: bool,
    preserve_source_chapters: bool,
    language: str | None = None,
    filename: str | None = None,
    proposed_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    display_filename = filename or normalization.upload_filename_for_format(format_name)
    if work_type == "screenplay":
        screenplay_payload = await parse_screenplay_upload(display_filename, raw)
        return {
            "chapters": screenplay_payload["chapters"],
            "screenplay_payload": screenplay_payload,
            "parser_diagnostics": None,
            "detected_language": language or "en",
        }

    parsed = await asyncio.to_thread(
        parse_structured_prose_upload,
        format_name=format_name,
        raw=raw,
        filename=display_filename,
        proposed_plan=proposed_plan,
        language=language,
    )
    return {**parsed, "screenplay_payload": None}


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
        title = book_text._clean_optional_text(
            " ".join(str(chapter.get("title") or "").split()).strip()
        )
        description = book_text._clean_optional_text(
            " ".join(str(chapter.get("description") or "").split()).strip()
        )
        chapter_kind = normalization.normalize_chapter_kind(
            chapter.get("chapter_kind") or chapter.get("section_type")
        )
        html = (
            manuscript.clean_manuscript_html(chapter.get("html")) if chapter.get("html") else None
        )
        images = list(chapter.get("images") or [])
        desired_number = chapter_number if replace_existing and chapter_number else running_number
        parts = (
            split_long_document(text)
            if chunk_long_documents and not preserve_exact_structure
            else [text]
        )
        for index, part in enumerate(parts, start=1):
            part_title = title
            if len(parts) > 1:
                base = title or f"Chapter {desired_number}"
                part_title = f"{base} (Part {index})"
            normalized.append(
                {
                    "number": desired_number,
                    "title": part_title,
                    "text": part,
                    "html": html if len(parts) == 1 else manuscript.manuscript_text_to_html(part),
                    "description": description,
                    "chapter_kind": chapter_kind if len(parts) == 1 else "chapter",
                    "structure_section_id": chapter.get("structure_section_id")
                    if len(parts) == 1
                    else None,
                    "include_in_analysis": chapter.get("include_in_analysis", True),
                    "images": images
                    if len(parts) == 1
                    else _filter_import_images_for_text(part, images),
                    "scene_heading": chapter.get("scene_heading"),
                    "scene_number": chapter.get("scene_number"),
                    "dialogue_count": chapter.get("dialogue_count"),
                }
            )
            desired_number += 1
        running_number = desired_number
    return normalized


def _filter_import_images_for_text(text: str, images: list[dict]) -> list[dict]:
    markers = {match.group(0) for match in re.finditer(r"\[\[IMAGE:[^\]]+\]\]", text or "")}
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
    from app.schemas.section import ImportPreview, ImportWarning, SectionMeta

    preview = ImportPreview()

    if work_type == "screenplay":
        from app.parsers.screenplay_parser import parse_screenplay

        if format_name == "pdf":
            from app.parsers.pdf_parser import parse_pdf

            parsed_pages = parse_document_or_400(
                parse_pdf, raw, filename="preview", split_large_chapters=False
            )
            require_extractable_manuscript_text(parsed_pages, "pdf")
            source_text = "\n\n".join(
                str(chapter.get("text") or "").strip()
                for chapter in parsed_pages
                if chapter.get("text")
            )
        elif format_name in ("txt", "md", "fountain", "screenplay", "script"):
            source_text = decode_manuscript_text(raw)
        else:
            raise HTTPException(400, f"Unsupported screenplay format: {format_name}")
        scenes = parse_screenplay(source_text)
        sections: list[SectionMeta] = []
        for i, scene in enumerate(scenes, start=1):
            scene_title = getattr(scene, "text", f"Scene {i}")
            sections.append(
                SectionMeta.from_heading(
                    title=str(scene_title).strip() or f"Scene {i}",
                    type_="chapter",
                    number=i,
                )
            )
        preview.sections = sections
        preview.chapter_count = len(sections)
        preview.total_words = len(source_text.split())
        preview.source_size_bytes = len(raw)
        preview.compute_confidence()
        return preview.model_dump()

    try:
        parsed = parse_structured_prose_upload(
            format_name=format_name,
            raw=raw,
            filename="preview",
            language=language,
            include_block_context=True,
        )
    except HTTPException as exc:
        if format_name != "pdf" or "No extractable text" not in str(exc.detail):
            raise
        preview.raw_diagnostics = {"anomalies": ["no_extractable_text"]}
        preview.warnings = [
            ImportWarning(
                message="This PDF has no extractable text. Export a text-based PDF or OCR it before importing."
            )
        ]
        preview.source_size_bytes = len(raw)
        return preview.model_dump()
    plan = parsed["structure_plan"]
    sections = [SectionMeta.model_validate(item) for item in plan["sections"]]
    preview.sections = sections
    preview.source_sha256 = plan["source_sha256"]
    preview.content_sha256 = plan["content_sha256"]
    preview.parser_version = plan["parser_version"]
    preview.block_count = parsed["block_count"]
    preview.block_word_counts = parsed["block_word_counts"]
    preview.block_openings = parsed["block_openings"]
    preview.block_closings = parsed["block_closings"]
    preview.block_locations = parsed["block_locations"]
    preview.detected_language = parsed["detected_language"]
    preview.chapter_count = sum(section.type == "chapter" for section in sections)
    preview.toc_detected = any(section.type == "toc" for section in sections)
    preview.front_matter_count = sum(
        section.type in {"notes", "chronology", "preface", "foreword", "dedication"}
        for section in sections
    )
    preview.total_words = sum(
        section.word_count for section in sections if section.type not in {"part", "toc"}
    )
    preview.source_size_bytes = len(raw)
    preview.raw_diagnostics = parsed["parser_diagnostics"]
    preview.warnings = [
        ImportWarning(message=warning, section_id=section.id)
        for section in sections
        for warning in section.warnings
    ]
    preview.warnings.extend(
        ImportWarning(
            message="Table of contents detected; its entries are structural hints, not story chapters.",
            section_id=section.id,
        )
        for section in sections
        if section.type == "toc"
    )
    oversized_part_openings = [
        section
        for section in sections
        if section.type == "part_opening" and section.word_count > 5000
    ]
    preview.warnings.extend(
        ImportWarning(
            message="This Part contains over 5,000 words without detected chapter boundaries. Review the chapter split before importing.",
            section_id=section.id,
        )
        for section in oversized_part_openings
    )
    for anomaly in (parsed["parser_diagnostics"] or {}).get("anomalies", []):
        preview.warnings.append(ImportWarning(message=f"Source extraction needs review: {anomaly}"))
    if any(section.type == "unknown" for section in sections):
        preview.warnings.append(
            ImportWarning(
                message="Unclassified text will be imported for reading and included in AI analysis. It may include supplemental material."
            )
        )
    preview.confidence = round(
        1 - min(0.75, 0.25 * sum(section.type == "unknown" for section in sections)), 2
    )
    if oversized_part_openings:
        preview.confidence = min(preview.confidence, 0.5)
    return preview.model_dump()
