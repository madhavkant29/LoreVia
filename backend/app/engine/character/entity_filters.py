from __future__ import annotations

import functools
import re
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
    "for", "from", "had", "has", "have", "he", "her", "here", "him", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "like", "me", "more",
    "my", "near", "no", "not", "now", "of", "off", "on", "once", "one",
    "or", "our", "out", "over", "she", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "to",
    "too", "up", "us", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "with", "without", "you", "your",
}


def entity_words(name: str | None) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", name or "")


def normalize_entity_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", name.lower())).strip()


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
    if trait_state:
        score += 1
    if relationship_count > 0:
        score += 1
    return score


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
    words = entity_words(name)
    if not words:
        return False

    shape_score = person_name_shape_score(name)
    evidence_score = profile_evidence_score(
        role=role,
        aliases=aliases,
        personality_tags=personality_tags,
        motivations=motivations,
        fears=fears,
        archetype=archetype,
        trait_state=trait_state,
        relationship_count=relationship_count,
    )

    if len(words) == 1:
        # Single-token names are the hardest to disambiguate from sentence-start capitalization.
        # Require stronger supporting evidence (traits/tags/aliases/role/etc) to avoid noise like "From", "Now", "Then".
        return shape_score >= 1 and evidence_score >= 2

    return shape_score >= 2 and (evidence_score >= 1 or shape_score >= 3)


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
    aliases: list[str] | None = None,
    arc_summary: str | None = None,
    personality_tags: list[str] | None = None,
    motivations: list[str] | None = None,
    fears: list[str] | None = None,
    archetype: str | None = None,
    trait_state: dict | None = None,
    relationship_count: int = 0,
    stopwords: frozenset[str] = frozenset(),
    exact_blocklist: frozenset[str] = frozenset(),
    concept_suffixes: tuple[str, ...] = (),
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
    if arc_summary:
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
