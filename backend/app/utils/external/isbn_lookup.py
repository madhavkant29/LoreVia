import re

import fitz

ISBN_RE = re.compile(r"97[89][\d\s-]{10,17}\d")


def extract_isbn_from_pdf(raw_bytes: bytes) -> str | None:
    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        for i in range(min(3, len(doc))):
            text = doc[i].get_text()
            m = ISBN_RE.search(text)
            if m:
                doc.close()
                return m.group().replace("-", "").replace(" ", "")
        doc.close()
    except Exception:
        pass
    return None
