---
name: orchestrator
description: |
  IMPLEMENT CODE: Minimal Orchestrator that chains Sizer → Policy → Ingest → Index → RAG, with tests.

  Deliverables

  1) src/agents/orchestrator.py
     - from dataclasses import dataclass
     - from pathlib import Path
     - from src.tools.sizer import measure_repo, SizerReport
     - from src.core.policy import decide_vectorization, VectorizationDecision
     - from src.agents.repo_ingestor import ingest_repo
     - from src.agents.indexer import index_repo, SessionIndex
     - from src.agents.rag_answerer import RAGAnswererAgent
     - class OrchestratorAgent:
         def __init__(self, root: str = ".", session_id: str = "default"):
             self.root = root
             self.session_id = session_id
             self.code_map = None
             self.chunks = None
             self.sizer: SizerReport | None = None
             self.decision: VectorizationDecision | None = None

         def ingest(self) -> dict:
             code_map, chunks = ingest_repo(self.root)
             self.code_map, self.chunks = code_map, chunks
             files = code_map.files
             return {"files": files, "commit": code_map.commit}

         def size_and_decide(self) -> dict:
             # Reuse paths from current code_map if present; else list Source files quickly
             files = self.code_map.files if self.code_map else []
             self.sizer = measure_repo(self.root, files)
             self.decision = decide_vectorization(self.sizer)
             return {
               "sizer": self.sizer.model_dump(),
               "vectorization": {
                  "use_embeddings": self.decision.use_embeddings,
                  "backend": self.decision.backend,
                  "reasons": self.decision.reasons
               }
             }

         def index(self) -> dict:
             assert self.code_map and self.chunks, "Call ingest() first"
             assert self.decision, "Call size_and_decide() first"
             result = index_repo(self.session_id, self.code_map, self.chunks, self.decision)
             return result

         def ask(self, query: str, k: int = 12, write_docs: bool = False) -> dict:
             retriever = SessionIndex.get(self.session_id)
             assert retriever is not None, "Call index() first"
             rag = RAGAnswererAgent(retriever)
             return rag.answer(query, k=k, write_docs=write_docs)

  2) tests/test_orchestrator.py
     - Create a tiny temp repo with 2-3 files (python/js/sql) similar to previous ingest tests
     - Monkeypatch embed_texts to deterministic small vectors
     - OrchestratorAgent(root=temp_dir, session_id="t1")
         .ingest(); .size_and_decide(); .index()
         res = .ask("where is the helper function?")
         - Assert res["sources"] includes one expected file path
         - If write_docs=True, ensure a docs/generated file path is returned

  Process
  - Show diffs; run pytest -q; commit "feat(core): minimal orchestrator chaining size→policy→ingest→index→rag"
tools: Read, Write, Edit, Bash
---