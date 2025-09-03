"""Tests for hybrid retrieval system."""

import pytest
from unittest.mock import Mock, MagicMock
import numpy as np

from src.tools.retrieval import HybridRetriever
from src.core.types import Chunk, RetrievalResult


class TestHybridRetriever:
    """Test cases for HybridRetriever."""
    
    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        return [
            Chunk(
                id="chunk_1",
                repo="test_repo",
                commit="abc123",
                path="src/utils.py",
                lang="python",
                start_line=1,
                end_line=20,
                text="def calculate_sum(a, b):\n    return a + b\n\nclass Calculator:\n    def add(self, x, y):\n        return x + y",
                symbols=["calculate_sum", "Calculator", "add"],
                imports=["math"],
                neighbors=["chunk_2"],
                hash="hash1"
            ),
            Chunk(
                id="chunk_2", 
                repo="test_repo",
                commit="abc123",
                path="src/math_ops.py",
                lang="python",
                start_line=1,
                end_line=15,
                text="def multiply(x, y):\n    return x * y\n\ndef divide(x, y):\n    if y != 0:\n        return x / y\n    return None",
                symbols=["multiply", "divide"],
                imports=["sys"],
                neighbors=["chunk_1", "chunk_3"],
                hash="hash2"
            ),
            Chunk(
                id="chunk_3",
                repo="test_repo", 
                commit="abc123",
                path="src/advanced.py",
                lang="python",
                start_line=1,
                end_line=25,
                text="import math\n\ndef square_root(n):\n    return math.sqrt(n)\n\nclass AdvancedCalculator:\n    def power(self, base, exp):\n        return base ** exp",
                symbols=["square_root", "AdvancedCalculator", "power"],
                imports=["math"],
                neighbors=["chunk_2"],
                hash="hash3"
            )
        ]
    
    @pytest.fixture
    def sample_vectors(self):
        """Create sample embedding vectors."""
        return [
            [0.1, 0.2, 0.3, 0.4, 0.5],  # chunk_1
            [0.2, 0.3, 0.4, 0.5, 0.6],  # chunk_2
            [0.3, 0.4, 0.5, 0.6, 0.7],  # chunk_3
        ]
    
    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings tool."""
        mock = Mock()
        mock.get_embeddings.return_value = [[0.15, 0.25, 0.35, 0.45, 0.55]]
        return mock
    
    @pytest.fixture
    def retriever(self, mock_embeddings):
        """Create retriever instance."""
        return HybridRetriever(embeddings_tool=mock_embeddings)
    
    def test_init(self):
        """Test retriever initialization."""
        embeddings = Mock()
        vector_search = Mock()
        retriever = HybridRetriever(embeddings, vector_search)
        
        assert retriever.embeddings is embeddings
        assert retriever.vector_search is vector_search
        assert retriever.bm25_index is None
        assert retriever.chunks == []
        assert retriever.vectors == []
        assert retriever._chunk_id_to_index == {}
    
    def test_bm25_index_chunks(self, retriever, sample_chunks):
        """Test BM25 indexing of chunks."""
        retriever.bm25_index_chunks(sample_chunks)
        
        assert len(retriever.chunks) == 3
        assert retriever.bm25_index is not None
        assert len(retriever._chunk_id_to_index) == 3
        assert retriever._chunk_id_to_index["chunk_1"] == 0
        assert retriever._chunk_id_to_index["chunk_2"] == 1
        assert retriever._chunk_id_to_index["chunk_3"] == 2
    
    def test_ann_index(self, retriever, sample_vectors):
        """Test ANN indexing of vectors."""
        retriever.ann_index(sample_vectors)
        
        assert len(retriever.vectors) == 3
        assert retriever.vectors == sample_vectors
    
    def test_index_chunks(self, retriever, sample_chunks, sample_vectors):
        """Test indexing chunks with vectors."""
        retriever.index_chunks(sample_chunks, sample_vectors)
        
        assert len(retriever.chunks) == 3
        assert len(retriever.vectors) == 3
        assert retriever.bm25_index is not None
    
    def test_bm25_search(self, retriever, sample_chunks):
        """Test BM25-only search."""
        retriever.bm25_index_chunks(sample_chunks)
        
        results = retriever.search("calculator sum", k=5, mode="bm25")
        
        assert isinstance(results, list)
        assert len(results) <= 5
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert result.score > 0
            assert result.chunk_id in ["chunk_1", "chunk_2", "chunk_3"]
    
    def test_vector_search(self, retriever, sample_chunks, sample_vectors):
        """Test vector-only search."""
        retriever.index_chunks(sample_chunks, sample_vectors)
        
        results = retriever.search("mathematical operations", k=3, mode="vector")
        
        assert isinstance(results, list)
        assert len(results) <= 3
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert result.score >= 0.1  # Threshold
    
    def test_hybrid_search(self, retriever, sample_chunks, sample_vectors):
        """Test hybrid search with RRF."""
        retriever.index_chunks(sample_chunks, sample_vectors)
        
        results = retriever.search("calculator", k=3, mode="hybrid")
        
        assert isinstance(results, list)
        assert len(results) <= 3
        for result in results:
            assert isinstance(result, RetrievalResult)
            assert result.score > 0
    
    def test_search_no_chunks(self, retriever):
        """Test search with no indexed chunks."""
        results = retriever.search("test query", k=5)
        assert results == []
    
    def test_search_different_modes(self, retriever, sample_chunks, sample_vectors):
        """Test search with different modes."""
        retriever.index_chunks(sample_chunks, sample_vectors)
        
        # Test all modes
        bm25_results = retriever.search("calculator", mode="bm25")
        vector_results = retriever.search("calculator", mode="vector")
        hybrid_results = retriever.search("calculator", mode="hybrid")
        
        assert isinstance(bm25_results, list)
        assert isinstance(vector_results, list)
        assert isinstance(hybrid_results, list)
    
    def test_reciprocal_rank_fusion(self, retriever, sample_chunks):
        """Test reciprocal rank fusion merging."""
        # Create mock results
        ann_results = [
            RetrievalResult(chunk_id="chunk_1", path="path1", score=0.9, neighbors=[]),
            RetrievalResult(chunk_id="chunk_2", path="path2", score=0.8, neighbors=[]),
        ]
        
        bm25_results = [
            RetrievalResult(chunk_id="chunk_2", path="path2", score=5.0, neighbors=[]),
            RetrievalResult(chunk_id="chunk_3", path="path3", score=3.0, neighbors=[]),
        ]
        
        merged = retriever.reciprocal_rank_fusion(ann_results, bm25_results, k=60)
        
        assert len(merged) == 3  # chunk_1, chunk_2, chunk_3
        assert merged[0].chunk_id == "chunk_2"  # Should be highest due to appearing in both
    
    def test_expand_with_neighbors(self, retriever, sample_chunks):
        """Test neighbor expansion."""
        retriever.bm25_index_chunks(sample_chunks)
        
        # Create initial results
        initial_results = [
            RetrievalResult(chunk_id="chunk_1", path="path1", score=0.9, neighbors=["chunk_2"])
        ]
        
        expanded = retriever._expand_with_neighbors(initial_results, target_k=5)
        
        # Should include original result plus neighbors
        assert len(expanded) >= len(initial_results)
        chunk_ids = [r.chunk_id for r in expanded]
        assert "chunk_1" in chunk_ids
        assert "chunk_2" in chunk_ids  # neighbor should be added
    
    def test_tokenize(self, retriever):
        """Test text tokenization."""
        text = "Hello World! This is a test-case with numbers123."
        tokens = retriever._tokenize(text)
        
        expected = ["hello", "world", "this", "is", "a", "test", "case", "with", "numbers123"]
        assert tokens == expected
    
    def test_cosine_similarity(self, retriever):
        """Test cosine similarity calculation."""
        vec1 = [1, 0, 0]
        vec2 = [0, 1, 0]
        vec3 = [1, 0, 0]
        
        # Orthogonal vectors should have 0 similarity
        sim1 = retriever._cosine_similarity(vec1, vec2)
        assert abs(sim1 - 0.0) < 1e-6
        
        # Identical vectors should have 1.0 similarity
        sim2 = retriever._cosine_similarity(vec1, vec3)
        assert abs(sim2 - 1.0) < 1e-6
        
        # Empty vectors should return 0
        sim3 = retriever._cosine_similarity([], [1, 2, 3])
        assert sim3 == 0.0
        
        # Zero vectors should return 0
        sim4 = retriever._cosine_similarity([0, 0, 0], [1, 2, 3])
        assert sim4 == 0.0
    
    def test_get_snippet(self, retriever):
        """Test snippet generation."""
        text = "This is a long text that contains calculator functions and other code."
        query = "calculator"
        
        snippet = retriever._get_snippet(text, query)
        
        assert len(snippet) <= 200
        assert "calculator" in snippet.lower()
    
    def test_get_snippet_no_match(self, retriever):
        """Test snippet generation when query doesn't match."""
        text = "This is some text without the search term."
        query = "nonexistent"
        
        snippet = retriever._get_snippet(text, query)
        
        # Should return beginning of text
        assert snippet.startswith("This is some text")
    
    def test_search_with_neighbor_expansion(self, retriever, sample_chunks, sample_vectors):
        """Test search with neighbor expansion enabled/disabled."""
        retriever.index_chunks(sample_chunks, sample_vectors)
        
        results_no_expand = retriever.search("calculator", k=2, expand_neighbors=False)
        results_with_expand = retriever.search("calculator", k=2, expand_neighbors=True)
        
        # With expansion should potentially have more results
        assert len(results_with_expand) >= len(results_no_expand)
    
    def test_vector_search_no_embeddings(self, sample_chunks, sample_vectors):
        """Test vector search without embeddings tool."""
        retriever = HybridRetriever(embeddings_tool=None)
        retriever.index_chunks(sample_chunks, sample_vectors)
        
        results = retriever.search("test", mode="vector")
        assert results == []
    
    def test_vector_search_embedding_error(self, retriever, sample_chunks, sample_vectors):
        """Test vector search when embedding fails."""
        retriever.index_chunks(sample_chunks, sample_vectors)
        retriever.embeddings.get_embeddings.side_effect = Exception("Embedding failed")
        
        results = retriever.search("test", mode="vector")
        assert results == []
    
    def test_rrf_with_empty_lists(self, retriever):
        """Test RRF with empty result lists."""
        merged = retriever.reciprocal_rank_fusion([], [], k=60)
        assert merged == []
    
    def test_rrf_with_one_empty_list(self, retriever):
        """Test RRF with one empty result list."""
        ann_results = [
            RetrievalResult(chunk_id="chunk_1", path="path1", score=0.9, neighbors=[])
        ]
        
        merged = retriever.reciprocal_rank_fusion(ann_results, [], k=60)
        assert len(merged) == 1
        assert merged[0].chunk_id == "chunk_1"
    
    def test_neighbor_expansion_no_neighbors(self, retriever, sample_chunks):
        """Test neighbor expansion when chunks have no neighbors."""
        # Modify chunks to have no neighbors
        chunks_no_neighbors = []
        for chunk in sample_chunks:
            chunk_copy = chunk.model_copy()
            chunk_copy.neighbors = []
            chunks_no_neighbors.append(chunk_copy)
        
        retriever.bm25_index_chunks(chunks_no_neighbors)
        
        initial_results = [
            RetrievalResult(chunk_id="chunk_1", path="path1", score=0.9, neighbors=[])
        ]
        
        expanded = retriever._expand_with_neighbors(initial_results, target_k=5)
        
        # Should only have original results
        assert len(expanded) == len(initial_results)


