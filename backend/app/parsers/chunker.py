import re

import tiktoken

_enc = tiktoken.encoding_for_model("gpt-4o")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


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
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if s.strip()]
    if len(sentences) <= 1:
        return [paragraph.strip()]

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
            # Keep an oversized sentence intact rather than cutting it mid-sentence.
            parts.append(sentence)
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
