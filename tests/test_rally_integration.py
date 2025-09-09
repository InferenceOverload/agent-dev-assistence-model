"""Integration tests for Rally API client and feature validation."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.rally import RallyClient
from src.services.rally_auth import (
    validate_rally_connection,
    get_user_workspaces,
    get_workspace_projects,
    check_rally_environment,
    setup_rally_environment
)
from src.agents.rally_planner import apply_to_rally, plan_from_requirement


class TestRallyClient:
    """Test Rally client functionality."""
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('httpx.Client')
    def test_get_feature_by_formatted_id(self, mock_client_class):
        """Test fetching feature by FormattedID."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "QueryResult": {
                "TotalResultCount": 1,
                "Results": [{
                    "ObjectID": 123456,
                    "FormattedID": "F12345",
                    "Name": "Authentication System",
                    "Description": "Implement OAuth2 authentication",
                    "State": {"Name": "In Progress"},
                    "Owner": {"_refObjectName": "John Doe"},
                    "LeafStoryCount": 5,
                    "AcceptedLeafStoryCount": 2
                }]
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        
        # Test
        client = RallyClient()
        result = client.get_feature("F12345")
        
        # Verify
        assert result["id"] == "123456"
        assert result["formatted_id"] == "F12345"
        assert result["name"] == "Authentication System"
        assert result["state"] == "In Progress"
        assert result["owner"] == "John Doe"
        assert result["story_count"] == 5
        assert result["accepted_story_count"] == 2
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('httpx.Client')
    def test_get_feature_by_object_id(self, mock_client_class):
        """Test fetching feature by ObjectID."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "_ref": "/portfolioitem/feature/123456",
            "ObjectID": 123456,
            "FormattedID": "F12345",
            "Name": "Payment Gateway",
            "Description": "Integrate Stripe payment processing",
            "State": {"Name": "Planning"},
            "Owner": None,
            "LeafStoryCount": 0,
            "AcceptedLeafStoryCount": 0
        }
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        
        # Test
        client = RallyClient()
        result = client.get_feature("123456")
        
        # Verify
        assert result["id"] == "123456"
        assert result["name"] == "Payment Gateway"
        assert result["state"] == "Planning"
        assert result["owner"] == ""
        assert result["story_count"] == 0
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('httpx.Client')
    def test_get_feature_not_found(self, mock_client_class):
        """Test fetching non-existent feature."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "QueryResult": {
                "TotalResultCount": 0,
                "Results": []
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        
        # Test
        client = RallyClient()
        with pytest.raises(Exception) as exc_info:
            client.get_feature("F99999")
        
        assert "Feature F99999 not found" in str(exc_info.value)
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('httpx.Client')
    def test_validate_feature_context_high_match(self, mock_client_class):
        """Test validating requirement with high feature match."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = RallyClient()
        
        feature_details = {
            "name": "Authentication System",
            "description": "Implement OAuth2 authentication with Google and GitHub"
        }
        
        requirement = "Add OAuth2 authentication support for Google login"
        
        result = client.validate_feature_context(feature_details, requirement)
        
        assert result["valid"] is True
        assert result["confidence"] >= 0.5
        assert "matches feature" in result["reason"]
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('httpx.Client')
    def test_validate_feature_context_low_match(self, mock_client_class):
        """Test validating requirement with low feature match."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = RallyClient()
        
        feature_details = {
            "name": "Payment Gateway",
            "description": "Integrate Stripe for payment processing"
        }
        
        requirement = "Add OAuth2 authentication support for Google login"
        
        result = client.validate_feature_context(feature_details, requirement)
        
        assert result["valid"] is False
        assert result["confidence"] < 0.25
        assert "different functionality" in result["reason"]
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('httpx.Client')
    def test_validate_feature_context_partial_match(self, mock_client_class):
        """Test validating requirement with partial feature match."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = RallyClient()
        
        feature_details = {
            "name": "User Management",
            "description": "Basic user registration and profile management"
        }
        
        requirement = "Add user authentication and login functionality"
        
        result = client.validate_feature_context(feature_details, requirement)
        
        assert result["valid"] is True
        assert 0.25 <= result["confidence"] < 0.5
        assert "Partial match" in result["reason"] or "Consider reviewing" in result["reason"]


class TestRallyAuth:
    """Test Rally authentication and setup helpers."""
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('src.services.rally_auth.RallyClient')
    def test_validate_rally_connection_success(self, mock_client_class):
        """Test successful Rally connection validation."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client._make_request.return_value = {"Name": "Test Workspace"}
        mock_client.workspace_id = "12345"
        
        # Test
        result = validate_rally_connection()
        
        # Verify
        assert result is True
        mock_client._make_request.assert_called_once()
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('src.services.rally.RallyClient')
    def test_validate_rally_connection_failure(self, mock_client_class):
        """Test failed Rally connection validation."""
        # Setup mock
        mock_client_class.side_effect = Exception("Connection failed")
        
        # Test
        result = validate_rally_connection()
        
        # Verify
        assert result is False
        
    @patch.dict(os.environ, {})
    def test_check_rally_environment_missing_config(self):
        """Test checking Rally environment with missing configuration."""
        result = check_rally_environment()
        
        assert result["configured"] is False
        assert result["connection_valid"] is False
        assert "RALLY_API_KEY environment variable not set" in result["issues"]
        assert "RALLY_WORKSPACE_ID environment variable not set" in result["issues"]
        assert "RALLY_PROJECT_ID environment variable not set" in result["issues"]
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('src.services.rally_auth.validate_rally_connection')
    def test_check_rally_environment_with_config(self, mock_validate):
        """Test checking Rally environment with configuration."""
        mock_validate.return_value = True
        
        result = check_rally_environment()
        
        assert result["configured"] is True
        assert result["connection_valid"] is True
        assert len(result["issues"]) == 0
        
    @patch.dict(os.environ, {})
    def test_setup_rally_environment_instructions(self):
        """Test Rally setup instructions generation."""
        result = setup_rally_environment()
        
        assert "status" in result
        assert "instructions" in result
        assert "RALLY_API_KEY" in result["instructions"]
        assert "RALLY_WORKSPACE_ID" in result["instructions"]
        assert "RALLY_PROJECT_ID" in result["instructions"]


