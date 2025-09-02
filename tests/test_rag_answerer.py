"""Tests for RAG Answerer agent."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from src.agents.rag_answerer import RAGAnswerer
from src.core.types import Chunk, CodeMap, RAGResponse, RetrievalResult
from src.tools.retrieval import HybridRetriever
from src.services.vertex_models import ModelRouter


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing."""
    return [
        Chunk(
            id="chunk_1",
            repo="test-repo",
            commit="abc123",
            path="src/main.py",
            lang="python",
            start_line=1,
            end_line=10,
            text="def main():\n    print('Hello, World!')\n    return 0",
            symbols=["main"],
            imports=["sys"],
            neighbors=["chunk_2"],
            hash="hash1"
        ),
        Chunk(
            id="chunk_2", 
            repo="test-repo",
            commit="abc123",
            path="src/utils.py",
            lang="python",
            start_line=1,
            end_line=15,
            text="def helper_function():\n    return 42\n\nclass Helper:\n    pass",
            symbols=["helper_function", "Helper"],
            imports=["os", "sys"],
            neighbors=["chunk_1"],
            hash="hash2"
        ),
        Chunk(
            id="chunk_3",
            repo="test-repo", 
            commit="abc123",
            path="src/config.py",
            lang="python",
            start_line=1,
            end_line=5,
            text="CONFIG = {\n    'debug': True\n}",
            symbols=["CONFIG"],
            imports=[],
            neighbors=[],
            hash="hash3"
        )
    ]


@pytest.fixture
def sample_retrieval_results():
    """Sample retrieval results for testing."""
    return [
        RetrievalResult(
            chunk_id="chunk_1",
            path="src/main.py",
            score=0.95,
            neighbors=["chunk_2"],
            snippet="def main():"
        ),
        RetrievalResult(
            chunk_id="chunk_2",
            path="src/utils.py", 
            score=0.80,
            neighbors=["chunk_1"],
            snippet="def helper_function():"
        )
    ]


@pytest.fixture
def sample_code_map():
    """Sample code map for testing."""
    return CodeMap(
        repo="test-repo",
        commit="abc123",
        files=["src/main.py", "src/utils.py", "src/config.py"],
        deps={
            "src/main.py": ["src/utils.py", "src/config.py"],
            "src/utils.py": ["src/config.py"],
            "src/config.py": []
        },
        symbol_index={
            "main": ["src/main.py"],
            "helper_function": ["src/utils.py"],
            "Helper": ["src/utils.py"],
            "CONFIG": ["src/config.py"]
        }
    )


@pytest.fixture
def mock_retriever(sample_chunks, sample_retrieval_results):
    """Mock hybrid retriever."""
    retriever = Mock(spec=HybridRetriever)
    retriever.chunks = sample_chunks
    retriever.search.return_value = sample_retrieval_results
    return retriever


@pytest.fixture
def mock_model_router():
    """Mock model router."""
    router = Mock(spec=ModelRouter)
    
    # Mock models
    fast_model = Mock()
    deep_model = Mock()
    long_context_model = Mock()
    
    router.llm_fast.return_value = fast_model
    router.llm_deep.return_value = deep_model 
    router.llm_long_context.return_value = long_context_model
    
    # Mock async generation
    router.generate_content = AsyncMock(return_value="Generated answer")
    
    return router


@pytest.fixture
def rag_answerer(mock_retriever, mock_model_router):
    """RAG answerer instance for testing."""
    return RAGAnswerer(mock_retriever, mock_model_router)


