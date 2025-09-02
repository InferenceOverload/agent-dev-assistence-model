"""Repository sizing and analysis tool.

Provides functionality to measure repository size, estimate token counts,
and compute chunking requirements for vector search and RAG applications.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List
from math import ceil

from pydantic import BaseModel


class SizerReport(BaseModel):
    """Report containing comprehensive repository size and analysis metrics."""
    
    repo: str
    commit: str
    file_count: int
    loc_total: int
    bytes_total: int
    lang_breakdown: Dict[str, Dict[str, int]]
    avg_file_loc: float
    max_file_loc: int
    estimated_tokens_repo: int
    chunk_estimate: int
    vector_count_estimate: int


# Language extension mappings
LANGUAGE_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.cpp': 'cpp',
    '.cxx': 'cpp',
    '.cc': 'cpp',
    '.c': 'c',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.rb': 'ruby',
    '.go': 'go',
    '.rs': 'rust',
    '.php': 'php',
    '.scala': 'scala',
    '.kt': 'kotlin',
    '.swift': 'swift',
    '.sh': 'shell',
    '.bash': 'shell',
    '.zsh': 'shell',
    '.sql': 'sql',
    '.md': 'markdown',
    '.txt': 'text',
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.json': 'json',
    '.xml': 'xml',
    '.html': 'html',
    '.css': 'css',
    '.scss': 'css',
    '.sass': 'css',
    '.r': 'r',
    '.R': 'r',
    '.m': 'matlab',
    '.pl': 'perl',
    '.lua': 'lua',
    '.dart': 'dart',
    '.vim': 'vim',
    '.clj': 'clojure',
    '.cljs': 'clojure',
    '.ex': 'elixir',
    '.exs': 'elixir',
}

# Directories/files to ignore
IGNORE_PATTERNS = {
    # Version control
    '.git', '.svn', '.hg', '.bzr',
    # Dependencies
    'node_modules', 'vendor', 'venv', '.venv', '__pycache__',
    # Build outputs
    'build', 'dist', 'target', 'bin', 'obj', 'out',
    # IDE/Editor
    '.vscode', '.idea', '.sublime-project', '.sublime-workspace',
    # OS
    '.DS_Store', 'Thumbs.db',
    # Logs and temps
    'logs', 'tmp', 'temp', '.tmp',
    # Package managers
    '.npm', '.yarn', '.pnpm-store',
}

# File patterns to ignore (lockfiles, binaries, etc.)
IGNORE_FILE_PATTERNS = {
    'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock',
    'Cargo.lock', 'go.sum', 'composer.lock',
}


def estimate_tokens(char_count: int) -> int:
    """Estimate token count from character count.
    
    Args:
        char_count: Number of characters
        
    Returns:
        Estimated token count (chars // 4)
    """
    return char_count // 4


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_EXTENSIONS.get(ext, 'unknown')


def _should_ignore_path(path: str) -> bool:
    """Check if a path should be ignored based on ignore patterns."""
    path_parts = Path(path).parts
    
    # Check if any part of the path matches ignore patterns
    for part in path_parts:
        if part in IGNORE_PATTERNS:
            return True
    
    # Check filename patterns
    filename = Path(path).name
    if filename in IGNORE_FILE_PATTERNS:
        return True
        
    return False


def _is_text_file(file_path: str) -> bool:
    """Check if a file is likely a text file based on extension."""
    ext = Path(file_path).suffix.lower()
    
    # Known text extensions
    text_extensions = set(LANGUAGE_EXTENSIONS.keys())
    text_extensions.update({
        '.txt', '.md', '.rst', '.tex', '.log', '.cfg', '.conf', '.ini',
        '.toml', '.lock', '.gitignore', '.gitattributes', '.editorconfig',
        '.dockerignore', '.env', '.example', '.sample'
    })
    
    return ext in text_extensions or ext == '' and not '.' in Path(file_path).stem


def _count_lines(file_content: str) -> int:
    """Count non-empty lines in file content."""
    return len([line for line in file_content.splitlines() if line.strip()])


def _get_git_commit(root: str) -> str:
    """Get short git commit hash, or return 'workspace' if not a git repo."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
    return 'workspace'


def measure_repo(
    root: str, 
    files: List[str], 
    chunk_loc: int = 300, 
    overlap_loc: int = 50
) -> SizerReport:
    """Measure repository size and compute analysis metrics.
    
    Args:
        root: Root directory path
        files: List of relative file paths to analyze
        chunk_loc: Lines of code per chunk for estimation
        overlap_loc: Overlap between chunks in lines
        
    Returns:
        SizerReport with comprehensive repository metrics
    """
    root_path = Path(root)
    repo_name = root_path.name
    commit = _get_git_commit(root)
    
    # Initialize counters
    file_count = 0
    loc_total = 0
    bytes_total = 0
    max_file_loc = 0
    lang_breakdown: Dict[str, Dict[str, int]] = {}
    total_chars = 0
    chunk_estimate = 0
    
    # Process each file
    for file_rel_path in files:
        # Skip ignored paths
        if _should_ignore_path(file_rel_path):
            continue
            
        file_path = root_path / file_rel_path
        
        # Skip if file doesn't exist or is not a text file
        if not file_path.exists() or not file_path.is_file():
            continue
            
        if not _is_text_file(str(file_path)):
            continue
        
        try:
            # Read file safely with error handling
            with file_path.open('r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Get file size in bytes
            file_bytes = len(content.encode('utf-8'))
            bytes_total += file_bytes
            total_chars += len(content)
            
            # Count lines of code
            file_loc = _count_lines(content)
            loc_total += file_loc
            max_file_loc = max(max_file_loc, file_loc)
            
            # Update language breakdown
            language = _detect_language(file_rel_path)
            if language not in lang_breakdown:
                lang_breakdown[language] = {'files': 0, 'loc': 0}
            lang_breakdown[language]['files'] += 1
            lang_breakdown[language]['loc'] += file_loc
            
            # Estimate chunks for this file
            if file_loc == 0:
                file_chunk_count = 1  # Empty files still get 1 chunk
            else:
                effective_chunk_size = max(1, chunk_loc - overlap_loc)
                file_chunk_count = max(1, ceil(file_loc / effective_chunk_size))
            
            chunk_estimate += file_chunk_count
            file_count += 1
            
        except (IOError, UnicodeDecodeError, PermissionError):
            # Skip files that can't be read
            continue
    
    # Calculate averages
    avg_file_loc = loc_total / file_count if file_count > 0 else 0.0
    
    # Estimate tokens
    estimated_tokens_repo = estimate_tokens(total_chars)
    
    # Vector count estimate equals chunk estimate
    vector_count_estimate = chunk_estimate
    
    return SizerReport(
        repo=repo_name,
        commit=commit,
        file_count=file_count,
        loc_total=loc_total,
        bytes_total=bytes_total,
        lang_breakdown=lang_breakdown,
        avg_file_loc=round(avg_file_loc, 2),
        max_file_loc=max_file_loc,
        estimated_tokens_repo=estimated_tokens_repo,
        chunk_estimate=chunk_estimate,
        vector_count_estimate=vector_count_estimate
    )