"""Plan lossless splits of saved Part bodies with numbered Roman headings."""

from __future__ import annotations

import re

from app.parsers.text_parser import parse_text_structure


def split_saved_part_chapters(part_title: str, text: str) -> list[dict]:
    """Return chapter bodies only when the entire saved Part has clear boundaries.

    Each returned ``raw_section`` is an exact slice of ``text``. The caller can
    keep that slice for audit while storing the body separately from its title.
    A non-empty Part introduction or ambiguous heading pattern is rejected.
    """
    if not part_title.strip() or not text.strip():
        raise ValueError("saved_part_source_missing")
    source = f"{part_title.strip()}\n\n{text}"
    sections = parse_text_structure(source, language="en")
    chapters = sections[1:]
    if (
        not sections
        or sections[0]["section_type"] != "part"
        or sections[0]["text"].strip()
        or len(chapters) < 2
        or any(section["section_type"] != "chapter" for section in chapters)
        or [section.get("source_number") for section in chapters]
        != list(range(1, len(chapters) + 1))
    ):
        raise ValueError("saved_part_chapter_boundaries_ambiguous")

    raw_lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in raw_lines:
        offsets.append(offsets[-1] + len(line))
    starts = [int(section["start_line"]) - 3 for section in chapters]
    if starts[0] != 0 or any(index < 0 or index >= len(raw_lines) for index in starts):
        raise ValueError("saved_part_chapter_boundaries_ambiguous")
    boundaries = [offsets[index] for index in starts] + [len(text)]
    result = []
    for section, start, end in zip(chapters, boundaries, boundaries[1:]):
        raw_section = text[start:end]
        heading, _, body = raw_section.partition("\n")
        if heading.strip().rstrip(".") != str(section["title"]).rstrip(".") or not body.strip():
            raise ValueError("saved_part_chapter_boundaries_ambiguous")
        result.append(
            {
                "title": section["title"],
                "source_number": section["source_number"],
                "text": body.strip(),
                "raw_section": raw_section,
                "start_offset": start,
                "end_offset": end,
            }
        )
    if "".join(item["raw_section"] for item in result) != text:
        raise ValueError("saved_part_chapter_boundaries_ambiguous")
    return result


def compare_saved_chapters_with_reparsed(saved: list[dict], reparsed: list[dict]) -> list[dict]:
    """Compare the current manuscript with a fresh import without exposing text."""
    expanded: list[dict] = []
    for chapter in saved:
        title = str(chapter.get("title") or "")
        text = str(chapter.get("text") or "")
        if title.endswith(" — opening"):
            expanded.extend(split_saved_part_chapters(title.removesuffix(" — opening"), text))
        else:
            expanded.append({"title": title, "text": text})

    comparisons: list[dict] = []
    for index in range(max(len(expanded), len(reparsed))):
        previous = expanded[index] if index < len(expanded) else None
        proposed = reparsed[index] if index < len(reparsed) else None
        current_text = str(previous.get("text") or "") if previous else ""
        proposed_text = str(proposed.get("text") or "") if proposed else ""
        content_preserved, line_wrap_joins = (
            _compare_reparsed_words(current_text, proposed_text)
            if previous and proposed
            else (False, 0)
        )
        comparisons.append(
            {
                "number": index + 1,
                "current_words": len(current_text.split()) if previous else None,
                "proposed_words": len(proposed_text.split()) if proposed else None,
                "current_paragraphs": len(
                    [part for part in re.split(r"\n\s*\n", current_text) if part.strip()]
                )
                if previous
                else None,
                "proposed_paragraphs": len(
                    [part for part in re.split(r"\n\s*\n", proposed_text) if part.strip()]
                )
                if proposed
                else None,
                "title_matches": previous is not None
                and proposed is not None
                and previous.get("title") == proposed.get("title"),
                "content_preserved": content_preserved,
                "line_wrap_joins": line_wrap_joins,
            }
        )
    return comparisons


def _compare_reparsed_words(current_text: str, proposed_text: str) -> tuple[bool, int]:
    """Accept only PDF line-wrap joins; reject inserted or changed manuscript words."""
    before = current_text.split()
    after = proposed_text.split()
    joins = 0
    old_index = new_index = 0
    while old_index < len(before) and new_index < len(after):
        if before[old_index] == after[new_index]:
            old_index += 1
            new_index += 1
            continue
        if old_index + 1 >= len(before):
            return False, joins
        first, second = before[old_index : old_index + 2]
        target = after[new_index]
        hyphen_join = first.endswith("-") and first[:-1] + second == target
        punctuation_join = second[0] in ".,;:!?" and first + second == target
        if not (hyphen_join or punctuation_join):
            return False, joins
        joins += 1
        old_index += 2
        new_index += 1
    return old_index == len(before) and new_index == len(after), joins
