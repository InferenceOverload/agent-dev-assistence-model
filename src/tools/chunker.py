"""Structure-aware code chunking for various file types."""

import ast
import hashlib
import re
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path


class ChunkLike:
    """Chunk-like object with required attributes."""
    def __init__(self, text: str, start_line: int, end_line: int, path: str):
        self.text = text
        self.start_line = start_line
        self.end_line = end_line
        self.path = path
        self.id = f"{path}:{start_line}-{end_line}"
        self.hash = hashlib.sha1(text.encode('utf-8')).hexdigest()


def chunk_code(path: str, text: str) -> List[ChunkLike]:
    """
    Split code into structure-aware chunks based on language.
    
    Args:
        path: File path
        text: File content
        
    Returns:
        List of ChunkLike objects
    """
    if not text or not text.strip():
        return []
    
    # Skip binary files
    try:
        text.encode('utf-8')
    except UnicodeDecodeError:
        return []
    
    # Detect language from path
    lang = _detect_language(path)
    
    # Route to appropriate chunker
    if lang in ("python", "py"):
        chunks = _chunk_python(text)
    elif lang in ("javascript", "js", "typescript", "ts", "jsx", "tsx"):
        chunks = _chunk_javascript(text)
    elif lang in ("terraform", "tf", "hcl"):
        chunks = _chunk_terraform(text)
    elif lang in ("sql", "psql", "mysql", "plsql"):
        chunks = _chunk_sql(text)
    elif lang in ("markdown", "md"):
        chunks = _chunk_markdown(text)
    else:
        # Fallback to line-based chunking
        chunks = _chunk_by_lines(text)
    
    # Convert to ChunkLike objects
    result = []
    for start_line, end_line, chunk_text in chunks:
        if chunk_text.strip():  # Never emit empty chunks
            result.append(ChunkLike(
                text=chunk_text,
                start_line=start_line,
                end_line=end_line,
                path=path
            ))
    
    return result


def _detect_language(path: str) -> str:
    """Detect language from file path."""
    p = Path(path)
    ext = p.suffix.lower()
    
    lang_map = {
        '.py': 'python',
        '.pyx': 'python',
        '.pyi': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.tf': 'terraform',
        '.hcl': 'terraform',
        '.sql': 'sql',
        '.psql': 'sql',
        '.plsql': 'sql',
        '.md': 'markdown',
        '.markdown': 'markdown',
    }
    
    return lang_map.get(ext, 'unknown')


