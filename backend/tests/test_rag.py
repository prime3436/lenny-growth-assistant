"""
Tests for the RAG ingestion and retrieval pipeline.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.ingestion import _parse_frontmatter, _clean_text, _chunk_text, TranscriptChunk
from app.services.rag import build_index, retrieve, format_context, _chunks, _bm25
from app.models.schemas import SourceChunk


# ── Ingestion tests ───────────────────────────────────────────

class TestParseFrontmatter:
    def test_parses_valid_yaml(self):
        raw = """---
title: How to Price a B2B SaaS Product
guest: Patrick Campbell
episode: 42
---
This is the transcript body."""
        meta, body = _parse_frontmatter(raw)
        assert meta["title"] == "How to Price a B2B SaaS Product"
        assert meta["guest"] == "Patrick Campbell"
        assert meta["episode"] == 42
        assert "transcript body" in body

    def test_handles_no_frontmatter(self):
        raw = "Just transcript text here."
        meta, body = _parse_frontmatter(raw)
        assert meta == {}
        assert body == raw

    def test_handles_malformed_yaml(self):
        raw = "---\nbad: yaml: here: x\n---\nbody"
        # Should not raise, just return empty meta
        meta, body = _parse_frontmatter(raw)
        assert isinstance(meta, dict)


class TestCleanText:
    def test_removes_timestamps(self):
        text = "[00:01:23] Hello there [00:02:45] world"
        result = _clean_text(text)
        assert "[" not in result
        assert "Hello there" in result

    def test_collapses_whitespace(self):
        text = "Line 1\n\n\n\nLine 2"
        result = _clean_text(text)
        assert "\n\n\n" not in result


class TestChunkText:
    def test_basic_chunking(self):
        words = ["word"] * 1000
        text = " ".join(words)
        chunks = _chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        for chunk in chunks:
            word_count = len(chunk.split())
            assert word_count <= 100

    def test_overlap_creates_continuity(self):
        text = " ".join([f"word{i}" for i in range(200)])
        chunks = _chunk_text(text, chunk_size=100, overlap=20)
        # Last words of chunk[0] should appear in chunk[1]
        last_words_c0 = set(chunks[0].split()[-20:])
        first_words_c1 = set(chunks[1].split()[:20])
        assert len(last_words_c0 & first_words_c1) > 0

    def test_short_text_single_chunk(self):
        text = "Short text here"
        chunks = _chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert chunks[0] == text


# ── RAG index tests ───────────────────────────────────────────

class TestBM25Index:
    @pytest.fixture(autouse=True)
    def mock_chunks(self, monkeypatch):
        """Inject synthetic chunks for testing without real transcripts."""
        fake_chunks = [
            TranscriptChunk(
                episode_title="How to Price B2B SaaS",
                episode_number="42",
                guest="Patrick Campbell",
                chunk_text="Pricing strategy for B2B SaaS requires understanding value metrics. Patrick explains how to find the right pricing anchor and avoid the most common pricing mistakes.",
                chunk_index=0,
            ),
            TranscriptChunk(
                episode_title="Finding Product Market Fit",
                episode_number="15",
                guest="Brian Balfour",
                chunk_text="Product market fit is not binary. Brian discusses how to measure retention and engagement to know when you have truly found product market fit.",
                chunk_index=0,
            ),
            TranscriptChunk(
                episode_title="Growth Loops vs Funnels",
                episode_number="88",
                guest="Casey Winters",
                chunk_text="Growth loops are more powerful than funnels because they compound over time. Casey explains viral loops, content loops, and paid loops.",
                chunk_index=0,
            ),
        ]
        import app.services.rag as rag_module
        rag_module._chunks = fake_chunks
        from rank_bm25 import BM25Okapi
        import string
        def _tok(text):
            t = text.lower().translate(str.maketrans("","",string.punctuation))
            return t.split()
        rag_module._tokenized_corpus = [_tok(c.chunk_text) for c in fake_chunks]
        rag_module._bm25 = BM25Okapi(rag_module._tokenized_corpus)

    def test_retrieve_returns_results(self):
        results = retrieve("pricing strategy B2B SaaS")
        assert len(results) > 0
        assert isinstance(results[0], SourceChunk)

    def test_retrieve_returns_relevant_results(self):
        results = retrieve("product market fit retention")
        titles = [r.episode_title for r in results]
        assert any("Product Market Fit" in t for t in titles)

    def test_retrieve_top_k(self):
        results = retrieve("growth", top_k=2)
        assert len(results) <= 2

    def test_retrieve_scores_positive(self):
        results = retrieve("pricing")
        for r in results:
            assert r.score > 0

    def test_format_context_not_empty(self):
        sources = retrieve("growth loops")
        context = format_context(sources)
        assert "[Source 1]" in context
        assert len(context) > 50

    def test_format_context_empty_sources(self):
        context = format_context([])
        assert "No relevant" in context
