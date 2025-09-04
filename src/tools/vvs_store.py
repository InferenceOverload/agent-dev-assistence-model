from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import os
from dataclasses import dataclass
from ..core.config import get_config

class VVSNotConfigured(RuntimeError):
    pass

@dataclass
class VVSItem:
    id: str
    vector: List[float]
    metadata: Dict[str, Any]

class VertexVectorStore:
    """
    Minimal adapter for Vertex Vector Search (Vector Search v2).
    NOTE: This implementation expects the environment to be configured with ADC and
    CONFIG.vvs_index / CONFIG.vvs_endpoint set. For unit tests we monkeypatch this class.
    """
    def __init__(self, project: str, location: str, index: str, endpoint: str):
        self.project = project
        self.location = location
        self.index = index
        self.endpoint = endpoint
        if not (project and location and index and endpoint):
            raise VVSNotConfigured("Missing VVS configuration (project/location/index/endpoint).")

    # ---- Public API ----
    def upsert(self, namespace: str, items: List[VVSItem]) -> None:
        """
        Upsert vectors with metadata. Batches are handled by caller.
        This is a placeholder that should call Vertex Vector Search API.
        For now, we raise if not configured and rely on tests to mock.
        """
        # Implement real upsert here using google.cloud.aiplatform v2 vector search, or REST.
        # We leave as a no-op placeholder to keep unit tests offline.
        if os.getenv("UNIT_TEST", "") == "1":
            return
        # If running for real without an implementation, surface a helpful error
        raise VVSNotConfigured("VertexVectorStore.upsert not implemented in this offline build.")

    def query(self, namespace: str, query_vector: List[float], top_k: int) -> List[Tuple[str, float]]:
        """
        Return list of (id, score). Real implementation should call VVS query.
        """
        if os.getenv("UNIT_TEST", "") == "1":
            return []
        raise VVSNotConfigured("VertexVectorStore.query not implemented in this offline build.")