from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Sequence
from pydantic import BaseModel
from .types import Chunk, CodeMap

# --- Session store contracts ---
class SessionStore(ABC):
    @abstractmethod
    def put_retriever(self, session_id: str, retriever: Any) -> None: ...
    @abstractmethod
    def get_retriever(self, session_id: str) -> Any | None: ...
    @abstractmethod
    def drop(self, session_id: str) -> None: ...

class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._reg: dict[str, Any] = {}
    def put_retriever(self, session_id: str, retriever: Any) -> None:
        self._reg[session_id] = retriever
    def get_retriever(self, session_id: str) -> Any | None:
        return self._reg.get(session_id)
    def drop(self, session_id: str) -> None:
        self._reg.pop(session_id, None)

class ADKSessionStore(SessionStore):
    """
    Placeholder adapter for Google ADK SessionService.
    Later: wrap InMemorySessionService/VertexAiSessionService.
    """
    def __init__(self) -> None:
        self._reg: dict[str, Any] = {}  # temporary; replace with ADK calls
    def put_retriever(self, session_id: str, retriever: Any) -> None:
        self._reg[session_id] = retriever
    def get_retriever(self, session_id: str) -> Any | None:
        return self._reg.get(session_id)
    def drop(self, session_id: str) -> None:
        self._reg.pop(session_id, None)

# --- Vector store contracts ---
class VectorStore(ABC):
    @abstractmethod
    def upsert(self, vectors: Sequence[Sequence[float]], chunks: Sequence[Chunk], code_map: CodeMap) -> dict: ...
    @abstractmethod
    def query(self, query_vec: Sequence[float], k: int = 12) -> list[dict]: ...

class InMemoryVectorStore(VectorStore):
    """
    Thin shim around the existing Retriever build path; stores vectors locally.
    """
    def __init__(self) -> None:
        self.vectors: list[list[float]] | None = None
        self.chunks: list[Chunk] | None = None
        self.code_map: CodeMap | None = None
    def upsert(self, vectors, chunks, code_map) -> dict:
        self.vectors = [list(v) for v in vectors]
        self.chunks = list(chunks)
        self.code_map = code_map
        return {"count": len(self.vectors)}
    def query(self, query_vec, k=12) -> list[dict]:
        raise NotImplementedError("Use Retriever.search; VectorStore shim is write-only in-memory")

class VertexVectorStore(VectorStore):
    """
    Placeholder adapter for Vertex Vector Search. Not implemented yet.
    """
    def __init__(self, index_name: str | None = None, endpoint: str | None = None, dim: int = 768) -> None:
        self.index_name = index_name
        self.endpoint = endpoint
        self.dim = dim
    def upsert(self, vectors, chunks, code_map) -> dict:
        raise NotImplementedError("VVS adapter not implemented yet")
    def query(self, query_vec, k=12) -> list[dict]:
        raise NotImplementedError("VVS adapter not implemented yet")

# Factory
class StorageFactory(BaseModel):
    use_vertex: bool = False
    dim: int = 768
    _session_store: SessionStore | None = None
    _vector_store: VectorStore | None = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def session_store(self) -> SessionStore:
        if self._session_store is None:
            self._session_store = InMemorySessionStore()
        return self._session_store
    
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = VertexVectorStore(dim=self.dim) if self.use_vertex else InMemoryVectorStore()
        return self._vector_store