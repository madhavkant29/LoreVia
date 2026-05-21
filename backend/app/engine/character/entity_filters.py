from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from collections.abc import Iterable

PERSON_ROLE_WORDS = {
    "mr", "mrs", "ms", "miss", "dr", "doctor", "professor", "captain", "commander",
    "sir", "lady", "lord", "king", "queen", "prince", "princess", "duke", "duchess",
    "baron", "master", "mistress", "mentor", "servant", "rider", "saber", "archer",
    "lancer", "caster", "berserker", "assassin", "ruler", "shielder", "avenger",
    "foreigner", "alterego", "alter", "teacher", "father", "mother", "brother",
    "sister", "uncle", "aunt",
}

NON_PERSON_HEADWORDS = {
    "academy", "association", "catholicism", "church", "city", "circles", "convention",
    "country", "crest", "department", "designations", "enforcers", "energy", "empire",
    "eyes", "fundamentals", "gospel", "kingdom", "magecraft", "magic", "mystic",
    "nation", "office", "order", "republic", "ritual", "school", "sequence", "society",
    "spirit", "system", "temple", "theory", "tower", "towers", "university", "wonders",
}

LEADING_DESCRIPTOR_WORDS = {
    "ancient", "arcane", "central", "eastern", "first", "fourth", "great", "holy",
    "last", "magic", "mystic", "northern", "old", "roman", "royal", "sacred",
    "second", "seventh", "silver", "southern", "starless", "third", "western", "young",
}

ABSTRACT_SUFFIXES = ("ism", "tion", "ness", "ity", "ology", "ship", "ment", "ance", "ence")
NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
}

COMMON_NON_NAME_WORDS = {
    # High-frequency English words that often appear capitalized at sentence start
    # and should almost never be treated as character entities.
    "a", "an", "and", "as", "at", "back", "because", "before", "but", "by",
    "come", "for", "from", "had", "has", "have", "he", "her", "here", "him", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "like", "me", "more",
    "my", "near", "no", "not", "now", "of", "off", "on", "once", "one",
    "or", "our", "out", "over", "she", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "to",
    "too", "up", "us", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "well", "would", "with", "without", "you", "your",
}

NON_NAME_PATTERNS = (
    re.compile(r"^(on|in|at|by|for|of|to|from)\s+\w+$", re.IGNORECASE),
    re.compile(r"^(the|a|an)\s+\w+$", re.IGNORECASE),
    re.compile(r"^(chapter|part|section)\s+\d+$", re.IGNORECASE),
    re.compile(r"^(he|she|it|they)\s+\w+$", re.IGNORECASE),
)


def entity_words(name: str | None) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", name or "")


def normalize_entity_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", name.lower())).strip()


def matches_non_name_pattern(name: str | None) -> bool:
    normalized = normalize_entity_name(name)
    if not normalized:
        return False
    return any(pattern.match(normalized) for pattern in NON_NAME_PATTERNS)


def person_name_shape_score(name: str | None) -> int:
    words = entity_words(name)
    if not words:
        return -10

    lowered = [word.casefold() for word in words]
    score = 0

    # Single-word common words (e.g., "From", "Then") are a primary false-positive source.
    if len(words) == 1 and lowered[0] in COMMON_NON_NAME_WORDS:
        score -= 6

    if len(words) == 1:
        score += 1 if len(words[0]) >= 4 else 0
    else:
        score += 2

    if any("-" in word or "'" in word for word in words):
        score += 1
    if any(word in PERSON_ROLE_WORDS for word in lowered):
        score += 2
    if lowered[0] in {"mr", "mrs", "ms", "miss", "dr", "sir", "lady", "lord"}:
        score += 1

    if len(words) >= 2 and lowered[-1].endswith("s") and lowered[-1] not in PERSON_ROLE_WORDS:
        score -= 3
    if lowered[-1] in NON_PERSON_HEADWORDS:
        score -= 4
    if any(word in NON_PERSON_HEADWORDS for word in lowered[1:-1]):
        score -= 3
    if any(word.endswith(ABSTRACT_SUFFIXES) for word in lowered):
        score -= 3
    if lowered[0] in LEADING_DESCRIPTOR_WORDS and lowered[-1] not in PERSON_ROLE_WORDS:
        score -= 2
    if lowered[0] in NUMBER_WORDS and lowered[-1] not in PERSON_ROLE_WORDS:
        score -= 2

    return score