class TestRetrievalResultIntegration:
    """Integration tests for retrieval results."""
    
    def test_end_to_end_search(self):
        """Test complete search workflow."""
        # Create sample data
        chunks = [
            Chunk(
                id="test_1",
                repo="repo",
                commit="commit1",
                path="file1.py",
                lang="python",
                start_line=1,
                end_line=10,
                text="def function_one():\n    pass",
                symbols=["function_one"],
                imports=[],
                neighbors=[],
                hash="hash1"
            ),
            Chunk(
                id="test_2",
                repo="repo", 
                commit="commit1",
                path="file2.py",
                lang="python",
                start_line=1,
                end_line=10,
                text="class MyClass:\n    def method_two(self):\n        pass",
                symbols=["MyClass", "method_two"],
                imports=[],
                neighbors=[],
                hash="hash2"
            )
        ]
        
        # Setup retriever
        mock_embeddings = Mock()
        mock_embeddings.get_embeddings.return_value = [[0.1, 0.2, 0.3]]
        
        retriever = HybridRetriever(mock_embeddings)
        
        # Index with vectors
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        retriever.index_chunks(chunks, vectors)
        
        # Search
        results = retriever.search("function", k=2)
        
        # Verify results
        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert all(r.chunk_id in ["test_1", "test_2"] for r in results)
        assert all(r.score > 0 for r in results)