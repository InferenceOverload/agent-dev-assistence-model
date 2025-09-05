"""Structure-aware code chunking for various file types."""

import ast
import hashlib
import re
from typing import List, Tuple, Optional
from pathlib import Path

from ..core.types import Chunk


def chunk_code(path: str, text: str, lang: str, repo: str = "", commit: str = "") -> List[Chunk]:
    """
    Split code into structure-aware chunks based on language.
    
    Args:
        path: File path
        text: File content
        lang: Language identifier (python, javascript, typescript, terraform, sql, markdown)
        repo: Repository name
        commit: Commit hash
        
    Returns:
        List of Chunk objects
    """
    if not text or not text.strip():
        return []
    
    # Normalize language
    lang_lower = lang.lower()
    
    # Route to appropriate chunker
    if lang_lower in ("python", "py"):
        chunks = _chunk_python(text)
    elif lang_lower in ("javascript", "js", "typescript", "ts", "jsx", "tsx"):
        chunks = _chunk_javascript(text)
    elif lang_lower in ("terraform", "tf", "hcl"):
        chunks = _chunk_terraform(text)
    elif lang_lower in ("sql", "psql", "mysql"):
        chunks = _chunk_sql(text)
    elif lang_lower in ("markdown", "md"):
        chunks = _chunk_markdown(text)
    else:
        # Fallback to line-based chunking
        chunks = _chunk_by_lines(text)
    
    # Convert to Chunk objects with metadata
    result = []
    for i, (start_line, end_line, chunk_text) in enumerate(chunks):
        if not chunk_text.strip():
            continue
            
        # Extract symbols (function/class names)
        symbols = _extract_symbols(chunk_text, lang_lower)
        
        # Extract imports
        imports = _extract_imports(chunk_text, lang_lower)
        
        # Create chunk ID
        chunk_id = f"{path}:{start_line}-{end_line}"
        
        result.append(Chunk(
            id=chunk_id,
            repo=repo,
            commit=commit,
            path=path,
            lang=lang,
            start_line=start_line,
            end_line=end_line,
            text=chunk_text,
            symbols=symbols,
            imports=imports,
            neighbors=[],  # Will be populated by caller
            hash=hashlib.sha1(chunk_text.encode('utf-8')).hexdigest()
        ))
    
    return result


def _chunk_python(text: str) -> List[Tuple[int, int, str]]:
    """Chunk Python code using AST for def/class boundaries."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fall back to line-based if syntax error
        return _chunk_by_lines(text)
    
    # Track top-level definitions
    definitions = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Only consider top-level or class-level definitions
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                definitions.append((node.lineno, node.end_lineno or node.lineno, node.name))
    
    # Sort by start line
    definitions.sort()
    
    # Group definitions and limit chunk size
    current_chunk_start = 1
    current_chunk_lines = []
    
    for start, end, name in definitions:
        # Get lines for this definition
        def_lines = lines[start-1:end]
        def_text = ''.join(def_lines)
        
        # If definition is too large, split it
        if len(def_text) > 3200:  # ~800 tokens
            # Add what we have so far
            if current_chunk_lines:
                chunk_text = ''.join(current_chunk_lines)
                chunks.append((current_chunk_start, start - 1, chunk_text))
                current_chunk_lines = []
            
            # Split large definition into smaller chunks
            sub_chunks = _split_large_block(def_lines, start)
            chunks.extend(sub_chunks)
            current_chunk_start = end + 1
        else:
            # Add to current chunk if it fits
            if current_chunk_lines and len(''.join(current_chunk_lines)) + len(def_text) > 3200:
                # Save current chunk
                chunk_text = ''.join(current_chunk_lines)
                chunk_end = start - 1
                chunks.append((current_chunk_start, chunk_end, chunk_text))
                current_chunk_lines = []
                current_chunk_start = start
            
            # Add definition to current chunk
            if not current_chunk_lines:
                current_chunk_start = start
            current_chunk_lines.extend(def_lines)
    
    # Add remaining lines
    if current_chunk_lines:
        chunk_text = ''.join(current_chunk_lines)
        chunks.append((current_chunk_start, current_chunk_start + len(current_chunk_lines) - 1, chunk_text))
    
    # Handle any leading code (imports, etc) before first definition
    if definitions and definitions[0][0] > 1:
        leading_text = ''.join(lines[:definitions[0][0] - 1])
        if leading_text.strip():
            chunks.insert(0, (1, definitions[0][0] - 1, leading_text))
    
    # Handle any trailing code
    if definitions:
        last_end = definitions[-1][1]
        if last_end < len(lines):
            trailing_text = ''.join(lines[last_end:])
            if trailing_text.strip():
                chunks.append((last_end + 1, len(lines), trailing_text))
    elif lines:
        # No definitions found, use whole file
        chunks = _chunk_by_lines(text)
    
    return chunks


def _chunk_javascript(text: str) -> List[Tuple[int, int, str]]:
    """Chunk JavaScript/TypeScript using regex for function/class/export."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Patterns for JS/TS structures
    patterns = [
        r'^export\s+(default\s+)?(function|class|const|let|var)\s+\w+',
        r'^(async\s+)?function\s+\w+',
        r'^class\s+\w+',
        r'^const\s+\w+\s*=\s*(async\s*)?\(',  # Arrow functions
        r'^export\s*\{',  # Export blocks
    ]
    
    combined_pattern = '|'.join(f'({p})' for p in patterns)
    
    # Find all structure boundaries
    boundaries = []
    for i, line in enumerate(lines, 1):
        if re.match(combined_pattern, line.strip()):
            boundaries.append(i)
    
    if not boundaries:
        return _chunk_by_lines(text)
    
    # Create chunks based on boundaries
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines)
        chunk_lines = lines[start - 1:end]
        chunk_text = ''.join(chunk_lines)
        
        # Split if too large
        if len(chunk_text) > 3200:
            sub_chunks = _split_large_block(chunk_lines, start)
            chunks.extend(sub_chunks)
        else:
            chunks.append((start, end, chunk_text))
    
    # Add any leading code before first boundary
    if boundaries and boundaries[0] > 1:
        leading_text = ''.join(lines[:boundaries[0] - 1])
        if leading_text.strip():
            chunks.insert(0, (1, boundaries[0] - 1, leading_text))
    
    return chunks


