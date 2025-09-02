"""Minimal Orchestrator that chains Sizer → Policy → Ingest → Index → RAG."""

from dataclasses import dataclass
from pathlib import Path
from src.tools.sizer import measure_repo, SizerReport
from src.core.policy import decide_vectorization, VectorizationDecision
from src.agents.repo_ingestor import ingest_repo
from src.agents.indexer import index_repo, SessionIndex


class RAGAnswererAgent:
    """Simple RAG answerer that uses a retriever."""
    
    def __init__(self, retriever):
        """Initialize with a retriever.
        
        Args:
            retriever: HybridRetriever instance
        """
        self.retriever = retriever
    
    def answer(self, query: str, k: int = 12, write_docs: bool = False) -> dict:
        """Answer a query using the retriever.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            write_docs: Whether to write documentation
            
        Returns:
            Answer dictionary with sources
        """
        # Search for relevant chunks
        results = self.retriever.search(query, k=k)
        
        if not results:
            return {
                "answer": "No relevant information found.",
                "sources": [],
                "token_count": 0,
                "model_used": "none"
            }
        
        # Extract sources
        sources = [result.path for result in results]
        
        # Simple answer generation (stub for now)
        answer = f"Found {len(results)} relevant code sections. Top match: {results[0].path}"
        if results[0].snippet:
            answer += f"\n\nRelevant code:\n{results[0].snippet}"
        
        response = {
            "answer": answer,
            "sources": sources,
            "token_count": len(answer) // 4,  # Rough estimate
            "model_used": "simple"
        }
        
        # Write docs if requested
        if write_docs:
            docs_path = Path("docs") / "generated" / f"{query.replace(' ', '_')[:50]}.md"
            docs_path.parent.mkdir(parents=True, exist_ok=True)
            docs_content = f"# {query}\n\n{answer}\n\n## Sources\n\n"
            for source in sources:
                docs_content += f"- {source}\n"
            docs_path.write_text(docs_content)
            response["docs_file"] = str(docs_path)
        
        return response


class OrchestratorAgent:
    """Minimal orchestrator that chains the pipeline steps."""
    
    def __init__(self, root: str = ".", session_id: str = "default"):
        """Initialize orchestrator.
        
        Args:
            root: Repository root path
            session_id: Session identifier
        """
        self.root = root
        self.session_id = session_id
        self.code_map = None
        self.chunks = None
        self.sizer: SizerReport | None = None
        self.decision: VectorizationDecision | None = None

    def ingest(self) -> dict:
        """Ingest repository and create code map and chunks.
        
        Returns:
            Ingestion results with files and commit info
        """
        code_map, chunks = ingest_repo(self.root)
        self.code_map, self.chunks = code_map, chunks
        files = code_map.files
        return {"files": files, "commit": code_map.commit}

    def size_and_decide(self) -> dict:
        """Size repository and make vectorization decision.
        
        Returns:
            Sizing and decision results
        """
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
        """Index chunks and build retriever.
        
        Returns:
            Indexing results
        """
        assert self.code_map and self.chunks, "Call ingest() first"
        assert self.decision, "Call size_and_decide() first"
        result = index_repo(self.session_id, self.code_map, self.chunks, self.decision)
        return result

    def ask(self, query: str, k: int = 12, write_docs: bool = False) -> dict:
        """Ask a query using RAG.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            write_docs: Whether to write documentation
            
        Returns:
            RAG response
        """
        retriever = SessionIndex.get(self.session_id)
        assert retriever is not None, "Call index() first"
        rag = RAGAnswererAgent(retriever)
        return rag.answer(query, k=k, write_docs=write_docs)