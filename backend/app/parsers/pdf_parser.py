import re
from collections import Counter

import fitz

CHAPTER_RE = re.compile(
    r"^(chapter\s+(?:\d+|[ivxlcdm]+)|ch\.\s*(?:\d+|[ivxlcdm]+)|prologue|epilogue|part\s+(?:\d+|[ivxlcdm]+))[\s:\-.]*",
    re.IGNORECASE,
)


def parse_pdf(raw_bytes: bytes) -> list[dict]:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    page_lines = [_page_lines(page.get_text("text")) for page in doc]
    repeated_headers = _detect_repeated_headers(page_lines)

    chapters: list[dict] = []
    current: dict | None = None

    for lines in page_lines:
        cleaned_lines = [line for line in lines if line not in repeated_headers and not _is_page_number(line)]
        cleaned_lines = _trim_edge_noise(cleaned_lines)
        paragraphs = _lines_to_paragraphs(cleaned_lines)

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

    if current and current["text"].strip():
        chapters.append(current)

    doc.close()
    normalized = _normalize_chapters(chapters)
    return normalized or [{"number": 1, "title": "Full Text", "text": _all(raw_bytes)}]


def _all(raw_bytes: bytes) -> str:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    page_lines = [_page_lines(doc[i].get_text("text")) for i in range(len(doc))]
    repeated_headers = _detect_repeated_headers(page_lines)
    paragraphs: list[str] = []

    for lines in page_lines:
        cleaned_lines = [line for line in lines if line not in repeated_headers and not _is_page_number(line)]
        cleaned_lines = _trim_edge_noise(cleaned_lines)
        paragraphs.extend(_lines_to_paragraphs(cleaned_lines))

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
        normalized.append(
            {
                "number": len(normalized) + 1,
                "title": title,
                "text": text,
            }
        )
    return normalized


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

    for line in lines:
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

    if current:
        paragraphs.append(current.strip())

    return paragraphs


def _join_line(current: str, line: str) -> str:
    if current.endswith("-") and not current.endswith("--"):
        return current[:-1] + line.lstrip()
    return f"{current.rstrip()} {line.lstrip()}"


def _extract_heading(paragraph: str) -> str | None:
    if CHAPTER_RE.match(paragraph) and len(paragraph) < 160:
        return paragraph.strip()
    return None


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"[ \t]+", " ", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