def _chunk_terraform(text: str) -> List[Tuple[int, int, str]]:
    """Chunk Terraform using regex for resource/module/provider blocks."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Pattern for Terraform blocks
    block_pattern = r'^(resource|module|provider|data|variable|output|locals)\s+'
    
    boundaries = []
    for i, line in enumerate(lines, 1):
        if re.match(block_pattern, line.strip()):
            boundaries.append(i)
    
    if not boundaries:
        return _chunk_by_lines(text)
    
    # Create chunks from boundaries
    for i, start in enumerate(boundaries):
        # Find the end of this block (next boundary or EOF)
        end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines)
        
        # Extract block
        chunk_lines = lines[start - 1:end]
        chunk_text = ''.join(chunk_lines)
        
        # Split if too large
        if len(chunk_text) > 3200:
            sub_chunks = _split_large_block(chunk_lines, start)
            chunks.extend(sub_chunks)
        else:
            chunks.append((start, end, chunk_text))
    
    return chunks


def _chunk_sql(text: str) -> List[Tuple[int, int, str]]:
    """Chunk SQL using CREATE statements as boundaries."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Pattern for SQL CREATE statements
    create_pattern = r'^CREATE\s+(TABLE|VIEW|FUNCTION|PROCEDURE|INDEX|TRIGGER|SCHEMA|DATABASE)'
    
    boundaries = []
    for i, line in enumerate(lines, 1):
        if re.match(create_pattern, line.strip(), re.IGNORECASE):
            boundaries.append(i)
    
    if not boundaries:
        return _chunk_by_lines(text)
    
    # Create chunks from boundaries
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] - 1 if i + 1 < len(boundaries) else len(lines)
        chunk_lines = lines[start - 1:end]
        chunk_text = ''.join(chunk_lines)
        
        # Split if too large
        if len(chunk_text) > 3200:
            sub_chunks = _split_large_block(chunk_lines, start)
            chunks.extend(sub_chunks)
        else:
            chunks.append((start, end, chunk_text))
    
    return chunks


