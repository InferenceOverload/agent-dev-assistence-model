"""Main agent module for ADK."""

from google.adk.agents import Agent
# Orchestrator is now class-based, no longer provides these functions
# from .orchestrator import detect_intent, route_to_agent
from .repo_ingestor import ingest_repo
from .rag_answerer import RAGAnswerer
# Indexer is now class-based, no longer provides these functions
# from .indexer import create_embeddings, index_vectors
from .planner_rally import create_user_story, plan_sprint_work
from .dev_pr import implement_feature, create_pull_request
from .sandbox_runner import deploy_preview, teardown_preview
from .code_exec_agent import run_python_tests, execute_code_snippet

# Create the root agent that ADK expects
root_agent = Agent(
    name="orchestrator",
    model="gemini-2.0-flash-exp",
    description="Root orchestrator that routes requests to specialized sub-agents",
    instruction="""You are the orchestrator for a multi-agent system.
    
    Your role is to:
    1. Understand user intent from their queries
    2. Route requests to the appropriate specialized agent or tool
    3. Coordinate responses when multiple capabilities are needed
    
    Available capabilities through your tools:
    - Repository ingestion: Clone and analyze codebases
    - Code search and Q&A: Search code and answer questions
    - Work planning: Create Rally stories and plan sprints
    - Development: Implement features and create pull requests
    - Deployment: Deploy preview environments
    - Testing: Run tests and execute code
    
    Use the available tools to process user requests.
    """,
    tools=[
        # Repo ingestion tools
        ingest_repo,
        # Note: RAGAnswerer is a class, not directly used as tools
        # RAG functionality should be accessed through orchestrator
        # Orchestration and indexing are now class-based
        # Planning tools
        create_user_story,
        plan_sprint_work,
        # Development tools
        implement_feature,
        create_pull_request,
        # Deployment tools
        deploy_preview,
        teardown_preview,
        # Testing tools
        run_python_tests,
        execute_code_snippet,
    ]
)