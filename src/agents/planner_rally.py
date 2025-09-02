"""Rally Planner Agent - Creates Rally work items from requirements."""

from google.adk.agents import Agent
from typing import Dict, Any, List
import logging
import json

logger = logging.getLogger(__name__)


def create_user_story(title: str, description: str, acceptance_criteria_json: str) -> str:
    """Create a Rally user story.
    
    Args:
        title: Story title
        description: Story description
        acceptance_criteria_json: JSON string of acceptance criteria
    
    Returns:
        Created story details
    """
    # Parse JSON input
    import json
    try:
        acceptance_criteria = json.loads(acceptance_criteria_json) if acceptance_criteria_json else []
    except json.JSONDecodeError:
        acceptance_criteria = []
    
    logger.info(f"Creating user story: {title}")
    
    # Mock implementation
    return json.dumps({
        "story_id": "US12345",
        "title": title,
        "description": description,
        "acceptance_criteria": acceptance_criteria,
        "status": "created",
        "url": "https://rally.example.com/story/US12345"
    })


def plan_sprint_work(requirements: str, sprint_name: str) -> str:
    """Plan work for a sprint based on requirements.
    
    Args:
        requirements: Requirements text
        sprint_name: Target sprint name
    
    Returns:
        Sprint plan with stories and tasks
    """
    logger.info(f"Planning sprint: {sprint_name}")
    
    # Mock implementation
    return json.dumps({
        "sprint": sprint_name,
        "stories": [
            {"id": "US12345", "title": "Implement authentication", "points": 5},
            {"id": "US12346", "title": "Add user dashboard", "points": 8}
        ],
        "total_points": 13,
        "status": "planned"
    })


# Create the ADK Agent
rally_planner_agent = Agent(
    name="rally_planner",
    model="gemini-2.0-flash-exp",
    description="Agent for creating Rally work items from requirements",
    instruction="""You are a project planning specialist.
    
    Your role:
    1. Convert requirements into actionable user stories
    2. Create Rally work items with clear acceptance criteria
    3. Plan sprint work and estimate story points
    
    Use the available tools:
    - create_user_story: Create Rally user stories
    - plan_sprint_work: Plan work for sprints
    """,
    tools=[create_user_story, plan_sprint_work]
)