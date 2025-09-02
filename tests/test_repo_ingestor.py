"""Tests for repository ingestion system."""

import os
import tempfile
from pathlib import Path
import pytest

from src.core.types import Chunk, CodeMap
from src.tools.repo_io import safe_join, is_binary_path, list_source_files, read_text_file
from src.tools.parsing import detect_language, extract_imports, find_symbols, split_code_windows
from src.agents.repo_ingestor import get_git_commit, compute_hash, ingest_repo


class TestRepoIO:
    """Test repository I/O functions."""

    def test_safe_join(self):
        """Test safe path joining."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Normal path joining - use realpath to handle symlinks consistently  
            result = safe_join(temp_dir, "src/app.py")
            expected = os.path.realpath(os.path.join(temp_dir, "src/app.py"))
            assert os.path.realpath(result) == expected
            
            # Prevent path traversal
            with pytest.raises(ValueError, match="Path traversal detected"):
                safe_join(temp_dir, "../../../etc/passwd")
            
            with pytest.raises(ValueError, match="Path traversal detected"):
                safe_join(temp_dir, "src/../../../etc/passwd")

    def test_is_binary_path(self):
        """Test binary file detection."""
        # Test extension-based detection
        assert is_binary_path("file.png") == True
        assert is_binary_path("file.pdf") == True
        assert is_binary_path("file.pyc") == True
        assert is_binary_path("file.py") == False
        assert is_binary_path("file.js") == False
        assert is_binary_path("file.txt") == False
        
        # Test with real files
        with tempfile.NamedTemporaryFile(suffix=".py", mode='w', delete=False) as f:
            f.write("print('hello')")
            f.flush()
            assert is_binary_path(f.name) == False
            os.unlink(f.name)
        
        with tempfile.NamedTemporaryFile(suffix=".bin", mode='wb', delete=False) as f:
            f.write(b'\x00\x01\x02\x03')
            f.flush()
            assert is_binary_path(f.name) == True
            os.unlink(f.name)

    def test_list_source_files(self):
        """Test source file listing with filters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test structure
            (Path(temp_dir) / "src").mkdir()
            (Path(temp_dir) / "src" / "app.py").write_text("print('hello')")
            (Path(temp_dir) / "src" / "util.js").write_text("console.log('hello')")
            (Path(temp_dir) / "node_modules").mkdir()
            (Path(temp_dir) / "node_modules" / "lib.js").write_text("module.exports = {}")
            (Path(temp_dir) / "dist").mkdir()
            (Path(temp_dir) / "dist" / "bundle.js").write_text("minified code")
            
            files = list_source_files(temp_dir)
            
            # Should include src files
            assert "src/app.py" in files
            assert "src/util.js" in files
            
            # Should exclude node_modules and dist
            assert "node_modules/lib.js" not in files
            assert "dist/bundle.js" not in files
            
            # Test custom include patterns
            files = list_source_files(temp_dir, include_globs=["src/**"])
            assert "src/app.py" in files
            assert "src/util.js" in files

    def test_read_text_file(self):
        """Test text file reading with safety checks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = Path(temp_dir) / "test.py"
            content = "print('hello world')\n"
            test_file.write_text(content)
            
            # Normal read
            result = read_text_file(temp_dir, "test.py")
            assert result == content
            
            # Test file too large
            large_content = "x" * 2_000_000  # > 1.5MB
            large_file = Path(temp_dir) / "large.py"
            large_file.write_text(large_content)
            
            with pytest.raises(ValueError, match="File too large"):
                read_text_file(temp_dir, "large.py")
            
            # Test non-existent file
            with pytest.raises(ValueError, match="Not a file"):
                read_text_file(temp_dir, "nonexistent.py")


class TestParsing:
    """Test code parsing functions."""

    def test_detect_language(self):
        """Test language detection by extension."""
        assert detect_language("file.py") == "python"
        assert detect_language("file.js") == "javascript"
        assert detect_language("file.tsx") == "typescript"
        assert detect_language("file.sql") == "sql"
        assert detect_language("file.unknown") == "other"

    def test_extract_imports_python(self):
        """Test Python import extraction."""
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        imports = extract_imports(code, "python")
        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "typing" in imports

    def test_extract_imports_javascript(self):
        """Test JavaScript import extraction."""
        code = """
