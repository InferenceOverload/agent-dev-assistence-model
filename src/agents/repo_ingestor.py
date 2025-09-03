"""Repository Ingestor - ingest repo files, build CodeMap and Chunks."""

import os
import subprocess
import hashlib
from pathlib import Path
from typing import Tuple, List

from ..core.types import Chunk, CodeMap
from ..tools.repo_io import list_source_files, read_text_file
from ..tools.parsing import detect_language, extract_imports, find_symbols, split_code_windows


def get_git_commit(root: str) -> str:
    """Get the current git commit SHA or fallback to 'workspace'.
    
    Args:
        root: Repository root path
    
    Returns:
        Short commit SHA or 'workspace' if not a git repository
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
    
    return "workspace"


def compute_hash(text: str) -> str:
    """Compute SHA1 hash of normalized text content.
    
    Args:
        text: Text content to hash
    
    Returns:
        SHA1 hash as hexadecimal string
    """
    # Normalize text: strip spaces at end of lines
    normalized_lines = [line.rstrip() for line in text.splitlines()]
    normalized_text = '\n'.join(normalized_lines)
    
    return hashlib.sha1(normalized_text.encode('utf-8')).hexdigest()


def ingest_repo(root: str = ".") -> Tuple[CodeMap, List[Chunk]]:
    """Ingest repository files and create CodeMap and Chunks.
    
    Args:
        root: Repository root path
    
    Returns:
        Tuple of (CodeMap, list of Chunks)
    """
    # Step 1: Get files and basic info
    files = list_source_files(root)
    commit = get_git_commit(root)
    repo = os.path.basename(os.path.abspath(root))
    
    # Initialize collections
    all_chunks = []
    deps = {}
    symbol_index = {}
    processed_files = []
    
    # Step 3: Process each file
    for file_path in files:
        try:
            # Read file content
            text = read_text_file(root, file_path)
            
            # Get language and metadata
            lang = detect_language(file_path)
            symbols = find_symbols(text, lang)
            imports = extract_imports(text, lang)
            
            # Split into windows/chunks
            windows = split_code_windows(text, lang)
            
            # Create chunks for each window
            for start_line, end_line, chunk_text in windows:
                chunk_id = f"{repo}:{commit}:{file_path}#{start_line}-{end_line}"
                
                chunk = Chunk(
                    id=chunk_id,
                    repo=repo,
                    commit=commit,
                    path=file_path,
                    lang=lang,
                    start_line=start_line,
                    end_line=end_line,
                    text=chunk_text,
                    symbols=symbols[:50],  # Limit to 50 symbols
                    imports=imports[:50],  # Limit to 50 imports
                    neighbors=[],  # Will be populated later if needed
                    hash=compute_hash(chunk_text)
                )
                
                all_chunks.append(chunk)
            
            # Build dependencies map
            deps[file_path] = imports
            
            # Build symbol index: symbol -> [files that define it]
            for symbol in symbols:
                if symbol not in symbol_index:
                    symbol_index[symbol] = []
                if file_path not in symbol_index[symbol]:
                    symbol_index[symbol].append(file_path)
            
            processed_files.append(file_path)
            
        except (ValueError, OSError) as e:
            # Skip files that can't be read (binary, too large, etc.)
            print(f"Skipping file {file_path}: {e}")
            continue
    
    # Create CodeMap
    code_map = CodeMap(
        repo=repo,
        commit=commit,
        files=processed_files,
        deps=deps,
        symbol_index=symbol_index
    )
    
    return code_map, all_chunks