def _chunk_python(text: str) -> List[Tuple[int, int, str]]:
    """Chunk Python code using AST for def/class boundaries."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fall back to line-based if syntax error
        return _chunk_by_lines(text)
    
    # Collect all top-level nodes with their line ranges
    nodes = []
    
    for node in tree.body:
        if hasattr(node, 'lineno'):
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
            nodes.append((node.lineno, end_line))
    
    if not nodes:
        return _chunk_by_lines(text)
    
    # Process nodes, keeping imports with first code block
    import_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if hasattr(node, 'end_lineno'):
                import_end = max(import_end, node.end_lineno)
        else:
            break
    
    current_chunk = []
    current_start = 1
    
    for i, (start, end) in enumerate(nodes):
        node_lines = lines[start-1:end]
        node_text = ''.join(node_lines)
        
        # First non-import node: include imports
        if i == 0 or (import_end > 0 and start > import_end and current_start == 1):
            if import_end > 0:
                import_lines = lines[:import_end]
                node_lines = import_lines + node_lines
                node_text = ''.join(node_lines)
                current_start = 1
                end = max(end, import_end)
        
        # Check size (~600-800 tokens, using 2400-3200 chars as proxy)
        if len(node_text) > 3200:
            # Split large node
            if current_chunk:
                chunks.append((current_start, start - 1, ''.join(current_chunk)))
                current_chunk = []
            
            # Split the large node with overlap
            sub_chunks = _split_large_block(node_lines, start, target_size=2400, overlap_size=480)
            chunks.extend(sub_chunks)
            current_start = end + 1
        elif current_chunk and len(''.join(current_chunk)) + len(node_text) > 3200:
            # Save current chunk
            chunks.append((current_start, start - 1, ''.join(current_chunk)))
            current_chunk = node_lines
            current_start = start
        else:
            # Add to current chunk
            if not current_chunk:
                current_start = start
            current_chunk.extend(node_lines)
    
    # Add remaining chunk
    if current_chunk:
        chunks.append((current_start, current_start + len(current_chunk) - 1, ''.join(current_chunk)))
    
    return chunks


def _chunk_javascript(text: str) -> List[Tuple[int, int, str]]:
    """Chunk JavaScript/TypeScript by function/class/export."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Find structure boundaries
    boundaries = []
    import_end = 0
    
    for i, line in enumerate(lines, 1):
        # Track imports
        if re.match(r'^\s*(import|require)\s+', line):
            import_end = i
        # Find structural elements
        elif re.match(r'^\s*(export\s+)?(default\s+)?(function|class|const|let|var)\s+\w+', line):
            boundaries.append(i)
        elif re.match(r'^\s*export\s+(default\s+)?[\{\(]', line):
            boundaries.append(i)
    
    if not boundaries:
        return _chunk_by_lines(text)
    
    # Process boundaries, keeping imports with first block
    current_chunk = []
    current_start = 1
    
    # Add imports to first chunk
    if import_end > 0:
        current_chunk = lines[:import_end]
        current_start = 1
    
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines)
        
        # Skip if this is within import section
        if start <= import_end:
            continue
            
        block_lines = lines[start - 1:end]
        block_text = ''.join(block_lines)
        
        # Include imports with first code block
        if i == 0 and import_end > 0 and not current_chunk:
            current_chunk = lines[:import_end]
            current_start = 1
        
        # Check size
        if len(block_text) > 3200:
            # Save current chunk
            if current_chunk:
                chunks.append((current_start, start - 1, ''.join(current_chunk)))
                current_chunk = []
            
            # Split large block
            sub_chunks = _split_large_block(block_lines, start, target_size=2400, overlap_size=480)
            chunks.extend(sub_chunks)
            current_start = end + 1
        elif current_chunk and len(''.join(current_chunk)) + len(block_text) > 3200:
            # Save current chunk
            chunks.append((current_start, start - 1, ''.join(current_chunk)))
            current_chunk = block_lines
            current_start = start
        else:
            # Add to current chunk
            if not current_chunk:
                current_start = start
            current_chunk.extend(block_lines)
    
    # Add remaining chunk
    if current_chunk:
        chunks.append((current_start, current_start + len(current_chunk) - 1, ''.join(current_chunk)))
    
    return chunks


def _chunk_terraform(text: str) -> List[Tuple[int, int, str]]:
    """Chunk Terraform by resource/module/provider blocks."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Find block boundaries
    boundaries = []
    block_pattern = r'^\s*(resource|module|provider|data|variable|output|locals)\s+'
    
    for i, line in enumerate(lines, 1):
        if re.match(block_pattern, line):
            boundaries.append(i)
    
    if not boundaries:
        return _chunk_by_lines(text)
    
    # Process blocks
    current_chunk = []
    current_start = 1
    
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines)
        block_lines = lines[start - 1:end]
        block_text = ''.join(block_lines)
        
        # Check size
        if len(block_text) > 3200:
            # Save current chunk
            if current_chunk:
                chunks.append((current_start, start - 1, ''.join(current_chunk)))
                current_chunk = []
            
            # Split large block
            sub_chunks = _split_large_block(block_lines, start, target_size=2400, overlap_size=480)
            chunks.extend(sub_chunks)
            current_start = end + 1
        elif current_chunk and len(''.join(current_chunk)) + len(block_text) > 3200:
            # Save current chunk
            chunks.append((current_start, start - 1, ''.join(current_chunk)))
            current_chunk = block_lines
            current_start = start
        else:
            # Add to current chunk
            if not current_chunk:
                current_start = start
            current_chunk.extend(block_lines)
    
    # Add remaining chunk
    if current_chunk:
        chunks.append((current_start, current_start + len(current_chunk) - 1, ''.join(current_chunk)))
    
    return chunks


def _chunk_sql(text: str) -> List[Tuple[int, int, str]]:
    """Chunk SQL/PLSQL by CREATE statements."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Find CREATE statement boundaries
    boundaries = []
    create_pattern = r'^\s*CREATE\s+(OR\s+REPLACE\s+)?(TABLE|VIEW|FUNCTION|PROCEDURE|INDEX|TRIGGER|SCHEMA|DATABASE|PACKAGE)'
    
    for i, line in enumerate(lines, 1):
        if re.match(create_pattern, line, re.IGNORECASE):
            boundaries.append(i)
    
    if not boundaries:
        return _chunk_by_lines(text)
    
    # Process CREATE blocks
    current_chunk = []
    current_start = 1
    
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines)
        block_lines = lines[start - 1:end]
        block_text = ''.join(block_lines)
        
        # Check size
        if len(block_text) > 3200:
            # Save current chunk
            if current_chunk:
                chunks.append((current_start, start - 1, ''.join(current_chunk)))
                current_chunk = []
            
            # Split large block
            sub_chunks = _split_large_block(block_lines, start, target_size=2400, overlap_size=480)
            chunks.extend(sub_chunks)
            current_start = end + 1
        elif current_chunk and len(''.join(current_chunk)) + len(block_text) > 3200:
            # Save current chunk
            chunks.append((current_start, start - 1, ''.join(current_chunk)))
            current_chunk = block_lines
            current_start = start
        else:
            # Add to current chunk
            if not current_chunk:
                current_start = start
            current_chunk.extend(block_lines)
    
    # Add remaining chunk
    if current_chunk:
        chunks.append((current_start, current_start + len(current_chunk) - 1, ''.join(current_chunk)))
    
    return chunks


