"""
Unit tests for paragraph-aware text chunking and content hashing.
"""

import pytest
from scripts.ingest import chunk_text, compute_content_hash


def test_compute_content_hash_deterministic():
    text = "Elena Verna on B2B product-led growth."
    hash1 = compute_content_hash(text)
    hash2 = compute_content_hash(text)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 length


def test_chunk_text_preserves_content_and_overlap():
    sample_text = (
        "First paragraph about retention. " * 20
        + "\n\n"
        + "Second paragraph about pricing experiments. " * 20
        + "\n\n"
        + "Third paragraph on high-leverage frameworks. " * 20
    )
    chunks = chunk_text(sample_text, target_chunk_words=50, overlap_words=10)
    assert len(chunks) >= 2
    assert "retention" in chunks[0]
