from pathlib import Path
from src.agents.repo_ingestor import ingest_repo
from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory

def test_file_summaries_and_compress(tmp_path, monkeypatch):
    # Mock Google Cloud project
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    
    # Create a medium repo with many files
    root = tmp_path / "bigrepo"
    (root / "pkg").mkdir(parents=True)
    for i in range(60):
        p = root / "pkg" / f"file_{i}.py"
        p.write_text("\n".join([f"# file {i}", "def f():", "    return 42"] * 5))
    # Ingest
    cmap, chunks = ingest_repo(str(root))
    orch = OrchestratorAgent(root=str(root), session_id="t", storage_factory=StorageFactory(use_vertex=False))
    orch.code_map, orch.chunks = cmap, chunks
    
    # Deterministic embeddings - mock both the module function and the Google client
    import src.tools.embeddings as emb
    def fake_embed(xs, dim=768):  # small vectors fine for tests
        return [[1.0] * dim for _ in xs]
    monkeypatch.setattr(emb, "embed_texts", fake_embed)
    
    # Also mock the Vertex AI client to avoid authentication issues
    from unittest.mock import MagicMock
    mock_client = MagicMock()
    monkeypatch.setattr(emb, "_get_vertex_client", lambda: mock_client)
    
    # Index (builds file summaries)
    orch.size_and_decide()
    idx = orch.index()
    assert idx["file_count"] >= 60
    # Collect evidence (should compress)
    ev = orch.collect_evidence("project overview", k=20)
    assert "doc_pack" in ev
    total_lines = sum(len((d.get("excerpt") or "").splitlines()) for d in ev["doc_pack"])
    assert total_lines <= 400