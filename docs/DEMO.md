# ADAM UI Demo Guide

This guide walks through running and testing the ADAM chat UI locally and deploying to Google Cloud Run.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Google Cloud SDK (for deployment)
- Rally and GitHub credentials configured

## Local Development

### Quick Start

```bash
# Run both API server and UI
./scripts/dev.sh
```

This will:
1. Create/activate Python virtual environment
2. Install all dependencies
3. Start FastAPI server on http://localhost:8000
4. Start Next.js UI on http://localhost:3000

### Manual Setup

If you prefer to run services separately:

#### API Server
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn httpx pydantic
pip install -e .

# Run server
python -m uvicorn server.api:app --reload --port 8000
```

#### UI Development
```bash
cd ui
npm install
npm run dev
```

## Environment Configuration

### VVS Configuration (.env.vvs)

Create `.env.vvs` for Vertex Vector Search:

```bash
# Google Cloud
export GCP_PROJECT_ID="your-project"
export GCP_REGION="us-central1"

# Vertex Vector Search
export VVS_ENABLED="true"
export VVS_INDEX_NAME="adam-index"
export VVS_ENDPOINT_ID="your-endpoint-id"
export VVS_DEPLOYED_INDEX_ID="your-deployed-index-id"

# Force VVS for small repos (optional)
export VVS_FORCE="1"
```

To use VVS configuration:
```bash
source .env.vvs
./scripts/dev.sh
```

### Rally Configuration

Set Rally credentials:
```bash
export RALLY_API_KEY="your-api-key"
export RALLY_WORKSPACE_ID="your-workspace"
export RALLY_PROJECT_ID="your-project"
```

### GitHub Configuration

For GitHub integration:
```bash
export GITHUB_TOKEN="your-token"
export GITHUB_ORG="your-org"
```

## Testing the UI

### 1. Load a Repository

Start a conversation:
```
Load repository https://github.com/anthropics/anthropic-sdk-python
```

The agent will:
- Clone the repository
- Build a code map
- Determine vectorization strategy
- Index if needed

### 2. Ask for Summary

```
What does this application do?
```

The agent will provide:
- Purpose & Overview
- Architecture
- Entry Points
- Dependencies
- How to Run

### 3. Generate Architecture Diagram

```
Show me an architecture diagram
```

The UI will render a Mermaid diagram showing:
- Component relationships
- Data flow
- System boundaries

### 4. Ask "How to Run"

```
How do I run this application locally?
```

The agent will analyze:
- Package files (package.json, requirements.txt, etc.)
- Configuration files
- Documentation
- Provide step-by-step instructions

### 5. Create Rally Items

```
Create a Rally story for adding OAuth authentication
```

The agent will:
- Show a preview of items to create
- Wait for confirmation
- Create items in Rally if confirmed

### 6. Extend Existing Rally Story

```
What's in story 123456789?
Create implementation tasks based on our repo analysis.
```

## Tool Timeline

The UI shows a real-time timeline of tool execution:
- 🟡 Yellow pulsing dot = Tool running
- 🟢 Green dot = Tool complete
- Tool names and outputs are displayed

## Mermaid Diagrams

Diagrams are automatically rendered when the agent generates them:
- Component diagrams
- Sequence diagrams
- Flow charts
- Entity relationships

## Deployment to Cloud Run

### Prerequisites

1. Enable APIs:
```bash
gcloud services enable cloudbuild.googleapis.com run.googleapis.com
```

2. Configure Docker for GCR:
```bash
gcloud auth configure-docker
```

### Deploy

```bash
# Set your project ID
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"  # or your preferred region

# Deploy
./scripts/deploy.sh
```

The script will:
1. Build a Docker image with both UI and API
2. Push to Google Container Registry
3. Deploy to Cloud Run
4. Return the public URL

### Post-Deployment

1. Test the deployment:
```bash
curl https://your-service-url.run.app/health
```

2. Set environment variables in Cloud Run:
```bash
gcloud run services update adam-ui \
  --set-env-vars "RALLY_API_KEY=xxx,GITHUB_TOKEN=yyy" \
  --region $GCP_REGION
```

3. View logs:
```bash
gcloud run logs read --service=adam-ui --region=$GCP_REGION
```

## Troubleshooting

### UI Not Connecting to API

Check CORS settings in `server/api.py`:
- Ensure your UI origin is in allowed_origins
- For production, update to your Cloud Run URL

### SSE Streaming Issues

If messages aren't streaming:
1. Check browser console for errors
2. Verify API is running: `curl http://localhost:8000/health`
3. Check CORS headers

### Mermaid Diagrams Not Rendering

Ensure mermaid is installed:
```bash
cd ui && npm install mermaid
```

### VVS Not Working

Check configuration:
```bash
echo $VVS_ENABLED  # Should be "true"
echo $GCP_PROJECT_ID  # Should be set
```

For small repos, force VVS:
```bash
export VVS_FORCE=1
```

## Performance Tips

1. **Use VVS for large repos** (>80k LOC)
2. **Keep sessions short** - data is session-scoped
3. **Use specific queries** for better retrieval
4. **Load repos once** per session

## Security Notes

- Never commit `.env` files
- Use Secret Manager for production credentials
- Enable authentication in Cloud Run for private deployments
- Rotate API keys regularly