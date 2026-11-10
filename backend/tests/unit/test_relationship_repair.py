import json

import pytest

from app.utils.characters.relationship_repair import (
    relationship_evidence_windows,
    verified_relationship_evidence_proposal,
)
from scripts.plan_relationship_evidence_review import (
    evidence_plan_hash,
    review_budget,
    review_prompt,
)


def test_relationship_evidence_windows_require_both_named_people():
    source = 'Mara crossed the market. "Wait," Lina said. ' + "x " * 2000 + "Mara returned."
    windows = relationship_evidence_windows(source, ["Mara"], ["Lina"])
    assert len(windows) == 1
    assert "Mara crossed" in windows[0][2]
    assert relationship_evidence_windows(source, ["Mara"], ["Jonas"]) == []
    assert relationship_evidence_windows("", ["Mara"], ["Lina"]) == []


def test_relationship_evidence_windows_prioritize_saved_quote():
    source = (
        "Mara and Lina waited at the gate. "
        + "x " * 1700
        + "Mara and Lina signed the pact together."
    )
    windows = relationship_evidence_windows(
        source,
        ["Mara"],
        ["Lina"],
        preferred_quote="Mara and Lina signed the pact together.",
    )
    assert len(windows) == 2
    assert "signed the pact" in windows[0][2]
    with pytest.raises(ValueError, match="window_limit"):
        relationship_evidence_windows(source, ["Mara"], ["Lina"], max_windows=0)


def test_verified_relationship_evidence_proposal_requires_exact_source_quote():
    source = "Mara and Lina signed the pact together."
    windows = [(100, 100 + len(source), source)]
    raw = json.dumps(
        {
            "supported": True,
            "relationship_type": "allies",
            "quote": "Mara and Lina signed the pact together.",
        }
    )
    assert verified_relationship_evidence_proposal(
        raw, windows=windows, left_name="Mara", right_name="Lina"
    ) == {
        "relationship_type": "allies",
        "quote": source,
        "source_start": 100,
        "source_end": 100 + len(source),
        "participants_anchored": True,
    }
    assert (
        verified_relationship_evidence_proposal(
            raw.replace("signed", "invented"),
            windows=windows,
            left_name="Mara",
            right_name="Lina",
        )
        is None
    )
    assert (
        verified_relationship_evidence_proposal(
            "not json", windows=windows, left_name="Mara", right_name="Lina"
        )
        is None
    )


def test_verified_relationship_evidence_proposal_marks_single_name_quote_for_review():
    source = "Mara met Lina beside the gate. Lina waved."
    raw = json.dumps(
        {"supported": True, "relationship_type": "acquaintance", "quote": "Lina waved."}
    )
    proposal = verified_relationship_evidence_proposal(
        raw,
        windows=[(0, len(source), source)],
        left_name="Mara",
        right_name="Lina",
    )
    assert proposal is not None
    assert proposal["participants_anchored"] is False


def test_relationship_review_budget_caps_calls_and_prompt_tokens(monkeypatch):
    rows = [
        {"prompt": review_prompt("Mara", "Lina", "friends", [(0, 21, "Mara met Lina at dawn.")])}
    ]
    budget = review_budget(rows)
    assert budget["calls"] == 1
    assert budget["max_total_tokens"] == budget["max_prompt_tokens"] + 300
    assert float(budget["max_cost_usd"]) <= 0.02
    with pytest.raises(ValueError, match="call_limit"):
        review_budget(rows * 13)
    monkeypatch.setattr(
        "scripts.plan_relationship_evidence_review.count_tokens", lambda _text: 2200
    )
    with pytest.raises(ValueError, match="prompt_limit"):
        review_budget(rows)


def test_evidence_plan_hash_changes_with_source_and_selected_prompt():
    rows = [{"relationship_id": "tie-1", "prompt": "Mara met Lina."}]
    original = evidence_plan_hash("repair-1", {2: "Mara met Lina."}, rows)
    assert original == evidence_plan_hash("repair-1", {2: "Mara met Lina."}, rows)
    assert original != evidence_plan_hash("repair-1", {2: "Mara missed Lina."}, rows)
    assert original != evidence_plan_hash("repair-2", {2: "Mara met Lina."}, rows)
    assert original != evidence_plan_hash(
        "repair-1", {2: "Mara met Lina."}, [{**rows[0], "prompt": "Different"}]
    )
