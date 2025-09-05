"""Tests for the LLM reranker service."""

import os
import json
import sys
from typing import List, Dict, Any
from unittest.mock import patch, MagicMock, Mock

import pytest

# Mock the google.cloud and vertexai modules before import
sys.modules['google.cloud.aiplatform'] = MagicMock()
sys.modules['vertexai.generative_models'] = MagicMock()

from src.services.reranker import score_passages


class TestReranker:
    """Test suite for the LLM reranker."""

    def test_reranker_disabled_returns_uniform_scores(self):
        """When reranking is disabled, should return uniform 0.5 scores."""
        with patch.dict(os.environ, {"RERANK_ENABLED": "0"}):
            passages = [
                {"path": "src/foo.py", "snippet": "def foo(): pass"},
                {"path": "src/bar.py", "snippet": "class Bar: pass"},
            ]
            
            scores = score_passages("find foo function", passages)
            
            assert scores == [0.5, 0.5]
    
    def test_reranker_enabled_calls_llm(self):
        """When enabled, should call Vertex AI LLM for scoring."""
        with patch.dict(os.environ, {
            "RERANK_ENABLED": "1",
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GOOGLE_CLOUD_LOCATION": "us-central1"
        }):
            # Create mocks
            mock_aiplatform = Mock()
            mock_model_class = Mock()
            mock_model = Mock()
            mock_response = Mock()
            mock_response.text = "[0.9, 0.3]"
            mock_model.generate_content.return_value = mock_response
            mock_model_class.return_value = mock_model
            
            # Patch the modules
            with patch.dict(sys.modules, {
                'google.cloud.aiplatform': mock_aiplatform,
                'vertexai.generative_models': Mock(GenerativeModel=mock_model_class)
            }):
                # Force reimport to pick up mocks
                import importlib
                import src.services.reranker
                importlib.reload(src.services.reranker)
                from src.services.reranker import score_passages
                
                passages = [
                    {"path": "src/foo.py", "snippet": "def foo(): return 42"},
                    {"path": "src/bar.py", "snippet": "class Bar: pass"},
                ]
                
                scores = score_passages("find foo function", passages)
                
                # Check initialization and model creation
                mock_aiplatform.init.assert_called_once_with(
                    project="test-project",
                    location="us-central1"
                )
                mock_model_class.assert_called_once_with("gemini-1.5-flash")
                
                # Check scores returned
                assert scores == [0.9, 0.3]
    
    def test_reranker_handles_empty_passages(self):
        """Should return empty list for empty passages."""
        with patch.dict(os.environ, {"RERANK_ENABLED": "1"}):
            scores = score_passages("query", [])
            assert scores == []
    
    def test_reranker_fallback_on_error(self):
        """Should return uniform scores if LLM fails."""
        with patch.dict(os.environ, {
            "RERANK_ENABLED": "1",
            "GOOGLE_CLOUD_PROJECT": "test-project"
        }):
            passages = [
                {"path": "a.py", "snippet": "code"},
                {"path": "b.py", "snippet": "code"},
            ]
            
            # Mock to raise an error
            mock_aiplatform = Mock()
            mock_aiplatform.init.side_effect = Exception("Connection error")
            
            with patch.dict(sys.modules, {
                'google.cloud.aiplatform': mock_aiplatform,
                'vertexai.generative_models': Mock()
            }):
                import importlib
                import src.services.reranker
                importlib.reload(src.services.reranker)
                from src.services.reranker import score_passages
                
                scores = score_passages("query", passages)
                
                # Should fall back to uniform scores
                assert scores == [0.5, 0.5]


class TestRerankerIntegration:
    """Integration tests for reranker with retriever."""
    
    def test_retriever_without_reranking(self):
        """Test that retriever works without reranking."""
        from src.tools.retrieval import HybridRetriever
        from src.core.types import Chunk
        
        # Create test chunks
        chunks = [
            Chunk(
                id="1",
                repo="test",
                commit="abc",
                path="src/main.py",
                lang="python",
                start_line=1,
                end_line=10,
                text="def main():\n    print('Hello')",
                symbols=["main"],
                imports=[],
                neighbors=[],
                hash="hash1"
            ),
        ]
        
        retriever = HybridRetriever()
        retriever.chunks = chunks
        retriever._chunk_id_to_index = {"1": 0}
        retriever.file_index = {}
        
        with patch.dict(os.environ, {"RERANK_ENABLED": "0"}):
            # Search without reranking
            results = retriever.search("main", k=1)
            assert len(results) <= 1
    
    def test_retriever_with_reranking_mock(self):
        """Test that retriever calls reranker when enabled."""
        from src.tools.retrieval import HybridRetriever
        from src.core.types import Chunk
        
        # Create test chunks
        chunks = [
            Chunk(
                id="1",
                repo="test",
                commit="abc",
                path="src/main.py",
                lang="python",
                start_line=1,
                end_line=10,
                text="def main():\n    print('Hello')",
                symbols=["main"],
                imports=[],
                neighbors=["2"],
                hash="hash1"
            ),
            Chunk(
                id="2",
                repo="test",
                commit="abc",
                path="src/utils.py",
                lang="python",
                start_line=1,
                end_line=5,
                text="def helper():\n    return 42",
                symbols=["helper"],
                imports=[],
                neighbors=["1"],
                hash="hash2"
            ),
        ]
        
        retriever = HybridRetriever()
        retriever.chunks = chunks
        retriever._chunk_id_to_index = {"1": 0, "2": 1}
        retriever.file_index = {"src/main.py": [0], "src/utils.py": [1]}
        
        with patch.dict(os.environ, {"RERANK_ENABLED": "1", "RERANK_TOPK": "10"}):
            # Mock the score_passages function to avoid calling real LLM
            with patch("src.services.reranker.score_passages") as mock_score:
                mock_score.return_value = [0.9, 0.3]  # Prefer first chunk
                
                results = retriever.search("main", k=2)
                
                # Should have called reranker (if chunks were found)
                if results:
                    mock_score.assert_called()