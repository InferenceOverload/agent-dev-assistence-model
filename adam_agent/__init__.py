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
def load_repo(url: str, ref: str | None = None) -> dict:
    """
    Clone a repo (https or file://) into a local workspace and set as active root.
    Returns {loaded, files, commit, status}.
    """
    status = [f"load_repo: {url}"]
    r = _orch.load_repo(url, ref=ref)
    status += r.get("status", [])
    ing = _orch.ingest()
    status += ing.get("status", [])
    out = {"loaded": r["root"], "files": len(ing["files"]), "commit": ing["commit"], "status": status}
    return out


def ingest() -> dict:
    """
    Ingest repository and create code map and chunks.
    Returns files list, commit hash, and status logs.
    """
    out = _orch.ingest()
    return out


def decide() -> dict:
    """
    Size repository and make vectorization decision.
    Returns sizer report, vectorization decision, and status logs.
    """
    out = _orch.size_and_decide()
    return out


def index() -> dict:
    """
    Index chunks and build retriever.
    Returns indexing results with vector count and status logs.
    """
    out = _orch.index()
    return out


def ask(query: str) -> dict:
    """
    Ask a query using RAG.
    Returns answer, sources, and status logs.
    """
    out = _orch.ask(query, k=12, write_docs=False)
    return out


# ---- Create the root agent ----
root_agent = Agent(
    name="adam_agent",
    model="gemini-2.0-flash-latest",  # Use latest flash model
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