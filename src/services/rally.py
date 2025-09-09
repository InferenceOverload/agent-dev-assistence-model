"""Rally API client for creating features, stories, and tasks.

Uses Rally Web Services API v2 with robust retries and error handling.
"""

import os
import time
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote
import httpx
from src.core.logging import get_logger

logger = get_logger(__name__)


class RallyClient:
    """Client for Rally Web Services API v2."""
    
    def __init__(self):
        """Initialize Rally client with environment configuration."""
        self.base_url = os.getenv("RALLY_BASE_URL", "https://rally1.rallydev.com")
        self.api_key = os.getenv("RALLY_API_KEY")
        self.workspace_id = os.getenv("RALLY_WORKSPACE_ID")
        self.project_id = os.getenv("RALLY_PROJECT_ID")
        
        if not self.api_key:
            raise ValueError("RALLY_API_KEY environment variable is required")
        if not self.workspace_id:
            raise ValueError("RALLY_WORKSPACE_ID environment variable is required")
        if not self.project_id:
            raise ValueError("RALLY_PROJECT_ID environment variable is required")
            
        self.client = httpx.Client(
            headers={
                "ZSESSIONID": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30.0
        )
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     retries: int = 3) -> Dict[str, Any]:
        """Make API request with retries and error handling.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request payload
            retries: Number of retry attempts
            
        Returns:
            Response data
            
        Raises:
            httpx.HTTPError: On request failure
        """
        url = f"{self.base_url}/slm/webservice/v2.0/{endpoint}"
        
        for attempt in range(retries):
            try:
                if method == "GET":
                    response = self.client.get(url)
                elif method == "POST":
                    response = self.client.post(url, json=data)
                elif method == "PUT":
                    response = self.client.put(url, json=data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                response.raise_for_status()
                
                result = response.json()
                if "CreateResult" in result:
                    create_result = result["CreateResult"]
                    if create_result.get("Errors"):
                        error_msg = "; ".join(create_result["Errors"])
                        raise Exception(f"Rally API error: {error_msg}")
                    return create_result
                elif "QueryResult" in result:
                    return result["QueryResult"]
                elif "OperationResult" in result:
                    op_result = result["OperationResult"]
                    if op_result.get("Errors"):
                        error_msg = "; ".join(op_result["Errors"])
                        raise Exception(f"Rally API error: {error_msg}")
                    return op_result
                else:
                    return result
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < retries - 1:
                    # Rate limited, exponential backoff
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif e.response.status_code >= 500 and attempt < retries - 1:
                    # Server error, retry with backoff
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error {e.response.status_code}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Rally API request failed: {e}")
                    raise
            except Exception as e:
                logger.error(f"Rally API request error: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
                
        raise Exception(f"Failed after {retries} attempts")
        
    def create_feature(self, title: str, description: str, tags: Optional[List[str]] = None) -> Dict[str, str]:
        """Create a Rally Feature (PortfolioItem).
        
        Args:
            title: Feature title
            description: Feature description
            tags: Optional tags
            
        Returns:
            Dict with "id" and "url" of created feature
        """
        data = {
            "PortfolioItem/Feature": {
                "Name": title,
                "Description": description,
                "Project": {"_ref": f"/project/{self.project_id}"},
                "Workspace": {"_ref": f"/workspace/{self.workspace_id}"}
            }
        }
        
        if tags:
            # Query for existing tags and create if needed
            tag_refs = []
            for tag_name in tags:
                tag_query = f'(Name = "{tag_name}")'
                tag_result = self._make_request("GET", f"tag?query={quote(tag_query)}&workspace=/workspace/{self.workspace_id}")
                
                if tag_result.get("TotalResultCount", 0) > 0:
                    tag_refs.append({"_ref": tag_result["Results"][0]["_ref"]})
                else:
                    # Create new tag
                    tag_data = {
                        "Tag": {
                            "Name": tag_name,
                            "Workspace": {"_ref": f"/workspace/{self.workspace_id}"}
                        }
                    }
                    tag_create = self._make_request("POST", "tag/create", tag_data)
                    if tag_create.get("Object"):
                        tag_refs.append({"_ref": tag_create["Object"]["_ref"]})
                        
            if tag_refs:
                data["PortfolioItem/Feature"]["Tags"] = tag_refs
                
        result = self._make_request("POST", "portfolioitem/feature/create", data)
        
        if result.get("Object"):
            obj = result["Object"]
            feature_id = str(obj["ObjectID"])
            feature_url = f"{self.base_url}/#/detail/portfolioitem/feature/{feature_id}"
            logger.info(f"Created feature: {title} (ID: {feature_id})")
            return {"id": feature_id, "url": feature_url}
        else:
            raise Exception("Failed to create feature")
            
    def create_story(self, feature_id: Optional[str], title: str, description: str,
                    acceptance_criteria: List[str], estimate: Optional[int] = None,
                    tags: Optional[List[str]] = None) -> Dict[str, str]:
        """Create a Rally User Story (HierarchicalRequirement).
        
        Args:
            feature_id: Parent feature ObjectID (optional)
            title: Story title
            description: Story description
            acceptance_criteria: List of acceptance criteria
            estimate: Story points estimate (optional)
            tags: Optional tags
            
        Returns:
            Dict with "id" and "url" of created story
        """
        # Format acceptance criteria as HTML list
        ac_html = "<ul>" + "".join(f"<li>{ac}</li>" for ac in acceptance_criteria) + "</ul>"
        
        data = {
            "HierarchicalRequirement": {
                "Name": title,
                "Description": description,
                "AcceptanceCriteria": ac_html,
                "Project": {"_ref": f"/project/{self.project_id}"},
                "Workspace": {"_ref": f"/workspace/{self.workspace_id}"}
            }
        }
        
        if feature_id:
            data["HierarchicalRequirement"]["PortfolioItem"] = {
                "_ref": f"/portfolioitem/feature/{feature_id}"
            }
            
        if estimate is not None:
            data["HierarchicalRequirement"]["PlanEstimate"] = estimate
            
        result = self._make_request("POST", "hierarchicalrequirement/create", data)
        
        if result.get("Object"):
            obj = result["Object"]
            story_id = str(obj["ObjectID"])
            story_url = f"{self.base_url}/#/detail/userstory/{story_id}"
            logger.info(f"Created story: {title} (ID: {story_id})")
            return {"id": story_id, "url": story_url}
        else:
            raise Exception("Failed to create story")
            
    def create_task(self, story_id: str, title: str, description: str,
                   estimate: Optional[float] = None, tags: Optional[List[str]] = None) -> Dict[str, str]:
        """Create a Rally Task.
        
        Args:
            story_id: Parent story ObjectID
            title: Task title
            description: Task description
            estimate: Task estimate in hours (optional)
            tags: Optional tags
            
        Returns:
            Dict with "id" and "url" of created task
        """
        data = {
            "Task": {
                "Name": title,
                "Description": description,
                "WorkProduct": {"_ref": f"/hierarchicalrequirement/{story_id}"},
                "Project": {"_ref": f"/project/{self.project_id}"},
                "Workspace": {"_ref": f"/workspace/{self.workspace_id}"}
            }
        }
        
        if estimate is not None:
            data["Task"]["Estimate"] = estimate
            
        result = self._make_request("POST", "task/create", data)
        
        if result.get("Object"):
            obj = result["Object"]
            task_id = str(obj["ObjectID"])
            task_url = f"{self.base_url}/#/detail/task/{task_id}"
            logger.info(f"Created task: {title} (ID: {task_id})")
            return {"id": task_id, "url": task_url}
        else:
            raise Exception("Failed to create task")
            
    def get_feature(self, feature_id: str) -> Dict[str, Any]:
        """Get a Rally Feature by ID.
        
        Args:
            feature_id: Feature FormattedID (e.g., "F123456") or ObjectID
            
        Returns:
            Feature details including name, description, state, owner
            
        Raises:
            Exception: If feature not found
        """
        # Determine if ID is FormattedID or ObjectID
        if feature_id.upper().startswith('F'):
            # FormattedID query
            query = f'(FormattedID = "{feature_id.upper()}")'
            endpoint = f"portfolioitem/feature?query={quote(query)}&workspace=/workspace/{self.workspace_id}&fetch=Name,Description,State,Owner,FormattedID,ObjectID,AcceptedLeafStoryCount,LeafStoryCount"
        else:
            # Direct ObjectID lookup
            endpoint = f"portfolioitem/feature/{feature_id}?fetch=Name,Description,State,Owner,FormattedID,ObjectID,AcceptedLeafStoryCount,LeafStoryCount"
            
        try:
            result = self._make_request("GET", endpoint)
            
            if "Results" in result and result.get("TotalResultCount", 0) > 0:
                feature = result["Results"][0]
            elif "_ref" in result:
                feature = result
            else:
                raise Exception(f"Feature {feature_id} not found")
                
            return {
                "id": str(feature.get("ObjectID", "")),
                "formatted_id": feature.get("FormattedID", ""),
                "name": feature.get("Name", ""),
                "description": feature.get("Description", ""),
                "state": feature.get("State", {}).get("Name", "") if feature.get("State") else "",
                "owner": feature.get("Owner", {}).get("_refObjectName", "") if feature.get("Owner") else "",
                "story_count": feature.get("LeafStoryCount", 0),
                "accepted_story_count": feature.get("AcceptedLeafStoryCount", 0),
                "url": f"{self.base_url}/#/detail/portfolioitem/feature/{feature.get('ObjectID', '')}"
            }
        except Exception as e:
            logger.error(f"Failed to get feature {feature_id}: {e}")
            raise Exception(f"Feature {feature_id} not found in Rally. Please check the feature ID.")
            
    def validate_feature_context(self, feature_details: Dict[str, Any], requirement: str) -> Dict[str, Any]:
        """Validate if a requirement matches feature context.
        
        Args:
            feature_details: Feature details from get_feature()
            requirement: User requirement text
            
        Returns:
            Validation result with confidence and reason
        """
        feature_name = feature_details.get("name", "").lower()
        feature_desc = feature_details.get("description", "").lower()
        requirement_lower = requirement.lower()
        
        # Extract key terms from requirement
        req_words = set(word for word in requirement_lower.split() 
                       if len(word) > 3 and word not in ["this", "that", "with", "from", "have"])
        
        # Check for matches in feature name and description
        name_matches = sum(1 for word in req_words if word in feature_name)
        desc_matches = sum(1 for word in req_words if word in feature_desc)
        
        total_words = len(req_words)
        if total_words == 0:
            return {
                "valid": True,
                "confidence": 0.5,
                "reason": "Unable to extract meaningful terms from requirement"
            }
            
        match_ratio = (name_matches * 2 + desc_matches) / (total_words * 2)  # Name matches weighted higher
        
        if match_ratio >= 0.5:
            return {
                "valid": True,
                "confidence": match_ratio,
                "reason": f"Requirement matches feature '{feature_details.get('name', '')}'"
            }
        elif match_ratio >= 0.25:
            return {
                "valid": True,
                "confidence": match_ratio,
                "reason": f"Partial match with feature '{feature_details.get('name', '')}'. Consider reviewing the alignment."
            }
        else:
            return {
                "valid": False,
                "confidence": match_ratio,
                "reason": f"Feature '{feature_details.get('name', '')}' appears to be about different functionality. The requirement doesn't align well with this feature's scope."
            }
            
    def link_artifact(self, item_id: str, url: str, description: str = "Related artifact") -> Dict[str, bool]:
        """Link an external artifact to a Rally item.
        
        Args:
            item_id: Rally item ObjectID
            url: External URL
            description: Link description
            
        Returns:
            Success status
        """
        # First, determine the type of the item
        for item_type in ["hierarchicalrequirement", "portfolioitem/feature", "task"]:
            try:
                # Try to get the item
                item_result = self._make_request("GET", f"{item_type}/{item_id}")
                if item_result:
                    # Add to the item's notes or description
                    update_data = {
                        item_type.split("/")[-1].title(): {
                            "ObjectID": item_id,
                            "Notes": f"<p>{description}: <a href='{url}'>{url}</a></p>"
                        }
                    }
                    
                    self._make_request("POST", f"{item_type}/{item_id}", update_data)
                    logger.info(f"Linked artifact to {item_type} {item_id}: {url}")
                    return {"ok": True}
            except:
                continue
                
        logger.warning(f"Could not find Rally item {item_id}")
        return {"ok": False}
        
    def __del__(self):
        """Cleanup client on deletion."""
        if hasattr(self, 'client'):
            self.client.close()


# Convenience functions for direct use
_client = None

def get_client() -> RallyClient:
    """Get or create Rally client singleton."""
    global _client
    if _client is None:
        _client = RallyClient()
    return _client

def create_feature(title: str, description: str, tags: Optional[List[str]] = None) -> Dict[str, str]:
    """Create a Rally feature."""
    return get_client().create_feature(title, description, tags)

def create_story(feature_id: Optional[str], title: str, description: str,
                acceptance_criteria: List[str], estimate: Optional[int] = None,
                tags: Optional[List[str]] = None) -> Dict[str, str]:
    """Create a Rally story."""
    return get_client().create_story(feature_id, title, description, acceptance_criteria, estimate, tags)

def create_task(story_id: str, title: str, description: str,
               estimate: Optional[float] = None, tags: Optional[List[str]] = None) -> Dict[str, str]:
    """Create a Rally task."""
    return get_client().create_task(story_id, title, description, estimate, tags)

def link_artifact(item_id: str, url: str, description: str = "Related artifact") -> Dict[str, bool]:
    """Link an artifact to a Rally item."""
    return get_client().link_artifact(item_id, url, description)