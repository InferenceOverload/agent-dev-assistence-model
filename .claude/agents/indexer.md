---
name: indexer
description: |
  IMPLEMENT CODE: Indexer agent to embed chunks (in-memory) and build session retriever, with tests.

  Deliverables

  1) src/agents/indexer.py
     - from typing import Dict, Tuple
     - from pydantic import BaseModel
     - from src.core.types import Chunk, CodeMap
     - from src.core.policy import VectorizationDecision
     - from src.tools.embeddings import embed_texts
     - from src.tools.retrieval import build_retriever, Retriever

     - class SessionIndex(BaseModel):
         """In-memory registry of Retrievers per session_id (ephemeral)."""
         registries: Dict[str, Retriever] = {}

         @classmethod
         def put(cls, session_id: str, retriever: Retriever) -> None: ...
         @classmethod
         def get(cls, session_id: str) -> Retriever | None: ...
         @classmethod
         def drop(cls, session_id: str) -> None: ...

     - def index_repo(
           session_id: str,
           code_map: CodeMap,
           chunks: list[Chunk],
           decision: VectorizationDecision,
           embed_dim: int = 1536
       ) -> dict:
         """
         - For now we ALWAYS compute in-memory embeddings for simplicity
           (policy 'backend' only controls Vertex Vector Search, which we haven't wired yet).
         - texts = [c.text for c in chunks]
         - vectors = embed_texts(texts, dim=embed_dim)
         - retriever = build_retriever(chunks, vectors, code_map)
         - SessionIndex.put(session_id, retriever)
         - Return { "session_id": ..., "vector_count": len(vectors), "backend": ("in_memory" or decision.backend) }
         """

  2) tests/test_indexer.py
     - Build a few synthetic Chunk objects + CodeMap
     - Monkeypatch src.tools.embeddings.embed_texts to return deterministic small vectors
     - Call index_repo(...) and SessionIndex.get(...) and assert retriever.search(...) returns a hit

  Process
  - Show diffs; run pytest -q; commit "feat(index): session indexer builds in-memory retriever"
tools: Read, Write, Edit, Bash
---