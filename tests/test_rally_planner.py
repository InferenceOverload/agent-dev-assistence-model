"""Tests for context-aware Rally planner."""

import os
from unittest.mock import Mock, patch, MagicMock
import pytest

from src.agents.rally_planner import (
    plan_from_requirement, preview_payload, apply_to_rally,
    WorkItem, RallyPlan
)
from src.services.session_context import get_context
from src.core.types import CodeMap, Component


class TestRallyPlanner:
    """Tests for Rally planner functions."""
    
    def test_plan_with_repo_context(self):
        """Test planning with repository context available."""
        # Create mock context with repo data
        context = {
            'repo_root': '/path/to/repo',
            'files': [
                'src/api/routes.py',
                'src/api/handlers.py',
                'src/auth/login.py',
                'src/auth/tokens.py',
                'src/database/models.py',
                'tests/test_api.py'
            ],
            'components': ['api', 'auth', 'database'],
            'frameworks': ['FastAPI', 'SQLAlchemy'],
            'code_map': Mock(files=['src/api/routes.py'], commit='abc123'),
            'commit': 'abc123'
        }
        
        requirement = "Add OAuth authentication to the API endpoints"
        
        # Create plan
        plan = plan_from_requirement(requirement, context)
        
        # Verify plan has context
        assert plan['context_available'] is True
        assert plan['repo_agnostic'] is False
        
        # Should identify relevant components
        assert 'api' in plan['components_touched']
        assert 'auth' in plan['components_touched']
        
        # Should have concrete stories
        assert len(plan['stories']) > 0
        story = plan['stories'][0]
        assert 'api' in story['title'].lower() or 'auth' in story['title'].lower()
        assert len(story['acceptance_criteria']) > 0
        
        # Should have tasks
        assert len(plan['tasks']) > 0
        
        # Should have references
        assert 'frameworks' in plan['references']
        assert 'FastAPI' in plan['references']['frameworks']
    
    def test_plan_without_repo_context(self):
        """Test planning without repository context."""
        context = {}  # Empty context
        
        requirement = "Add OAuth authentication to the API endpoints"
        
        # Create plan
        plan = plan_from_requirement(requirement, context)
        
        # Verify plan is repo-agnostic
        assert plan['context_available'] is False
        assert plan['repo_agnostic'] is True
        
        # Should have assumptions
        assert len(plan['assumptions']) > 0
        assert "No repository loaded" in plan['assumptions'][0]
        
        # Should have clarifying questions
        assert len(plan['clarifying_questions']) > 0
        assert "repository URL" in plan['clarifying_questions'][0]
        
        # Should still create generic stories
        assert len(plan['stories']) > 0
        
        # Should have risks
        assert len(plan['risks']) > 0
        assert "No repository context" in plan['risks'][0]
    
    def test_preview_payload(self):
        """Test preview generation."""
        # Create a plan
        context = {'files': ['test.py'], 'components': ['test']}
        plan = plan_from_requirement("Test requirement", context)
        
        # Generate preview
        preview = preview_payload(plan)
        
        # Verify preview structure
        assert 'plan_id' in preview
        assert 'summary' in preview
        assert 'items' in preview
        assert 'requires_confirmation' in preview
        assert preview['requires_confirmation'] is True
        assert 'confirm_message' in preview
        
        # Verify items in preview
        for item in preview['items']:
            assert 'type' in item
            assert 'title' in item
    
    def test_preview_with_repo_agnostic_plan(self):
        """Test preview for repo-agnostic plan shows context request."""
        context = {}  # No repo context
        plan = plan_from_requirement("Test requirement", context)
        
        preview = preview_payload(plan)
        
        # Should have context request
        assert 'context_request' in preview
        assert "No repository loaded" in preview['context_request']
        assert "load_repo" in preview['context_request']
        
        # Should include assumptions and questions
        assert 'assumptions' in preview
        assert 'clarifying_questions' in preview
    
    @patch('src.agents.rally_planner.RallyClient')
    def test_apply_confirm_false(self, mock_rally_client):
        """Test apply_to_rally with confirm=False returns preview."""
        context = {'files': ['test.py']}
        plan = plan_from_requirement("Test requirement", context)
        
        # Apply without confirmation
        result = apply_to_rally(plan, confirm=False)
        
        # Should return preview
        assert 'preview' in result
        assert 'requires_confirmation' in result
        assert result['requires_confirmation'] is True
        
        # Should NOT call Rally API
        mock_rally_client.assert_not_called()
    
    @patch.dict(os.environ, {
        'RALLY_API_KEY': 'test_key',
        'RALLY_WORKSPACE_ID': 'ws123',
        'RALLY_PROJECT_ID': 'proj456'
    })
    @patch('src.agents.rally_planner.RallyClient')
    def test_apply_confirm_true(self, mock_rally_client):
        """Test apply_to_rally with confirm=True calls Rally API."""
        # Setup mock client
        mock_client = Mock()
        mock_rally_client.return_value = mock_client
        
        # Mock API responses
        mock_client.create_feature.return_value = {"id": "feat123", "url": "http://rally/feat123"}
        mock_client.create_story.return_value = {"id": "story456", "url": "http://rally/story456"}
        mock_client.create_task.return_value = {"id": "task789", "url": "http://rally/task789"}
        
        # Create a complex plan with feature
        context = {'files': ['api.py', 'auth.py', 'db.py'], 'components': ['api', 'auth', 'database']}
        plan = plan_from_requirement("Add complex multi-component system integration", context)
        
        # Apply with confirmation
        result = apply_to_rally(plan, confirm=True)
        
        # Should have created items
        assert 'feature' in result
        assert 'stories' in result
        assert 'tasks' in result
        assert 'audit' in result
        assert 'summary' in result
        
        # Should have called Rally API
        if plan['feature']:
            mock_client.create_feature.assert_called()
        assert mock_client.create_story.call_count >= 1
    
    def test_apply_without_rally_config(self):
        """Test apply_to_rally without Rally configuration."""
        # Clear Rally env vars
        with patch.dict(os.environ, {}, clear=True):
            context = {'files': ['test.py']}
            plan = plan_from_requirement("Test requirement", context)
            
            # Apply with confirmation
            result = apply_to_rally(plan, confirm=True)
            
            # Should return error
            assert 'error' in result
            assert "RALLY_API_KEY" in result['message']
            assert 'preview' in result  # Should still include preview
    
    def test_plan_idempotency(self):
        """Test that running preview twice doesn't change the plan."""
        context = {'files': ['test.py'], 'components': ['test']}
        requirement = "Test requirement"
        
        # Create plan twice
        plan1 = plan_from_requirement(requirement, context)
        plan2 = plan_from_requirement(requirement, context)
        
        # Plans should be identical except for plan_id and created_at
        assert plan1['requirement'] == plan2['requirement']
        assert plan1['stories'][0]['title'] == plan2['stories'][0]['title']
        assert plan1['context_available'] == plan2['context_available']
    
    def test_complex_requirement_creates_feature(self):
        """Test that complex requirements create a feature."""
        context = {
            'files': ['a.py', 'b.py', 'c.py'],
            'components': ['comp1', 'comp2', 'comp3', 'comp4']
        }
        
        # Long, complex requirement
        requirement = (
            "Implement a comprehensive authentication and authorization system "
            "with multiple OAuth providers, role-based access control, "
            "session management, audit logging, and integration with external "
            "identity providers across all system components"
        )
        
        plan = plan_from_requirement(requirement, context)
        
        # Should create a feature for complexity
        assert plan['feature'] is not None
        assert "Feature:" in plan['feature']['title']
        # Components are in components_touched at plan level
        assert len(plan['components_touched']) > 0
    
    def test_simple_requirement_no_feature(self):
        """Test that simple requirements don't create a feature."""
        context = {'files': ['test.py'], 'components': ['test']}
        requirement = "Fix login bug"
        
        plan = plan_from_requirement(requirement, context)
        
        # Should not create feature for simple requirement
        assert plan['feature'] is None
        # But should have stories
        assert len(plan['stories']) > 0


