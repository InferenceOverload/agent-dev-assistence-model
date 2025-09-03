"""Tests for orchestrator agent."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.agents.orchestrator import OrchestratorAgent, RAGAnswererAgent
from src.core.storage import StorageFactory
from src.tools.retrieval import HybridRetriever
from src.core.types import RetrievalResult


@pytest.fixture
def temp_repo():
    """Create a temporary repository with test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create src directory to match default include patterns
        src_dir = Path(temp_dir) / "src"
        src_dir.mkdir()
        
        # Create test files in src directory
        py_file = src_dir / "helper.py"
        py_file.write_text('''def helper_function():
    """This is a helper function."""
    return "help"

class UtilityClass:
    """A utility class for testing."""
    
    def method(self):
        return helper_function()
''')
        
        js_file = src_dir / "utils.js"  
        js_file.write_text('''function utilityFunction() {
    // Utility function in JavaScript
    return "util";
}

const config = {
    name: "test"
};
''')
        
        sql_file = src_dir / "schema.sql"
        sql_file.write_text('''CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255)
);

CREATE INDEX idx_users_email ON users(email);
''')
        
        yield temp_dir


@patch('src.agents.indexer.embed_texts')
def test_orchestrator_full_pipeline(mock_embed_texts, temp_repo):
    """Test full orchestrator pipeline: ingest -> size -> index -> ask."""
    # Mock embeddings to return deterministic vectors
    mock_embed_texts.return_value = [
        [0.1] * 768,  # First chunk
        [0.2] * 768,  # Second chunk  
        [0.3] * 768,  # Third chunk
    ]
    
    # Create storage factory
    storage_factory = StorageFactory(use_vertex=False)
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(root=temp_repo, session_id="test_pipeline", storage_factory=storage_factory)
    
    # Step 1: Ingest
    ingest_result = orchestrator.ingest()
    assert "files" in ingest_result
    assert "commit" in ingest_result
    assert len(ingest_result["files"]) >= 3  # At least our test files
    assert any("helper.py" in f for f in ingest_result["files"])
    assert any("utils.js" in f for f in ingest_result["files"])
    assert any("schema.sql" in f for f in ingest_result["files"])
    
    # Step 2: Size and decide
    size_result = orchestrator.size_and_decide()
    assert "sizer" in size_result
    assert "vectorization" in size_result
    assert "use_embeddings" in size_result["vectorization"]
    assert "backend" in size_result["vectorization"]
    assert "reasons" in size_result["vectorization"]
    
    # Step 3: Index
    index_result = orchestrator.index()
    assert index_result["session_id"] == "test_pipeline"
    assert "vector_count" in index_result
    assert "backend" in index_result
    
    # Verify retriever was stored
    retriever = storage_factory.session_store().get_retriever("test_pipeline")
    assert retriever is not None
    assert len(retriever.chunks) > 0
    
    # Step 4: Ask
    ask_result = orchestrator.ask("where is the helper function?")
    assert "answer" in ask_result
    assert "sources" in ask_result
    assert len(ask_result["sources"]) > 0
    assert any("helper.py" in source for source in ask_result["sources"])


def test_orchestrator_assertions(monkeypatch):
    """Test that orchestrator requires proper order of operations."""
    # Mock embed_texts to avoid needing GCP credentials
    def mock_embed_texts(texts, dim=768):
        return [[0.1] * dim for _ in texts]
    
    monkeypatch.setattr("src.agents.indexer.embed_texts", mock_embed_texts)
    
    orchestrator = OrchestratorAgent(root=".", session_id="test_assertions")
    
    # Test that index requires ingest and size_and_decide
    with pytest.raises(AssertionError, match="Call ingest"):
        orchestrator.index()
    
    # Ingest first
    orchestrator.ingest()
    
    # Still need size_and_decide
    with pytest.raises(AssertionError, match="Call size_and_decide"):
        orchestrator.index()
    
    # Now size_and_decide
    orchestrator.size_and_decide()
    
    # Now index should work
    result = orchestrator.index()
    assert "status" in result
    
    # Test that ask creates index if needed
    orchestrator.ask("test query")


def test_rag_answerer_agent():
    """Test RAGAnswererAgent with mock retriever."""
    # Create mock retriever with test results
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [
        RetrievalResult(
            chunk_id="test:commit:file.py#1-10",
            path="file.py",
            score=0.9,
            neighbors=[],
            snippet="def test_function():\n    return 'test'"
        ),
        RetrievalResult(
            chunk_id="test:commit:file.js#1-5", 
            path="file.js",
            score=0.7,
            neighbors=[],
            snippet="function helper() {\n    return 'help';\n}"
        )
    ]
    
    # Test RAG answerer
    rag = RAGAnswererAgent(mock_retriever)
    result = rag.answer("test query", k=5)
    
    # Verify search was called
    mock_retriever.search.assert_called_once_with("test query", k=5)
    
    # Verify response format
    assert "answer" in result
    assert "sources" in result
    assert "token_count" in result
    assert "model_used" in result
    assert len(result["sources"]) == 2
    assert "file.py" in result["sources"]
    assert "file.js" in result["sources"]
    assert "test_function" in result["answer"]  # Should include snippet


def test_rag_answerer_agent_no_results():
    """Test RAGAnswererAgent when no results are found."""
    # Create mock retriever that returns empty results
    mock_retriever = MagicMock()
    mock_retriever.search.return_value = []
    
    rag = RAGAnswererAgent(mock_retriever)
    result = rag.answer("unknown query")
    
    assert result["answer"] == "No relevant information found."
    assert result["sources"] == []
    assert result["token_count"] == 0
    assert result["model_used"] == "none"


def test_rag_answerer_agent_write_docs():
    """Test RAGAnswererAgent documentation writing."""
    # Create mock retriever
    mock_retriever = MagicMock() 
    mock_retriever.search.return_value = [
        RetrievalResult(
            chunk_id="test:commit:docs.py#1-10",
            path="docs.py",
            score=0.8,
            neighbors=[],
            snippet="# Documentation example"
        )
    ]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temp directory for docs generation
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            
            rag = RAGAnswererAgent(mock_retriever)
            result = rag.answer("test documentation", write_docs=True)
            
            # Check that docs file was created
            assert "docs_file" in result
            docs_path = Path(result["docs_file"])
            assert docs_path.exists()
            
            # Check docs content
            content = docs_path.read_text()
            assert "# test documentation" in content
            assert "docs.py" in content
            
        finally:
            os.chdir(original_cwd)


@patch('src.agents.indexer.embed_texts')
def test_orchestrator_with_small_repo(mock_embed_texts, temp_repo):
    """Test orchestrator behavior with small repository (no embeddings needed)."""
    # Mock empty embeddings (shouldn't be called for small repo)
    mock_embed_texts.return_value = []
    
    # Create storage factory
    storage_factory = StorageFactory(use_vertex=False)
    
    # Initialize orchestrator
    orchestrator = OrchestratorAgent(root=temp_repo, session_id="small_test", storage_factory=storage_factory)
    
    # Run pipeline
    ingest_result = orchestrator.ingest()
    size_result = orchestrator.size_and_decide()
    
    # Small repo should not use embeddings
    # (depends on repo size - our test repo might be small enough)
    vectorization = size_result["vectorization"]
    if not vectorization["use_embeddings"]:
        # For small repos without embeddings, index should handle gracefully
        index_result = orchestrator.index()
        assert "vector_count" in index_result