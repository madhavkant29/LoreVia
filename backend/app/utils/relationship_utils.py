from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from math import inf
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character, CharacterRelationshipCandidate
from app.models.intelligence import CharacterRelationship
from app.utils.characters.relationship_evidence import relationship_quote_anchors_participants


def clean_relationship_text(value: object | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def normalize_relationship_type_value(value: object | None) -> str:
    text = clean_relationship_text(value)
    if not text:
        return "connection"
    return _normalize_relationship_label_token(text) or "connection"


RELATIONSHIP_LABEL_DISPLAY: dict[str, str] = {
    "connection": "connection",
    "ally": "ally",
    "enemy": "enemy",
    "family": "family",
    "mentor": "mentor",
    "neutral": "neutral",
    "political": "political",
    "rival": "rival",
    "romantic": "romantic",
    "friend": "friend",
    "friend_toxic": "friend (toxic)",
    "friend_romantic": "friend (romantic)",
    "friend_codependent": "friend (codependent)",
    "friend_platonic": "friend (platonic)",
    "friend_casual": "friend (casual)",
    "friend_open": "friend (open)",
    "best_friend": "best friend",
    "childhood_friend": "childhood friend",
    "former_friend": "former friend",
    "secret_friend": "secret friend",
    "loyal_friend": "loyal friend",
    "protective_friend": "protective friend",
    "jealous_friend": "jealous friend",
    "one_sided_friend": "one-sided friend",
    "manipulative_friend": "manipulative friend",
    "fake_friend": "fake friend",
    "enemy_turned_friend": "enemy-turned-friend",
    "friend_turned_enemy": "friend-turned-enemy",
    "confidant": "confidant",
    "drinking_buddy": "drinking buddy",
    "travel_companion": "travel companion",
    "online_friend": "online friend",
    "pen_pal": "pen pal",
    "social_circle_member": "social circle member",
    "roommate": "roommate",
    "housemate": "housemate",
    "cousin_brother": "cousin (brother)",
    "cousin_sister": "cousin (sister)",
    "sibling": "sibling",
    "brother": "brother",
    "sister": "sister",
    "half_brother": "half-brother",
    "half_sister": "half-sister",
    "stepfather": "stepfather",
    "stepmother": "stepmother",
    "stepsibling": "stepsibling",
    "father": "father",
    "mother": "mother",
    "son": "son",
    "daughter": "daughter",
    "grandmother_maternal": "grandmother (maternal)",
    "grandmother_paternal": "grandmother (paternal)",
    "grandfather_maternal": "grandfather (maternal)",
    "grandfather_paternal": "grandfather (paternal)",
    "uncle": "uncle",
    "aunt": "aunt",
    "nephew": "nephew",
    "niece": "niece",
    "in_law": "in-law",
    "father_in_law": "father-in-law",
    "mother_in_law": "mother-in-law",
    "brother_in_law": "brother-in-law",
    "sister_in_law": "sister-in-law",
    "godfather": "godfather",
    "godmother": "godmother",
    "guardian": "guardian",
    "foster_parent": "foster parent",
    "adopted_parent": "adopted parent",
    "adopted_child": "adopted child",
    "ancestor": "ancestor",
    "descendant": "descendant",
    "heir": "heir",
    "family_rival": "family rival",
    "estranged_family": "estranged family",
    "disowned_child": "disowned child",
    "illegitimate_child": "illegitimate child",
    "missing_relative": "missing relative",
    "lover": "lover",
    "crush": "crush",
    "mutual_crush": "mutual crush",
    "unrequited_love": "unrequited love",
    "secret_lover": "secret lover",
    "ex_lover": "ex-lover",
    "ex_partner": "ex-partner",
    "boyfriend": "boyfriend",
    "girlfriend": "girlfriend",
    "fiance": "fiance",
    "fiancee": "fiancee",
    "husband": "husband",
    "wife": "wife",
    "spouse": "spouse",
    "affair_partner": "affair partner",
    "forbidden_romance": "forbidden romance",
    "arranged_marriage_partner": "arranged marriage partner",
    "political_marriage_partner": "political marriage partner",
    "soulmate": "soulmate",
    "casual_fling": "casual fling",
    "friends_with_benefits": "friends-with-benefits",
    "love_triangle_rival": "love triangle rival",
    "romantic_rival": "romantic rival",
    "toxic_lover": "toxic lover",
    "obsessive_lover": "obsessive lover",
    "protective_lover": "protective lover",
    "superior": "superior",
    "subordinate": "subordinate",
    "commander": "commander",
    "soldier": "soldier",
    "ruler": "ruler",
    "subject": "subject",
    "king": "king",
    "queen": "queen",
    "prince": "prince",
    "princess": "princess",
    "lord": "lord",
    "lady": "lady",
    "servant": "servant",
    "master": "master",
    "slave": "slave",
    "owner": "owner",
    "bodyguard": "bodyguard",
    "client": "client",
    "patron": "patron",
    "sponsor": "sponsor",
    "benefactor": "benefactor",
    "debtor": "debtor",
    "creditor": "creditor",
    "blackmailer": "blackmailer",
    "hostage": "hostage",
    "captor": "captor",
    "prisoner": "prisoner",
    "handler": "handler",
    "asset": "asset",
    "informant": "informant",
    "spy": "spy",
    "mole": "mole",
    "double_agent": "double agent",
    "puppet": "puppet",
    "controller": "controller",
    "pawn_tool": "pawn (tool)",
    "enforcer": "enforcer",
    "henchman": "henchman",
    "right_hand_person": "right-hand person",
    "leader": "leader",
    "boss": "boss",
    "employee": "employee",
    "manager": "manager",
    "assistant": "assistant",
    "intern": "intern",
    "co_founder": "co-founder",
    "business_partner": "business partner",
    "investor": "investor",
    "contractor": "contractor",
    "consultant": "consultant",
    "customer": "customer",
    "colleague": "colleague",
    "rival_colleague": "rival colleague",
    "former_colleague": "former colleague",
    "workplace_rival": "workplace rival",
    "work_mentor": "work mentor",
    "work_friend": "work friend",
    "workplace_friend": "workplace friend",
    "work_spouse": "work spouse",
    "team_member": "team member",
    "teammate": "teammate",
    "supervisor": "supervisor",
    "apprentice": "apprentice",
    "protege": "protege",
    "teacher": "teacher",
    "student": "student",
    "professor": "professor",
    "researcher": "researcher",
    "doctor": "doctor",
    "patient": "patient",
    "lawyer": "lawyer",
    "nemesis": "nemesis",
    "bully": "bully",
    "victim": "victim",
    "abuser": "abuser",
    "survivor": "survivor",
    "hunter": "hunter",
}

RELATIONSHIP_LABEL_ALIASES: dict[str, str] = {
    "freind": "friend",
    "friend_toxic": "friend_toxic",
    "toxic_friend": "friend_toxic",
    "romantic_friend": "friend_romantic",
    "codependent_friend": "friend_codependent",
    "platonic_friend": "friend_platonic",
    "casual_friend": "friend_casual",
    "open_friend": "friend_open",
    "cousin_bro": "cousin_brother",
    "cousin_sis": "cousin_sister",
    "sibling_brother": "brother",
    "sibling_sister": "sister",
    "half_sibling_brother": "half_brother",
    "half_sibling_sister": "half_sister",
    "maternal_grandmother": "grandmother_maternal",
    "paternal_grandmother": "grandmother_paternal",
    "maternal_grandfather": "grandfather_maternal",
    "paternal_grandfather": "grandfather_paternal",
    "fiance": "fiance",
    "fiancee": "fiancee",
    "fiance_": "fiance",
    "fiancee_": "fiancee",
    "fwb": "friends_with_benefits",
    "workplace_freind": "workplace_friend",
    "workplace_friend": "workplace_friend",
    "work_friend": "work_friend",
    "pawn": "pawn_tool",
    "tool": "pawn_tool",
    "subject": "subject",
}

RELATIONSHIP_SUPERSEDES: dict[str, set[str]] = {
    "half_brother": {"brother", "sibling"},
    "half_sister": {"sister", "sibling"},
    "stepfather": {"father"},
    "stepmother": {"mother"},
    "ex_lover": {"lover"},
    "ex_partner": {"lover", "boyfriend", "girlfriend", "spouse"},
    "former_friend": {"friend"},
    "friend_turned_enemy": {"friend"},
    "enemy_turned_friend": {"enemy"},
    "friend_toxic": {"friend"},
    "friend_romantic": {"friend"},
    "friend_codependent": {"friend"},
    "friend_platonic": {"friend"},
    "friend_casual": {"friend"},
    "friend_open": {"friend"},
    "toxic_lover": {"lover"},
    "obsessive_lover": {"lover"},
    "protective_lover": {"lover"},
    "workplace_friend": {"friend"},
    "work_friend": {"friend"},
}

RELATIONSHIP_PRIMARY_PRIORITY: tuple[str, ...] = (
    "half_sister",
    "half_brother",
    "sister",
    "brother",
    "spouse",
    "husband",
    "wife",
    "father",
    "mother",
    "son",
    "daughter",
    "lover",
    "ex_lover",
    "boyfriend",
    "girlfriend",
    "forbidden_romance",
    "mentor",
    "teacher",
    "student",
    "master",
    "slave",
    "owner",
    "captor",
    "prisoner",
    "enemy",
    "rival",
    "friend_toxic",
    "friend_romantic",
    "friend",
    "workplace_friend",
    "colleague",
    "ally",
    "family",
    "romantic",
    "political",
    "neutral",
)

GENERIC_RELATIONSHIP_TYPES = {
    "connection",
    "neutral",
    "family",
    "romantic",
    "ally",
    "friend",
    "political",
}


def _normalize_relationship_label_token(value: object | None) -> str | None:
    text = clean_relationship_text(value)
    if not text:
        return None
    normalized = text.casefold().replace("&", " and ")
    normalized = normalized.replace("'", "")
    normalized = normalized.replace("(", " ").replace(")", " ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("-", "_")
    normalized = "_".join(normalized.split())
    normalized = normalized.replace("__", "_").strip("_")
    normalized = RELATIONSHIP_LABEL_ALIASES.get(normalized, normalized)
    return normalized if normalized in RELATIONSHIP_LABEL_DISPLAY else normalized


def _iter_relationship_label_values(value: object | None) -> Iterable[object]:
    if value is None:
        return []
    if isinstance(value, str):
        split = value.replace("+", ",").replace(";", ",").split(",")
        return [item for item in split if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (dict, bytes)):
        return value
    return [value]


def normalize_relationship_labels(value: object | None) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for raw in _iter_relationship_label_values(value):
        label = _normalize_relationship_label_token(raw)
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)

    superseded: set[str] = set()
    for label in labels:
        superseded.update(RELATIONSHIP_SUPERSEDES.get(label, set()))
    return [label for label in labels if label not in superseded]


def relationship_label_display(label: object | None) -> str:
    normalized = _normalize_relationship_label_token(label) or "connection"
    return RELATIONSHIP_LABEL_DISPLAY.get(normalized, normalized.replace("_", " "))


def relationship_labels_display(labels: object | None) -> list[str]:
    return [relationship_label_display(label) for label in normalize_relationship_labels(labels)]


def derive_relationship_primary_type(
    rel_type: object | None,
    *,
    shared_labels: object | None = None,
    character_a_to_b_labels: object | None = None,
    character_b_to_a_labels: object | None = None,
) -> str:
    normalized_type = normalize_relationship_type_value(rel_type)
    labels = (
        normalize_relationship_labels(character_a_to_b_labels)
        + normalize_relationship_labels(character_b_to_a_labels)
        + normalize_relationship_labels(shared_labels)
    )
    if labels and normalized_type in GENERIC_RELATIONSHIP_TYPES:
        ranked = sorted(
            labels,
            key=lambda label: (
                RELATIONSHIP_PRIMARY_PRIORITY.index(label)
                if label in RELATIONSHIP_PRIMARY_PRIORITY
                else len(RELATIONSHIP_PRIMARY_PRIORITY)
            ),
        )
        return ranked[0]
    return normalized_type


def relationship_labels_signature(
    *,
    shared_labels: object | None,
    character_a_to_b_labels: object | None,
    character_b_to_a_labels: object | None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    return (
        tuple(normalize_relationship_labels(shared_labels)),
        tuple(normalize_relationship_labels(character_a_to_b_labels)),
        tuple(normalize_relationship_labels(character_b_to_a_labels)),
    )


def normalize_relationship_sentiment_value(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def canonical_relationship_pair_ids(
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID]:
    if str(character_a_id) <= str(character_b_id):
        return character_a_id, character_b_id
    return character_b_id, character_a_id


def canonical_relationship_pair_key(
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
) -> tuple[str, str]:
    left, right = canonical_relationship_pair_ids(character_a_id, character_b_id)
    return str(left), str(right)


def relationship_pair_matches(
    relationship: CharacterRelationship,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
) -> bool:
    pair = canonical_relationship_pair_ids(character_a_id, character_b_id)
    return (
        canonical_relationship_pair_ids(
            getattr(relationship, "character_a_id"),
            getattr(relationship, "character_b_id"),
        )
        == pair
    )


def relationship_pair_key_for_row(relationship: CharacterRelationship) -> tuple[str, str]:
    return canonical_relationship_pair_key(
        getattr(relationship, "character_a_id"),
        getattr(relationship, "character_b_id"),
    )


def relationship_state_signature(
    *,
    rel_type: object | None,
    sentiment: object | None,
    description: object | None,
    shared_labels: object | None = None,
    character_a_to_b_labels: object | None = None,
    character_b_to_a_labels: object | None = None,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], float | None, str]:
    normalized_shared, normalized_a_to_b, normalized_b_to_a = relationship_labels_signature(
        shared_labels=shared_labels,
        character_a_to_b_labels=character_a_to_b_labels,
        character_b_to_a_labels=character_b_to_a_labels,
    )
    return (
        derive_relationship_primary_type(
            rel_type,
            shared_labels=normalized_shared,
            character_a_to_b_labels=normalized_a_to_b,
            character_b_to_a_labels=normalized_b_to_a,
        ),
        normalized_shared,
        normalized_a_to_b,
        normalized_b_to_a,
        normalize_relationship_sentiment_value(sentiment),
        clean_relationship_text(description) or "",
    )


def relationship_state_signature_for_row(
    relationship: CharacterRelationship,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], float | None, str]:
    return relationship_state_signature(
        rel_type=getattr(relationship, "rel_type", None),
        sentiment=getattr(relationship, "sentiment", None),
        description=getattr(relationship, "description", None),
        shared_labels=getattr(relationship, "shared_labels", None),
        character_a_to_b_labels=getattr(relationship, "character_a_to_b_labels", None),
        character_b_to_a_labels=getattr(relationship, "character_b_to_a_labels", None),
    )


def relationship_effective_status(relationship: CharacterRelationship, chapter: int) -> str:
    to_chapter = getattr(relationship, "to_chapter", None)
    if to_chapter is not None and to_chapter < chapter:
        return "ended"
    return "ongoing"


def _relationship_sort_key(
    relationship: CharacterRelationship,
    *,
    preferred_relationship_id: uuid.UUID | None = None,
) -> tuple[int, int, float, str]:
    relationship_id = getattr(relationship, "id", None)
    to_chapter = getattr(relationship, "to_chapter", None)
    preferred_order = (
        1 if preferred_relationship_id and relationship_id == preferred_relationship_id else 0
    )
    return (
        int(getattr(relationship, "from_chapter", 0) or 0),
        preferred_order,
        -(float(to_chapter) if to_chapter is not None else inf),
        str(relationship_id),
    )


def canonicalize_relationship_rows(
    relationships: Iterable[CharacterRelationship],
    *,
    preferred_relationship_id: uuid.UUID | None = None,
) -> tuple[list[CharacterRelationship], list[CharacterRelationship]]:
    rows = sorted(
        list(relationships),
        key=lambda relationship: _relationship_sort_key(
            relationship,
            preferred_relationship_id=preferred_relationship_id,
        ),
    )
    kept: list[CharacterRelationship] = []
    removed: list[CharacterRelationship] = []
    index = 0
    while index < len(rows):
        relationship = rows[index]
        if getattr(relationship, "from_chapter", None) is None:
            relationship.from_chapter = 1
        if not hasattr(relationship, "to_chapter"):
            relationship.to_chapter = None
        if not hasattr(relationship, "shared_labels"):
            relationship.shared_labels = []
        if not hasattr(relationship, "character_a_to_b_labels"):
            relationship.character_a_to_b_labels = []
        if not hasattr(relationship, "character_b_to_a_labels"):
            relationship.character_b_to_a_labels = []
        if not hasattr(relationship, "label_evidence"):
            relationship.label_evidence = {}
        if not hasattr(relationship, "id"):
            relationship.id = None
        if not hasattr(relationship, "book_id"):
            relationship.book_id = None
        original_a_id = relationship.character_a_id
        left_id, right_id = canonical_relationship_pair_ids(
            relationship.character_a_id,
            relationship.character_b_id,
        )
        relationship.character_a_id = left_id
        relationship.character_b_id = right_id
        if original_a_id != left_id:
            relationship.character_a_to_b_labels, relationship.character_b_to_a_labels = (
                relationship.character_b_to_a_labels,
                relationship.character_a_to_b_labels,
            )
        relationship.shared_labels = normalize_relationship_labels(relationship.shared_labels)
        relationship.character_a_to_b_labels = normalize_relationship_labels(
            relationship.character_a_to_b_labels
        )
        relationship.character_b_to_a_labels = normalize_relationship_labels(
            relationship.character_b_to_a_labels
        )
        relationship.rel_type = derive_relationship_primary_type(
            relationship.rel_type,
            shared_labels=relationship.shared_labels,
            character_a_to_b_labels=relationship.character_a_to_b_labels,
            character_b_to_a_labels=relationship.character_b_to_a_labels,
        )
        relationship.description = clean_relationship_text(relationship.description)
        relationship.sentiment = normalize_relationship_sentiment_value(relationship.sentiment)

        if relationship.from_chapter < 1:
            relationship.from_chapter = 1
        if (
            relationship.to_chapter is not None
            and relationship.to_chapter < relationship.from_chapter
        ):
            relationship.to_chapter = relationship.from_chapter

        if not kept:
            kept.append(relationship)
            index += 1
            continue

        previous = kept[-1]
        previous_signature = relationship_state_signature_for_row(previous)
        current_signature = relationship_state_signature_for_row(relationship)
        previous_to = previous.to_chapter
        current_to = relationship.to_chapter

        if previous_signature == current_signature:
            previous_open_ended = previous_to is None
            current_open_ended = current_to is None
            previous_covers_current = previous_open_ended or (
                previous_to is not None and previous_to >= relationship.from_chapter - 1
            )
            if previous_covers_current:
                if previous_open_ended or current_open_ended:
                    previous.to_chapter = None
                elif current_to is not None:
                    previous.to_chapter = max(previous_to or current_to, current_to)
                removed.append(relationship)
                index += 1
                continue

        if relationship.from_chapter <= previous.from_chapter:
            original_previous_to = previous.to_chapter
            if (
                relationship.from_chapter == previous.from_chapter
                and current_to is not None
                and (original_previous_to is None or original_previous_to > current_to)
                and previous_signature != current_signature
            ):
                tail = CharacterRelationship(
                    book_id=previous.book_id,
                    character_a_id=previous.character_a_id,
                    character_b_id=previous.character_b_id,
                    rel_type=previous.rel_type,
                    sentiment=previous.sentiment,
                    description=previous.description,
                    from_chapter=current_to + 1,
                    to_chapter=original_previous_to,
                    shared_labels=list(previous.shared_labels or []),
                    character_a_to_b_labels=list(previous.character_a_to_b_labels or []),
                    character_b_to_a_labels=list(previous.character_b_to_a_labels or []),
                    label_evidence=dict(previous.label_evidence or {}),
                )
                insert_at = len(rows)
                tail_sort_key = _relationship_sort_key(
                    tail,
                    preferred_relationship_id=preferred_relationship_id,
                )
                for offset in range(index + 1, len(rows)):
                    if (
                        _relationship_sort_key(
                            rows[offset],
                            preferred_relationship_id=preferred_relationship_id,
                        )
                        > tail_sort_key
                    ):
                        insert_at = offset
                        break
                rows.insert(insert_at, tail)
            removed.append(previous)
            kept[-1] = relationship
            index += 1
            continue

        if previous.to_chapter is None or previous.to_chapter >= relationship.from_chapter:
            original_previous_to = previous.to_chapter
            if (
                current_to is not None
                and (original_previous_to is None or original_previous_to > current_to)
                and previous_signature != current_signature
            ):
                tail = CharacterRelationship(
                    book_id=previous.book_id,
                    character_a_id=previous.character_a_id,
                    character_b_id=previous.character_b_id,
                    rel_type=previous.rel_type,
                    sentiment=previous.sentiment,
                    description=previous.description,
                    from_chapter=current_to + 1,
                    to_chapter=original_previous_to,
                    shared_labels=list(previous.shared_labels or []),
                    character_a_to_b_labels=list(previous.character_a_to_b_labels or []),
                    character_b_to_a_labels=list(previous.character_b_to_a_labels or []),
                    label_evidence=dict(previous.label_evidence or {}),
                )
                insert_at = len(rows)
                tail_sort_key = _relationship_sort_key(
                    tail,
                    preferred_relationship_id=preferred_relationship_id,
                )
                for offset in range(index + 1, len(rows)):
                    if (
                        _relationship_sort_key(
                            rows[offset],
                            preferred_relationship_id=preferred_relationship_id,
                        )
                        > tail_sort_key
                    ):
                        insert_at = offset
                        break
                rows.insert(insert_at, tail)
            previous.to_chapter = relationship.from_chapter - 1
            if previous.to_chapter < previous.from_chapter:
                removed.append(previous)
                kept[-1] = relationship
                index += 1
                continue

        kept.append(relationship)
        index += 1

    return kept, removed


def canonicalize_relationship_book_rows(
    relationships: Iterable[CharacterRelationship],
) -> tuple[list[CharacterRelationship], list[CharacterRelationship]]:
    grouped: dict[tuple[str, str], list[CharacterRelationship]] = defaultdict(list)
    for relationship in relationships:
        grouped[relationship_pair_key_for_row(relationship)].append(relationship)

    kept: list[CharacterRelationship] = []
    removed: list[CharacterRelationship] = []
    for pair_rows in grouped.values():
        pair_kept, pair_removed = canonicalize_relationship_rows(pair_rows)
        kept.extend(pair_kept)
        removed.extend(pair_removed)
    kept.sort(key=lambda relationship: _relationship_sort_key(relationship))
    return kept, removed


async def normalize_relationship_pair_timeline(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    preferred_relationship_id: uuid.UUID | None = None,
) -> tuple[list[CharacterRelationship], list[CharacterRelationship]]:
    left_id, right_id = canonical_relationship_pair_ids(character_a_id, character_b_id)
    rows = (
        (
            await db.execute(
                select(CharacterRelationship).where(
                    CharacterRelationship.book_id == book_id,
                    or_(
                        and_(
                            CharacterRelationship.character_a_id == left_id,
                            CharacterRelationship.character_b_id == right_id,
                        ),
                        and_(
                            CharacterRelationship.character_a_id == right_id,
                            CharacterRelationship.character_b_id == left_id,
                        ),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    kept, removed = canonicalize_relationship_rows(
        rows,
        preferred_relationship_id=preferred_relationship_id,
    )
    for relationship in kept:
        if relationship.id is None:
            db.add(relationship)
    for relationship in removed:
        if not getattr(relationship, "edited_by_author", False):
            await db.delete(relationship)
    await db.flush()
    return kept, removed


async def upsert_relationship_timeline_state(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    character_a_id: uuid.UUID,
    character_b_id: uuid.UUID,
    rel_type: str,
    sentiment: float | None,
    description: str | None,
    from_chapter: int,
    to_chapter: int | None = None,
    relationship_id: uuid.UUID | None = None,
    shared_labels: object | None = None,
    character_a_to_b_labels: object | None = None,
    character_b_to_a_labels: object | None = None,
    label_evidence: dict[str, Any] | None = None,
) -> tuple[CharacterRelationship, bool]:
    left_id, right_id = canonical_relationship_pair_ids(character_a_id, character_b_id)
    normalized_shared = normalize_relationship_labels(shared_labels)
    normalized_a_to_b = normalize_relationship_labels(character_a_to_b_labels)
    normalized_b_to_a = normalize_relationship_labels(character_b_to_a_labels)
    if character_a_id != left_id:
        normalized_a_to_b, normalized_b_to_a = normalized_b_to_a, normalized_a_to_b
    normalized_type = derive_relationship_primary_type(
        rel_type,
        shared_labels=normalized_shared,
        character_a_to_b_labels=normalized_a_to_b,
        character_b_to_a_labels=normalized_b_to_a,
    )
    target_relationship: CharacterRelationship | None = None
    if relationship_id is not None:
        target_relationship = await db.get(CharacterRelationship, relationship_id)
        if target_relationship is None:
            raise ValueError("Relationship not found")
        canonical_a_to_b_provided = (
            character_a_to_b_labels is not None
            if character_a_id == left_id
            else character_b_to_a_labels is not None
        )
        canonical_b_to_a_provided = (
            character_b_to_a_labels is not None
            if character_a_id == left_id
            else character_a_to_b_labels is not None
        )
        if shared_labels is None:
            normalized_shared = normalize_relationship_labels(
                getattr(target_relationship, "shared_labels", None)
            )
        if not canonical_a_to_b_provided:
            normalized_a_to_b = normalize_relationship_labels(
                getattr(target_relationship, "character_a_to_b_labels", None)
            )
        if not canonical_b_to_a_provided:
            normalized_b_to_a = normalize_relationship_labels(
                getattr(target_relationship, "character_b_to_a_labels", None)
            )
        if label_evidence is None:
            label_evidence = dict(getattr(target_relationship, "label_evidence", None) or {})
        normalized_type = derive_relationship_primary_type(
            rel_type,
            shared_labels=normalized_shared,
            character_a_to_b_labels=normalized_a_to_b,
            character_b_to_a_labels=normalized_b_to_a,
        )
    if target_relationship is None:
        _existing_curated = await db.execute(
            select(CharacterRelationship)
            .where(
                CharacterRelationship.book_id == book_id,
                CharacterRelationship.character_a_id == left_id,
                CharacterRelationship.character_b_id == right_id,
                CharacterRelationship.edited_by_author.is_(True),
            )
            .limit(1)
        )
        curated = _existing_curated.scalar_one_or_none()
        if curated is not None:
            return curated, False
        target_relationship = CharacterRelationship(
            book_id=book_id,
            character_a_id=left_id,
            character_b_id=right_id,
            rel_type=normalized_type,
            sentiment=normalize_relationship_sentiment_value(sentiment),
            description=clean_relationship_text(description),
            from_chapter=from_chapter,
            to_chapter=to_chapter,
            shared_labels=normalized_shared,
            character_a_to_b_labels=normalized_a_to_b,
            character_b_to_a_labels=normalized_b_to_a,
            label_evidence=label_evidence or {},
        )
        db.add(target_relationship)

    if getattr(target_relationship, "edited_by_author", False):
        return target_relationship, False

    target_relationship.book_id = book_id
    target_relationship.character_a_id = left_id
    target_relationship.character_b_id = right_id
    target_relationship.rel_type = normalized_type
    target_relationship.sentiment = normalize_relationship_sentiment_value(sentiment)
    target_relationship.description = clean_relationship_text(description)
    target_relationship.from_chapter = from_chapter
    target_relationship.to_chapter = to_chapter
    target_relationship.shared_labels = normalized_shared
    target_relationship.character_a_to_b_labels = normalized_a_to_b
    target_relationship.character_b_to_a_labels = normalized_b_to_a
    target_relationship.label_evidence = label_evidence or {}
    await db.flush()

    kept, removed = await normalize_relationship_pair_timeline(
        db,
        book_id=book_id,
        character_a_id=left_id,
        character_b_id=right_id,
        preferred_relationship_id=target_relationship.id,
    )
    removed_ids = {relationship.id for relationship in removed}
    created_new_state = target_relationship.id not in removed_ids
    if created_new_state:
        return target_relationship, True

    target_signature = relationship_state_signature_for_row(target_relationship)
    for relationship in kept:
        if relationship_state_signature_for_row(relationship) != target_signature:
            continue
        if relationship.from_chapter <= from_chapter and (
            relationship.to_chapter is None or relationship.to_chapter >= from_chapter
        ):
            return relationship, False
    return kept[-1], False


async def repair_relationship_timelines(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, int]:
    rows = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
            )
        )
        .scalars()
        .all()
    )
    removed_total = 0
    repaired_pairs = 0
    normalized_rows = 0
    grouped: dict[tuple[str, str], list[CharacterRelationship]] = defaultdict(list)
    for relationship in rows:
        grouped[relationship_pair_key_for_row(relationship)].append(relationship)
    for pair_rows in grouped.values():
        original_state = [
            (
                relationship.character_a_id,
                relationship.character_b_id,
                relationship.rel_type,
                relationship.sentiment,
                relationship.description,
                relationship.from_chapter,
                relationship.to_chapter,
            )
            for relationship in pair_rows
        ]
        kept, removed = canonicalize_relationship_rows(pair_rows)
        for relationship in kept:
            if relationship.id is None:
                db.add(relationship)
        removed_total += len(removed)
        normalized_rows += len(kept)
        if removed:
            repaired_pairs += 1
        else:
            current_state = [
                (
                    relationship.character_a_id,
                    relationship.character_b_id,
                    relationship.rel_type,
                    relationship.sentiment,
                    relationship.description,
                    relationship.from_chapter,
                    relationship.to_chapter,
                )
                for relationship in kept
            ]
            if current_state != original_state:
                repaired_pairs += 1
        for relationship in removed:
            if not getattr(relationship, "edited_by_author", False):
                await db.delete(relationship)

    candidate_rows = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book_id
                )
            )
        )
        .scalars()
        .all()
    )
    updated_candidates = 0
    for candidate in candidate_rows:
        evidence = dict(candidate.evidence or {})
        changed = False
        if candidate.matched_character_a_id and candidate.matched_character_b_id:
            left_id, right_id = canonical_relationship_pair_ids(
                candidate.matched_character_a_id,
                candidate.matched_character_b_id,
            )
            if candidate.matched_character_a_id != left_id:
                candidate.matched_character_a_id = left_id
                changed = True
            if candidate.matched_character_b_id != right_id:
                candidate.matched_character_b_id = right_id
                changed = True
            pair_key = [str(left_id), str(right_id)]
            if evidence.get("pair_key") != pair_key:
                evidence["pair_key"] = pair_key
                changed = True
        if changed:
            candidate.evidence = evidence
            updated_candidates += 1

    await db.flush()
    return {
        "pairs_repaired": repaired_pairs,
        "relationships_deleted": removed_total,
        "relationships_remaining": normalized_rows,
        "relationship_candidates_updated": updated_candidates,
    }


