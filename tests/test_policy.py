"""Tests for vectorization policy decision engine."""

import pytest

from src.core.policy import VectorizationDecision, decide_vectorization
from src.tools.sizer import SizerReport


def create_minimal_sizer_report(
    loc_total: int = 1000,
    file_count: int = 50,
    vector_count_estimate: int = 100,
    estimated_tokens_repo: int = 10000,
    bytes_total: int = 100000
) -> SizerReport:
    """Create a minimal SizerReport for testing."""
    return SizerReport(
        repo="test-repo",
        commit="abc123",
        file_count=file_count,
        loc_total=loc_total,
        bytes_total=bytes_total,
        lang_breakdown={"python": {"files": file_count, "loc": loc_total}},
        avg_file_loc=loc_total / file_count if file_count > 0 else 0.0,
        max_file_loc=200,
        estimated_tokens_repo=estimated_tokens_repo,
        chunk_estimate=vector_count_estimate,
        vector_count_estimate=vector_count_estimate
    )


class TestVectorizationDecision:
    """Tests for VectorizationDecision model."""
    
    def test_vectorization_decision_creation(self):
        """Test creating a VectorizationDecision."""
        decision = VectorizationDecision(
            use_embeddings=True,
            backend="vertex_vector_search",
            reasons=["Test reason"]
        )
        
        assert decision.use_embeddings is True
        assert decision.backend == "vertex_vector_search"
        assert decision.reasons == ["Test reason"]


class TestDecideVectorization:
    """Tests for decide_vectorization function."""
    
    def test_small_repo_no_embeddings(self):
        """Test that small repositories don't use embeddings."""
        s = create_minimal_sizer_report(
            loc_total=5000,
            file_count=100,
            vector_count_estimate=500,
            estimated_tokens_repo=20000
        )
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is False
        assert decision.backend == "in_memory"
        assert "No embeddings needed for small repository" in decision.reasons
    
    def test_large_loc_triggers_embeddings(self):
        """Test that LOC >= 80,000 triggers embeddings."""
        s = create_minimal_sizer_report(loc_total=80000)
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert "Large codebase: 80,000 LOC >= 80,000 threshold" in decision.reasons
    
    def test_high_file_count_triggers_embeddings(self):
        """Test that file_count >= 1,500 triggers embeddings."""
        s = create_minimal_sizer_report(file_count=1500)
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert "High file count: 1,500 files >= 1,500 threshold" in decision.reasons
    
    def test_high_vector_count_triggers_embeddings(self):
        """Test that vector_count_estimate >= 8,000 triggers embeddings."""
        s = create_minimal_sizer_report(vector_count_estimate=8000)
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert "High vector count: 8,000 vectors >= 8,000 threshold" in decision.reasons
    
    def test_high_token_count_triggers_embeddings(self):
        """Test that estimated_tokens_repo >= 1,500,000 triggers embeddings."""
        s = create_minimal_sizer_report(estimated_tokens_repo=1500000)
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert "High token count: 1,500,000 tokens >= 1,500,000 threshold" in decision.reasons
    
    def test_multiple_embedding_triggers(self):
        """Test that multiple rules can trigger embeddings simultaneously."""
        s = create_minimal_sizer_report(
            loc_total=90000,
            file_count=2000,
            vector_count_estimate=10000,
            estimated_tokens_repo=2000000
        )
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        # All four rules should trigger
        assert len([r for r in decision.reasons if "threshold" in r]) == 4
    
    def test_in_memory_backend_default(self):
        """Test that in_memory is default backend when embeddings are used."""
        s = create_minimal_sizer_report(loc_total=80000)
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert decision.backend == "in_memory"
        assert "Using in-memory backend for manageable size and low concurrency" in decision.reasons
    
    def test_large_vector_count_triggers_vertex(self):
        """Test that vector_count_estimate >= 50,000 triggers Vertex backend."""
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings first
            vector_count_estimate=50000
        )
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert decision.backend == "vertex_vector_search"
        # Updated to match new logic
        assert any("use Vertex Vector Search" in r for r in decision.reasons)
    
    def test_large_bytes_triggers_vertex(self):
        """Test that bytes_total >= 1.5GB triggers Vertex backend."""
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings first
            bytes_total=1500000000  # 1.5GB
        )
        
        decision = decide_vectorization(s)
        
        assert decision.use_embeddings is True
        assert decision.backend == "vertex_vector_search"
        assert "Large repository size: 1,500,000,000 bytes >= 1.5GB requires Vertex" in decision.reasons
    
    def test_high_concurrency_triggers_vertex(self):
        """Test that concurrent_sessions >= 3 + vector_count >= 20,000 triggers Vertex."""
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings first
            vector_count_estimate=20000
        )
        
        decision = decide_vectorization(s, expected_concurrent_sessions=3)
        
        assert decision.use_embeddings is True
        assert decision.backend == "vertex_vector_search"
        assert "High concurrency: 3 sessions + 20,000 vectors requires Vertex" in decision.reasons
    
    def test_high_concurrency_low_vectors_stays_memory(self):
        """Test that very small vector count stays in memory."""
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings first
            vector_count_estimate=5000,  # Below new 10,000 threshold
            file_count=100  # Below 1200 threshold
        )
        
        decision = decide_vectorization(s, expected_concurrent_sessions=5)
        
        assert decision.use_embeddings is True
        assert decision.backend == "in_memory"
        assert "Using in-memory backend for manageable size and low concurrency" in decision.reasons
    
    def test_reuse_across_sessions_triggers_vertex(self):
        """Test that reuse_repo_across_sessions triggers Vertex backend."""
        s = create_minimal_sizer_report(loc_total=80000)  # Trigger embeddings first
        
        decision = decide_vectorization(s, reuse_repo_across_sessions=True)
        
        assert decision.use_embeddings is True
        assert decision.backend == "vertex_vector_search"
        assert "Repository reuse across sessions requires Vertex for persistence" in decision.reasons
    
    def test_multiple_vertex_triggers(self):
        """Test that multiple rules can trigger Vertex backend."""
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings
            vector_count_estimate=60000,  # Trigger large vector count
            bytes_total=2000000000  # Trigger large bytes
        )
        
        decision = decide_vectorization(
            s, 
            expected_concurrent_sessions=4,  # With 60k vectors, triggers concurrency
            reuse_repo_across_sessions=True  # Trigger reuse
        )
        
        assert decision.use_embeddings is True
        assert decision.backend == "vertex_vector_search"
        # Should have multiple Vertex-related reasons
        vertex_reasons = [r for r in decision.reasons if "Vertex" in r or "requires" in r]
        assert len(vertex_reasons) >= 3
    
    def test_edge_case_exact_thresholds(self):
        """Test behavior at exact threshold values."""
        # Test exact LOC threshold
        s = create_minimal_sizer_report(loc_total=80000)
        decision = decide_vectorization(s)
        assert decision.use_embeddings is True
        
        # Test just below threshold
        s = create_minimal_sizer_report(loc_total=79999)
        decision = decide_vectorization(s)
        assert decision.use_embeddings is False
        
        # Test exact vector threshold for Vertex
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings
            vector_count_estimate=50000
        )
        decision = decide_vectorization(s)
        assert decision.backend == "vertex_vector_search"
        
        # Test just below NEW Vertex threshold (10,000)
        s = create_minimal_sizer_report(
            loc_total=80000,  # Trigger embeddings
            vector_count_estimate=9999,  # Just below 10,000 threshold
            file_count=100  # Below 1200 threshold
        )
        decision = decide_vectorization(s)
        assert decision.backend == "in_memory"


if __name__ == "__main__":
    pytest.main([__file__])