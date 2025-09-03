"""Vectorization policy decision engine.

Provides deterministic policy decisions for when to use embeddings and which
vector backend to choose based on repository characteristics and usage patterns.
"""

from typing import List
from pydantic import BaseModel

from ..tools.sizer import SizerReport


class VectorizationDecision(BaseModel):
    """Decision result for vectorization strategy."""
    
    use_embeddings: bool
    backend: str  # "in_memory" | "vertex_vector_search"
    reasons: List[str]


def decide_vectorization(
    s: SizerReport,
    expected_concurrent_sessions: int = 1,
    reuse_repo_across_sessions: bool = False
) -> VectorizationDecision:
    """
    Decide vectorization strategy based on repository size and usage patterns.
    
    Args:
        s: Repository size report containing metrics
        expected_concurrent_sessions: Number of expected concurrent sessions
        reuse_repo_across_sessions: Whether repo will be reused across sessions
        
    Returns:
        VectorizationDecision with strategy and reasoning
        
    Rules:
        A) use_embeddings = True if ANY:
             s.loc_total>=80_000 or s.file_count>=1_500 or
             s.vector_count_estimate>=8_000 or s.estimated_tokens_repo>=1_500_000
        B) backend = "in_memory" unless ANY:
             s.vector_count_estimate>=50_000 or s.bytes_total>=1_500_000_000 or
             (expected_concurrent_sessions>=3 and s.vector_count_estimate>=20_000) or
             reuse_repo_across_sessions
        Append 1-line reasons for each fired rule.
    """
    use_embeddings = False
    backend = "in_memory"
    reasons = []
    
    # Rule A: Decide if embeddings should be used
    if s.loc_total >= 80_000:
        use_embeddings = True
        reasons.append(f"Large codebase: {s.loc_total:,} LOC >= 80,000 threshold")
    
    if s.file_count >= 1_500:
        use_embeddings = True
        reasons.append(f"High file count: {s.file_count:,} files >= 1,500 threshold")
    
    if s.vector_count_estimate >= 8_000:
        use_embeddings = True
        reasons.append(f"High vector count: {s.vector_count_estimate:,} vectors >= 8,000 threshold")
    
    if s.estimated_tokens_repo >= 1_500_000:
        use_embeddings = True
        reasons.append(f"High token count: {s.estimated_tokens_repo:,} tokens >= 1,500,000 threshold")
    
    # If no embeddings needed, skip backend decision
    if not use_embeddings:
        reasons.append("No embeddings needed for small repository")
        return VectorizationDecision(
            use_embeddings=use_embeddings,
            backend=backend,
            reasons=reasons
        )
    
    # Rule B: Decide backend (only if using embeddings)
    if s.vector_count_estimate >= 50_000:
        backend = "vertex_vector_search"
        reasons.append(f"Large vector count: {s.vector_count_estimate:,} vectors >= 50,000 requires Vertex")
    
    if s.bytes_total >= 1_500_000_000:  # ~1.5GB
        backend = "vertex_vector_search" 
        reasons.append(f"Large repository size: {s.bytes_total:,} bytes >= 1.5GB requires Vertex")
    
    if expected_concurrent_sessions >= 3 and s.vector_count_estimate >= 20_000:
        backend = "vertex_vector_search"
        reasons.append(f"High concurrency: {expected_concurrent_sessions} sessions + {s.vector_count_estimate:,} vectors requires Vertex")
    
    if reuse_repo_across_sessions:
        backend = "vertex_vector_search"
        reasons.append("Repository reuse across sessions requires Vertex for persistence")
    
    if backend == "in_memory":
        reasons.append("Using in-memory backend for manageable size and low concurrency")
    
    return VectorizationDecision(
        use_embeddings=use_embeddings,
        backend=backend,
        reasons=reasons
    )