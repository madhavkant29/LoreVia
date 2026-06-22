from __future__ import annotations

import io
import re
import zipfile
from html import unescape
from typing import Any, cast

import fitz
import httpx

ISBN_TOKEN_RE = re.compile(r"\b(?:ISBN(?:-1[03])?:?\s*)?([0-9Xx][0-9Xx\s-]{8,24}[0-9Xx])\b")
COPYRIGHT_RE = re.compile(r"(?:copyright|\u00a9|\(c\)|all rights reserved)", re.IGNORECASE)
PUBLIC_DOMAIN_RE = re.compile(r"(?:public domain|project gutenberg)", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


async def check_isbn(isbn: str) -> dict:
    normalized = normalize_isbn(isbn)
    if not normalized:
        return {"found": False}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://openlibrary.org/api/books",
                params={"bibkeys": f"ISBN:{normalized}", "format": "json", "jscmd": "data"},
            )
            data = resp.json()
            key = f"ISBN:{normalized}"
            if key in data:
                entry = data[key]
                return {
                    "found": True,
                    "title": entry.get("title"),
                    "authors": [a["name"] for a in entry.get("authors", [])],
                    "requires_disclaimer": True,
                }
    except Exception:
        pass
    return {"found": False}


def normalize_isbn(value: str | None) -> str | None:
    cleaned = re.sub(r"[^0-9Xx]", "", str(value or "")).upper()
    if len(cleaned) == 13 and _is_valid_isbn13(cleaned):
        return cleaned
    if len(cleaned) == 10 and _is_valid_isbn10(cleaned):
        return cleaned
    return None


def extract_isbn_from_text(text: str | None) -> str | None:
    candidates = extract_isbn_candidates_from_text(text)
    return candidates[0] if candidates else None


def extract_isbn_candidates_from_text(text: str | None) -> list[str]:
    seen: set[str] = set()
    found: list[str] = []
    for match in ISBN_TOKEN_RE.finditer(str(text or "")):
        normalized = normalize_isbn(match.group(1))
        if normalized and normalized not in seen:
            seen.add(normalized)
            found.append(normalized)
    found.sort(key=lambda item: (len(item) != 13, item))
    return found


async def evaluate_document_copyright(
    *,
    format_name: str | None,
    raw: bytes,
    existing_isbn: str | None = None,
) -> dict[str, Any]:
    document_text = extract_document_text_for_copyright_checks(format_name, raw)
    resolved_isbn = normalize_isbn(existing_isbn) or extract_isbn_from_text(document_text)
    registry_hit = False

    if resolved_isbn:
        registry_hit = bool((await check_isbn(resolved_isbn)).get("found", False))

    has_public_domain_marker = bool(PUBLIC_DOMAIN_RE.search(document_text))
    has_copyright_marker = bool(COPYRIGHT_RE.search(document_text))
    has_isbn_signal = resolved_isbn is not None
    copyright_warning = bool(
        registry_hit or has_isbn_signal or (has_copyright_marker and not has_public_domain_marker)
    )

    return {
        "isbn": resolved_isbn,
        "copyright_warning": copyright_warning,
        "registry_hit": registry_hit,
        "has_copyright_marker": has_copyright_marker,
        "has_public_domain_marker": has_public_domain_marker,
    }


def extract_document_text_for_copyright_checks(format_name: str | None, raw: bytes) -> str:
    normalized_format = " ".join(str(format_name or "").split()).strip().lower()
    if not raw:
        return ""
    if normalized_format == "pdf":
        return _extract_pdf_text(raw)
    if normalized_format in {"txt", "md", "fountain"}:
        return _safe_decode(raw)
    if normalized_format == "docx":
        return _extract_zip_text(
            raw, suffixes=(".xml",), preferred_names=("word/document.xml", "docProps/core.xml")
        )
    if normalized_format == "epub":
        return _extract_zip_text(
            raw,
            suffixes=(".xhtml", ".html", ".htm", ".xml"),
            preferred_names=("content.opf", "toc.ncx", "mimetype"),
        )
    return ""


def _extract_pdf_text(raw: bytes) -> str:
    try:
        doc = cast(Any, fitz).open(stream=raw, filetype="pdf")
        parts: list[str] = []
        for index in range(min(5, len(doc))):
            parts.append(str(cast(Any, doc[index]).get_text() or ""))
        doc.close()
        return _normalize_text("\n".join(parts))
    except Exception:
        return ""


def _extract_zip_text(
    raw: bytes, *, suffixes: tuple[str, ...], preferred_names: tuple[str, ...]
) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            selected_names: list[str] = []
            names = archive.namelist()
            for preferred_name in preferred_names:
                if preferred_name in names:
                    selected_names.append(preferred_name)
            for name in names:
                lower = name.lower()
                if name in selected_names or not lower.endswith(suffixes):
                    continue
                selected_names.append(name)
                if len(selected_names) >= 8:
                    break

            parts: list[str] = []
            for name in selected_names[:8]:
                parts.append(_strip_tags(_safe_decode(archive.read(name))))
            return _normalize_text("\n".join(parts))
    except Exception:
        return ""


def _strip_tags(value: str) -> str:
    return unescape(TAG_RE.sub(" ", value))


def _safe_decode(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _normalize_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _is_valid_isbn10(value: str) -> bool:
    if len(value) != 10:
        return False
    total = 0
    for index, char in enumerate(value[:9], start=1):
        if not char.isdigit():
            return False
        total += index * int(char)
    check_char = 10 if value[9] == "X" else int(value[9]) if value[9].isdigit() else -1
    if check_char < 0:
        return False
    return total % 11 == check_char


def _is_valid_isbn13(value: str) -> bool:
    if len(value) != 13 or not value.isdigit():
        return False
    total = 0
    for index, char in enumerate(value[:12]):
        total += int(char) * (1 if index % 2 == 0 else 3)
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(value[12])
