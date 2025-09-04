"""Minimal Orchestrator that chains Sizer → Policy → Ingest → Index → RAG."""

from dataclasses import dataclass
from pathlib import Path
from ..tools.sizer import measure_repo, SizerReport
from ..core.policy import decide_vectorization, VectorizationDecision
from ..core.storage import StorageFactory
from .repo_ingestor import ingest_repo
from .indexer import index_repo


class RAGAnswererAgent:
    """Simple RAG answerer that uses a retriever."""
    
    def __init__(self, retriever):
        """Initialize with a retriever.
        
        Args:
            retriever: HybridRetriever instance
        """
        self.retriever = retriever
    
    def answer(self, query: str, k: int = 50, write_docs: bool = False) -> dict:
        """Answer a query using the retriever.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            write_docs: Whether to write documentation
            
        Returns:
            Answer dictionary with sources
        """
        # Auto-switch to hierarchical for large repos
        try:
            file_count = int(getattr(self.retriever, "meta", {}).get("file_count", 0))
            chunk_count = int(getattr(self.retriever, "meta", {}).get("chunk_count", 0))
        except (TypeError, ValueError):
            file_count = 0
            chunk_count = 0
        status_note = None
        
        if file_count >= 500 or chunk_count >= 6000:
            try:
                from ..tools.embeddings import embed_texts
                results = self.retriever.search_hierarchical(
                    query, 
                    embed_query_fn=lambda xs: embed_texts(xs, dim=768),
                    k=k, k_files=50, k_chunks_per_file=3
                )
                status_note = f"hierarchical: {file_count} files, {chunk_count} chunks → top 50 files, 3 chunks/file"
            except Exception:
                results = self.retriever.search(query, k=k)
        else:
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
        if status_note:
            response["status_note"] = status_note
        
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
    
    def collect(self, query: str, k: int = 50, max_tokens: int = 60000) -> dict:
        """Return only the evidence (doc_pack) for the given query — no answer synthesis.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            max_tokens: Maximum tokens in doc pack
            
        Returns:
            Dictionary with query and doc_pack
        """
        # Auto-switch to hierarchical for large repos
        try:
            file_count = int(getattr(self.retriever, "meta", {}).get("file_count", 0))
            chunk_count = int(getattr(self.retriever, "meta", {}).get("chunk_count", 0))
        except (TypeError, ValueError):
            file_count = 0
            chunk_count = 0
        status_note = None
        
        if file_count >= 500 or chunk_count >= 6000:
            try:
                from ..tools.embeddings import embed_texts
                results = self.retriever.search_hierarchical(
                    query,
                    embed_query_fn=lambda xs: embed_texts(xs, dim=768),
                    k=k, k_files=50, k_chunks_per_file=3
                )
                status_note = f"hierarchical: {file_count} files, {chunk_count} chunks → top 50 files, 3 chunks/file"
            except Exception:
                results = self.retriever.search(query, k=k)
        else:
            results = self.retriever.search(query, k=k)
        
        # Build doc pack from results
        doc_pack = []
        for result in results:
            doc_item = {
                "path": result.path,
                "score": result.score,
                "excerpt": result.snippet if hasattr(result, 'snippet') else ""
            }
            
            # Try to get chunk details if available
            if hasattr(result, 'chunk_id'):
                # Extract line numbers from chunk_id if in format repo:commit:path#start-end
                chunk_id = result.chunk_id
                if '#' in chunk_id:
                    parts = chunk_id.split('#')
                    if len(parts) > 1 and '-' in parts[1]:
                        lines = parts[1].split('-')
                        doc_item["start_line"] = int(lines[0]) if lines[0].isdigit() else 1
                        doc_item["end_line"] = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else doc_item.get("start_line", 1)
            
            doc_pack.append(doc_item)
        
        # Compress doc pack
        doc_pack = self.compress_doc_pack(doc_pack, max_lines=400)
        
        out = {"query": query, "doc_pack": doc_pack}
        if status_note:
            out["status_note"] = status_note
        return out
    
    def compress_doc_pack(self, doc_pack: list, max_lines: int = 400) -> list:
        """Keep excerpts concise for synthesis.
        
        Args:
            doc_pack: List of doc items
            max_lines: Maximum total lines
            
        Returns:
            Compressed doc pack
        """
        if not doc_pack:
            return doc_pack
        MAX_PER = 12
        seen = set()
        total = 0
        out = []
        for d in doc_pack:
            ex = (d.get("excerpt") or "").splitlines()
            key = (d.get("path"), d.get("start_line"), d.get("end_line"), "\n".join(ex[:5]))
            if key in seen:
                continue
            seen.add(key)
            trimmed = "\n".join(ex[:MAX_PER])
            kept = {**d, "excerpt": trimmed}
            lines = len(trimmed.splitlines())
            if total + lines > max_lines:
                break
            total += lines
            out.append(kept)
        return out


