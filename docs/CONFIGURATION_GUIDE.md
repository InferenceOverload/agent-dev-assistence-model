# ADAM Configuration Guide

## Overview
This guide documents all environment variables and configuration options for controlling ADAM's behavior. All features are opt-in and disabled by default unless noted.

## Quick Start for Testing

```bash
# Basic setup (no advanced features)
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
adk web

# Enable ALL performance features for testing
export VVS_ENABLED=true
export RERANK_ENABLED=1
export VVS_FORCE=1  # Force VVS even for small repos
source .env.vvs    # Load VVS index/endpoint config
adk web
```

## Environment Variables Reference

### Core Configuration

| Variable | Default | Description | When to Use |
|----------|---------|-------------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Required | Your GCP project ID | Always required |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP region for Vertex AI | Change if using different region |
| `GITHUB_TOKEN` | None | GitHub personal access token | For PR creation/management |

### Workspace Storage Configuration

| Variable | Default | Description | When to Use |
|----------|---------|-------------|-------------|
| `ADAM_STORAGE_TYPE` | `local` | Storage backend (`local` or `gcs`) | Use `gcs` for Vertex AI production |
| `ADAM_WORKSPACE_ROOT` | `.workspace` | Local storage directory | Change for custom local path |
| `ADAM_GCS_BUCKET` | None | GCS bucket name | Required when storage_type=gcs |
| `ADAM_GCS_PREFIX` | `workspace` | Prefix for GCS objects | Organize multiple workspaces |

**Notes:**
- In cloud environments (Vertex AI, Cloud Run), defaults to `/tmp/adam_workspace` automatically
- GCS storage provides persistence across container restarts and instances
- Local storage is ephemeral in containerized environments

### Rally Integration Configuration

| Variable | Default | Description | When to Use |
|----------|---------|-------------|-------------|
| `RALLY_API_KEY` | None | Rally API key (zsessionid) | Required for Rally features |
| `RALLY_BASE_URL` | `https://rally1.rallydev.com` | Rally API base URL | Change for on-premise Rally |
| `RALLY_WORKSPACE_ID` | None | Rally workspace ObjectID | Required for Rally features |
| `RALLY_PROJECT_ID` | None | Rally project ObjectID | Required for Rally features |

### Vertex Vector Search (VVS) Configuration

| Variable | Default | Description | When to Use |
|----------|---------|-------------|-------------|
| `VVS_ENABLED` | `false` | Enable Vertex Vector Search | For repos >1200 files or concurrent sessions |
| `VVS_INDEX` | None | Full VVS index resource name | Required when VVS_ENABLED=true |
| `VVS_ENDPOINT` | None | Full VVS endpoint resource name | Required when VVS_ENABLED=true |
| `VVS_NAMESPACE_MODE` | `session` | Namespace strategy (`session` or `commit`) | Use `commit` for persistence across sessions |
| `VVS_UPSERT_BATCH` | `256` | Batch size for vector upserts | Tune based on index config |
| **Testing Overrides** |
| `VVS_FORCE` | `0` | Force VVS regardless of repo size | Testing VVS with small repos |
| `VVS_MIN_FILES` | `1200` | File count threshold for auto-VVS | Lower to trigger VVS earlier |
| `VVS_MIN_CHUNKS` | `10000` | Chunk count threshold for auto-VVS | Lower to trigger VVS earlier |

### LLM Reranking Configuration

| Variable | Default | Description | When to Use |
|----------|---------|-------------|-------------|
| `RERANK_ENABLED` | `0` | Enable LLM-based reranking | Improve precision for complex queries |
| `RERANK_TOPK` | `80` | Number of candidates to rerank | Increase for broader reranking |

### Session Configuration

| Variable | Default | Description | When to Use |
|----------|---------|-------------|-------------|
| `SESSION_TTL_MINUTES` | `60` | Session timeout in minutes | Adjust based on usage patterns |
| `USE_MEMORY_BANK` | `false` | Enable persistent memory bank | For cross-session continuity |

## Feature Decision Matrix

