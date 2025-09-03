---
name: repo-sizer
description: |
  IMPLEMENT CODE: Create a programmatic repo sizer with tests.

  Deliverables:
  1) src/tools/sizer.py implementing:
     - Pydantic model:
         class SizerReport(BaseModel):
             repo: str
             commit: str
             file_count: int
             loc_total: int
             bytes_total: int
             lang_breakdown: dict[str, dict[str,int]]
             avg_file_loc: float
             max_file_loc: int
             estimated_tokens_repo: int
             chunk_estimate: int
             vector_count_estimate: int
     - def estimate_tokens(char_count: int) -> int  # tokens ~= chars//4
     - def measure_repo(root: str, files: list[str], chunk_loc: int = 300, overlap_loc: int = 50) -> SizerReport
       * Read files safely (join root/path); ignore vendor/build/node_modules/.git/.venv and binaries/lockfiles.
       * Detect language by extension; fill lang_breakdown {"python":{"files":X,"loc":Y}, ...}.
       * Compute totals, averages, max; total chars -> estimated_tokens_repo.
       * chunk_estimate ~= sum over files of ceil(max(1, (loc - overlap)/(chunk_loc - overlap))).
       * vector_count_estimate = chunk_estimate.
       * repo = basename(root); commit = `git rev-parse --short HEAD` else "workspace".

  2) tests/test_sizer.py:
     - temp files → measure_repo returns coherent counts
     - empty file still yields >=1 chunk
     - estimate_tokens simple sanity
     - mark tests fast and deterministic

  3) Packaging:
     - Ensure package inits exist: src/agents/__init__.py, src/tools/__init__.py, src/services/__init__.py, src/core/__init__.py
     - Ensure deps: add pydantic and pytest if missing (pyproject.toml or requirements.txt)

  Process:
  - Show diffs.
  - Run pytest -q.
  - Commit: "feat(core): add sizer module + tests"
tools: Read, Write, Edit, Bash
---