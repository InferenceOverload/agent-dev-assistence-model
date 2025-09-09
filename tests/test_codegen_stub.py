"""Tests for codegen stub functionality."""

import json
import pytest
from src.agents.codegen_stub import codegen_stub, pr_draft_stub
from src.models.change import ProposedPatch, PRDraft, FileDiff
from src.tools.git_ops import sanitize_branch_name


def test_codegen_stub_roundtrip():
    """Test codegen stub with story and devplan."""
    story = {
        "title": "[Feat] Add footer component",
        "impacted_paths": ["client/src/App.jsx", "client/src/Footer.jsx"]
    }
    devplan = {
        "branch": "feat/add-footer",
        "impacted_paths": ["client/src/Footer.jsx"],
        "tests": ["test_footer_renders"]
    }
    
    patch = codegen_stub(json.dumps(story), json.dumps(devplan))
    
    assert patch.branch.startswith("feat/")
    assert len(patch.files) > 0
    assert any(f.path.endswith("Footer.jsx") or "NewFeature.jsx" in f.path for f in patch.files)
    # Tests are now generated from task decomposition
    assert len(patch.tests) > 0
    assert len(patch.notes) > 0
    
    # Test PR draft from patch
    draft = pr_draft_stub(patch.model_dump_json())
    assert "Implement" in draft.title
    assert draft.branch == patch.branch
    assert len(draft.impact_paths) == len(patch.files)


def test_codegen_stub_empty_inputs():
    """Test codegen stub with empty or invalid inputs."""
    # Empty JSON strings
    patch = codegen_stub("{}", "{}")
    assert patch.branch == "feat/feature"  # Default branch
    assert len(patch.files) == 0
    assert len(patch.tests) == 0
    
    # Invalid JSON
    patch = codegen_stub("invalid", "also invalid")
    assert patch.branch == "feat/feature"
    assert len(patch.files) == 0


def test_pr_draft_stub_formatting():
    """Test PR draft formatting."""
    patch_data = {
        "branch": "feat/test-feature",
        "files": [
            {"path": "src/main.py", "diff": "dummy diff"},
            {"path": "tests/test_main.py", "diff": "test diff"}
        ],
        "tests": ["test_feature_works"],
        "notes": ["This is a test"]
    }
    
    draft = pr_draft_stub(json.dumps(patch_data))
    
    assert draft.title == "[feat/test-feature] Implement Test Feature"
    assert "feat/test-feature" in draft.body
    assert "src/main.py" in draft.body
    assert "tests/test_main.py" in draft.body
    assert "test_feature_works" in draft.body
    assert len(draft.checklist) > 0
    assert draft.impact_paths == ["src/main.py", "tests/test_main.py"]


def test_branch_name_sanitization():
    """Test branch name sanitization."""
    # Test various input strings
    assert sanitize_branch_name("Feature: Add New API") == "Feature-Add-New-API"
    assert sanitize_branch_name("[JIRA-123] Fix bug!!!") == "JIRA-123-Fix-bug"
    assert sanitize_branch_name("  spaces  everywhere  ") == "spaces-everywhere"
    assert sanitize_branch_name("a" * 100)[:50] == "a" * 50
    assert sanitize_branch_name("////slashes////") == "slashes"
    assert sanitize_branch_name("") == "feature"


def test_codegen_with_many_files():
    """Test codegen with many impacted files."""
    story = {"title": "Big refactor", "impacted_paths": []}
    
    # Add 30 paths
    paths = [f"src/module{i}/file{i}.py" for i in range(30)]
    devplan = {"impacted_paths": paths}
    
    patch = codegen_stub(json.dumps(story), json.dumps(devplan))
    
    # Should limit to 20 files
    assert len(patch.files) == 20
    assert all(isinstance(f, FileDiff) for f in patch.files)


def test_pr_draft_with_many_files():
    """Test PR draft with many impacted files."""
    files = [{"path": f"file{i}.py", "diff": "diff"} for i in range(60)]
    patch_data = {"branch": "feat/many", "files": files}
    
    draft = pr_draft_stub(json.dumps(patch_data))
    
    # Should mention truncation
    assert "10 more files" in draft.body  # 60 - 50 = 10
    assert len(draft.impact_paths) == 60


def test_integrated_workflow():
    """Test the integrated workflow from story to PR draft."""
    # Story from planning
    story = {
        "title": "Add dark mode toggle",
        "description": "Users want a dark mode option",
        "acceptance_criteria": ["Toggle in settings", "Persists on reload"],
        "impacted_paths": ["src/components/Settings.jsx", "src/styles/theme.css"]
    }
    
    # Dev plan
    devplan = {
        "branch": "feat/dark-mode",
        "impacted_paths": ["src/components/Settings.jsx", "src/styles/theme.css", "src/utils/theme.js"],
        "tests": ["test_dark_mode_toggle", "test_theme_persistence"]
    }
    
    # Generate patch
    patch = codegen_stub(json.dumps(story), json.dumps(devplan))
    assert isinstance(patch, ProposedPatch)
    assert len(patch.files) >= 3  # May include additional files from task decomposition
    assert len(patch.tests) >= 1  # Task decomposer generates tests dynamically
    
    # Generate PR draft
    draft = pr_draft_stub(patch.model_dump_json())
    assert isinstance(draft, PRDraft)
    assert "dark" in draft.title.lower()
    assert all(path in draft.body for path in ["Settings.jsx", "theme.css", "theme.js"])


def test_adk_tool_functions():
    """Test ADK tool wrapper functions."""
    from adam_agent import gen_code, pr_draft
    
    # Test gen_code
    story_json = json.dumps({"title": "Test", "impacted_paths": ["test.py"]})
    devplan_json = json.dumps({"impacted_paths": ["test.py"], "tests": ["test_it"]})
    
    result = gen_code(story_json, devplan_json)
    assert "patch" in result
    assert "status" in result
    assert isinstance(result["patch"], dict)
    
    # Test pr_draft
    patch_json = json.dumps(result["patch"])
    pr_result = pr_draft(patch_json)
    assert "pr" in pr_result
    assert "status" in pr_result
    assert isinstance(pr_result["pr"], dict)