def _chunk_markdown(text: str) -> List[Tuple[int, int, str]]:
    """Chunk Markdown by headings, merging tiny sections."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Find heading boundaries
    sections = []
    current_section = []
    current_start = 1
    
    heading_pattern = r'^#{1,6}\s+'
    
    for i, line in enumerate(lines, 1):
        if re.match(heading_pattern, line):
            # Save previous section
            if current_section:
                sections.append((current_start, i - 1, ''.join(current_section)))
            current_section = [line]
            current_start = i
        else:
            current_section.append(line)
    
    # Add last section
    if current_section:
        sections.append((current_start, len(lines), ''.join(current_section)))
    
    if not sections:
        return _chunk_by_lines(text)
    
    # Merge tiny sections (less than 200 chars)
    merged = []
    current_chunk = []
    current_start = None
    
    for start, end, section_text in sections:
        if current_start is None:
            current_start = start
        
        # Always start new chunk at # (H1) headings
        if section_text.startswith('# ') and current_chunk:
            merged.append((current_start, end - 1, ''.join(c[2] for c in current_chunk)))
            current_chunk = [(start, end, section_text)]
            current_start = start
        # Check if adding would exceed size
        elif current_chunk and len(''.join(c[2] for c in current_chunk)) + len(section_text) > 3200:
            merged.append((current_start, current_chunk[-1][1], ''.join(c[2] for c in current_chunk)))
            current_chunk = [(start, end, section_text)]
            current_start = start
        else:
            current_chunk.append((start, end, section_text))
    
    # Add remaining sections
    if current_chunk:
        merged.append((current_start, current_chunk[-1][1], ''.join(c[2] for c in current_chunk)))
    
    return merged


def _chunk_by_lines(text: str, target_size: int = 2400, overlap_size: int = 480) -> List[Tuple[int, int, str]]:
    """Fallback line-based chunking with overlap."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    if not lines:
        return []
    
    # Estimate lines per chunk (assuming ~80 chars per line)
    lines_per_chunk = max(1, target_size // 80)
    overlap_lines = max(1, overlap_size // 80)
    
    i = 0
    while i < len(lines):
        chunk_end = min(i + lines_per_chunk, len(lines))
        chunk_lines = lines[i:chunk_end]
        chunk_text = ''.join(chunk_lines)
        
        chunks.append((i + 1, chunk_end, chunk_text))
        
        # Move forward with overlap
        i += lines_per_chunk - overlap_lines
        if i >= len(lines) - overlap_lines:
            break
    
    return chunks


def _split_large_block(lines: List[str], start_line: int, 
                       target_size: int = 2400, overlap_size: int = 480) -> List[Tuple[int, int, str]]:
    """Split a large block into smaller chunks with overlap."""
    chunks = []
    
    # Estimate lines per chunk
    lines_per_chunk = max(1, target_size // 80)
    overlap_lines = max(1, overlap_size // 80)
    
    i = 0
    while i < len(lines):
        chunk_end = min(i + lines_per_chunk, len(lines))
        chunk_lines = lines[i:chunk_end]
        chunk_text = ''.join(chunk_lines)
        
        actual_start = start_line + i
        actual_end = start_line + chunk_end - 1
        chunks.append((actual_start, actual_end, chunk_text))
        
        i += lines_per_chunk - overlap_lines
        if i >= len(lines) - overlap_lines:
            break
    
    return chunks