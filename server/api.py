"""FastAPI server that bridges to ADK agent with SSE streaming."""

import os
import json
import asyncio
import traceback
from typing import Optional, AsyncIterator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our ADK agent
from adam_agent import root_agent

app = FastAPI(title="ADAM Agent API")

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


async def stream_agent_response(message: str, session_id: str) -> AsyncIterator[str]:
    """Stream agent responses as Server-Sent Events."""
    try:
        # Send initial event
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"
        
        # For now, we'll run the agent synchronously and stream the response
        # In production, you'd want to use the ADK Runner's async capabilities
        
        # Process the message through our agent
        # This is a simplified version - in production you'd integrate with ADK Runner
        response_text = ""
        
        # Check for specific commands that trigger tools
        if "load_repo" in message.lower() or "repository" in message.lower():
            yield f"data: {json.dumps({'type': 'tool_start', 'name': 'load_repo', 'args': {}})}\n\n"
            # Simulate tool execution
            await asyncio.sleep(0.1)
            yield f"data: {json.dumps({'type': 'tool_end', 'name': 'load_repo', 'output': 'Repository loaded'})}\n\n"
        
        if "diagram" in message.lower() or "mermaid" in message.lower():
            # Generate a sample diagram
            mermaid_code = """graph TD
    A[User Request] --> B[ADK Agent]
    B --> C[Process Message]
    C --> D[Execute Tools]
    D --> E[Generate Response]
    E --> F[Stream to UI]"""
            yield f"data: {json.dumps({'type': 'diagram', 'mermaid': mermaid_code})}\n\n"
        
        # Stream the main response
        response_text = f"I received your message: '{message}'. "
        response_text += "I'm the ADAM agent running through FastAPI. "
        response_text += "I can help you analyze repositories, create Rally items, and generate code. "
        response_text += "Try asking me to load a repository or generate a diagram!"
        
        # Stream response in chunks to simulate LLM streaming
        words = response_text.split()
        current_chunk = ""
        for i, word in enumerate(words):
            current_chunk += word + " "
            if i % 3 == 2 or i == len(words) - 1:  # Send every 3 words
                yield f"data: {json.dumps({'type': 'llm', 'text': current_chunk})}\n\n"
                current_chunk = ""
                await asyncio.sleep(0.05)  # Simulate streaming delay
        
        # Send completion event
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
        
    except Exception as e:
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat responses using Server-Sent Events."""
    session_id = request.session_id or "default"
    
    return StreamingResponse(
        stream_agent_response(request.message, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# For serving static files in production
if os.path.exists("static"):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory="static", html=True), name="static")