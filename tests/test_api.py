"""Tests for FastAPI server."""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.api import app

client = TestClient(app)


def test_health_endpoint():
    """Test that /health endpoint returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_chat_stream_requires_post():
    """Test that /chat/stream requires POST method."""
    response = client.get("/chat/stream")
    assert response.status_code == 405


def test_chat_stream_with_message():
    """Test that /chat/stream accepts a message and returns SSE."""
    response = client.post(
        "/chat/stream",
        json={"message": "Hello"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    # Read some of the streamed content
    content = b""
    for chunk in response.iter_bytes(1024):
        content += chunk
        if len(content) > 100:  # Read enough to verify it's streaming
            break
    
    # Should contain SSE formatted data
    assert b"data: " in content
    assert b"type" in content


def test_chat_stream_with_session_id():
    """Test that /chat/stream accepts session_id."""
    response = client.post(
        "/chat/stream",
        json={"message": "Hello", "session_id": "test-session"}
    )
    assert response.status_code == 200
    
    # Read initial response
    content = b""
    for chunk in response.iter_bytes(512):
        content += chunk
        break
    
    # Should contain session_id in response
    decoded = content.decode('utf-8')
    assert "test-session" in decoded or "session_id" in decoded.lower()


def test_cors_headers():
    """Test that CORS headers are set correctly."""
    response = client.options(
        "/chat/stream",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST"
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])