#!/usr/bin/env python3
"""Smoke test for Vertex Vector Search - upsert and query live."""

import os
import sys
from google.cloud import aiplatform
from google.cloud.aiplatform_v1.types import IndexDatapoint

PROJECT_ID = os.environ["PROJECT_ID"]
LOCATION = os.environ.get("LOCATION", "us-central1")
INDEX = os.environ["VVS_INDEX"]
ENDPOINT = os.environ["VVS_ENDPOINT"]

aiplatform.init(project=PROJECT_ID, location=LOCATION)
index = aiplatform.MatchingEngineIndex(index_name=INDEX)
endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=ENDPOINT)

# Three tiny vectors (8-dim here for demo, but real index expects 768)
# We will pad vectors to 768 for the demo
def pad(v, n=768):
    return v + [0.0] * (n - len(v))

vecs = [
    ("doc1", pad([0.9, 0.1, 0.0, 0.0, 0, 0, 0, 0]), {"path": "demo/doc1.txt"}),
    ("doc2", pad([0.1, 0.9, 0.0, 0.0, 0, 0, 0, 0]), {"path": "demo/doc2.txt"}),
    ("doc3", pad([0.0, 0.1, 0.9, 0.0, 0, 0, 0, 0]), {"path": "demo/doc3.txt"}),
]

# Upsert
dps = [IndexDatapoint(datapoint_id=i, feature_vector=v) for (i, v, _) in vecs]
index.upsert_datapoints(datapoints=dps)
print("UPSERTED:", [i for (i, _, _) in vecs])

# Query near doc2 vector
q = vecs[1][1]
resp = endpoint.match(queries=[q], num_neighbors=3)
for r in resp:
    print("QUERY RESULTS:")
    for nn in r.nearest_neighbors:
        print("  id=", nn.id, "distance=", nn.distance)