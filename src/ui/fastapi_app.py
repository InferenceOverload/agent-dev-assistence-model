"""FastAPI application for chat UI."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime

from ..core.types import ChatMessage, AgentRequest, AgentResponse
from ..core.config import load_config
from ..core.logging import setup_logging

logger = logging.getLogger(__name__)

app = FastAPI(title="ADK Multi-Agent System", version="0.1.0")

# Global runner instance (initialized on startup)
runner = None


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None
    stream: bool = False
    

class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    session_id: str
    metadata: Dict[str, Any] = {}
    

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global runner
    
    # Setup logging
    setup_logging()
    
    # Load configuration
    config = load_config()
    
    # Initialize ADK runner
    # TODO: Initialize runner with orchestrator agent
    logger.info("Application started")
    

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint for agent interaction."""
    try:
        if runner is None:
            raise HTTPException(status_code=503, detail="Runner not initialized")
            
        # Create agent request
        agent_request = AgentRequest(
            action="chat",
            params={"message": request.message},
            session_id=request.session_id
        )
        
        # TODO: Forward to ADK runner
        # response = await runner.run_async(agent_request)
        
        # Placeholder response
        response_text = f"Received: {request.message}"
        
        return ChatResponse(
            response=response_text,
            session_id=request.session_id or "default",
            metadata={"timestamp": datetime.utcnow().isoformat()}
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        

@app.post("/agent/{agent_name}/invoke")
async def invoke_agent(agent_name: str, request: AgentRequest):
    """Direct agent invocation endpoint."""
    try:
        if runner is None:
            raise HTTPException(status_code=503, detail="Runner not initialized")
            
        # TODO: Route to specific agent
        
        return AgentResponse(
            status="success",
            result={"agent": agent_name, "action": request.action},
            metadata={"timestamp": datetime.utcnow().isoformat()}
        )
        
    except Exception as e:
        logger.error(f"Agent invocation error: {e}", exc_info=True)
        return AgentResponse(
            status="error",
            error=str(e)
        )
        

@app.get("/sessions")
async def list_sessions():
    """List active sessions."""
    # TODO: Get sessions from runner
    return {"sessions": []}
    

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    # TODO: Delete session from runner
    return {"status": "deleted", "session_id": session_id}
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)