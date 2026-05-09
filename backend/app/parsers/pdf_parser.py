from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Sequence
from typing import Any, cast

import fitz

CHAPTER_RE = re.compile(
    r"^(?:(?:chapter|ch\.?|part|volume|vol\.?|book|act|episode|section|scene)\s+"
    r"(?:\d+[a-z]?|[ivxlcdm]+|[a-z]{1,3}|[a-z]+(?:[-\s][a-z]+)*)"
    r"(?:\s*[:.\-]\s*.+)?|prologue|epilogue|interlude|afterword|appendix(?:\s+[a-z0-9]+)?)$",
    re.IGNORECASE,
)
UPPER_HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9\s'\",:;.!?\-]{2,60}$")
ROMAN_HEADING_RE = re.compile(r"^[IVXLCDM]{1,12}[.: -]?$", re.IGNORECASE)
FRONT_MATTER_RE = re.compile(
    r"(translated by|illustrations? by|compiled/formatted by|edited by|proofread by|typeset by|"
    r"cover (?:art|design) by|project gutenberg|all rights reserved|table of contents|copyright|isbn|"
    r"contents|dedication|acknowledg(?:e)?ments?)",
    re.IGNORECASE,
)
ORNAMENT_RE = re.compile(r"[\u2600-\u27ff\u3000-\u303f\uFF00-\uFFEF\U0001F000-\U0001F9FF]+")
MEDIA_MARKER_TEMPLATE = "[[IMAGE:{marker}]]"
MEDIA_MARKER_RE = re.compile(r"\[\[IMAGE:[^\]]+\]\]")
PARAGRAPH_SPLIT_TARGET_WORDS = 7000
HEADER_ZONE_RATIO = 0.12
FOOTER_ZONE_RATIO = 0.10
MIN_SUSPICIOUS_CHAPTER_WORDS = 14000
HEADING_FALLBACK_RE = re.compile(
    r"^(chapter|ch\.?|part|volume|vol\.?|book|act|episode|section|scene|prologue|epilogue|interlude|afterword|appendix)\b",
    re.IGNORECASE,
)
NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
    "fortieth": 40,
    "fiftieth": 50,
    "sixtieth": 60,
    "seventieth": 70,
    "eightieth": 80,
    "ninetieth": 90,
}
LETTER_HEADING_RE = re.compile(r"^[a-z]{1,3}$", re.IGNORECASE)
HEADING_NUMBER_RE = re.compile(
    r"^(?:chapter|ch\.?|part|volume|vol\.?|book|act|episode|section|scene)\s+([a-z0-9ivxlcdm]+(?:[-\s][a-z0-9ivxlcdm]+)*)\b",
    re.IGNORECASE,
)
PAGINATION_RE = re.compile(
    r"^(?:page\s+)?\d+\s+(?:of|/)\s+\d+(?:\s+[A-Za-z])?$",
    re.IGNORECASE,
)


def parse_pdf(raw_bytes: bytes, *, split_large_chapters: bool = True) -> list[dict]:
    chapters, _ = parse_pdf_with_diagnostics(raw_bytes, split_large_chapters=split_large_chapters)
    return chapters


def parse_pdf_with_diagnostics(raw_bytes: bytes, *, split_large_chapters: bool = True) -> tuple[list[dict], dict[str, Any]]:
    return _parse_pdf_internal(raw_bytes, split_large_chapters=split_large_chapters)


