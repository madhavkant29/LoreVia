import os
import re
import tempfile

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from app.parsers.pdf_parser import _extract_source_number_from_heading

PARAGRAPH_SPLIT_TARGET_WORDS = 7000


def parse_epub(raw_bytes: bytes, *, split_large_chapters: bool = True) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(raw_bytes)
        path = tmp.name
    try:
        book = epub.read_epub(path)
        chapters, n = [], 1
        for item in book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for tag in soup(["script", "style", "img"]):
                tag.decompose()
            raw_text = soup.get_text(separator="\n")
            cleaned_text = re.sub(r"[\u2726\u2318\u2600-\u26FF\u2700-\u27BF]", " ", raw_text)
            text = "\n".join(line.strip() for line in cleaned_text.splitlines() if line.strip())
            if len(text) < 100:
                continue
            title = next(
                (soup.find(tag_name) for tag_name in ["h1", "h2", "h3"] if soup.find(tag_name)),
                None,
            )
            title_text = title.get_text().strip() if title else f"Chapter {n}"
            chapters.append(
                {
                    "number": n,
                    "title": title_text,
                    "text": text,
                    "source_number": _extract_source_number_from_heading(title_text),
                }
            )
            n += 1
        return _split_large_chapters(chapters, split_large_chapters=split_large_chapters)
    finally:
        os.unlink(path)


def _split_large_chapters(chapters: list[dict], *, split_large_chapters: bool) -> list[dict]:
    normalized: list[dict] = []
    next_number = 1
    for chapter in chapters:
        parts = [part.strip() for part in re.split(r"\n\s*\n+", chapter["text"]) if part.strip()]
        split_parts = _split_parts(parts) if split_large_chapters else [parts]
        for index, split_part in enumerate(split_parts, start=1):
            title = chapter["title"]
            if len(split_parts) > 1:
                title = f"{title} - Part {index}"
            normalized.append(
                {
                    "number": next_number,
                    "title": title,
                    "text": "\n\n".join(split_part),
                    "source_number": chapter.get("source_number")
                    if len(split_parts) == 1
                    else None,
                }
            )
            next_number += 1
    return normalized


def _split_parts(parts: list[str]) -> list[list[str]]:
    if not parts:
        return []
    sections: list[list[str]] = []
    current: list[str] = []
    current_words = 0
    for part in parts:
        part_words = len(re.findall(r"\b\w+\b", part))
        if (
            current
            and current_words + part_words > PARAGRAPH_SPLIT_TARGET_WORDS
            and _can_close_section(current)
        ):
            sections.append(current)
            current = []
            current_words = 0
        current.append(part)
        current_words += part_words
    if current:
        sections.append(current)
    return sections


def _can_close_section(parts: list[str]) -> bool:
    for part in reversed(parts):
        stripped = part.strip()
        if not stripped:
            continue
        return bool(re.search(r"[.!?][\"')\]]*\s*$", stripped))
    return False
