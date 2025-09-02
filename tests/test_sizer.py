"""Tests for the repository sizer module."""

import tempfile
import pytest
from pathlib import Path
from src.tools.sizer import (
    SizerReport,
    estimate_tokens,
    measure_repo,
    _detect_language,
    _should_ignore_path,
    _is_text_file,
    _count_lines,
)


class TestEstimateTokens:
    """Tests for token estimation function."""
    
    def test_estimate_tokens_basic(self):
        """Test basic token estimation."""
        assert estimate_tokens(100) == 25
        assert estimate_tokens(400) == 100
        assert estimate_tokens(0) == 0
        assert estimate_tokens(1) == 0  # Integer division
        assert estimate_tokens(3) == 0
        assert estimate_tokens(4) == 1


class TestLanguageDetection:
    """Tests for language detection."""
    
    def test_detect_language_known_extensions(self):
        """Test detection of known file extensions."""
        assert _detect_language("script.py") == "python"
        assert _detect_language("app.js") == "javascript"
        assert _detect_language("component.tsx") == "typescript"
        assert _detect_language("Main.java") == "java"
        assert _detect_language("program.cpp") == "cpp"
        assert _detect_language("README.md") == "markdown"
        assert _detect_language("config.yml") == "yaml"
    
    def test_detect_language_unknown_extension(self):
        """Test detection of unknown extensions."""
        assert _detect_language("file.xyz") == "unknown"
        assert _detect_language("noextension") == "unknown"
    
    def test_detect_language_case_insensitive(self):
        """Test that detection is case insensitive."""
        assert _detect_language("Script.PY") == "python"
        assert _detect_language("App.JS") == "javascript"


class TestPathFiltering:
    """Tests for path filtering logic."""
    
    def test_should_ignore_path_common_dirs(self):
        """Test ignoring of common directories."""
        assert _should_ignore_path("node_modules/package/file.js") is True
        assert _should_ignore_path(".git/config") is True
        assert _should_ignore_path("build/output.jar") is True
        assert _should_ignore_path("venv/lib/python3.9/site-packages/module.py") is True
        assert _should_ignore_path("__pycache__/file.pyc") is True
    
    def test_should_ignore_path_lockfiles(self):
        """Test ignoring of lockfiles."""
        assert _should_ignore_path("package-lock.json") is True
        assert _should_ignore_path("yarn.lock") is True
        assert _should_ignore_path("Pipfile.lock") is True
        assert _should_ignore_path("Cargo.lock") is True
    
    def test_should_not_ignore_valid_paths(self):
        """Test that valid paths are not ignored."""
        assert _should_ignore_path("src/main.py") is False
        assert _should_ignore_path("tests/test_example.py") is False
        assert _should_ignore_path("README.md") is False
        assert _should_ignore_path("package.json") is False


class TestTextFileDetection:
    """Tests for text file detection."""
    
    def test_is_text_file_known_extensions(self):
        """Test detection of known text file extensions."""
        assert _is_text_file("script.py") is True
        assert _is_text_file("README.md") is True
        assert _is_text_file("config.json") is True
        assert _is_text_file("style.css") is True
        assert _is_text_file("notes.txt") is True
    
    def test_is_text_file_unknown_extensions(self):
        """Test handling of unknown extensions."""
        # Files with unknown extensions are not treated as text by default
        assert _is_text_file("binary.exe") is False
        assert _is_text_file("image.png") is False


class TestLineCounter:
    """Tests for line counting function."""
    
    def test_count_lines_basic(self):
        """Test basic line counting."""
        content = "line1\nline2\nline3"
        assert _count_lines(content) == 3
    
    def test_count_lines_empty_file(self):
        """Test counting lines in empty file."""
        assert _count_lines("") == 0
        assert _count_lines("\n\n\n") == 0  # Only empty lines
    
    def test_count_lines_with_empty_lines(self):
        """Test counting lines with empty lines mixed in."""
        content = "line1\n\nline2\n\n\nline3\n"
        assert _count_lines(content) == 3
    
    def test_count_lines_whitespace_only_lines(self):
        """Test that whitespace-only lines are not counted."""
        content = "line1\n   \nline2\n\t\nline3"
        assert _count_lines(content) == 3