import React from 'react';
import { Component } from 'react';
const fs = require('fs');
import('./dynamic-module');
"""
        imports = extract_imports(code, "javascript")
        assert "react" in imports
        assert "fs" in imports
        assert "./dynamic-module" in imports

    def test_extract_imports_sql(self):
        """Test SQL table reference extraction."""
        code = """
SELECT * FROM users 
JOIN orders ON users.id = orders.user_id
FROM products
"""
        imports = extract_imports(code, "sql")
        assert "users" in imports
        assert "orders" in imports
        assert "products" in imports

    def test_find_symbols_python(self):
        """Test Python symbol extraction."""
        code = """
def hello_world():
    pass

class MyClass:
    def method(self):
        pass

async def async_func():
    pass
"""
        symbols = find_symbols(code, "python")
        assert "hello_world" in symbols
        assert "MyClass" in symbols
        assert "async_func" in symbols

    def test_find_symbols_javascript(self):
        """Test JavaScript symbol extraction."""
        code = """
function hello() {}
class MyClass {}
const arrow = () => {}
export function exported() {}
const funcExpr = function() {}
"""
        symbols = find_symbols(code, "javascript")
        assert "hello" in symbols
        assert "MyClass" in symbols
        assert "exported" in symbols
        assert "funcExpr" in symbols

    def test_find_symbols_sql(self):
        """Test SQL symbol extraction."""
        code = """
