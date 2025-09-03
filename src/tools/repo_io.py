"""Repository I/O operations with safety and filtering."""

import os
import pathlib
from pathlib import Path
from typing import List, Optional
import fnmatch
import hashlib
import subprocess
import shutil
import re


def safe_join(root: str, rel: str) -> str:
    """Join paths safely, preventing path traversal attacks.
    
    Args:
        root: Root directory path
        rel: Relative path to join
        
    Returns:
        Absolute path inside root
        
    Raises:
        ValueError: If the resulting path is outside root
    """
    root_path = Path(root).resolve()
    try:
        # Handle both absolute and relative paths in rel
        if os.path.isabs(rel):
            # If rel is absolute, make it relative by removing root parts
            rel = os.path.relpath(rel, root)
        
        full_path = (root_path / rel).resolve()
        
        # Ensure the resolved path is within root
        full_path.relative_to(root_path)
        return str(full_path)
    except ValueError:
        raise ValueError(f"Path traversal detected: {rel} outside {root}")


def is_binary_path(path: str) -> bool:
    """Check if a file path likely contains binary content.
    
    Args:
        path: File path to check
        
    Returns:
        True if likely binary, False otherwise
    """
    # Binary extensions
    binary_exts = {
        '.exe', '.dll', '.so', '.dylib', '.bin', '.o', '.obj',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.ico',
        '.mp3', '.mp4', '.avi', '.mov', '.wav', '.ogg',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
        '.ttf', '.otf', '.woff', '.woff2',
        '.class', '.jar', '.war',
        '.pyc', '.pyo', '.pyd'
    }
    
    ext = pathlib.Path(path).suffix.lower()
    if ext in binary_exts:
        return True
    
    # Quick byte sniff for files without clear extensions
    if os.path.exists(path) and os.path.isfile(path):
        try:
            with open(path, 'rb') as f:
                chunk = f.read(512)  # Read first 512 bytes
                if b'\x00' in chunk:  # Null bytes typically indicate binary
                    return True
                # Check for high ratio of non-printable characters
                printable = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13))
                if len(chunk) > 0 and printable / len(chunk) < 0.75:
                    return True
        except (IOError, OSError):
            pass
    
    return False


def list_source_files(
    root: str,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None
) -> List[str]:
    """List source files in a directory tree with glob filtering.
    
    Args:
        root: Root directory to scan
        include_globs: Glob patterns to include (default: source dirs)
        exclude_globs: Glob patterns to exclude (default: build/cache dirs)
        
    Returns:
        List of relative file paths (posix style)
    """
    if include_globs is None:
        include_globs = ["src/**", "configs/**", "docs/**"]
    
    if exclude_globs is None:
        exclude_globs = [
            "**/node_modules/**", "**/.git/**", "**/.venv/**", "**/dist/**",
            "**/build/**", "**/.next/**", "**/.turbo/**", "**/.pytest_cache/**",
            "**/__pycache__/**", "**/.mypy_cache/**", "**/.ruff_cache/**",
            "**/*.lock", "**/package-lock.json", "**/yarn.lock", "**/*.min.*",
            "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.pdf"
        ]
    
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise ValueError(f"Root directory does not exist: {root}")
    
    # Collect all files
    all_files = []
    for file_path in root_path.rglob("*"):
        if file_path.is_file():
            try:
                rel_path = file_path.relative_to(root_path)
                # Convert to posix style for consistency
                posix_path = rel_path.as_posix()
                all_files.append(posix_path)
            except ValueError:
                continue  # Skip files outside root
    
    # Apply include filters
    included_files = []
    if include_globs:
        for file_path in all_files:
            if any(fnmatch.fnmatch(file_path, pattern) for pattern in include_globs):
                included_files.append(file_path)
    else:
        included_files = all_files
    
    # Apply exclude filters
    filtered_files = []
    for file_path in included_files:
        if not any(fnmatch.fnmatch(file_path, pattern) for pattern in exclude_globs):
            # Check if it's likely binary
            abs_path = root_path / file_path
            if not is_binary_path(str(abs_path)):
                filtered_files.append(file_path)
    
    return sorted(filtered_files)


def read_text_file(root: str, rel: str, max_bytes: int = 1_500_000) -> str:
    """Read a text file safely with size and binary checks.
    
    Args:
        root: Root directory
        rel: Relative path to file
        max_bytes: Maximum file size to read
        
    Returns:
        File content as string
        
    Raises:
        ValueError: If file is too large, binary, or path unsafe
        IOError: If file cannot be read
    """
    abs_path = safe_join(root, rel)
    
    if not os.path.isfile(abs_path):
        raise ValueError(f"Not a file: {rel}")
    
    # Check file size
    file_size = os.path.getsize(abs_path)
    if file_size > max_bytes:
        raise ValueError(f"File too large: {rel} ({file_size} bytes > {max_bytes})")
    
    # Check if binary
    if is_binary_path(abs_path):
        raise ValueError(f"Binary file detected: {rel}")
    
    # Read file with encoding detection
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    for encoding in encodings:
        try:
            with open(abs_path, 'r', encoding=encoding) as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            continue
        except (IOError, OSError) as e:
            raise IOError(f"Cannot read file {rel}: {e}")
    
    raise ValueError(f"Cannot decode text file: {rel}")


def safe_workspace_root() -> str:
    """Ensure a local workspace folder exists for cloned repos."""
    p = pathlib.Path(".workspace/repos").resolve()
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def slugify_url(url: str) -> str:
    """Create a safe directory name from a URL."""
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", (url.split("/")[-1] or "repo"))[:24]
    return f"{base}-{h}"


def clone_repo(url: str, ref: str | None = None) -> str:
    """
    Clone a git repo into .workspace/repos/<slug>, shallow by default.
    Supports https and file:// URLs. Returns absolute path to clone.
    If the folder exists, keep it; if ref is provided, fetch/checkout that ref.
    """
    root = pathlib.Path(safe_workspace_root())
    slug = slugify_url(url)
    dest = root / slug
    if not dest.exists():
        cmd = ["git", "clone", "--depth", "1", url, str(dest)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    if ref:
        subprocess.run(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", ref], 
                      check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(dest), "checkout", ref], 
                      check=True, capture_output=True, text=True)
    return str(dest.resolve())