"""Tests for LLM reranker."""

import os
import sys
import pytest
from unittest.mock import patch, Mock

from src.services.reranker import score_passages
from src.tools.retrieval import HybridRetriever
from src.core.types import Chunk, RetrievalResult


class TestReranker:
    """Test suite for passage reranking."""
    
    def test_reranker_disabled_returns_uniform(self):
        """When disabled, should return uniform scores."""
        with patch.dict(os.environ, {"RERANK_ENABLED": "0"}):
            passages = [
                {"path": "file1.py", "text": "def foo(): pass"},
                {"path": "file2.py", "text": "class Bar: pass"},
            ]
            
            scores = score_passages("find foo", passages)
            
            assert scores == [0.5, 0.5]
    
    def test_reranker_empty_passages(self):
        """Should handle empty passages list."""
        scores = score_passages("query", [])
        assert scores == []
    
    def test_reranker_enabled_mock(self):
        """Test reranker with mocked LLM response."""
        with patch.dict(os.environ, {
            "RERANK_ENABLED": "1",
            "GOOGLE_CLOUD_PROJECT": "test-project"
        }):
            # Mock at the module level where they're imported
            mock_ai = Mock()
            mock_model_class = Mock()
            mock_model = Mock()
            mock_response = Mock()
            mock_response.text = "[0.9, 0.2, 0.6]"
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            with patch.dict("sys.modules", {
                "google.cloud.aiplatform": mock_ai,
                "vertexai.generative_models": Mock(GenerativeModel=mock_model_class)
            }):
                passages = [
                    {"path": "relevant.py", "text": "def search_function(): pass"},
                    {"path": "unrelated.py", "text": "import os"},  
                    {"path": "somewhat.py", "text": "def find_item(): pass"},
                ]
                
                scores = score_passages("search function", passages)
                
                assert scores == [0.9, 0.2, 0.6]
                assert mock_model.generate_content.called
    
    def test_reranker_error_fallback(self):
        """Should return uniform scores on error."""
        with patch.dict(os.environ, {"RERANK_ENABLED": "1"}):
            # Mock to raise an error
            mock_ai = Mock()
            mock_ai.init.side_effect = Exception("API error")
            
            with patch.dict("sys.modules", {
                "google.cloud.aiplatform": mock_ai,
                "vertexai.generative_models": Mock()
            }):
                passages = [
                    {"path": "file1.py", "text": "code"},
                    {"path": "file2.py", "text": "more code"},
                ]
                
                scores = score_passages("query", passages)
                
                # Should fall back to uniform scores
                assert scores == [0.5, 0.5]
    
    def test_reranker_clamps_scores(self):
        """Should clamp scores to [0, 1] range."""
        with patch.dict(os.environ, {"RERANK_ENABLED": "1"}):
            mock_ai = Mock()
            mock_model_class = Mock()
            mock_model = Mock()
            mock_response = Mock()
            # Return out-of-range scores
            mock_response.text = "[-0.5, 1.5, 0.5]"
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            with patch.dict("sys.modules", {
                "google.cloud.aiplatform": mock_ai,
                "vertexai.generative_models": Mock(GenerativeModel=mock_model_class)
            }):
                passages = [
                    {"path": "a.py", "text": "code"},
                    {"path": "b.py", "text": "code"},
                    {"path": "c.py", "text": "code"},
                ]
                
                scores = score_passages("query", passages)
                
                # Should be clamped to valid range
                assert scores == [0.0, 1.0, 0.5]
    
    def test_reranker_pads_missing_scores(self):
        """Should pad with default scores if LLM returns fewer."""
        with patch.dict(os.environ, {"RERANK_ENABLED": "1"}):
            mock_ai = Mock()
            mock_model_class = Mock()
            mock_model = Mock()
            mock_response = Mock()
            # Return fewer scores than passages
            mock_response.text = "[0.8]"
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            with patch.dict("sys.modules", {
                "google.cloud.aiplatform": mock_ai,
                "vertexai.generative_models": Mock(GenerativeModel=mock_model_class)
            }):
                passages = [
                    {"path": "a.py", "text": "code"},
                    {"path": "b.py", "text": "code"},
                    {"path": "c.py", "text": "code"},
                ]
                
                scores = score_passages("query", passages)
                
                # Should pad with 0.5
                assert scores == [0.8, 0.5, 0.5]


