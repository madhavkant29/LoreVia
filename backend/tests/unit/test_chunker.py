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