class TestRAGAnswerer:
    """Test RAG Answerer functionality."""
    
    @pytest.mark.asyncio
    async def test_answer_basic(self, rag_answerer, mock_retriever, mock_model_router):
        """Test basic answer generation."""
        query = "How does the main function work?"
        
        response = await rag_answerer.answer(query)
        
        # Verify retrieval was called
        mock_retriever.search.assert_called_once_with(query, k=12, expand_neighbors=False)
        
        # Verify response structure
        assert isinstance(response, RAGResponse)
        assert response.answer == "Generated answer"
        assert len(response.sources) > 0
        assert response.token_count > 0
        assert len(response.chunks_used) > 0
        assert response.model_used in ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-pro-long-context"]
        
        # Verify model generation was called
        mock_model_router.generate_content.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_answer_with_code_map(self, rag_answerer, sample_code_map, mock_retriever):
        """Test answer generation with code map neighbor expansion."""
        query = "How are functions organized?"
        
        response = await rag_answerer.answer(query, code_map=sample_code_map)
        
        # Verify neighbor expansion was enabled
        mock_retriever.search.assert_called_once_with(query, k=12, expand_neighbors=True)
        
        assert isinstance(response, RAGResponse)
        assert len(response.sources) > 0
        
    @pytest.mark.asyncio
    async def test_answer_no_results(self, rag_answerer, mock_retriever):
        """Test handling when no retrieval results found."""
        mock_retriever.search.return_value = []
        
        response = await rag_answerer.answer("What is this?")
        
        assert "couldn't find relevant information" in response.answer
        assert response.sources == []
        assert response.token_count == 0
        assert response.chunks_used == []
        assert response.model_used == "none"
        
    @pytest.mark.asyncio
    async def test_model_selection_by_token_count(self, rag_answerer, mock_model_router):
        """Test model selection based on token count."""
        # Test with small content (should use fast model)
        query = "Simple question"
        
        response = await rag_answerer.answer(query)
        
        # Should use fast model for small token count
        mock_model_router.llm_fast.assert_called()
        assert response.model_used == "gemini-2.0-flash"
        
    @pytest.mark.asyncio
    async def test_model_selection_large_context(self, rag_answerer, mock_model_router, mock_retriever):
        """Test model selection for large context."""
        # Create large retrieval results that will trigger deep model
        large_chunk = Chunk(
            id="large_chunk",
            repo="test-repo",
            commit="abc123", 
            path="src/large.py",
            lang="python",
            start_line=1,
            end_line=1000,
            text="# Very large code chunk\n" + "def function():\n    pass\n" * 2000,  # Large content
            symbols=["function"] * 100,
            imports=["module"] * 50,
            neighbors=[],
            hash="large_hash"
        )
        
        # Mock retriever to return large chunks
        mock_retriever.chunks = [large_chunk] * 5
        large_results = [
            RetrievalResult(
                chunk_id="large_chunk",
                path="src/large.py",
                score=0.95,
                neighbors=[],
                snippet="def function():"
            )
        ] * 5
        mock_retriever.search.return_value = large_results
        
        response = await rag_answerer.answer("Complex question")
        
        # Should use deep or long-context model for large content
        assert response.model_used in ["gemini-1.5-pro", "gemini-1.5-pro-long-context"]
        
    @pytest.mark.asyncio
    async def test_generate_docs(self, rag_answerer, sample_chunks, mock_model_router):
        """Test documentation generation."""
        topic = "Main Module"
        
        docs = await rag_answerer.generate_docs(topic, sample_chunks)
        
        # Verify deep model was used for docs
        mock_model_router.llm_deep.assert_called()
        mock_model_router.generate_content.assert_called()
        
        # Verify docs were generated
        assert isinstance(docs, str)
        assert docs == "Generated answer"  # Mocked response
        
    @pytest.mark.asyncio
    async def test_generate_docs_no_chunks(self, rag_answerer):
        """Test documentation generation with no chunks."""
        topic = "Empty Module"
        
        docs = await rag_answerer.generate_docs(topic, [])
        
        assert topic in docs
        assert "No relevant code found" in docs
        
    @pytest.mark.asyncio
    async def test_error_handling(self, rag_answerer, mock_model_router):
        """Test error handling during generation."""
        mock_model_router.generate_content.side_effect = Exception("API Error")
        
        response = await rag_answerer.answer("Test query")
        
        assert "error while generating" in response.answer
        assert "API Error" in response.answer
        
    def test_doc_pack_assembly(self, rag_answerer, sample_chunks):
        """Test document pack assembly."""
        query = "How does it work?"
        
        doc_pack = rag_answerer._assemble_doc_pack(sample_chunks, query)
        
        # Verify document structure
        assert "Relevant Code Context" in doc_pack
        assert query in doc_pack
        assert "File: src/main.py" in doc_pack
        assert "File: src/utils.py" in doc_pack
        assert "Lines 1-10" in doc_pack
        assert "**Symbols:** main" in doc_pack  # Updated format
        assert "**Imports:** sys" in doc_pack  # Updated format
        assert "```python" in doc_pack
        assert "def main():" in doc_pack
        
    def test_doc_pack_assembly_for_docs(self, rag_answerer, sample_chunks):
        """Test document pack assembly for documentation."""
        topic = "API Documentation"
        
        doc_pack = rag_answerer._assemble_doc_pack(sample_chunks, topic, for_docs=True)
        
        # Verify documentation-specific formatting
        assert f"Code Context for: {topic}" in doc_pack
        assert "File: src/main.py" in doc_pack
        
    def test_neighbor_expansion(self, rag_answerer, sample_code_map, sample_retrieval_results):
        """Test neighbor expansion with code map."""
        expanded = rag_answerer._expand_with_code_map_neighbors(
            sample_retrieval_results, sample_code_map, max_neighbors=3
        )
        
        # Should have original results plus some neighbors
        assert len(expanded) >= len(sample_retrieval_results)
        
        # Check that neighbors were added with reduced scores
        neighbor_results = [r for r in expanded if r.chunk_id.startswith("neighbor_")]
        if neighbor_results:
            # Neighbor scores should be reduced
            original_score = sample_retrieval_results[0].score
            neighbor_score = neighbor_results[0].score
            assert neighbor_score < original_score
            
    def test_get_chunks_from_results(self, rag_answerer, sample_retrieval_results):
        """Test extracting chunks from retrieval results."""
        chunks = rag_answerer._get_chunks_from_results(sample_retrieval_results)
        
        assert len(chunks) == 2  # Should find 2 matching chunks
        assert chunks[0].id == "chunk_1"
        assert chunks[1].id == "chunk_2"
        
    def test_build_answer_prompt(self, rag_answerer):
        """Test answer prompt construction."""
        query = "What does this function do?"
        doc_pack = "Sample code context"
        
        prompt = rag_answerer._build_answer_prompt(query, doc_pack)
        
        assert query in prompt
        assert doc_pack in prompt
        assert "expert software engineer" in prompt
        assert "Code Context:" in prompt
        
    def test_build_docs_prompt(self, rag_answerer):
        """Test documentation prompt construction."""
        topic = "Authentication System"
        doc_context = "Authentication code context"
        
        prompt = rag_answerer._build_docs_prompt(topic, doc_context)
        
        assert topic in prompt
        assert doc_context in prompt
        assert "technical documentation expert" in prompt
        assert "markdown documentation" in prompt
        
    def test_empty_chunks_handling(self, rag_answerer):
        """Test handling of empty chunks list."""
        doc_pack = rag_answerer._assemble_doc_pack([], "test query")
        assert doc_pack == ""
        
        chunks = rag_answerer._get_chunks_from_results([])
        assert chunks == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])