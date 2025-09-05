"""Tests for Rally service and planner."""

import os
import json
from unittest.mock import Mock, patch, MagicMock
import pytest
import httpx

from src.services.rally import RallyClient
from src.agents.rally_planner import plan_from_requirement, preview_payload, apply_to_rally
from src.core.types import KnowledgeGraph, Component


class TestRallyClient:
    """Tests for Rally API client."""
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    def test_init_with_env_vars(self):
        """Test client initialization with environment variables."""
        client = RallyClient()
        assert client.api_key == "test_key"
        assert client.workspace_id == "workspace123"
        assert client.project_id == "project456"
    
    def test_init_without_api_key(self):
        """Test client initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="RALLY_API_KEY"):
                RallyClient()
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    @patch('httpx.Client')
    def test_create_feature(self, mock_client_class):
        """Test creating a Rally feature."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Mock GET for tag query
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            "QueryResult": {
                "TotalResultCount": 0,
                "Results": []
            }
        }
        mock_get_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_get_response
        
        # Mock POST for feature and tag creation
        def post_side_effect(url, **kwargs):
            mock_response = Mock()
            if "tag/create" in url:
                mock_response.json.return_value = {
                    "CreateResult": {
                        "Object": {"ObjectID": "tag123", "_ref": "/tag/tag123"}
                    }
                }
            else:
                mock_response.json.return_value = {
                    "CreateResult": {
                        "Object": {"ObjectID": "12345"}
                    }
                }
            mock_response.raise_for_status = Mock()
            return mock_response
        
        mock_client.post.side_effect = post_side_effect
        
        # Test
        client = RallyClient()
        result = client.create_feature("Test Feature", "Feature description", ["tag1", "tag2"])
        
        # Verify
        assert result["id"] == "12345"
        assert "rally" in result["url"].lower()
        # Post called 3 times: 2 for tags, 1 for feature
        assert mock_client.post.call_count == 3
        
        # Check the feature creation call (last one)
        feature_call = mock_client.post.call_args_list[-1]
        assert "/portfolioitem/feature/create" in feature_call[0][0]
        
        # Check payload
        payload = feature_call.kwargs['json']
        assert payload["PortfolioItem/Feature"]["Name"] == "Test Feature"
        assert payload["PortfolioItem/Feature"]["Description"] == "Feature description"
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    @patch('httpx.Client')
    def test_create_story(self, mock_client_class):
        """Test creating a Rally story."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "CreateResult": {
                "Object": {"ObjectID": "67890"}
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.post.return_value = mock_response
        
        # Test
        client = RallyClient()
        result = client.create_story(
            "12345",
            "Test Story",
            "Story description",
            ["AC1", "AC2"],
            5
        )
        
        # Verify
        assert result["id"] == "67890"
        assert "rally" in result["url"].lower()
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/hierarchicalrequirement/create" in call_args[0][0]
        
        # Check payload
        payload = call_args.kwargs['json']
        assert payload["HierarchicalRequirement"]["Name"] == "Test Story"
        assert payload["HierarchicalRequirement"]["PlanEstimate"] == 5
        assert "<li>AC1</li>" in payload["HierarchicalRequirement"]["AcceptanceCriteria"]
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    @patch('httpx.Client')
    def test_create_task(self, mock_client_class):
        """Test creating a Rally task."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "CreateResult": {
                "Object": {"ObjectID": "11111"}
            }
        }
        mock_response.raise_for_status = Mock()
        mock_client.post.return_value = mock_response
        
        # Test
        client = RallyClient()
        result = client.create_task("67890", "Test Task", "Task description", 3.5)
        
        # Verify
        assert result["id"] == "11111"
        assert "rally" in result["url"].lower()
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/task/create" in call_args[0][0]
        
        # Check payload
        payload = call_args.kwargs['json']
        assert payload["Task"]["Name"] == "Test Task"
        assert payload["Task"]["Estimate"] == 3.5
        assert payload["Task"]["WorkProduct"]["_ref"] == "/hierarchicalrequirement/67890"
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    @patch('httpx.Client')
    def test_retry_on_rate_limit(self, mock_client_class):
        """Test retry logic on 429 rate limit."""
        # Setup mock
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # First call: 429 error
        mock_error_response = Mock()
        mock_error_response.status_code = 429
        error = httpx.HTTPStatusError("Rate limited", request=Mock(), response=mock_error_response)
        
        # Second call: success
        mock_success_response = Mock()
        mock_success_response.json.return_value = {
            "CreateResult": {
                "Object": {"ObjectID": "99999"}
            }
        }
        mock_success_response.raise_for_status = Mock()
        
        mock_client.post.side_effect = [error, mock_success_response]
        
        # Test with mocked sleep
        with patch('time.sleep'):
            client = RallyClient()
            result = client.create_feature("Test", "Desc")
        
        # Verify retry occurred
        assert result["id"] == "99999"
        assert "rally" in result["url"].lower()
        assert mock_client.post.call_count == 2