### When to Enable Each Feature

#### Vertex Vector Search (VVS)
**Enable when:**
- Repository has >1200 files
- Repository has >10,000 estimated chunks
- Need concurrent sessions accessing same repo
- Want persistence across sessions
- Repository size >1.5GB

**Keep disabled when:**
- Small repositories (<1200 files)
- Single-session usage
- Want minimal latency
- Testing/development with small codebases

#### LLM Reranking
**Enable when:**
- Need high precision for complex queries
- Searching for semantic concepts vs exact matches
- Have sufficient LLM quota/budget
- Users report irrelevant results in top positions

**Keep disabled when:**
- Simple keyword searches work well
- Need minimal latency
- Cost optimization is priority
- BM25+vector fusion is sufficient

## Configuration Profiles

### Development/Testing Profile
```bash
# Minimal config for local development
export GOOGLE_CLOUD_PROJECT=my-dev-project
export GOOGLE_CLOUD_LOCATION=us-central1
# No VVS, no reranking - fast and simple
```

### Small Repository Profile
```bash
# For repos <1200 files
export GOOGLE_CLOUD_PROJECT=my-project
export GOOGLE_CLOUD_LOCATION=us-central1
export RERANK_ENABLED=1  # Optional: improve precision
# VVS disabled by default (uses in-memory vectors)
```

### Large Repository Profile
```bash
# For repos >1200 files
source .env.vvs  # Load VVS config
export VVS_ENABLED=true
export RERANK_ENABLED=1
export RERANK_TOPK=100  # Rerank more candidates
```

### Demo/Testing Profile
```bash
# Force all features for testing/demos
source .env.vvs
export VVS_FORCE=1  # Force VVS even for small repos
export VVS_MIN_FILES=50  # Lower thresholds
export VVS_MIN_CHUNKS=500
export RERANK_ENABLED=1
export RERANK_TOPK=50
```

### Production Profile
```bash
# Optimized for production use
source .env.vvs
export VVS_ENABLED=true
export VVS_NAMESPACE_MODE=commit  # Persistence across sessions
export RERANK_ENABLED=1
export RERANK_TOPK=80
export SESSION_TTL_MINUTES=120
```

### Vertex AI Deployment Profile
```bash
# For deployment on Vertex AI Agent Builder
export GOOGLE_CLOUD_PROJECT=my-project
export GOOGLE_CLOUD_LOCATION=us-central1

# Use GCS for persistent workspace storage
export ADAM_STORAGE_TYPE=gcs
export ADAM_GCS_BUCKET=my-adam-workspace-bucket
export ADAM_GCS_PREFIX=vertex-ai-agents

# Enable VVS for large repos
source .env.vvs
export VVS_ENABLED=true
export VVS_NAMESPACE_MODE=commit

# Rally integration (if needed)
export RALLY_API_KEY=${SECRET_RALLY_API_KEY}
export RALLY_WORKSPACE_ID=12345678
export RALLY_PROJECT_ID=87654321
```

### Local Development Profile with GCS
```bash
# Use GCS storage even in local development
export ADAM_STORAGE_TYPE=gcs
export ADAM_GCS_BUCKET=my-dev-bucket
export ADAM_GCS_PREFIX=dev-workspace

# Or use local storage with custom path
export ADAM_STORAGE_TYPE=local
export ADAM_WORKSPACE_ROOT=/tmp/adam-dev
```

### Cloud Run Deployment Profile
```bash
# Automatically uses /tmp for workspace (detected via K_SERVICE)
export GOOGLE_CLOUD_PROJECT=my-project

# Optional: Use GCS for persistence
export ADAM_STORAGE_TYPE=gcs
export ADAM_GCS_BUCKET=my-cloudrun-workspace
```

## Workspace Storage Details

### Storage Backend Selection
ADAM automatically selects the appropriate storage based on environment:

1. **Local Development** (default)
   - Uses `.workspace` directory in current folder
   - All cloned repos stored locally
   - Persistent across sessions on same machine

