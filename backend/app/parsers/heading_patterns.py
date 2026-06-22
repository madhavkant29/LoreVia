"""
Multilingual heading registry and regex builder for manuscript import.

Supports: en, fr, es, de, it, pt.

Provides:
- HEADING_PATTERNS: per-language heading keyword dictionaries
- NUMBER_WORDS_BY_LANG / ORDINAL_WORDS_BY_LANG: per-language number/ordinal maps
- build_heading_regex(): compile a multilingual CHAPTER_RE equivalent
- classify_heading_type(): identify section type from heading text
- is_toc_indicator() / has_toc_signals(): TOC detection heuristics
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal

LanguageCode = Literal["en", "fr", "es", "de", "it", "pt"]
SectionType = Literal[
    "chapter",
    "part",
    "prologue",
    "epilogue",
    "preface",
    "foreword",
    "toc",
    "interlude",
    "appendix",
    "afterword",
    "acknowledgements",
    "dedication",
    "copyright",
    "title_page",
    "glossary",
    "notes",
    "unknown",
]

ALL_LANGUAGES: list[LanguageCode] = ["en", "fr", "es", "de", "it", "pt"]

# ── Per-language heading keywords ───────────────────────────────────────────
# Each list entry is a variant that will be matched case-insensitively.
# Include both accented and unaccented forms for OCR/export tolerance.
# Include common typo variants (e.g. "chaptre" for "chapitre").
#
# Types that take a number (will be followed by digit/roman/word-number):
#   chapter, part, volume, book, act, episode, section, scene
# Standalone types (no number expected):
#   prologue, epilogue, interlude, afterword, preface, foreword,
#   acknowledgements, toc, dedication, copyright, glossary, notes

HEADING_PATTERNS: dict[str, dict[str, list[str]]] = {
    "en": {
        "chapter": ["chapter", "chap.", "ch."],
        "part": ["part", "book", "volume", "vol.", "act", "episode", "section", "scene"],
        "prologue": ["prologue", "prolog"],
        "epilogue": ["epilogue", "epilog"],
        "preface": ["preface", "foreword", "introduction", "intro"],
        "toc": ["table of contents", "contents", "index"],
        "interlude": ["interlude"],
        "appendix": ["appendix", "appendices"],
        "afterword": ["afterword"],
        "acknowledgements": ["acknowledgements", "acknowledgments"],
        "dedication": ["dedication"],
        "copyright": ["copyright"],
        "title_page": [],
        "glossary": ["glossary"],
        "notes": ["notes", "author notes", "author's note", "authors note"],
    },
    "fr": {
        "chapter": [
            "chapitre",
            "chaptre",
            "chap.",
        ],
        "part": [
            "partie",
            "parti",
            "tome",
            "livre",
            "acte",
            "épisode",
            "episode",
            "section",
            "scène",
            "scene",
            "volume",
            "vol.",
        ],
        "prologue": ["prologue", "prolog"],
        "epilogue": [
            "épilogue",
            "epilogue",
        ],
        "preface": [
            "préface",
            "preface",
            "avant-propos",
            "avantpropos",
            "avant propos",
            "introduction",
            "intro",
        ],
        "toc": [
            "table des matières",
            "table des matieres",
            "sommaire",
            "table de matières",
            "table de matieres",
            "index",
        ],
        "interlude": ["interlude", "intermède", "intermede"],
        "appendix": ["appendice", "annexe", "appendices", "annexes"],
        "afterword": ["postface", "après-propos", "apres-propos", "epilogue", "épilogue"],
        "acknowledgements": [
            "remerciements",
            "remerciments",
            "reconnaissances",
        ],
        "dedication": ["dédicace", "dedicace"],
        "copyright": ["droit d'auteur", "droits d'auteur", "copyright"],
        "title_page": [],
        "glossary": ["glossaire"],
        "notes": [
            "notes de l'auteur",
            "notes de l'auteure",
            "note de l'auteur",
            "note de l'auteure",
            "notes",
        ],
    },
    "es": {
        "chapter": ["capítulo", "capitulo", "cap."],
        "part": [
            "parte",
            "libro",
            "volumen",
            "vol.",
            "acto",
            "episodio",
            "sección",
            "seccion",
            "escena",
        ],
        "prologue": ["prólogo", "prologo"],
        "epilogue": ["epílogo", "epilogo"],
        "preface": ["prefacio", "introducción", "introduccion", "intro"],
        "toc": [
            "índice",
            "indice",
            "tabla de contenidos",
            "tabla de contenido",
            "índice de materias",
            "indice de materias",
        ],
        "interlude": ["interludio"],
        "appendix": ["apéndice", "apendice", "anexo", "apéndices", "apendices"],
        "afterword": ["epílogo", "epilogo", "posfacio"],
        "acknowledgements": ["agradecimientos", "agradecimentos", "reconocimientos"],
        "dedication": ["dedicatoria", "dedicación", "dedicacion"],
        "copyright": ["derechos de autor", "copyright"],
        "title_page": [],
        "glossary": ["glosario"],
        "notes": ["notas del autor", "nota del autor", "notas de la autora", "notas"],
    },
    "de": {
        "chapter": ["kapitel", "kap."],
        "part": [
            "teil",
            "buch",
            "band",
            "akt",
            "episode",
            "abschnitt",
            "szene",
            "volumen",
            "vol.",
        ],
        "prologue": ["prolog", "vorwort"],
        "epilogue": ["epilog", "nachwort"],
        "preface": ["vorwort", "einführung", "einfuehrung", "einleitung", "intro"],
        "toc": [
            "inhaltsverzeichnis",
            "inhaltsverzeichniss",
            "inhalt",
            "index",
        ],
        "interlude": ["zwischenspiel", "interludium"],
        "appendix": ["anhang", "anhänge", "anhaenge", "appendix"],
        "afterword": ["nachwort"],
        "acknowledgements": ["danksagung", "danksagungen", "dank"],
        "dedication": ["widmung"],
        "copyright": ["urheberrecht", "copyright"],
        "title_page": [],
        "glossary": ["glossar"],
        "notes": ["anmerkungen des autors", "anmerkung des autors", "anmerkungen"],
    },
    "it": {
        "chapter": ["capitolo", "cap."],
        "part": [
            "parte",
            "libro",
            "volume",
            "vol.",
            "atto",
            "episodio",
            "sezione",
            "scena",
        ],
        "prologue": ["prologo", "prolog"],
        "epilogue": ["epilogo", "epilog"],
        "preface": ["prefazione", "introduzione", "intro"],
        "toc": [
            "indice",
            "indici",
            "sommario",
            "tabella dei contenuti",
        ],
        "interlude": ["interludio", "intermezzo"],
        "appendix": ["appendice", "allegato", "appendici"],
        "afterword": ["postfazione", "epilogo"],
        "acknowledgements": ["ringraziamenti", "riconoscimenti"],
        "dedication": ["dedica"],
        "copyright": ["diritti d'autore", "copyright"],
        "title_page": [],
        "glossary": ["glossario"],
        "notes": ["note dell'autore", "note dell'autrice", "note"],
    },
    "pt": {
        "chapter": ["capítulo", "capitulo", "cap."],
        "part": [
            "parte",
            "livro",
            "volume",
            "vol.",
            "ato",
            "episódio",
            "episodio",
            "seção",
            "seccao",
            "secção",
            "cena",
        ],
        "prologue": ["prólogo", "prologo"],
        "epilogue": ["epílogo", "epilogo"],
        "preface": ["prefácio", "prefacio", "introdução", "introducao", "intro"],
        "toc": [
            "índice",
            "indice",
            "sumário",
            "sumario",
            "tabela de conteúdos",
            "tabela de conteudos",
        ],
        "interlude": ["interlúdio", "interludio"],
        "appendix": ["apêndice", "apendice", "anexo", "apêndices", "apendices"],
        "afterword": ["posfácio", "posfacio", "epílogo", "epilogo"],
        "acknowledgements": ["agradecimentos", "reconhecimentos"],
        "dedication": ["dedicatória", "dedicatoria"],
        "copyright": ["direitos autorais", "copyright", "direitos de autor"],
        "title_page": [],
        "glossary": ["glossário", "glossario"],
        "notes": ["notas do autor", "nota do autor", "notas da autora", "notas"],
    },
}


# ── Per-language number words ───────────────────────────────────────────────


def _en_number_words() -> dict[str, int]:
    return {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }


def _fr_number_words() -> dict[str, int]:
    return {
        "zéro": 0,
        "zero": 0,
        "un": 1,
        "une": 1,
        "deux": 2,
        "trois": 3,
        "quatre": 4,
        "cinq": 5,
        "six": 6,
        "sept": 7,
        "huit": 8,
        "neuf": 9,
        "dix": 10,
        "onze": 11,
        "douze": 12,
        "treize": 13,
        "quatorze": 14,
        "quinze": 15,
        "seize": 16,
        "dix-sept": 17,
        "dixsept": 17,
        "dix-huit": 18,
        "dixhuit": 18,
        "dix-neuf": 19,
        "dixneuf": 19,
        "vingt": 20,
        "trente": 30,
        "quarante": 40,
        "cinquante": 50,
        "soixante": 60,
        "soixante-dix": 70,
        "soixantedix": 70,
        "quatre-vingts": 80,
        "quatrevingts": 80,
        "quatre-vingt": 80,
        "quatre-vingt-dix": 90,
        "quatrevingtdix": 90,
        "cent": 100,
    }


def _es_number_words() -> dict[str, int]:
    return {
        "cero": 0,
        "uno": 1,
        "un": 1,
        "una": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9,
        "diez": 10,
        "once": 11,
        "doce": 12,
        "trece": 13,
        "catorce": 14,
        "quince": 15,
        "dieciséis": 16,
        "dieciseis": 16,
        "diecisiete": 17,
        "dieciocho": 18,
        "diecinueve": 19,
        "veinte": 20,
        "treinta": 30,
        "cuarenta": 40,
        "cincuenta": 50,
        "sesenta": 60,
        "setenta": 70,
        "ochenta": 80,
        "noventa": 90,
    }


def _de_number_words() -> dict[str, int]:
    return {
        "null": 0,
        "eins": 1,
        "ein": 1,
        "eine": 1,
        "zwei": 2,
        "drei": 3,
        "vier": 4,
        "fünf": 5,
        "funf": 5,
        "sechs": 6,
        "sieben": 7,
        "acht": 8,
        "neun": 9,
        "zehn": 10,
        "elf": 11,
        "zwölf": 12,
        "zwolf": 12,
        "dreizehn": 13,
        "vierzehn": 14,
        "fünfzehn": 15,
        "funfzehn": 15,
        "sechzehn": 16,
        "siebzehn": 17,
        "achtzehn": 18,
        "neunzehn": 19,
        "zwanzig": 20,
        "dreißig": 30,
        "dreissig": 30,
        "vierzig": 40,
        "fünfzig": 50,
        "funfzig": 50,
        "sechzig": 60,
        "siebzig": 70,
        "achtzig": 80,
        "neunzig": 90,
    }


def _it_number_words() -> dict[str, int]:
    return {
        "zero": 0,
        "uno": 1,
        "una": 1,
        "un": 1,
        "due": 2,
        "tre": 3,
        "quattro": 4,
        "cinque": 5,
        "sei": 6,
        "sette": 7,
        "otto": 8,
        "nove": 9,
        "dieci": 10,
        "undici": 11,
        "dodici": 12,
        "tredici": 13,
        "quattordici": 14,
        "quindici": 15,
        "sedici": 16,
        "diciassette": 17,
        "diciotto": 18,
        "diciannove": 19,
        "venti": 20,
        "trenta": 30,
        "quaranta": 40,
        "cinquanta": 50,
        "sessanta": 60,
        "settanta": 70,
        "ottanta": 80,
        "novanta": 90,
    }


def _pt_number_words() -> dict[str, int]:
    return {
        "zero": 0,
        "um": 1,
        "uma": 1,
        "dois": 2,
        "duas": 2,
        "três": 3,
        "tres": 3,
        "quatro": 4,
        "cinco": 5,
        "seis": 6,
        "sete": 7,
        "oito": 8,
        "nove": 9,
        "dez": 10,
        "onze": 11,
        "doze": 12,
        "treze": 13,
        "catorze": 14,
        "quatorze": 14,
        "quinze": 15,
        "dezasseis": 16,
        "dezesseis": 16,
        "dezassete": 17,
        "dezessete": 17,
        "dezoito": 18,
        "dezanove": 19,
        "dezenove": 19,
        "vinte": 20,
        "trinta": 30,
        "quarenta": 40,
        "cinquenta": 50,
        "sessenta": 60,
        "setenta": 70,
        "oitenta": 80,
        "noventa": 90,
    }


NUMBER_WORDS_BY_LANG: dict[str, dict[str, int]] = {
    "en": _en_number_words(),
    "fr": _fr_number_words(),
    "es": _es_number_words(),
    "de": _de_number_words(),
    "it": _it_number_words(),
    "pt": _pt_number_words(),
}

# ── Per-language ordinal words ──────────────────────────────────────────────


def _en_ordinal_words() -> dict[str, int]:
    return {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
        "eleventh": 11,
        "twelfth": 12,
        "thirteenth": 13,
        "fourteenth": 14,
        "fifteenth": 15,
        "sixteenth": 16,
        "seventeenth": 17,
        "eighteenth": 18,
        "nineteenth": 19,
        "twentieth": 20,
        "thirtieth": 30,
        "fortieth": 40,
        "fiftieth": 50,
        "sixtieth": 60,
        "seventieth": 70,
        "eightieth": 80,
        "ninetieth": 90,
    }


def _fr_ordinal_words() -> dict[str, int]:
    return {
        "premier": 1,
        "première": 1,
        "premiere": 1,
        "prem": 1,
        "deuxième": 2,
        "deuxieme": 2,
        "second": 2,
        "seconde": 2,
        "troisième": 3,
        "troisieme": 3,
        "quatrième": 4,
        "quatrieme": 4,
        "cinquième": 5,
        "cinquieme": 5,
        "sixième": 6,
        "sixieme": 6,
        "septième": 7,
        "septieme": 7,
        "huitième": 8,
        "huitieme": 8,
        "neuvième": 9,
        "neuvieme": 9,
        "dixième": 10,
        "dixieme": 10,
        "onzième": 11,
        "onzieme": 11,
        "douzième": 12,
        "douzieme": 12,
        "treizième": 13,
        "treizieme": 13,
        "quatorzième": 14,
        "quatorzieme": 14,
        "quinzième": 15,
        "quinzieme": 15,
        "seizième": 16,
        "seizieme": 16,
        "dix-septième": 17,
        "dixseptieme": 17,
        "dix-huitième": 18,
        "dixhuitieme": 18,
        "dix-neuvième": 19,
        "dixneuvieme": 19,
        "vingtième": 20,
        "vingtieme": 20,
        "trentième": 30,
        "trentieme": 30,
        "quarantième": 40,
        "quarantieme": 40,
        "cinquantième": 50,
        "cinquantieme": 50,
        "soixantième": 60,
        "soixantieme": 60,
        "soixante-dixième": 70,
        "soixantedixieme": 70,
        "quatre-vingtième": 80,
        "quatrevingtieme": 80,
        "quatre-vingt-dixième": 90,
        "quatrevingtdixieme": 90,
    }


def _es_ordinal_words() -> dict[str, int]:
    return {
        "primero": 1,
        "primera": 1,
        "primer": 1,
        "segundo": 2,
        "segunda": 2,
        "tercero": 3,
        "tercera": 3,
        "tercer": 3,
        "cuarto": 4,
        "cuarta": 4,
        "quinto": 5,
        "quinta": 5,
        "sexto": 6,
        "sexta": 6,
        "séptimo": 7,
        "septimo": 7,
        "séptima": 7,
        "septima": 7,
        "octavo": 8,
        "octava": 8,
        "noveno": 9,
        "novena": 9,
        "décimo": 10,
        "decimo": 10,
        "undécimo": 11,
        "undecimo": 11,
        "duodécimo": 12,
        "duodecimo": 12,
        "vigésimo": 20,
        "vigesimo": 20,
        "trigésimo": 30,
        "trigesimo": 30,
    }


def _de_ordinal_words() -> dict[str, int]:
    return {
        "erste": 1,
        "erster": 1,
        "erstes": 1,
        "zweite": 2,
        "zweiter": 2,
        "zweites": 2,
        "dritte": 3,
        "dritter": 3,
        "drittes": 3,
        "vierte": 4,
        "vierter": 4,
        "viertes": 4,
        "fünfte": 5,
        "funfte": 5,
        "fünfter": 5,
        "funfter": 5,
        "sechste": 6,
        "sechster": 6,
        "siebte": 7,
        "siebter": 7,
        "siebente": 7,
        "achte": 8,
        "achter": 8,
        "neunte": 9,
        "neunter": 9,
        "zehnte": 10,
        "zehnter": 10,
        "elfte": 11,
        "elfter": 11,
        "zwölfte": 12,
        "zwolfte": 12,
        "dreizehnte": 13,
        "vierzehnte": 14,
        "fünfzehnte": 15,
        "funfzehnte": 15,
        "sechzehnte": 16,
        "siebzehnte": 17,
        "achtzehnte": 18,
        "neunzehnte": 19,
        "zwanzigste": 20,
        "dreißigste": 30,
        "dreissigste": 30,
        "vierzigste": 40,
        "fünfzigste": 50,
        "funfzigste": 50,
        "sechzigste": 60,
        "siebzigste": 70,
        "achtzigste": 80,
        "neunzigste": 90,
    }


def _it_ordinal_words() -> dict[str, int]:
    return {
        "primo": 1,
        "prima": 1,
        "secondo": 2,
        "seconda": 2,
        "terzo": 3,
        "terza": 3,
        "quarto": 4,
        "quarta": 4,
        "quinto": 5,
        "quinta": 5,
        "sesto": 6,
        "sesta": 6,
        "settimo": 7,
        "settima": 7,
        "ottavo": 8,
        "ottava": 8,
        "nono": 9,
        "nona": 9,
        "decimo": 10,
        "decima": 10,
        "undicesimo": 11,
        "dodicesimo": 12,
        "tredicesimo": 13,
        "quattordicesimo": 14,
        "quindicesimo": 15,
        "sedicesimo": 16,
        "diciassettesimo": 17,
        "diciottesimo": 18,
        "diciannovesimo": 19,
        "ventesimo": 20,
        "trentesimo": 30,
        "quarantesimo": 40,
        "cinquantesimo": 50,
        "sessantesimo": 60,
        "settantesimo": 70,
        "ottantesimo": 80,
        "novantesimo": 90,
    }


def _pt_ordinal_words() -> dict[str, int]:
    return {
        "primeiro": 1,
        "primeira": 1,
        "segundo": 2,
        "segunda": 2,
        "terceiro": 3,
        "terceira": 3,
        "quarto": 4,
        "quarta": 4,
        "quinto": 5,
        "quinta": 5,
        "sexto": 6,
        "sexta": 6,
        "sétimo": 7,
        "setimo": 7,
        "sétima": 7,
        "setima": 7,
        "oitavo": 8,
        "oitava": 8,
        "nono": 9,
        "nona": 9,
        "décimo": 10,
        "decimo": 10,
        "vigésimo": 20,
        "vigesimo": 20,
        "trigésimo": 30,
        "trigesimo": 30,
    }


ORDINAL_WORDS_BY_LANG: dict[str, dict[str, int]] = {
    "en": _en_ordinal_words(),
    "fr": _fr_ordinal_words(),
    "es": _es_ordinal_words(),
    "de": _de_ordinal_words(),
    "it": _it_ordinal_words(),
    "pt": _pt_ordinal_words(),
}

# ── Backward-compatible aliases (English only, matching pdf_parser.py) ──────

NUMBER_WORDS = _en_number_words()
ORDINAL_WORDS = _en_ordinal_words()

# ── Legacy regexes (kept for reference; build_heading_regex() is preferred) ─

_ROMAN_NUMERAL_RE = r"[IVXLCDM]+"
_LETTER_RE = r"[A-Za-z]{1,3}"

# ── Regex builder ───────────────────────────────────────────────────────────

# Section types that expect a number/identifier after the heading keyword.
_NUMBERED_TYPES = {"chapter", "part"}

# Section types that are standalone (no number).
_STANDALONE_TYPES = {
    "prologue",
    "epilogue",
    "preface",
    "foreword",
    "toc",
    "interlude",
    "appendix",
    "afterword",
    "acknowledgements",
    "dedication",
    "copyright",
    "title_page",
    "glossary",
    "notes",
}


def _collect_keywords(
    languages: list[str],
    section_types: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Collect numbered and standalone keywords across languages.

    Returns (numbered_keywords, standalone_keywords) where each list
    contains unique, regex-escaped, case-insensitive keyword patterns.
    """
    numbered: set[str] = set()
    standalone: set[str] = set()

    for lang in languages:
        patterns = HEADING_PATTERNS.get(lang)
        if patterns is None:
            continue
        for stype, keywords in patterns.items():
            if section_types is not None and stype not in section_types:
                continue
            escaped = [re.escape(kw) for kw in keywords if kw]
            if stype in _NUMBERED_TYPES:
                numbered.update(escaped)
            elif stype in _STANDALONE_TYPES:
                standalone.update(escaped)

    return sorted(numbered, key=len, reverse=True), sorted(standalone, key=len, reverse=True)


