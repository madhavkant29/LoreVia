import re
from collections import Counter

import fitz

MAX_WORDS_PER_CHAPTER = 5000
CHAPTER_WORD_TOLERANCE = 100

CHAPTER_RE = re.compile(
    r"^(chapter\s+(?:\d+|[ivxlcdm]+)|ch\.\s*(?:\d+|[ivxlcdm]+)|prologue|epilogue|part\s+(?:\d+|[ivxlcdm]+))[\s:\-.]*",
    re.IGNORECASE,
)
ROMAN_HEADING_RE = re.compile(r"^(?:[ivxlcdm]{1,8})$", re.IGNORECASE)


def parse_pdf(raw_bytes: bytes) -> list[dict]:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    page_lines = [_page_lines(page.get_text("text")) for page in doc]
    repeated_headers = _detect_repeated_headers(page_lines)

    chapters: list[dict] = []
    current: dict | None = None
    pending_paragraph: str | None = None

    for lines in page_lines:
        cleaned_lines = [line for line in lines if line not in repeated_headers and not _is_page_number(line)]
        cleaned_lines = _trim_edge_noise(cleaned_lines)
        paragraphs = _lines_to_paragraphs(cleaned_lines)
        paragraphs, pending_paragraph = _merge_page_boundary_paragraphs(paragraphs, pending_paragraph)

        for paragraph in paragraphs:
            heading = _extract_heading(paragraph)
            if heading:
                if current and current["text"].strip():
                    chapters.append(current)
                current = {"number": len(chapters) + 1, "title": heading, "text": ""}
                remainder = paragraph[len(heading):].strip(" :-.\n")
                if remainder and current is not None:
                    current["text"] += remainder + "\n\n"
            elif current is not None:
                current["text"] += paragraph + "\n\n"

    if pending_paragraph and current is not None:
        current["text"] += pending_paragraph + "\n\n"

    if current and current["text"].strip():
        chapters.append(current)

    doc.close()
    normalized = _normalize_chapters(chapters)
    if normalized:
        return normalized

    fallback_text = _all(raw_bytes)
    fallback_chapters = _normalize_chapters(
        [{"number": 1, "title": "Full Text", "text": fallback_text}]
    )
    return fallback_chapters or [{"number": 1, "title": "Full Text", "text": fallback_text}]


def _all(raw_bytes: bytes) -> str:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    page_lines = [_page_lines(doc[i].get_text("text")) for i in range(len(doc))]
    repeated_headers = _detect_repeated_headers(page_lines)
    paragraphs: list[str] = []
    pending_paragraph: str | None = None

    for lines in page_lines:
        cleaned_lines = [line for line in lines if line not in repeated_headers and not _is_page_number(line)]
        cleaned_lines = _trim_edge_noise(cleaned_lines)
        page_paragraphs = _lines_to_paragraphs(cleaned_lines)
        page_paragraphs, pending_paragraph = _merge_page_boundary_paragraphs(page_paragraphs, pending_paragraph)
        paragraphs.extend(page_paragraphs)

    if pending_paragraph:
        paragraphs.append(pending_paragraph)

    doc.close()
    return "\n\n".join(paragraphs)


def _normalize_chapters(chapters: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for chapter in chapters:
        text = _clean_text(chapter["text"])
        if len(text) < 200:
            continue
        title = (chapter.get("title") or "").strip() or f"Chapter {len(normalized) + 1}"
        if normalized and normalized[-1]["title"].strip().lower() == title.lower():
            normalized[-1]["text"] += "\n\n" + text
            continue
        normalized.append({"number": len(normalized) + 1, "title": title, "text": text})

    final_chapters: list[dict] = []
    for chapter in normalized:
        if _word_count(chapter["text"]) > MAX_WORDS_PER_CHAPTER:
            final_chapters.extend(_split_overlong_chapter(chapter["title"], chapter["text"]))
        else:
            final_chapters.append(
                {
                    "number": len(final_chapters) + 1,
                    "title": chapter["title"],
                    "text": chapter["text"],
                }
            )

    if len(final_chapters) == 1 and _word_count(final_chapters[0]["text"]) > MAX_WORDS_PER_CHAPTER:
        return _split_virtual_chapters(final_chapters[0]["text"])
    return final_chapters


def _page_lines(page_text: str) -> list[str]:
    return [line.strip() for line in page_text.splitlines() if line.strip()]


def _detect_repeated_headers(page_lines: list[list[str]]) -> set[str]:
    counter: Counter[str] = Counter()
    total_pages = len(page_lines)

    for lines in page_lines:
        candidates = lines[:2] + lines[-2:]
        seen_on_page = set()
        for line in candidates:
            normalized = " ".join(line.split())
            if not normalized or _is_page_number(normalized) or len(normalized) > 80:
                continue
            if normalized in seen_on_page:
                continue
            seen_on_page.add(normalized)
            counter[normalized] += 1

    threshold = max(3, total_pages // 8) if total_pages >= 8 else 3
    return {
        line
        for line, count in counter.items()
        if count >= threshold and not CHAPTER_RE.match(line)
    }


def _is_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"[\[\(]?\d{1,4}[\]\)]?", line.strip()))


