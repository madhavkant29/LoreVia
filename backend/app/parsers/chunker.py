import re

import tiktoken

_enc = tiktoken.encoding_for_model("gpt-4o")
MEDIA_MARKER_RE = re.compile(r"\[\[IMAGE:[^\]]+\]\]")


def count_tokens(text: str) -> int:
    sanitized = MEDIA_MARKER_RE.sub(" ", text)
    return len(_enc.encode(sanitized))


def chunk_text(text: str, max_tokens: int = 1500, overlap: int = 100) -> list[str]:
    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = count_tokens(paragraph)

        if paragraph_tokens > max_tokens:
            oversized_parts = _split_large_paragraph(paragraph, max_tokens)
            for part in oversized_parts:
                part_tokens = count_tokens(part)
                if current and current_tokens + part_tokens > max_tokens:
                    chunks.append("\n\n".join(current))
                    current, current_tokens = _paragraph_overlap(current, overlap)
                current.append(part)
                current_tokens += part_tokens
            continue

        if current and current_tokens + paragraph_tokens > max_tokens:
            chunks.append("\n\n".join(current))
            current, current_tokens = _paragraph_overlap(current, overlap)

        current.append(paragraph)
        current_tokens += paragraph_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    return paragraphs


def _paragraph_overlap(paragraphs: list[str], overlap_tokens: int) -> tuple[list[str], int]:
    overlap_parts: list[str] = []
    overlap_count = 0

    for paragraph in reversed(paragraphs):
        token_count = count_tokens(paragraph)
        if overlap_parts and overlap_count + token_count > overlap_tokens:
            break
        overlap_parts.insert(0, paragraph)
        overlap_count += token_count
        if overlap_count >= overlap_tokens:
            break

    return overlap_parts, overlap_count


def _split_large_paragraph(paragraph: str, max_tokens: int) -> list[str]:
    sentences = [s.strip() for s in _sentence_segments(paragraph) if s.strip()]
    if len(sentences) <= 1:
        return _split_oversized_sentence(paragraph.strip(), max_tokens)

    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        if sentence_tokens > max_tokens:
            if current:
                parts.append(" ".join(current))
                current = []
                current_tokens = 0
            parts.extend(_split_oversized_sentence(sentence, max_tokens))
            continue

        if current and current_tokens + sentence_tokens > max_tokens:
            parts.append(" ".join(current))
            current = []
            current_tokens = 0

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        parts.append(" ".join(current))

    return parts


def _split_oversized_sentence(sentence: str, max_tokens: int) -> list[str]:
    clause_parts = _split_on_clause_boundaries(sentence)
    if len(clause_parts) > 1:
        parts: list[str] = []
        current: list[str] = []
        for clause in clause_parts:
            candidate = " ".join([*current, clause]).strip()
            if current and count_tokens(candidate) > max_tokens:
                parts.append(" ".join(current).strip())
                current = [clause]
                continue
            current.append(clause)
        if current:
            parts.append(" ".join(current).strip())
        if all(count_tokens(part) <= max_tokens for part in parts):
            return [part for part in parts if part]

    words = sentence.split()
    if not words:
        return [sentence]

    parts: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join([*current, word]).strip()
        if current and count_tokens(candidate) > max_tokens:
            parts.append(" ".join(current).strip())
            current = [word]
            continue
        current.append(word)

    if current:
        parts.append(" ".join(current).strip())

    return [part for part in parts if part]


def _sentence_segments(paragraph: str) -> list[str]:
    protected = paragraph
    abbreviations = {
        "Mr.": "Mr<dot>",
        "Mrs.": "Mrs<dot>",
        "Ms.": "Ms<dot>",
        "Dr.": "Dr<dot>",
        "Prof.": "Prof<dot>",
        "Sr.": "Sr<dot>",
        "Jr.": "Jr<dot>",
        "St.": "St<dot>",
        "vs.": "vs<dot>",
        "etc.": "etc<dot>",
        "e.g.": "eg<dot>",
        "i.e.": "ie<dot>",
    }
    for source, target in abbreviations.items():
        protected = protected.replace(source, target)
    segments = [segment.replace("<dot>", ".").strip() for segment in re.split(r"(?<=[.!?])\s+", protected) if segment.strip()]
    return segments


def _split_on_clause_boundaries(sentence: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[,;:—-])\s+", sentence) if part.strip()]
