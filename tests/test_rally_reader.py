"""Tests for Rally reader service."""

import os
from unittest.mock import Mock, patch
import pytest

from src.services.rally_reader import get_story, get_feature, get_story_context


class TestRallyReader:
    """Tests for Rally reader functions."""
    
    @patch.dict(os.environ, {
        'RALLY_API_KEY': 'test_key',
        'RALLY_WORKSPACE_ID': 'ws123',
        'RALLY_PROJECT_ID': 'proj456'
    })
    @patch('src.services.rally_reader.RallyClient')
    def test_get_story_success(self, mock_rally_client):
        """Test successfully fetching a Rally story."""
        # Setup mock client
        mock_client = Mock()
        mock_rally_client.return_value = mock_client
        
        # Mock API response
        mock_response = {
            "Name": "Implement OAuth authentication",
            "Description": "Add OAuth 2.0 support to the API",
            "AcceptanceCriteria": "<ul><li>OAuth flow works</li><li>Tokens are validated</li></ul>",
            "ScheduleState": "In-Progress",
            "PlanEstimate": 5.0,
            "PortfolioItem": {"_ref": "/portfolioitem/feature/789"}
        }
        mock_client._make_request.return_value = mock_response
        mock_client.base_url = "https://rally.example.com"
        
        # Call function
        result = get_story("123456")
        
        # Verify
        assert result["id"] == "123456"
        assert result["title"] == "Implement OAuth authentication"
        assert result["description"] == "Add OAuth 2.0 support to the API"
        assert result["acceptance_criteria"] == "<ul><li>OAuth flow works</li><li>Tokens are validated</li></ul>"
        assert result["state"] == "In-Progress"
        assert result["estimate"] == 5.0
        assert result["feature"] == "789"
        assert "rally.example.com" in result["url"]
        
        # Verify API call
        mock_client._make_request.assert_called_once_with(
            "GET", "hierarchicalrequirement/123456"
        )
    
    @patch.dict(os.environ, {
        'RALLY_API_KEY': 'test_key',
        'RALLY_WORKSPACE_ID': 'ws123',
        'RALLY_PROJECT_ID': 'proj456'
    })
    @patch('src.services.rally_reader.RallyClient')
    def test_get_story_error(self, mock_rally_client):
        """Test error handling when fetching a story."""
        # Setup mock client to raise error
        mock_client = Mock()
        mock_rally_client.return_value = mock_client
        mock_client._make_request.side_effect = Exception("API Error")
        
        # Call function
        result = get_story("invalid")
        
        # Verify error response
        assert "error" in result
        assert "API Error" in result["error"]
    
    @patch.dict(os.environ, {
        'RALLY_API_KEY': 'test_key',
        'RALLY_WORKSPACE_ID': 'ws123',
        'RALLY_PROJECT_ID': 'proj456'
    })
    @patch('src.services.rally_reader.RallyClient')
    def test_get_feature_success(self, mock_rally_client):
        """Test successfully fetching a Rally feature."""
        # Setup mock client
        mock_client = Mock()
        mock_rally_client.return_value = mock_client
        
        # Mock API response
        mock_response = {
            "Name": "Authentication System",
            "Description": "Complete authentication and authorization system",
            "State": {"Name": "Developing"}
        }
        mock_client._make_request.return_value = mock_response
        mock_client.base_url = "https://rally.example.com"
        
        # Call function
        result = get_feature("789")
        
        # Verify
        assert result["id"] == "789"
        assert result["title"] == "Authentication System"
        assert result["description"] == "Complete authentication and authorization system"
        assert result["state"] == "Developing"
        assert "rally.example.com" in result["url"]
        
        # Verify API call
        mock_client._make_request.assert_called_once_with(
            "GET", "portfolioitem/feature/789"
        )
    
    @patch.dict(os.environ, {
        'RALLY_API_KEY': 'test_key',
        'RALLY_WORKSPACE_ID': 'ws123',
        'RALLY_PROJECT_ID': 'proj456'
    })
    @patch('src.services.rally_reader.get_story')
    @patch('src.services.rally_reader.get_feature')
    def test_get_story_context_with_feature(self, mock_get_feature, mock_get_story):
        """Test getting full story context including parent feature."""
        # Mock story response with feature
        mock_get_story.return_value = {
            "id": "123",
            "title": "OAuth implementation",
            "feature": "789",
            "description": "Add OAuth support"
        }
        
        # Mock feature response
        mock_get_feature.return_value = {
            "id": "789",
            "title": "Auth System",
            "description": "Full auth system"
        }
        
        # Call function
        result = get_story_context("123")
        
        # Verify
        assert result["story"]["id"] == "123"
        assert result["story"]["title"] == "OAuth implementation"
        assert result["feature"]["id"] == "789"
        assert result["feature"]["title"] == "Auth System"
        
        # Verify calls
        mock_get_story.assert_called_once_with("123")
        mock_get_feature.assert_called_once_with("789")
    
    @patch.dict(os.environ, {
        'RALLY_API_KEY': 'test_key',
        'RALLY_WORKSPACE_ID': 'ws123',
        'RALLY_PROJECT_ID': 'proj456'
    })
    @patch('src.services.rally_reader.get_story')
    @patch('src.services.rally_reader.get_feature')
    def test_get_story_context_no_feature(self, mock_get_feature, mock_get_story):
        """Test getting story context when story has no parent feature."""
        # Mock story response without feature
        mock_get_story.return_value = {
            "id": "123",
            "title": "Standalone bug fix",
            "feature": None,
            "description": "Fix login bug"
        }
        
        # Call function
        result = get_story_context("123")
        
        # Verify
        assert result["story"]["id"] == "123"
        assert result["story"]["title"] == "Standalone bug fix"
        assert result["feature"] == {}
        
        # Verify feature was not fetched
        mock_get_story.assert_called_once_with("123")
        mock_get_feature.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])