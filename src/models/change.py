"""Data models for code generation and PR drafting."""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class FileDiff(BaseModel):
    """Represents a diff for a single file."""
    path: str = Field(..., description="Relative file path")
    diff: str = Field(..., description="Unified diff or patch text")
    summary: Optional[str] = Field(None, description="One-line explanation of the change")


class ProposedPatch(BaseModel):
    """Collection of file diffs forming a complete patch."""
    branch: str = Field(..., description="Feature branch name to apply the patch")
    files: List[FileDiff] = Field(default_factory=list, description="Per-file diffs")
    tests: List[str] = Field(default_factory=list, description="Suggested test names to implement")
    notes: List[str] = Field(default_factory=list, description="Explanatory notes or assumptions")


class PRDraft(BaseModel):
    """Pull request draft with metadata."""
    title: str
    body: str
    branch: str
    impact_paths: List[str] = Field(default_factory=list)
    checklist: List[str] = Field(default_factory=list)