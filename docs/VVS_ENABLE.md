# Vertex Vector Search Enablement (Production Path)

## Overview
Vertex Vector Search (VVS) provides a scalable, managed vector similarity search service that automatically indexes to repositories with >1200 files or >10,000 chunks.

## Setup Steps

### 1) Provision Vector Search resources
- Create an index and endpoint in your GCP project/region (Vertex AI → Vector Search).
- Note the full resource names for index and endpoint.

### 2) Authentication
Ensure Application Default Credentials (ADC) are configured on the host running ADK:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 3) Set environment variables
```bash
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
export GOOGLE_CLOUD_LOCATION=us-central1
export VVS_INDEX=projects/.../locations/.../indexes/INDEX_ID
export VVS_ENDPOINT=projects/.../locations/.../indexEndpoints/ENDPOINT_ID
export VVS_NAMESPACE_MODE=session    # or 'commit' for persistence
```

### 4) Enable in configuration
Update your `configs/app.yaml`:
```yaml
vector_search:
  vvs_enabled: true
  vvs_upsert_batch: 256  # Adjust based on your needs
```

## Auto-Switch Thresholds

The system automatically switches to VVS when:
- Repository has ≥1200 files
- Repository has ≥10,000 chunks (estimated)
- Repository size ≥50,000 vectors

## Testing

To test VVS integration without actual GCP resources:
```bash
export UNIT_TEST=1
pytest tests/test_vvs_path.py
```

## Performance Tuning

- **Batch size**: Adjust `vvs_upsert_batch` based on your index configuration
- **Namespace mode**: 
  - `session`: Vectors are scoped to session (default)
  - `commit`: Vectors are scoped to git commit (for persistence)
- **Dimensions**: VVS uses 768-dimensional vectors by default

## Monitoring

Check indexing status in responses:
```json
{
  "backend": "vertex_vector_search",
  "using_vvs": true,
  "vector_count": 5000,
  ...
}
```