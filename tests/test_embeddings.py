"""Tests for embeddings functionality."""

import pytest
from unittest.mock import Mock, patch
import numpy as np
from typing import List

from src.tools.embeddings import (
    embed_texts, 
    embed_query, 
    NotConfiguredError,
    _truncate_text
)


class MockEmbedding:
    """Mock embedding object returned by Vertex AI."""
    def __init__(self, values: List[float]):
        self.values = values


class TestEmbeddings:
    """Test suite for embeddings functionality."""

    def test_not_configured_error_no_project(self):
        """Test that NotConfiguredError is raised when GOOGLE_CLOUD_PROJECT is not set."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(NotConfiguredError, match="GOOGLE_CLOUD_PROJECT"):
                embed_texts(["test text"])

    @patch('src.tools.embeddings._get_vertex_client')
    def test_embed_texts_empty_list(self, mock_client):
        """Test embedding empty list returns empty result."""
        result = embed_texts([])
        assert result == []
        mock_client.assert_not_called()

    @patch('src.tools.embeddings._get_vertex_client')
    def test_embed_texts_single_text(self, mock_client):
        """Test embedding single text."""
        # Mock the vertex client and embeddings
        mock_model = Mock()
        mock_embedding = MockEmbedding([0.1, 0.2, 0.3])
        mock_model.get_embeddings.return_value = [mock_embedding]
        mock_client.return_value = mock_model
        
        result = embed_texts(["test text"], dim=1536)
        
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
        mock_model.get_embeddings.assert_called_once_with(
            ["test text"],
            output_dimensionality=1536
        )

    @patch('src.tools.embeddings._get_vertex_client')
    def test_embed_texts_multiple_texts(self, mock_client):
        """Test embedding multiple texts preserves order."""
        mock_model = Mock()
        mock_embeddings = [
            MockEmbedding([0.1, 0.2, 0.3]),
            MockEmbedding([0.4, 0.5, 0.6])
        ]
        mock_model.get_embeddings.return_value = mock_embeddings
        mock_client.return_value = mock_model
        
        texts = ["first text", "second text"]
        result = embed_texts(texts, dim=1536)
        
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

    @patch('src.tools.embeddings._get_vertex_client')
    def test_embed_query_wrapper(self, mock_client):
        """Test embed_query is a proper wrapper for embed_texts."""
        mock_model = Mock()
        mock_embedding = MockEmbedding([0.7, 0.8, 0.9])
        mock_model.get_embeddings.return_value = [mock_embedding]
        mock_client.return_value = mock_model
        
        result = embed_query("test query", dim=1536)
        
        assert result == [0.7, 0.8, 0.9]
        mock_model.get_embeddings.assert_called_once_with(
            ["test query"],
            output_dimensionality=1536
        )

    def test_cosine_similarity_same_text(self):
        """Test that same text has high cosine similarity (>= 0.98)."""
        # Create deterministic mock embeddings for same text
        same_embedding = [0.5, 0.5, 0.7071]  # normalized vector
        
        with patch('src.tools.embeddings._get_vertex_client') as mock_client:
            mock_model = Mock()
            mock_embedding = MockEmbedding(same_embedding)
            mock_model.get_embeddings.return_value = [mock_embedding]
            mock_client.return_value = mock_model
            
            # Get embeddings for same text twice
            emb1 = embed_query("same text")
            emb2 = embed_query("same text")
            
            # Calculate cosine similarity
            cos_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            assert cos_sim >= 0.98

    def test_cosine_similarity_different_texts(self):
        """Test that different texts have lower cosine similarity (< 0.9)."""
        # Create mock embeddings for different texts
        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [0.0, 1.0, 0.0]  # orthogonal vectors
        
        with patch('src.tools.embeddings._get_vertex_client') as mock_client:
            mock_model = Mock()
            
            # Set up different return values for different calls
            def side_effect(texts, **kwargs):
                if texts == ["text one"]:
                    return [MockEmbedding(embedding1)]
                elif texts == ["text two"]:
                    return [MockEmbedding(embedding2)]
                
            mock_model.get_embeddings.side_effect = side_effect
            mock_client.return_value = mock_model
            
            emb1 = embed_query("text one")
            emb2 = embed_query("text two")
            
            # Calculate cosine similarity
            cos_sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            assert cos_sim < 0.9

    @patch('src.tools.embeddings._get_vertex_client')
    def test_batch_size_variance(self, mock_client):
        """Test that different batch sizes return aligned shapes."""
        mock_model = Mock()
        
        # Mock responses for single and batch calls
        single_embedding = MockEmbedding([0.1, 0.2, 0.3])
        batch_embeddings = [
            MockEmbedding([0.1, 0.2, 0.3]),
            MockEmbedding([0.4, 0.5, 0.6]),
            MockEmbedding([0.7, 0.8, 0.9])
        ]
        
        def mock_get_embeddings(texts, **kwargs):
            if len(texts) == 1:
                return [single_embedding]
            else:
                return batch_embeddings[:len(texts)]
        
        mock_model.get_embeddings.side_effect = mock_get_embeddings
        mock_client.return_value = mock_model
        
        # Test single embedding
        result_single = embed_texts(["single text"])
        assert len(result_single) == 1
        assert len(result_single[0]) == 3
        
        # Test batch of 3
        result_batch = embed_texts(["text 1", "text 2", "text 3"])
        assert len(result_batch) == 3
        assert all(len(emb) == 3 for emb in result_batch)

    def test_invalid_dimensionality(self):
        """Test that invalid dimensionality raises ValueError."""
        with pytest.raises(ValueError, match="Invalid dimensionality"):
            embed_texts(["test"], dim=999)

    def test_text_truncation(self):
        """Test text truncation functionality."""
        # Test normal text (no truncation needed)
        short_text = "This is a short text"
        assert _truncate_text(short_text, max_chars=100) == short_text
        
        # Test long text that needs truncation
        long_text = "word " * 2000  # Creates text longer than default limit
        truncated = _truncate_text(long_text, max_chars=50)
        
        assert len(truncated) <= 50
        assert not truncated.endswith(" ")  # Should not end with partial word
        assert truncated in long_text  # Should be a prefix

    @patch('src.tools.embeddings._get_vertex_client')
    @patch('src.tools.embeddings.time.sleep')
    def test_retry_logic_retryable_error(self, mock_sleep, mock_client):
        """Test retry logic for retryable errors."""
        mock_model = Mock()
        
        # First call fails with 429, second succeeds
        mock_embedding = MockEmbedding([0.1, 0.2, 0.3])
        mock_model.get_embeddings.side_effect = [
            Exception("429 Too Many Requests"),
            [mock_embedding]
        ]
        mock_client.return_value = mock_model
        
        result = embed_texts(["test text"])
        
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
        assert mock_model.get_embeddings.call_count == 2
        mock_sleep.assert_called_once()  # Should have slept for retry

    @patch('src.tools.embeddings._get_vertex_client')
    def test_non_retryable_error(self, mock_client):
        """Test that non-retryable errors are raised immediately."""
        mock_model = Mock()
        mock_model.get_embeddings.side_effect = Exception("400 Bad Request")
        mock_client.return_value = mock_model
        
        with pytest.raises(Exception, match="400 Bad Request"):
            embed_texts(["test text"])
        
        # Should only try once for non-retryable error
        assert mock_model.get_embeddings.call_count == 1

    @patch('src.tools.embeddings._get_vertex_client')
    @patch('src.tools.embeddings.time.sleep')
    def test_max_retries_exceeded(self, mock_sleep, mock_client):
        """Test behavior when max retries is exceeded."""
        mock_model = Mock()
        mock_model.get_embeddings.side_effect = Exception("503 Service Unavailable")
        mock_client.return_value = mock_model
        
        with pytest.raises(Exception, match="503 Service Unavailable"):
            embed_texts(["test text"])
        
        # Should try max_retries times (5)
        assert mock_model.get_embeddings.call_count == 5
        assert mock_sleep.call_count == 4  # Sleep between retries