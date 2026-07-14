import re

import pytest

from app.utils import language_utils
from app.utils.language_utils import (
    STOPWORDS,
    TRIGRAM_PROFILES,
    _score_headings,
    _score_stopwords,
    _score_trigrams,
    _tokenize,
    _trigrams,
    detect_language,
)

# ── Tokenizer ──────────────────────────────────────────────────────────────


def test_tokenize_english():
    tokens = _tokenize("Hello world, this is a test!")
    assert "hello" in tokens
    assert "world" in tokens
    assert "this" in tokens
    assert "a" in tokens
    assert "test" in tokens


def test_tokenize_french_accents():
    tokens = _tokenize("C'était une nuit sombre et orageuse.")
    assert "tait" in tokens or "c" in tokens or "était" in tokens


def test_tokenize_empty():
    assert _tokenize("") == []
    assert _tokenize("   ") == []


def test_tokenize_punctuation_only():
    assert _tokenize("... --- !!!") == []


# ── Stopword scoring ───────────────────────────────────────────────────────


def test_score_stopwords_english():
    tokens = _tokenize("the cat sat on the mat and it was happy")
    score = _score_stopwords(tokens, "en")
    assert score > 0.2
    assert score < 1.0


def test_score_stopwords_french():
    tokens = _tokenize("le chat est sur le tapis et il était content")
    score = _score_stopwords(tokens, "fr")
    assert score > 0.15


def test_score_stopwords_empty_tokens():
    assert _score_stopwords([], "en") == 0.0


def test_score_stopwords_unknown_language():
    tokens = _tokenize("hello world")
    assert _score_stopwords(tokens, "xx") == 0.0


def test_score_stopwords_spanish():
    tokens = _tokenize("el gato esta en la mesa y es muy feliz")
    score = _score_stopwords(tokens, "es")
    assert score > 0.15


def test_score_stopwords_german():
    tokens = _tokenize("die katze ist auf dem tisch und sie ist glucklich")
    score = _score_stopwords(tokens, "de")
    assert score > 0.15


def test_score_stopwords_italian():
    tokens = _tokenize("il gatto e sul tavolo ed e molto felice")
    score = _score_stopwords(tokens, "it")
    assert score > 0.15


def test_score_stopwords_portuguese():
    tokens = _tokenize("o gato esta na mesa e muito feliz")
    score = _score_stopwords(tokens, "pt")
    assert score > 0.15


# ── Trigram scoring ────────────────────────────────────────────────────────


def test_trigrams_non_empty():
    text = "hello world"
    tris = _trigrams(text)
    assert len(tris) > 0


def test_trigrams_short_text():
    text = "ab"
    tris = _trigrams(text)
    assert len(tris) == 0


def test_score_trigrams_english():
    text = "the quick brown fox jumps over the lazy dog"
    score = _score_trigrams(text, "en")
    assert score > 0.0


def test_score_trigrams_french():
    text = "le renard brun rapide saute par dessus le chien paresseux"
    score = _score_trigrams(text, "fr")
    assert score > 0.0


def test_score_trigrams_empty():
    assert _score_trigrams("", "en") == 0.0


def test_score_trigrams_unknown_language():
    assert _score_trigrams("hello world", "xx") == 0.0


# ── Heading scoring ────────────────────────────────────────────────────────


def test_score_headings_french():
    text = "Chapitre 1: SCYLLA\n\nIl était une fois..."
    score = _score_headings(text, "fr")
    assert score > 0.0


def test_score_headings_english():
    text = "Chapter 1: The Beginning\n\nOnce upon a time..."
    score = _score_headings(text, "en")
    assert score > 0.0


def test_score_headings_no_headings():
    text = "Just a regular paragraph with no chapter headings at all."
    score = _score_headings(text, "en")
    assert score == 0.0


def test_score_headings_empty():
    assert _score_headings("", "en") == 0.0


def test_score_headings_mismatched_language():
    text = "Chapitre 1: SCYLLA"
    score = _score_headings(text, "en")
    assert score == 0.0


def test_score_headings_unknown_language():
    text = "Chapter 1"
    score = _score_headings(text, "xx")
    assert score == 0.0


# ── detect_language ────────────────────────────────────────────────────────


def test_score_headings_only_swallows_expected_regex_build_failures(monkeypatch):
    def _invalid_heading_regex(*_args, **_kwargs):
        raise re.error("invalid regex")

    monkeypatch.setattr(language_utils, "build_heading_regex", _invalid_heading_regex)

    assert _score_headings("Chapter 1", "en") == 0.0

    def _unexpected_heading_bug(*_args, **_kwargs):
        raise RuntimeError("heading builder bug")

    monkeypatch.setattr(language_utils, "build_heading_regex", _unexpected_heading_bug)

    with pytest.raises(RuntimeError, match="heading builder bug"):
        _score_headings("Chapter 1", "en")


def test_detect_english():
    text = "It was a dark and stormy night. The rain fell in torrents, except at occasional intervals, when it was checked by a violent gust of wind which swept up the streets of London."
    result = detect_language(text)
    assert result["detected"] == "en"
    assert result["confidence"] > 0.3
    assert len(result["candidates"]) == 6


