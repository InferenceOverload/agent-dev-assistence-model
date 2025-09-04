"""Pydantic models for repository analysis."""

from __future__ import annotations
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class Component(BaseModel):
    """A logical component in the repository."""
    name: str = Field(description="Component name (e.g., 'API', 'Database', 'Frontend')")
    type: str = Field(description="Component type (e.g., 'service', 'library', 'database', 'ui')")
    path: str = Field(description="Primary path for this component")
    language: str = Field(description="Primary language (python, java, javascript, sql, terraform, rust)")
    files_count: int = Field(default=0, description="Number of files in component")
    
    
class Relation(BaseModel):
    """A relationship between components."""
    source: str = Field(description="Source component name")
    target: str = Field(description="Target component name")
    type: str = Field(description="Relation type (imports, calls, queries, deploys, configures)")
    confidence: float = Field(default=1.0, description="Confidence score 0-1")


class RepoFacts(BaseModel):
    """Repository facts extracted from analysis."""
    components: List[Component] = Field(default_factory=list, description="Detected components")
    relations: List[Relation] = Field(default_factory=list, description="Component relationships")
    languages: Dict[str, int] = Field(default_factory=dict, description="Language file counts")
    entry_points: List[str] = Field(default_factory=list, description="Detected entry point files")
    frameworks: List[str] = Field(default_factory=list, description="Detected frameworks")
    databases: List[str] = Field(default_factory=list, description="Detected database systems")
    deploy_targets: List[str] = Field(default_factory=list, description="Detected deployment targets")