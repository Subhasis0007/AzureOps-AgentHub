from __future__ import annotations


def chunk_text_by_tokens(text: str, *, chunk_size: int = 800, overlap: int = 200) -> list[str]:
    """
    Approximate token chunking by whitespace-separated words.
    This keeps deterministic behavior for tests and local execution.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += step

    return chunks
