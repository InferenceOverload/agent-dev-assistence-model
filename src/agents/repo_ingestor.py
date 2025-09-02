"""Repo Ingestor Agent - Handles repository cloning and analysis."""

from google.adk.agents import Agent
from typing import Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


def clone_repository(repo_url: str, branch: Optional[str] = None) -> str:
    """Clone a repository for analysis.
    
    Args:
        repo_url: URL of the repository to clone
        branch: Optional branch to checkout
    
    Returns:
        Status message with repository information
    """
    logger.info(f"Cloning repository: {repo_url} (branch: {branch or 'main'})")
    
    # Mock implementation for testing
    return json.dumps({
        "status": "success",
        "repo_url": repo_url,
        "branch": branch or "main",
        "files_found": 42,
        "languages": ["python", "javascript", "yaml"],
        "message": f"Successfully cloned repository from {repo_url}"
    })


def analyze_codebase(repo_path: str) -> str:
    """Analyze the codebase structure and create a code map.
    
    Args:
        repo_path: Path to the cloned repository
    
    Returns:
        Code map with files, dependencies, and symbols
    """
    logger.info(f"Analyzing codebase at: {repo_path}")
    
    # Mock implementation for testing
    return json.dumps({
        "code_map": {
            "total_files": 42,
            "total_lines": 5000,
            "main_languages": ["python", "javascript"],
            "key_modules": [
                "src/agents",
                "src/tools",
                "src/services"
            ],
            "dependencies": {
                "python": ["google-adk", "vertexai", "pydantic"],
                "javascript": ["react", "typescript"]
            }
        },
        "message": "Code map generated successfully"
    })


def list_repository_files(repo_path: str, pattern: str = "*") -> str:
    """List files in the repository matching a pattern.
    
    Args:
        repo_path: Path to the repository
        pattern: Glob pattern to match files
    
    Returns:
        List of matching files
    """
    logger.info(f"Listing files in {repo_path} with pattern: {pattern}")
    
    # Mock implementation
    return json.dumps({
        "files": [
            "src/agents/orchestrator.py",
            "src/agents/repo_ingestor.py",
            "src/tools/repo_io.py",
            "README.md",
            "pyproject.toml"
        ],
        "total_count": 5
    })


# Create the ADK Agent
repo_ingestor_agent = Agent(
    name="repo_ingestor",
    model="gemini-2.0-flash-exp",
    description="Agent for cloning and analyzing repositories",
    instruction="""You are a repository ingestion specialist.
    
    Your capabilities:
    1. Clone repositories from various sources (GitHub, GitLab, etc.)
    2. Analyze codebase structure and create code maps
    3. Identify programming languages, dependencies, and key modules
    4. List and filter files based on patterns
    
    Use the available tools to:
    - clone_repository: Clone a repository from a URL
    - analyze_codebase: Create a comprehensive code map
    - list_repository_files: List files matching patterns
    
    When asked to ingest a repository, always:
    1. Clone it first
    2. Analyze the structure
    3. Report key findings
    """,
    tools=[clone_repository, analyze_codebase, list_repository_files]
)