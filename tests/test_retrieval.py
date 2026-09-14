import pytest
from app.db import get_db_context
from app.services.retrieval import RetrievalService
from scripts.ingest import generate_local_embedding


def test_cosine_similarity_identical_and_orthogonal():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert pytest.approx(RetrievalService.cosine_similarity(v1, v2)) == 1.0
    assert pytest.approx(RetrievalService.cosine_similarity(v1, v3)) == 0.0


def test_cosine_similarity_dimension_mismatch_safety():
    """Validates that vectors of differing lengths return 0.0 without throwing ValueError."""
    v1 = [1.0, 2.0, 3.0]
    v2 = [1.0, 2.0]
    assert RetrievalService.cosine_similarity(v1, v2) == 0.0
    assert RetrievalService.cosine_similarity([], v1) == 0.0
    assert RetrievalService.cosine_similarity(v1, []) == 0.0


def test_retrieval_threshold_refusal():
    """Validates that a query with no matches above the similarity threshold yields zero citations."""
    with get_db_context() as db:
        unrelated_vector = [0.0] * 3072
        citations = RetrievalService.search_chunks(
            db=db,
            query_vector=unrelated_vector,
            top_k=5,
            threshold=0.99,
            is_cloud=False
        )
        assert len(citations) == 0


def test_retrieval_finds_relevant_chunk():
    """Validates that semantic vector query retrieves matching topic from DB."""
    with get_db_context() as db:
        sample_query = "pricing experiments should never be done haphazardly"
        query_vector = generate_local_embedding(sample_query, dim=3072)
        citations = RetrievalService.search_chunks(
            db=db,
            query_vector=query_vector,
            top_k=3,
            threshold=0.85,
            is_cloud=False
        )
        assert len(citations) > 0
        assert any("Pricing Experiments" in c.episode_title for c in citations)
