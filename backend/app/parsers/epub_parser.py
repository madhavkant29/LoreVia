import os
import re
import tempfile

import ebooklib
from bs4 import BeautifulSoup, NavigableString, Tag
from ebooklib import epub

from app.parsers.pdf_parser import _extract_source_number_from_heading
from app.parsers.text_parser import parse_text_chapters

PARAGRAPH_SPLIT_TARGET_WORDS = 7000
MIN_EPUB_BODY_CHARS = 24
EPUB_BLOCK_TAGS = {
    "article",
    "blockquote",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "section",
}


def _extract_epub_blocks(soup: BeautifulSoup) -> list[str]:
    """Read block and inline XHTML content in document order without dropping div-based prose."""
    blocks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        text = re.sub(r"\s+", " ", "".join(current)).strip()
        if text:
            blocks.append(text)
        current.clear()

    def visit(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            current.append(str(node))
            return
        if node.name == "br":
            flush()
            return
        is_block = node.name in EPUB_BLOCK_TAGS
        if is_block:
            flush()
        for child in node.children:
            if isinstance(child, (Tag, NavigableString)):
                visit(child)
        if is_block:
            flush()

    root = soup.body or soup
    for child in root.children:
        if isinstance(child, (Tag, NavigableString)):
            visit(child)
    flush()
    return blocks


def parse_epub(raw_bytes: bytes, *, split_large_chapters: bool = True) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(raw_bytes)
        path = tmp.name
    try:
        book = epub.read_epub(path)
        chapters, n = [], 1
        spine = getattr(book, "spine", None) or []
        ordered_items = []
        get_item_with_id = getattr(book, "get_item_with_id", None)
        if spine and callable(get_item_with_id):
            seen_ids: set[str] = set()
            for spine_entry in spine:
                item_id = spine_entry[0] if isinstance(spine_entry, (tuple, list)) else spine_entry
                if not isinstance(item_id, str) or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                item = get_item_with_id(item_id)
                if item is not None:
                    ordered_items.append(item)
        if not ordered_items:
            ordered_items = list(book.get_items())

        for item in ordered_items:
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for tag in soup(["script", "style", "img", "nav"]):
                tag.decompose()
            title = soup.find(["h1", "h2", "h3"])
            title_text = title.get_text().strip() if title else f"Chapter {n}"
            blocks = _extract_epub_blocks(soup)
            raw_text = "\n\n".join(blocks)
            cleaned_text = re.sub(r"[\u2726\u2318\u2600-\u26FF\u2700-\u27BF]", " ", raw_text)
            text = "\n\n".join(part.strip() for part in cleaned_text.split("\n\n") if part.strip())
            body_text = text.replace(title_text, "", 1).strip() if title else text
            explicit_chapter = title and _extract_source_number_from_heading(title_text) is not None
            minimum_body_chars = 8 if explicit_chapter else MIN_EPUB_BODY_CHARS
            short_complete_sentence = bool(
                explicit_chapter and re.search(r"[.!?…][\"'”’]?$", body_text)
            )
            if len(body_text) < minimum_body_chars and not short_complete_sentence:
                continue
            if len(soup.find_all(["h1", "h2", "h3"])) >= 2:
                sections = parse_text_chapters(text)
                if len(sections) > 1 and all(
                    section["section_type"] in {"chapter", "prologue", "epilogue"}
                    for section in sections
                ):
                    for section in sections:
                        section_title = section["title"]
                        chapters.append(
                            {
                                "number": n,
                                "title": section_title,
                                "text": f"{section_title}\n\n{section['text']}",
                                "source_number": _extract_source_number_from_heading(section_title),
                            }
                        )
                        n += 1
                    continue
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


def parse_epub_structure(raw_bytes: bytes) -> list[dict]:
    """Read XHTML in spine order and retain heading evidence for the outline."""
    from app.parsers.text_parser import parse_text_structure

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(raw_bytes)
        path = tmp.name
    try:
        book = epub.read_epub(path)
        spine = getattr(book, "spine", None) or []
        ordered = []
        for entry in spine:
            item_id = entry[0] if isinstance(entry, (tuple, list)) else entry
            item = book.get_item_with_id(item_id) if isinstance(item_id, str) else None
            if item is not None and item.get_type() == ebooklib.ITEM_DOCUMENT:
                ordered.append(item)
        if not ordered:
            ordered = [
                item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT
            ]

        lines: list[str] = []
        locations: list[str] = []
        heading_lines: set[int] = set()
        navigation_entries: list[tuple[str, str]] = []
        for item in ordered:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            for navigation in soup.find_all("nav"):
                entries = [" ".join(entry.stripped_strings) for entry in navigation.find_all("li")]
                navigation_entries.extend(
                    (entry, str(item.get_name() or item.get_id())) for entry in entries if entry
                )
            for tag in soup(["script", "style", "nav"]):
                tag.decompose()
            location = str(item.get_name() or item.get_id())
            for content, is_heading in _structured_epub_blocks(soup):
                if lines:
                    lines.append("")
                    locations.append(location)
                if is_heading:
                    heading_lines.add(len(lines))
                lines.append(content)
                locations.append(location)
        sections = parse_text_structure(
            "\n".join(lines),
            heading_hint_lines=heading_lines,
            source_name="EPUB line",
        )
        for section in sections:
            start = max(0, int(section.get("start_line") or 1) - 1)
            end = max(start, int(section.get("end_line") or 1) - 1)
            first = locations[min(start, len(locations) - 1)] if locations else "EPUB"
            last = locations[min(end, len(locations) - 1)] if locations else first
            section["source_location"] = first if first == last else f"{first}–{last}"
        if navigation_entries and not any(
            section.get("section_type") == "toc" for section in sections
        ):
            sections.insert(
                0,
                {
                    "title": "Contents",
                    "text": "\n".join(entry for entry, _location in navigation_entries),
                    "section_type": "toc",
                    "source_location": navigation_entries[0][1],
                },
            )
        return sections
    finally:
        os.unlink(path)


def _structured_epub_blocks(soup: BeautifulSoup) -> list[tuple[str, bool]]:
    blocks: list[tuple[str, bool]] = []
    current: list[str] = []

    def flush(heading: bool = False) -> None:
        content = re.sub(r"\s+", " ", "".join(current)).strip()
        if content:
            blocks.append((content, heading))
        current.clear()

    def visit(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            current.append(str(node))
            return
        if node.name == "br":
            flush()
            return
        is_block = node.name in EPUB_BLOCK_TAGS
        if is_block:
            flush()
        for child in node.children:
            if isinstance(child, (Tag, NavigableString)):
                visit(child)
        if is_block:
            flush(node.name in {"h1", "h2", "h3", "h4", "h5", "h6"})

    root = soup.body or soup
    for child in root.children:
        if isinstance(child, (Tag, NavigableString)):
            visit(child)
    flush()
    return blocks


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
