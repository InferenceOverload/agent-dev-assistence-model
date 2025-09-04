import os
import json
from src.agents.repo_ingestor import ingest_repo
from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory
from src.core.policy import VectorizationDecision

def test_vvs_index_and_query_mock(tmp_path, monkeypatch):
    os.environ["UNIT_TEST"] = "1"  # make adapter no-op
    # Mock Google Cloud project and VVS settings
    monkeypatch.setenv("VVS_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("VVS_INDEX", "test-index")
    monkeypatch.setenv("VVS_ENDPOINT", "test-endpoint")
    
    # Clear the config cache so it picks up the new env vars
    import src.core.config as cfg
    cfg.CONFIG = None
    
    # tiny repo
    root = tmp_path / "r"
    (root / "a").mkdir(parents=True)
    (root / "a" / "f.py").write_text("def main():\n    print('x')\n")
    cmap, chunks = ingest_repo(str(root))
    orch = OrchestratorAgent(root=str(root), session_id="s1", storage_factory=StorageFactory(use_vertex=True))
    orch.code_map, orch.chunks = cmap, chunks
    # force VVS in decision
    orch.decision = VectorizationDecision(use_embeddings=True, backend="vertex_vector_search", reasons=["test"])
    # monkeypatch indexer to use small fake embeddings
    import src.tools.embeddings as emb
    def fake_embed(xs, dim=768): return [[1.0]*8 for _ in xs]
    monkeypatch.setattr(emb, "embed_texts", fake_embed)
    
    # Also mock the Vertex AI client to avoid authentication issues
    from unittest.mock import MagicMock
    mock_client = MagicMock()
    monkeypatch.setattr(emb, "_get_vertex_client", lambda: mock_client)
    
    # index (will call vvs.upsert but no-op)
    idx = orch.index()
    assert idx.get("using_vvs", False) == True or idx.get("backend") == "vertex_vector_search"
    
    # collect evidence / answer should still run without errors (external ann returns no candidates)
    out = orch.collect_evidence("project overview", k=5)
    assert "doc_pack" in out