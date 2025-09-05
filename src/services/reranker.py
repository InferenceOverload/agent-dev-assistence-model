"""LLM-based passage reranking service for improved retrieval precision."""

import os
from typing import List, Dict, Any
import json


def score_passages(query: str, passages: List[Dict[str, Any]]) -> List[float]:
    """
    Score passages for relevance to a query using an LLM.
    
    Args:
        query: The search query
        passages: List of passage dicts with 'path', 'snippet', and optional 'meta' fields
        
    Returns:
        List of relevance scores (0.0 to 1.0) for each passage
    """
    # Check if reranking is enabled
    if not os.getenv("RERANK_ENABLED", "0") in ("1", "true", "TRUE"):
        # Return uniform scores if disabled (no-op)
        return [0.5] * len(passages)
    
    if not passages:
        return []
    
    try:
        # Import Vertex AI only when needed
        from google.cloud import aiplatform
        from vertexai.generative_models import GenerativeModel
        
        # Initialize Vertex AI (uses ADC)
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        if project:
            aiplatform.init(project=project, location=location)
        
        # Use Gemini Flash for fast reranking
        model = GenerativeModel("gemini-1.5-flash")
        
        # Prepare passages for scoring (cap at 1200 chars each)
        passages_text = []
        for i, p in enumerate(passages):
            snippet = (p.get("snippet", "") or "")[:1200]
            path = p.get("path", "unknown")
            passages_text.append(f"[{i}] {path}\n{snippet}")
        
        # Build the scoring prompt
        prompt = f"""You are a code search relevance scorer. Given a query and code passages, score each passage's relevance from 0.0 to 1.0.

Query: {query}

Passages:
{chr(10).join(passages_text[:20])}  # Cap at 20 passages to avoid token limits

Return ONLY a JSON array of scores in order, one per passage. Example: [0.9, 0.3, 0.7, ...]
Scores should reflect:
- 0.9-1.0: Highly relevant, directly answers the query
- 0.6-0.8: Relevant, contains useful related information
- 0.3-0.5: Somewhat relevant, tangentially related
- 0.0-0.2: Not relevant

JSON scores:"""
        
        # Get response from model
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 500,
            }
        )
        
        # Parse scores from response
        response_text = response.text.strip()
        # Handle potential markdown code blocks
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        
        scores = json.loads(response_text.strip())
        
        # Validate and normalize scores
        if not isinstance(scores, list):
            raise ValueError("Expected list of scores")
        
        # Ensure we have the right number of scores
        if len(scores) < len(passages):
            # Pad with default scores if needed
            scores.extend([0.5] * (len(passages) - len(scores)))
        elif len(scores) > len(passages):
            # Truncate if too many
            scores = scores[:len(passages)]
        
        # Clamp scores to [0.0, 1.0]
        scores = [max(0.0, min(1.0, float(s))) for s in scores]
        
        return scores
        
    except Exception as e:
        # On any error, return uniform scores (fallback to no reranking)
        print(f"Reranking error: {e}")
        return [0.5] * len(passages)