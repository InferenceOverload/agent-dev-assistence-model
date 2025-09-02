"""Indexer agent to embed chunks (in-memory) and build session retriever."""

from typing import Dict, Tuple

from src.core.types import Chunk, CodeMap
from src.core.policy import VectorizationDecision
from src.tools.embeddings import embed_texts
from src.tools.retrieval import HybridRetriever


class SessionIndex:
    """In-memory registry of Retrievers per session_id (ephemeral)."""
    
    registries: Dict[str, HybridRetriever] = {}

    @classmethod
    def put(cls, session_id: str, retriever: HybridRetriever) -> None:
        """Store a retriever for a session.
        
        Args:
            session_id: Session identifier
            retriever: Retriever instance to store
        """
        cls.registries[session_id] = retriever

    @classmethod
    def get(cls, session_id: str) -> HybridRetriever | None:
        """Get a retriever for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Retriever instance or None if not found
        """
        return cls.registries.get(session_id)

    @classmethod
    def drop(cls, session_id: str) -> None:
        """Remove a retriever for a session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in cls.registries:
            del cls.registries[session_id]


def index_repo(
    session_id: str,
    code_map: CodeMap,
    chunks: list[Chunk],
    decision: VectorizationDecision,
    embed_dim: int = 1536
) -> dict:
    """Index repository chunks and build retriever.
    
    Args:
        session_id: Session identifier
        code_map: Repository code map
        chunks: List of code chunks
        decision: Vectorization policy decision
        embed_dim: Embedding dimensionality
        
    Returns:
        Indexing results dictionary
    """
    # For now we ALWAYS compute in-memory embeddings for simplicity
    # (policy 'backend' only controls Vertex Vector Search, which we haven't wired yet)
    
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
    
    # Store in session registry
    SessionIndex.put(session_id, retriever)
    
    return {
        "session_id": session_id,
        "vector_count": len(vectors),
        "backend": decision.backend if decision.use_embeddings else "in_memory"
    }