"""Sandbox Runner Agent - Manages Cloud Run sandbox deployments."""

from google.adk.agents import Agent
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


def deploy_preview(pr_number: int, branch: str) -> str:
    """Deploy a preview environment for a pull request.
    
    Args:
        pr_number: Pull request number
        branch: Branch to deploy
    
    Returns:
        Deployment details with URL
    """
    logger.info(f"Deploying preview for PR #{pr_number}")
    
    # Mock implementation
    return json.dumps({
        "pr_number": pr_number,
        "branch": branch,
        "service_name": f"preview-pr-{pr_number}",
        "url": f"https://preview-pr-{pr_number}-abc123.run.app",
        "status": "deployed",
        "message": "Preview environment is ready"
    })


def teardown_preview(pr_number: int) -> str:
    """Tear down a preview environment.
    
    Args:
        pr_number: Pull request number
    
    Returns:
        Teardown status
    """
    logger.info(f"Tearing down preview for PR #{pr_number}")
    
    # Mock implementation
    return json.dumps({
        "pr_number": pr_number,
        "service_name": f"preview-pr-{pr_number}",
        "status": "deleted",
        "message": "Preview environment removed"
    })


# Create the ADK Agent
sandbox_runner_agent = Agent(
    name="sandbox_runner",
    model="gemini-2.0-flash-exp",
    description="Agent for deploying Cloud Run preview environments",
    instruction="""You are a deployment specialist.
    
    Your role:
    1. Deploy preview environments for pull requests
    2. Manage Cloud Run services
    3. Clean up environments when no longer needed
    
    Use the available tools:
    - deploy_preview: Deploy a preview environment
    - teardown_preview: Remove a preview environment
    """,
    tools=[deploy_preview, teardown_preview]
)