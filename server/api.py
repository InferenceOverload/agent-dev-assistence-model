"""FastAPI server that bridges to ADK agent with real SSE streaming."""

import os
import json
import asyncio
import logging
from typing import Optional, AsyncIterator
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our ADK agent and runners
try:
    from google.adk import runners
    from adam_agent import root_agent
    ADK_AVAILABLE = True
    logger.info("ADK runners imported successfully")
except ImportError as e:
    logger.warning(f"ADK import failed: {e}, using fallback mode")
    ADK_AVAILABLE = False
    root_agent = None

app = FastAPI(title="ADAM Agent API")

# Configure CORS for local development (both Next.js and Vite ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"ok": True}


async def stream_adk_events(message: str, session_id: str) -> AsyncIterator[str]:
    """Stream real ADK agent events as Server-Sent Events."""
    logger.info(f"Starting SSE stream - message: {message[:50]}..., session: {session_id}")
    
    if not ADK_AVAILABLE or not root_agent:
        # Fallback for when ADK is not available
        logger.warning("ADK not available, using fallback response")
        yield f"data: {json.dumps({'type': 'error', 'message': 'ADK agent not available'})}\n\n"
        return
    
    try:
        # Create the ADK runner request
        agent_name = getattr(root_agent, "name", "adam_agent")
        runner_request = {
            "agent_name": agent_name,
            "input": message,
            "session_id": session_id or "",
            "state": {}
        }
        
        logger.info(f"Calling ADK runner with agent: {agent_name}")
        
        # Stream events from ADK runner
        event_count = 0
        async for event in runners.run_sse(root_agent, runner_request):
            event_count += 1
            logger.info(f"Event {event_count}: {event.get('type', 'unknown')}")
            
            # Forward the event verbatim
            yield f"data: {json.dumps(event)}\n\n"
            
            # Log specific event types for debugging
            if event.get("type") == "tool_start":
                logger.info(f"Tool started: {event.get('name')} with args: {event.get('args')}")
            elif event.get("type") == "tool_end":
                logger.info(f"Tool ended: {event.get('name')}")
            elif event.get("type") == "llm_output":
                text = event.get("text", "")
                logger.debug(f"LLM output: {text[:100]}...")
        
        logger.info(f"Stream completed with {event_count} events")
        
    except Exception as e:
        logger.error(f"Error in ADK stream: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.get("/chat/stream")
async def chat_stream_get(
    message: str = Query(..., description="The message to send to the agent"),
    session_id: Optional[str] = Query(None, description="Optional session ID")
):
    """Stream chat responses using Server-Sent Events via GET."""
    session_id = session_id or "default"
    
    return StreamingResponse(
        stream_adk_events(message, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.post("/chat/stream")
async def chat_stream_post(request: ChatRequest):
    """Stream chat responses using Server-Sent Events via POST (backward compatibility)."""
    session_id = request.session_id or "default"
    
    return StreamingResponse(
        stream_adk_events(request.message, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/backend/status")
async def backend_status():
    """Get backend status including VVS configuration."""
    try:
        # Import orchestrator to get backend info
        from src.agents.orchestrator import OrchestratorAgent
        from src.core.storage import StorageFactory
        
        # Create a temporary orchestrator to check status
        orch = OrchestratorAgent(
            root=".",
            session_id="status-check",
            storage_factory=StorageFactory(use_vertex=False)
        )
        
        # Get decision info if available
        decision_info = {}
        if hasattr(orch, 'decision') and orch.decision:
            decision_info = {
                "decision_backend": orch.decision.get("backend", "unknown"),
                "using_vvs": orch.decision.get("backend") == "vertex-vector-search",
                "policy_reasons": orch.decision.get("reasons", []),
            }
        
        # Get index info if available
        index_info = {}
        if hasattr(orch, 'retriever') and orch.retriever:
            index_info = {
                "chunk_count": getattr(orch.retriever, 'chunk_count', 0),
                "backend_type": getattr(orch.retriever, 'backend', 'unknown')
            }
        
        # Get file count from code map
        file_count = 0
        if hasattr(orch, 'code_map') and orch.code_map:
            file_count = len(orch.code_map.files) if hasattr(orch.code_map, 'files') else 0
        
        # Check environment variables
        env_info = {
            "VVS_FORCE": os.getenv("VVS_FORCE", "0"),
            "VVS_ENABLED": os.getenv("VVS_ENABLED", "false"),
            "GCP_PROJECT_ID": bool(os.getenv("GCP_PROJECT_ID"))
        }
        
        return {
            "status": "ok",
            "file_count": file_count,
            **decision_info,
            **index_info,
            "environment": env_info
        }
        
    except Exception as e:
        logger.error(f"Error getting backend status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "environment": {
                "VVS_FORCE": os.getenv("VVS_FORCE", "0"),
                "VVS_ENABLED": os.getenv("VVS_ENABLED", "false")
            }
        }


# For serving static files in production
if os.path.exists("static"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="static", html=True), name="static")