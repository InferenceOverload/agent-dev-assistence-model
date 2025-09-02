# ADK Multi-Agent System

A multi-agent system built on Google Cloud Platform using Vertex AI and Google ADK (Agent Development Kit).

## Features

- **Repository Ingestion**: Understand arbitrary repos (React, Python, SQL, etc.) and build a Code Map
- **Intelligent Q&A**: Answer questions about code using RAG (Retrieval-Augmented Generation)
- **Work Planning**: Convert requirements into Rally stories/features/tasks
- **Automated Development**: Implement stories, create GitHub PRs, and run tests
- **Sandbox Deployment**: Spin up Cloud Run previews for validation
- **Session-Scoped**: Data is session-only by default (no persistence unless enabled)

## Architecture

### Agents

1. **Orchestrator** (gemini-2.0-flash): Root agent for intent routing
2. **Repo Ingestor**: Clones and analyzes repositories
3. **Indexer**: Creates embeddings and manages vector indices
4. **RAG Answerer** (gemini-1.5-pro): Retrieval-augmented Q&A and doc generation
5. **Rally Planner**: Creates work items from requirements
6. **Dev & PR Agent**: Implements stories and creates pull requests
7. **Code Exec Agent**: Runs tests using built-in code execution
8. **Sandbox Runner**: Deploys Cloud Run preview environments

### Technology Stack

- **Google ADK**: Agent framework with built-in tools
- **Vertex AI**: Gemini models and Text Embeddings
- **Vertex Vector Search**: Scalable vector similarity search
- **Cloud Run**: Serverless container deployment
- **FastAPI**: REST API and chat interface

## Setup

### Prerequisites

- Python 3.10+
- Google Cloud Project with Vertex AI enabled
- Rally API access (optional)
- GitHub token (optional)

### Installation

1. Clone the repository:
```bash
git clone <your-repo>
cd adk-multi-agent
```

2. Install dependencies:
```bash
pip install -e ".[dev]"
```

3. Configure the application:
```bash
cp configs/app.example.yaml configs/app.yaml
# Edit configs/app.yaml with your settings
```

4. Set environment variables:
```bash
export GCP_PROJECT="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
export RALLY_API_KEY="your-rally-key"  # Optional
export GITHUB_TOKEN="your-github-token"  # Optional
```

## Usage

### Local Development

1. Run the ADK agent:
```bash
python run_agent.py
```

2. Or start the FastAPI UI:
```bash
uvicorn src.ui.fastapi_app:app --reload
```

3. Access the API at http://localhost:8000

### ADK Development UI

```bash
adk web  # Start the ADK dev UI
```

### API Examples

```python
# Chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What does the authentication module do?"}'

# Direct agent invocation
curl -X POST http://localhost:8000/agent/repo_ingestor/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "action": "ingest",
    "params": {"repo_url": "https://github.com/example/repo"}
  }'
```

## Development

### Project Structure

```
.
├── src/
│   ├── agents/       # Agent implementations
│   ├── tools/        # Tool wrappers
│   ├── services/     # External service clients
│   ├── core/         # Core types and utilities
│   └── ui/           # FastAPI application
├── configs/          # Configuration files
├── docs/             # Generated documentation
└── tests/            # Unit tests
```

### Running Tests

```bash
pytest tests/
```

### Linting and Type Checking

```bash
ruff check src/
mypy src/
```

## Deployment

### Cloud Run Deployment

```bash
adk deploy cloud_run \
  --project=$GCP_PROJECT \
  --region=us-central1
```

### Manual Deployment

```bash
gcloud run deploy adk-multi-agent \
  --source . \
  --project=$GCP_PROJECT \
  --region=us-central1
```

## Configuration

Key configuration options in `configs/app.yaml`:

- **GCP Settings**: Project ID, region
- **Model Selection**: Fast vs deep models
- **Embedding**: Dimensions (768/1536/3072)
- **Vector Search**: Enable/disable, streaming mode
- **Session**: TTL, memory persistence
- **Integrations**: Rally, GitHub credentials

## License

MIT