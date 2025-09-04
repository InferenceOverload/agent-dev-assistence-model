from __future__ import annotations
from typing import List, Dict
from collections import defaultdict

def _top_dirs(paths: List[str], max_dirs: int = 8) -> List[str]:
    counts: Dict[str,int] = defaultdict(int)
    for p in paths:
        head = p.split("/", 1)[0] if "/" in p else p
        counts[head] += 1
    return [d for d, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:max_dirs]]

def mermaid_repo_tree(paths: List[str], max_files_per_dir: int = 10) -> str:
    if not paths:
        return "graph TD;\n  A[empty repo];"
    tops = set(_top_dirs(paths))
    groups: Dict[str, List[str]] = defaultdict(list)
    for p in paths:
        head = p.split("/", 1)[0] if "/" in p else p
        key = head if head in tops else "_other"
        groups[key].append(p)
    lines = ["graph TD", "  root((repo))"]
    def sanitize(label: str) -> str:
        return label.replace("/", "_").replace(".", "_").replace("-", "_")
    for g, files in groups.items():
        node = sanitize(g)
        lines.append(f"  root --> {node}[{g}/]")
        for fp in sorted(files)[:max_files_per_dir]:
            leaf = sanitize(fp)
            lines.append(f"  {node} --> {leaf}({fp})")
    return ";\n".join(lines) + ";"