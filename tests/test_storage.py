"""Tests for storage adapters."""

import pytest
from src.core.storage import (
    InMemorySessionStore,
    ADKSessionStore, 
    InMemoryVectorStore,
    VertexVectorStore,
    StorageFactory
)
from src.core.types import Chunk, CodeMap


def test_in_memory_session_store():
    """Test InMemorySessionStore put/get/drop roundtrip."""
    store = InMemorySessionStore()
    
    # Test initial state
    assert store.get_retriever("test") is None
    
    # Test put and get
    test_retriever = {"test": "retriever"}  # Mock retriever
    store.put_retriever("test", test_retriever)
    assert store.get_retriever("test") is test_retriever
    
    # Test overwrite
    new_retriever = {"new": "retriever"}
    store.put_retriever("test", new_retriever)
    assert store.get_retriever("test") is new_retriever
    
    # Test drop
    store.drop("test")
    assert store.get_retriever("test") is None
    
    # Test drop non-existent (should not raise)
    store.drop("nonexistent")


def test_adk_session_store():
    """Test ADKSessionStore placeholder functionality."""
    store = ADKSessionStore()
    
    # Should have same behavior as InMemorySessionStore for now
    assert store.get_retriever("test") is None
    
    test_retriever = {"test": "retriever"}
    store.put_retriever("test", test_retriever)
    assert store.get_retriever("test") is test_retriever
    
    store.drop("test")
    assert store.get_retriever("test") is None


def test_in_memory_vector_store():
    """Test InMemoryVectorStore upsert returns correct count."""
    store = InMemoryVectorStore()
    
    # Create test data
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    chunks = [
        Chunk(
            id="test:commit:file1.py#1-10",
            repo="test",
            commit="commit",
            path="file1.py",
            lang="python",
            start_line=1,
            end_line=10,
            text="test code",
            symbols=[],
            imports=[],
            neighbors=[],
            hash="hash1"
        ),
        Chunk(
            id="test:commit:file2.py#1-5",
            repo="test",
            commit="commit", 
            path="file2.py",
            lang="python",
            start_line=1,
            end_line=5,
            text="more code",
            symbols=[],
            imports=[],
            neighbors=[],
            hash="hash2"
        )
    ]
    code_map = CodeMap(
        repo="test",
        commit="commit",
        files=["file1.py", "file2.py"],
        deps={},
        symbol_index={}
    )
    
    # Test upsert
    result = store.upsert(vectors, chunks, code_map)
    assert result["count"] == 2
    
    # Verify data was stored
    assert store.vectors == vectors
    assert store.chunks == chunks
    assert store.code_map == code_map
    
    # Test query (should raise NotImplementedError)
    with pytest.raises(NotImplementedError):
        store.query([0.1, 0.2, 0.3], k=5)


def test_vertex_vector_store():
    """Test VertexVectorStore placeholder functionality."""
    store = VertexVectorStore(index_name="test_index", endpoint="test_endpoint", dim=768)
    
    # Verify initialization
    assert store.index_name == "test_index"
    assert store.endpoint == "test_endpoint"
    assert store.dim == 768
    
    # Test upsert (should raise NotImplementedError)
    with pytest.raises(NotImplementedError):
        store.upsert([], [], CodeMap(repo="test", commit="commit", files=[], deps={}, symbol_index={}))
    
    # Test query (should raise NotImplementedError)
    with pytest.raises(NotImplementedError):
        store.query([0.1, 0.2, 0.3], k=5)


def test_storage_factory():
    """Test StorageFactory creates correct store types."""
    # Test default factory (in-memory)
    factory = StorageFactory(use_vertex=False, dim=768)
    assert factory.use_vertex is False
    assert factory.dim == 768
    
    session_store = factory.session_store()
    assert isinstance(session_store, InMemorySessionStore)
    
    vector_store = factory.vector_store()
    assert isinstance(vector_store, InMemoryVectorStore)
    
    # Test that repeated calls return the same instance
    assert factory.session_store() is session_store
    assert factory.vector_store() is vector_store
    
    # Test vertex factory
    vertex_factory = StorageFactory(use_vertex=True, dim=768)
    assert vertex_factory.use_vertex is True
    assert vertex_factory.dim == 768
    
    vertex_session_store = vertex_factory.session_store()
    assert isinstance(vertex_session_store, InMemorySessionStore)  # Still in-memory for sessions
    
    vertex_vector_store = vertex_factory.vector_store()
    assert isinstance(vertex_vector_store, VertexVectorStore)
    assert vertex_vector_store.dim == 768