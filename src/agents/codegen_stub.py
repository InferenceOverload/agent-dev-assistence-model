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
    Enhanced stub that uses task decomposition to generate more realistic patches.
    
    Args:
        story_json: JSON string with story specification
        devplan_json: JSON string with development plan
        
    Returns:
        ProposedPatch with realistic stub diffs
    """
    from ..agents.task_decomposer import decompose_feature_request
    from ..analysis.models import RepoFacts
    
    story = _load_json(story_json)
    dev = _load_json(devplan_json)

    title = (story.get("title") or "feature").strip()
    description = story.get("description", title)
    branch = f"feat/{sanitize_branch_name(title or 'change')}"
    
    # Use task decomposer for better file structure
    repo_facts = RepoFacts()  # Would be populated from actual analysis
    decomposition = decompose_feature_request(description, repo_facts)
    
    # Merge impacted paths from all sources
    impacted: List[str] = list(dict.fromkeys(
        decomposition["files_to_modify"] +
        (dev.get("impacted_paths") or []) + 
        (story.get("impacted_paths") or [])
    ))

    files: List[FileDiff] = []
    
    # Generate more realistic diffs based on file type
    for p in impacted[:20]:  # Limit to 20 files
        file_ext = p.split('.')[-1] if '.' in p else ''
        is_new = "new" in p.lower() or not p.startswith("src/")
        
        # Generate language-specific diff content
        if file_ext in ['py', 'python']:
            diff_content = _generate_python_diff(p, title, is_new)
        elif file_ext in ['js', 'jsx', 'ts', 'tsx']:
            diff_content = _generate_javascript_diff(p, title, is_new)
        elif file_ext in ['java']:
            diff_content = _generate_java_diff(p, title, is_new)
        elif file_ext in ['sql']:
            diff_content = _generate_sql_diff(p, title, is_new)
        else:
            diff_content = _generate_generic_diff(p, title, is_new)
        
        files.append(FileDiff(
            path=p, 
            diff=diff_content, 
            summary=f"{'Create' if is_new else 'Update'} {p} for {title[:30]}"
        ))

    # Generate tests from decomposition
    tests = decomposition["tests_needed"][:3]
    if not tests and impacted:
        tests = [f"test_{sanitize_branch_name(impacted[0]).replace('-','_').replace('/','_')}_behavior"]

    # Add implementation notes from decomposition
    notes = [
        f"Implementation complexity: {decomposition['complexity']}",
        f"Estimated effort: {decomposition['estimated_effort_hours']} hours"
    ]
    
    # Add design decisions as notes
    for decision in decomposition["design_decisions"][:2]:
        notes.append(f"Design: {decision}")

    return ProposedPatch(branch=branch, files=files, tests=tests, notes=notes)


def _generate_python_diff(path: str, title: str, is_new: bool) -> str:
    """Generate Python-specific diff."""
    if is_new:
        return f"""--- /dev/null
+++ b/{path}
@@ -0,0 +1,15 @@
+\"\"\"Implementation for {title}.\"\"\"
+
+from typing import Dict, Any
+import logging
+
+logger = logging.getLogger(__name__)
+
+
+class {title.replace(' ', '')}:
+    \"\"\"Handle {title} functionality.\"\"\"
+    
+    def __init__(self):
+        \"\"\"Initialize {title}.\"\"\"
+        self.config = {{}}
+        logger.info(f"Initialized {{self.__class__.__name__}}")
"""
    else:
        return f"""--- a/{path}
+++ b/{path}
@@ -10,6 +10,15 @@ class ExistingClass:
         self.data = data
         
+    def handle_{sanitize_branch_name(title).replace('-', '_')}(self, request: Dict[str, Any]) -> Dict[str, Any]:
+        \"\"\"Handle {title} functionality.
+        
+        Args:
+            request: Request data
+            
+        Returns:
+            Response data
+        \"\"\"
+        # TODO: Implement {title}
+        return {{"status": "success"}}
"""


def _generate_javascript_diff(path: str, title: str, is_new: bool) -> str:
    """Generate JavaScript/TypeScript diff."""
    is_react = 'component' in path.lower() or '.jsx' in path or '.tsx' in path
    
    if is_new and is_react:
        return f"""--- /dev/null
