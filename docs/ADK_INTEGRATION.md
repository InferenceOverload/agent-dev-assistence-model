# ADK Integration Guide

This guide explains how ADAM integrates with Google's Agent Development Kit (ADK) and provides multiple UI options.

## Overview

ADAM is built as an ADK agent with multiple UI options:
1. **ADK Web UI** - Google's built-in development interface
2. **ADK API Server** - REST API for programmatic access
3. **Custom UI** - FastAPI bridge + Next.js frontend
4. **Hybrid Mode** - Custom UI proxying to ADK API

## Quick Start

### Option 1: Use ADK's Built-in Web UI (Recommended for Development)

```bash
# Run Google's ADK Web UI
./scripts/adk_dev.sh adk-web

# Or directly:
adk web
```

Opens at http://localhost:8000 with:
- Interactive chat interface
- Tool call inspection
- Event tracing
- Voice/audio support (for compatible models)

### Option 2: Custom UI with FastAPI Bridge

```bash
# Run custom FastAPI + Next.js UI
./scripts/adk_dev.sh custom
```

This starts:
- FastAPI server on http://localhost:8000
- Next.js UI on http://localhost:3000

### Option 3: ADK API Server

```bash
# Run ADK's REST API server
./scripts/adk_dev.sh adk-api

# Or directly:
adk api_server
```

API available at http://localhost:8080

Test with:
```bash
curl -X POST http://localhost:8080/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"input": "Load repository https://github.com/..."}'
```

### Option 4: Hybrid Mode (Both ADK API + Custom UI)

```bash
# Run both ADK API and custom UI
./scripts/adk_dev.sh both
```

This runs:
- ADK API Server on :8080
- Custom UI on :3000 (proxies to ADK when available)

## How It Works

### Agent Structure

The ADAM agent (`adam_agent/__init__.py`) is a proper ADK agent with:
- `Agent` class from `google.adk`
- Registered tools (load_repo, ask, index, etc.)
- Proper instruction set
- State management

### ADK Methods Available

The agent provides:
- `run_async(input_text, state)` - Asynchronous execution
- `run_live(input_text, state)` - Live/streaming execution (if configured)

### Custom UI Integration

The custom UI (`server/api.py`) integrates with ADK by:

1. **Direct Agent Calls** (when possible):
```python
result = await root_agent.run_async(
    input_text=message,
    state={"session_id": session_id}
)
```

2. **Fallback to Tool Calls** (for simple commands):
```python
from adam_agent import load_repo, ask
result = load_repo(url)
answer = ask(query)
```

3. **Proxy to ADK API** (when running):
```python
# Proxies to http://localhost:8080/agent/run
response = await client.post("http://localhost:8080/agent/run", ...)
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              User Interface                  │
├─────────────────────────────────────────────┤
│  Option A: ADK Web UI (localhost:8000)      │
│  Option B: Custom Next.js (localhost:3000)   │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│            API Layer                         │
├─────────────────────────────────────────────┤
│  Option A: ADK API Server (:8080)           │
│  Option B: FastAPI Bridge (:8000)           │
└─────────────┬───────────────────────────────┘
              │
┌─────────────▼───────────────────────────────┐
│         ADAM Agent (ADK)                     │
├─────────────────────────────────────────────┤
│  - Tools: load_repo, ask, index, etc.       │
│  - Orchestrator: OrchestratorAgent          │
│  - Storage: Local/GCS workspace             │
│  - Indexing: In-memory/VVS                  │
└─────────────────────────────────────────────┘
```

## Streaming & SSE

### Issue with Initial Approach
- Tried to use `runners.run_sse()` - **doesn't exist**
- ADK doesn't expose SSE streaming directly

### Current Solutions

1. **Use ADK Web UI** - Already handles streaming
2. **Poll ADK API** - Make repeated calls
3. **Custom Bridge** - FastAPI wraps agent calls and streams results

### Proper Streaming Pattern

For true streaming, follow ADK's [custom streaming sample](https://google.github.io/adk-docs/streaming/custom-streaming/):

```python
# Server side: Use LiveRequestQueue
from google.adk import LiveRequestQueue

queue = LiveRequestQueue()
# Process messages from queue
```

```javascript
// Client side: Use EventSource
const eventSource = new EventSource('/chat/stream');
eventSource.onmessage = (event) => {
  // Handle streamed events
};
```

## Environment Variables

### ADK Configuration
```bash
# Google Cloud
export GOOGLE_CLOUD_PROJECT="your-project"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"

# Or use gcloud auth
gcloud auth application-default login
```

### VVS Configuration
```bash
export VVS_ENABLED="true"
export VVS_FORCE="1"  # Force VVS even for small repos
```

### Rally Integration
```bash
export RALLY_API_KEY="your-key"
export RALLY_WORKSPACE_ID="your-workspace"
export RALLY_PROJECT_ID="your-project"
```

## Testing

### 1. Test ADK Web UI
```bash
adk web
# Open http://localhost:8000
# Try: "Load repository https://github.com/google/jax"
```

### 2. Test Custom UI
```bash
./scripts/adk_dev.sh custom
# Open http://localhost:3000
# Try: "Load repository https://github.com/google/jax"
```

### 3. Test Direct API
```bash
adk api_server

# In another terminal:
curl -X POST http://localhost:8080/agent/run \
  -H 'Content-Type: application/json' \
  -d '{"input": "What files are in the repository?"}'
```

## Troubleshooting

### "module 'google.adk.runners' has no attribute 'run_sse'"
- This method doesn't exist in ADK
- Use `agent.run_async()` or `agent.run_live()` instead
- Or use ADK's built-in UI/API server

### Agent Not Loading
```bash
# Check ADK installation
python -c "from google import adk; print('ADK OK')"

# Check agent loads
python -c "from adam_agent import root_agent; print(root_agent)"
```

### Custom UI Not Streaming
- The current implementation falls back to direct tool calls
- For true streaming, use ADK Web UI or implement LiveRequestQueue pattern

### Port Conflicts
- ADK Web UI: default port 8000
- ADK API Server: default port 8080
- Custom FastAPI: configurable (default 8000)
- Next.js UI: default port 3000

Change ports if needed:
```bash
# ADK Web on different port
adk web --port 8001

# FastAPI on different port
uvicorn server.api:app --port 8002
```

## Production Deployment

### Deploy to Vertex AI Agent Engine
```bash
adk deploy agent-engine
```

### Deploy to Cloud Run
```bash
adk deploy cloud_run
```

### Deploy Custom UI
Use the provided Dockerfile and deploy script:
```bash
./scripts/deploy.sh
```

## Best Practices

1. **Development**: Use `adk web` for interactive development
2. **Testing**: Use `adk api_server` for API testing
3. **Production**: Deploy to Vertex AI Agent Engine
4. **Custom UI**: Only if you need specific features not in ADK Web

## Next Steps

1. Test with ADK Web UI first
2. Verify agent tools work correctly
3. Use ADK API server for programmatic access
4. Deploy to Vertex AI for production