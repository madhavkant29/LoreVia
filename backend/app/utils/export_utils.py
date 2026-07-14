"""
Compatibility export surface for manuscript, novel, character-card, and bible exports.

Heavy renderers live in focused modules so this file stays import-only and easy to audit.
"""

from __future__ import annotations

from app.utils.export_character_bible_utils import (
    character_bible_docx,
    character_bible_markdown,
    character_bible_pdf,
)
from app.utils.export_character_bible_vault_utils import (
    build_character_bible_vault_context,
    character_bible_vault_folder,
    character_bible_vault_manifest,
    character_bible_vault_preview,
)
from app.utils.export_character_card_utils import (
    character_card_docx,
    character_card_markdown,
    character_card_pdf,
)
from app.utils.export_common_utils import (
    EXPORT_ATTRIBUTION,
    _apply_pdf_metadata,
    _clean_line,
    _export_font_docx_name,
    _export_font_epub_stack,
    _export_font_pdf_names,
    _normalize_unicode_for_export,
    _safe_name,
    _set_docx_core_properties,
    export_filename_base,
    export_font_label,
    export_font_notice,
    normalize_export_font_family,
)
from app.utils.export_manuscript_docx_utils import manuscript_docx
from app.utils.export_manuscript_epub_utils import manuscript_epub, manuscript_epub_compiled
from app.utils.export_manuscript_formatting_utils import (
    _approx_word_count_label,
    _chapter_body_blocks,
    _chapter_heading_lines,
    _manuscript_end_marker,
    _manuscript_front_matter,
    _manuscript_toc_label,
    _scene_heading_lines,
)
from app.utils.export_manuscript_pdf_utils import manuscript_pdf, manuscript_pdf_compiled
from app.utils.export_novel_render_utils import (
    novel_docx,
    novel_epub_compiled,
    novel_pdf_compiled,
)
from app.utils.export_preset_utils import manuscript_export_preset, novel_export_preset
from app.utils.export_vault_utils import manuscript_vault_zip
from app.utils.index_format import format_index

__all__ = [
    "EXPORT_ATTRIBUTION",
    "_apply_pdf_metadata",
    "_approx_word_count_label",
    "_chapter_body_blocks",
    "_chapter_heading_lines",
    "_clean_line",
    "_export_font_docx_name",
    "_export_font_epub_stack",
    "_export_font_pdf_names",
    "_manuscript_end_marker",
    "_manuscript_front_matter",
    "_manuscript_toc_label",
    "_normalize_unicode_for_export",
    "_safe_name",
    "_scene_heading_lines",
    "_set_docx_core_properties",
    "build_character_bible_vault_context",
    "character_bible_docx",
    "character_bible_markdown",
    "character_bible_pdf",
    "character_bible_vault_folder",
    "character_bible_vault_manifest",
    "character_bible_vault_preview",
    "character_card_docx",
    "character_card_markdown",
    "character_card_pdf",
    "export_filename_base",
    "export_font_label",
    "export_font_notice",
    "format_index",
    "manuscript_docx",
    "manuscript_epub",
    "manuscript_epub_compiled",
    "manuscript_export_preset",
    "manuscript_pdf",
    "manuscript_pdf_compiled",
    "manuscript_vault_zip",
    "normalize_export_font_family",
    "novel_docx",
    "novel_epub_compiled",
    "novel_export_preset",
    "novel_pdf_compiled",
]
