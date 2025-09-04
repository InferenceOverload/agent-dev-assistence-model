"""Tests for evidence collection tools."""

import pytest
from pathlib import Path

from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory
from src.agents.repo_ingestor import ingest_repo
from src.core.policy import VectorizationDecision


def test_collect_evidence_small_repo(tmp_path, monkeypatch):
    """Test evidence collection on a small repository."""
    root = tmp_path / "repo"
    src_dir = root / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "app.py").write_text("def main():\n    print('hello')\n")
    (root / "README.md").write_text("# Test App\n\nPurpose: demonstration\n")
    
    # Ingest the repo
    cmap, chunks = ingest_repo(str(root))
    
    # Create orchestrator
    orch = OrchestratorAgent(root=str(root), session_id="test1", storage_factory=StorageFactory(use_vertex=False))
    orch.code_map, orch.chunks = cmap, chunks
    
    # Mock embeddings to deterministic vectors
    def fake_embed(texts, dim=768):
        return [[0.1] * dim for _ in texts]
    
    import src.agents.indexer as idx
    monkeypatch.setattr(idx, "embed_texts", fake_embed)
    
    # Set decision to use embeddings
    orch.decision = VectorizationDecision(use_embeddings=True, backend="in_memory", reasons=["test"])
    
    # Build index
    orch.index()
    
    # Test evidence collection
    ev = orch.collect_evidence("project overview", k=10)
    assert "doc_pack" in ev
    assert isinstance(ev["doc_pack"], list)
    assert "status" in ev
    
    # Should find some results
    if len(ev["doc_pack"]) > 0:
        # Check structure of doc items
        first_item = ev["doc_pack"][0]
        assert "path" in first_item
        assert "score" in first_item
        assert "excerpt" in first_item


def test_repo_synopsis(tmp_path, monkeypatch):
    """Test repo synopsis generation."""
    root = tmp_path / "repo"
    src_dir = root / "src"
    src_dir.mkdir(parents=True)
    
    # Create various files that should be picked up by synopsis
    (root / "README.md").write_text("# My App\n\nOverview: test application")
    (src_dir / "main.py").write_text("def main():\n    app.run()")
    (src_dir / "routes.py").write_text("@app.route('/home')\ndef home(): pass")
    (root / "requirements.txt").write_text("flask==2.0.0\nrequests==2.28.0")
    (root / "package.json").write_text('{"name": "app", "dependencies": {}}')
    
    # Ingest the repo
    cmap, chunks = ingest_repo(str(root))
    
    # Create orchestrator
    orch = OrchestratorAgent(root=str(root), session_id="test2", storage_factory=StorageFactory(use_vertex=False))
    orch.code_map, orch.chunks = cmap, chunks
    
    # Mock embeddings
    def fake_embed(texts, dim=768):
        return [[0.2] * dim for _ in texts]
    
    import src.agents.indexer as idx
    monkeypatch.setattr(idx, "embed_texts", fake_embed)
    
    # Set decision and index
    orch.decision = VectorizationDecision(use_embeddings=True, backend="in_memory", reasons=["test"])
    orch.index()
    
    # Test synopsis
    synopsis = orch.repo_synopsis()
    assert "doc_pack" in synopsis
    assert isinstance(synopsis["doc_pack"], list)
    assert "status" in synopsis
    
    # Check status message
    assert len(synopsis["status"]) > 0
    assert "repo_synopsis collected" in synopsis["status"][0]


def test_collect_evidence_auto_index(tmp_path, monkeypatch):
    """Test that collect_evidence auto-indexes if needed."""
    root = tmp_path / "repo"
    src_dir = root / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "test.py").write_text("def test():\n    return True\n")
    
    # Create orchestrator without indexing
    orch = OrchestratorAgent(root=str(root), session_id="test3", storage_factory=StorageFactory(use_vertex=False))
    
    # Mock embeddings
    def fake_embed(texts, dim=768):
        return [[0.3] * dim for _ in texts]
    
    import src.agents.indexer as idx
    monkeypatch.setattr(idx, "embed_texts", fake_embed)
    
    # Call collect_evidence without prior indexing - should auto-index
    ev = orch.collect_evidence("test function", k=5)
    
    # Should succeed and have results
    assert "doc_pack" in ev
    assert "status" in ev
    
    # Verify that indexing happened
    assert orch.code_map is not None
    assert orch.chunks is not None
    assert orch.decision is not None


def test_rag_answerer_collect_method(tmp_path, monkeypatch):
    """Test RAGAnswererAgent.collect method directly."""
    from src.agents.orchestrator import RAGAnswererAgent
    from src.tools.retrieval import HybridRetriever
    from src.core.types import Chunk, RetrievalResult
    
    # Create mock chunks
    chunks = [
        Chunk(
            id="test:commit:file.py#1-10",
            repo="test",
            commit="abc123",
            path="file.py",
            lang="python",
            start_line=1,
            end_line=10,
            text="def hello():\n    return 'world'",
            symbols=["hello"],
            imports=[],
            neighbors=[],
            hash="hash1"
        )
    ]
    
    # Create mock retriever
    class MockRetriever:
        def __init__(self):
            self.chunks = chunks
            
        def search(self, query, k=12):
            return [
                RetrievalResult(
                    chunk_id="test:commit:file.py#1-10",
                    path="file.py",
                    score=0.9,
                    neighbors=[],
                    snippet="def hello():\n    return 'world'"
                )
            ]
    
    retriever = MockRetriever()
    rag = RAGAnswererAgent(retriever)
    
    # Test collect method
    result = rag.collect("hello function", k=10)
    
    assert "query" in result
    assert result["query"] == "hello function"
    assert "doc_pack" in result
    assert isinstance(result["doc_pack"], list)
    
    if len(result["doc_pack"]) > 0:
        item = result["doc_pack"][0]
        assert "path" in item
        assert item["path"] == "file.py"
        assert "score" in item
        assert item["score"] == 0.9
        assert "excerpt" in item