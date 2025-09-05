"""Tests for structure-aware code chunking."""

import pytest
from src.tools.chunker import chunk_code


class TestPythonChunking:
    """Test Python code chunking."""
    
    def test_chunk_python_functions(self):
        """Test chunking Python code with functions."""
        code = '''def hello():
    """Say hello."""
    print("Hello, World!")

def goodbye():
    """Say goodbye."""
    print("Goodbye!")
    
class Greeter:
    def __init__(self, name):
        self.name = name
    
    def greet(self):
        print(f"Hello, {self.name}!")
'''
        chunks = chunk_code("test.py", code, "python", "test", "abc123")
        
        # Should create chunks for functions and class
        assert len(chunks) > 0
        
        # Check that chunks have proper metadata
        for chunk in chunks:
            assert chunk.path == "test.py"
            assert chunk.lang == "python"
            assert chunk.repo == "test"
            assert chunk.commit == "abc123"
            assert chunk.text.strip()  # No empty chunks
            
        # Check symbols are extracted
        all_symbols = []
        for chunk in chunks:
            all_symbols.extend(chunk.symbols)
        assert "hello" in all_symbols or "goodbye" in all_symbols or "Greeter" in all_symbols
    
    def test_chunk_large_python_function(self):
        """Test splitting large Python functions."""
        # Create a large function
        lines = ['def large_function():']
        lines.append('    """A very large function."""')
        for i in range(200):  # Make it large
            lines.append(f'    print("Line {i}")')
        lines.append('    return None')
        
        code = '\n'.join(lines)
        chunks = chunk_code("large.py", code, "python")
        
        # Should split into multiple chunks
        assert len(chunks) >= 2
        
        # Each chunk should have reasonable size
        for chunk in chunks:
            assert len(chunk.text) < 4000  # ~1000 tokens
    
    def test_empty_python_file(self):
        """Test handling empty Python file."""
        chunks = chunk_code("empty.py", "", "python")
        assert len(chunks) == 0
        
        chunks = chunk_code("whitespace.py", "   \n\n  ", "python")
        assert len(chunks) == 0


class TestJavaScriptChunking:
    """Test JavaScript/TypeScript code chunking."""
    
    def test_chunk_javascript_functions(self):
        """Test chunking JavaScript with various function styles."""
        code = '''// Utility functions
export function add(a, b) {
    return a + b;
}

export const multiply = (a, b) => {
    return a * b;
};

class Calculator {
    constructor() {
        this.result = 0;
    }
    
    calculate(a, b) {
        return this.add(a, b);
    }
}

export default Calculator;
'''
        chunks = chunk_code("calc.js", code, "javascript")
        
        assert len(chunks) > 0
        
        # Check symbols extraction
        all_symbols = []
        for chunk in chunks:
            all_symbols.extend(chunk.symbols)
        
        # Should find at least some symbols
        assert "add" in all_symbols or "multiply" in all_symbols or "Calculator" in all_symbols
    
    def test_chunk_typescript_with_types(self):
        """Test TypeScript with type annotations."""
        code = '''interface User {
    id: number;
    name: string;
}

export async function getUser(id: number): Promise<User> {
    const response = await fetch(`/api/users/${id}`);
    return response.json();
}

export class UserService {
    async getAll(): Promise<User[]> {
        return [];
    }
}
'''
        chunks = chunk_code("user.ts", code, "typescript")
        
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.text.strip()


class TestTerraformChunking:
    """Test Terraform code chunking."""
    
    def test_chunk_terraform_resources(self):
        """Test chunking Terraform with resources and modules."""
        code = '''provider "aws" {
  region = "us-west-2"
}

resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
  
  tags = {
    Name = "WebServer"
  }
}

module "vpc" {
  source = "./modules/vpc"
  
  cidr_block = "10.0.0.0/16"
}

resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}
'''
        chunks = chunk_code("main.tf", code, "terraform")
        
        assert len(chunks) > 0
        
        # Each resource/module should be in its own chunk or grouped
        for chunk in chunks:
            assert chunk.text.strip()
            # Check it contains terraform keywords
            text_lower = chunk.text.lower()
            assert any(keyword in text_lower for keyword in ['provider', 'resource', 'module'])


class TestSQLChunking:
    """Test SQL code chunking."""
    
    def test_chunk_sql_tables(self):
        """Test chunking SQL with CREATE statements."""
        code = '''-- User tables
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(200),
    content TEXT,
    published BOOLEAN DEFAULT false
);

CREATE VIEW active_users AS
SELECT * FROM users
WHERE last_login > NOW() - INTERVAL '30 days';

CREATE FUNCTION get_user_posts(user_id INTEGER)
RETURNS TABLE(title VARCHAR, content TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT title, content FROM posts WHERE user_id = user_id;
END;
$$ LANGUAGE plpgsql;
'''
        chunks = chunk_code("schema.sql", code, "sql")
        
        assert len(chunks) > 0
        
        # Check symbols extraction
        all_symbols = []
        for chunk in chunks:
            all_symbols.extend(chunk.symbols)
        
        # Should find table/view names
        assert any(s.lower() in ['users', 'posts', 'active_users'] for s in all_symbols)


