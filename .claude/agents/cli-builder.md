---
name: cli-builder
description: |
  IMPLEMENT CODE: Create a CLI that runs the Orchestrator end-to-end with useful subcommands, and add tests.

  Deliverables

  1) src/ui/cli.py
     - Provide a `main()` using argparse with subcommands:
       * ingest        -> orchestrator.ingest()
       * decide        -> orchestrator.size_and_decide() (ensure ingest has been called; if not, call it)
       * index         -> orchestrator.index() (call ingest+decide first if needed)
       * ask           -> orchestrator.ask(--query, --k, --write-docs)
       * all           -> run ingest -> decide -> index; if --query passed, also ask; else print summary JSON
     - Common flags:
       * --root PATH (default ".")
       * --session ID (default "default")
       * --query "text" (for ask/all)
       * --k INT (default 12)
       * --write-docs (flag)
     - Output: print compact JSON to stdout for each subcommand.
     - Handle errors with nonzero exit and a short message to stderr.
     - Do not require cloud credentials; everything runs in-memory.

     Skeleton:
       from src.agents.orchestrator import OrchestratorAgent
       def run_pipeline(args): ...
       def main(): argparse setup; dispatch; print JSON

  2) tests/test_cli.py
     - Create a tiny temp repo fixture with a few files under src/ (py/js/sql minimal).
     - Monkeypatch embeddings to return deterministic vectors (avoid network).
     - Call main() by patching sys.argv for:
         * ["prog", "all", "--root", tmp, "--session", "t1"]
         * ["prog", "ask", "--root", tmp, "--session", "t2", "--query", "helper function", "--write-docs"]
       - Assert JSON printed contains expected keys; for "ask" ensure "sources" is a non-empty list; when --write-docs set, ensure a docs/generated path string is returned.
     - Also test `-h` prints usage (capture SystemExit code 0).

  3) Packaging
     - If pyproject.toml exists, add a console script:
         [project.scripts]
         adk-orch = "src.ui.cli:main"
       (If using requirements.txt only, create a minimal pyproject.toml with name/version and the scripts entry.)
     - Ensure __init__.py exist for src/ui and package paths import cleanly.

  Process
  - Show diffs.
  - Run pytest -q.
  - Commit: "feat(cli): orchestrator CLI (ingest→decide→index→ask) + tests"
tools: Read, Write, Edit, Bash
---