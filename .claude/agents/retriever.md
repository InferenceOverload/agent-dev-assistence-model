---
name: retriever
description: |
  IMPLEMENT CODE: Hybrid retrieval system combining BM25 and vector search.
  
  Deliverables:
  1) src/tools/retrieval.py
     - class HybridRetriever:
         def __init__(self, chunks: list[Chunk], vectors: Optional[np.ndarray] = None):
             Build BM25 index from chunks text; store vectors if provided.
         def search(self, query: str, k: int = 12, embed_fn: Optional[Callable] = None) -> list[RetrievalResult]:
             If vectors exist and embed_fn provided: get ANN candidates (cosine).
             Get BM25 candidates. Merge via reciprocal rank fusion.
             Return scored results with chunk_id, path, score.
     
     Implementation notes:
       * Use rank-bm25 for BM25 indexing
       * For ANN: if vectors provided, use numpy cosine similarity (no FAISS dependency)
       * RRF formula: 1/(k+rank) where k=60 is a good default
       * RetrievalResult should include chunk metadata for expansion
  
  2) tests/test_retrieval.py
     - test hybrid search returns expected chunks
     - test BM25-only mode (no vectors)
     - test vector-only mode (no BM25)
     - test RRF merging preserves top results
     - test with edge cases (empty query, single chunk)
  
  3) Packaging
     - Import Chunk, RetrievalResult from src.core.types
     - Ensure numpy is available for vector operations
  
  Process:
  - Show diffs; run pytest -q; commit "feat(rag): hybrid retrieval system"
tools: Read, Write, Edit, Bash
---