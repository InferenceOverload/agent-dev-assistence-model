"""Model router for Vertex AI Gemini models."""

from typing import Optional, List, Dict, Any
import logging
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel

logger = logging.getLogger(__name__)


class ModelRouter:
    """Router for selecting appropriate Gemini models."""
    
    def __init__(self, project: str, location: str = "us-central1"):
        self.project = project
        self.location = location
        aiplatform.init(project=project, location=location)
        
    def llm_fast(self) -> GenerativeModel:
        """Get fast model for routing and tool-heavy work.
        
        Returns:
            gemini-2.0-flash-exp model instance
        """
        return GenerativeModel("gemini-2.0-flash-exp")
        
    def llm_deep(self) -> GenerativeModel:
        """Get deep model for complex reasoning.
        
        Returns:
            gemini-1.5-pro model instance
        """
        return GenerativeModel("gemini-1.5-pro-002")
        
    def llm_long_context(self) -> GenerativeModel:
        """Get long-context model for large documents.
        
        Returns:
            gemini-1.5-pro with extended context
        """
        return GenerativeModel("gemini-1.5-pro-002")
        
    def embedder(self, dim: int = 1536) -> TextEmbeddingModel:
        """Get text embedding model.
        
        Args:
            dim: Output dimensionality (768, 1536, or 3072)
        
        Returns:
            Text embedding model with specified dimensions
        """
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        # Note: output_dimensionality is set during embedding call
        return model
        
    async def generate_content(
        self,
        model: GenerativeModel,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 8192
    ) -> str:
        """Generate content with a model.
        
        Args:
            model: Generative model instance
            prompt: Input prompt
            temperature: Generation temperature
            max_tokens: Maximum output tokens
        
        Returns:
            Generated text
        """
        response = await model.generate_content_async(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
        )
        return response.text