def _parse_pdf_internal(raw_bytes: bytes, *, split_large_chapters: bool) -> tuple[list[dict], dict[str, Any]]:
    doc = cast(Any, fitz).open(stream=raw_bytes, filetype="pdf")
    try:
        total_pages = int(doc.page_count or 0)
        repeated_noise = _detect_repeated_headers(doc)
        stream = []
        diagnostics_state = {
            "text_line_count": 0,
            "noise_lines_removed": 0,
            "noise_reason_counts": Counter(),
            "inline_artifacts_removed": 0,
        }

        for page_number, page in enumerate(doc, start=1):
            page_height = float(cast(Any, page).rect.height or 0)
            pending_lines: list[dict] = []
            for item in _page_blocks(page):
                if item["type"] == "text":
                    cleaned = _clean_text(item["text"])
                    if not cleaned:
                        continue
                    diagnostics_state["text_line_count"] += 1
                    noise_reason = _page_margin_noise_reason(
                        cleaned,
                        bbox=item["bbox"],
                        page_height=page_height,
                        repeated_noise=repeated_noise,
                        total_pages=total_pages,
                        page_number=page_number,
                    )
                    if noise_reason:
                        diagnostics_state["noise_lines_removed"] += 1
                        diagnostics_state["noise_reason_counts"][noise_reason] += 1
                        continue
                    pending_lines.append({"text": cleaned, "bbox": item["bbox"]})
                    continue

                stream.extend(
                    _line_items_to_paragraph_items(
                        pending_lines,
                        page_number=page_number,
                        total_pages=total_pages,
                        diagnostics_state=diagnostics_state,
                    )
                )
                pending_lines = []
                stream.append(
                    {
                        "type": "image",
                        "bytes": item["bytes"],
                        "content_type": item["content_type"],
                        "filename": item["filename"],
                        "page": page_number,
                        "bbox": item["bbox"],
                    }
                )

            stream.extend(
                _line_items_to_paragraph_items(
                    pending_lines,
                    page_number=page_number,
                    total_pages=total_pages,
                    diagnostics_state=diagnostics_state,
                )
            )

        chapters = _build_chapters(stream)
        initial_anomalies = _collect_parse_anomalies(chapters, total_pages=total_pages)
        fallback_strategy: str | None = None
        if _should_retry_with_permissive_headings(chapters, anomalies=initial_anomalies):
            permissive_chapters = _build_chapters(stream, permissive_headings=True)
            if _parse_quality_score(permissive_chapters) > _parse_quality_score(chapters):
                chapters = permissive_chapters
                fallback_strategy = "permissive_heading_retry"

        effective_split = split_large_chapters or _needs_forced_large_chapter_split(chapters, total_pages=total_pages)
        normalized_chapters = _normalize_chapters(
            chapters,
            split_large_chapters=effective_split,
            total_pages=total_pages,
        )
        final_anomalies = _collect_parse_anomalies(chapters, total_pages=total_pages, normalized_chapters=normalized_chapters)
        diagnostics = _build_parser_diagnostics(
            chapters,
            normalized_chapters=normalized_chapters,
            total_pages=total_pages,
            repeated_noise=repeated_noise,
            fallback_strategy=fallback_strategy,
            forced_large_chapter_split=effective_split and not split_large_chapters,
            anomalies=final_anomalies,
            diagnostics_state=diagnostics_state,
        )
        return normalized_chapters or [{"number": 1, "title": "Full Text", "text": "", "images": []}], diagnostics
    finally:
        doc.close()


def extract_first_page_cover(raw_bytes: bytes) -> tuple[bytes, str] | None:
    doc = cast(Any, fitz).open(stream=raw_bytes, filetype="pdf")
    try:
        if doc.page_count == 0:
            return None
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200, alpha=False, annots=True)
        return pix.tobytes("png"), "image/png"
    finally:
        doc.close()


def _page_blocks(page: fitz.Page) -> list[dict]:
    page_any = cast(Any, page)
    items: list[dict] = []

    raw_dict = page_any.get_text("dict")
    for block in raw_dict.get("blocks", []):
        block_type = block.get("type")
        if block_type == 0:
            for line in block.get("lines", []):
                text = _extract_line_text(line)
                if not text.strip():
                    continue
                bbox = tuple(line.get("bbox") or block.get("bbox") or (0, 0, 0, 0))
                items.append(
                    {
                        "type": "text",
                        "bbox": _normalize_bbox(bbox),
                        "text": text,
                    }
                )
            continue

        if block_type == 1:
            raw = block.get("image")
            if not raw:
                continue
            ext = block.get("ext") or "png"
            items.append(
                {
                    "type": "image",
                    "bbox": _normalize_bbox(tuple(block.get("bbox") or (0, 0, 0, 0))),
                    "bytes": raw,
                    "content_type": f"image/{ext.lower()}",
                    "filename": f"{uuid.uuid4().hex}.{ext.lower()}",
                }
            )

    return sorted(items, key=lambda item: (item["bbox"][1], item["bbox"][0]))


