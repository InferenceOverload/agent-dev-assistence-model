---
name: rag-answerer
description: |
  IMPLEMENT CODE: RAG answering agent that assembles context and generates responses.
  
  Deliverables:
  1) src/agents/rag_answerer.py
     - class RAGAnswerer:
         def __init__(self, retriever: HybridRetriever, model_router: ModelRouter):
             Store retriever and model router.
         def answer(self, query: str, code_map: Optional[CodeMap] = None) -> RAGResponse:
             Retrieve top-k chunks via retriever.search().
             If code_map provided, expand with neighbor chunks.
             Assemble doc pack with chunk texts and metadata.
             Choose model based on token count (fast if <200k, deep otherwise).
             Generate answer with sources.
         def generate_docs(self, topic: str, chunks: list[Chunk]) -> str:
             Generate markdown documentation for a topic using provided chunks.
     
     Implementation notes:
       * RAGResponse: Pydantic model with answer: str, sources: list[str], token_count: int
       * Doc pack format: include path, symbols, imports in chunk headers
       * Token estimation: ~4 chars per token
       * Neighbor expansion: add imports/importers from code_map if available
  
  2) tests/test_rag_answerer.py
     - mock retriever and model router
     - test doc pack assembly includes metadata
     - test model selection based on token count
     - test neighbor expansion when code_map provided
     - test generate_docs produces markdown
  
  3) Packaging
     - Import from src.tools.retrieval, src.services.vertex_models
     - Add RAGResponse to src.core.types if not exists
  
  Process:
  - Show diffs; run pytest -q; commit "feat(rag): answering agent with context assembly"
tools: Read, Write, Edit, Bash
---