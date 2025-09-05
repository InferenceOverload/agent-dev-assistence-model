"""FastAPI server that bridges to ADK agent with proper integration."""

import os
import json
import asyncio
import logging
from typing import Optional, AsyncIterator, Any, Dict
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys
import traceback

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our ADK agent
try:
    from adam_agent import root_agent
    ADK_AVAILABLE = True
    logger.info(f"ADK agent loaded: {type(root_agent)}")
except ImportError as e:
    logger.warning(f"ADK agent import failed: {e}")
    ADK_AVAILABLE = False
    root_agent = None

app = FastAPI(title="ADAM Agent API")

# Configure CORS for local development (both Next.js and Vite ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"],
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
    return {"ok": True, "adk_available": ADK_AVAILABLE}


async def stream_agent_response(message: str, session_id: str) -> AsyncIterator[str]:
    """Stream agent responses as Server-Sent Events using proper ADK methods."""
    logger.info(f"Starting agent stream - message: {message[:50]}..., session: {session_id}")
    
    if not ADK_AVAILABLE or not root_agent:
        logger.warning("ADK agent not available")
        yield f"data: {json.dumps({'type': 'error', 'message': 'ADK agent not available'})}\n\n"
        return
    
    try:
        # Check if we should use run_async or run_live
        if hasattr(root_agent, 'run_async'):
            logger.info("Using run_async method")
            
            # Create a state dict for the session
            state = {"session_id": session_id}
            
            # Run the agent asynchronously
            try:
                # First, let's try to run it and get the result
                result = await root_agent.run_async(
                    input_text=message,
                    state=state
                )
                
                # Process the result
                if isinstance(result, dict):
                    # If result has text content
                    if 'text' in result:
                        yield f"data: {json.dumps({'type': 'llm_output', 'text': result['text']})}\n\n"
                    
                    # If result has tool calls
                    if 'tool_calls' in result:
                        for tool_call in result.get('tool_calls', []):
                            yield f"data: {json.dumps({'type': 'tool_start', 'name': tool_call.get('name', 'unknown'), 'args': tool_call.get('args', {})})}\n\n"
                            yield f"data: {json.dumps({'type': 'tool_end', 'name': tool_call.get('name', 'unknown'), 'output': tool_call.get('output', '')})}\n\n"
                    
                    # If result has output directly
                    if 'output' in result:
                        output = result['output']
                        if isinstance(output, str):
                            yield f"data: {json.dumps({'type': 'llm_output', 'text': output})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'llm_output', 'text': json.dumps(output)})}\n\n"
                    
                    # Log the full result for debugging
                    logger.info(f"Agent result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
                    
                elif isinstance(result, str):
                    # Simple text response
                    yield f"data: {json.dumps({'type': 'llm_output', 'text': result})}\n\n"
                else:
                    # Unknown result type
                    logger.warning(f"Unknown result type: {type(result)}")
                    yield f"data: {json.dumps({'type': 'llm_output', 'text': str(result)})}\n\n"
                
            except Exception as e:
                logger.error(f"Error running agent: {e}", exc_info=True)
                # Fallback: call the agent tools directly for demonstration
                logger.info("Falling back to direct tool invocation")
                
                # Import the tools to call them directly
                from adam_agent import load_repo, ask, index, ingest, decide
                
                # Simple pattern matching for commands
                if "load" in message.lower() and ("repo" in message.lower() or "github" in message.lower()):
                    # Extract URL from message
                    words = message.split()
                    url = None
                    for word in words:
                        if "github.com" in word or "http" in word:
                            url = word.strip()
                            break
                    
                    if url:
                        yield f"data: {json.dumps({'type': 'tool_start', 'name': 'load_repo', 'args': {'url': url}})}\n\n"
                        try:
                            result = load_repo(url)
                            yield f"data: {json.dumps({'type': 'tool_end', 'name': 'load_repo', 'output': result})}\n\n"
                            files_count = result.get('files', 0)
                            commit_hash = result.get('commit', 'unknown')
                            yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Repository loaded successfully. Files: {files_count}, Commit: {commit_hash}'})}\n\n"
                        except Exception as tool_error:
                            yield f"data: {json.dumps({'type': 'tool_end', 'name': 'load_repo', 'output': str(tool_error)})}\n\n"
                            yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Error loading repository: {tool_error}'})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'llm_output', 'text': 'Please provide a repository URL to load.'})}\n\n"
                
                elif "ask" in message.lower() or "what" in message.lower() or "explain" in message.lower():
                    # Use the ask tool
                    query = message
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': 'ask', 'args': {'query': query}})}\n\n"
                    try:
                        result = ask(query)
                        yield f"data: {json.dumps({'type': 'tool_end', 'name': 'ask', 'output': 'Answer generated'})}\n\n"
                        answer = result.get('answer', 'No answer available')
                        yield f"data: {json.dumps({'type': 'llm_output', 'text': answer})}\n\n"
                    except Exception as tool_error:
                        yield f"data: {json.dumps({'type': 'tool_end', 'name': 'ask', 'output': str(tool_error)})}\n\n"
                        yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Error: {tool_error}'})}\n\n"
                
                else:
                    # Default response
                    yield f"data: {json.dumps({'type': 'llm_output', 'text': f'I can help you analyze repositories. Try: \"Load repository [URL]\" or \"What does this code do?\"'})}\n\n"
        
        else:
            logger.warning("Agent doesn't have run_async method")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Agent configuration error'})}\n\n"
        
        # Send completion event
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
        
    except Exception as e:
        logger.error(f"Error in stream: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.get("/chat/stream")
async def chat_stream_get(
    message: str = Query(..., description="The message to send to the agent"),
    session_id: Optional[str] = Query(None, description="Optional session ID")
):
    """Stream chat responses using Server-Sent Events via GET."""
    session_id = session_id or "default"
    
    return StreamingResponse(
        stream_agent_response(message, session_id),
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
        stream_agent_response(request.message, session_id),
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
            "adk_available": ADK_AVAILABLE,
            **decision_info,
            **index_info,
            "environment": env_info
        }
        
    except Exception as e:
        logger.error(f"Error getting backend status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "adk_available": ADK_AVAILABLE,
            "environment": {
                "VVS_FORCE": os.getenv("VVS_FORCE", "0"),
                "VVS_ENABLED": os.getenv("VVS_ENABLED", "false")
            }
        }


# Alternative: Proxy to ADK API server if it's running
@app.post("/agent/run")
async def proxy_to_adk_api(request: ChatRequest):
    """
    Proxy requests to ADK API server if you're running it with 'adk api_server'.
    This endpoint mimics what ADK's API server would provide.
    """
    if not ADK_AVAILABLE:
        raise HTTPException(status_code=503, detail="ADK agent not available")
    
    try:
        import httpx
        
        # Try to proxy to ADK API server (if running on default port 8080)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8080/agent/run",
                json={"input": request.message, "session_id": request.session_id}
            )
            return response.json()
    except Exception as e:
        # Fallback to direct agent call
        logger.info(f"ADK API server not available, using direct call: {e}")
        
        if hasattr(root_agent, 'run_async'):
            result = await root_agent.run_async(
                input_text=request.message,
                state={"session_id": request.session_id}
            )
            return {"result": result}
        else:
            raise HTTPException(status_code=500, detail="Agent doesn't support async execution")


# For serving static files in production
if os.path.exists("static"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="static", html=True), name="static")