@pytest.mark.skip(reason="RallyPlanner class replaced with context-aware functions")
class TestRallyPlanner:
    """Tests for Rally planner agent."""
    
    def test_work_item_creation(self):
        """Test WorkItem dataclass."""
        item = WorkItem(
            type=WorkItemType.STORY,
            title="Test Story",
            description="Story description",
            acceptance_criteria=["AC1", "AC2"],
            estimate=5
        )
        
        assert item.type == WorkItemType.STORY
        assert item.title == "Test Story"
        assert len(item.acceptance_criteria) == 2
        
        # Test dict conversion
        item_dict = item.to_dict()
        assert item_dict["type"] == "story"
        assert item_dict["estimate"] == 5
    
    def test_rally_plan_creation(self):
        """Test RallyPlan dataclass."""
        feature = WorkItem(WorkItemType.FEATURE, "Feature", "Desc")
        story = WorkItem(WorkItemType.STORY, "Story", "Desc", estimate=5)
        task = WorkItem(WorkItemType.TASK, "Task", "Desc", estimate=2)
        
        plan = RallyPlan(
            plan_id="test123",
            feature=feature,
            stories=[story],
            tasks=[task],
            total_estimate=5,
            impacted_components=["comp1", "comp2"]
        )
        
        # Test preview
        preview = plan.preview()
        assert "Feature: Feature" in preview
        assert "Stories (1):" in preview
        assert "Tasks (1):" in preview
        assert "Total Estimate: 5" in preview
        
        # Test dict conversion
        plan_dict = plan.to_dict()
        assert plan_dict["plan_id"] == "test123"
        assert plan_dict["total_estimate"] == 5
        assert len(plan_dict["stories"]) == 1
    
    def test_analyze_requirement_with_kg(self):
        """Test requirement analysis with knowledge graph."""
        # Create mock KG
        kg = KnowledgeGraph(
            nodes={},
            components={
                "auth": Component(
                    name="auth",
                    files=["src/auth/login.py", "src/auth/token.py"],
                    imports=[],
                    exports=[],
                    dependencies=[]
                ),
                "api": Component(
                    name="api",
                    files=["src/api/routes.py", "src/api/handlers.py"],
                    imports=[],
                    exports=[],
                    dependencies=[]
                )
            },
            relations=[]
        )
        
        planner = RallyPlanner(rally_client=Mock())
        
        # Test with component name in requirement
        components, paths = planner._analyze_requirement(
            "Update the auth component to support OAuth",
            kg
        )
        
        assert "auth" in components
        assert "src/auth/login.py" in paths["auth"]
        assert "src/auth/token.py" in paths["auth"]
    
    def test_decompose_simple_requirement(self):
        """Test decomposing a simple requirement."""
        planner = RallyPlanner(rally_client=Mock())
        
        feature, stories, tasks = planner._decompose_requirement(
            "Fix login bug",
            [],
            {}
        )
        
        # Simple requirement should not create a feature
        assert feature is None
        assert len(stories) == 1
        assert stories[0].title == "Fix login bug"
        assert len(tasks) == 2  # Implementation + tests
    
    def test_decompose_complex_requirement(self):
        """Test decomposing a complex requirement."""
        planner = RallyPlanner(rally_client=Mock())
        
        feature, stories, tasks = planner._decompose_requirement(
            "Implement complete authentication system with OAuth, JWT tokens, "
            "role-based access control, and audit logging across multiple services",
            ["auth", "api", "logging"],
            {
                "auth": ["src/auth/login.py"],
                "api": ["src/api/routes.py"],
                "logging": ["src/logging/audit.py"]
            }
        )
        
        # Complex requirement should create a feature
        assert feature is not None
        assert feature.type == WorkItemType.FEATURE
        assert "authentication system" in feature.title.lower()
        
        # Should create stories per component
        assert len(stories) == 3
        story_titles = [s.title for s in stories]
        assert any("auth" in t for t in story_titles)
        assert any("api" in t for t in story_titles)
        
        # Should create tasks
        assert len(tasks) >= 3
    
    @patch('uuid.uuid4')
    def test_plan_to_rally(self, mock_uuid):
        """Test creating a Rally plan from requirement."""
        # Create a mock UUID that returns the expected value when sliced
        mock_uuid_obj = Mock()
        mock_uuid_obj.__str__ = Mock(return_value="abcd1234-1234-1234-1234-123456789abc")
        mock_uuid.return_value = mock_uuid_obj
        
        kg = KnowledgeGraph(
            nodes={},
            components={
                "frontend": Component(
                    name="frontend",
                    files=["src/ui/app.js"],
                    imports=[],
                    exports=[],
                    dependencies=[]
                )
            },
            relations=[]
        )
        
        planner = RallyPlanner(rally_client=Mock())
        plan = planner.plan_to_rally(
            "Add dark mode to frontend",
            kg
        )
        
        assert plan.plan_id == "abcd1234"
        assert "frontend" in plan.impacted_components
        assert len(plan.stories) >= 1
        assert plan.total_estimate > 0
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    def test_apply_plan_dry_run(self):
        """Test applying a plan in dry run mode."""
        planner = RallyPlanner(rally_client=Mock())
        
        # Create and store a plan
        plan = RallyPlan(
            plan_id="test123",
            feature=WorkItem(WorkItemType.FEATURE, "Feature", "Desc"),
            stories=[WorkItem(WorkItemType.STORY, "Story", "Desc")],
            tasks=[WorkItem(WorkItemType.TASK, "Task", "Desc")],
            total_estimate=5,
            impacted_components=["comp1"]
        )
        planner._plans["test123"] = plan
        
        # Apply in dry run
        result = planner.apply_plan("test123", dry_run=True)
        
        assert result["dry_run"] is True
        assert "plan_preview" in result
        assert "Feature" in result["plan_preview"]
    
    @patch.dict(os.environ, {
        "RALLY_API_KEY": "test_key",
        "RALLY_WORKSPACE_ID": "workspace123",
        "RALLY_PROJECT_ID": "project456"
    })
    def test_apply_plan_real(self):
        """Test applying a plan to create real items."""
        mock_client = Mock()
        mock_client.create_feature.return_value = "feat123"
        mock_client.create_story.return_value = "story456"
        mock_client.create_task.return_value = "task789"
        
        planner = RallyPlanner(rally_client=mock_client)
        
        # Create and store a plan
        plan = RallyPlan(
            plan_id="test123",
            feature=WorkItem(WorkItemType.FEATURE, "Feature", "Desc", tags=["tag1"]),
            stories=[WorkItem(WorkItemType.STORY, "Story", "Desc", acceptance_criteria=["AC1"])],
            tasks=[WorkItem(WorkItemType.TASK, "Task", "Desc")],
            total_estimate=5,
            impacted_components=["comp1"]
        )
        planner._plans["test123"] = plan
        
        # Apply for real
        result = planner.apply_plan("test123", dry_run=False)
        
        assert result["feature_id"] == "feat123"
        assert result["story_ids"] == ["story456"]
        assert result["task_ids"] == ["task789"]
        
        # Verify client calls
        mock_client.create_feature.assert_called_once_with("Feature", "Desc", ["tag1"])
        mock_client.create_story.assert_called_once()
        mock_client.create_task.assert_called_once()
        
        # Plan should be removed after successful application
        assert "test123" not in planner._plans
    
    def test_get_and_list_plans(self):
        """Test getting and listing stored plans."""
        planner = RallyPlanner(rally_client=Mock())
        
        # Initially empty
        assert planner.list_plans() == []
        assert planner.get_plan("nonexistent") is None
        
        # Create plans
        plan1 = RallyPlan("plan1", None, [], [], 0, [])
        plan2 = RallyPlan("plan2", None, [], [], 0, [])
        
        planner._plans["plan1"] = plan1
        planner._plans["plan2"] = plan2
        
        # Test listing
        plans = planner.list_plans()
        assert len(plans) == 2
        assert "plan1" in plans
        assert "plan2" in plans
        
        # Test getting
        retrieved = planner.get_plan("plan1")
        assert retrieved == plan1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])