def _trim_edge_noise(lines: list[str]) -> list[str]:
    trimmed = list(lines)

    while trimmed and _looks_like_edge_header_fragment(trimmed[0], trimmed[1] if len(trimmed) > 1 else None):
        trimmed.pop(0)

    while trimmed and _looks_like_edge_footer_fragment(trimmed[-1]):
        trimmed.pop()

    return trimmed


def _looks_like_edge_header_fragment(line: str, next_line: str | None) -> bool:
    normalized = " ".join(line.split())
    if not normalized or CHAPTER_RE.match(normalized) or _is_page_number(normalized):
        return False
    if len(normalized) > 40 or normalized.endswith((".", "!", "?", ":", ";")):
        return False

    words = normalized.split()
    if len(words) > 5:
        return False

    if next_line and next_line[:1].isupper():
        lowercase_words = {"and", "of", "the", "to", "in", "a", "an"}
        if all(word[:1].isupper() or word.lower() in lowercase_words for word in words):
            return True
    return False


def _looks_like_edge_footer_fragment(line: str) -> bool:
    normalized = " ".join(line.split())
    if not normalized or CHAPTER_RE.match(normalized) or _is_page_number(normalized):
        return False
    lowered = normalized.lower()
    if "prepared and published by" in lowered or "project gutenberg" in lowered:
        return True
    if len(normalized) > 30:
        return False
    if normalized.endswith((".", "!", "?", ":", ";")):
        return False
    words = normalized.split()
    lowercase_words = {"and", "of", "the", "to", "in", "a", "an"}
    return len(words) <= 4 and all(word[:1].isupper() or word.lower() in lowercase_words for word in words)


def _lines_to_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current = ""

    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else None
        if not line:
            if current:
                paragraphs.append(current.strip())
                current = ""
            continue

        if CHAPTER_RE.match(line) and len(line) < 120:
            if current:
                paragraphs.append(current.strip())
                current = ""
            paragraphs.append(line.strip())
            continue

        if current:
            current = _join_line(current, line)
        else:
            current = line

        if current and _looks_like_paragraph_boundary(current, next_line):
            paragraphs.append(current.strip())
            current = ""

    if current:
        paragraphs.append(current.strip())

    return paragraphs


def _join_line(current: str, line: str) -> str:
    if current.endswith("-") and not current.endswith("--"):
        return current[:-1] + line.lstrip()
    return f"{current.rstrip()} {line.lstrip()}"


def _looks_like_paragraph_boundary(current: str, next_line: str | None) -> bool:
    if next_line is None:
        return False
    current_text = current.strip()
    next_text = next_line.strip()
    if not current_text or not next_text:
        return False
    if not re.search(r'[.!?]["\']?$', current_text):
        return False
    if CHAPTER_RE.match(next_text):
        return True
    if len(current_text) < 60:
        return False
    return next_text[:1].isupper()


def _extract_heading(paragraph: str) -> str | None:
    stripped = paragraph.strip()
    if CHAPTER_RE.match(stripped) and len(stripped) < 160:
        return stripped
    if ROMAN_HEADING_RE.fullmatch(stripped):
        return f"Chapter {stripped.upper()}"
    if re.fullmatch(r"(?:book|part)\s+[ivxlcdm]+", stripped, re.IGNORECASE):
        return stripped
    if re.fullmatch(r"(?:one|two|three|four|five|six|seven|eight|nine|ten)", stripped, re.IGNORECASE):
        return f"Chapter {stripped.title()}"
    return None


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"(?i)\n{2,}prepared and published by:.*$", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _split_virtual_chapters(text: str, target_words: int = 2200, max_words: int = 3200) -> list[dict]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    chapters: list[dict] = []
    current_parts: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = _word_count(paragraph)
        if paragraph_words > max_words:
            sentence_parts = _split_paragraph_to_sections(paragraph, target_words, max_words)
            for sentence_part in sentence_parts:
                part_words = _word_count(sentence_part)
                if current_parts and current_words + part_words > max_words:
                    chapters.append(_build_virtual_chapter(len(chapters) + 1, current_parts))
                    current_parts = []
                    current_words = 0
                current_parts.append(sentence_part)
                current_words += part_words
            continue

        if current_parts and current_words + paragraph_words > max_words:
            chapters.append(_build_virtual_chapter(len(chapters) + 1, current_parts))
            current_parts = []
            current_words = 0

        current_parts.append(paragraph)
        current_words += paragraph_words

        if current_words >= target_words:
            chapters.append(_build_virtual_chapter(len(chapters) + 1, current_parts))
            current_parts = []
            current_words = 0

    if current_parts:
        chapters.append(_build_virtual_chapter(len(chapters) + 1, current_parts))

    return chapters