def _build_number_pattern(languages: list[str]) -> str:
    """Build the number-matching subpattern for heading regex.

    Covers: digits, roman numerals, letters, written number words,
    written ordinals, and compound number-words (e.g. twenty-one).
    """
    digit_pattern = r"\d+[a-z]?"

    number_words_by_lang: set[str] = set()
    ordinal_words_by_lang: set[str] = set()
    for lang in languages:
        nw = NUMBER_WORDS_BY_LANG.get(lang, {})
        ow = ORDINAL_WORDS_BY_LANG.get(lang, {})
        number_words_by_lang.update(nw.keys())
        ordinal_words_by_lang.update(ow.keys())

    number_word_alt = ""
    if number_words_by_lang:
        escaped = sorted(
            {re.escape(w) for w in number_words_by_lang if len(w) > 1},
            key=len,
            reverse=True,
        )
        number_word_alt = "|".join(escaped)

    ordinal_word_alt = ""
    if ordinal_words_by_lang:
        escaped = sorted(
            {re.escape(w) for w in ordinal_words_by_lang if len(w) > 1},
            key=len,
            reverse=True,
        )
        ordinal_word_alt = "|".join(escaped)

    parts: list[str] = [digit_pattern, _ROMAN_NUMERAL_RE, _LETTER_RE]

    if number_word_alt:
        parts.append(f"(?:{number_word_alt})")
    if ordinal_word_alt:
        parts.append(f"(?:{ordinal_word_alt})")

    all_number_words = number_words_by_lang | ordinal_words_by_lang
    if all_number_words:
        escaped_all = sorted(
            {re.escape(w) for w in all_number_words if len(w) > 1},
            key=len,
            reverse=True,
        )
        compound = f"(?:{'|'.join(escaped_all)})(?:[-\\s](?:{'|'.join(escaped_all)}))?"
        parts.append(compound)

    return "|".join(parts)


