"""
BM25-based Retrieval Augmented Generation (RAG) service.

At startup, ingests all transcripts and builds a BM25 index in memory.
Provides retrieve() to fetch top-k relevant chunks for a query.
"""
from __future__ import annotations

import logging
import string
from typing import Optional

from rank_bm25 import BM25Okapi

from app.services.ingestion import TranscriptChunk, ingest_transcripts
from app.config import get_settings
from app.models.schemas import SourceChunk

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Singleton index ───────────────────────────────────────────────────────────

_chunks: list[TranscriptChunk] = []
_bm25: Optional[BM25Okapi] = None
_tokenized_corpus: list[list[str]] = []


def _tokenize(text: str) -> list[str]:
    """Lowercase + remove punctuation tokenizer."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return text.split()


def build_index(force_refresh: bool = False) -> int:
    """
    Build (or rebuild) the BM25 index from transcripts.
    Returns the total number of indexed chunks.
    """
    global _chunks, _bm25, _tokenized_corpus

    logger.info("Building BM25 index …")
    _chunks = ingest_transcripts(
        data_dir=settings.transcripts_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        force_refresh=force_refresh,
    )

    if not _chunks:
        logger.warning("No transcript chunks found — index is empty.")
        _bm25 = None
        return 0

    _tokenized_corpus = [_tokenize(c.chunk_text) for c in _chunks]
    _bm25 = BM25Okapi(_tokenized_corpus)
    logger.info(f"BM25 index ready: {len(_chunks)} chunks")
    return len(_chunks)


def retrieve(query: str, top_k: int | None = None) -> list[SourceChunk]:
    """
    Retrieve the top-k most relevant chunks for a query.
    Returns a list of SourceChunk objects with scores.
    """
    if _bm25 is None or not _chunks:
        logger.warning("RAG index is empty — call build_index() first.")
        return []

    k = top_k or settings.bm25_top_k
    tokenized_query = _tokenize(query)
    scores = _bm25.get_scores(tokenized_query)

    # Get top-k indices sorted by score descending
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    results = []
    for idx in top_indices:
        chunk = _chunks[idx]
        score = float(scores[idx])
        if score > 0:  # skip zero-score results
            results.append(
                SourceChunk(
                    episode_title=chunk.episode_title,
                    episode_number=chunk.episode_number,
                    guest=chunk.guest,
                    chunk_text=chunk.chunk_text,
                    score=round(score, 4),
                )
            )
    return results


def index_size() -> int:
    """Return current number of indexed chunks."""
    return len(_chunks)


def format_context(chunks: list[SourceChunk]) -> str:
    """Format retrieved chunks into a context block for the LLM prompt."""
    if not chunks:
        return "No relevant transcript context found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = f"Episode: {chunk.episode_title}"
        if chunk.guest:
            meta += f" | Guest: {chunk.guest}"
        if chunk.episode_number:
            meta += f" | Ep #{chunk.episode_number}"
        parts.append(f"[Source {i}] {meta}\n{chunk.chunk_text}")

    return "\n\n---\n\n".join(parts)
