from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any, cast

import fitz

CHAPTER_RE = re.compile(
    r"^(?:(?:chapter|ch\.?|part|volume|vol\.?|book|act|episode|section|scene)\s+"
    r"(?:\d+[a-z]?|[ivxlcdm]+|[a-z]{1,3}|[a-z]+(?:[-\s][a-z]+)*)"
    r"(?:\s*[:.\-]\s*.+)?|prologue|epilogue|interlude|afterword|appendix(?:\s+[a-z0-9]+)?)$",
    re.IGNORECASE,
)
UPPER_HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9\s'\",:;.!?\-]{2,60}$")
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


def parse_pdf(raw_bytes: bytes, *, split_large_chapters: bool = True) -> list[dict]:
    doc = cast(Any, fitz).open(stream=raw_bytes, filetype="pdf")
    try:
        repeated_noise = _detect_repeated_headers(doc)
        stream = []

        for page_number, page in enumerate(doc, start=1):
            for item in _page_blocks(page):
                if item["type"] == "text":
                    paragraphs = _blocks_to_paragraphs(item["text"])
                    for paragraph in paragraphs:
                        cleaned = _clean_text(paragraph)
                        if not cleaned:
                            continue
                        if _is_repeated_noise(cleaned, repeated_noise):
                            continue
                        stream.append(
                            {
                                "type": "text",
                                "text": cleaned,
                                "page": page_number,
                                "bbox": item["bbox"],
                            }
                        )
                else:
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

        chapters = _build_chapters(stream)
        chapters = _normalize_chapters(chapters, split_large_chapters=split_large_chapters)
        return chapters or [{"number": 1, "title": "Full Text", "text": "", "images": []}]
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

    for block in page_any.get_text("blocks"):
        if len(block) < 5:
            continue
        x0, y0, x1, y1, text = block[:5]
        if not isinstance(text, str):
            continue
        if not text.strip():
            continue
        items.append(
            {
                "type": "text",
                "bbox": (float(x0), float(y0), float(x1), float(y1)),
                "text": text,
            }
        )

    raw_dict = page_any.get_text("dict")
    for block in raw_dict.get("blocks", []):
        if block.get("type") != 1:
            continue
        raw = block.get("image")
        if not raw:
            continue
        ext = block.get("ext") or "png"
        items.append(
            {
                "type": "image",
                "bbox": tuple(block.get("bbox") or (0, 0, 0, 0)),
                "bytes": raw,
                "content_type": f"image/{ext.lower()}",
                "filename": f"{uuid.uuid4().hex}.{ext.lower()}",
            }
        )

    return sorted(items, key=lambda item: (item["bbox"][1], item["bbox"][0]))


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


def _build_chapters(stream: list[dict]) -> list[dict]:
    chapters: list[dict] = []
    current = _blank_chapter(1)

    for item in stream:
        if item["type"] == "text":
            heading = _extract_heading(item["text"])
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


def _normalize_chapters(chapters: list[dict], *, split_large_chapters: bool) -> list[dict]:
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
            text = _assemble_text_parts(text_parts_part)
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
        for block in page_any.get_text("blocks"):
            if len(block) < 5:
                continue
            x0, y0, x1, y1, text = block[:5]
            if not isinstance(text, str):
                continue
            cleaned = _clean_text(text)
            if not cleaned or len(cleaned) > 120:
                continue
            near_top = float(y0) <= min(80.0, height * 0.12)
            near_bottom = float(y1) >= max(0.0, height * 0.88)
            if near_top or near_bottom:
                seen.append(cleaned.lower())
    counts = Counter(seen)
    return {text for text, count in counts.items() if count >= 3}


def _is_repeated_noise(text: str, repeated_noise: set[str]) -> bool:
    lowered = text.lower()
    return lowered in repeated_noise or lowered.isdigit()


def _extract_heading(text: str) -> str | None:
    lines = [line.strip() for line in text.replace("\r", "\n").splitlines() if line.strip()]
    if not lines:
        return None
    first_line = _normalize_heading_candidate(lines[0]).strip(" .:-")
    if not first_line:
        return None
    if CHAPTER_RE.match(first_line):
        return first_line
    if UPPER_HEADING_RE.match(first_line) and len(first_line.split()) <= 8:
        return first_line.title()
    # Fallback: if it looks like a chapter heading with decorations, strip all non-alphanumeric and return
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


def _assemble_text_parts(text_parts: list[str]) -> str:
    parts = [part.strip() for part in text_parts if part and part.strip()]
    return "\n\n".join(parts)


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
