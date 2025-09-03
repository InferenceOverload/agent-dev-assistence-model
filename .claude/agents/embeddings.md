---
name: embeddings
description: |
  IMPLEMENT CODE: Vertex Text Embeddings client with tests.

  Deliverables:
  1) src/tools/embeddings.py
     - def embed_texts(texts: list[str], dim: int = 1536) -> list[list[float]]:
         Use Vertex Text Embeddings (gemini-embedding-001) with output_dimensionality=dim.
         Batch size 4–8; cap each input to ~8000 tokens equivalent (safe truncation by chars).
         Retry exponential backoff on 429/5xx, up to 5 tries.
         Preserve input order.
     - def embed_query(text: str, dim: int = 1536) -> list[float]:
         Convenience wrapper calling embed_texts([text], dim)[0].

     Implementation notes:
       * Use google-cloud-aiplatform / vertexai SDK if configured; otherwise provide a stub that raises a clear NotConfiguredError.
       * Put a lightweight interface so later we can inject mocks easily.

  2) tests/test_embeddings.py
     - mock embedding calls so tests don't hit network.
     - same text twice -> cosine >= 0.98
     - different texts -> cosine < 0.9
     - batch size variance (1 vs 8) returns aligned shapes

  3) Packaging
     - Ensure imports resolve and tests run offline.

  Process
  - Show diffs; run pytest -q; commit "feat(rag): embeddings client + tests"
tools: Read, Write, Edit, Bash
---