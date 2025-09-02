"""Orchestrator Agent - Root agent for intent routing and sub-agent coordination."""

from google.adk.agents import Agent
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def route_to_agent(intent: str, query: str) -> str:
    """Route user query to appropriate sub-agent based on intent.
    
    Args:
        intent: Detected intent (ingest, ask, plan, develop, sandbox)
        query: User query to process
    
    Returns:
        Response from the appropriate sub-agent
    """
    logger.info(f"Routing intent '{intent}' with query: {query}")
    
    # Mock routing logic for testing
    routing_map = {
        "ingest": "repo_ingestor_agent",
        "ask": "rag_answerer_agent",
        "plan": "rally_planner_agent",
        "develop": "dev_pr_agent",
        "sandbox": "sandbox_runner_agent",
        "index": "indexer_agent",
    }
    
    agent_name = routing_map.get(intent, "unknown")
    return f"[{agent_name}] Processing: {query}"


def detect_intent(query: str) -> str:
    """Detect user intent from query.
    
    Args:
        query: User query
    
    Returns:
        Detected intent category
    """
    query_lower = query.lower()
    
    # Simple keyword-based intent detection for testing
    if any(word in query_lower for word in ["clone", "ingest", "repo", "repository"]):
        return "ingest"
    elif any(word in query_lower for word in ["what", "how", "why", "explain", "tell"]):
        return "ask"
    elif any(word in query_lower for word in ["plan", "story", "rally", "ticket"]):
        return "plan"
    elif any(word in query_lower for word in ["implement", "code", "develop", "pr", "pull"]):
        return "develop"
    elif any(word in query_lower for word in ["deploy", "sandbox", "preview", "cloud run"]):
        return "sandbox"
    elif any(word in query_lower for word in ["index", "embed", "vector"]):
        return "index"
    else:
        return "ask"  # Default to Q&A


# Create the ADK Agent
orchestrator_agent = Agent(
    name="orchestrator",
    model="gemini-2.0-flash-exp",
    description="Root orchestrator that routes requests to specialized sub-agents",
    instruction="""You are the orchestrator for a multi-agent system.
    
    Your role is to:
    1. Understand user intent from their queries
    2. Route requests to the appropriate specialized agent
    3. Coordinate responses from multiple agents when needed
    
    Available sub-agents:
    - repo_ingestor: Clones and analyzes repositories
    - indexer: Creates embeddings and manages vector indices
    - rag_answerer: Answers questions using retrieval-augmented generation
    - rally_planner: Creates Rally work items from requirements
    - dev_pr: Implements stories and creates pull requests
    - sandbox_runner: Deploys Cloud Run preview environments
    - code_exec: Runs tests using built-in code execution
    
    Use the detect_intent and route_to_agent tools to process requests.
    """,
    tools=[detect_intent, route_to_agent],
)

# After all agents are imported, we'll add sub_agents
# This will be done in __init__.py to avoid circular imports