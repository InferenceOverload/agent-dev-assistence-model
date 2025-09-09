"""Rally authentication and connection validation service."""

import os
from typing import Dict, List, Optional, Any
from src.services.rally import RallyClient
from src.core.logging import get_logger

logger = get_logger(__name__)


def validate_rally_connection() -> bool:
    """Test Rally connection with a simple query.
    
    Returns:
        True if authenticated and accessible, False otherwise
    """
    try:
        client = RallyClient()
        # Try a simple query to verify connection
        result = client._make_request("GET", f"workspace/{client.workspace_id}?fetch=Name")
        if result and result.get("Name"):
            logger.info(f"Rally connection validated. Workspace: {result.get('Name')}")
            return True
        return False
    except Exception as e:
        logger.error(f"Rally connection validation failed: {e}")
        return False


def get_user_workspaces() -> List[Dict[str, str]]:
    """List available workspaces for the authenticated user.
    
    Returns:
        List of workspace dictionaries with id, name, and state
    """
    try:
        client = RallyClient()
        result = client._make_request("GET", "subscription?fetch=Workspaces")
        
        workspaces = []
        if result and result.get("Workspaces"):
            workspace_results = client._make_request("GET", result["Workspaces"]["_ref"].split("/slm/webservice/v2.0/")[-1] + "?fetch=Name,State,ObjectID")
            if workspace_results and workspace_results.get("Results"):
                for ws in workspace_results["Results"]:
                    workspaces.append({
                        "id": str(ws.get("ObjectID", "")),
                        "name": ws.get("Name", ""),
                        "state": ws.get("State", "")
                    })
        return workspaces
    except Exception as e:
        logger.error(f"Failed to get workspaces: {e}")
        return []


def get_workspace_projects(workspace_id: Optional[str] = None) -> List[Dict[str, str]]:
    """List projects in a workspace.
    
    Args:
        workspace_id: Workspace ObjectID (uses env default if not provided)
        
    Returns:
        List of project dictionaries with id, name, and state
    """
    try:
        client = RallyClient()
        ws_id = workspace_id or client.workspace_id
        
        result = client._make_request("GET", f"project?workspace=/workspace/{ws_id}&fetch=Name,State,ObjectID")
        
        projects = []
        if result and result.get("Results"):
            for proj in result["Results"]:
                projects.append({
                    "id": str(proj.get("ObjectID", "")),
                    "name": proj.get("Name", ""),
                    "state": proj.get("State", "")
                })
        return projects
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        return []


def check_rally_environment() -> Dict[str, Any]:
    """Check Rally environment configuration.
    
    Returns:
        Dictionary with configuration status and any issues
    """
    issues = []
    config = {
        "api_key": bool(os.getenv("RALLY_API_KEY")),
        "workspace_id": bool(os.getenv("RALLY_WORKSPACE_ID")),
        "project_id": bool(os.getenv("RALLY_PROJECT_ID")),
        "base_url": os.getenv("RALLY_BASE_URL", "https://rally1.rallydev.com")
    }
    
    if not config["api_key"]:
        issues.append("RALLY_API_KEY environment variable not set")
    if not config["workspace_id"]:
        issues.append("RALLY_WORKSPACE_ID environment variable not set")
    if not config["project_id"]:
        issues.append("RALLY_PROJECT_ID environment variable not set")
    
    # Try to validate connection if all required vars are present
    connection_valid = False
    if not issues:
        connection_valid = validate_rally_connection()
        if not connection_valid:
            issues.append("Failed to connect to Rally with provided credentials")
    
    return {
        "configured": len(issues) == 0,
        "connection_valid": connection_valid,
        "config": config,
        "issues": issues
    }


def setup_rally_environment() -> Dict[str, Any]:
    """Interactive setup helper for Rally environment.
    
    Returns:
        Setup instructions and current status
    """
    status = check_rally_environment()
    
    instructions = []
    if not status["configured"]:
        instructions.append("To configure Rally integration, set the following environment variables:")
        instructions.append("")
        instructions.append("1. RALLY_API_KEY: Your Rally API key (zsessionid)")
        instructions.append("   - Get this from Rally -> User Menu -> API Keys")
        instructions.append("")
        instructions.append("2. RALLY_WORKSPACE_ID: Your workspace ObjectID")
        instructions.append("   - Find in Rally URL: .../workspace/{ID}/...")
        instructions.append("")
        instructions.append("3. RALLY_PROJECT_ID: Your project ObjectID")
        instructions.append("   - Find in Rally URL: .../project/{ID}/...")
        instructions.append("")
        instructions.append("Optional:")
        instructions.append("4. RALLY_BASE_URL: Rally instance URL (default: https://rally1.rallydev.com)")
        instructions.append("")
        instructions.append("Example:")
        instructions.append("export RALLY_API_KEY='_abc123...'")
        instructions.append("export RALLY_WORKSPACE_ID='12345678'")
        instructions.append("export RALLY_PROJECT_ID='87654321'")
    else:
        instructions.append("Rally is configured and ready to use!")
        if status["connection_valid"]:
            instructions.append("✓ Connection to Rally verified successfully")
        
    return {
        "status": status,
        "instructions": "\n".join(instructions)
    }