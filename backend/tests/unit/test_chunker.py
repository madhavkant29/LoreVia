from app.parsers import chunker
from app.parsers.chunker import ChunkingConfig, chunk_text, count_tokens


def test_chunks_respect_max_tokens():
    long_text = "This is a sentence. " * 200
    chunks = chunk_text(long_text, max_tokens=500, overlap=50)
    for chunk in chunks:
        assert count_tokens(chunk) <= 500


def test_chunking_without_overlap_preserves_all_non_whitespace_characters_in_order():
    passages = [
        "Dr. Vale opens the archive. Mara follows him, then stops. " * 30,
        "\n\n".join(f"The harbor gate closes at hour {index}." for index in range(30)),
        "門が開いた。彼女は振り返らなかった。" * 40,
        "archivekey" * 120,
    ]
    for passage in passages:
        chunks = chunk_text(passage, max_tokens=60, overlap=0)
        assert chunks
        assert all(count_tokens(chunk) <= 60 for chunk in chunks)
        assert "".join("".join(chunks).split()) == "".join(passage.split())


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


def test_overlap_never_pushes_a_chunk_past_the_hard_token_cap():
    paragraphs = [
        "A narrow bridge crosses the black river at dawn.",
        "The watchman leaves a lantern beside the eastern gate.",
        "Mara returns for the lantern before the bell rings.",
        "The bridge is empty when the patrol arrives again.",
    ]
    limit = max(count_tokens(paragraph) for paragraph in paragraphs) + 3
    chunks = chunk_text(
        "\n\n".join(paragraphs),
        config=ChunkingConfig(
            target_tokens=limit - 2, max_tokens=limit, min_tokens=0, overlap_tokens=limit - 3
        ),
    )

    assert len(chunks) > 1
    assert all(count_tokens(part) <= limit for part in chunks)
    assert all(any(paragraph in part for part in chunks) for paragraph in paragraphs)


def test_long_unspaced_input_is_not_lost_or_allowed_to_exceed_the_token_cap():
    word = "archivekey" * 150
    chunks = chunk_text(word, max_tokens=8, overlap=0)

    assert len(chunks) > 1
    assert all(count_tokens(part) <= 8 for part in chunks)
    assert "".join("".join(chunks).split()) == word