def test_detect_french():
    text = "C'était une nuit sombre et orageuse. La pluie tombait à torrents, sauf par intervalles, quand elle était arrêtée par une violente rafale de vent qui balayait les rues de Paris."
    result = detect_language(text)
    assert result["detected"] == "fr"
    assert result["confidence"] > 0.3
    assert len(result["candidates"]) == 6


def test_detect_french_manuscript_with_headings():
    text = """Chapitre 1: SCYLLA
Cet Ulysse qui a accosté sur mon île était un homme étrange.

Chapitre 2: LE CHANGE-FORME
Le matin se leva sur une brume épaisse qui enveloppait le port tout entier.

Chapitre 3: LOUIS
Ne t'inquiète pas Louis, tout ira bien quand nous aurons traversé la mer.
"""
    result = detect_language(text)
    assert result["detected"] == "fr"
    assert result["confidence"] > 0.4
    assert len(result["candidates"]) == 6


def test_detect_spanish():
    text = "Era una noche oscura y tormentosa. La lluvia caía a torrentes, excepto en intervalos ocasionales, cuando era detenida por una violenta ráfaga de viento que barría las calles de Madrid."
    result = detect_language(text)
    assert result["detected"] == "es"
    assert result["confidence"] > 0.2
    assert len(result["candidates"]) == 6


def test_detect_german():
    text = "Es war eine dunkle und stürmische Nacht. Der Regen fiel in Strömen, außer in gelegentlichen Abständen, wenn er von einem heftigen Windstoß aufgehalten wurde, der durch die Straßen von Berlin fegte."
    result = detect_language(text)
    assert result["detected"] == "de"
    assert result["confidence"] > 0.3
    assert len(result["candidates"]) == 6


def test_detect_italian():
    text = "Era una notte buia e tempestosa. La pioggia cadeva a torrenti, tranne che a intervalli occasionali, quando veniva fermata da una violenta raffica di vento che spazzava le strade di Roma."
    result = detect_language(text)
    assert result["detected"] == "it"
    assert result["confidence"] > 0.2
    assert len(result["candidates"]) == 6


def test_detect_portuguese():
    text = "Era uma noite escura e tempestuosa. A chuva caía em torrentes, exceto em intervalos ocasionais, quando era detida por uma violenta rajada de vento que varria as ruas de Lisboa."
    result = detect_language(text)
    assert result["detected"] == "pt"
    assert result["confidence"] > 0.2
    assert len(result["candidates"]) == 6


def test_detect_empty_text():
    result = detect_language("")
    assert result["detected"] == "en"
    assert result["confidence"] == 0.0


def test_detect_very_short_text():
    result = detect_language("Bonjour")
    assert result["detected"] == "en"
    assert result["confidence"] == 0.0


def test_detect_language_subset():
    text = "Chapter 1: The Beginning. Once upon a time there lived a king."
    result = detect_language(text, languages=["en", "fr"])
    assert result["detected"] == "en"
    assert len(result["candidates"]) == 2


def test_detect_empty_languages():
    text = "Hello world"
    result = detect_language(text, languages=[])
    assert result["detected"] == "en"
    assert result["confidence"] == 0.0


def test_candidates_are_ranked():
    text = "It was a dark and stormy night upon the moors."
    result = detect_language(text)
    scores = [c["score"] for c in result["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_candidates_have_details():
    text = "It was a dark and stormy night."
    result = detect_language(text)
    for candidate in result["candidates"]:
        assert "language" in candidate
        assert "score" in candidate
        assert "details" in candidate
        assert "stopword_ratio" in candidate["details"]
        assert "trigram_overlap" in candidate["details"]
        assert "heading_score" in candidate["details"]


def test_max_chars_limit():
    long_text = "the " * 10000
    result = detect_language(long_text, max_chars=100)
    assert result["detected"] == "en"


# ── Data integrity ─────────────────────────────────────────────────────────


def test_all_languages_have_stopwords():
    from app.utils.language_utils import ALL_LANGUAGES as LANG_KEYS

    for lang in ["en", "fr", "es", "de", "it", "pt"]:
        assert lang in STOPWORDS, f"Missing stopwords for {lang}"
        assert len(STOPWORDS[lang]) >= 50, f"Too few stopwords for {lang}"


def test_all_languages_have_trigram_profiles():
    for lang in ["en", "fr", "es", "de", "it", "pt"]:
        assert lang in TRIGRAM_PROFILES, f"Missing trigram profile for {lang}"
        assert len(TRIGRAM_PROFILES[lang]) >= 30, f"Too few trigrams for {lang}"


def test_stopwords_are_lowercase():
    for lang, words in STOPWORDS.items():
        for word in words:
            assert word == word.lower(), f"{lang} stopword {word!r} is not lowercase"


def test_no_empty_stopwords():
    for lang, words in STOPWORDS.items():
        for word in words:
            assert word.strip(), f"{lang} has empty stopword"


def test_no_duplicate_trigrams():
    for lang, tris in TRIGRAM_PROFILES.items():
        assert len(tris) == len(set(tris)), f"{lang} trigram profile has duplicates"


def test_trigram_length():
    for lang, tris in TRIGRAM_PROFILES.items():
        for tri in tris:
            assert 3 <= len(tri) <= 4, f"{lang} trigram {tri!r} has unexpected length {len(tri)}"
