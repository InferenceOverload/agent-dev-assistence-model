"""Tests for CLI module."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.ui.cli import main


@pytest.fixture
def temp_repo():
    """Create a temporary repository with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        
        # Create src directory with sample files
        src_dir = repo_path / "src"
        src_dir.mkdir()
        
        # Python file
        (src_dir / "helper.py").write_text("""
def helper_function():
    '''A helper function that does something useful.'''
    return "hello world"

class UtilityClass:
    def process(self, data):
        return data.upper()
""")
        
        # JavaScript file
        (src_dir / "app.js").write_text("""
function helperFunction() {
    // A helper function in JavaScript
    return "hello world";
}

class Utils {
    process(data) {
        return data.toUpperCase();
    }
}
""")
        
        # SQL file
        (src_dir / "schema.sql").write_text("""
-- Helper table for utilities
CREATE TABLE helper_data (
    id INTEGER PRIMARY KEY,
    value TEXT NOT NULL
);

-- Helper view
CREATE VIEW helper_summary AS 
SELECT COUNT(*) as total FROM helper_data;
""")
        
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, capture_output=True)
        
        yield str(repo_path)


@pytest.fixture
def mock_embeddings():
    """Mock embeddings to return deterministic vectors."""
    def fake_embed_texts(texts, dim=768):
        """Return deterministic vectors based on text hash."""
        vectors = []
        for i, text in enumerate(texts):
            # Create deterministic vector based on text hash and index
            vector = [float((hash(text) + j + i) % 100) / 100.0 for j in range(dim)]
            vectors.append(vector)
        return vectors
    
    with patch("src.agents.indexer.embed_texts", side_effect=fake_embed_texts):
        yield fake_embed_texts


def test_cli_all_command(temp_repo, mock_embeddings, capsys):
    """Test the 'all' command."""
    test_args = ["prog", "all", "--root", temp_repo, "--session", "t1"]
    
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit as e:
            # If SystemExit is raised, ensure it's success
            assert e.code == 0
    
    # Check output
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Verify expected keys in output
    assert "ingest" in result
    assert "decide" in result  
    assert "index" in result
    assert "ask" not in result  # No query provided
    
    # Verify ingest results
    assert "files" in result["ingest"]
    assert "commit" in result["ingest"]
    assert len(result["ingest"]["files"]) > 0
    
    # Verify decide results
    assert "sizer" in result["decide"]
    assert "vectorization" in result["decide"]
    assert "use_embeddings" in result["decide"]["vectorization"]
    
    # Verify index results
    assert "session_id" in result["index"]


def test_cli_ask_command_with_docs(temp_repo, mock_embeddings, capsys):
    """Test the 'ask' command with --write-docs flag."""
    test_args = [
        "prog", "ask", 
        "--root", temp_repo, 
        "--session", "t2",
        "--query", "helper function",
        "--write-docs"
    ]
    
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit as e:
            # If SystemExit is raised, ensure it's success
            assert e.code == 0
    
    # Check output
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Verify expected keys
    assert "answer" in result
    assert "sources" in result
    assert "token_count" in result
    assert "model_used" in result
    
    # Ensure sources is a non-empty list
    assert isinstance(result["sources"], list)
    assert len(result["sources"]) > 0
    
    # When --write-docs is set, should have docs_file path
    assert "docs_file" in result
    assert "docs/generated" in result["docs_file"]
    
    # Verify docs file was created
    docs_path = Path(result["docs_file"])
    assert docs_path.exists()
    docs_content = docs_path.read_text()
    assert "helper function" in docs_content
    assert "## Sources" in docs_content


def test_cli_individual_commands(temp_repo, mock_embeddings, capsys):
    """Test individual commands in sequence."""
    session_id = "t3"
    
    # Test ingest
    with patch.object(sys, 'argv', ["prog", "ingest", "--root", temp_repo, "--session", session_id]):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
    
    captured = capsys.readouterr()
    ingest_result = json.loads(captured.out)
    assert "files" in ingest_result
    assert "commit" in ingest_result
    
    # Test decide
    with patch.object(sys, 'argv', ["prog", "decide", "--root", temp_repo, "--session", session_id]):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
    
    captured = capsys.readouterr()
    decide_result = json.loads(captured.out)
    assert "sizer" in decide_result
    assert "vectorization" in decide_result
    
    # Test index
    with patch.object(sys, 'argv', ["prog", "index", "--root", temp_repo, "--session", session_id]):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
    
    captured = capsys.readouterr()
    index_result = json.loads(captured.out)
    assert "session_id" in index_result  # Fixed key name
    
    # Test ask
    with patch.object(sys, 'argv', ["prog", "ask", "--root", temp_repo, "--session", session_id, "--query", "utility class"]):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0
    
    captured = capsys.readouterr()
    ask_result = json.loads(captured.out)
    assert "answer" in ask_result
    assert "sources" in ask_result


def test_cli_help_output(capsys):
    """Test that -h prints usage and exits with code 0."""
    with patch.object(sys, 'argv', ["prog", "-h"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Help should exit with code 0
        assert exc_info.value.code == 0
    
    # Check that help was printed
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()
    assert "orchestrator cli" in captured.out.lower()
    assert "ingest" in captured.out
    assert "decide" in captured.out
    assert "index" in captured.out
    assert "ask" in captured.out
    assert "all" in captured.out


def test_cli_error_handling(capsys):
    """Test error handling for invalid inputs."""
    # Test with non-existent root path
    with patch.object(sys, 'argv', ["prog", "all", "--root", "/nonexistent/path"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Should exit with non-zero code (1 for custom errors, 2 for argparse errors)
        assert exc_info.value.code in [1, 2]
    
    # Check error message
    captured = capsys.readouterr()
    # The error could be from our validation or from argparse
    assert "does not exist" in captured.err or "error:" in captured.err
    
    # Test ask command without query
    with patch.object(sys, 'argv', ["prog", "ask"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Should exit with non-zero code (1 for our custom validation)
        assert exc_info.value.code == 1
    
    # Check error message  
    captured = capsys.readouterr()
    assert "required" in captured.err


def test_cli_all_with_query(temp_repo, mock_embeddings, capsys):
    """Test 'all' command with query parameter."""
    test_args = [
        "prog", "all", 
        "--root", temp_repo, 
        "--session", "t4",
        "--query", "javascript function",
        "--k", "5"
    ]
    
    with patch.object(sys, 'argv', test_args):
        try:
            main()
        except SystemExit as e:
            # If SystemExit is raised, ensure it's success
            assert e.code == 0
    
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    
    # Should have all pipeline steps plus ask
    assert "ingest" in result
    assert "decide" in result
    assert "index" in result
    assert "ask" in result
    
    # Ask results should have sources
    assert "sources" in result["ask"]
    assert isinstance(result["ask"]["sources"], list)