async def reconcile_extracted_relationships(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
) -> dict[str, int]:
    from app.engine.character.deduplicator import resolve_character_match_ids
    from app.utils.characters.extraction import resolve_character_reference_from_roster
    from app.utils.characters.governance import is_cast_visible_character
    from app.utils.characters.identity import (
        family_role_reference,
        filter_character_identity_aliases,
    )
    from app.utils.characters.serialization import is_protected_character

    characters = (
        (await db.execute(select(Character).where(Character.book_id == book_id))).scalars().all()
    )
    sanitized_aliases = 0
    for character in characters:
        if is_protected_character(character):
            continue
        aliases = filter_character_identity_aliases(character.name, character.aliases or [])
        if aliases != list(character.aliases or []):
            character.aliases = aliases
            sanitized_aliases += 1

    visible_characters = [
        character for character in characters if is_cast_visible_character(character)
    ]
    visible_ids = {character.id for character in visible_characters}
    roster = [
        (character.id, character.name, character.aliases or []) for character in visible_characters
    ]

    removed_hidden_relationships = 0
    relationship_rows = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book_id)
            )
        )
        .scalars()
        .all()
    )
    for relationship in relationship_rows:
        if getattr(relationship, "edited_by_author", False):
            continue
        if (
            relationship.character_a_id in visible_ids
            and relationship.character_b_id in visible_ids
        ):
            continue
        await db.delete(relationship)
        removed_hidden_relationships += 1

    def _resolve(raw_name: str, description: str | None) -> list[uuid.UUID]:
        candidate = clean_relationship_text(raw_name)
        if not candidate:
            return []
        if not family_role_reference(candidate)[1]:
            matches = resolve_character_match_ids(candidate, [], roster)
            if matches:
                return matches
        context_text = clean_relationship_text(description)
        resolved = resolve_character_reference_from_roster(
            visible_characters,
            candidate,
            context_text=context_text,
        )
        return [resolved.id] if resolved is not None else []

    candidates = (
        (
            await db.execute(
                select(CharacterRelationshipCandidate).where(
                    CharacterRelationshipCandidate.book_id == book_id,
                    CharacterRelationshipCandidate.status.in_(
                        ("pending", "suppressed", "accepted")
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    reconciled_candidates = 0
    demoted_candidates = 0
    for candidate in candidates:
        was_auto_reconciled = (
            candidate.status == "accepted"
            and "relationship_auto_reconciled" in set(candidate.reason_codes or [])
        )
        if candidate.status == "accepted" and not was_auto_reconciled:
            continue
        evidence = dict(candidate.evidence or {})
        extracted_relationship = (
            evidence.get("relationship") if isinstance(evidence.get("relationship"), dict) else {}
        )
        citation = extracted_relationship.get("label_evidence")
        citation = citation if isinstance(citation, dict) else {}
        source_verified = evidence.get("source_quote_verified") is True
        participants_anchored = relationship_quote_anchors_participants(
            citation.get("quote"), candidate.raw_character_a, candidate.raw_character_b
        )
        if not source_verified or not participants_anchored:
            if was_auto_reconciled:
                candidate.status = "pending"
                candidate.reason_codes = [
                    "relationship_source_quote_unverified"
                    if not source_verified
                    else "relationship_participants_unanchored"
                ]
                evidence["relationship_auto_reconciled"] = False
                candidate.evidence = evidence
                demoted_candidates += 1
            continue
        left_matches = _resolve(candidate.raw_character_a, candidate.description)
        right_matches = _resolve(candidate.raw_character_b, candidate.description)
        if len(left_matches) != 1 or len(right_matches) != 1 or left_matches[0] == right_matches[0]:
            if was_auto_reconciled:
                candidate.matched_character_a_id = None
                candidate.matched_character_b_id = None
                candidate.status = "suppressed"
                candidate.reason_codes = ["relationship_unresolved"]
                evidence["resolution"] = "unresolved_after_reconcile"
                evidence["relationship_auto_reconciled"] = False
                candidate.evidence = evidence
                demoted_candidates += 1
            continue
        relationship, _created = await upsert_relationship_timeline_state(
            db,
            book_id=book_id,
            character_a_id=left_matches[0],
            character_b_id=right_matches[0],
            rel_type=candidate.rel_type or "connection",
            sentiment=candidate.sentiment,
            description=candidate.description,
            from_chapter=int(candidate.chapter_number or 1),
            shared_labels=extracted_relationship.get("shared_labels"),
            character_a_to_b_labels=extracted_relationship.get("character_a_to_b_labels"),
            character_b_to_a_labels=extracted_relationship.get("character_b_to_a_labels"),
            label_evidence=extracted_relationship.get("label_evidence")
            if isinstance(extracted_relationship.get("label_evidence"), dict)
            else evidence,
        )
        candidate.matched_character_a_id = relationship.character_a_id
        candidate.matched_character_b_id = relationship.character_b_id
        candidate.status = "accepted"
        candidate.reason_codes = ["relationship_auto_reconciled"]
        evidence["pair_key"] = [str(relationship.character_a_id), str(relationship.character_b_id)]
        evidence["resolution"] = "resolved:resolved"
        evidence["relationship_auto_reconciled"] = True
        candidate.evidence = evidence
        reconciled_candidates += 1

    timeline_result = await repair_relationship_timelines(db, book_id=book_id)
    return {
        "aliases_sanitized": sanitized_aliases,
        "hidden_relationships_removed": removed_hidden_relationships,
        "relationship_candidates_reconciled": reconciled_candidates,
        "relationship_candidates_demoted": demoted_candidates,
        "timeline_pairs_repaired": int(timeline_result.get("pairs_repaired") or 0),
    }
