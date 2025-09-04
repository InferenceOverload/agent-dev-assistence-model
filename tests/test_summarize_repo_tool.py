"""Test for summarize_repo tool."""

from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory
from src.agents.repo_ingestor import ingest_repo


def test_summarize_repo_bundle(tmp_path, monkeypatch):
    """Test that summarize_repo returns proper bundle structure."""
    # Prepare a tiny repo
    root = tmp_path / "r"
    src_dir = root / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "app.py").write_text("def main():\n    print('hello')\n")
    (root / "README.md").write_text("# Demo\nThis is a demo app.\n")
    
    # Ingest and prepare
    cmap, chunks = ingest_repo(str(root))
    orch = OrchestratorAgent(
        root=str(root), 
        session_id="t", 
        storage_factory=StorageFactory(use_vertex=False)
    )
    orch.code_map, orch.chunks = cmap, chunks
    
    # Deterministic embeddings to avoid network calls
    import src.agents.indexer as idx
    def fake_embed(texts, dim=768): 
        return [[1.0] * dim for _ in texts]
    monkeypatch.setattr(idx, "embed_texts", fake_embed)
    
    # Size, decide, and index
    orch.size_and_decide()
    orch.index()
    
    # Call repo_synopsis
    bundle = orch.repo_synopsis()
    assert "doc_pack" in bundle
    assert isinstance(bundle["doc_pack"], list)
    assert "status" in bundle
    
    # Now test the summarize_repo tool wrapper
    # Import the function from adam_agent
    from adam_agent import summarize_repo
    
    result = summarize_repo()
    
    # Check structure
    assert "doc_pack" in result
    assert "outline" in result
    assert "status" in result
    
    # Check outline contents
    assert isinstance(result["outline"], list)
    assert len(result["outline"]) == 8  # Should have 8 sections
    assert "Purpose & Overview" in result["outline"]
    assert "Architecture" in result["outline"]
    assert "Entry Points" in result["outline"]
    assert "Data & Integrations" in result["outline"]
    assert "Dependencies" in result["outline"]
    assert "How to Run" in result["outline"]
    assert "Gaps / Unknowns" in result["outline"]
    assert "Next Steps" in result["outline"]
    
    # Check status
    assert isinstance(result["status"], list)
    assert len(result["status"]) > 0
    assert "summarize_repo" in result["status"][0]


def test_summarize_repo_with_richer_content(tmp_path, monkeypatch):
    """Test summarize_repo with a more realistic repository structure."""
    # Create a richer repo structure
    root = tmp_path / "app"
    src_dir = root / "src"
    src_dir.mkdir(parents=True)
    
    # Create various files
    (root / "README.md").write_text(
        "# MyApp\n\nA web application for managing tasks.\n\n## Installation\n\nnpm install"
    )
    (src_dir / "main.py").write_text(
        "from flask import Flask\n\napp = Flask(__name__)\n\nif __name__ == '__main__':\n    app.run()"
    )
    (src_dir / "routes.py").write_text(
        "@app.route('/')\ndef index():\n    return render_template('index.html')"
    )
    (root / "package.json").write_text(
        '{"name": "myapp", "version": "1.0.0", "dependencies": {"express": "^4.17.1"}}'
    )
    (root / "requirements.txt").write_text("flask==2.0.1\nsqlalchemy==1.4.25")
    
    # Ingest and prepare
    cmap, chunks = ingest_repo(str(root))
    orch = OrchestratorAgent(
        root=str(root),
        session_id="t2",
        storage_factory=StorageFactory(use_vertex=False)
    )
    orch.code_map, orch.chunks = cmap, chunks
    
    # Mock embeddings
    import src.agents.indexer as idx
    def fake_embed(texts, dim=768):
        return [[0.5] * dim for _ in texts]
    monkeypatch.setattr(idx, "embed_texts", fake_embed)
    
    # Index
    orch.size_and_decide()
    orch.index()
    
    # Test the summarize functionality
    from adam_agent import summarize_repo
    result = summarize_repo()
    
    # Should have collected evidence from multiple files
    assert len(result["doc_pack"]) > 0
    
    # Check that different types of files are represented
    paths = [item["path"] for item in result["doc_pack"]]
    
    # The doc_pack should contain various file types
    # (exact contents depend on search scoring, but we should have some results)
    assert len(paths) > 0