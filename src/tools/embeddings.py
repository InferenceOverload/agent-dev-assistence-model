"""Vertex AI Text Embeddings client."""

from typing import List
import time
import random
import logging
import os
from math import ceil

logger = logging.getLogger(__name__)


class NotConfiguredError(Exception):
    """Raised when Vertex AI is not properly configured."""
    pass


def _get_vertex_client():
    """Get Vertex AI client with lazy initialization and error handling."""
    try:
        import vertexai
        from vertexai.language_models import TextEmbeddingModel
        
        # Check if we have basic GCP configuration
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise NotConfiguredError(
                "GOOGLE_CLOUD_PROJECT environment variable not set. "
                "Please configure Vertex AI credentials."
            )
        
        # Initialize Vertex AI (this will use default credentials)
        try:
            vertexai.init(project=project_id)
            model = TextEmbeddingModel.from_pretrained("text-embedding-004")
            return model
        except Exception as e:
            raise NotConfiguredError(
                f"Failed to initialize Vertex AI: {e}. "
                "Please check your GCP credentials and project configuration."
            ) from e
    except ImportError as e:
        raise NotConfiguredError(
            f"Vertex AI SDK not available: {e}. "
            "Please install google-cloud-aiplatform and vertexai."
        ) from e


def _truncate_text(text: str, max_chars: int = 8000) -> str:
    """Safely truncate text to avoid token limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(' ', 1)[0]  # Split on word boundary


def embed_texts(texts: List[str], dim: int = 768) -> List[List[float]]:
    """Get embeddings for texts using Vertex AI gemini-embedding-001.
    
    Args:
        texts: List of texts to embed
        dim: Output dimensionality (1-768, default 768)
    
    Returns:
        List of embedding vectors (preserves input order)
        
    Raises:
        NotConfiguredError: If Vertex AI is not properly configured
    """
    if not texts:
        return []
    
    # Validate dimensionality
    if dim < 1 or dim >= 769:
        raise ValueError(f"Invalid dimensionality {dim}. Must be between 1 and 768")
    
    model = _get_vertex_client()
    
    # Truncate texts to safe length
    truncated_texts = [_truncate_text(text) for text in texts]
    
    # Process in batches of 4-8
    batch_size = min(8, max(4, len(texts)))
    all_embeddings = []
    
    for i in range(0, len(truncated_texts), batch_size):
        batch = truncated_texts[i:i + batch_size]
        batch_embeddings = _embed_batch_with_retry(model, batch, dim)
        all_embeddings.extend(batch_embeddings)
    
    return all_embeddings


def embed_query(text: str, dim: int = 768) -> List[float]:
    """Convenience wrapper for embedding a single query text.
    
    Args:
        text: Text to embed
        dim: Output dimensionality
    
    Returns:
        Single embedding vector
        
    Raises:
        NotConfiguredError: If Vertex AI is not properly configured
    """
    embeddings = embed_texts([text], dim)
    return embeddings[0]


def _embed_batch_with_retry(
    model, 
    texts: List[str], 
    dim: int,
    max_retries: int = 5
) -> List[List[float]]:
    """Embed a batch of texts with exponential backoff retry logic.
    
    Args:
        model: Vertex AI TextEmbeddingModel instance
        texts: Batch of texts to embed
        dim: Output dimensionality
        max_retries: Maximum retry attempts
        
    Returns:
        List of embedding vectors for the batch
    """
    for attempt in range(max_retries):
        try:
            # Use the correct model name and parameters for Vertex AI
            embeddings = model.get_embeddings(
                texts,
                output_dimensionality=dim
            )
            
            # Extract vectors from embedding objects
            return [emb.values for emb in embeddings]
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a retryable error
            if any(code in error_str for code in ['429', '500', '502', '503', '504']):
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Retryable error on attempt {attempt + 1}/{max_retries}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)
                    continue
            
            # Non-retryable error or max retries exceeded
            logger.error(f"Failed to get embeddings after {attempt + 1} attempts: {e}")
            raise
    
    raise RuntimeError(f"Failed to get embeddings after {max_retries} retries")