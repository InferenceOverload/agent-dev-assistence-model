"""ADAM Agent package for Google ADK integration."""

from google import adk
from google.adk import Agent
import sys
import os
from typing import Dict, Any, Optional

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory

# Initialize a shared orchestrator instance
_orch = OrchestratorAgent(
    root=".",
    session_id="adk",
    storage_factory=StorageFactory(use_vertex=False)
)


# ---- Tools exposed to ADK ----
def load_repo(url: str, ref: str = "") -> dict:
    """
    Clone a repo (https or file://) into a local workspace and set as active root.
    
    Parameters:
        url: Repository URL (https or file://).
        ref: Optional git ref (branch, tag, or commit). Use empty string if not provided.
    
    Returns:
        Dictionary with keys: loaded (path), files (count), commit (hash), status (list).
    """
    status = [f"load_repo: {url}"]
    ref_opt = ref if ref else None  # Convert empty string to None for internal use
    r = _orch.load_repo(url, ref=ref_opt)
    status += r.get("status", [])
    ing = _orch.ingest()
    status += ing.get("status", [])
    out = {"loaded": r["root"], "files": len(ing["files"]), "commit": ing["commit"], "status": status}
    return out


def ingest() -> dict:
    """
    Ingest the current repository root.
    
    Returns:
        Dictionary with keys: files (list), commit (hash), status (list).
    """
    return _orch.ingest()


def decide() -> dict:
    """
    Compute sizing and vectorization policy decision.
    
    Returns:
        Dictionary with keys: sizer (report), vectorization (decision), status (list).
    """
    return _orch.size_and_decide()


def index() -> dict:
    """
    Build an in-memory index (embeddings + retriever).
    
    Returns:
        Dictionary with keys: session_id, vector_count, backend, status (list).
    """
    return _orch.index()


def ask(query: str, k: int = 50) -> dict:
    """
    Answer a question about the current repository.
    
    Parameters:
        query: The user question.
        k: Top-k chunks to retrieve (default 50). Use larger k for small repos.
    
    Returns:
        Dictionary with keys: answer, sources (list), token_count, model_used, status (list).
    """
    return _orch.ask(query, k=int(k), write_docs=False)


# ---- Create the root agent ----
root_agent = Agent(
    name="adam_agent",
    model="gemini-2.0-flash-exp",  # Use stable flash experimental model
    description="Repo analysis & RAG helper",
    instruction=(
        "You are a repo analysis assistant. "
        "Always use tools to ground your answers. "
        "When the user provides a repository URL, call load_repo(url) first. "
        "Before answering repo questions, call ingest -> decide -> index. "
        "Do NOT answer from prior knowledge; rely on tool outputs."
    ),
    tools=[load_repo, ingest, decide, index, ask],
)