"""Full-chapter work planning preserves coverage and per-voice identities."""

import uuid
from pathlib import Path

from app.evaluation.voice_consistency import load_voice_evaluation_cases
from app.utils.voice_chapter_review_utils import (
    aggregate_voice_chapter_results,
    plan_voice_chapter_work,
    voice_chapter_fingerprint,
)


def cast(names):
    return [
        {"id": uuid.uuid5(uuid.NAMESPACE_DNS, name), "name": name, "aliases": []} for name in names
    ]


def test_long_chapter_plans_every_named_speaker_beyond_five():
    names = ["Mara", "Lina", "Nora", "Gregor", "Grete", "Arin", "Soren"]
    text = (
        " ".join(f'{name} said, "I will take the north road before dawn."' for name in names)
        + "\n\n"
        + ("The road stretched toward the distant city. " * 350)
    )
    assert len(text) > 12_000
    plan = plan_voice_chapter_work(text, 4, cast(names))
    assert {item["character_name"] for item in plan["work"]} == set(names)
    assert all(item["end"] - item["start"] <= 10_000 for item in plan["work"])
    assert plan["known_character_count"] == 7
    assert plan["sections"][0]["start"] == 0
    assert plan["sections"][-1]["end"] == len(text)


def test_unknown_quote_is_reported_and_named_alias_can_be_reviewed():
    characters = cast(["Mara"])
    characters[0]["aliases"] = ["Captain Mara"]
    text = (
        'Captain Mara said, "Keep the lantern lit tonight." Someone whispered, "Do not follow me."'
    )
    plan = plan_voice_chapter_work(text, 2, characters)
    assert any(item["character_name"] == "Mara" for item in plan["work"])
    assert plan["unknown_quotes"]


def test_identified_narrator_gets_separate_voice_work():
    text = 'I am Mara. I walked to the harbor before dawn. Mara said, "I will return tomorrow."'
    plan = plan_voice_chapter_work(text, 3, cast(["Mara"]))
    assert any(item["voice_mode"] == "first_person_narration" for item in plan["work"])
    assert plan["narrator_identified"] is True


def test_empty_cast_never_claims_an_unknown_quote_was_reviewed():
    plan = plan_voice_chapter_work('"Who is there?"', 1, [])
    report = aggregate_voice_chapter_results(source_text='"Who is there?"', plan=plan, completed={})
    assert report["status"] == "insufficient_evidence"
    assert report["voices"] == []
    assert report["coverage"]["unattributed_quoted_ranges"]


def test_aggregate_deduplicates_overlap_and_keeps_global_offsets():
    character_id = str(uuid.uuid4())
    work = [
        {
            "key": "one",
            "character_id": character_id,
            "character_name": "Mara",
            "voice_mode": "dialogue",
            "start": 0,
            "end": 10,
        },
        {
            "key": "two",
            "character_id": character_id,
            "character_name": "Mara",
            "voice_mode": "dialogue",
            "start": 8,
            "end": 18,
        },
    ]
    issue = {"finding_key": "same", "title": "Register shift"}
    completed = {
        key: {
            "review": {"status": "complete", "issues": [issue]},
            "warnings": [],
            "coverage": {
                "processed_ranges": [{"start": 0, "end": 10}],
                "compared_ranges": [{"start": 2, "end": 8}],
                "total_characters": 10,
            },
        }
        for key in ("one", "two")
    }
    result = aggregate_voice_chapter_results(
        source_text="a" * 18,
        plan={"work": work, "unknown_quotes": [], "narrator_identified": False},
        completed=completed,
    )
    assert result["status"] == "complete"
    assert len(result["voices"][0]["issues"]) == 1
    assert result["voices"][0]["coverage"]["processed_ranges"] == [{"start": 0, "end": 18}]
    assert result["voices"][0]["coverage"]["compared_ranges"] == [
        {"start": 2, "end": 8},
        {"start": 10, "end": 16},
    ]


def test_source_fingerprint_changes_with_edits():
    assert voice_chapter_fingerprint("a") != voice_chapter_fingerprint("a ")


def test_synthetic_long_chapters_plan_late_voices_without_gaps():
    corpus = Path(__file__).resolve().parents[2] / "evals/voice_consistency/v1/cases.json"
    cases = load_voice_evaluation_cases(corpus)
    for case_id in ("many_speakers_and_late_voice_shift", "long_narration_with_late_shift"):
        case = next(item for item in cases if item["id"] == case_id)
        names = [case["character_name"], *case.get("other_character_names", [])]
        text = case["submitted_text"]
        plan = plan_voice_chapter_work(text, case["submitted_chapter"], cast(names))
        assert plan["sections"][0]["start"] == 0
        assert plan["sections"][-1]["end"] == len(text)
        assert all(
            current["start"] <= previous["end"]
            for previous, current in zip(plan["sections"], plan["sections"][1:])
        )
        late_start = text.index(case["expected_issues"][0]["submitted_excerpt"])
        assert any(
            item["character_name"] == case["character_name"]
            and item["start"] <= late_start < item["end"]
            for item in plan["work"]
        )
        if case_id == "many_speakers_and_late_voice_shift":
            assert len({item["character_name"] for item in plan["work"]}) > 5