def looks_like_person_entity_name(name: str | None) -> bool:
    words = entity_words(name)
    if not words:
        return False
    cleaned = " ".join(words)
    if cleaned.endswith("'s"):
        return False
    if len(words) == 1 and len(words[0]) <= 3:
        return False
    return person_name_shape_score(cleaned) >= 1


def profile_evidence_score(
    *,
    role: str | None = None,
    aliases: Iterable[str] | None = None,
    personality_tags: Iterable[str] | None = None,
    motivations: Iterable[str] | None = None,
    fears: Iterable[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
) -> int:
    score = 0
    if role:
        score += 1
    if aliases:
        score += 1
    if personality_tags:
        score += 1
    if motivations or fears:
        score += 1
    if archetype:
        score += 1
    if _has_meaningful_trait_state(trait_state):
        score += 1
    if relationship_count > 0:
        score += 1
    return score


GENERIC_PROFILE_PHRASES = {
    "appearance not yet described",
    "background character",
    "is a character",
    "mysterious figure",
    "normal character",
    "plain character",
    "protagonist",
    "supporting character",
    "this character is a character",
    "tragic figure",
    "unknown character",
}


def _has_meaningful_text(value: str | None) -> bool:
    cleaned = re.sub(r"\s+", " ", (value or "").strip()).casefold()
    return bool(cleaned) and cleaned not in GENERIC_PROFILE_PHRASES


def _has_meaningful_trait_state(trait_state: dict | None) -> bool:
    if not isinstance(trait_state, dict):
        return False
    for value in trait_state.values():
        if not isinstance(value, dict):
            continue
        raw_value = str(value.get("value") or "").strip()
        if raw_value and raw_value.casefold() not in GENERIC_PROFILE_PHRASES:
            return True
    return False


def _evidence_support_score(evidence: dict | None) -> int:
    if not isinstance(evidence, dict):
        return 0

    score = 0
    mention_count = int(evidence.get("mention_count") or 0)
    strong_mention_count = int(evidence.get("strong_mention_count") or 0)
    if mention_count >= 2:
        score += 1
    if strong_mention_count >= 1:
        score += 2
    if strong_mention_count >= 2:
        score += 1
    if evidence.get("has_dialogue_or_action"):
        score += 1
    if evidence.get("has_physical_description"):
        score += 1
    if evidence.get("appears_multiple_times"):
        score += 1
    return score


def _single_token_name(name: str | None) -> str | None:
    words = entity_words(name)
    if len(words) != 1:
        return None
    return words[0].casefold()


def _single_token_has_grounded_support(evidence: dict | None) -> bool:
    if not isinstance(evidence, dict):
        return False
    mention_count = int(evidence.get("mention_count") or 0)
    strong_mention_count = int(evidence.get("strong_mention_count") or 0)
    has_dialogue_or_action = bool(evidence.get("has_dialogue_or_action"))
    has_physical_description = bool(evidence.get("has_physical_description"))
    appears_multiple_times = bool(evidence.get("appears_multiple_times"))
    return bool(
        strong_mention_count >= 2
        or (
            strong_mention_count >= 1
            and has_dialogue_or_action
            and (appears_multiple_times or mention_count >= 3 or has_physical_description)
        )
    )


@dataclass(frozen=True)
class CharacterPersistenceDecision:
    allowed: bool
    score: int
    reasons: tuple[str, ...]


def character_persistence_decision(
    name: str | None,
    *,
    confidence: float | None = None,
    role: str | None = None,
    aliases: Iterable[str] | None = None,
    personality_tags: Iterable[str] | None = None,
    motivations: Iterable[str] | None = None,
    fears: Iterable[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
    arc_summary: str | None = None,
    evidence: dict | None = None,
    entity_type: str | None = None,
    stopwords: frozenset[str] = frozenset(COMMON_NON_NAME_WORDS),
    exact_blocklist: frozenset[str] = frozenset(),
    concept_suffixes: tuple[str, ...] = (),
    non_name_patterns: tuple[re.Pattern[str], ...] = NON_NAME_PATTERNS,
    use_ner: bool = True,
) -> CharacterPersistenceDecision:
    score = character_visibility_score(
        name,
        role=role,
        aliases=aliases,
        arc_summary=arc_summary,
        personality_tags=personality_tags,
        motivations=motivations,
        fears=fears,
        archetype=archetype,
        trait_state=trait_state,
        relationship_count=relationship_count,
        stopwords=stopwords,
        exact_blocklist=exact_blocklist,
        concept_suffixes=concept_suffixes,
        non_name_patterns=non_name_patterns,
        use_ner=use_ner,
    )

    reasons: list[str] = []
    normalized_entity_type = re.sub(r"\s+", " ", (entity_type or "person").strip()).casefold()
    if normalized_entity_type not in {"person", "alias", "unknown"}:
        reasons.append("entity_type_not_person")

    support_score = _evidence_support_score(evidence)
    profile_score = profile_evidence_score(
        role=role,
        aliases=aliases,
        personality_tags=personality_tags,
        motivations=motivations,
        fears=fears,
        archetype=archetype,
        trait_state=trait_state,
        relationship_count=relationship_count,
    )

    if score < VISIBILITY_THRESHOLD and support_score < 2 and profile_score == 0:
        reasons.append("visibility_score_below_threshold")
    if support_score == 0 and profile_score == 0:
        reasons.append("insufficient_passage_support")

    if _single_token_name(name):
        if not _single_token_has_grounded_support(evidence):
            reasons.append("single_token_needs_stronger_support")
        if support_score < 3 and profile_score == 0:
            reasons.append("single_token_lacks_profile_evidence")

    if any(reason == "visibility_score_below_threshold" for reason in reasons):
        return CharacterPersistenceDecision(allowed=False, score=score, reasons=tuple(reasons))

    if arc_summary and not _has_meaningful_text(arc_summary):
        if profile_score == 0 and support_score < 2:
            reasons.append("generic_profile_summary")

    if support_score < 2 and profile_score == 0:
        reasons.append("no_profile_or_passage_signal")

    if _single_token_name(name) and not _single_token_has_grounded_support(evidence):
        reasons.append("single_token_requires_more_evidence")

    allowed = not reasons
    return CharacterPersistenceDecision(allowed=allowed, score=score, reasons=tuple(reasons))


def can_persist_character(
    name: str | None,
    **kwargs,
) -> bool:
    return character_persistence_decision(name, **kwargs).allowed


def is_displayable_character_entity(
    name: str | None,
    *,
    role: str | None = None,
    aliases: Iterable[str] | None = None,
    personality_tags: Iterable[str] | None = None,
    motivations: Iterable[str] | None = None,
    fears: Iterable[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
) -> bool:
    score = character_visibility_score(
        name,
        role=role,
        aliases=aliases,
        arc_summary=None,
        personality_tags=personality_tags,
        motivations=motivations,
        fears=fears,
        archetype=archetype,
        trait_state=trait_state,
        relationship_count=relationship_count,
        stopwords=frozenset(COMMON_NON_NAME_WORDS),
    )
    return score >= VISIBILITY_THRESHOLD


# ─── spaCy NER layer (optional, lazy-loaded) ──────────────────────────────────
# Requires:  python -m spacy download en_core_web_sm
#
# If the model is absent the NER score degrades to 0, and shape + profile
# signals still carry the decision — the system never hard-fails.

NER_LABEL_SCORES: dict[str, int] = {
    "PERSON":        3,   # named person — strong positive
    "ORG":          -2,   # organisation
    "GPE":          -3,   # geo-political entity (city / country)
    "LOC":          -3,   # location
    "FAC":          -3,   # facility
    "PRODUCT":      -1,   # product name
    "EVENT":        -1,   # named event
    "WORK_OF_ART":  -1,   # book / movie title
    "LAW":          -2,
    "LANGUAGE":     -2,
    "NORP":         -2,   # nationality / religion / political group
}

_nlp = None
_nlp_loaded = False


def _get_nlp():
    """Lazily load en_core_web_sm with only the NER pipeline enabled.
    Returns None if the model is not installed."""
    global _nlp, _nlp_loaded
    if _nlp_loaded:
        return _nlp
    try:
        import spacy
        _nlp = spacy.load(
            "en_core_web_sm",
            exclude=["tok2vec", "tagger", "parser", "attribute_ruler", "lemmatizer"],
        )
    except Exception:
        _nlp = None
    _nlp_loaded = True
    return _nlp


@functools.lru_cache(maxsize=2048)
def ner_entity_score(name: str) -> int:
    """Run NER on a name snippet and return a score delta.

    Results are LRU-cached per unique name string (2 048 slots — enough for
    a full novel cast plus aliases).  Returns 0 if spaCy is unavailable or
    the name is too short to be meaningful.

    Label mapping (NER_LABEL_SCORES):
      PERSON      → +3   (clearly a named person)
      ORG/GPE/LOC → -2/-3 (place or institution, not a story character)
      unknown     → 0
    """
    if not name or len(name.strip()) < 3:
        return 0
    nlp = _get_nlp()
    if nlp is None:
        return 0
    doc = nlp(name.strip())
    if not doc.ents:
        return 0
    # Pick the longest entity span as the primary classification.
    best = max(doc.ents, key=lambda e: len(e.text), default=None)
    return NER_LABEL_SCORES.get(best.label_, 0) if best else 0


# ─── Composite visibility scoring constants ───────────────────────────────────

STOPWORD_PENALTY = -3       # name is a known common / noise word  (soft — NER can override)
KNOWN_CONCEPT_PENALTY = -4  # name is in the exact-match concept blocklist
SUFFIX_CONCEPT_PENALTY = -2 # name ends with a known concept suffix (e.g. " Association")
NON_NAME_PATTERN_PENALTY = -4
ARC_EVIDENCE_BONUS = 1      # character has an arc_summary on record
SINGLE_PROPER_NAME_BONUS = 1  # title-cased single word ≥4 chars, not a common word
                               # rescues short CJK-origin names (Ling, Shen, Yuki) that
                               # en_core_web_sm cannot tag as PERSON in isolation
VISIBILITY_THRESHOLD = 2    # composite score >= this → treat as a visible character


# ─── Composite character visibility scorer ────────────────────────────────────

def character_visibility_score(
    name: str | None,
    *,
    role: str | None = None,
    aliases: Iterable[str] | None = None,
    arc_summary: str | None = None,
    personality_tags: Iterable[str] | None = None,
    motivations: Iterable[str] | None = None,
    fears: Iterable[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
    stopwords: frozenset[str] = frozenset(COMMON_NON_NAME_WORDS),
    exact_blocklist: frozenset[str] = frozenset(),
    concept_suffixes: tuple[str, ...] = (),
    non_name_patterns: tuple[re.Pattern[str], ...] = NON_NAME_PATTERNS,
    use_ner: bool = True,
) -> int:
    """Composite score for whether an entity should be treated as a visible
    story character.

    Score components
    ────────────────
    + person_name_shape_score     multi-word names, title prefixes, hyphens …
    + ner_entity_score            PERSON → +3 | ORG/GPE/LOC → -2/-3 (spaCy, cached)
    + profile_evidence_score      role, aliases, personality_tags, trait_state …
    + ARC_EVIDENCE_BONUS          has arc_summary
    + SINGLE_PROPER_NAME_BONUS    single title-cased word ≥4 chars, not a common word
                                  (rescues short CJK-origin names spaCy can't classify)
    - STOPWORD_PENALTY            name is a known common word  ← SOFT, NER can override
    - KNOWN_CONCEPT_PENALTY       name is in the exact blocklist
    - SUFFIX_CONCEPT_PENALTY      name ends with a concept suffix

    Decision gate (caller-side):
        visible = character_visibility_score(...) >= VISIBILITY_THRESHOLD  # 2
    """
    if not name:
        return -99

    normalized = re.sub(r"\s+", " ", name.strip()).casefold()
    title_name = re.sub(r"\s+", " ", name.strip())

    score = 0

    # 1. Shape heuristics — multi-word bonus, title prefix, hyphen bonus, etc.
    score += person_name_shape_score(name)

    # 2. NER signal — lazily loaded, LRU-cached; degrades to 0 if model absent
    if use_ner:
        score += ner_entity_score(title_name)

    # 3. Database profile evidence — role, aliases, tags, trait_state, etc.
    score += profile_evidence_score(
        role=role,
        aliases=aliases,
        personality_tags=personality_tags,
        motivations=motivations,
        fears=fears,
        archetype=archetype,
        trait_state=trait_state,
        relationship_count=relationship_count,
    )

    # 4. Arc summary bonus
    if _has_meaningful_text(arc_summary):
        score += ARC_EVIDENCE_BONUS

    # 5. Single proper-name candidate bonus.
    #    Targets short title-cased single-token names from CJK and non-Western
    #    fiction backgrounds (e.g. "Ling", "Shen", "Yuki", "Emre") that
    #    en_core_web_sm cannot confidently tag as PERSON in isolation because
    #    they lack the surrounding sentence context the model was trained on.
    #    Guard: word must be ≥ 4 chars AND not in COMMON_NON_NAME_WORDS so
    #    common sentence-start capitalisations ("Back", "More", "Once") are
    #    unaffected — the shape score already penalises those via the -6 deduct
    #    for COMMON_NON_NAME_WORDS, but this bonus would otherwise partially
    #    counteract that, so the guard is essential.
    words_raw = entity_words(title_name)
    if (
        len(words_raw) == 1
        and len(words_raw[0]) >= 4
        and words_raw[0][0].isupper()
        and words_raw[0].casefold() not in COMMON_NON_NAME_WORDS
    ):
        score += SINGLE_PROPER_NAME_BONUS

    # 6. Soft stopword penalty — likely noise, but a strong NER or profile
    #    signal can overcome it.  Stopwords are NOT a hard gate here.
    if normalized in stopwords:
        score += STOPWORD_PENALTY

    if matches_non_name_pattern(title_name) or any(pattern.match(normalized) for pattern in non_name_patterns):
        score += NON_NAME_PATTERN_PENALTY

    # 7. Exact concept blocklist — known non-person proper nouns
    if title_name in exact_blocklist:
        score += KNOWN_CONCEPT_PENALTY

    # 8. Concept-suffix penalty — "Magic Circles", "Mage's Association", etc.
    if any(title_name.endswith(sfx) for sfx in concept_suffixes):
        score += SUFFIX_CONCEPT_PENALTY

    return score


# ─── Gag / meme character detection ──────────────────────────────────────────
# Identifies comic-relief, absurdist, and one-off meme characters based on
# soft scoring across personality signals, archetype, arc language, and
# statistical footprint.  Never a hard gate — returns a numeric score so
# callers can apply their own threshold.

_GAG_PERSONALITY_MARKERS: frozenset[str] = frozenset({
    "comedic", "absurdist", "clumsy", "bumbling", "eccentric", "quirky",
    "slapstick", "goofy", "silly", "ridiculous", "oblivious", "buffoon",
    "hapless", "dim-witted", "naive", "over-the-top", "flamboyant",
    "chaotic", "erratic", "wacky", "manic", "comic-relief", "parody",
    "self-aware", "fourth-wall", "meta", "satirical", "ironic",
})

_GAG_ARCHETYPE_SIGNALS: frozenset[str] = frozenset({
    "fool", "trickster", "jester", "court jester", "clown", "comic relief",
    "sidekick", "bumbling sidekick", "village idiot", "eccentric mentor",
    "absurd villain", "parody", "meme", "comic villain", "one-off",
    "throwaway", "cameo",
})

_GAG_ARC_PHRASES: tuple[str, ...] = (
    "comic relief", "played for laughs", "running gag", "running joke",
    "punchline", "punchline character", "absurd", "deliberately ridiculous",
    "comedic foil", "meme", "satirical", "satirize", "parody of",
    "breaks the fourth wall", "self-aware", "one-off joke",
    "appears once for a laugh", "forgotten immediately", "throwaway",
)


def gag_character_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
    mention_count: int = 0,
    role: str | None = None,
    growth_events: list[dict] | None = None,
) -> int:
    """Composite score for whether a character functions as a gag / meme figure.

    Score components
    ────────────────
    + personality_tag overlap with _GAG_PERSONALITY_MARKERS (+2 per match, cap 4)
    + archetype overlap with _GAG_ARCHETYPE_SIGNALS (+3)
    + arc_summary contains known gag phrases (+2 per match, cap 4)
    + very low mention count with a non-major role (+1)  — throwaway figures
    - arc_summary is long and has growth_events  (-2)    — genuine arc overrides
    - role is "mc" or "sc" and mention_count > 10  (-3) — significant characters

    Callers should treat score >= 3 as a probable gag character.
    """
    score = 0

    # 1. Personality tags
    tag_hits = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _GAG_PERSONALITY_MARKERS:
            score += 2
            tag_hits += 1
            if tag_hits >= 2:
                break  # cap: +4

    # 2. Archetype signal
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _GAG_ARCHETYPE_SIGNALS):
        score += 3

    # 3. Arc summary phrase matching
    arc_lower = (arc_summary or "").lower()
    phrase_hits = 0
    for phrase in _GAG_ARC_PHRASES:
        if phrase in arc_lower:
            score += 2
            phrase_hits += 1
            if phrase_hits >= 2:
                break  # cap: +4

    # 4. Low-mention throwaway bonus
    if mention_count > 0 and mention_count <= 3 and role not in ("mc", "sc"):
        score += 1

    # 5. Genuine-arc override penalties
    has_growth = isinstance(growth_events, list) and len(growth_events) >= 2
    if has_growth and len(arc_lower) > 200:
        score -= 2  # a real arc with multiple growth beats is unlikely a gag

    if role in ("mc", "sc") and mention_count > 10:
        score -= 3  # main/supporting cast with many mentions are story-critical

    return score


def is_gag_character(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
    mention_count: int = 0,
    role: str | None = None,
    growth_events: list[dict] | None = None,
    threshold: int = 3,
) -> bool:
    """Return True when the character scores at or above the gag threshold."""
    return gag_character_score(
        personality_tags=personality_tags,
        archetype=archetype,
        arc_summary=arc_summary,
        mention_count=mention_count,
        role=role,
        growth_events=growth_events,
    ) >= threshold


# ─── Complex character detection ─────────────────────────────────────────────
# Identifies characters with depth, growth, and narrative significance.

def complex_character_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
    mention_count: int = 0,
    role: str | None = None,
    growth_events: list[dict] | None = None,
    motivations: list[str] | None = None,
    fears: list[str] | None = None,
) -> int:
    """Composite score for whether a character is complex (has depth and growth).

    Score components
    ────────────────
    + personality_tags count (+1 per tag, cap 3)
    + motivations present (+2)
    + fears present (+2)
    + growth_events count (+1 per event, cap 3)
    + arc_summary length and depth (+2 if >100 chars, +1 if >50)
    + role is "mc" or "sc" (+2)
    + mention_count > 10 (+1)
    - arc_summary is very short or missing (-2)
    - no growth_events and high mention_count (-2)
    """
    score = 0

    # 1. Personality tags diversity
    if personality_tags:
        score += min(len(personality_tags), 3)

    # 2. Internal conflict indicators
    if motivations:
        score += 2
    if fears:
        score += 2

    # 3. Growth events
    if growth_events:
        score += min(len(growth_events), 3)

    # 4. Arc summary depth
    arc_len = len(arc_summary or "")
    if arc_len > 100:
        score += 2
    elif arc_len > 50:
        score += 1
    elif arc_len < 20:
        score -= 2

    # 5. Role significance
    if role in ("mc", "sc"):
        score += 2

    # 6. Narrative presence
    if mention_count > 10:
        score += 1

    # 7. Override penalties
    if not growth_events and mention_count > 20:
        score -= 2  # high mentions but no growth suggests flat character

    return score


# ─── Subtype scoring functions ───────────────────────────────────────────────
# Each subtype has markers for personality, archetype, and arc language.

# Emotional subtypes
_STOIC_MARKERS: frozenset[str] = frozenset({
    "stoic", "unemotional", "reserved", "calm", "composed", "detached",
    "unflappable", "steady", "stoic", "emotionless", "impassive",
})
_STOIC_ARCHETYPES: frozenset[str] = frozenset({
    "stoic hero", "silent protagonist", "warrior monk", "stoic mentor",
    "unflappable leader", "stone-faced",
})
_STOIC_PHRASES: tuple[str, ...] = (
    "maintains composure", "shows no emotion", "keeps feelings hidden",
    "stoic demeanor", "unflappable", "emotionally reserved", "calm under pressure",
)

def stoic_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _STOIC_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _STOIC_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _STOIC_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


_BROKEN_MARKERS: frozenset[str] = frozenset({
    "broken", "traumatized", "damaged", "scarred", "wounded", "shattered",
    "haunted", "tormented", "suffering", "pained", "hurt", "devastated",
})
_BROKEN_ARCHETYPES: frozenset[str] = frozenset({
    "broken hero", "tragic figure", "wounded healer", "trauma survivor",
    "damaged protagonist", "haunted past",
})
_BROKEN_PHRASES: tuple[str, ...] = (
    "broken by", "trauma from", "haunted by past", "emotional scars",
    "deeply wounded", "psychological damage", "never recovered from",
)

def broken_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
    growth_events: list[dict] | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _BROKEN_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _BROKEN_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _BROKEN_PHRASES:
        if phrase in arc_lower:
            score += 2
    # Check growth events for trauma-related impact
    if growth_events:
        for event in growth_events:
            impact = (event.get("impact") or "").lower()
            if any(word in impact for word in ["trauma", "wound", "scar", "broken", "hurt"]):
                score += 1
    return min(score, 10)


_HIDING_FEELINGS_MARKERS: frozenset[str] = frozenset({
    "secretive", "guarded", "closed off", "withdrawn", "private", "mysterious",
    "evasive", "defensive", "hidden", "suppressed", "bottled up",
})
_HIDING_FEELINGS_ARCHETYPES: frozenset[str] = frozenset({
    "mysterious stranger", "secretive protagonist", "hidden past",
    "enigmatic figure", "cloaked figure",
})
_HIDING_FEELINGS_PHRASES: tuple[str, ...] = (
    "hides feelings", "bottles up emotions", "keeps to themselves",
    "guarded about", "secretive nature", "won't open up", "emotional walls",
)

def hiding_feelings_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _HIDING_FEELINGS_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _HIDING_FEELINGS_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _HIDING_FEELINGS_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


# Moral subtypes
_PSYCHOPATH_MARKERS: frozenset[str] = frozenset({
    "psychopathic", "sociopathic", "remorseless", "ruthless", "cold-blooded",
    "sadistic", "manipulative", "lacks empathy", "cruel", "merciless",
})
_PSYCHOPATH_ARCHETYPES: frozenset[str] = frozenset({
    "psychopath", "sociopath", "serial killer", "cold-blooded killer",
    "ruthless villain", "sadistic antagonist",
})
_PSYCHOPATH_PHRASES: tuple[str, ...] = (
    "no empathy", "lacks remorse", "psychopathic tendencies", "cold-blooded",
    "sadistic pleasure", "enjoys suffering", "ruthless killer",
)

def psychopath_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _PSYCHOPATH_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _PSYCHOPATH_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _PSYCHOPATH_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


_SERIOUS_MARKERS: frozenset[str] = frozenset({
    "serious", "grim", "stern", "solemn", "dour", "severe", "intense",
    "no-nonsense", "businesslike", "formal", "strict", "disciplined",
})
_SERIOUS_ARCHETYPES: frozenset[str] = frozenset({
    "serious protagonist", "grim warrior", "stern mentor", "no-nonsense leader",
    "disciplined soldier", "formal authority",
})
_SERIOUS_PHRASES: tuple[str, ...] = (
    "takes things seriously", "grim demeanor", "stern expression",
    "no-nonsense approach", "serious manner", "deadly serious",
)

def serious_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _SERIOUS_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _SERIOUS_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _SERIOUS_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


# Personality subtypes
_CHARISMATIC_MARKERS: frozenset[str] = frozenset({
    "charismatic", "charming", "magnetic", "persuasive", "influential",
    "captivating", "enchanting", "compelling", "inspiring", "leader-like",
})
_CHARISMATIC_ARCHETYPES: frozenset[str] = frozenset({
    "charismatic leader", "natural leader", "inspiring figure", "cult leader",
    "beloved hero", "popular figure",
})
_CHARISMATIC_PHRASES: tuple[str, ...] = (
    "natural charisma", "magnetic personality", "inspires others",
    "charms people", "persuasive speaker", "draws people in",
)

def charismatic_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _CHARISMATIC_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _CHARISMATIC_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _CHARISMATIC_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


_CYNICAL_MARKERS: frozenset[str] = frozenset({
    "cynical", "skeptical", "distrustful", "pessimistic", "world-weary",
    "jaded", "disillusioned", "cynical", "sarcastic", "ironic",
})
_CYNICAL_ARCHETYPES: frozenset[str] = frozenset({
    "cynical protagonist", "jaded veteran", "disillusioned hero",
    "world-weary detective", "skeptical investigator",
})
_CYNICAL_PHRASES: tuple[str, ...] = (
    "cynical outlook", "lost faith", "disillusioned with", "skeptical of",
    "world-weary", "jaded by experience", "sees the worst in people",
)

def cynical_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _CYNICAL_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _CYNICAL_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _CYNICAL_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


# Social subtypes
_LONER_MARKERS: frozenset[str] = frozenset({
    "loner", "solitary", "isolated", "reclusive", "anti-social", "withdrawn",
    "introverted", "alone", "independent", "self-reliant",
})
_LONER_ARCHETYPES: frozenset[str] = frozenset({
    "loner protagonist", "solitary figure", "reclusive genius",
    "isolated wanderer", "lone wolf",
})
_LONER_PHRASES: tuple[str, ...] = (
    "prefers solitude", "works alone", "isolated from", "loner by choice",
    "keeps to themselves", "no close connections", "solitary life",
)

def loner_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _LONER_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _LONER_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _LONER_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


_MENTOR_MARKERS: frozenset[str] = frozenset({
    "wise", "guiding", "teaching", "mentor", "teacher", "advisor",
    "experienced", "knowledgeable", "patient", "nurturing",
})
_MENTOR_ARCHETYPES: frozenset[str] = frozenset({
    "mentor", "wise teacher", "old master", "guiding figure",
    "experienced advisor", "patient teacher",
})
_MENTOR_PHRASES: tuple[str, ...] = (
    "mentors", "teaches", "guides", "imparts wisdom", "shares experience",
    "acts as mentor", "wise guidance", "teacher figure",
)

def mentor_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _MENTOR_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _MENTOR_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _MENTOR_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


# Mental subtypes
_INTELLIGENT_MARKERS: frozenset[str] = frozenset({
    "intelligent", "smart", "brilliant", "genius", "clever", "sharp",
    "analytical", "strategic", "intellectual", "quick-witted",
})
_INTELLIGENT_ARCHETYPES: frozenset[str] = frozenset({
    "genius", "intellectual", "strategist", "mastermind", "brilliant scientist",
    "clever tactician", "quick-witted hero",
})
_INTELLIGENT_PHRASES: tuple[str, ...] = (
    "highly intelligent", "brilliant mind", "strategic thinker", "genius-level",
    "quick-witted", "analytical mind", "intellectual prowess",
)

def intelligent_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _INTELLIGENT_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _INTELLIGENT_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _INTELLIGENT_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


_NAIVE_MARKERS: frozenset[str] = frozenset({
    "naive", "innocent", "inexperienced", "idealistic", "optimistic",
    "trusting", "gullible", "unworldly", "pure", "unsuspecting",
})
_NAIVE_ARCHETYPES: frozenset[str] = frozenset({
    "innocent protagonist", "naive hero", "idealistic youth",
    "trusting soul", "pure-hearted figure",
})
_NAIVE_PHRASES: tuple[str, ...] = (
    "naive about", "innocent to", "idealistic view", "trusting nature",
    "believes the best", "unaware of", "pure heart",
)

def naive_score(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
) -> int:
    score = 0
    for tag in (personality_tags or []):
        if tag.strip().lower() in _NAIVE_MARKERS:
            score += 2
    arch_lower = (archetype or "").strip().lower()
    if any(signal in arch_lower for signal in _NAIVE_ARCHETYPES):
        score += 3
    arc_lower = (arc_summary or "").lower()
    for phrase in _NAIVE_PHRASES:
        if phrase in arc_lower:
            score += 2
    return min(score, 10)


# ─── Composite subtype scoring ───────────────────────────────────────────────

def compute_all_subtype_scores(
    *,
    personality_tags: list[str] | None = None,
    archetype: str | None = None,
    arc_summary: str | None = None,
    growth_events: list[dict] | None = None,
) -> dict[str, int]:
    """Compute scores for all subtypes and return as a dictionary.

    Returns a dict like {"stoic": 7, "broken": 3, "charismatic": 5, ...}
    Only includes subtypes with score >= 3 to reduce noise.
    """
    scores = {
        "stoic": stoic_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "broken": broken_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary, growth_events=growth_events),
        "hiding_feelings": hiding_feelings_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "psychopath": psychopath_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "serious": serious_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "charismatic": charismatic_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "cynical": cynical_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "loner": loner_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "mentor": mentor_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "intelligent": intelligent_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
        "naive": naive_score(personality_tags=personality_tags, archetype=archetype, arc_summary=arc_summary),
    }
    # Filter to only scores >= 3 to reduce noise
    return {k: v for k, v in scores.items() if v >= 3}
