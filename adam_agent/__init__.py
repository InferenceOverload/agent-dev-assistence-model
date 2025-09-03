"""ADAM Agent package for Google ADK integration."""

from google import adk
from google.adk import Agent
from pydantic import Field
from typing import Dict, Any, Optional
import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.orchestrator import OrchestratorAgent
from src.core.storage import StorageFactory


class AdamRootAgent(Agent):
    """ADAM root agent exposing orchestrator pipeline to ADK web UI."""
    
    name: str = Field(default="adam-orchestrator", description="Agent name")
    model: str = Field(default="gemini-2.0-flash", description="Default model")
    orchestrator: Optional[OrchestratorAgent] = Field(default=None, description="Orchestrator instance")
    
    def __init__(self, **data):
        """Initialize the ADAM root agent."""
        super().__init__(**data)
        # Initialize orchestrator lazily to avoid import issues
        self._init_orchestrator()
    
    def _init_orchestrator(self):
        """Initialize the orchestrator instance."""
        if self.orchestrator is None:
            storage_factory = StorageFactory(use_vertex=False)
            self.orchestrator = OrchestratorAgent(
                root=".",
                session_id="adk-root",
                storage_factory=storage_factory
            )
    
    def process(self, message: str) -> str:
        """
        Process user message: interpret keywords and call appropriate methods.
        
        Args:
            message: User message
            
        Returns:
            Response string
        """
        m = (message or "").lower()
        
        # Check for specific commands
        if "ingest" in m:
            result = self.ingest()
            return f"✅ Ingested {len(result['files'])} files @ commit {result['commit']}"
        
        if "decide" in m or "policy" in m or "size" in m:
            result = self.decide()
            vec = result['vectorization']
            return f"📊 Decision: use_embeddings={vec['use_embeddings']}, backend={vec['backend']}"
        
        if "index" in m:
            result = self.index()
            return f"🔍 Indexed {result['vector_count']} chunks ({result['backend']})"
        
        if "help" in m:
            return self.help()
        
        # Default: treat as a question
        query = message.strip()
        result = self.ask(query=query)
        return result["answer"]
    
    def help(self) -> str:
        """
        Show available commands.
        
        Returns:
            Help text
        """
        return """
Available commands:
• ingest - Ingest repository files
• decide/policy/size - Analyze repo size and decide vectorization strategy  
• index - Build vector index
• ask [question] - Ask questions about the codebase
• help - Show this help message

Or just ask any question about the codebase!
"""
    
    def ingest(self) -> Dict[str, Any]:
        """
        Ingest repository and create code map and chunks.
        
        Returns:
            Ingestion results with files and commit info
        """
        self._init_orchestrator()
        return self.orchestrator.ingest()
    
    def decide(self) -> Dict[str, Any]:
        """
        Size repository and make vectorization decision.
        
        Returns:
            Sizing and decision results
        """
        self._init_orchestrator()
        # Ensure ingest has been called
        if self.orchestrator.code_map is None:
            self.orchestrator.ingest()
        return self.orchestrator.size_and_decide()
    
    def index(self) -> Dict[str, Any]:
        """
        Index chunks and build retriever.
        
        Returns:
            Indexing results
        """
        self._init_orchestrator()
        # Ensure prerequisites
        if self.orchestrator.code_map is None:
            self.orchestrator.ingest()
        if self.orchestrator.decision is None:
            self.orchestrator.size_and_decide()
        return self.orchestrator.index()
    
    def ask(self, query: str, k: int = 12, write_docs: bool = False) -> Dict[str, Any]:
        """
        Ask a query using RAG.
        
        Args:
            query: Query text
            k: Number of results to retrieve
            write_docs: Whether to write documentation
            
        Returns:
            RAG response with answer and sources
        """
        self._init_orchestrator()
        # Ensure full pipeline has run
        if self.orchestrator.code_map is None:
            self.orchestrator.ingest()
        if self.orchestrator.decision is None:
            self.orchestrator.size_and_decide()
        
        # Try to get retriever, index if needed
        try:
            retriever = self.orchestrator.storage_factory.session_store().get_retriever(
                self.orchestrator.session_id
            )
            if retriever is None:
                self.orchestrator.index()
        except:
            self.orchestrator.index()
        
        return self.orchestrator.ask(query, k=k, write_docs=write_docs)


# Create the root agent instance that ADK will use
root_agent = AdamRootAgent()