# Vertex Vector Search Enablement (Scripts + SDK)

## Overview
Vertex Vector Search (VVS) provides a scalable, managed vector similarity search service that automatically indexes repositories with >1200 files or >10,000 chunks.

## Quick Path (Recommended)

1. **Auth & Project**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   export PROJECT_ID=your-proj
   export LOCATION=us-central1
   ```

2. **One-shot setup**:
   ```bash
   bash scripts/setup_vvs.sh
   ```
   This enables services, creates index+endpoint, deploys, and writes `.env.vvs`.

3. **Load env file before running ADK**:
   ```bash
   set -a; source .env.vvs; set +a
   export PYTHONPATH="$(pwd)"
   adk web
   ```

4. **Smoke test (optional)**:
   ```bash
   make vvs-smoke
   ```
   This upserts 3 test vectors and queries them to verify the deployment works.

## Manual Setup Steps

### 1) Provision Vector Search resources
Use the provisioning script:
```bash
make vvs-provision
```
Or manually create an index and endpoint in your GCP project/region (Vertex AI → Vector Search).

### 2) Authentication
Ensure Application Default Credentials (ADC) are configured:
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
export VVS_ENABLED=true
export VVS_NAMESPACE_MODE=session    # or 'commit' for persistence
```

### 4) Enable in configuration
Update your `configs/app.yaml`:
```yaml
vector_search:
  vvs_enabled: true
  vvs_upsert_batch: 256  # Adjust based on your needs
```

## Makefile Targets

- `make vvs-setup` - Run complete setup (services, index, endpoint, env file)
- `make vvs-provision` - Just provision index/endpoint via SDK
- `make vvs-smoke` - Test upsert and query with live endpoint
- `make vvs-clean-env` - Remove `.env.vvs` file

## Auto-Switch Thresholds

The system automatically switches to VVS when:
- Repository has ≥1200 files
- Repository has ≥10,000 chunks (estimated)

You can force-enable VVS by setting `VVS_ENABLED=true`.

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

## Troubleshooting

- **VVSNotConfigured error**: Check that all required env vars are set
- **Authentication errors**: Ensure ADC is configured with proper permissions
- **Index not found**: Verify the index/endpoint resource names are correct
- **First deploy slow**: Initial index deployment can take 20-30 minutes

> NOTE: The adapter `VertexVectorStore` is implemented via the Vertex AI Python SDK.
> If you need VPC/private endpoints, configure your endpoint accordingly and adjust the SDK calls.