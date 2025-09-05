#!/usr/bin/env python3
"""Deploy existing index to endpoint."""

from google.cloud import aiplatform

PROJECT_ID = "insurance-claims-poc"
LOCATION = "us-central1"
INDEX_ID = "4080456975467413504"
ENDPOINT_ID = "2848124343056072704"

aiplatform.init(project=PROJECT_ID, location=LOCATION)

# Get existing resources
index = aiplatform.MatchingEngineIndex(
    index_name=f"projects/325675975173/locations/{LOCATION}/indexes/{INDEX_ID}"
)
endpoint = aiplatform.MatchingEngineIndexEndpoint(
    index_endpoint_name=f"projects/325675975173/locations/{LOCATION}/indexEndpoints/{ENDPOINT_ID}"
)

# Check if already deployed
print("Checking current deployments...")
deployed_indexes = endpoint.deployed_indexes
if deployed_indexes:
    print(f"Index already deployed: {deployed_indexes}")
else:
    print("Deploying index to endpoint...")
    # Deploy with valid ID (letters, numbers, underscores only)
    deployed_id = f"vs_deployed_{PROJECT_ID.replace('-', '_')}"
    endpoint.deploy_index(
        index=index,
        deployed_index_id=deployed_id,
    )
    print(f"Deployed with ID: {deployed_id}")

print("\nResources ready:")
print(f"INDEX: {index.resource_name}")
print(f"ENDPOINT: {endpoint.resource_name}")