def build_heading_regex(
    languages: list[str] | None = None,
    section_types: list[str] | None = None,
) -> re.Pattern:
    """Compile a multilingual chapter-heading regex.

    Args:
        languages: ISO 639-1 codes (default: all supported).
        section_types: Filter to specific section types (default: all).

    Returns:
        Compiled regex with re.IGNORECASE flag, matching heading lines
        in the same style as the original CHAPTER_RE in pdf_parser.py.

    Example matches:
        "Chapter 1"           → match
        "Chapitre 10: SCYLLA" → match
        "Prologue"            → match
        "Préface"             → match
        "Table des matières"  → match
    """
    langs = languages if languages is not None else ALL_LANGUAGES
    numbered_kws, standalone_kws = _collect_keywords(langs, section_types)

    pattern_parts: list[str] = []

    if numbered_kws:
        num_alt = "|".join(numbered_kws)
        num_pat = _build_number_pattern(langs)
        pattern_parts.append(rf"(?:{num_alt})\s+(?:{num_pat})(?:\s*[:.\-]\s*.+)?")

    if standalone_kws:
        sa_alt = "|".join(standalone_kws)
        pattern_parts.append(rf"(?:{sa_alt})(?:\s+[a-z0-9]+)?")

    if not pattern_parts:
        pattern_parts.append(r"(?!)")

    full_pattern = r"^(?:" + "|".join(pattern_parts) + r")$"
    return re.compile(full_pattern, re.IGNORECASE)