class TestMarkdownChunking:
    """Test Markdown document chunking."""
    
    def test_chunk_markdown_headings(self):
        """Test chunking Markdown by headings."""
        code = '''# Project Title

This is the introduction to the project.

## Installation

Install using pip:
```bash
pip install myproject
```

## Usage

Here's how to use it:

```python
import myproject
myproject.run()
```

### Advanced Usage

For advanced users...

## Contributing

Please read CONTRIBUTING.md

### Code Style

We use black for formatting.

### Testing

Run tests with pytest.
'''
        chunks = chunk_code("README.md", code, "markdown")
        
        assert len(chunks) > 0
        
        # Should group small sections but respect heading structure
        for chunk in chunks:
            assert chunk.text.strip()
            # Each chunk should start with or contain a heading
            assert '#' in chunk.text
    
    def test_merge_tiny_markdown_sections(self):
        """Test that tiny markdown sections are merged."""
        code = '''# Title

Short intro.

## A

One line.

## B 

Another line.

## C

Yet another.

# Big Section

This section has a lot more content that goes on for multiple lines
and paragraphs with various details about the implementation and
design decisions that were made during development.
'''
        chunks = chunk_code("doc.md", code, "markdown")
        
        # Tiny sections should be merged
        assert len(chunks) <= 3  # Should merge tiny sections


class TestFallbackChunking:
    """Test fallback line-based chunking."""
    
    def test_unknown_language_fallback(self):
        """Test that unknown languages use line-based chunking."""
        code = "Line 1\n" * 300  # 300 lines
        
        chunks = chunk_code("file.xyz", code, "unknown")
        
        assert len(chunks) > 1  # Should split into multiple chunks
        
        # Check overlap
        if len(chunks) > 1:
            # Later chunks should have some overlap with previous
            assert chunks[0].end_line >= chunks[1].start_line - 30
    
    def test_binary_file_handling(self):
        """Test handling files with invalid UTF-8."""
        # This would be binary data in practice
        code = "Normal text\n" + "More text\n" * 50
        
        chunks = chunk_code("file.bin", code, "binary")
        
        # Should handle gracefully
        assert len(chunks) >= 1


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_syntax_error_python(self):
        """Test Python with syntax errors falls back gracefully."""
        code = '''def broken(
    print "missing closing paren"
    
def another():
    return 42
'''
        chunks = chunk_code("broken.py", code, "python")
        
        # Should still produce chunks using fallback
        assert len(chunks) > 0
    
    def test_mixed_content(self):
        """Test file with mixed content types."""
        code = '''# Documentation

Some docs here.

```python
def example():
    return True
```

More documentation.

```sql
SELECT * FROM users;
```
'''
        chunks = chunk_code("mixed.md", code, "markdown")
        
        assert len(chunks) > 0
        # Should handle code blocks within markdown
    
    def test_very_long_lines(self):
        """Test handling very long lines."""
        long_line = "x = '" + "a" * 5000 + "'"
        code = f"def func():\n    {long_line}\n    return x"
        
        chunks = chunk_code("long.py", code, "python")
        
        assert len(chunks) > 0
        # Should handle without error
    
    def test_unicode_content(self):
        """Test handling unicode content."""
        code = '''def hello():
    """Say hello in multiple languages."""
    print("Hello 你好 مرحبا こんにちは")
    print("Émojis: 🎉 🚀 ✨")
'''
        chunks = chunk_code("unicode.py", code, "python")
        
        assert len(chunks) > 0
        # Should preserve unicode
        assert "你好" in chunks[0].text
        assert "🎉" in chunks[0].text


class TestChunkMetadata:
    """Test chunk metadata extraction."""
    
    def test_python_imports_extraction(self):
        """Test extraction of Python imports."""
        code = '''import os
from pathlib import Path
from typing import List, Dict
import numpy as np

def process():
    return Path.cwd()
'''
        chunks = chunk_code("test.py", code, "python")
        
        assert len(chunks) > 0
        # Check imports are extracted
        all_imports = []
        for chunk in chunks:
            all_imports.extend(chunk.imports)
        
        assert "os" in all_imports
        assert "pathlib" in all_imports
        assert "typing" in all_imports
        assert "numpy" in all_imports
    
    def test_javascript_imports_extraction(self):
        """Test extraction of JavaScript imports."""
        code = '''import React from 'react';
import { useState, useEffect } from 'react';
const lodash = require('lodash');

export function Component() {
    return <div>Hello</div>;
}
'''
        chunks = chunk_code("component.jsx", code, "javascript")
        
        assert len(chunks) > 0
        all_imports = []
        for chunk in chunks:
            all_imports.extend(chunk.imports)
        
        assert "react" in all_imports
        assert "lodash" in all_imports
    
    def test_chunk_id_generation(self):
        """Test that chunk IDs are unique and informative."""
        code = '''def func1():
    pass

def func2():
    pass
'''
        chunks = chunk_code("test.py", code, "python", "myrepo", "abc123")
        
        assert len(chunks) > 0
        
        # Check IDs are unique
        ids = [chunk.id for chunk in chunks]
        assert len(ids) == len(set(ids))
        
        # Check ID format
        for chunk in chunks:
            assert "test.py" in chunk.id
            assert ":" in chunk.id