def _split_overlong_chapter(title: str, text: str) -> list[dict]:
    parts = _split_text_near_limit(
        text,
        target_words=MAX_WORDS_PER_CHAPTER,
        min_words=MAX_WORDS_PER_CHAPTER - CHAPTER_WORD_TOLERANCE,
        max_words=MAX_WORDS_PER_CHAPTER + CHAPTER_WORD_TOLERANCE,
    )
    if len(parts) == 1:
        return [
            {
                "number": 1,
                "title": title,
                "text": text,
            }
        ]

    split_parts: list[dict] = []
    for index, part in enumerate(parts, start=1):
        split_parts.append(
            {
                "number": index,
                "title": f"{title} ({index})",
                "text": part,
            }
        )
    return split_parts


def _split_text_near_limit(text: str, target_words: int, min_words: int, max_words: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    parts: list[str] = []
    current_parts: list[str] = []
    current_words = 0

    for paragraph in paragraphs:
        paragraph_words = _word_count(paragraph)

        if paragraph_words > max_words:
            sentence_sections = _split_paragraph_near_limit(paragraph, target_words, min_words, max_words)
            for section in sentence_sections:
                section_words = _word_count(section)
                if current_parts and current_words + section_words > max_words:
                    parts.append(_clean_text("\n\n".join(current_parts)))
                    current_parts = []
                    current_words = 0
                current_parts.append(section)
                current_words += section_words
                if min_words <= current_words <= max_words:
                    parts.append(_clean_text("\n\n".join(current_parts)))
                    current_parts = []
                    current_words = 0
            continue

        if current_parts and current_words + paragraph_words > max_words:
            parts.append(_clean_text("\n\n".join(current_parts)))
            current_parts = []
            current_words = 0

        current_parts.append(paragraph)
        current_words += paragraph_words

        if min_words <= current_words <= max_words:
            parts.append(_clean_text("\n\n".join(current_parts)))
            current_parts = []
            current_words = 0

    if current_parts:
        if parts and _word_count("\n\n".join(current_parts)) < min_words:
            parts[-1] = _clean_text(parts[-1] + "\n\n" + "\n\n".join(current_parts))
        else:
            parts.append(_clean_text("\n\n".join(current_parts)))

    return parts


def _split_paragraph_near_limit(paragraph: str, target_words: int, min_words: int, max_words: int) -> list[str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", paragraph) if sentence.strip()]
    if len(sentences) <= 1:
        return [paragraph]

    sections: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = _word_count(sentence)
        if current and current_words + sentence_words > max_words:
            sections.append(" ".join(current).strip())
            current = []
            current_words = 0

        current.append(sentence)
        current_words += sentence_words

        if min_words <= current_words <= max_words:
            sections.append(" ".join(current).strip())
            current = []
            current_words = 0

    if current:
        if sections and _word_count(current[0]) + _word_count(sections[-1]) <= max_words and _word_count(" ".join(current)) < min_words:
            sections[-1] = f"{sections[-1]} {' '.join(current).strip()}".strip()
        else:
            sections.append(" ".join(current).strip())

    return sections


def _split_paragraph_to_sections(paragraph: str, target_words: int, max_words: int) -> list[str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", paragraph) if sentence.strip()]
    if len(sentences) <= 1:
        return [paragraph]

    sections: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = _word_count(sentence)
        if current and current_words + sentence_words > max_words:
            sections.append(" ".join(current).strip())
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
        if current_words >= target_words:
            sections.append(" ".join(current).strip())
            current = []
            current_words = 0

    if current:
        sections.append(" ".join(current).strip())

    return sections


def _build_virtual_chapter(number: int, parts: list[str]) -> dict:
    return {
        "number": number,
        "title": f"Section {number}",
        "text": _clean_text("\n\n".join(parts)),
    }


def _merge_page_boundary_paragraphs(
    paragraphs: list[str],
    pending_paragraph: str | None,
) -> tuple[list[str], str | None]:
    merged = list(paragraphs)

    if pending_paragraph:
        if merged and _should_merge_across_pages(pending_paragraph, merged[0]):
            merged[0] = _join_line(pending_paragraph, merged[0])
        else:
            merged.insert(0, pending_paragraph)

    if not merged:
        return merged, None

    if _is_open_paragraph(merged[-1]):
        return merged[:-1], merged[-1]

    return merged, None


def _is_open_paragraph(paragraph: str) -> bool:
    text = paragraph.strip()
    if not text:
        return False
    return not bool(re.search(r'[.!?]["\')\]]?$', text))


def _should_merge_across_pages(previous: str, following: str) -> bool:
    prev = previous.strip()
    nxt = following.strip()
    if not prev or not nxt:
        return False
    if _extract_heading(nxt):
        return False
    if re.search(r'[.!?]["\')\]]?$', prev):
        return False
    return True
