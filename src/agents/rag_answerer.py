"""RAG answering agent that assembles context and generates responses."""

import asyncio
import logging
from typing import List, Optional, Dict, Any
import re

from ..core.types import Chunk, CodeMap, RAGResponse, RetrievalResult
from ..tools.retrieval import HybridRetriever
from ..services.vertex_models import ModelRouter

logger = logging.getLogger(__name__)


class RAGAnswerer:
    """RAG agent for answering questions using retrieved code context."""
    
    def __init__(self, retriever: HybridRetriever, model_router: ModelRouter):
        """Initialize RAG answerer.
        
        Args:
            retriever: Hybrid retrieval system
            model_router: Model routing for generation
        """
        self.retriever = retriever
        self.model_router = model_router
        
    async def answer(self, query: str, code_map: Optional[CodeMap] = None) -> RAGResponse:
        """Answer a query using retrieved code context.
        
        Args:
            query: User query
            code_map: Optional code map for neighbor expansion
            
        Returns:
            RAG response with answer and metadata
        """
        logger.info(f"Answering query: {query[:100]}...")
        
        # Retrieve relevant chunks
        retrieval_results = self.retriever.search(query, k=12, expand_neighbors=bool(code_map))
        
        if not retrieval_results:
            return RAGResponse(
                answer="I couldn't find relevant information in the codebase to answer your question.",
                sources=[],
                token_count=0,
                chunks_used=[],
                model_used="none"
            )
        
        # Expand with neighbors if code_map provided
        if code_map:
            retrieval_results = self._expand_with_code_map_neighbors(
                retrieval_results, code_map, max_neighbors=6
            )
        
        # Get chunks for context assembly
        chunks = self._get_chunks_from_results(retrieval_results)
        
        # Assemble doc pack
        doc_pack = self._assemble_doc_pack(chunks, query)
        
        # Estimate token count (rough estimate: ~4 chars per token)
        token_count = len(doc_pack) // 4
        
        # Choose model based on token count
        if token_count > 200000:
            model = self.model_router.llm_long_context()
            model_name = "gemini-1.5-pro-long-context"
        elif token_count > 50000:
            model = self.model_router.llm_deep()
            model_name = "gemini-1.5-pro"
        else:
            model = self.model_router.llm_fast()
            model_name = "gemini-2.0-flash"
            
        logger.info(f"Using model {model_name} for {token_count} tokens")
        
        # Generate answer
        prompt = self._build_answer_prompt(query, doc_pack)
        
        try:
            answer = await self.model_router.generate_content(
                model, prompt, temperature=0.1, max_tokens=4096
            )
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            return RAGResponse(
                answer=f"Sorry, I encountered an error while generating the answer: {str(e)}",
                sources=[],
                token_count=token_count,
                chunks_used=[],
                model_used=model_name
            )
        
        # Extract sources and chunks used
        sources = list(set(chunk.path for chunk in chunks))
        chunks_used = [chunk.id for chunk in chunks]
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            token_count=token_count,
            chunks_used=chunks_used,
            model_used=model_name
        )
    
    async def generate_docs(self, topic: str, chunks: List[Chunk]) -> str:
        """Generate markdown documentation for a topic using provided chunks.
        
        Args:
            topic: Documentation topic
            chunks: Relevant code chunks
            
        Returns:
            Generated markdown documentation
        """
        logger.info(f"Generating docs for topic: {topic}")
        
        if not chunks:
            return f"# {topic}\n\nNo relevant code found for this topic."
        
        # Assemble documentation context
        doc_context = self._assemble_doc_pack(chunks, topic, for_docs=True)
        
        # Build documentation prompt
        prompt = self._build_docs_prompt(topic, doc_context)
        
        # Use deep model for documentation generation
        model = self.model_router.llm_deep()
        
        try:
            docs = await self.model_router.generate_content(
                model, prompt, temperature=0.2, max_tokens=8192
            )
            return docs
        except Exception as e:
            logger.error(f"Failed to generate docs: {e}")
            return f"# {topic}\n\nError generating documentation: {str(e)}"
    
    def _expand_with_code_map_neighbors(
        self,
        results: List[RetrievalResult],
        code_map: CodeMap,
        max_neighbors: int = 6
    ) -> List[RetrievalResult]:
        """Expand results with neighbors from code map.
        
        Args:
            results: Initial retrieval results
            code_map: Code map with dependency information
            max_neighbors: Maximum neighbors to add
            
        Returns:
            Expanded results with neighbors
        """
        expanded_results = results.copy()
        added_neighbors = 0
        seen_paths = {r.path for r in results}
        
        for result in results[:max_neighbors]:  # Only expand top results
            if added_neighbors >= max_neighbors:
                break
                
            # Get file dependencies and importers
            file_path = result.path
            dependencies = code_map.deps.get(file_path, [])
            
            # Find importers (reverse lookup)
            importers = [
                path for path, deps in code_map.deps.items()
                if file_path in deps and path != file_path
            ]
            
            # Add neighbors from both dependencies and importers
            neighbor_paths = (dependencies + importers)[:max_neighbors - added_neighbors]
            
            for neighbor_path in neighbor_paths:
                if neighbor_path not in seen_paths:
                    # Create a neighbor result with reduced score
                    neighbor_result = RetrievalResult(
                        chunk_id=f"neighbor_{neighbor_path.replace('/', '_')}",
                        path=neighbor_path,
                        score=result.score * 0.3,  # Reduced score for neighbors
                        neighbors=[],
                        snippet=f"Dependency of {file_path}"
                    )
                    expanded_results.append(neighbor_result)
                    seen_paths.add(neighbor_path)
                    added_neighbors += 1
                    
                    if added_neighbors >= max_neighbors:
                        break
        
        return expanded_results
    
    def _get_chunks_from_results(self, results: List[RetrievalResult]) -> List[Chunk]:
        """Get chunk objects from retrieval results.
        
        Args:
            results: Retrieval results
            
        Returns:
            List of chunk objects
        """
        chunks = []
        for result in results:
            # Find chunk in retriever's chunks
            for chunk in self.retriever.chunks:
                if chunk.id == result.chunk_id:
                    chunks.append(chunk)
                    break
        
        return chunks
    
    def _assemble_doc_pack(self, chunks: List[Chunk], query: str, for_docs: bool = False) -> str:
        """Assemble chunks into a structured document pack.
        
        Args:
            chunks: List of relevant chunks
            query: Original query for context
            for_docs: Whether assembling for documentation generation
            
        Returns:
            Formatted document pack
        """
        if not chunks:
            return ""
        
        # Group chunks by file
        files = {}
        for chunk in chunks:
            if chunk.path not in files:
                files[chunk.path] = []
            files[chunk.path].append(chunk)
        
        # Build document pack
        doc_parts = []
        
        if for_docs:
            doc_parts.append(f"# Code Context for: {query}\n")
        else:
            doc_parts.append(f"# Relevant Code Context\n")
            doc_parts.append(f"Query: {query}\n")
        
        for file_path, file_chunks in files.items():
            doc_parts.append(f"\n## File: {file_path}\n")
            
            # Sort chunks by line number
            file_chunks.sort(key=lambda c: c.start_line)
            
            for chunk in file_chunks:
                doc_parts.append(f"\n### Lines {chunk.start_line}-{chunk.end_line}")
                
                # Add metadata
                if chunk.symbols:
                    doc_parts.append(f"**Symbols:** {', '.join(chunk.symbols)}")
                if chunk.imports:
                    doc_parts.append(f"**Imports:** {', '.join(chunk.imports)}")
                
                doc_parts.append("```" + chunk.lang)
                doc_parts.append(chunk.text)
                doc_parts.append("```\n")
        
        return "\n".join(doc_parts)
    
    def _build_answer_prompt(self, query: str, doc_pack: str) -> str:
        """Build prompt for answer generation.
        
        Args:
            query: User query
            doc_pack: Assembled document context
            
        Returns:
            Formatted prompt
        """
        return f"""You are an expert software engineer helping to understand a codebase. 
Answer the user's question based on the provided code context.

Be specific and cite relevant code sections. If the context doesn't contain enough 
information to fully answer the question, say so clearly.

Format your answer with:
1. A clear, direct answer
2. Relevant code examples or references
3. Any important caveats or additional context

User Question: {query}

Code Context:
{doc_pack}

Answer:"""

    def _build_docs_prompt(self, topic: str, doc_context: str) -> str:
        """Build prompt for documentation generation.
        
        Args:
            topic: Documentation topic
            doc_context: Code context for documentation
            
        Returns:
            Formatted prompt
        """
        return f"""You are a technical documentation expert. Generate comprehensive markdown 
documentation for the given topic based on the provided code context.

The documentation should include:
1. Clear overview and purpose
2. Key components and their roles  
3. Usage examples where applicable
4. Important implementation details
5. Dependencies and relationships

Topic: {topic}

Code Context:
{doc_context}

Generate well-structured markdown documentation:"""