# ── Section type classifier ─────────────────────────────────────────────────


def classify_heading_type(
    heading: str,
    language: str,
) -> tuple[SectionType, float]:
    """Identify the section type of a heading text.

    Args:
        heading: The cleaned heading text (e.g. "Chapitre 1: SCYLLA").
        language: Detected or user-specified language code.

    Returns:
        (section_type, confidence) where confidence is 0.0–1.0.
        Returns ("unknown", 0.0) when no type can be determined.
    """
    if not heading or not heading.strip():
        return "unknown", 0.0

    cleaned = heading.strip()
    patterns = HEADING_PATTERNS.get(language, HEADING_PATTERNS["en"])

    best_type: SectionType = "unknown"
    best_score = 0.0

    for stype, keywords in patterns.items():
        if not keywords:
            continue
        for kw in keywords:
            escaped = re.escape(kw)
            if re.search(rf"\b{escaped}\b", cleaned, re.IGNORECASE):
                score = len(kw) / len(cleaned) if len(cleaned) > 0 else 1.0
                boost = 1.0
                if re.match(rf"^{escaped}", cleaned, re.IGNORECASE):
                    boost = 1.3
                    # Strong boost for numbered headings (Chapter 1, Part IV, etc.)
                    # to prevent embedded keywords like "Introduction" from
                    # overriding the chapter classification.
                    if stype in _NUMBERED_TYPES and _has_number_after_keyword(cleaned, language):
                        boost = 2.0
                score = min(1.0, score * boost)
                if score > best_score:
                    best_score = score
                    best_type = stype

    if best_type in _NUMBERED_TYPES and not _has_number_after_keyword(cleaned, language):
        return best_type, best_score * 0.7

    return best_type, best_score


