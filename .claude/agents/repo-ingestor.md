---
name: repo-ingestor
description: |
  IMPLEMENT CODE: Repo I/O, language-aware parsing, and RepoIngestor agent with tests.

  Deliverables

  1) src/tools/repo_io.py
     Functions:
       - def safe_join(root: str, rel: str) -> str
         * prevent path traversal; return absolute path inside root
       - def is_binary_path(path: str) -> bool
         * simple heuristic via extension & a quick bytes sniff
       - def list_source_files(
             root: str,
             include_globs: list[str] | None = None,
             exclude_globs: list[str] | None = None
         ) -> list[str]
         * Defaults:
             include: ["src/**", "configs/**", "docs/**"]
             exclude: ["**/node_modules/**","**/.git/**","**/.venv/**","**/dist/**","**/build/**","**/.next/**","**/.turbo/**",
                       "**/.pytest_cache/**","**/__pycache__/**","**/.mypy_cache/**","**/.ruff_cache/**",
                       "**/*.lock","**/package-lock.json","**/yarn.lock","**/*.min.*","**/*.png","**/*.jpg","**/*.jpeg","**/*.pdf"]
         * Return paths relative to root (posix style)
       - def read_text_file(root: str, rel: str, max_bytes: int = 1_500_000) -> str
         * safe join; if >max_bytes or binary -> raise ValueError

  2) src/tools/parsing.py
     Functions:
       - def detect_language(path: str) -> str
         * by extension: py/js/ts/tsx/java/go/cpp/c/h/rs/sql/html/css/yaml/json/others
       - def extract_imports(text: str, lang: str) -> list[str]
         * regex heuristics:
             py: ^\s*(from\s+([\w\.]+)\s+import|import\s+([\w\.]+))
             js/ts: import ... from 'x' | require('x')
             sql: (FROM|JOIN)\s+([A-Za-z0-9_\.]+)
             others: conservative
       - def find_symbols(text: str, lang: str) -> list[str]
         * regex heuristics:
             py: def NAME( / class NAME
             js/ts: function NAME | class NAME | const NAME = (function|class)
             sql: CREATE (TABLE|VIEW|FUNCTION) NAME
       - def split_code_windows(text: str, lang: str, chunk_loc: int = 300, overlap_loc: int = 50)
           -> list[tuple[int,int,str]]
         * line-based windows; ensure at least 1 chunk; overlap handling
         * return (start_line, end_line, chunk_text)

  3) src/agents/repo_ingestor.py
     - from src.core.types import Chunk, CodeMap
     - from src.tools.repo_io import list_source_files, read_text_file
     - from src.tools.parsing import detect_language, extract_imports, find_symbols, split_code_windows
     - def get_git_commit(root: str) -> str:
         run `git rev-parse --short HEAD`; fallback "workspace"
     - def compute_hash(text: str) -> str:  sha1 of normalized text (strip spaces at ends of lines)
     - def ingest_repo(root: str = ".") -> tuple[CodeMap, list[Chunk]]:
         Steps:
           1) files = list_source_files(root)
           2) commit = get_git_commit(root); repo = basename(root)
           3) Iterate files:
                - read text (skip >max_bytes/binary)
                - lang = detect_language(path)
                - symbols = find_symbols(text, lang)
                - imports = extract_imports(text, lang)
                - windows = split_code_windows(text, lang)
                - for each window: create Chunk(
                      id=f"{repo}:{commit}:{path}#{start_line}-{end_line}",
                      repo=repo, commit=commit, path=path, lang=lang,
                      start_line=start, end_line=end, text=chunk_text,
                      symbols=symbols[:50], imports=imports[:50],
                      neighbors=[], hash=compute_hash(chunk_text)
                  )
           4) Build deps dict: path -> imports
           5) Build symbol_index: symbol -> [paths] (unique)
           6) Return CodeMap(repo, commit, files, deps, symbol_index) and all chunks

  4) tests/test_repo_ingestor.py
     - Create a temp dir with a tiny src/ layout:
         src/app.py (two defs, import os)
         src/util/helpers.js (one function, import from "./lib/x")
         src/db/schema.sql (CREATE TABLE/VIEW; a simple SELECT FROM)
       * Call ingest_repo(root=temp_dir)
       * Assertions:
           - CodeMap.files contains those paths (posix style)
           - deps has keys for those paths; imports non-empty
           - at least 1 Chunk per file; Chunk fields populated; hashes non-empty
           - symbol_index maps expected symbols to their files
           - windowing respects chunk_loc default (i.e., not zero, and covers the file)

  Packaging
     - Ensure __init__.py in src/agents, src/tools, src/core, src/services
     - Adjust pyproject/requirements if new deps used
     - Keep tests fast & deterministic

  Process
     - Show diffs.
     - Run pytest -q.
     - Commit: "feat(ingest): repo_io + parsing + repo_ingestor with tests"
tools: Read, Write, Edit, Bash
---