2. **Cloud Environments** (auto-detected)
   - Detects: `K_SERVICE`, `VERTEX_AI_ENDPOINT_ID`, `GAE_ENV`
   - Automatically uses `/tmp/adam_workspace`
   - Ephemeral - lost on container restart

3. **GCS Storage** (configured)
   - Set `ADAM_STORAGE_TYPE=gcs`
   - Persistent across all instances
   - Shared between multiple agents
   - Survives container restarts

### GCS Storage Setup
```bash
# 1. Create a GCS bucket
gsutil mb gs://my-adam-workspace

# 2. Set permissions (for Vertex AI service account)
gsutil iam ch serviceAccount:vertex-ai-sa@project.iam.gserviceaccount.com:objectAdmin gs://my-adam-workspace

# 3. Configure ADAM
export ADAM_STORAGE_TYPE=gcs
export ADAM_GCS_BUCKET=my-adam-workspace
export ADAM_GCS_PREFIX=production  # Optional: organize by environment
```

### Storage Performance Considerations

| Storage Type | Latency | Persistence | Scalability | Cost |
|-------------|---------|-------------|-------------|------|
| Local `.workspace` | Fastest | Local only | Single instance | Free |
| Cloud `/tmp` | Fast | Ephemeral | Per instance | Free |
| GCS | +100-300ms | Permanent | Multi-instance | ~$0.02/GB/month |

### When to Use Each Storage Type

**Local Storage:**
- Development and testing
- Single-user scenarios
- Small repos that fit in memory

**Cloud `/tmp` Storage:**
- Stateless processing
- Short-lived sessions
- Cost optimization

**GCS Storage:**
- Production deployments
- Multi-agent scenarios
- Large repos requiring persistence
- Shared workspace between teams

## How Features Interact

1. **Base Retrieval**: Always active - BM25 + in-memory vectors
2. **VVS Enhancement**: When enabled, replaces in-memory vectors with cloud-based index
3. **Reranking Layer**: When enabled, post-processes top-K results from base/VVS retrieval
4. **Policy Engine**: Automatically decides when to use embeddings based on repo size
5. **Workspace Storage**: Manages cloned repositories independent of vector storage

## Performance Impact

| Feature | Latency Impact | Cost Impact | Quality Impact |
|---------|---------------|-------------|----------------|
| Base Only | Baseline | Minimal | Good for small repos |
| +VVS | +100-200ms | +$0.05/1K queries | Better for large repos |
| +Reranking | +500-1000ms | +$0.01/query | 20-30% precision gain |
| Both | +600-1200ms | Both costs | Best quality |

## Monitoring & Debugging

Check active configuration:
```bash
# See what's enabled
env | grep -E "VVS_|RERANK_|GOOGLE_CLOUD"

# Check if VVS is being used (in responses)
# Look for: "backend": "vertex_vector_search"

# Check if reranking is active
# Look for LLM calls to Gemini Flash in logs
```

## Common Configurations

### "I want the best quality, cost is not a concern"
```bash
source .env.vvs
export VVS_ENABLED=true
export RERANK_ENABLED=1
export RERANK_TOPK=150
```

### "I want fast responses for a small codebase"
```bash
# Use defaults - everything disabled
export GOOGLE_CLOUD_PROJECT=my-project
```

### "I'm debugging why results are poor"
```bash
# Enable reranking first (biggest quality impact)
export RERANK_ENABLED=1
export RERANK_TOPK=100

# If still poor, check if VVS would help
export VVS_FORCE=1  # Test with VVS
```

### "I want to test all features with a tiny repo"
```bash
source .env.vvs
export VVS_FORCE=1
export VVS_MIN_FILES=10
export VVS_MIN_CHUNKS=100
export RERANK_ENABLED=1
```

## Troubleshooting

### Workspace Storage Issues

**`.workspace` folder created locally:**
- This is expected in local development
- Add `.workspace/` to `.gitignore`
- Use `ADAM_WORKSPACE_ROOT=/tmp/workspace` to change location