def _extract_line_text(line: dict[str, Any]) -> str:
    parts: list[str] = []
    for span in line.get("spans", []):
        text = span.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return "".join(parts)


def _normalize_bbox(bbox: tuple[Any, ...]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (list(bbox) + [0, 0, 0, 0])[:4]
    return float(x0), float(y0), float(x1), float(y1)


def _line_items_to_paragraph_items(
    lines: list[dict],
    *,
    page_number: int,
    total_pages: int,
    diagnostics_state: dict[str, Any] | None = None,
) -> list[dict]:
    if not lines:
        return []

    typical_line_height = _median(
        [
            max(1.0, float(line["bbox"][3]) - float(line["bbox"][1]))
            for line in lines
        ]
    )
    paragraphs: list[dict] = []
    current: list[dict] = []

    for line in lines:
        if current and _should_break_between_lines(current[-1], line, typical_line_height):
            paragraph = _paragraph_item_from_lines(
                current,
                page_number=page_number,
                total_pages=total_pages,
                diagnostics_state=diagnostics_state,
            )
            if paragraph is not None:
                paragraphs.append(paragraph)
            current = []
        current.append(line)

    if current:
        paragraph = _paragraph_item_from_lines(
            current,
            page_number=page_number,
            total_pages=total_pages,
            diagnostics_state=diagnostics_state,
        )
        if paragraph is not None:
            paragraphs.append(paragraph)

    return paragraphs


def _should_break_between_lines(previous_line: dict, current_line: dict, typical_line_height: float) -> bool:
    previous_text = str(previous_line.get("text") or "").strip()
    current_text = str(current_line.get("text") or "").strip()
    if not previous_text or not current_text:
        return False
    if _extract_heading(current_text):
        return True

    previous_bbox = _normalize_bbox(tuple(previous_line.get("bbox") or (0, 0, 0, 0)))
    current_bbox = _normalize_bbox(tuple(current_line.get("bbox") or (0, 0, 0, 0)))
    vertical_gap = current_bbox[1] - previous_bbox[3]
    indent_delta = current_bbox[0] - previous_bbox[0]

    if vertical_gap > max(6.0, typical_line_height * 0.65):
        return True
    if indent_delta > max(10.0, typical_line_height * 0.75):
        return True
    return False


def _paragraph_item_from_lines(
    lines: list[dict],
    *,
    page_number: int,
    total_pages: int,
    diagnostics_state: dict[str, Any] | None = None,
) -> dict | None:
    text = "\n".join(str(line.get("text") or "") for line in lines if str(line.get("text") or "").strip())
    cleaned = _clean_text(text)
    cleaned, removed_count = _scrub_inline_page_artifacts(cleaned, total_pages=total_pages, page_number=page_number)
    if diagnostics_state is not None:
        diagnostics_state["inline_artifacts_removed"] += removed_count
    if not cleaned:
        return None

    x0 = min(float(line["bbox"][0]) for line in lines)
    y0 = min(float(line["bbox"][1]) for line in lines)
    x1 = max(float(line["bbox"][2]) for line in lines)
    y1 = max(float(line["bbox"][3]) for line in lines)
    return {
        "type": "text",
        "text": cleaned,
        "page": page_number,
        "bbox": (x0, y0, x1, y1),
    }


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _blocks_to_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        return []
    parts = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if parts:
        merged_parts: list[str] = []
        for part in parts:
            merged_parts.extend(_merge_soft_wrapped_lines(part))
        return [part for part in merged_parts if part]
    return [normalized]


def _merge_soft_wrapped_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    paragraphs: list[str] = []
    current = lines[0]

    for line in lines[1:]:
        if _should_start_new_paragraph(current, line):
            paragraphs.append(current.strip())
            current = line
            continue
        current = f"{current} {line}".strip()

    if current:
        paragraphs.append(current.strip())
    return paragraphs


def _build_chapters(stream: list[dict], *, permissive_headings: bool = False) -> list[dict]:
    chapters: list[dict] = []
    current = _blank_chapter(1)

    for index, item in enumerate(stream):
        if item["type"] == "text":
            next_text = None
            if index + 1 < len(stream) and stream[index + 1]["type"] == "text":
                next_text = stream[index + 1]["text"]
            heading = _extract_heading(
                item["text"],
                next_text=next_text,
                permissive=permissive_headings,
            )
            if heading:
                remainder = _heading_remainder(item["text"], heading)
                if _chapter_has_content(current):
                    chapters.append(current)
                    current = _blank_chapter(len(chapters) + 1, heading)
                else:
                    current["title"] = heading
                if remainder:
                    current["text_parts"].append(remainder)
                continue

            if not _chapter_has_content(current) and _is_probable_front_matter(item["text"]):
                continue

            if current["text_parts"]:
                previous = current["text_parts"][-1]
                if (
                    isinstance(previous, str)
                    and not MEDIA_MARKER_RE.fullmatch(previous.strip())
                    and _should_merge_across_pages(previous, item["text"])
                ):
                    current["text_parts"][-1] = f"{previous} {item['text']}".strip()
                    continue

            current["text_parts"].append(item["text"])
            continue

        if not current["title"] and not _chapter_has_content(current):
            current["title"] = "Opening"

        marker = MEDIA_MARKER_TEMPLATE.format(marker=uuid.uuid4().hex)
        current["text_parts"].append(marker)
        current["images"].append(
            {
                "marker": marker,
                "bytes": item["bytes"],
                "content_type": item["content_type"],
                "filename": item["filename"],
            }
        )

    if _chapter_has_content(current) or current["images"]:
        chapters.append(current)

    return chapters


def _normalize_chapters(chapters: list[dict], *, split_large_chapters: bool, total_pages: int) -> list[dict]:
    normalized: list[dict] = []
    next_number = 1
    for chapter in chapters:
        text_parts = _drop_front_matter_text_parts(chapter["text_parts"])
        if not any(part.strip() for part in text_parts) and not chapter["images"]:
            continue
        split_parts = _split_large_chapter_parts(text_parts) if split_large_chapters else [text_parts]
        chapter_title = chapter.get("title") or f"Chapter {next_number}"
        source_number = _extract_source_number_from_heading(chapter.get("title"))
        for part_index, text_parts_part in enumerate(split_parts, start=1):
            text = _assemble_text_parts(text_parts_part, total_pages=total_pages)
            if not text and not chapter["images"]:
                continue
            title = chapter_title
            if len(split_parts) > 1:
                title = f"{chapter_title} - Part {part_index}"
            normalized.append(
                {
                    "number": next_number,
                    "title": title,
                    "text": text,
                    "images": _images_for_text_parts(text_parts_part, chapter["images"]),
                    "source_number": source_number if len(split_parts) == 1 else None,
                }
            )
            next_number += 1
    return normalized


def _extract_source_number_from_heading(title: str | None) -> int | None:
    if not title:
        return None
    match = HEADING_NUMBER_RE.match(title.strip())
    if not match:
        return None
    raw_number = match.group(1).strip().lower().rstrip(".:-")
    if raw_number.isdigit():
        return int(raw_number)
    digit_with_suffix = re.fullmatch(r"(\d+)[a-z]", raw_number)
    if digit_with_suffix:
        return int(digit_with_suffix.group(1))
    if raw_number in NUMBER_WORDS:
        return NUMBER_WORDS[raw_number]
    if raw_number in ORDINAL_WORDS:
        return ORDINAL_WORDS[raw_number]
    word_number = _word_number_to_int(raw_number)
    if word_number is not None:
        return word_number
    if len(raw_number) > 1 and re.fullmatch(r"[ivxlcdm]+", raw_number):
        roman_value = _roman_to_int(raw_number)
        if roman_value and roman_value > 0:
            return roman_value
    letter_number = _letter_sequence_to_int(raw_number)
    if letter_number is not None:
        return letter_number
    roman_value = _roman_to_int(raw_number)
    return roman_value if roman_value and roman_value > 0 else None


def _word_number_to_int(value: str) -> int | None:
    normalized = value.strip().lower().replace("-", " ")
    parts = [part for part in normalized.split() if part]
    if not parts:
        return None
    if len(parts) == 1:
        if parts[0] in NUMBER_WORDS:
            return NUMBER_WORDS[parts[0]]
        if parts[0] in ORDINAL_WORDS:
            return ORDINAL_WORDS[parts[0]]
        return None
    if len(parts) != 2:
        return None

    tens, ones = parts
    if tens not in NUMBER_WORDS or NUMBER_WORDS[tens] < 20 or NUMBER_WORDS[tens] % 10 != 0:
        return None
    if ones in NUMBER_WORDS and 0 < NUMBER_WORDS[ones] < 10:
        return NUMBER_WORDS[tens] + NUMBER_WORDS[ones]
    if ones in ORDINAL_WORDS and 0 < ORDINAL_WORDS[ones] < 10:
        return NUMBER_WORDS[tens] + ORDINAL_WORDS[ones]
    return None


def _letter_sequence_to_int(value: str) -> int | None:
    normalized = value.strip().lower()
    if not LETTER_HEADING_RE.fullmatch(normalized):
        return None
    total = 0
    for char in normalized:
        total = (total * 26) + (ord(char) - ord("a") + 1)
    return total or None


def _roman_to_int(value: str) -> int | None:
    roman_map = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    previous = 0
    for char in reversed(value.lower()):
        current = roman_map.get(char)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total or None


def _blank_chapter(number: int, title: str | None = None) -> dict:
    return {
        "number": number,
        "title": title,
        "text_parts": [],
        "images": [],
    }


def _chapter_has_content(chapter: dict) -> bool:
    return any(
        part.strip() and not MEDIA_MARKER_RE.fullmatch(part.strip())
        for part in chapter["text_parts"]
    )


def _detect_repeated_headers(doc: fitz.Document) -> set[str]:
    doc_any = cast(Any, doc)
    seen: list[str] = []
    for page in doc_any:
        page_any = cast(Any, page)
        height = float(page_any.rect.height or 0)
        for item in _page_blocks(page_any):
            if item["type"] != "text":
                continue
            cleaned = _clean_text(item["text"])
            if not cleaned or len(cleaned) > 120:
                continue
            near_top = float(item["bbox"][1]) <= min(80.0, height * HEADER_ZONE_RATIO)
            near_bottom = float(item["bbox"][3]) >= max(0.0, height * (1.0 - FOOTER_ZONE_RATIO))
            if near_top or near_bottom:
                seen.append(cleaned.lower())
    counts = Counter(seen)
    return {text for text, count in counts.items() if count >= 3}


def _is_repeated_noise(text: str, repeated_noise: set[str]) -> bool:
    lowered = text.lower()
    return lowered in repeated_noise or lowered.isdigit() or _is_pagination_noise(text)


def _extract_heading(text: str, *, next_text: str | None = None, permissive: bool = False) -> str | None:
    lines = [line.strip() for line in text.replace("\r", "\n").splitlines() if line.strip()]
    if not lines:
        return None
    first_line = _normalize_heading_candidate(lines[0]).strip(" .:-")
    if not first_line:
        return None
    if CHAPTER_RE.match(first_line):
        return first_line
    heading_candidate = None
    score = 0
    if ROMAN_HEADING_RE.match(first_line):
        heading_candidate = first_line.rstrip(".:-").upper()
        score += 4
    if UPPER_HEADING_RE.match(first_line) and len(first_line.split()) <= 8:
        heading_candidate = heading_candidate or first_line.title()
        score += 2
    if len(first_line.split()) <= 6 and len(first_line) <= 40:
        score += 1
    if next_text and _count_words(next_text) >= 12:
        score += 1
    threshold = 3 if permissive else 4
    if heading_candidate and score >= threshold:
        return heading_candidate
    cleaned_line = re.sub(r"[^\w\s]", "", first_line).strip()
    if cleaned_line and HEADING_FALLBACK_RE.match(cleaned_line):
        return cleaned_line
    return None


def _normalize_heading_candidate(text: str) -> str:
    cleaned = text.strip()
    cleaned = ORNAMENT_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(" .", ".").strip(" .:-")
    return cleaned


def _is_pagination_noise(
    text: str,
    *,
    total_pages: int | None = None,
    page_number: int | None = None,
) -> bool:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return False
    counter = _match_pagination_counter(normalized)
    if counter is None:
        return False
    current, total = counter
    if total_pages is not None and total != total_pages:
        return False
    if page_number is not None and current not in {page_number - 1, page_number, page_number + 1}:
        return False
    return True


def _match_pagination_counter(text: str) -> tuple[int, int] | None:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized or not PAGINATION_RE.fullmatch(normalized):
        return None
    numbers = [int(match) for match in re.findall(r"\d+", normalized)]
    if len(numbers) < 2:
        return None
    current, total = numbers[0], numbers[1]
    if current < 1 or total < 1 or current > total:
        return None
    return current, total


def _page_margin_noise_reason(
    text: str,
    *,
    bbox: tuple[float, float, float, float],
    page_height: float,
    repeated_noise: set[str],
    total_pages: int,
    page_number: int,
) -> str | None:
    normalized = " ".join(str(text or "").split()).strip()
    if not normalized:
        return "empty_margin_line"

    lowered = normalized.lower()
    near_top = bbox[1] <= min(80.0, page_height * HEADER_ZONE_RATIO)
    near_bottom = bbox[3] >= max(0.0, page_height * (1.0 - FOOTER_ZONE_RATIO))
    if not (near_top or near_bottom):
        return None
    if lowered in repeated_noise:
        return "repeated_margin_noise"
    if _is_pagination_noise(normalized, total_pages=total_pages, page_number=page_number):
        return "pagination_counter"
    if near_bottom and normalized.isdigit() and int(normalized) in {page_number, total_pages}:
        return "folio_number"
    return None


def _is_page_margin_noise(
    text: str,
    *,
    bbox: tuple[float, float, float, float],
    page_height: float,
    repeated_noise: set[str],
    total_pages: int,
    page_number: int,
) -> bool:
    return _page_margin_noise_reason(
        text,
        bbox=bbox,
        page_height=page_height,
        repeated_noise=repeated_noise,
        total_pages=total_pages,
        page_number=page_number,
    ) is not None


def _heading_remainder(text: str, heading: str) -> str:
    raw = text.replace("\r", "\n").strip()
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return ""
    normalized_first = _normalize_heading_candidate(lines[0])
    if normalized_first.lower() == heading.lower():
        # Clean each line to remove ornaments
        remainder_lines = [_clean_text(line) for line in lines[1:]]
        # Filter out empty lines after cleaning
        remainder_lines = [line for line in remainder_lines if line.strip()]
        # Join and clean again to catch any remaining ornaments
        result = "\n".join(remainder_lines).strip()
        return _clean_text(result)
    # Try to match heading in the flattened text and extract remainder
    flattened = _normalize_heading_candidate(raw)
    match = re.match(re.escape(heading) + r"[\s:.\-]*", flattened, flags=re.IGNORECASE)
    if not match:
        return ""
    remainder = flattened[match.end():].strip()
    # Clean the remainder to remove any remaining ornaments
    return _clean_text(remainder)


def _clean_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = normalized.replace("\u00ad", "")
    # Remove special Unicode symbols including black diamond (u2726) and place of interest (u2318)
    normalized = ORNAMENT_RE.sub("", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"[^\S\n]+([,.;:!?])", r"\1", normalized)
    normalized = re.sub(r"([A-Za-z0-9])-\n([A-Za-z0-9])", r"\1\2", normalized)
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", normalized)
    normalized = re.sub(r" {2,}", " ", normalized)
    return normalized.strip()


def _scrub_inline_page_artifacts(
    text: str,
    *,
    total_pages: int | None,
    page_number: int | None = None,
) -> tuple[str, int]:
    if not text:
        return "", 0

    removed = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal removed
        matched = match.group(0)
        if not _is_pagination_noise(matched, total_pages=total_pages, page_number=page_number):
            return matched
        removed += 1
        return " "

    cleaned = re.sub(
        r"(?<!\w)(?:page\s+)?\d+\s*(?:of|/)\s*\d+(?:\s+[A-Za-z])?(?!\w)",
        _replace,
        text,
        flags=re.IGNORECASE,
    )
    return _clean_text(cleaned), removed


def _should_start_new_paragraph(previous: str, current: str) -> bool:
    previous = previous.strip()
    current = current.strip()
    if not previous:
        return True
    if not current:
        return False
    if MEDIA_MARKER_RE.fullmatch(previous) or MEDIA_MARKER_RE.fullmatch(current):
        return True
    if re.search(r"[.!?][\"')\]]*$", previous):
        return bool(re.match(r"^[A-Z0-9\"“‘(\[]", current))
    return False


def _assemble_text_parts(text_parts: list[str], *, total_pages: int | None = None) -> str:
    parts = [part.strip() for part in text_parts if part and part.strip()]
    cleaned, _ = _scrub_inline_page_artifacts("\n\n".join(parts), total_pages=total_pages)
    return cleaned


def _drop_front_matter_paragraphs(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    while paragraphs and _is_probable_front_matter(paragraphs[0]):
        paragraphs.pop(0)
    return "\n\n".join(paragraphs)


def _drop_front_matter_text_parts(text_parts: list[str]) -> list[str]:
    parts = [part.strip() for part in text_parts if part and part.strip()]
    preserved_prefix: list[str] = []
    while parts:
        if MEDIA_MARKER_RE.fullmatch(parts[0]):
            preserved_prefix.append(parts.pop(0))
            continue
        normalized = MEDIA_MARKER_RE.sub(" ", parts[0]).strip()
        if not normalized:
            parts.pop(0)
            continue
        if _is_probable_front_matter(normalized):
            parts.pop(0)
            continue
        break
    return preserved_prefix + parts


def _split_large_chapter_parts(text_parts: list[str]) -> list[list[str]]:
    if not text_parts:
        return []

    sections: list[list[str]] = []
    current: list[str] = []
    current_words = 0

    for part in text_parts:
        part_words = _count_words(part)
        projected_words = current_words + part_words
        should_split = (
            current
            and projected_words > PARAGRAPH_SPLIT_TARGET_WORDS
            and _can_close_section(current)
        )
        if should_split:
            sections.append(current)
            current = []
            current_words = 0
        current.append(part)
        current_words += part_words

    if current:
        sections.append(current)
    return sections


def _count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", MEDIA_MARKER_RE.sub(" ", text)))


def _can_close_section(parts: list[str]) -> bool:
    for part in reversed(parts):
        stripped = MEDIA_MARKER_RE.sub(" ", part).strip()
        if not stripped:
            continue
        return bool(re.search(r"[.!?][\"')\]]*\s*$", stripped))
    return False


def _images_for_text_parts(text_parts: list[str], images: list[dict]) -> list[dict]:
    markers = {
        match.group(0)
        for part in text_parts
        for match in MEDIA_MARKER_RE.finditer(part)
    }
    return [image for image in images if image.get("marker") in markers]


def _is_probable_front_matter(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    if FRONT_MATTER_RE.search(cleaned):
        return True
    if cleaned.lower().startswith("volume ") and len(cleaned.split()) <= 16:
        return True
    if len(cleaned) <= 80 and cleaned.lower().startswith("by "):
        return True
    return False


def _should_merge_across_pages(previous: str, current: str) -> bool:
    previous = _clean_text(previous)
    current = _clean_text(current)
    if not previous or not current:
        return False
    if _extract_heading(current):
        return False
    return previous[-1] not in ".!?\"'"


def _needs_forced_large_chapter_split(chapters: list[dict], *, total_pages: int) -> bool:
    word_counts = [_chapter_word_count(chapter) for chapter in chapters if _chapter_word_count(chapter) > 0]
    if not word_counts:
        return False

    largest = max(word_counts)
    if largest < MIN_SUSPICIOUS_CHAPTER_WORDS:
        return False

    median_words = _median([float(count) for count in word_counts])
    if len(word_counts) == 1:
        return total_pages >= 80 or largest >= PARAGRAPH_SPLIT_TARGET_WORDS * 3
    return largest >= max(PARAGRAPH_SPLIT_TARGET_WORDS * 2, int(median_words * 3))


def _chapter_word_count(chapter: dict) -> int:
    return sum(_count_words(str(part or "")) for part in chapter.get("text_parts", []))


def _collect_parse_anomalies(
    chapters: Sequence[dict],
    *,
    total_pages: int,
    normalized_chapters: Sequence[dict] | None = None,
) -> list[str]:
    anomalies: list[str] = []
    word_counts = [_chapter_word_count(chapter) for chapter in chapters if _chapter_word_count(chapter) > 0]
    if word_counts:
        largest = max(word_counts)
        median_words = _median([float(count) for count in word_counts])
        if median_words and largest >= max(PARAGRAPH_SPLIT_TARGET_WORDS * 2, int(median_words * 3)):
            anomalies.append("oversized_chapter_outlier")

    if _has_heading_style_dropout(chapters):
        anomalies.append("heading_style_dropout")

    if normalized_chapters:
        residual_artifacts = sum(_count_residual_page_artifacts(str(chapter.get("text") or ""), total_pages=total_pages) for chapter in normalized_chapters)
        if residual_artifacts:
            anomalies.append("residual_page_artifacts")

    return sorted(dict.fromkeys(anomalies))


def _has_heading_style_dropout(chapters: Sequence[dict]) -> bool:
    if len(chapters) < 4:
        return False

    explicit_indices = [
        index
        for index, chapter in enumerate(chapters)
        if str(chapter.get("title") or "").strip()
    ]
    if len(explicit_indices) < 3:
        return False
    last_explicit_index = explicit_indices[-1]
    if last_explicit_index >= len(chapters) - 1:
        return False

    trailing_word_count = sum(_chapter_word_count(chapter) for chapter in chapters[last_explicit_index + 1 :])
    return trailing_word_count >= MIN_SUSPICIOUS_CHAPTER_WORDS


def _should_retry_with_permissive_headings(chapters: Sequence[dict], *, anomalies: Sequence[str]) -> bool:
    return any(flag in {"oversized_chapter_outlier", "heading_style_dropout"} for flag in anomalies)


def _parse_quality_score(chapters: Sequence[dict]) -> tuple[int, int, int, int]:
    explicit_heading_count = sum(1 for chapter in chapters if str(chapter.get("title") or "").strip())
    word_counts = [_chapter_word_count(chapter) for chapter in chapters if _chapter_word_count(chapter) > 0]
    largest = max(word_counts) if word_counts else 0
    return (
        explicit_heading_count,
        len(chapters),
        -largest,
        -sum(1 for count in word_counts if count >= MIN_SUSPICIOUS_CHAPTER_WORDS),
    )


def _count_residual_page_artifacts(text: str, *, total_pages: int) -> int:
    if not text:
        return 0
    count = 0
    for match in re.finditer(r"(?<!\w)(?:page\s+)?\d+\s*(?:of|/)\s*\d+(?:\s+[A-Za-z])?(?!\w)", text, flags=re.IGNORECASE):
        if _is_pagination_noise(match.group(0), total_pages=total_pages):
            count += 1
    return count


def _build_parser_diagnostics(
    chapters: Sequence[dict],
    *,
    normalized_chapters: Sequence[dict],
    total_pages: int,
    repeated_noise: set[str],
    fallback_strategy: str | None,
    forced_large_chapter_split: bool,
    anomalies: Sequence[str],
    diagnostics_state: dict[str, Any],
) -> dict[str, Any]:
    word_counts = [_count_words(str(chapter.get("text") or "")) for chapter in normalized_chapters if str(chapter.get("text") or "").strip()]
    headings = [str(chapter.get("title") or "").strip() for chapter in chapters if str(chapter.get("title") or "").strip()]
    residual_artifacts = sum(_count_residual_page_artifacts(str(chapter.get("text") or ""), total_pages=total_pages) for chapter in normalized_chapters)

    chapter_word_stats = {
        "min": min(word_counts) if word_counts else 0,
        "median": int(round(_median([float(count) for count in word_counts]))) if word_counts else 0,
        "max": max(word_counts) if word_counts else 0,
    }

    return {
        "source": "pdf",
        "parser_version": "pdf_linewise_v3",
        "total_pages": total_pages,
        "chapter_count": len(normalized_chapters),
        "heading_count": len(headings),
        "heading_samples": headings[:12],
        "repeated_noise_count": len(repeated_noise),
        "text_line_count": int(diagnostics_state.get("text_line_count") or 0),
        "noise_lines_removed": int(diagnostics_state.get("noise_lines_removed") or 0),
        "noise_reason_counts": dict(diagnostics_state.get("noise_reason_counts") or {}),
        "inline_artifacts_removed": int(diagnostics_state.get("inline_artifacts_removed") or 0),
        "residual_page_artifact_count": residual_artifacts,
        "chapter_word_stats": chapter_word_stats,
        "anomalies": list(anomalies),
        "fallback_strategy": fallback_strategy,
        "forced_large_chapter_split": bool(forced_large_chapter_split),
    }
