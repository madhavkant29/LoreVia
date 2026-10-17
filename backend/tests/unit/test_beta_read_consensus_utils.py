import uuid
from types import SimpleNamespace

from app.utils.beta_read_consensus_utils import build_beta_read_consensus_payload


def _assignment(state: str = "submitted"):
    return SimpleNamespace(id=uuid.uuid4(), state=state)


def _item(assignment_id, kind, chapter_number, body, *, status="open", question_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        assignment_id=assignment_id,
        kind=kind,
        chapter_number=chapter_number,
        body=body,
        anchor_text=None,
        metadata_json={"author_status": status},
        question_id=question_id,
    )


def test_consensus_groups_hotspots_themes_and_disagreement():
    first = _assignment()
    second = _assignment("in_progress")
    items = [
        _item(first.id, "confusing", 3, "The timeline reveal was confusing"),
        _item(second.id, "favorite", 3, "The timeline reveal was my favorite"),
        _item(second.id, "boring", 4, "The middle dialogue dragged", status="resolved"),
    ]

    payload = build_beta_read_consensus_payload([first, second], items, [])

    assert payload["summary"] == {
        "reader_count": 2,
        "submitted_reader_count": 1,
        "feedback_item_count": 3,
        "open_feedback_count": 2,
        "hotspot_count": 2,
        "disagreement_count": 1,
    }
    assert payload["chapter_hotspots"][0]["chapter_number"] == 3
    assert payload["chapter_hotspots"][0]["disagreement"] is True
    assert any(
        theme["label"] == "timeline" and theme["reader_count"] == 2 for theme in payload["themes"]
    )
    assert payload["revision_candidates"][0]["chapter_number"] == 3


def test_consensus_collects_answers_by_question():
    assignment = _assignment()
    question_id = uuid.uuid4()
    question = SimpleNamespace(id=question_id, prompt="Where did you lose momentum?")
    items = [_item(assignment.id, "answer", None, "During the chase", question_id=question_id)]

    payload = build_beta_read_consensus_payload([assignment], items, [question])

    assert payload["question_consensus"][0] == {
        "question_id": str(question_id),
        "prompt": "Where did you lose momentum?",
        "answer_count": 1,
        "reader_count": 1,
        "answers": ["During the chase"],
    }


def test_consensus_groups_equivalent_questions_across_assignments():
    first = _assignment()
    second = _assignment()
    first_question_id = uuid.uuid4()
    second_question_id = uuid.uuid4()
    questions = [
        SimpleNamespace(id=first_question_id, prompt="Did the reveal land?"),
        SimpleNamespace(id=second_question_id, prompt="  DID the reveal land? "),
    ]
    items = [
        _item(first.id, "answer", None, "Yes, immediately", question_id=first_question_id),
        _item(
            second.id, "answer", None, "Only after the next scene", question_id=second_question_id
        ),
    ]

    payload = build_beta_read_consensus_payload([first, second], items, questions)

    assert len(payload["question_consensus"]) == 1
    assert payload["question_consensus"][0] == {
        "question_id": str(first_question_id),
        "prompt": "Did the reveal land?",
        "answer_count": 2,
        "reader_count": 2,
        "answers": ["Yes, immediately", "Only after the next scene"],
    }


def test_consensus_does_not_call_one_readers_mixed_reactions_disagreement():
    assignment = _assignment()
    items = [
        _item(assignment.id, "confusing", 2, "The opening was unclear"),
        _item(assignment.id, "favorite", 2, "The opening was still my favorite"),
    ]

    payload = build_beta_read_consensus_payload([assignment], items, [])

    assert payload["chapter_hotspots"][0]["disagreement"] is False
    assert payload["summary"]["disagreement_count"] == 0
