import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tempfile, os


def parse_epub(raw_bytes: bytes) -> list[dict]:
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
            text = "\n".join(
                l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()
            )
            if len(text) < 100:
                continue
            title = next((soup.find(t) for t in ["h1","h2","h3"] if soup.find(t)), None)
            chapters.append({
                "number": n,
                "title": title.get_text().strip() if title else f"Chapter {n}",
                "text": text,
            })
            n += 1
        return chapters
    finally:
        os.unlink(path)
