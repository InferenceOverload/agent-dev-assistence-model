#!/usr/bin/env python3
"""Provision Vertex Vector Search index and endpoint via SDK."""

import os
from google.cloud import aiplatform

PROJECT_ID = os.environ["PROJECT_ID"]
LOCATION = os.environ.get("LOCATION", "us-central1")

aiplatform.init(project=PROJECT_ID, location=LOCATION)

# Use a stable display name if re-run; SDK handles reuse by name differently than ID.
index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
    display_name=f"vs-index-{PROJECT_ID}",
    dimensions=768,
    distance_measure_type="COSINE_DISTANCE",
    approximate_neighbors_count=20,
    index_update_method="STREAM_UPDATE",
)
endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
    display_name=f"vs-endpoint-{PROJECT_ID}",
    public_endpoint_enabled=True,
)

# Deploy (may take ~20–30 minutes on first deploy)
endpoint.deploy_index(
    index=index,
    deployed_index_id=f"vs-deployed-{PROJECT_ID}",
)

# Also print to stdout and append to a log file for the setup script
msg = []
msg.append(f"INDEX: {index.resource_name}")
msg.append(f"ENDPOINT: {endpoint.resource_name}")
out = "\n".join(msg)
print(out)

os.makedirs("scripts", exist_ok=True)
with open("scripts/.provision.log", "a", encoding="utf-8") as f:
    f.write(out + "\n")