class TestRallyPlannerIntegration:
    """Test Rally planner with feature validation."""
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('src.agents.rally_planner.RallyClient')
    def test_apply_to_rally_with_matching_feature(self, mock_client_class):
        """Test applying plan with matching feature validation."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock feature fetch
        mock_client.get_feature.return_value = {
            "id": "123456",
            "formatted_id": "F12345",
            "name": "Authentication System",
            "description": "OAuth2 authentication"
        }
        
        # Mock validation - high match
        mock_client.validate_feature_context.return_value = {
            "valid": True,
            "confidence": 0.8,
            "reason": "Requirement matches feature 'Authentication System'"
        }
        
        # Mock story creation
        mock_client.create_story.return_value = {
            "id": "999",
            "url": "https://rally.example.com/story/999"
        }
        
        # Create plan
        plan = {
            "plan_id": "test123",
            "requirement": "Add OAuth2 authentication",
            "context_available": True,
            "repo_agnostic": False,
            "feature": None,  # No new feature since we're using existing
            "stories": [{
                "title": "Implement OAuth2",
                "description": "Add OAuth2 support",
                "acceptance_criteria": ["Login works"],
                "estimate": 5,
                "tags": ["auth"],
                "components": [],
                "files": []
            }],
            "tasks": [],
            "assumptions": [],
            "clarifying_questions": [],
            "risks": []
        }
        
        # Test
        result = apply_to_rally(plan, confirm=True, feature_id="F12345")
        
        # Verify
        assert "feature_used" in result
        assert result["feature_used"] == "123456"
        assert len(result["stories"]) == 1
        assert result["stories"][0]["id"] == "999"
        mock_client.get_feature.assert_called_once_with("F12345")
        mock_client.validate_feature_context.assert_called_once()
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('src.agents.rally_planner.RallyClient')
    def test_apply_to_rally_with_mismatched_feature(self, mock_client_class):
        """Test applying plan with mismatched feature validation."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock feature fetch
        mock_client.get_feature.return_value = {
            "id": "123456",
            "formatted_id": "F12345",
            "name": "Payment Gateway",
            "description": "Stripe integration"
        }
        
        # Mock validation - low match
        mock_client.validate_feature_context.return_value = {
            "valid": False,
            "confidence": 0.1,
            "reason": "Feature 'Payment Gateway' appears to be about different functionality"
        }
        
        # Create plan
        plan = {
            "plan_id": "test123",
            "requirement": "Add OAuth2 authentication",
            "context_available": True,
            "repo_agnostic": False,
            "feature": None,
            "stories": [{
                "title": "Implement OAuth2",
                "description": "Add OAuth2 support",
                "acceptance_criteria": ["Login works"],
                "estimate": 5,
                "tags": ["auth"],
                "components": [],
                "files": []
            }],
            "tasks": [],
            "assumptions": [],
            "clarifying_questions": [],
            "risks": []
        }
        
        # Test
        result = apply_to_rally(plan, confirm=True, feature_id="F12345")
        
        # Verify warning returned
        assert "warning" in result
        assert "Feature context mismatch" in result["warning"]
        assert "validation" in result
        assert result["validation"]["valid"] is False
        assert "confirm_anyway" in result
        mock_client.get_feature.assert_called_once_with("F12345")
        mock_client.validate_feature_context.assert_called_once()
        
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "12345",
        "RALLY_PROJECT_ID": "67890"
    })
    @patch('src.services.rally.RallyClient')
    def test_apply_to_rally_preview_mode(self, mock_client_class):
        """Test applying plan in preview mode."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Create plan
        plan = {
            "plan_id": "test123",
            "requirement": "Add feature",
            "context_available": True,
            "repo_agnostic": False,
            "feature": {
                "title": "New Feature",
                "description": "Description",
                "tags": [],
                "components": []
            },
            "stories": [{
                "title": "Story 1",
                "description": "Story desc",
                "acceptance_criteria": ["AC1"],
                "estimate": 3,
                "tags": [],
                "components": ["api"],
                "files": ["api.py"]
            }],
            "tasks": [{
                "title": "Task 1",
                "description": "Task desc",
                "estimate": 2,
                "tags": []
            }],
            "assumptions": [],
            "clarifying_questions": [],
            "risks": []
        }
        
        # Test preview mode (confirm=False)
        result = apply_to_rally(plan, confirm=False)
        
        # Verify
        assert "preview" in result
        assert "requires_confirmation" in result
        assert result["requires_confirmation"] is True
        preview = result["preview"]
        assert preview["plan_id"] == "test123"
        assert "Creating 1 stories and 1 tasks" in preview["summary"]
        assert len(preview["items"]) == 2  # Feature + Story
        
    @patch.dict(os.environ, {})
    def test_apply_to_rally_no_config(self):
        """Test applying plan without Rally configuration."""
        plan = {
            "plan_id": "test123",
            "requirement": "Add feature",
            "feature": None,
            "stories": [],
            "tasks": [],
            "context_available": True,
            "repo_agnostic": False,
            "assumptions": [],
            "clarifying_questions": [],
            "risks": []
        }
        
        # Test
        result = apply_to_rally(plan, confirm=True)
        
        # Verify
        assert "error" in result
        assert "Rally not configured" in result["error"]
        assert "Set RALLY_API_KEY" in result["message"]
        assert "preview" in result


class TestPlanFromRequirement:
    """Test requirement to Rally plan conversion."""
    
    def test_plan_from_requirement_with_repo_context(self):
        """Test creating plan with repository context."""
        requirement = "Add authentication to the API endpoints"
        context = {
            "code_map": {"files": ["api/auth.py", "api/users.py"]},
            "files": ["api/auth.py", "api/users.py", "tests/test_auth.py"],
            "components": ["api", "tests"],
            "frameworks": ["FastAPI", "pytest"],
            "repo_root": "/path/to/myrepo"
        }
        
        plan = plan_from_requirement(requirement, context)
        
        assert plan["requirement"] == requirement
        assert plan["context_available"] is True
        assert plan["repo_agnostic"] is False
        assert len(plan["stories"]) > 0
        assert len(plan["components_touched"]) > 0
        assert "api" in plan["components_touched"]
        
    def test_plan_from_requirement_without_repo_context(self):
        """Test creating plan without repository context."""
        requirement = "Add authentication to the API endpoints"
        context = {}
        
        plan = plan_from_requirement(requirement, context)
        
        assert plan["requirement"] == requirement
        assert plan["context_available"] is False
        assert plan["repo_agnostic"] is True
        assert len(plan["assumptions"]) > 0
        assert len(plan["clarifying_questions"]) > 0
        assert "No repository loaded" in plan["assumptions"][0]
        
    def test_plan_from_requirement_complex_feature(self):
        """Test creating plan for complex requirement."""
        requirement = "Implement a complete authentication system with OAuth2, JWT tokens, role-based access control, and integration with multiple identity providers"
        context = {
            "files": ["auth.py", "models.py", "api.py"],
            "components": ["auth", "models", "api", "middleware", "utils"],
            "repo_root": "/path/to/repo"
        }
        
        plan = plan_from_requirement(requirement, context)
        
        # Should create a feature for complex requirement
        assert plan["feature"] is not None
        assert "Feature:" in plan["feature"]["title"]
        assert len(plan["stories"]) > 2  # Multiple components
        assert len(plan["risks"]) > 0  # Complex = risks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])