class TestMeasureRepo:
    """Tests for the main measure_repo function."""
    
    def test_measure_repo_basic(self):
        """Test basic repository measurement with temporary files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "main.py").write_text("def hello():\n    print('hello')\n    return True\n")
            (temp_path / "test.js").write_text("function test() {\n  return 42;\n}\n")
            (temp_path / "README.md").write_text("# Project\n\nDescription here.\n")
            
            files = ["main.py", "test.js", "README.md"]
            
            result = measure_repo(str(temp_path), files)
            
            # Basic validations
            assert isinstance(result, SizerReport)
            assert result.repo == temp_path.name
            assert result.file_count == 3
            assert result.loc_total == 8  # 3 + 3 + 2 = 8 non-empty lines (python: 3, js: 3, md: 2)
            assert result.bytes_total > 0
            assert result.max_file_loc == 3
            assert result.avg_file_loc > 0
            assert result.estimated_tokens_repo > 0
            assert result.chunk_estimate >= 3  # At least 1 chunk per file
            assert result.vector_count_estimate == result.chunk_estimate
            
            # Check language breakdown
            assert "python" in result.lang_breakdown
            assert "javascript" in result.lang_breakdown
            assert "markdown" in result.lang_breakdown
            assert result.lang_breakdown["python"]["files"] == 1
            assert result.lang_breakdown["python"]["loc"] == 3
    
    def test_measure_repo_empty_file(self):
        """Test that empty files still yield at least 1 chunk."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create empty file
            (temp_path / "empty.py").write_text("")
            
            result = measure_repo(str(temp_path), ["empty.py"])
            
            assert result.file_count == 1
            assert result.loc_total == 0
            assert result.chunk_estimate >= 1  # Empty file still gets 1 chunk
            assert result.vector_count_estimate >= 1
    
    def test_measure_repo_with_ignored_files(self):
        """Test that ignored files are properly excluded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create valid file
            (temp_path / "main.py").write_text("print('hello')")
            
            # Create ignored files/directories
            (temp_path / "package-lock.json").write_text('{"name": "test"}')
            node_modules = temp_path / "node_modules"
            node_modules.mkdir()
            (node_modules / "module.js").write_text("module.exports = {};")
            
            files = ["main.py", "package-lock.json", "node_modules/module.js"]
            
            result = measure_repo(str(temp_path), files)
            
            # Only main.py should be counted
            assert result.file_count == 1
            assert "python" in result.lang_breakdown
            assert result.lang_breakdown["python"]["files"] == 1
    
    def test_measure_repo_chunking_estimates(self):
        """Test chunk estimation with different file sizes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a large file that should result in multiple chunks
            large_content = "\n".join([f"line_{i}" for i in range(500)])
            (temp_path / "large.py").write_text(large_content)
            
            # Create a small file
            (temp_path / "small.py").write_text("print('small')")
            
            result = measure_repo(str(temp_path), ["large.py", "small.py"], chunk_loc=300, overlap_loc=50)
            
            assert result.file_count == 2
            assert result.loc_total == 501  # 500 + 1
            assert result.chunk_estimate > 2  # Should need multiple chunks for large file
    
    def test_measure_repo_nonexistent_files(self):
        """Test handling of nonexistent files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create one valid file
            (temp_path / "exists.py").write_text("print('exists')")
            
            files = ["exists.py", "nonexistent.py", "also_missing.js"]
            
            result = measure_repo(str(temp_path), files)
            
            # Only the existing file should be counted
            assert result.file_count == 1
            assert result.loc_total == 1
    
    def test_measure_repo_commit_detection(self):
        """Test git commit detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.py").write_text("print('test')")
            
            result = measure_repo(str(temp_path), ["test.py"])
            
            # Should default to 'workspace' when not in a git repo
            assert result.commit == "workspace"


# Mark all tests as fast and deterministic
pytestmark = pytest.mark.filterwarnings("ignore:.*:DeprecationWarning")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])