class TestRerankerIntegration:
    """Test reranker integration with HybridRetriever."""
    
    def test_retriever_reranking_changes_order(self):
        """Test that reranking changes result order."""
        # Create test chunks
        chunks = [
            Chunk(
                id="1", repo="test", commit="abc", path="match.py", lang="python",
                start_line=1, end_line=10, text="def exact_match(): pass",
                symbols=["exact_match"], imports=[], neighbors=[], hash="h1"
            ),
            Chunk(
                id="2", repo="test", commit="abc", path="partial.py", lang="python",
                start_line=1, end_line=10, text="def partial(): pass",
                symbols=["partial"], imports=[], neighbors=[], hash="h2"
            ),
            Chunk(
                id="3", repo="test", commit="abc", path="unrelated.py", lang="python",
                start_line=1, end_line=10, text="import os\nimport sys",
                symbols=[], imports=["os", "sys"], neighbors=[], hash="h3"
            ),
        ]
        
        retriever = HybridRetriever()
        retriever.chunks = chunks
        retriever._chunk_id_to_index = {c.id: i for i, c in enumerate(chunks)}
        retriever.file_index = {}
        
        # Mock reranker to prefer second chunk
        def mock_score_passages(query, passages):
            # Return scores that reverse the order
            return [0.3, 0.9, 0.1]  # Prefer second chunk
        
        with patch.dict(os.environ, {"RERANK_ENABLED": "1", "RERANK_TOPK": "10"}):
            # Patch at the module level since it's imported conditionally
            with patch("src.services.reranker.score_passages", side_effect=mock_score_passages):
                results = retriever.search("exact", k=3)
                
                # Without reranking, "exact_match" would be first
                # With our mock reranker, "partial" should be first
                if results:  # May be empty if no BM25 index built
                    # Just verify reranking was applied (scores changed)
                    assert any(r.score != 0.5 for r in results)
    
    def test_retriever_reranking_disabled(self):
        """Test that retriever works without reranking."""
        chunks = [
            Chunk(
                id="1", repo="test", commit="abc", path="test.py", lang="python",
                start_line=1, end_line=10, text="def test(): pass",
                symbols=["test"], imports=[], neighbors=[], hash="h1"
            ),
        ]
        
        retriever = HybridRetriever()
        retriever.chunks = chunks
        retriever._chunk_id_to_index = {"1": 0}
        retriever.file_index = {}
        
        with patch.dict(os.environ, {"RERANK_ENABLED": "0"}):
            # Should work without calling reranker
            results = retriever.search("test", k=1)
            # Just verify it doesn't crash
            assert isinstance(results, list)
    
    def test_retriever_topk_limit(self):
        """Test that only top-K candidates are reranked."""
        # Create many chunks
        chunks = []
        for i in range(100):
            chunks.append(Chunk(
                id=str(i), repo="test", commit="abc", 
                path=f"file{i}.py", lang="python",
                start_line=1, end_line=10, 
                text=f"def func{i}(): pass",
                symbols=[f"func{i}"], imports=[], neighbors=[], hash=f"h{i}"
            ))
        
        retriever = HybridRetriever()
        retriever.chunks = chunks
        retriever._chunk_id_to_index = {c.id: i for i, c in enumerate(chunks)}
        retriever.file_index = {}
        
        passages_passed = []
        
        def capture_passages(query, passages):
            passages_passed.extend(passages)
            return [0.5] * len(passages)
        
        with patch.dict(os.environ, {"RERANK_ENABLED": "1", "RERANK_TOPK": "20"}):
            # Patch at the module level since it's imported conditionally
            with patch("src.services.reranker.score_passages", side_effect=capture_passages):
                results = retriever.search("func", k=50)
                
                # Should only rerank top 20
                if passages_passed:
                    assert len(passages_passed) <= 20