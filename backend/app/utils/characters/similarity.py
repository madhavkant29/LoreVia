"""Focused character similarity workflows."""

from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher

from app.utils.characters.identity import (
    has_conflicting_title_identity,
    has_shared_surname,
    normalize_character_name,
)

_TITLE_IDENTITY_GROUPS = {
    "mr": "male",
    "master": "male",
    "sir": "male",
    "mrs": "female",
    "ms": "female",
    "miss": "female",
    "mistress": "female",
}


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current = [i]
        for j, char_right in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (char_left != char_right)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _sequence_ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def name_similarity(name1: str | None, name2: str | None) -> float:
    left = normalize_character_name(name1)
    right = normalize_character_name(name2)
    if not left or not right:
        return 0.0
    if left == right:
        if has_conflicting_title_identity(name1, name2):
            return 0.35
        return 1.0

    jw = _sequence_ratio(left, right)
    token_sort = _sequence_ratio(" ".join(sorted(left.split())), " ".join(sorted(right.split())))
    token_set = _sequence_ratio(
        " ".join(sorted(set(left.split()))), " ".join(sorted(set(right.split())))
    )
    score = max(jw, token_sort, token_set)

    if has_conflicting_title_identity(name1, name2):
        score = min(score, 0.35)

    if has_shared_surname(name1, name2) and score >= 0.70:
        score = min(1.0, score + 0.15)

    left_tokens = left.split()
    right_tokens = right.split()
    if len(left_tokens) <= 2 and len(right_tokens) <= 2 and _levenshtein_distance(left, right) <= 2:
        score = max(score, 0.9)

    if (
        len(left_tokens) >= 2
        and len(right_tokens) >= 2
        and (left.startswith(right) or right.startswith(left))
    ):
        score = max(score, 0.88)

    return min(score, 1.0)


def description_similarity(desc1: str | None, desc2: str | None) -> float:
    left = " ".join((desc1 or "").split()).strip()
    right = " ".join((desc2 or "").split()).strip()
    if not left or not right:
        return 0.0
    if left.casefold() == right.casefold():
        return 1.0
    try:
        left_tokens = _similarity_tokens(left)
        right_tokens = _similarity_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0

        doc_freq: dict[str, int] = {}
        for token in set(left_tokens) | set(right_tokens):
            doc_freq[token] = int(token in left_tokens) + int(token in right_tokens)

        def _vector(tokens: list[str]) -> dict[str, float]:
            counts = Counter(tokens)
            total = len(tokens)
            vector: dict[str, float] = {}
            for token, count in counts.items():
                idf = math.log((2 + 1) / (doc_freq[token] + 1)) + 1
                vector[token] = (count / total) * idf
            return vector

        left_vec = _vector(left_tokens)
        right_vec = _vector(right_tokens)
        return _cosine_from_vectors(left_vec, right_vec)
    except (ArithmeticError, TypeError, ValueError):
        return 0.0


def _similarity_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[A-Za-z0-9]+", text.casefold()) if len(token) > 2]


def _cosine_from_vectors(left_vec: dict[str, float], right_vec: dict[str, float]) -> float:
    shared = set(left_vec) & set(right_vec)
    if not shared:
        return 0.0
    dot = sum(left_vec[token] * right_vec[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_vec.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vec.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
