"""Core data types and Pydantic models."""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class Chunk(BaseModel):
    """Code chunk with metadata."""
    id: str = Field(..., description="Unique chunk identifier")
    repo: str = Field(..., description="Repository name")
    commit: str = Field(..., description="Commit SHA")
    path: str = Field(..., description="File path")
    lang: str = Field(..., description="Programming language")
    start_line: int = Field(..., description="Starting line number")
    end_line: int = Field(..., description="Ending line number")
    text: str = Field(..., description="Chunk text content")
    symbols: List[str] = Field(default_factory=list, description="Defined symbols")
    imports: List[str] = Field(default_factory=list, description="Import statements")
    neighbors: List[str] = Field(default_factory=list, description="Neighbor chunk IDs")
    hash: str = Field(..., description="Content hash")
    

class CodeMap(BaseModel):
    """Repository code map with dependencies."""
    repo: str = Field(..., description="Repository name")
    commit: str = Field(..., description="Commit SHA")
    files: List[str] = Field(default_factory=list, description="File paths")
    deps: Dict[str, List[str]] = Field(default_factory=dict, description="File dependencies")
    symbol_index: Dict[str, List[str]] = Field(default_factory=dict, description="Symbol to file mapping")
    

class RetrievalResult(BaseModel):
    """Search result from retrieval."""
    chunk_id: str = Field(..., description="Chunk identifier")
    path: str = Field(..., description="File path")
    score: float = Field(..., description="Relevance score")
    neighbors: List[str] = Field(default_factory=list, description="Related chunk IDs")
    snippet: Optional[str] = Field(None, description="Code snippet preview")
    

class StorySpec(BaseModel):
    """Rally story specification."""
    title: str = Field(..., description="Story title")
    description: str = Field(..., description="Story description")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Acceptance criteria")
    impacted_paths: List[str] = Field(default_factory=list, description="Affected file paths")
    estimated_points: Optional[int] = Field(None, description="Story points")
    tags: List[str] = Field(default_factory=list, description="Story tags")
    

class PRPlan(BaseModel):
    """Pull request implementation plan."""
    branch: str = Field(..., description="Branch name")
    commits: List[str] = Field(default_factory=list, description="Planned commits")
    summary: str = Field(..., description="PR summary")
    impacted_paths: List[str] = Field(default_factory=list, description="Modified files")
    tests: List[str] = Field(default_factory=list, description="Test files to run")
    sandbox_url: Optional[str] = Field(None, description="Preview environment URL")
    

class AgentRequest(BaseModel):
    """Generic agent request."""
    action: str = Field(..., description="Action to perform")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    session_id: Optional[str] = Field(None, description="Session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    

class AgentResponse(BaseModel):
    """Generic agent response."""
    status: str = Field(..., description="Response status")
    result: Optional[Any] = Field(None, description="Action result")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    

class RAGResponse(BaseModel):
    """Response from RAG answering system."""
    answer: str = Field(..., description="Generated answer")
    sources: List[str] = Field(default_factory=list, description="Source paths referenced")
    token_count: int = Field(..., description="Estimated token count of context")
    chunks_used: List[str] = Field(default_factory=list, description="Chunk IDs used")
    model_used: str = Field(..., description="Model used for generation")
    

class ChatMessage(BaseModel):
    """Chat message for UI."""
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Component(BaseModel):
    """Component in the knowledge graph."""
    name: str = Field(..., description="Component name")
    files: List[str] = Field(default_factory=list, description="Files in this component")
    imports: List[str] = Field(default_factory=list, description="External imports")
    exports: List[str] = Field(default_factory=list, description="Exported symbols")
    dependencies: List[str] = Field(default_factory=list, description="Component dependencies")


class KnowledgeGraph(BaseModel):
    """Knowledge graph of repository structure."""
    nodes: Dict[str, Any] = Field(default_factory=dict, description="Graph nodes")
    components: Dict[str, Component] = Field(default_factory=dict, description="Components")
    relations: List[Dict[str, str]] = Field(default_factory=list, description="Relations between components")