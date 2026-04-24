from __future__ import annotations

import re
import uuid
from collections import Counter

import fitz

CHAPTER_RE = re.compile(
    r"^(?:(?:chapter|ch\.?|part|volume|vol\.?|book|act|episode|section|scene)\s+"
    r"(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth)"
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
ORNAMENT_RE = re.compile(r"[\u2600-\u27ff\u3000-\u303f\uFF00-\uFFEF]+")
MEDIA_MARKER_TEMPLATE = "[[IMAGE:{marker}]]"
MEDIA_MARKER_RE = re.compile(r"\[\[IMAGE:[^\]]+\]\]")
PARAGRAPH_SPLIT_MAX_WORDS = 4000


def parse_pdf(raw_bytes: bytes) -> list[dict]:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
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
        chapters = _normalize_chapters(chapters)
        return chapters or [{"number": 1, "title": "Full Text", "text": "", "images": []}]
    finally:
        doc.close()


def extract_first_page_cover(raw_bytes: bytes) -> tuple[bytes, str] | None:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    try:
        if doc.page_count == 0:
            return None
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200, alpha=False, annots=True)
        return pix.tobytes("png"), "image/png"
    finally:
        doc.close()


def _page_blocks(page: fitz.Page) -> list[dict]:
    items: list[dict] = []

    for block in page.get_text("blocks"):
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

    raw_dict = page.get_text("dict")
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


def _normalize_chapters(chapters: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    next_number = 1
    for chapter in chapters:
        text_parts = _drop_front_matter_text_parts(chapter["text_parts"])
        if not any(part.strip() for part in text_parts) and not chapter["images"]:
            continue
        split_parts = _split_large_chapter_parts(text_parts)
        for part_index, text_parts_part in enumerate(split_parts, start=1):
            text = _assemble_text_parts(text_parts_part)
            if not text and not chapter["images"]:
                continue
            title = chapter["title"] or f"Chapter {next_number}"
            if len(split_parts) > 1:
                title = f"{title} - Part {part_index}"
            normalized.append(
                {
                    "number": next_number,
                    "title": title,
                    "text": text,
                    "images": _images_for_text_parts(text_parts_part, chapter["images"]),
                }
            )
            next_number += 1
    return normalized


def _blank_chapter(number: int, title: str | None = None) -> dict:
    return {
        "number": number,
        "title": title,
        "text_parts": [],
        "images": [],
    }


def _chapter_has_content(chapter: dict) -> bool:
    return any(part.strip() for part in chapter["text_parts"])


def _detect_repeated_headers(doc: fitz.Document) -> set[str]:
    seen: list[str] = []
    for page in doc:
        height = float(page.rect.height or 0)
        for block in page.get_text("blocks"):
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
    # Fallback: if it looks like a chapter heading with decorations, strip ornaments and return
    cleaned_line = ORNAMENT_RE.sub("", first_line).strip()
    if any(word.lower() in ["chapter", "prologue", "epilogue", "part", "volume"] for word in cleaned_line.split()):
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
        return _clean_text("\n".join(lines[1:]))
    flattened = _normalize_heading_candidate(raw)
    match = re.match(re.escape(heading) + r"[\s:.\-]*", flattened, flags=re.IGNORECASE)
    if not match:
        return ""
    remainder = flattened[match.end():].strip()
    return _clean_text(remainder)


def _clean_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = normalized.replace("\u00ad", "")
    # Remove special Unicode symbols including black diamond (u2726) and place of interest (u2318)
    normalized = ORNAMENT_RE.sub(" ", normalized)
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
    while parts:
        normalized = MEDIA_MARKER_RE.sub(" ", parts[0]).strip()
        if not normalized:
            parts.pop(0)
            continue
        if _is_probable_front_matter(normalized):
            parts.pop(0)
            continue
        break
    return parts


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
            and projected_words > PARAGRAPH_SPLIT_MAX_WORDS
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
