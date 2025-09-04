"""Codegen and PR draft stubs for development workflow."""

from __future__ import annotations
import json
from typing import List, Dict, Any
from pydantic import BaseModel
from ..tools.git_ops import sanitize_branch_name
from ..models.change import ProposedPatch, FileDiff, PRDraft


def _load_json(s: str) -> Dict[str, Any]:
    """Safely load JSON string, returning empty dict on failure."""
    try:
        return json.loads(s or "{}")
    except Exception:
        return {}


def codegen_stub(story_json: str, devplan_json: str) -> ProposedPatch:
    """
    Deterministic, offline stub that converts StorySpec + DevPlan JSON into a ProposedPatch.
    
    - Picks impacted paths from DevPlan (fallback to StorySpec.impacted_paths).
    - Emits minimal 'unified diff' placeholders per file.
    - Generates a feature branch from story title.
    
    Args:
        story_json: JSON string with story specification
        devplan_json: JSON string with development plan
        
    Returns:
        ProposedPatch with stub diffs
    """
    story = _load_json(story_json)
    dev = _load_json(devplan_json)

    title = (story.get("title") or "feature").strip()
    branch = f"feat/{sanitize_branch_name(title or 'change')}"
    impacted: List[str] = list(dict.fromkeys(
        (dev.get("impacted_paths") or []) + (story.get("impacted_paths") or [])
    ))

    files: List[FileDiff] = []
    for p in impacted[:20]:  # Limit to 20 files for stub
        diff = f"""--- a/{p}
+++ b/{p}
@@ -1,3 +1,4 @@
 // TODO: existing code
-// TODO: implement
+// TODO: implement: {title}
+// Generated stub for {p}
"""
        files.append(FileDiff(path=p, diff=diff, summary=f"Scaffold changes for {p}"))

    tests = (dev.get("tests") or [])
    if not tests and impacted:
        tests = [f"test_{sanitize_branch_name(impacted[0]).replace('-','_').replace('/','_')}_behavior"]

    notes = [
        "This is a stub patch. Replace placeholder diffs with actual edits.",
        "Run code formatter and tests locally before raising a PR."
    ]

    return ProposedPatch(branch=branch, files=files, tests=tests, notes=notes)


def pr_draft_stub(patch_json: str) -> PRDraft:
    """
    Deterministic, offline PR draft based on ProposedPatch JSON.
    
    Creates a title/body and checklist referencing impacted files.
    
    Args:
        patch_json: JSON string with ProposedPatch data
        
    Returns:
        PRDraft with formatted title and body
    """
    data = _load_json(patch_json)
    branch = data.get("branch") or "feat/change"
    impact_paths = [f.get("path") for f in (data.get("files") or []) 
                    if isinstance(f, dict) and f.get("path")]

    # Extract feature name from branch
    feature_name = branch.split('/')[-1].replace('-', ' ').title()
    
    title = f"[{branch}] Implement {feature_name}"
    
    body_lines = [
        f"Branch: `{branch}`",
        "",
        "## Summary",
        "- Implements planned changes from Rally stories and Dev plan.",
        f"- Feature: {feature_name}",
        "",
        "## Impacted files",
    ]
    
    # Add impacted files (limit to 50 for readability)
    if impact_paths:
        for p in impact_paths[:50]:
            body_lines.append(f"- `{p}`")
        
        if len(impact_paths) > 50:
            body_lines.append(f"- ... and {len(impact_paths) - 50} more files")
    
    body_lines.extend([
        "",
        "## Tests",
    ])
    
    # Add test info if available
    tests = data.get("tests") or []
    if tests:
        for test in tests[:10]:
            body_lines.append(f"- `{test}`")
    else:
        body_lines.append("- No specific tests identified yet")
    
    body_lines.extend([
        "",
        "## Checklist",
        "- [ ] Unit tests updated/added",
        "- [ ] Lint/format passes",
        "- [ ] Local run verified",
        "- [ ] Documentation updated if needed",
    ])
    
    return PRDraft(
        title=title,
        body="\n".join(body_lines),
        branch=branch,
        impact_paths=impact_paths,
        checklist=[
            "Unit tests updated/added",
            "Lint/format passes",
            "Local run verified",
            "Documentation updated if needed"
        ],
    )