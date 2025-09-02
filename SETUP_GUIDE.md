# ADK Multi-Agent System Setup Guide

## ✅ Completed Steps

1. **Virtual Environment Created**
   - Location: `venv/`
   - Python version: 3.13

2. **Dependencies Installed**
   - Google ADK framework
   - All required packages for agents
   - Development tools

3. **Agent Structure Created**
   - 8 specialized agents with mock tools
   - Orchestrator as root agent
   - Proper ADK agent definitions

## 🔑 Required: Add Your API Key

### Option 1: Google AI Studio (Recommended for Testing)

1. Get your API key from: https://makersuite.google.com/app/apikey
2. Edit the `.env` file:
   ```bash
   GOOGLE_API_KEY=your-actual-api-key-here
   ```

### Option 2: Vertex AI (For Production)

1. Set up a GCP project with Vertex AI enabled
2. Edit the `.env` file:
   ```bash
   # Comment out GOOGLE_API_KEY
   # GOOGLE_API_KEY=...
   
   # Uncomment and fill these:
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_LOCATION=us-central1
   GOOGLE_GENAI_USE_VERTEXAI=True
   ```

## 🚀 Testing the System

### 1. Activate Virtual Environment
```bash
source venv/bin/activate
```

### 2. Test with ADK Web (Interactive UI)
```bash
adk web src.agents
```
Then open: http://localhost:8000

### 3. Test in Terminal
```bash
adk run src.agents
```

### 4. Test Individual Agents
```bash
python test_agents.py
```

## 📝 Current Agent Capabilities (Mock Implementation)

- **Orchestrator**: Routes requests to appropriate agents
- **Repo Ingestor**: Mock cloning and analysis
- **Indexer**: Mock embeddings and vector indexing
- **RAG Answerer**: Mock code search and Q&A
- **Rally Planner**: Mock story creation
- **Dev & PR**: Mock feature implementation
- **Sandbox Runner**: Mock Cloud Run deployment
- **Code Exec**: Mock test execution

## 🔧 Next Steps

Once you've added your API key:

1. Test agent communication with `adk web`
2. Replace mock tools with real implementations as needed
3. Configure Rally/GitHub credentials if using those integrations

## 📚 Important Files

- `.env` - Your API keys (keep private!)
- `src/agents/` - Agent definitions
- `src/tools/` - Tool implementations (currently stubs)
- `test_agents.py` - Test script

## ⚠️ Troubleshooting

- If `adk web` fails, ensure your API key is correctly set in `.env`
- Check that virtual environment is activated
- For Vertex AI, ensure you have proper GCP credentials configured