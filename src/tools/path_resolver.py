from __future__ import annotations
from typing import Iterable, List

def resolve_paths(candidates: Iterable[str], repo_files: Iterable[str]) -> List[str]:
    """
    Normalize candidate paths against actual repo files.
    Strategy:
      - prefer exact match
      - else match by suffix (e.g., 'client/src/App.js' or 'App.js')
      - dedupe
    """
    repo = list(repo_files or [])
    out: List[str] = []
    seen = set()
    cand_list = list(dict.fromkeys([c.strip() for c in candidates or [] if c and c.strip()]))
    for c in cand_list:
        # exact
        if c in repo and c not in seen:
            out.append(c); seen.add(c); continue
        # suffix
        matches = [rf for rf in repo if rf.endswith(c)]
        if matches:
            # choose the longest path (most specific)
            best = max(matches, key=len)
            if best not in seen:
                out.append(best); seen.add(best)
    return out