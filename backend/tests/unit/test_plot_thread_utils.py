from types import SimpleNamespace

from app.utils.plot_thread_utils import (
    build_plot_thread_payload,
    derive_plot_thread_status,
    merge_plot_thread_status,
    normalize_plot_thread_status,
    plot_thread_lookup_key,
)


def test_plot_thread_lookup_key_normalizes_spacing_and_punctuation():
    assert plot_thread_lookup_key("Joren promised to return the amulet!") == "joren promised to return the amulet"


def test_normalize_plot_thread_status_maps_legacy_ongoing_to_developing():
    assert normalize_plot_thread_status("ongoing") == "developing"


def test_merge_plot_thread_status_marks_reopened_resolved_thread_as_contradicted():
    assert merge_plot_thread_status("resolved", "developing") == "contradicted"


def test_derive_plot_thread_status_flags_stale_threads():
    assert derive_plot_thread_status(
        "developing",
        introduced_at=2,
        last_mentioned_at=3,
        resolved_at=None,
        current_chapter=10,
    ) == "possibly_abandoned"
    assert derive_plot_thread_status(
        "developing",
        introduced_at=2,
        last_mentioned_at=3,
        resolved_at=None,
        current_chapter=16,
    ) == "forgotten"


def test_build_plot_thread_payload_exposes_lifecycle_metadata():
    payload = build_plot_thread_payload(
        SimpleNamespace(
            id="thread-1",
            title="Joren promised to return the amulet",
            thread_type="promise",
            status="developing",
            description="Mira is still waiting on the promise.",
            introduced_at=9,
            last_mentioned_at=14,
            resolved_at=None,
            mention_count=3,
            importance=8,
            note="Needs payoff before the finale.",
            character_ids=["Joren", "Mira"],
        ),
        current_chapter=14,
    )

    assert payload["first_mentioned"] == 9
    assert payload["last_mentioned"] == 14
    assert payload["related_characters"] == ["Joren", "Mira"]
    assert payload["risk"] is not None
    assert payload["suggested_action"] is not None