**GCS storage not working:**
- Verify bucket exists: `gsutil ls gs://your-bucket`
- Check permissions: `gsutil iam get gs://your-bucket`
- Ensure `ADAM_GCS_BUCKET` is set correctly
- Check for `google-cloud-storage` library: `pip install google-cloud-storage`

**Vertex AI deployment failures:**
- Storage defaults to `/tmp` automatically
- For persistence, configure GCS storage
- Check container has write permissions to `/tmp`

### Rally Integration Issues

**Rally API errors:**
- Verify `RALLY_API_KEY` is correct (get from Rally user settings)
- Check workspace/project IDs are ObjectIDs (not names)
- Test connection: `curl -H "zsessionid: $RALLY_API_KEY" https://rally1.rallydev.com/slm/webservice/v2.0/user`
- Ensure user has permissions to create work items

**Work items not created:**
- Check for dry-run mode (happens when RALLY_API_KEY not set)
- Verify project permissions in Rally
- Check Rally subscription limits

### VVS Not Working
- Check `VVS_ENABLED=true` is set
- Verify `.env.vvs` is sourced
- Ensure VVS_INDEX and VVS_ENDPOINT are set
- Check GCP permissions for Vector Search API

### Reranking Not Applied
- Check `RERANK_ENABLED=1` is set (note: use `1` not `true`)
- Verify Gemini Flash quota available
- Check logs for reranking errors (falls back silently)

### High Latency
- Disable reranking if not needed: `unset RERANK_ENABLED`
- Reduce RERANK_TOPK to rerank fewer candidates
- Consider using VVS only for very large repos
- Switch from GCS to local storage if latency critical

## Cost Optimization

To minimize costs while maintaining quality:
```bash
# Use reranking selectively
export RERANK_ENABLED=1
export RERANK_TOPK=40  # Rerank only top 40

# Use VVS only when automatic thresholds met
export VVS_ENABLED=true
# Don't set VVS_FORCE - let policy decide
```

## Quick Test Commands

```bash
# Test current config
echo "VVS: ${VVS_ENABLED:-disabled}"
echo "Rerank: ${RERANK_ENABLED:-disabled}"
echo "Project: ${GOOGLE_CLOUD_PROJECT}"
echo "Storage: ${ADAM_STORAGE_TYPE:-local}"
echo "Rally: ${RALLY_API_KEY:+configured}"

# Test with minimal features
unset VVS_ENABLED RERANK_ENABLED ADAM_STORAGE_TYPE
adk web

# Test with all features
export VVS_ENABLED=true RERANK_ENABLED=1
export ADAM_STORAGE_TYPE=gcs
adk web
```

## Complete Configuration File Example

Create `configs/app.yaml`:
```yaml
# Core GCP settings
gcp:
  project: "my-project-id"
  location: "us-central1"

# Vertex AI models
vertex:
  fast_model: "gemini-2.0-flash-exp"
  deep_model: "gemini-1.5-pro-002"
  embedding_model: "text-embedding-004"
  embedding_dim: 1536

# Workspace storage
workspace:
  storage_type: "gcs"  # or "local"
  local_root: ".workspace"
  gcs_bucket: "my-adam-workspace"
  gcs_prefix: "production"

# Rally integration
rally:
  api_key: null  # Set via RALLY_API_KEY env var
  workspace: "12345678"
  project: "87654321"

# GitHub integration  
github:
  token: null  # Set via GITHUB_TOKEN env var
  owner: "my-org"
  repo: "my-repo"

# Vector search
vector_search:
  enabled: true
  use_streaming: true
  vvs_enabled: true
  vvs_index: "projects/my-project/locations/us-central1/indexes/adam-index"
  vvs_endpoint: "projects/my-project/locations/us-central1/indexEndpoints/adam-endpoint"

# Session management
session:
  ttl_minutes: 120
  use_memory_bank: false

# Agent settings
agents:
  orchestrator:
    temperature: 0.1
    max_tokens: 1024
  rag_answerer:
    retrieval_k: 12
    expand_neighbors: true
    max_context_tokens: 500000
```