"""Indexer agent to embed chunks (in-memory) and build session retriever."""

from typing import Dict, Tuple

from ..core.types import Chunk, CodeMap
from ..core.policy import VectorizationDecision
from ..core.storage import StorageFactory
from ..tools.embeddings import embed_texts
from ..tools.retrieval import HybridRetriever


def index_repo(
    session_id: str,
    code_map: CodeMap,
    chunks: list[Chunk],
    decision: VectorizationDecision,
    embed_dim: int = 768,
    storage_factory: StorageFactory | None = None
) -> dict:
    """Index repository chunks and build retriever.
    
    Args:
        session_id: Session identifier
        code_map: Repository code map
        chunks: List of code chunks
        decision: Vectorization policy decision
        embed_dim: Embedding dimensionality
        storage_factory: Storage factory for session and vector stores
        
    Returns:
        Indexing results dictionary
    """
    # Use default storage factory if not provided
    if storage_factory is None:
        storage_factory = StorageFactory(use_vertex=False, dim=embed_dim)
    
    if not chunks:
        return {
            "session_id": session_id,
            "vector_count": 0,
            "backend": "in_memory"
        }
    
    # Filter out empty/whitespace chunks before embedding to avoid 400 "text content is empty"
    filtered: list[Chunk] = []
    filtered_texts: list[str] = []
    for c in chunks:
        t = (c.text or "").strip()
        if not t:
            continue
        filtered.append(c)
        filtered_texts.append(c.text)  # Use original text to maintain consistency
    
    if not filtered_texts:
        # No meaningful content; return an index stub
        retriever = HybridRetriever()
        storage_factory.session_store().put_retriever(session_id, retriever)
        return {
            "backend": "vertex_vector_search" if storage_factory.use_vertex else "in_memory",
            "vector_count": 0,
            "session_id": session_id,
            "file_count": len(code_map.files) if code_map and code_map.files else 0,
            "chunk_count": 0,
            "status": ["index: no non-empty chunks; created empty retriever"],
        }
    
    # Build retriever
    retriever = HybridRetriever()
    
    # Get embeddings only if policy says to use them
    vectors = []
    if decision.use_embeddings:
        vectors = embed_texts(filtered_texts, dim=embed_dim)
        # Index chunks with vectors
        retriever.index_chunks(filtered, vectors)
    else:
        # Index chunks without vectors (BM25 only)
        retriever.index_chunks(filtered, None)
    
    # Build file-level summaries for hierarchical retrieval (only if using embeddings)
    if decision.use_embeddings:
        try:
            retriever.build_file_summaries(lambda xs: embed_texts(xs, dim=embed_dim))
        except Exception:
            pass
    
    # --- Vertex Vector Search path ---
    used_vvs = False
    backend = "in_memory"
    if decision.backend == "vertex_vector_search":
        vvs = storage_factory.vvs() if storage_factory else None
        if vvs is not None:
            used_vvs = True
            backend = "vertex_vector_search"
            # namespace per session or commit
            from ..core.config import get_config
            config = get_config()
            if config.vector_search.vvs_namespace_mode == "commit":
                ns = f"{code_map.commit if code_map else session_id}"
            else:
                ns = f"session:{session_id}"
            # upsert in batches
            from ..tools.vvs_store import VVSItem
            batch = config.vector_search.vvs_upsert_batch
            items = []
            for c, v in zip(filtered, vectors):
                cid = getattr(c, "id", None) or f"{c.path}:{c.start_line}:{c.end_line}"
                items.append(VVSItem(id=cid, vector=v, metadata={"path": c.path, "start": c.start_line, "end": c.end_line}))
            for i in range(0, len(items), batch):
                vvs.upsert(ns, items[i:i+batch])
            # wire ANN provider that maps VVS IDs back to chunk indices
            id_to_idx = { (getattr(c, "id", None) or f"{c.path}:{c.start_line}:{c.end_line}") : idx for idx, c in enumerate(filtered) }
            def _ann(qv, topk):
                # VVS returns [(id, score)], map to (chunk_index, score)
                pairs = vvs.query(ns, qv, topk)
                return [(id_to_idx[i], s) for (i, s) in pairs if i in id_to_idx]
            retriever.ann_provider = _ann
    # --- end VVS path ---
    
    # Store retriever in session store
    storage_factory.session_store().put_retriever(session_id, retriever)
    
    # Store vectors in vector store (skip if using VVS or not using embeddings)
    if not used_vvs and decision.use_embeddings and vectors:
        storage_factory.vector_store().upsert(vectors, filtered, code_map)
    
    return {
        "session_id": session_id,
        "vector_count": len(vectors),
        "backend": backend,
        "file_count": retriever.meta.get("file_count", 0),
        "chunk_count": retriever.meta.get("chunk_count", 0),
        "using_vvs": used_vvs,
    }