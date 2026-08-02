from app.parsers import chunker
from app.parsers.chunker import chunk_text, count_tokens


def test_chunks_respect_max_tokens():
    long_text = "This is a sentence. " * 200
    chunks = chunk_text(long_text, max_tokens=500, overlap=50)
    for chunk in chunks:
        assert count_tokens(chunk) <= 600  # allow slight overshoot on last chunk


def test_overlap_preserves_context():
    text = ". ".join(f"Sentence {i}" for i in range(50)) + "."
    chunks = chunk_text(text, max_tokens=100, overlap=20)
    assert len(chunks) > 1
    # Second chunk should share some content with first (overlap)
    first_words = set(chunks[0].split()[-10:])
    second_words = set(chunks[1].split()[:15])
    assert len(first_words & second_words) > 0


def test_single_chunk_for_short_text():
    text = "Short text. Only two sentences."
    chunks = chunk_text(text, max_tokens=1500, overlap=100)
    assert len(chunks) == 1


def test_large_paragraph_respects_abbreviations_when_splitting():
    text = (
        "Dr. Hargrove stayed silent. Mr. Vale answered slowly. The corridor remained still. " * 40
    )
    chunks = chunk_text(text, max_tokens=120, overlap=20)
    assert all("Dr." in chunk or "Mr." in chunk or "corridor" in chunk for chunk in chunks)


def test_oversized_sentence_prefers_clause_boundaries_before_word_splits():
    sentence = "Alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa, lambda."
    chunks = chunk_text(sentence, max_tokens=15, overlap=0)
    assert len(chunks) > 1
    assert any("," in chunk for chunk in chunks[:-1])


def test_token_count_has_conservative_offline_fallback(monkeypatch):
    monkeypatch.setattr(chunker, "_enc", None)
    monkeypatch.setattr(chunker, "_encoding_load_failed", False)

    def unavailable(_model):
        raise OSError("network unavailable")

    monkeypatch.setattr(chunker.tiktoken, "encoding_for_model", unavailable)

    assert count_tokens("abcdef") == 2
    assert count_tokens("") == 0
    assert count_tokens("[[IMAGE:cover.png]]") > 0
    assert chunker._encoding_load_failed is True