def _chunk_markdown(text: str) -> List[Tuple[int, int, str]]:
    """Chunk Markdown by headings, merging tiny sections."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    # Pattern for markdown headings
    heading_pattern = r'^#{1,6}\s+'
    
    sections = []
    current_section_start = 1
    current_section_lines = []
    
    for i, line in enumerate(lines, 1):
        if re.match(heading_pattern, line):
            # Save previous section
            if current_section_lines:
                sections.append((current_section_start, i - 1, ''.join(current_section_lines)))
            # Start new section
            current_section_start = i
            current_section_lines = [line]
        else:
            current_section_lines.append(line)
    
    # Add last section
    if current_section_lines:
        sections.append((current_section_start, len(lines), ''.join(current_section_lines)))
    
    if not sections:
        return _chunk_by_lines(text)
    
    # Merge tiny sections
    merged_sections = []
    current_chunk = []
    current_start = None
    
    for start, end, section_text in sections:
        if current_start is None:
            current_start = start
        
        # If adding this section would exceed size limit, save current chunk
        if current_chunk and len(''.join(c[2] for c in current_chunk)) + len(section_text) > 3200:
            merged_text = ''.join(c[2] for c in current_chunk)
            merged_end = current_chunk[-1][1]
            merged_sections.append((current_start, merged_end, merged_text))
            current_chunk = []
            current_start = start
        
        current_chunk.append((start, end, section_text))
    
    # Add remaining sections
    if current_chunk:
        merged_text = ''.join(c[2] for c in current_chunk)
        merged_end = current_chunk[-1][1]
        merged_sections.append((current_start, merged_end, merged_text))
    
    return merged_sections


def _chunk_by_lines(text: str, target_lines: int = 200, overlap_lines: int = 30) -> List[Tuple[int, int, str]]:
    """Fallback line-based chunking with overlap."""
    chunks = []
    lines = text.splitlines(keepends=True)
    
    if not lines:
        return []
    
    i = 0
    while i < len(lines):
        chunk_end = min(i + target_lines, len(lines))
        chunk_lines = lines[i:chunk_end]
        chunk_text = ''.join(chunk_lines)
        
        chunks.append((i + 1, chunk_end, chunk_text))
        
        # Move forward with overlap
        i += target_lines - overlap_lines
        if i >= len(lines):
            break
    
    return chunks


def _split_large_block(lines: List[str], start_line: int, 
                       target_lines: int = 150, overlap_lines: int = 20) -> List[Tuple[int, int, str]]:
    """Split a large block into smaller chunks with overlap."""
    chunks = []
    
    i = 0
    while i < len(lines):
        chunk_end = min(i + target_lines, len(lines))
        chunk_lines = lines[i:chunk_end]
        chunk_text = ''.join(chunk_lines)
        
        actual_start = start_line + i
        actual_end = start_line + chunk_end - 1
        chunks.append((actual_start, actual_end, chunk_text))
        
        i += target_lines - overlap_lines
        if i >= len(lines):
            break
    
    return chunks


def _extract_symbols(text: str, lang: str) -> List[str]:
    """Extract function/class names from code."""
    symbols = []
    
    if lang in ("python", "py"):
        # Match def and class statements
        for match in re.finditer(r'(?:def|class)\s+(\w+)', text):
            symbols.append(match.group(1))
    elif lang in ("javascript", "js", "typescript", "ts"):
        # Match function and class declarations
        for match in re.finditer(r'(?:function|class)\s+(\w+)', text):
            symbols.append(match.group(1))
        # Match const/let/var function assignments
        for match in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', text):
            symbols.append(match.group(1))
    elif lang == "sql":
        # Match CREATE statements
        for match in re.finditer(r'CREATE\s+(?:TABLE|VIEW|FUNCTION|PROCEDURE)\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', text, re.IGNORECASE):
            symbols.append(match.group(1))
    
    return list(set(symbols))  # Remove duplicates


def _extract_imports(text: str, lang: str) -> List[str]:
    """Extract import statements from code."""
    imports = []
    
    if lang in ("python", "py"):
        # Match: from module import ..., import module
        for match in re.finditer(r'^\s*(?:from\s+(\S+)\s+import|import\s+)(.+)', text, re.MULTILINE):
            if match.group(1):
                # from X import Y format
                imports.append(match.group(1).split('.')[0])  # Get base module
            else:
                # import X format
                for imp in match.group(2).split(','):
                    imp = imp.strip().split(' as ')[0].split('.')[0]
                    if imp and imp not in ('*', ):
                        imports.append(imp)
    elif lang in ("javascript", "js", "typescript", "ts", "jsx", "tsx"):
        for match in re.finditer(r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]', text):
            imports.append(match.group(1))
        for match in re.finditer(r'require\([\'"](.+?)[\'"]\)', text):
            imports.append(match.group(1))
    
    return list(set(imports))  # Remove duplicates