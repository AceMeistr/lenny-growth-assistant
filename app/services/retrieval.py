import logging
from typing import List, Tuple
import numpy as np
from sqlalchemy.orm import Session as DBSession

from app.models.entities import TranscriptChunk, TranscriptSource
from app.models.schemas import Citation

logger = logging.getLogger(__name__)


class RetrievalService:
    """Performs semantic search across ingested Lenny transcript chunks."""

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two vectors with dimension checking."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        a = np.array(v1, dtype=float)
        b = np.array(v2, dtype=float)
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    @classmethod
    def search_chunks(
        cls,
        db: DBSession,
        query_vector: List[float],
        top_k: int = 6,
        threshold: float = 0.35,
        is_cloud: bool = False
    ) -> List[Citation]:
        """
        Search chunks in database matching the query vector.
        Pre-filters with SQL LIMIT 200 to avoid O(N) full table scan in Python.
        Enforces vector dimension compatibility.
        """
        if db is None or not query_vector:
            return []

        chunks = db.query(TranscriptChunk).limit(200).all()
        if not chunks:
            return []

        scored_chunks: List[Tuple[float, TranscriptChunk]] = []
        for chunk in chunks:
            vec = chunk.embedding_cloud if is_cloud else chunk.embedding_local
            if not vec:
                vec = chunk.embedding_local or chunk.embedding_cloud
            if not vec or len(vec) != len(query_vector):
                continue

            score = cls.cosine_similarity(query_vector, vec)
            if score >= threshold:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_scored = scored_chunks[:max(1, top_k)]

        citations: List[Citation] = []
        for score, chunk in top_scored:
            source = db.query(TranscriptSource).filter_by(id=chunk.source_id).first()
            episode_title = source.episode_title if source else "Lenny's Podcast"
            episode_url = source.episode_url if source else None
            snippet = chunk.content[:220].strip() + ("..." if len(chunk.content) > 220 else "")

            citations.append(
                Citation(
                    episode_title=episode_title,
                    source_url=episode_url,
                    chunk_index=chunk.chunk_index,
                    content_snippet=snippet,
                    similarity_score=round(score, 4)
                )
            )

        return citations
