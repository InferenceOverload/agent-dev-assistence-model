from src.agents.repo_ingestor import ingest_repo
from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory

def test_index_skips_empty_chunks(tmp_path, monkeypatch):
    # Mock Google Cloud project
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    # file with some empty lines and whitespace-only text blocks
    (root / "pkg" / "a.py").write_text(" \n\n# header\n\n\ndef f():\n    pass\n\n")
    (root / "pkg" / "b.py").write_text("\n\n   \n")  # effectively empty
    cmap, chunks = ingest_repo(str(root))
    # Should still create some chunks but not include purely empty ones
    orch = OrchestratorAgent(root=str(root), session_id="t", storage_factory=StorageFactory(use_vertex=False))
    orch.code_map, orch.chunks = cmap, chunks
    
    # Monkeypatch embeddings to assert no empty strings are passed
    import src.tools.embeddings as emb
    def fake_embed(xs, dim=768):
        assert all((x or "").strip() for x in xs), "embed_texts received an empty/whitespace string"
        return [[1.0] * 8 for _ in xs]
    monkeypatch.setattr(emb, "embed_texts", fake_embed)
    
    # Also mock the Vertex AI client to avoid authentication issues
    from unittest.mock import MagicMock
    mock_client = MagicMock()
    monkeypatch.setattr(emb, "_get_vertex_client", lambda: mock_client)
    
    orch.size_and_decide()
    idx = orch.index()
    assert idx["vector_count"] >= 0  # no crash