class TestSessionContext:
    """Tests for session context helper."""
    
    def test_get_context_with_full_session(self):
        """Test getting context from a full orchestrator session."""
        # Create mock orchestrator
        orch = Mock()
        orch.root = '/path/to/repo'
        orch.code_map = Mock(
            files=['src/app.py', 'tests/test_app.py'],
            commit='abc123'
        )
        orch.sizer = Mock(
            total_files=10,
            total_lines=1000,
            size_bytes=100000
        )
        
        # Get context
        ctx = get_context(orch)
        
        # Verify context
        assert ctx['repo_root'] == '/path/to/repo'
        assert len(ctx['files']) == 2
        assert ctx['commit'] == 'abc123'
        assert 'code_map_summary' in ctx
        assert ctx['repo_size']['total_files'] == 10
    
    def test_get_context_empty_orchestrator(self):
        """Test getting context from empty orchestrator."""
        orch = Mock()
        # Remove all attributes
        del orch.root
        del orch.code_map
        
        # Get context - should not crash
        ctx = get_context(orch)
        
        # Should return empty context
        assert 'repo_root' not in ctx
        assert 'files' not in ctx
        assert 'code_map' not in ctx
    
    @patch('adam_agent._cached_facts')
    def test_get_context_with_cached_facts(self, mock_facts):
        """Test getting context includes cached repo facts."""
        # Setup mock facts
        mock_facts.components = {'api': Mock(), 'auth': Mock()}
        mock_facts.frameworks = ['FastAPI', 'SQLAlchemy']
        
        orch = Mock()
        orch.root = '/repo'
        
        with patch('src.services.session_context.adam_agent', create=True) as mock_adam:
            mock_adam._cached_facts = mock_facts
            
            ctx = get_context(orch)
            
            # Should include repo facts
            assert 'components' in ctx
            assert 'api' in ctx['components']
            assert 'frameworks' in ctx
            assert 'FastAPI' in ctx['frameworks']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])