def _has_number_after_keyword(heading: str, language: str) -> bool:
    """Check if heading has a number after the keyword portion."""
    patterns = HEADING_PATTERNS.get(language, HEADING_PATTERNS["en"])
    numbered_keywords: list[str] = []
    for stype in _NUMBERED_TYPES:
        numbered_keywords.extend(patterns.get(stype, []))

    for kw in sorted(numbered_keywords, key=len, reverse=True):
        escaped = re.escape(kw)
        m = re.match(rf"^{escaped}\s+(.+)", heading, re.IGNORECASE)
        if m:
            rest = m.group(1).strip()
            rest_no_title = re.split(r"\s*[:.\-]\s*", rest, maxsplit=1)[0].strip()
            if re.match(r"^\d+[a-z]?$", rest_no_title, re.IGNORECASE):
                return True
            if re.match(rf"^[{''.join(set('IVXLCDM'))}]+$", rest_no_title, re.IGNORECASE):
                return True
            nw = NUMBER_WORDS_BY_LANG.get(language, {})
            ow = ORDINAL_WORDS_BY_LANG.get(language, {})
            token = rest_no_title.lower()
            if token in nw or token in ow:
                return True
            return False
    return False


# ── TOC detection heuristics ────────────────────────────────────────────────

_TOC_DOT_PATTERN = re.compile(r"[.]{5,}|[.]\s+[.]")  # 5+ contiguous dots or spaced dots
_TOC_PAGE_NUMBER_PATTERN = re.compile(r"\d{1,4}\s*$")


