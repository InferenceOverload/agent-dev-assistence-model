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
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env files
try:
    from dotenv import load_dotenv
    # Try loading from adam_agent/.env first (has actual keys)
    adam_env = Path(__file__).parent.parent / "adam_agent" / ".env"
    if adam_env.exists():
        load_dotenv(adam_env, override=True)
        print(f"Loaded environment from {adam_env}")
    # Also load root .env if it exists
    root_env = Path(__file__).parent.parent / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)  # Don't override adam_agent settings
except ImportError:
    pass  # dotenv not installed

# Configure logging
logging.basicConfig(level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
logger = logging.getLogger(__name__)

# Import our ADK agent and Runner
try:
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService, VertexAiSessionService
    from google.genai.types import Content
    from adam_agent import root_agent
    ADK_AVAILABLE = True
    logger.info(f"ADK agent loaded: {type(root_agent)}")
except ImportError as e:
    logger.warning(f"ADK agent import failed: {e}")
    ADK_AVAILABLE = False
    root_agent = None
    Runner = None
    InMemorySessionService = None
    VertexAiSessionService = None
    Content = None

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


def _make_session_service():
    """Create appropriate session service based on environment."""
    if not ADK_AVAILABLE or not InMemorySessionService:
        return None
    
    # Toggle persistent sessions if desired
    if os.getenv("USE_VERTEX_SESSIONS") in ("1", "true", "TRUE", "yes", "YES"):
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if VertexAiSessionService and project:
            try:
                return VertexAiSessionService(project=project, location=location)
            except Exception as e:
                logger.warning(f"Failed to create VertexAiSessionService: {e}")
    
    return InMemorySessionService()


# Create a singleton runner instance
_runner_instance = None
_session_service_instance = None

def _get_or_create_runner():
    """Get or create a singleton ADK Runner instance."""
    global _runner_instance, _session_service_instance
    
    if _runner_instance:
        return _runner_instance
    
    if not ADK_AVAILABLE or not Runner or not root_agent:
        return None
    
    if not _session_service_instance:
        _session_service_instance = _make_session_service()
    
    if not _session_service_instance:
        return None
    
    _runner_instance = Runner(
        app_name=os.getenv("APP_NAME", "adam"),
        agent=root_agent,
        session_service=_session_service_instance,
    )
    logger.info("Created singleton Runner instance")
    return _runner_instance


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
    
    # Try to create and use ADK Runner
    runner = None
    try:
        runner = _get_or_create_runner()
        if runner:
            logger.info("Using ADK Runner for streaming")
            
            # Ensure session exists (create if needed)
            session_id_to_use = session_id or "default"
            try:
                # Try to get existing session
                await runner.session_service.get_session(session_id_to_use)
                logger.info(f"Using existing session: {session_id_to_use}")
            except Exception as e:
                # Create new session if it doesn't exist
                logger.info(f"Session {session_id_to_use} not found, creating new session")
                try:
                    await runner.session_service.create_session(
                        app_name=os.getenv("APP_NAME", "adam"),
                        user_id="user",
                        session_id=session_id_to_use,
                        state={}
                    )
                    logger.info(f"Created new session: {session_id_to_use}")
                except Exception as create_error:
                    logger.error(f"Failed to create session: {create_error}")
                    # Fallback to default session
                    session_id_to_use = "default"
            
            # Create Content object for the message
            message_content = Content(parts=[{"text": message}]) if Content else message
            
            # Stream structured ADK events
            event_count = 0
            async for event in runner.run_async(
                user_id="user",  # Default user ID
                session_id=session_id_to_use,
                new_message=message_content,  # The message as Content object
                state_delta=None,  # Optional state updates
            ):
                event_count += 1
                logger.debug(f"Event {event_count}: {type(event)}")
                
                # Log event attributes for debugging
                if hasattr(event, 'model_dump'):
                    logger.debug(f"Event dump: {event.model_dump()}")
                elif hasattr(event, '__dict__'):
                    logger.debug(f"Event dict: {event.__dict__}")
                
                # Check if event is a dict or has attributes
                if isinstance(event, dict):
                    # Forward the event as-is
                    yield f"data: {json.dumps(event)}\n\n"
                    await asyncio.sleep(0)
                else:
                    # Process event attributes
                    event_data = {}
                    
                    # Handle ADK Event with content
                    if hasattr(event, 'content') and event.content:
                        # Extract text from content parts
                        content = event.content
                        if hasattr(content, 'parts'):
                            text_parts = []
                            for part in content.parts:
                                if hasattr(part, 'text') and part.text:
                                    text_parts.append(part.text)
                            if text_parts:
                                combined_text = ''.join(text_parts)
                                event_data = {'type': 'llm_output', 'text': combined_text}
                    
                    # Handle tool calls if present
                    elif hasattr(event, 'tool_calls'):
                        for tool_call in event.tool_calls:
                            if hasattr(tool_call, 'name'):
                                event_data = {
                                    'type': 'tool_call',
                                    'name': tool_call.name,
                                    'args': getattr(tool_call, 'args', {})
                                }
                                yield f"data: {json.dumps(event_data)}\n\n"
                                await asyncio.sleep(0)
                        continue  # Already yielded tool calls
                    
                    # Handle other event types
                    elif hasattr(event, '__class__'):
                        event_type = event.__class__.__name__
                        
                        if 'ToolCallStart' in event_type:
                            event_data = {
                                'type': 'tool_start',
                                'name': getattr(event, 'tool_name', 'unknown'),
                                'args': getattr(event, 'tool_args', {})
                            }
                        elif 'ToolCallEnd' in event_type:
                            event_data = {
                                'type': 'tool_end',
                                'name': getattr(event, 'tool_name', 'unknown'),
                                'output': getattr(event, 'tool_output', '')
                            }
                    
                    if event_data:
                        yield f"data: {json.dumps(event_data)}\n\n"
                        await asyncio.sleep(0)
            
            logger.info(f"Streamed {event_count} events from ADK Runner")
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            return
            
    except Exception as runner_error:
        logger.error(f"Runner error: {runner_error}", exc_info=True)
        # Fall through to direct tool invocation
        
        # Fallback: call the agent tools directly for demonstration
        logger.info("Using direct tool invocation fallback")
        
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
                await asyncio.sleep(0)
                
                try:
                    result = load_repo(url)
                    logger.info(f"Load_repo tool returned: {type(result)}")
                    
                    # Extract key info
                    files_count = result.get('files', 0) if isinstance(result, dict) else 0
                    commit_hash = result.get('commit', 'unknown') if isinstance(result, dict) else 'unknown'
                    
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': 'load_repo', 'output': 'Repository loaded'})}\n\n"
                    await asyncio.sleep(0)
                    
                    yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Repository loaded successfully. Files: {files_count}, Commit: {commit_hash}'})}\n\n"
                    await asyncio.sleep(0)
                    
                except Exception as tool_error:
                    logger.error(f"Load_repo tool error: {tool_error}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': 'load_repo', 'output': str(tool_error)})}\n\n"
                    yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Error loading repository: {tool_error}'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'llm_output', 'text': 'Please provide a repository URL to load.'})}\n\n"
        
        elif "what" in message.lower() or "explain" in message.lower() or "tell me" in message.lower():
            # Use the ask tool
            query = message
            yield f"data: {json.dumps({'type': 'tool_start', 'name': 'ask', 'args': {'query': query}})}\n\n"
            await asyncio.sleep(0)  # Allow UI to update
            
            try:
                result = ask(query)
                logger.info(f"Ask tool returned: {type(result)}")
                
                # Handle different result types
                if isinstance(result, dict):
                    answer = result.get('answer', result.get('response', str(result)))
                else:
                    answer = str(result) if result else 'No answer available'
                
                # Send tool end first
                yield f"data: {json.dumps({'type': 'tool_end', 'name': 'ask', 'output': 'Query processed'})}\n\n"
                await asyncio.sleep(0)  # Allow UI to update
                
                # Then send the actual answer as llm_output
                if answer:
                    yield f"data: {json.dumps({'type': 'llm_output', 'text': answer})}\n\n"
                    await asyncio.sleep(0)  # Allow UI to update
                    
            except Exception as tool_error:
                logger.error(f"Ask tool error: {tool_error}", exc_info=True)
                yield f"data: {json.dumps({'type': 'tool_end', 'name': 'ask', 'output': str(tool_error)})}\n\n"
                yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Error: {tool_error}'})}\n\n"
        
        elif "index" in message.lower():
            # Build index
            yield f"data: {json.dumps({'type': 'tool_start', 'name': 'index', 'args': {}})}\n\n"
            await asyncio.sleep(0)
            
            try:
                result = index()
                logger.info(f"Index tool returned: {type(result)}")
                
                # Extract key info from result
                vector_count = result.get("vector_count", 0) if isinstance(result, dict) else 0
                backend = result.get("backend", "unknown") if isinstance(result, dict) else "unknown"
                
                yield f"data: {json.dumps({'type': 'tool_end', 'name': 'index', 'output': 'Index built successfully'})}\n\n"
                await asyncio.sleep(0)
                
                yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Index built: {vector_count} vectors, backend: {backend}'})}\n\n"
                await asyncio.sleep(0)
                
            except Exception as tool_error:
                logger.error(f"Index tool error: {tool_error}", exc_info=True)
                yield f"data: {json.dumps({'type': 'tool_end', 'name': 'index', 'output': str(tool_error)})}\n\n"
                yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Error: {tool_error}'})}\n\n"
        
        elif "ingest" in message.lower():
            # Ingest repository
            yield f"data: {json.dumps({'type': 'tool_start', 'name': 'ingest', 'args': {}})}\n\n"
            await asyncio.sleep(0)
            
            try:
                result = ingest()
                logger.info(f"Ingest tool returned: {type(result)}")
                
                # Extract file count
                file_count = len(result.get("files", [])) if isinstance(result, dict) else 0
                
                yield f"data: {json.dumps({'type': 'tool_end', 'name': 'ingest', 'output': 'Repository ingested'})}\n\n"
                await asyncio.sleep(0)
                
                yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Repository ingested: {file_count} files'})}\n\n"
                await asyncio.sleep(0)
                
            except Exception as tool_error:
                logger.error(f"Ingest tool error: {tool_error}", exc_info=True)
                yield f"data: {json.dumps({'type': 'tool_end', 'name': 'ingest', 'output': str(tool_error)})}\n\n"
                yield f"data: {json.dumps({'type': 'llm_output', 'text': f'Error: {tool_error}'})}\n\n"
        
        else:
            # Default response with help
            help_text = """I can help you analyze repositories. Here are some commands you can try:

1. Load a repository: "Load repository https://github.com/..."
2. Ask questions: "What does this code do?"
3. Build index: "Index the repository"
4. Ingest files: "Ingest the current repository"

For the best experience, try using 'adk web' for Google's built-in UI, or 'adk api_server' for the REST API."""
            yield f"data: {json.dumps({'type': 'llm_output', 'text': help_text})}\n\n"
        
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
        # Fallback to direct tool call
        logger.info(f"ADK API server not available, using direct tool call: {e}")
        
        # Since we can't use run_async directly, call tools instead
        from adam_agent import ask
        
        try:
            result = ask(request.message)
            return {"result": result}
        except Exception as tool_error:
            raise HTTPException(status_code=500, detail=str(tool_error))


# For serving static files in production
if os.path.exists("static"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="static", html=True), name="static")