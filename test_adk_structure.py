#!/usr/bin/env python
"""Test ADK structure is correct."""

import sys
import importlib

def test_adk_structure():
    """Verify ADK can find and load our agent."""
    print("Testing ADK Structure")
    print("=" * 40)
    
    # Test 1: Can we import the module?
    try:
        agents_module = importlib.import_module('src.agents')
        print("✓ Module 'src.agents' imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import 'src.agents': {e}")
        return False
    
    # Test 2: Does it have the agent submodule?
    if hasattr(agents_module, 'agent'):
        print("✓ Found 'agent' submodule")
    else:
        print("✗ 'agent' submodule not found")
        return False
    
    # Test 3: Can we access root_agent?
    try:
        from src.agents.agent import root_agent
        print(f"✓ Found root_agent: {root_agent.name}")
        print(f"  Model: {root_agent.model}")
        print(f"  Tools: {len(root_agent.tools)} tools available")
    except ImportError as e:
        print(f"✗ Failed to import root_agent: {e}")
        return False
    except AttributeError as e:
        print(f"✗ root_agent is not an Agent instance: {e}")
        return False
    
    print("\n" + "=" * 40)
    print("✓ ADK structure is correct!")
    print("\nYou can now run:")
    print("  adk web src.agents")
    print("  adk run src.agents")
    return True

if __name__ == "__main__":
    success = test_adk_structure()
    sys.exit(0 if success else 1)