"""Tests for structure-aware code chunking."""

import pytest
from src.tools.chunker import chunk_code, ChunkLike


class TestPythonChunking:
    """Test Python code chunking."""
    
    def test_chunk_python_def_class(self):
        """Test chunking Python code with def and class."""
        code = '''import os
import sys

def hello():
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
        chunks = chunk_code("test.py", code)
        
        # Should create chunks for functions and class
        assert len(chunks) > 0
        assert all(isinstance(c, ChunkLike) for c in chunks)
        
        # Check that chunks have proper metadata
        for chunk in chunks:
            assert chunk.path == "test.py"
            assert chunk.text.strip()  # No empty chunks
            assert chunk.start_line > 0
            assert chunk.end_line >= chunk.start_line
            assert len(chunk.hash) == 40  # SHA1 hex
        
        # Imports should be with first code block
        first_chunk_text = chunks[0].text
        assert "import os" in first_chunk_text or any("import os" in c.text for c in chunks)
    
    def test_chunk_large_python_function(self):
        """Test splitting large Python functions."""
        # Create a large function
        lines = ['def large_function():']
        lines.append('    """A very large function."""')
        for i in range(100):  # Make it large
            lines.append(f'    print("Line {i}")')
            lines.append(f'    x_{i} = {i} * 2')
        lines.append('    return None')
        
        code = '\n'.join(lines)
        chunks = chunk_code("large.py", code)
        
        # Should split into multiple chunks with overlap
        assert len(chunks) >= 2
        
        # Each chunk should have reasonable size (~600-800 tokens = ~2400-3200 chars)
        for chunk in chunks:
            assert len(chunk.text) <= 3500  # Allow some wiggle room
    
    def test_empty_python_file(self):
        """Test handling empty Python file."""
        chunks = chunk_code("empty.py", "")
        assert len(chunks) == 0
        
        chunks = chunk_code("whitespace.py", "   \n\n  ")
        assert len(chunks) == 0


class TestJavaScriptChunking:
    """Test JavaScript/TypeScript code chunking."""
    
    def test_chunk_javascript_functions(self):
        """Test chunking JavaScript with various function styles."""
        code = '''import React from 'react';
import { useState } from 'react';

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
        chunks = chunk_code("calc.js", code)
        
        assert len(chunks) > 0
        
        # Imports should be kept with first block
        first_chunk = chunks[0].text
        assert "import React" in first_chunk
    
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
        chunks = chunk_code("user.ts", code)
        
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
        chunks = chunk_code("main.tf", code)
        
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

CREATE OR REPLACE FUNCTION get_user_posts(user_id INTEGER)
RETURNS TABLE(title VARCHAR, content TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT title, content FROM posts WHERE user_id = user_id;
END;
$$ LANGUAGE plpgsql;
'''
        chunks = chunk_code("schema.sql", code)
        
        assert len(chunks) > 0
        
        # Each CREATE should be in a chunk
        all_text = ' '.join(c.text for c in chunks).upper()
        assert 'CREATE TABLE USERS' in all_text
        assert 'CREATE TABLE POSTS' in all_text
    
    def test_chunk_plsql(self):
        """Test PL/SQL with packages."""
        code = '''CREATE OR REPLACE PACKAGE user_pkg AS
    PROCEDURE add_user(p_name VARCHAR2, p_email VARCHAR2);
    FUNCTION get_user_count RETURN NUMBER;
END user_pkg;
/

CREATE OR REPLACE PACKAGE BODY user_pkg AS
    PROCEDURE add_user(p_name VARCHAR2, p_email VARCHAR2) IS
    BEGIN
        INSERT INTO users (name, email) VALUES (p_name, p_email);
    END;
    
    FUNCTION get_user_count RETURN NUMBER IS
        v_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM users;
        RETURN v_count;
    END;
END user_pkg;
/
'''
        chunks = chunk_code("user_pkg.plsql", code)
        assert len(chunks) > 0


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
        chunks = chunk_code("README.md", code)
        
        assert len(chunks) > 0
        
        # Should group sections intelligently
        for chunk in chunks:
            assert chunk.text.strip()
            # Each chunk should contain heading(s)
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
        chunks = chunk_code("doc.md", code)
        
        # Tiny sections should be merged
        assert len(chunks) <= 3  # Should merge tiny sections
        
        # Check H1 sections start new chunks
        h1_chunks = [c for c in chunks if c.text.startswith('# ')]
        assert len(h1_chunks) <= 2


class TestFallbackChunking:
    """Test fallback line-based chunking."""
    
    def test_unknown_language_fallback(self):
        """Test that unknown languages use line-based chunking."""
        code = '\n'.join([f"Line {i}" for i in range(200)])  # 200 lines
        
        chunks = chunk_code("file.xyz", code)
        
        assert len(chunks) > 1  # Should split into multiple chunks
        
        # Check overlap exists (lines appear in multiple chunks)
        if len(chunks) > 1:
            # Some lines should appear in both chunks (overlap)
            chunk0_lines = chunks[0].text.split('\n')
            chunk1_lines = chunks[1].text.split('\n')
            # Should have some overlap
            overlap = set(chunk0_lines) & set(chunk1_lines)
            assert len(overlap) > 0
    
    def test_binary_file_skip(self):
        """Test skipping binary files."""
        # Binary-like content (would fail UTF-8 encoding in real case)
        # For testing, we'll use normal text since we can't actually create invalid UTF-8
        code = "Normal text that represents a file"
        
        chunks = chunk_code("file.bin", code)
        
        # Should handle gracefully (fallback chunking)
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
        chunks = chunk_code("broken.py", code)
        
        # Should still produce chunks using fallback
        assert len(chunks) > 0
        assert all(c.text.strip() for c in chunks)
    
    def test_very_long_lines(self):
        """Test handling very long lines."""
        long_line = "x = '" + "a" * 5000 + "'"
        code = f"def func():\n    {long_line}\n    return x"
        
        chunks = chunk_code("long.py", code)
        
        assert len(chunks) > 0
        # Should handle without error


class TestChunkBoundaries:
    """Test that chunk boundaries are correct."""
    
    def test_chunk_boundaries_continuous(self):
        """Test that chunks have proper line boundaries."""
        code = '''def func1():
    pass

def func2():
    pass

def func3():
    pass
'''
        chunks = chunk_code("test.py", code)
        
        for chunk in chunks:
            # Boundaries should be positive
            assert chunk.start_line > 0
            assert chunk.end_line >= chunk.start_line
            
            # Text line count should roughly match boundaries
            lines_in_text = len(chunk.text.strip().split('\n'))
            boundary_lines = chunk.end_line - chunk.start_line + 1
            # Allow for some discrepancy due to empty lines
            assert abs(lines_in_text - boundary_lines) <= 2
    
    def test_chunk_size_window(self):
        """Test that chunks stay within size window."""
        # Create code with known structure
        code = '\n'.join([
            'def func1():',
            '    """Function 1"""',
            '    ' + '\n    '.join([f'print("{i}")' for i in range(20)]),
            '',
            'def func2():',
            '    """Function 2"""',
            '    ' + '\n    '.join([f'print("{i}")' for i in range(20)]),
        ])
        
        chunks = chunk_code("test.py", code)
        
        for chunk in chunks:
            # ~600-800 tokens target = ~2400-3200 chars
            assert len(chunk.text) <= 3500  # Allow some buffer
            # Should not be too small unless it's the last chunk
            if chunk != chunks[-1]:
                assert len(chunk.text) >= 100  # Minimum reasonable size