"""Configuration management with environment overrides."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class GCPConfig(BaseModel):
    """GCP configuration."""
    project: str = Field(..., description="GCP project ID")
    location: str = Field(default="us-central1", description="GCP region")
    

class VertexConfig(BaseModel):
    """Vertex AI configuration."""
    fast_model: str = Field(default="gemini-2.0-flash-exp")
    deep_model: str = Field(default="gemini-1.5-pro-002")
    embedding_model: str = Field(default="text-embedding-004")
    embedding_dim: int = Field(default=768)
    

class VectorSearchConfig(BaseModel):
    """Vector search configuration."""
    enabled: bool = Field(default=False)
    index_name: Optional[str] = None
    use_streaming: bool = Field(default=True)
    

class RallyConfig(BaseModel):
    """Rally configuration."""
    api_key: Optional[str] = None
    workspace: Optional[str] = None
    project: Optional[str] = None
    

class GitHubConfig(BaseModel):
    """GitHub configuration."""
    token: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None
    

class SessionConfig(BaseModel):
    """Session configuration."""
    ttl_minutes: int = Field(default=60)
    use_memory_bank: bool = Field(default=False)
    

class AppConfig(BaseModel):
    """Application configuration."""
    gcp: GCPConfig
    vertex: VertexConfig = Field(default_factory=VertexConfig)
    vector_search: VectorSearchConfig = Field(default_factory=VectorSearchConfig)
    rally: RallyConfig = Field(default_factory=RallyConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    

def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from file with environment overrides.
    
    Args:
        config_path: Path to config file (default: configs/app.yaml)
    
    Returns:
        Loaded configuration
    """
    if config_path is None:
        config_path = "configs/app.yaml"
        
    config_dict = {}
    
    # Load from file if exists
    if Path(config_path).exists():
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f) or {}
    
    # Apply environment overrides
    if project := os.getenv("GCP_PROJECT"):
        config_dict.setdefault("gcp", {})["project"] = project
    if location := os.getenv("GCP_LOCATION"):
        config_dict.setdefault("gcp", {})["location"] = location
    if rally_key := os.getenv("RALLY_API_KEY"):
        config_dict.setdefault("rally", {})["api_key"] = rally_key
    if github_token := os.getenv("GITHUB_TOKEN"):
        config_dict.setdefault("github", {})["token"] = github_token
        
    return AppConfig(**config_dict)