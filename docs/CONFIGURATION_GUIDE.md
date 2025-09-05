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
| `RALLY_API_KEY` | None | Rally API key for backlog planning | When using Rally integration |
| `GITHUB_TOKEN` | None | GitHub personal access token | For PR creation/management |

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

## How Features Interact

1. **Base Retrieval**: Always active - BM25 + in-memory vectors
2. **VVS Enhancement**: When enabled, replaces in-memory vectors with cloud-based index
3. **Reranking Layer**: When enabled, post-processes top-K results from base/VVS retrieval
4. **Policy Engine**: Automatically decides when to use embeddings based on repo size

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

# Test with minimal features
unset VVS_ENABLED RERANK_ENABLED
adk web

# Test with all features
export VVS_ENABLED=true RERANK_ENABLED=1
adk web
```