def is_toc_indicator(line: str) -> bool:
    """Check if a single line looks like a table-of-contents entry.

    Signals:
    - Contains dotted leaders (.....)
    - Line ends with a page number and has a heading-like prefix
    - Short line that looks like a chapter listing (e.g. "Chapter 1......5")
    """
    stripped = line.strip()
    if not stripped:
        return False
    if _TOC_DOT_PATTERN.search(stripped):
        return True
    if _TOC_PAGE_NUMBER_PATTERN.search(stripped):
        pre_number = re.sub(r"\d{1,4}\s*$", "", stripped).strip()
        # Require a substantial prefix (> 20 chars) to avoid flagging bare
        # chapter headings like "Chapter 1" that happen to end in a number.
        if len(pre_number) > 15 and len(pre_number) < 200:
            return True
    return False


def has_toc_signals(lines: list[str], sample_size: int = 40) -> bool:
    """Check if a block of lines contains TOC-like patterns.

    Heuristics:
    - Multiple lines (>= 3) within the sample match TOC indicators.
    - High heading density (many short lines with heading-like patterns).
    - Low average line length relative to normal body text.
    """
    if not lines or len(lines) < 3:
        return False

    sample = lines[: min(len(lines), sample_size)]
    if any(len(_TOC_DOT_PATTERN.findall(line)) >= 3 for line in sample):
        return True

    toc_count = sum(1 for line in sample if is_toc_indicator(line))
    if toc_count >= 3:
        return True

    non_empty = [line for line in sample if line.strip()]
    if len(non_empty) < 5:
        return False

    avg_len = sum(len(line) for line in non_empty) / len(non_empty)
    if avg_len < 80 and toc_count >= 1:
        return True

    return False


