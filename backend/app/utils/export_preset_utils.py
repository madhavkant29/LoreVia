from __future__ import annotations

from typing import Any


def manuscript_export_preset(preset: str) -> dict[str, Any]:
    normalized = " ".join((preset or "").split()).strip().lower()
    if normalized == "kdp_paperback":
        return {
            "docx_font": "Garamond",
            "docx_font_size": 11,
            "pdf_page_size": "LETTER",
            "pdf_margins": (0.88, 0.75, 0.8, 0.8),
            "title": "6×9 print paperback",
        }
    if normalized == "trade_paperback":
        return {
            "docx_font": "Garamond",
            "docx_font_size": 11,
            "pdf_page_size": "A5",
            "pdf_margins": (0.8, 0.8, 0.75, 0.75),
            "title": "Trade paperback",
        }
    return {
        "docx_font": "Times New Roman",
        "docx_font_size": 12,
        "pdf_page_size": "LETTER",
        "pdf_margins": (1.0, 1.0, 1.0, 1.0),
        "title": "Standard manuscript",
    }


def novel_export_preset(preset: str) -> dict[str, Any]:
    normalized = " ".join((preset or "").split()).strip().lower()
    if normalized == "trade_novel":
        return {
            "docx_font": "Garamond",
            "docx_font_size": 11,
            "pdf_page_size": "LETTER",
            "docx_page_size": (6.0, 9.0),
            "pdf_margins": (0.88, 0.88, 0.8, 0.8),
            "title": "Trade novel",
        }
    if normalized == "large_print":
        return {
            "docx_font": "Georgia",
            "docx_font_size": 14,
            "pdf_page_size": "LETTER",
            "docx_page_size": (8.5, 11.0),
            "pdf_margins": (1.0, 1.0, 1.0, 1.0),
            "title": "Large print",
        }
    if normalized == "ebook_optimized":
        return {
            "docx_font": "Garamond",
            "docx_font_size": 11,
            "pdf_page_size": "A5",
            "docx_page_size": (5.83, 8.27),
            "pdf_margins": (0.7, 0.7, 0.7, 0.7),
            "title": "eBook optimized",
        }
    return {
        "docx_font": "Garamond",
        "docx_font_size": 11,
        "pdf_page_size": "A5",
        "docx_page_size": (5.83, 8.27),
        "pdf_margins": (0.8, 0.8, 0.8, 0.8),
        "title": "Standard novel",
    }
