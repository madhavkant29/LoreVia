from types import SimpleNamespace

from app.utils.plot_thread_utils import resolve_plot_thread_identity


def test_plot_thread_identity_resolves_paraphrased_title_from_story_signals():
    existing = SimpleNamespace(
        title="The missing moon-key",
        description="Mira must recover the silver key before the eclipse.",
        thread_type="object",
        character_ids=["Mira"],
        introduced_at=1,
        last_mentioned_at=3,
    )

    resolved = resolve_plot_thread_identity(
        [existing],
        title="Recovering the moon key",
        description="Mira searches for the silver key before the eclipse.",
        thread_type="object",
        character_names=["Mira"],
        chapter_number=4,
    )

    assert resolved is existing


def test_plot_thread_identity_does_not_merge_title_only_collision():
    existing = SimpleNamespace(
        title="The promise",
        description="A political oath between rival houses.",
        thread_type="political",
        character_ids=["Mara"],
        introduced_at=1,
        last_mentioned_at=2,
    )

    assert (
        resolve_plot_thread_identity(
            [existing],
            title="The promise",
            description="A child promises to return a lost dog.",
            thread_type="goal",
            character_names=["Noah"],
            chapter_number=3,
            minimum_score=0.75,
        )
        is None
    )
