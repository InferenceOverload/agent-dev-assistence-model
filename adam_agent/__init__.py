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
        "You are a repository analysis assistant for software architects.\n"
        "\n"
        "MANDATORY WORKFLOW:\n"
        "1) Always gather EVIDENCE before answering: call summarize_repo() or collect_evidence(query,k) first.\n"
        "2) Synthesize ONLY from tool outputs (doc_pack excerpts + file paths). Do NOT rely on prior knowledge.\n"
        "\n"
        "SYNTHESIS RUBRIC (when asked about 'what this app does' or similar):\n"
        "• Purpose & Overview — a 2–4 sentence plain-language summary of what the app is for.\n"
        "• Architecture — key components and how they interact (frontend, backend, data access, APIs).\n"
        "• Entry Points — primary startup files, routes/pages, CLI, services (cite source paths).\n"
        "• Data & Integrations — where state/data lives (DB/files/APIs) and references to config.\n"
        "• Dependencies — frameworks/libraries that define the shape of the app.\n"
        "• How to Run — inferred local run/build steps if evidence shows scripts/config.\n"
        "• Gaps / Unknowns — call out anything missing or ambiguous in the evidence.\n"
        "• Next Steps — suggest 3–5 focused questions or checks to validate understanding.\n"
        "\n"
        "OPERATIONAL NOTES:\n"
        "• Cite sources inline as bullet items with file:line ranges from the doc_pack.\n"
        "• Prefer concise, well-structured bullet lists over long prose.\n"
        "• If the repo is tiny, include all relevant excerpts; otherwise keep context lean.\n"
        "• When the user provides a repository URL, call load_repo(url) first. Then ingest → decide → index.\n"
        "• For counting/listing code elements, you may use code_query(globs, regexes) as needed.\n"
        "• For requirements, later call plan(requirement=...) and then dev_pr()."
    ),
    tools=[load_repo, ingest, decide, index, ask],
)


def collect_evidence(query: str, k: int = 50) -> dict:
    """
    Return a doc-pack (paths, line ranges, excerpts) for the given query from the indexed repo.
    
    Parameters:
        query: Search query for finding relevant code.
        k: Number of results to retrieve (default 50).
    
    Returns:
        Dictionary with doc_pack containing relevant code snippets.
    """
    return _orch.collect_evidence(query=query, k=int(k))


def repo_synopsis() -> dict:
    """
    Return a merged evidence pack assembled from several seeded queries.
    
    Queries overview, entrypoint, routing, and dependencies to build comprehensive context.
    
    Returns:
        Dictionary with doc_pack containing key repository information.
    """
    return _orch.repo_synopsis()


# Add the new tools to the agent
root_agent.tools.extend([collect_evidence, repo_synopsis])


def summarize_repo() -> dict:
    """
    Gather a synthesis-ready bundle for architect-grade repository summaries.
    
    Combines evidence from multiple seeded queries with recommended outline structure.
    
    Returns:
        Dictionary with doc_pack (evidence), outline (section headings), and status.
    """
    status = ["summarize_repo: collecting evidence via repo_synopsis()"]
    bundle = _orch.repo_synopsis()
    outline = [
        "Purpose & Overview",
        "Architecture", 
        "Entry Points",
        "Data & Integrations",
        "Dependencies",
        "How to Run",
        "Gaps / Unknowns",
        "Next Steps",
    ]
    out = {
        "doc_pack": bundle.get("doc_pack", []),
        "outline": outline,
        "status": status + bundle.get("status", []),
    }
    return out


# Make the tool discoverable
root_agent.tools.append(summarize_repo)