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
    
    # Extract texts for embedding
    texts = [chunk.text for chunk in chunks]
    
    # Get embeddings
    vectors = embed_texts(texts, dim=embed_dim)
    
    # Build retriever
    retriever = HybridRetriever()
    
    # Index chunks and vectors
    retriever.index_chunks(chunks, vectors)
    
    # Build file-level summaries for hierarchical retrieval
    try:
        retriever.build_file_summaries(lambda xs: embed_texts(xs, dim=embed_dim))
    except Exception:
        pass
    
    # Store retriever in session store
    storage_factory.session_store().put_retriever(session_id, retriever)
    
    # Store vectors in vector store
    storage_factory.vector_store().upsert(vectors, chunks, code_map)
    
    return {
        "session_id": session_id,
        "vector_count": len(vectors),
        "backend": "vertex_vector_search" if storage_factory.use_vertex else "in_memory",
        "file_count": retriever.meta.get("file_count", 0),
        "chunk_count": retriever.meta.get("chunk_count", 0),
    }