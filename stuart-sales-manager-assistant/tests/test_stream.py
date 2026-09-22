from ui.stream import word_deltas


def test_word_deltas_keep_words_and_spacing() -> None:
    chunks = word_deltas("NovaPay is high risk.")
    assert chunks
    assert "".join(chunks).strip() == "NovaPay is high risk."


def test_word_deltas_keep_leading_newlines() -> None:
    chunks = word_deltas("\n\n## Summary\nWest is ready.")
    assert "".join(chunks) == "\n\n## Summary\nWest is ready."
