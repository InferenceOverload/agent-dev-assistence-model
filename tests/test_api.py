"""Tests for FastAPI server."""

import pytest
from fastapi.testclient import TestClient
import sys
import os
import json
from unittest.mock import patch, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.api import app

client = TestClient(app)


def test_health_endpoint():
    """Test that /health endpoint returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    # API now also returns adk_available status


def test_chat_stream_get_requires_message():
    """Test that GET /chat/stream requires message parameter."""
    response = client.get("/chat/stream")
    assert response.status_code == 422  # Unprocessable Entity (missing required param)


def test_chat_stream_get_with_message():
    """Test that GET /chat/stream accepts message parameter."""
    response = client.get("/chat/stream?message=Hello")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    # Read some of the streamed content
    content = b""
    for chunk in response.iter_bytes(1024):
        content += chunk
        if len(content) > 50:  # Read enough to verify it's streaming
            break
    
    # Should contain SSE formatted data
    assert b"data: " in content


def test_chat_stream_post_backward_compat():
    """Test that POST /chat/stream still works for backward compatibility."""
    response = client.post(
        "/chat/stream",
        json={"message": "Hello"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


def test_chat_stream_with_session_id():
    """Test that /chat/stream accepts session_id."""
    response = client.get("/chat/stream?message=Hello&session_id=test-session")
    assert response.status_code == 200
    
    # Read initial response
    content = b""
    for chunk in response.iter_bytes(512):
        content += chunk
        if len(content) > 50:
            break
    
    # Should be SSE format
    assert b"data: " in content


def test_backend_status_endpoint():
    """Test backend status endpoint."""
    response = client.get("/backend/status")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "environment" in data
    
    # Check environment variables are included
    env = data["environment"]
    assert "VVS_FORCE" in env
    assert "VVS_ENABLED" in env


def test_cors_headers():
    """Test that CORS headers are set correctly for both ports."""
    # Test for Next.js port
    response = client.options(
        "/chat/stream",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    
    # Test for Vite port
    response = client.options(
        "/chat/stream",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


# Removed test_stream_adk_events_shape as stream_adk_events function no longer exists
# The API has been refactored to use different streaming mechanisms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])