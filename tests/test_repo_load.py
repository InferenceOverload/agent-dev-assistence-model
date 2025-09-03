"""Tests for repository loading and cloning."""

import os
import subprocess
import sys
import tempfile
import pathlib
import shutil
import pytest

from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory
from src.tools.repo_io import clone_repo, safe_workspace_root


def make_local_git_repo(tmp_path):
    """Create a local git repository for testing."""
    origin = tmp_path / "origin"
    origin.mkdir()
    
    # Create some test files
    (origin / "app.py").write_text("print('hi')\n")
    (origin / "src").mkdir()
    (origin / "src" / "utils.py").write_text("def helper():\n    return 42\n")
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=origin, check=True, 
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@test.com"], 
                  cwd=origin, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], 
                  cwd=origin, check=True)
    subprocess.run(["git", "add", "."], cwd=origin, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=origin, check=True)
    
    return origin


def test_clone_and_load_file_url(tmp_path, monkeypatch):
    """Test cloning from a file:// URL and loading into orchestrator."""
    # Create a test git repo
    origin = make_local_git_repo(tmp_path)
    url = f"file://{origin.resolve()}"
    
    # Test clone_repo
    cloned_path = clone_repo(url)
    assert os.path.exists(os.path.join(cloned_path, "app.py"))
    assert os.path.exists(os.path.join(cloned_path, "src", "utils.py"))
    
    # Test loading into orchestrator
    orch = OrchestratorAgent(
        root=".", 
        session_id="test_load", 
        storage_factory=StorageFactory(use_vertex=False)
    )
    
    info = orch.load_repo(url)
    assert "root" in info
    assert os.path.isdir(info["root"])
    assert "status" in info
    assert len(info["status"]) > 0
    
    # Test ingestion after load
    ing = orch.ingest()
    assert len(ing["files"]) >= 1  # At least src/utils.py should be found
    assert "status" in ing
    
    # Clean up workspace
    workspace_root = pathlib.Path(safe_workspace_root())
    if workspace_root.exists():
        shutil.rmtree(workspace_root.parent, ignore_errors=True)


def test_clone_repo_reuse_existing(tmp_path):
    """Test that clone_repo reuses existing clones."""
    # Create a test git repo
    origin = make_local_git_repo(tmp_path)
    url = f"file://{origin.resolve()}"
    
    # First clone
    path1 = clone_repo(url)
    assert os.path.exists(path1)
    
    # Add a marker file to the clone
    marker_file = os.path.join(path1, "marker.txt")
    with open(marker_file, "w") as f:
        f.write("test")
    
    # Second clone should reuse the same directory
    path2 = clone_repo(url)
    assert path1 == path2
    assert os.path.exists(marker_file), "Clone should reuse existing directory"
    
    # Clean up workspace
    workspace_root = pathlib.Path(safe_workspace_root())
    if workspace_root.exists():
        shutil.rmtree(workspace_root.parent, ignore_errors=True)


def test_orchestrator_status_logs(monkeypatch):
    """Test that orchestrator methods return status logs."""
    # Mock embed_texts to avoid needing GCP credentials
    def mock_embed_texts(texts, dim=1536):
        return [[0.1] * dim for _ in texts]
    
    monkeypatch.setattr("src.agents.indexer.embed_texts", mock_embed_texts)
    
    orch = OrchestratorAgent(
        root=".",
        session_id="test_status",
        storage_factory=StorageFactory(use_vertex=False)
    )
    
    # Test ingest status
    ing = orch.ingest()
    assert "status" in ing
    assert isinstance(ing["status"], list)
    assert len(ing["status"]) > 0
    
    # Test size_and_decide status
    dec = orch.size_and_decide()
    assert "status" in dec
    assert isinstance(dec["status"], list)
    
    # Test index status
    idx = orch.index()
    assert "status" in idx
    assert isinstance(idx["status"], list)
    
    # Test ask status
    ask_result = orch.ask("test query")
    assert "status" in ask_result
    assert isinstance(ask_result["status"], list)