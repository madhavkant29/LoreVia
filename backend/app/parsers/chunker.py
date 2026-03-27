import tiktoken
import re

_enc = tiktoken.encoding_for_model("gpt-4o")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def chunk_text(text: str, max_tokens: int = 1500, overlap: int = 100) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+|\n\n+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    chunks, current, current_tokens = [], [], 0

    for s in sentences:
        st = count_tokens(s)
        if current_tokens + st > max_tokens and current:
            chunks.append(" ".join(current))
            overlap_sents, overlap_toks = [], 0
            for prev in reversed(current):
                t = count_tokens(prev)
                if overlap_toks + t <= overlap:
                    overlap_sents.insert(0, prev)
                    overlap_toks += t
                else:
                    break
            current, current_tokens = overlap_sents, overlap_toks
        current.append(s)
        current_tokens += st

    if current:
        chunks.append(" ".join(current))
    return chunks
