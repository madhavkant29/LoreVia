import pytest

from app.utils.characters.partition_evidence import collect_partition_evidence


def test_partition_evidence_uses_late_mention_instead_of_chunk_prefix():
    source = "An unrelated opening. " * 150 + "Mara Vale kept the final ledger."

    result = collect_partition_evidence([(2, source)], name="Mara Vale", aliases=[])

    assert len(source) > 2_200
    assert result["mention_count"] == 1
    assert result["first_chapter"] == 2
    assert result["last_seen_chapter"] == 2
    assert len(result["snippets"]) == 1
    assert result["snippet_chapters"] == [2]
    assert "Mara Vale kept the final ledger" in result["snippets"][0]
    assert result["snippets"][0] != source[:2_200]


def test_partition_evidence_samples_early_and_late_chapters_without_double_counting_aliases():
    chapters = [
        (chapter, f"Mara Vale left clue {chapter}. " + "Empty hallway. " * 170)
        for chapter in range(1, 10)
    ]

    result = collect_partition_evidence(chapters, name="Mara Vale", aliases=["Mara"])

    assert result["mention_count"] == 9
    assert result["chapter_counts"] == {chapter: 1 for chapter in range(1, 10)}
    assert len(result["snippets"]) == 6
    assert result["snippet_chapters"][0] == 1
    assert result["snippet_chapters"][-1] == 9
    assert "clue 1" in result["snippets"][0]
    assert "clue 9" in result["snippets"][-1]
    assert all("Mara Vale" in snippet for snippet in result["snippets"])


def test_partition_evidence_handles_repeated_mentions_and_role_case_variants():
    source = "The warden stood beside the door. " * 2 + "the warden closed the gate."

    result = collect_partition_evidence([(3, source)], name="the warden", aliases=[])

    assert result["mention_count"] == 3
    assert result["chapter_counts"] == {3: 3}
    assert len(result["snippets"]) == 1
    assert "the warden closed the gate" in result["snippets"][0]


def test_partition_evidence_does_not_match_partial_names_or_empty_targets():
    source = "Marabelle opened the door. The market was empty."

    assert collect_partition_evidence([(1, source)], name="Mara", aliases=[])["mention_count"] == 0
    assert collect_partition_evidence([(1, source)], name="", aliases=[])["snippets"] == []
    assert collect_partition_evidence([(1, source)], name="", aliases=[])["snippet_chapters"] == []
    with pytest.raises(ValueError, match="invalid_partition_evidence_window"):
        collect_partition_evidence([(1, source)], name="Mara", aliases=[], max_snippets=0)