+++ b/{path}
@@ -0,0 +1,20 @@
+import React from 'react';
+
+interface {title.replace(' ', '')}Props {{
+  // TODO: Define props
+}}
+
+export const {title.replace(' ', '')}: React.FC<{title.replace(' ', '')}Props> = (props) => {{
+  // TODO: Implement {title} component
+  
+  return (
+    <div className="{sanitize_branch_name(title)}">
+      <h2>{{title}}</h2>
+      {{/* TODO: Add component content */}}
+    </div>
+  );
+}};
+
+export default {title.replace(' ', '')};
"""
    elif is_new:
        return f"""--- /dev/null
+++ b/{path}
@@ -0,0 +1,12 @@
+/**
+ * Implementation for {title}
+ */
+
+export function handle{title.replace(' ', '')}(data) {{
+  // TODO: Implement {title}
+  console.log('Processing:', data);
+  
+  return {{
+    status: 'success',
+    result: data
+  }};
+}}
"""
    else:
        return f"""--- a/{path}
+++ b/{path}
@@ -25,3 +25,12 @@ export class Service {{
     return result;
   }}
+  
+  async handle{title.replace(' ', '')}(request) {{
+    // TODO: Implement {title}
+    const result = await this.process(request);
+    return {{
+      status: 'success',
+      data: result
+    }};
+  }}
"""


def _generate_java_diff(path: str, title: str, is_new: bool) -> str:
    """Generate Java diff."""
    class_name = title.replace(' ', '')
    if is_new:
        return f"""--- /dev/null
+++ b/{path}
@@ -0,0 +1,18 @@
+package com.example.feature;
+
+import java.util.Map;
+import java.util.HashMap;
+
+public class {class_name} {{
+    
+    private Map<String, Object> config;
+    
+    public {class_name}() {{
+        this.config = new HashMap<>();
+    }}
+    
+    public Map<String, Object> handle(Map<String, Object> request) {{
+        // TODO: Implement {title}
+        return Map.of("status", "success");
+    }}
+}}
"""
    else:
        return f"""--- a/{path}
+++ b/{path}
@@ -45,4 +45,11 @@ public class ExistingService {{
         return response;
     }}
+    
+    public Map<String, Object> handle{class_name}(Map<String, Object> request) {{
+        // TODO: Implement {title}
+        logger.info("Processing {title}");
+        Map<String, Object> result = new HashMap<>();
+        result.put("status", "success");
+        return result;
+    }}
"""


def _generate_sql_diff(path: str, title: str, is_new: bool) -> str:
    """Generate SQL diff."""
    table_name = sanitize_branch_name(title).replace('-', '_')
    if is_new or 'migration' in path.lower():
        return f"""--- /dev/null
+++ b/{path}
@@ -0,0 +1,15 @@
+-- Migration for {title}
+
+CREATE TABLE IF NOT EXISTS {table_name} (
+    id SERIAL PRIMARY KEY,
+    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
+    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
+    status VARCHAR(50) DEFAULT 'active',
+    data JSONB
+);
+
+CREATE INDEX idx_{table_name}_status ON {table_name}(status);
+CREATE INDEX idx_{table_name}_created_at ON {table_name}(created_at);
+
+-- TODO: Add additional columns and constraints for {title}
"""
    else:
        return f"""--- a/{path}
+++ b/{path}
@@ -10,3 +10,8 @@ SELECT * FROM existing_table;
 
 -- Existing queries
+
+-- New query for {title}
+SELECT id, status, data
+FROM {table_name}
+WHERE status = 'active'
+ORDER BY created_at DESC;
"""


def _generate_generic_diff(path: str, title: str, is_new: bool) -> str:
    """Generate generic diff for unknown file types."""
    if is_new:
        return f"""--- /dev/null
+++ b/{path}
@@ -0,0 +1,5 @@
+# Implementation for {title}
+
+TODO: Add implementation for {title}
+This file was generated as part of the {title} feature.
+Please replace this with actual implementation.
"""
    else:
        return f"""--- a/{path}
+++ b/{path}
@@ -1,3 +1,4 @@
 # Existing content
-# TODO: implement
+# TODO: implement: {title}
+# Updated for {title} feature
"""


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