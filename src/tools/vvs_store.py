from __future__ import annotations
from typing import List, Dict, Any, Tuple
import os
from dataclasses import dataclass

class VVSNotConfigured(RuntimeError):
    pass

@dataclass
class VVSItem:
    id: str
    vector: List[float]
    metadata: Dict[str, Any]

class VertexVectorStore:
    """
    Vertex Vector Search adapter (Vector Search v2).
    Requires ADC auth and configured index/endpoint.
    """
    def __init__(self, project: str, location: str, index: str, endpoint: str):
        if not (project and location and index and endpoint):
            raise VVSNotConfigured("Missing VVS configuration (project/location/index/endpoint).")
        
        # For unit tests, skip SDK initialization
        if os.getenv("UNIT_TEST", "") == "1":
            self._index = None
            self._endpoint = None
            return
        
        # Real implementation using SDK
        try:
            from google.cloud import aiplatform
            aiplatform.init(project=project, location=location)
            self._index = aiplatform.MatchingEngineIndex(index_name=index)
            self._endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=endpoint)
        except ImportError:
            raise VVSNotConfigured("google-cloud-aiplatform not installed. Run: pip install google-cloud-aiplatform")
        except Exception as e:
            raise VVSNotConfigured(f"Failed to initialize VVS client: {e}")

    def _to_datapoint(self, it: VVSItem):
        """Convert VVSItem to IndexDatapoint."""
        from google.cloud.aiplatform_v1.types import IndexDatapoint
        
        # Optional metadata as restrictions (filter fields)
        restricts = []
        for k in ("path", "start", "end"):
            if k in it.metadata and it.metadata[k] is not None:
                restricts.append(IndexDatapoint.Restriction(
                    namespace=k,
                    allow_list=[str(it.metadata[k])]
                ))
        return IndexDatapoint(
            datapoint_id=it.id,
            feature_vector=it.vector,
            restricts=restricts or None,
        )

    def upsert(self, namespace: str, items: List[VVSItem]) -> None:
        """
        Upsert vectors with metadata. Batches are handled by caller.
        """
        if os.getenv("UNIT_TEST", "") == "1":
            return  # No-op for unit tests
        
        if not items or not self._index:
            return
        
        dps = [self._to_datapoint(it) for it in items]
        self._index.upsert_datapoints(datapoints=dps)

    def query(self, namespace: str, query_vector: List[float], top_k: int) -> List[Tuple[str, float]]:
        """
        Return list of (id, score). Real implementation calls VVS query.
        """
        if os.getenv("UNIT_TEST", "") == "1":
            return []  # Empty results for unit tests
        
        if not self._endpoint:
            return []
        
        resp = self._endpoint.match(
            queries=[query_vector],
            num_neighbors=top_k,
        )
        out: List[Tuple[str, float]] = []
        for r in resp:
            for nn in r.nearest_neighbors:
                # Convert distance to similarity-ish score (cosine distance → similarity)
                sim = 1.0 / (1.0 + (nn.distance or 0.0))
                out.append((nn.id, float(sim)))
        return out