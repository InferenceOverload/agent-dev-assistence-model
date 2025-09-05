"""Rally reader service for fetching existing work items."""

import os
from typing import Dict, Any, Optional
from src.services.rally import RallyClient
from src.core.logging import get_logger

logger = get_logger(__name__)


def get_story(story_id: str) -> Dict[str, Any]:
    """Fetch a Rally story by ID.
    
    Args:
        story_id: Rally story ObjectID
        
    Returns:
        Story details including title, description, acceptance criteria
    """
    try:
        client = RallyClient()
        # Use the REST API to get story details
        result = client._make_request("GET", f"hierarchicalrequirement/{story_id}")
        
        if result:
            story = result
            return {
                "id": story_id,
                "title": story.get("Name", ""),
                "description": story.get("Description", ""),
                "acceptance_criteria": story.get("AcceptanceCriteria", ""),
                "state": story.get("ScheduleState", ""),
                "estimate": story.get("PlanEstimate"),
                "feature": story.get("PortfolioItem", {}).get("_ref", "").split("/")[-1] if story.get("PortfolioItem") else None,
                "url": f"{client.base_url}/#/detail/userstory/{story_id}"
            }
    except Exception as e:
        logger.error(f"Failed to fetch story {story_id}: {e}")
        return {"error": str(e)}


def get_feature(feature_id: str) -> Dict[str, Any]:
    """Fetch a Rally feature by ID.
    
    Args:
        feature_id: Rally feature ObjectID
        
    Returns:
        Feature details
    """
    try:
        client = RallyClient()
        result = client._make_request("GET", f"portfolioitem/feature/{feature_id}")
        
        if result:
            feature = result
            return {
                "id": feature_id,
                "title": feature.get("Name", ""),
                "description": feature.get("Description", ""),
                "state": feature.get("State", {}).get("Name", "") if feature.get("State") else "",
                "url": f"{client.base_url}/#/detail/portfolioitem/feature/{feature_id}"
            }
    except Exception as e:
        logger.error(f"Failed to fetch feature {feature_id}: {e}")
        return {"error": str(e)}


def get_story_context(story_id: str) -> Dict[str, Any]:
    """Get full context for a story including parent feature.
    
    Args:
        story_id: Rally story ObjectID
        
    Returns:
        Combined story and feature context
    """
    context = {"story": {}, "feature": {}}
    
    # Get the story
    story = get_story(story_id)
    context["story"] = story
    
    # Get parent feature if exists
    if story and story.get("feature"):
        feature = get_feature(story["feature"])
        context["feature"] = feature
        
    return context