def get_number_words(language: str) -> dict[str, int]:
    return NUMBER_WORDS_BY_LANG.get(language, _en_number_words())


def get_ordinal_words(language: str) -> dict[str, int]:
    return ORDINAL_WORDS_BY_LANG.get(language, _en_ordinal_words())


def get_section_type_defaults(section_type: SectionType) -> dict:
    """Return default display/analysis settings for a section type.

    Returns dict with:
        include_in_analysis: bool — whether AI extraction should process this section
        display_order: int — sort order for UI (lower = earlier in document flow)
    """
    include_by_default = {
        "chapter",
        "prologue",
        "epilogue",
        "scene",
        "interlude",
    }
    optional = {"preface", "foreword", "appendix", "afterword", "part", "unknown"}

    if section_type in include_by_default:
        include = True
    elif section_type in optional:
        include = True  # included by default but user may toggle off
    else:
        include = False

    return {
        "include_in_analysis": include,
        "display_order": _display_order(section_type),
    }


def _display_order(section_type: SectionType) -> int:
    order = {
        "title_page": 0,
        "copyright": 1,
        "dedication": 2,
        "toc": 3,
        "foreword": 4,
        "preface": 5,
        "acknowledgements": 6,
        "prologue": 7,
        "part": 8,
        "chapter": 9,
        "scene": 10,
        "interlude": 11,
        "epilogue": 12,
        "afterword": 13,
        "appendix": 14,
        "glossary": 15,
        "notes": 16,
        "unknown": 99,
    }
    return order.get(section_type, 99)
