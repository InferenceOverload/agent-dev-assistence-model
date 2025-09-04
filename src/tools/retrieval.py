"""Hybrid retrieval with BM25 and vector search."""

from typing import List, Dict, Optional, Any, Tuple
import logging
import re
from collections import defaultdict
from rank_bm25 import BM25Okapi
import numpy as np

from ..core.types import Chunk, RetrievalResult

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retrieval combining BM25 and vector search."""
    
    def __init__(self, embeddings_tool=None, vector_search_tool=None):
        """Initialize retriever.
        
        Args:
            embeddings_tool: Tool for generating embeddings
            vector_search_tool: Tool for vector search (optional)
        """
        self.embeddings = embeddings_tool
        self.vector_search = vector_search_tool
        self.bm25_index: Optional[BM25Okapi] = None
        self.chunks: List[Chunk] = []
        self.vectors: List[List[float]] = []
        self._chunk_id_to_index: Dict[str, int] = {}
        
    def bm25_index_chunks(self, chunks: List[Chunk]) -> None:
        """Build BM25 index from chunks.
        
        Args:
            chunks: List of Chunk objects
        """
        logger.info(f"Building BM25 index for {len(chunks)} chunks")
        self.chunks = chunks
        self._chunk_id_to_index = {chunk.id: i for i, chunk in enumerate(chunks)}
        
        # Tokenize text for BM25
        tokenized_texts = []
        for chunk in chunks:
            # Combine text with symbols and path for better search
            search_text = f"{chunk.text} {' '.join(chunk.symbols)} {chunk.path}"
            tokens = self._tokenize(search_text)
            tokenized_texts.append(tokens)
        
        self.bm25_index = BM25Okapi(tokenized_texts)
        logger.info("BM25 index built successfully")
        
    def ann_index(self, vectors: List[List[float]]) -> None:
        """Build in-memory ANN index from vectors.
        
        Args:
            vectors: List of embedding vectors
        """
        logger.info(f"Building ANN index for {len(vectors)} vectors")
        self.vectors = vectors
        # For simplicity, we store vectors in memory and use cosine similarity
        # For larger datasets, consider using FAISS
        logger.info("ANN index built successfully")
        
    def index_chunks(self, chunks: List[Chunk], vectors: Optional[List[List[float]]] = None) -> None:
        """Index chunks with both BM25 and vector search.
        
        Args:
            chunks: List of Chunk objects
            vectors: Optional pre-computed vectors
        """
        self.bm25_index_chunks(chunks)
        if vectors:
            self.ann_index(vectors)
        
    def search(
        self,
        query_text: str,
        k: int = 12,
        expand_neighbors: bool = True,
        mode: str = "hybrid"  # "hybrid", "bm25", "vector"
    ) -> List[RetrievalResult]:
        """Hybrid search with reciprocal rank fusion.
        
        Args:
            query_text: Search query
            k: Number of results
            expand_neighbors: Whether to include neighbor chunks
            mode: Search mode ("hybrid", "bm25", "vector")
        
        Returns:
            Ranked retrieval results
        """
        if not self.chunks:
            logger.warning("No chunks indexed")
            return []
            
        logger.info(f"Searching for '{query_text}' with mode={mode}, k={k}")
        
        if mode == "bm25":
            return self._bm25_search(query_text, k, expand_neighbors)
        elif mode == "vector":
            return self._vector_search(query_text, k, expand_neighbors)
        else:  # hybrid
            return self._hybrid_search(query_text, k, expand_neighbors)
            
    def _bm25_search(self, query_text: str, k: int, expand_neighbors: bool) -> List[RetrievalResult]:
        """BM25-only search."""
        if not self.bm25_index:
            return []
            
        tokens = self._tokenize(query_text)
        scores = self.bm25_index.get_scores(tokens)
        
        # Get top k results
        top_indices = np.argsort(scores)[::-1][:k * 2]  # Get more for neighbor expansion
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include relevant results
                chunk = self.chunks[idx]
                result = RetrievalResult(
                    chunk_id=chunk.id,
                    path=chunk.path,
                    score=float(scores[idx]),
                    neighbors=chunk.neighbors.copy(),
                    snippet=self._get_snippet(chunk.text, query_text)
                )
                results.append(result)
                
        if expand_neighbors:
            results = self._expand_with_neighbors(results, k)
        
        return results[:k]
        
    def _vector_search(self, query_text: str, k: int, expand_neighbors: bool) -> List[RetrievalResult]:
        """Vector-only search."""
        if not self.vectors or not self.embeddings:
            return []
            
        # Get query embedding
        try:
            query_embedding = self.embeddings.get_embeddings([query_text], dim=len(self.vectors[0]))[0]
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            return []
            
        # Compute cosine similarities
        scores = []
        for vector in self.vectors:
            similarity = self._cosine_similarity(query_embedding, vector)
            scores.append(similarity)
            
        # Get top k results
        top_indices = np.argsort(scores)[::-1][:k * 2]  # Get more for neighbor expansion
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0.1:  # Threshold for relevance
                chunk = self.chunks[idx]
                result = RetrievalResult(
                    chunk_id=chunk.id,
                    path=chunk.path,
                    score=float(scores[idx]),
                    neighbors=chunk.neighbors.copy(),
                    snippet=self._get_snippet(chunk.text, query_text)
                )
                results.append(result)
                
        if expand_neighbors:
            results = self._expand_with_neighbors(results, k)
            
        return results[:k]
        
    def _hybrid_search(self, query_text: str, k: int, expand_neighbors: bool) -> List[RetrievalResult]:
        """Hybrid search combining BM25 and vector search."""
        # Get results from both methods
        bm25_results = self._bm25_search(query_text, k * 2, False)
        vector_results = self._vector_search(query_text, k * 2, False) if self.vectors else []
        
        if not bm25_results and not vector_results:
            return []
            
        # Merge using reciprocal rank fusion
        merged_results = self.reciprocal_rank_fusion(vector_results, bm25_results, k=60)
        
        if expand_neighbors:
            merged_results = self._expand_with_neighbors(merged_results, k)
            
        return merged_results[:k]
        
    def reciprocal_rank_fusion(
        self,
        ann_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
        k: int = 60
    ) -> List[RetrievalResult]:
        """Merge results using reciprocal rank fusion.
        
        Args:
            ann_results: Results from vector search
            bm25_results: Results from BM25
            k: Fusion constant
        
        Returns:
            Merged and re-ranked results
        """
        # Create score maps for each method
        ann_scores = {result.chunk_id: 1.0 / (rank + k) for rank, result in enumerate(ann_results)}
        bm25_scores = {result.chunk_id: 1.0 / (rank + k) for rank, result in enumerate(bm25_results)}
        
        # Collect all unique chunk IDs
        all_chunk_ids = set(ann_scores.keys()) | set(bm25_scores.keys())
        
        # Compute combined scores
        combined_scores = {}
        chunk_objects = {}
        
        # Build chunk lookup
        for result in ann_results + bm25_results:
            chunk_objects[result.chunk_id] = result
            
        for chunk_id in all_chunk_ids:
            rrf_score = ann_scores.get(chunk_id, 0) + bm25_scores.get(chunk_id, 0)
            combined_scores[chunk_id] = rrf_score
            
        # Sort by combined score
        sorted_chunks = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Create final results
        merged_results = []
        for chunk_id, score in sorted_chunks:
            if chunk_id in chunk_objects:
                result = chunk_objects[chunk_id]
                # Update score to RRF score
                result.score = score
                merged_results.append(result)
        
        # Apply filename bonus for likely "overview" files
        def _name_bonus(path: str) -> float:
            low = path.lower()
            if "readme" in low: return 0.08
            if low.endswith(("package.json", "manifest.json")): return 0.05
            if any(n in low for n in ("app.", "main.", "index.")): return 0.04
            return 0.0
        
        for r in merged_results:
            r.score += _name_bonus(r.path)
        
        # Re-sort after applying bonuses
        merged_results.sort(key=lambda x: x.score, reverse=True)
                
        return merged_results
        
    def _expand_with_neighbors(self, results: List[RetrievalResult], target_k: int) -> List[RetrievalResult]:
        """Expand results with neighbor chunks."""
        seen_chunk_ids = {result.chunk_id for result in results}
        expanded_results = results.copy()
        
        # Add neighbor chunks with reduced scores
        for result in results[:target_k // 2]:  # Only expand top half
            for neighbor_id in result.neighbors:
                if neighbor_id not in seen_chunk_ids and len(expanded_results) < target_k * 2:
                    # Find neighbor chunk
                    neighbor_idx = self._chunk_id_to_index.get(neighbor_id)
                    if neighbor_idx is not None:
                        neighbor_chunk = self.chunks[neighbor_idx]
                        neighbor_result = RetrievalResult(
                            chunk_id=neighbor_chunk.id,
                            path=neighbor_chunk.path,
                            score=result.score * 0.5,  # Reduce score for neighbors
                            neighbors=neighbor_chunk.neighbors.copy(),
                            snippet=neighbor_chunk.text[:200] + "..." if len(neighbor_chunk.text) > 200 else neighbor_chunk.text
                        )
                        expanded_results.append(neighbor_result)
                        seen_chunk_ids.add(neighbor_id)
                        
        return expanded_results
        
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25."""
        # Convert to lowercase and split on non-alphanumeric characters
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens
        
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0
            
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return float(np.dot(vec1_np, vec2_np) / (norm1 * norm2))
        
    def _get_snippet(self, text: str, query: str, max_length: int = 200) -> str:
        """Generate a snippet around query matches."""
        query_words = self._tokenize(query)
        text_lower = text.lower()
        
        # Find the first occurrence of any query word
        best_start = 0
        for word in query_words:
            pos = text_lower.find(word)
            if pos != -1:
                # Start snippet a bit before the match
                best_start = max(0, pos - 50)
                break
                
        # Extract snippet
        snippet = text[best_start:best_start + max_length]
        if best_start > 0:
            snippet = "..." + snippet
        if len(text) > best_start + max_length:
            snippet += "..."
            
        return snippet