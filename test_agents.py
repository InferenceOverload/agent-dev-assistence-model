#!/usr/bin/env python
"""Test script for ADK agents."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agents import (
    root_agent,
    orchestrator_agent,
    repo_ingestor_agent,
    rag_answerer_agent
)

def test_agents():
    """Test that agents are properly configured."""
    print("Testing ADK Agent Configuration\n" + "="*40)
    
    # Test orchestrator
    print(f"\n✓ Root Agent: {root_agent.name}")
    print(f"  Model: {root_agent.model}")
    print(f"  Tools: {[tool.__name__ for tool in root_agent.tools]}")
    print(f"  Sub-agents: {[agent.name for agent in orchestrator_agent.sub_agents]}")
    
    # Test individual agents
    agents_to_test = [
        repo_ingestor_agent,
        rag_answerer_agent
    ]
    
    for agent in agents_to_test:
        print(f"\n✓ Agent: {agent.name}")
        print(f"  Model: {agent.model}")
        print(f"  Tools: {[tool.__name__ for tool in agent.tools]}")
    
    print("\n" + "="*40)
    print("All agents configured successfully!")
    print("\nTo run with ADK web interface:")
    print("  1. Copy .env.example to .env and add your API key")
    print("  2. Run: adk web src.agents")
    print("\nTo run in terminal:")
    print("  Run: adk run src.agents")

if __name__ == "__main__":
    test_agents()