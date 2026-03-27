import fitz
import re

CHAPTER_RE = re.compile(
    r"^(chapter\s+\d+|ch\.\s*\d+|prologue|epilogue|part\s+\d+)[\s:—]*",
    re.IGNORECASE,
)


def parse_pdf(raw_bytes: bytes) -> list[dict]:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    chapters, current = [], {"number": 1, "title": "Chapter 1", "text": ""}
    for page in doc:
        for line in page.get_text("text").split("\n"):
            s = line.strip()
            if s and CHAPTER_RE.match(s) and len(s) < 60:
                if current["text"].strip():
                    chapters.append(current)
                current = {"number": len(chapters) + 2, "title": s, "text": ""}
            else:
                current["text"] += line + "\n"
    if current["text"].strip():
        chapters.append(current)
    doc.close()
    return chapters or [{"number": 1, "title": "Full Text", "text": _all(raw_bytes)}]


def _all(raw_bytes: bytes) -> str:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    t = "\n".join(doc[i].get_text("text") for i in range(len(doc)))
    doc.close()
    return t