class OrchestratorAgent:
    """Minimal orchestrator that chains the pipeline steps."""
    
    def __init__(self, root: str = ".", session_id: str = "default", storage_factory: StorageFactory | None = None):
        """Initialize orchestrator.
        
        Args:
            root: Repository root path
            session_id: Session identifier
            storage_factory: Storage factory for session and vector stores
        """
        self.root = root
        self.session_id = session_id
        self.code_map = None
        self.chunks = None
        self.sizer: SizerReport | None = None
        self.decision: VectorizationDecision | None = None
        self.storage_factory = storage_factory or StorageFactory(use_vertex=False)
    
    def load_repo(self, url: str, ref: str | None = None) -> dict:
        """Clone a repo URL and set as current root; clears previous state."""
        from ..tools.repo_io import clone_repo
        status = ["starting clone…"]
        path = clone_repo(url, ref=ref)
        status.append(f"cloned to {path}")
        # Reset state to new root
        self.root = path
        self.code_map = None
        self.chunks = None
        self.sizer = None
        self.decision = None
        status.append("switched orchestrator root")
        return {"root": path, "status": status}

    def ingest(self) -> dict:
        """Ingest repository and create code map and chunks.
        
        Returns:
            Ingestion results with files and commit info
        """
        status = [f"ingesting repo at {self.root}…"]
        code_map, chunks = ingest_repo(self.root)
        self.code_map, self.chunks = code_map, chunks
        files = code_map.files
        status.append(f"found {len(files)} files @ commit {code_map.commit}")
        return {"files": files, "commit": code_map.commit, "status": status}

    def size_and_decide(self) -> dict:
        """Size repository and make vectorization decision.
        
        Returns:
            Sizing and decision results
        """
        status = ["sizing repo…"]
        # Reuse paths from current code_map if present; else list Source files quickly
        files = self.code_map.files if self.code_map else []
        self.sizer = measure_repo(self.root, files)
        self.decision = decide_vectorization(self.sizer)
        status.append(f"decision: use_embeddings={self.decision.use_embeddings}, backend={self.decision.backend}")
        return {
            "sizer": self.sizer.model_dump(),
            "vectorization": {
                "use_embeddings": self.decision.use_embeddings,
                "backend": self.decision.backend,
                "reasons": self.decision.reasons
            },
            "status": status
        }

    def index(self) -> dict:
        """Index chunks and build retriever.
        
        Returns:
            Indexing results
        """
        assert self.code_map and self.chunks, "Call ingest() first"
        assert self.decision, "Call size_and_decide() first"
        status = ["indexing…"]
        result = index_repo(self.session_id, self.code_map, self.chunks, self.decision, storage_factory=self.storage_factory)
        status.append(f"indexed {result.get('vector_count', 0)} vectors using {result.get('backend')}")
        result["status"] = status
        return result

    def ask(self, query: str, k: int = 50, write_docs: bool = False) -> dict:
        """Ask a query using RAG.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            write_docs: Whether to write documentation
            
        Returns:
            RAG response
        """
        retriever = self.storage_factory.session_store().get_retriever(self.session_id)
        status = [f"answering: {query[:80]}…"]
        if retriever is None:
            status.append("no index found; indexing now…")
            if self.code_map is None:
                self.ingest()
            if self.decision is None:
                self.size_and_decide()
            _ = self.index()
            retriever = self.storage_factory.session_store().get_retriever(self.session_id)
            assert retriever is not None, "Indexing failed"
        
        # If the repo is tiny, expand k to cover all chunks
        try:
            total_chunks = len(self.chunks or [])
            if total_chunks and total_chunks <= 120 and k < total_chunks:
                status.append(f"small repo detected ({total_chunks} chunks) → expanding k to {total_chunks}")
                k = total_chunks
        except Exception:
            pass
        
        rag = RAGAnswererAgent(retriever)
        out = rag.answer(query, k=k, write_docs=write_docs)
        out["status"] = status + ["answer ready"]
        return out
    
    def collect_evidence(self, query: str, k: int = 50) -> dict:
        """Return a doc-pack for a query, using the current retriever.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            
        Returns:
            Dictionary with query, doc_pack and status
        """
        retriever = self.storage_factory.session_store().get_retriever(self.session_id)
        if retriever is None:
            # Auto-index if needed
            if self.code_map is None:
                self.ingest()
            if self.decision is None:
                self.size_and_decide()
            self.index()
            retriever = self.storage_factory.session_store().get_retriever(self.session_id)
            assert retriever is not None, "Indexing failed"
        
        rag = RAGAnswererAgent(retriever)
        out = rag.collect(query=query, k=k)
        out["status"] = [f"collected evidence for: {query[:80]} (k={k})"]
        return out
    
    def repo_synopsis(self) -> dict:
        """Seeded evidence useful for 'what does this app do?'.
        
        Queries: overview, entrypoint, routing/pages, configuration/dependencies.
        
        Returns:
            Dictionary with merged doc_pack and status
        """
        retriever = self.storage_factory.session_store().get_retriever(self.session_id)
        if retriever is None:
            # Auto-index if needed
            if self.code_map is None:
                self.ingest()
            if self.decision is None:
                self.size_and_decide()
            self.index()
            retriever = self.storage_factory.session_store().get_retriever(self.session_id)
            assert retriever is not None, "Indexing failed"
        
        rag = RAGAnswererAgent(retriever)
        seeds = [
            "project overview purpose goals readme",
            "main entry file app startup bootstrapping",
            "routing pages endpoints components controllers",
            "dependencies configuration package json requirements manifest settings",
        ]
        packs, total = [], 0
        for q in seeds:
            ev = rag.collect(query=q, k=40)
            packs.extend(ev.get("doc_pack", []))
            total += len(ev.get("doc_pack", []))
        
        # Remove duplicates based on path
        seen_paths = set()
        unique_packs = []
        for item in packs:
            if item["path"] not in seen_paths:
                seen_paths.add(item["path"])
                unique_packs.append(item)
        
        return {"doc_pack": unique_packs, "status": [f"repo_synopsis collected {total} snippets from {len(seeds)} seeded queries"]}