"""Language-aware code parsing and chunking utilities."""

import re
from typing import List, Tuple
from pathlib import Path


def detect_language(path: str) -> str:
    """Detect programming language from file extension.
    
    Args:
        path: File path to analyze
        
    Returns:
        Language identifier string
    """
    ext = Path(path).suffix.lower()
    
    # Language mapping by extension
    lang_map = {
        '.py': 'python',
        '.js': 'javascript', 
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.java': 'java',
        '.go': 'go',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.rs': 'rust',
        '.sql': 'sql',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.scss': 'css',
        '.sass': 'css',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.json': 'json',
        '.xml': 'xml',
        '.md': 'markdown',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.rb': 'ruby',
        '.php': 'php',
        '.scala': 'scala',
        '.kt': 'kotlin',
        '.swift': 'swift',
        '.r': 'r',
        '.R': 'r'
    }
    
    return lang_map.get(ext, 'other')


def extract_imports(text: str, lang: str) -> List[str]:
    """Extract import statements using regex heuristics.
    
    Args:
        text: Source code text
        lang: Programming language
        
    Returns:
        List of imported module/package names
    """
    imports = []
    
    if lang == 'python':
        # Match: import module, from module import ..., from .relative import ...
        patterns = [
            r'^\s*import\s+([\w\.]+)',
            r'^\s*from\s+([\w\.]+)\s+import',
            r'^\s*from\s+(\.\w*[\w\.]*)\s+import'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            imports.extend(matches)
    
    elif lang in ['javascript', 'typescript']:
        # Match: import ... from 'module', require('module')
        patterns = [
            r'import.*?from\s+["\']([^"\']+)["\']',
            r'require\s*\(\s*["\']([^"\']+)["\']\s*\)',
            r'import\s*\(\s*["\']([^"\']+)["\']\s*\)'  # dynamic imports
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            imports.extend(matches)
    
    elif lang == 'java':
        # Match: import package.Class;
        pattern = r'^\s*import\s+([\w\.]+);'
        matches = re.findall(pattern, text, re.MULTILINE)
        imports.extend(matches)
    
    elif lang == 'go':
        # Match: import "package", import ( "package1" "package2" )
        patterns = [
            r'import\s+"([^"]+)"',
            r'import\s+\(\s*"([^"]+)"',
            r'^\s*"([^"]+)"\s*$'  # within import blocks
        ]
        # Handle multi-line import blocks
        import_blocks = re.findall(r'import\s*\(\s*(.*?)\s*\)', text, re.DOTALL)
        for block in import_blocks:
            block_imports = re.findall(r'"([^"]+)"', block)
            imports.extend(block_imports)
        
        # Handle single imports
        single_imports = re.findall(r'import\s+"([^"]+)"', text)
        imports.extend(single_imports)
    
    elif lang == 'sql':
        # Match: FROM table, JOIN table - basic table references
        patterns = [
            r'(?:FROM|JOIN)\s+([A-Za-z0-9_\.]+)',
            r'(?:FROM|JOIN)\s+`([^`]+)`',
            r'(?:FROM|JOIN)\s+"([^"]+)"',
            r'(?:FROM|JOIN)\s+\'([^\']+)\''
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            imports.extend(matches)
    
    # Remove duplicates and filter out empty strings
    return [imp for imp in list(set(imports)) if imp and imp.strip()]


def find_symbols(text: str, lang: str) -> List[str]:
    """Find defined symbols (functions, classes, etc.) using regex heuristics.
    
    Args:
        text: Source code text
        lang: Programming language
        
    Returns:
        List of symbol names
    """
    symbols = []
    
    if lang == 'python':
        # Match: def function_name(, class ClassName:
        patterns = [
            r'^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
            r'^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]',
            r'^\s*async\s+def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            symbols.extend(matches)
    
    elif lang in ['javascript', 'typescript']:
        # Match: function name(, class Name, const name = function, const name = (
        patterns = [
            r'function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(',
            r'class\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function',
            r'const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(',
            r'const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*async\s*\(',
            r'export\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'export\s+class\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'export\s+const\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            r'([A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*function\s*\(',  # object methods
            r'([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^)]*\)\s*=>\s*{',  # arrow functions
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            symbols.extend(matches)
    
    elif lang == 'java':
        # Match: public/private/protected class/interface/enum, method declarations
        patterns = [
            r'(?:public|private|protected)?\s*class\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'(?:public|private|protected)?\s*interface\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'(?:public|private|protected)?\s*enum\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            symbols.extend(matches)
    
    elif lang == 'go':
        # Match: func name(, type Name struct, type Name interface
        patterns = [
            r'func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
            r'func\s*\([^)]*\)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(',  # methods
            r'type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct',
            r'type\s+([A-Za-z_][A-Za-z0-9_]*)\s+interface'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text)
            symbols.extend(matches)
    
    elif lang == 'sql':
        # Match: CREATE TABLE name, CREATE VIEW name, CREATE FUNCTION name
        patterns = [
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)',
            r'CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)',
            r'CREATE\s+FUNCTION\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'CREATE\s+PROCEDURE\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'CREATE\s+INDEX\s+([A-Za-z_][A-Za-z0-9_]*)'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            symbols.extend(matches)
    
    elif lang in ['cpp', 'c']:
        # Match: function definitions, class/struct definitions
        patterns = [
            r'(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'(?:void|int|float|double|char|bool|auto|[A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*{',
            r'^\s*([A-Za-z_][A-Za-z0-9_]*)::[A-Za-z_][A-Za-z0-9_]*\s*\('  # method definitions
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            symbols.extend(matches)
    
    # Remove duplicates and filter out empty/common words
    filtered_symbols = []
    common_words = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'return', 'break', 'continue'}
    for symbol in set(symbols):
        if symbol and symbol.strip() and symbol.lower() not in common_words:
            filtered_symbols.append(symbol.strip())
    
    return filtered_symbols


def split_code_windows(
    text: str, 
    lang: str, 
    chunk_loc: int = 300, 
    overlap_loc: int = 50
) -> List[Tuple[int, int, str]]:
    """Split code into overlapping windows by lines.
    
    Args:
        text: Source code text
        lang: Programming language (for future enhancements)
        chunk_loc: Target lines per chunk
        overlap_loc: Lines to overlap between chunks
        
    Returns:
        List of (start_line, end_line, chunk_text) tuples
    """
    lines = text.splitlines(keepends=True)
    total_lines = len(lines)
    
    # Ensure at least one chunk
    if total_lines == 0:
        return [(1, 1, "")]
    
    if total_lines <= chunk_loc:
        # Single chunk for small files
        return [(1, total_lines, text)]
    
    chunks = []
    start_line = 0
    
    while start_line < total_lines:
        end_line = min(start_line + chunk_loc, total_lines)
        
        # Extract chunk text
        chunk_lines = lines[start_line:end_line]
        chunk_text = ''.join(chunk_lines)
        
        # Convert to 1-based line numbers
        chunks.append((start_line + 1, end_line, chunk_text))
        
        # Move to next chunk with overlap
        if end_line >= total_lines:
            break
        
        start_line = end_line - overlap_loc
        
        # Prevent infinite loop if overlap is too large
        if start_line <= chunks[-1][0] - 1:  # -1 to convert back to 0-based
            start_line = chunks[-1][1]  # Start at end of previous chunk
    
    return chunks