CREATE TABLE users (id INT PRIMARY KEY);
CREATE VIEW user_stats AS SELECT * FROM users;
CREATE FUNCTION get_user(id INT) RETURNS VARCHAR;
"""
        symbols = find_symbols(code, "sql")
        assert "users" in symbols
        assert "user_stats" in symbols
        assert "get_user" in symbols

    def test_split_code_windows(self):
        """Test code splitting into windows."""
        # Create text with many lines
        lines = [f"line {i}" for i in range(1, 101)]
        text = '\n'.join(lines)
        
        # Test with default chunk size
        windows = split_code_windows(text, "python", chunk_loc=30, overlap_loc=5)
        
        assert len(windows) > 1  # Should create multiple chunks
        
        # Check first window
        start, end, chunk_text = windows[0]
        assert start == 1
        assert end <= 30
        assert "line 1" in chunk_text
        
        # Check overlap between consecutive windows
        if len(windows) > 1:
            _, end1, _ = windows[0]
            start2, _, _ = windows[1]
            overlap = end1 - start2 + 1
            assert overlap >= 0  # Should have some overlap
        
        # Test single chunk for small files
        small_text = "line1\nline2\nline3"
        windows = split_code_windows(small_text, "python")
        assert len(windows) == 1
        assert windows[0] == (1, 3, small_text)
        
        # Test empty text
        windows = split_code_windows("", "python")
        assert windows == [(1, 1, "")]


class TestRepoIngestor:
    """Test repository ingestor."""

    def test_compute_hash(self):
        """Test text content hashing."""
        text1 = "hello\nworld  \n  test  "
        text2 = "hello\nworld\n  test"  # Same after normalization
        
        hash1 = compute_hash(text1)
        hash2 = compute_hash(text2)
        
        assert hash1 == hash2  # Should be same after stripping line endings
        assert len(hash1) == 40  # SHA1 hex length

    def test_get_git_commit(self):
        """Test git commit retrieval."""
        # Test non-git directory
        with tempfile.TemporaryDirectory() as temp_dir:
            commit = get_git_commit(temp_dir)
            assert commit == "workspace"

    def test_ingest_repo_full(self):
        """Test complete repository ingestion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test repository structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Create src/app.py with two functions and import
            app_py_content = """import os
import sys

def main():
    print("Hello World")
    
def helper_function():
    return "helper"
"""
            (src_dir / "app.py").write_text(app_py_content)
            
            # Create src/util/helpers.js
            util_dir = src_dir / "util"
            util_dir.mkdir()
            helpers_js_content = """import { libFunction } from "./lib/x";

function processData(data) {
    return libFunction(data);
}

export default processData;
"""
            (util_dir / "helpers.js").write_text(helpers_js_content)
            
            # Create src/db/schema.sql
            db_dir = src_dir / "db"
            db_dir.mkdir()
            schema_sql_content = """CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255)
);

CREATE VIEW active_users AS 
SELECT * FROM users WHERE active = 1;

SELECT name FROM users;
"""
            (db_dir / "schema.sql").write_text(schema_sql_content)
            
            # Run ingestion
            code_map, chunks = ingest_repo(temp_dir)
            
            # Test CodeMap
            assert isinstance(code_map, CodeMap)
            assert code_map.repo == os.path.basename(temp_dir)
            assert code_map.commit == "workspace"  # No git repo
            
            # Check files are present (posix style paths)
            expected_files = ["src/app.py", "src/util/helpers.js", "src/db/schema.sql"]
            for expected_file in expected_files:
                assert expected_file in code_map.files
            
            # Test dependencies
            assert "src/app.py" in code_map.deps
            assert "os" in code_map.deps["src/app.py"]
            assert "sys" in code_map.deps["src/app.py"]
            
            assert "src/util/helpers.js" in code_map.deps
            assert "./lib/x" in code_map.deps["src/util/helpers.js"]
            
            assert "src/db/schema.sql" in code_map.deps
            assert "users" in code_map.deps["src/db/schema.sql"]
            
            # Test symbol index
            assert "main" in code_map.symbol_index
            assert "src/app.py" in code_map.symbol_index["main"]
            
            assert "processData" in code_map.symbol_index
            assert "src/util/helpers.js" in code_map.symbol_index["processData"]
            
            assert "users" in code_map.symbol_index
            assert "src/db/schema.sql" in code_map.symbol_index["users"]
            
            # Test chunks
            assert len(chunks) >= 3  # At least one chunk per file
            
            for chunk in chunks:
                assert isinstance(chunk, Chunk)
                assert chunk.repo == code_map.repo
                assert chunk.commit == code_map.commit
                assert chunk.path in code_map.files
                assert chunk.lang in ["python", "javascript", "sql"]
                assert chunk.start_line >= 1
                assert chunk.end_line >= chunk.start_line
                assert len(chunk.text) > 0
                assert len(chunk.hash) == 40  # SHA1 hex length
                assert len(chunk.symbols) <= 50  # Limited as specified
                assert len(chunk.imports) <= 50  # Limited as specified
            
            # Test windowing respects chunk_loc default
            # Files should be chunked appropriately (not zero chunks, covers content)
            python_chunks = [c for c in chunks if c.lang == "python"]
            assert len(python_chunks) >= 1
            
            # Verify chunk content contains expected code
            app_chunks = [c for c in chunks if c.path == "src/app.py"]
            assert len(app_chunks) >= 1
            combined_text = "".join(c.text for c in app_chunks)
            assert "def main" in combined_text
            assert "def helper_function" in combined_text
            
            js_chunks = [c for c in chunks if c.path == "src/util/helpers.js"]
            assert len(js_chunks) >= 1
            combined_js = "".join(c.text for c in js_chunks)
            assert "processData" in combined_js
            
            sql_chunks = [c for c in chunks if c.path == "src/db/schema.sql"]
            assert len(sql_chunks) >= 1
            combined_sql = "".join(c.text for c in sql_chunks)
            assert "CREATE TABLE users" in combined_sql
            assert "CREATE VIEW active_users" in combined_sql