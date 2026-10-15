DEFAULT_WRITING_TEMPLATES = [
    {
        "id": "chapter-three-act",
        "kind": "chapter",
        "title": "Chapter Three-Beat",
        "description": "Open with pressure, pivot in the middle, end on a story-moving turn.",
        "content": (
            "Opening beat\n"
            "- What changes immediately in this chapter?\n\n"
            "Middle escalation\n"
            "- What complication or reversal raises the cost?\n\n"
            "Closing turn\n"
            "- What question, threat, or choice launches the next chapter?"
        ),
    },
    {
        "id": "scene-goal-conflict-disaster",
        "kind": "scene",
        "title": "Scene Goal / Conflict / Disaster",
        "description": "Classic scene structure for momentum and tension.",
        "content": (
            "Goal\n"
            "- What does the point-of-view character want right now?\n\n"
            "Conflict\n"
            "- Who or what blocks them?\n\n"
            "Disaster / turn\n"
            "- What goes wrong, changes, or costs more than expected?"
        ),
    },
    {
        "id": "story-five-pivots",
        "kind": "story",
        "title": "Story Five Pivots",
        "description": "A compact scaffold for act structure and turning points.",
        "content": (
            "Setup promise\n"
            "- What emotional and plot promise does the story make?\n\n"
            "Inciting shift\n"
            "- What forces the protagonist out of stasis?\n\n"
            "Midpoint change\n"
            "- What truth, reveal, or victory changes the meaning of the conflict?\n\n"
            "Dark turn\n"
            "- What loss or collapse strips away the easy path?\n\n"
            "Climax and aftermath\n"
            "- What final choice resolves the central pressure?"
        ),
    },
]

DEFAULT_WRITER_WORKSPACE = {
    "word_count_goals": {
        "chapter_target": 2500,
        "book_target": 80000,
        "session_target": 1000,
    },
    "goal_calendar": [],
    "corkboard_cards": [],
    "templates": DEFAULT_WRITING_TEMPLATES,
    "publishing": {
        "active_preset": "standard_manuscript",
        "trim_size": "6x9",
        "include_title_page": True,
        "mirror_margins": True,
    },
    "editor_preferences": {
        "font_family": "Times New Roman",
        "font_size": 12,
        "line_height": 1.8,
        "manuscript_width": "standard",
        "show_page_guides": True,
        "focus_mode": False,
        "default_scene_separator": "asterisks",
    },
    "reading_themes": {
        "active_theme": "light",
        "allow_dark_mode": True,
    },
    "typewriter_mode": {
        "enabled": False,
        "center_offset_px": 160,
    },
    "manuscript_layout": {
        "margins": "standard",
        "page_size": "letter",
        "orientation": "portrait",
        "show_headers": True,
        "show_footers": True,
        "page_numbering": True,
        "different_first_page": True,
    },
    "structure_tree": [],
    "manuscript_front_matter": {
        "author_name": "",
        "pen_name": "",
        "contact_email": "",
        "contact_phone": "",
        "contact_address": "",
        "title": "",
        "subtitle": "",
        "header_last_name": "",
        "header_title": "",
        "approximate_word_count_override": None,
        "dedication": "",
        "acknowledgments": "",
        "epigraph": "",
        "prologue": "",
        "include_dedication": False,
        "include_acknowledgments": False,
        "include_epigraph": False,
        "include_prologue": False,
    },
    "novel_preface": "",
    "novel_front_matter": {
        "dedication": "",
        "acknowledgements": "",
        "copyright_page": "",
        "about_author": "",
        "series_book_list": "",
    },
    "novel_epub_metadata": {
        "publisher": "",
        "language": "en",
        "isbn": "",
        "description": "",
        "series_name": "",
        "series_number": "",
    },
    "revision_board": {
        "items": [],
        "last_generated_at": None,
    },
    "activation": {
        "completed_at": None,
        "completion_action": None,
        "completed_finding_id": None,
    },
    "revision_recent_edits": [],
    "revision_rounds": [],
    "ai_beta_reader": {"reports": []},
    "first_impression": {
        "status": "not_started",
        "job_id": None,
        "report_id": None,
        "request_hash": None,
        "source_fingerprint": None,
        "started_at": None,
        "completed_at": None,
        "error_code": None,
    },
    "index_format": "arabic",
    "source_fingerprint": None,
    "reprocess": {
        "auto_reprocess_enabled": True,
        "pending_chapters": [],
    },
    "processing": None,
}
