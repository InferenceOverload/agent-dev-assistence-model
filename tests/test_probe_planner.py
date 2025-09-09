"""Tests for probe planner module."""

import pytest
from src.agents.probe_planner import create_probe_plan
from src.analysis.models import RepoFacts, Component


class TestProbePlanner:
    """Test probe planning functionality."""
    
    def test_auth_query_creates_auth_probes(self):
        """Test that authentication queries generate appropriate probes."""
        query = "How does authentication work in this system?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any(p["type"] == "code_search" for p in probes)
        assert any("auth" in p["query"].lower() for p in probes)
        assert any("jwt" in p["query"].lower() or "oauth" in p["query"].lower() for p in probes)
    
    def test_database_query_creates_db_probes(self):
        """Test that database queries generate appropriate probes."""
        query = "What database models are used?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any("model" in p["query"].lower() for p in probes)
        assert any(p["type"] == "file_list" for p in probes)
    
    def test_api_query_creates_endpoint_probes(self):
        """Test that API queries generate endpoint probes."""
        query = "What API endpoints are available?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any("route" in p["query"].lower() or "endpoint" in p["query"].lower() for p in probes)
        assert any(p["type"] == "file_list" and "**/api/**" in p["query"] for p in probes)
    
    def test_frontend_query_creates_ui_probes(self):
        """Test that frontend queries generate UI probes."""
        query = "How is the React frontend structured?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any("component" in p["query"].lower() for p in probes)
        assert any("**/*.jsx" in p["query"] or "**/*.tsx" in p["query"] for p in probes)
    
    def test_testing_query_creates_test_probes(self):
        """Test that testing queries generate test probes."""
        query = "What tests exist for this codebase?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any("test" in p["query"].lower() for p in probes)
        assert any("**/test/**" in p["query"] or "**/*test*" in p["query"] for p in probes)
    
    def test_config_query_creates_config_probes(self):
        """Test that configuration queries generate config probes."""
        query = "How is the application configured?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any("config" in p["query"].lower() or "env" in p["query"].lower() for p in probes)
        assert any(".env" in p["query"] or "config" in p["query"] for p in probes)
    
    def test_deployment_query_creates_deploy_probes(self):
        """Test that deployment queries generate deploy probes."""
        query = "How is this application deployed to Kubernetes?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert any("docker" in p["query"].lower() or "kubernetes" in p["query"].lower() for p in probes)
        assert any("*.yaml" in p["query"] or "Dockerfile" in p["query"] for p in probes)
    
    def test_generic_query_creates_general_probes(self):
        """Test that generic queries create general search probes."""
        query = "explain the main functionality"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        assert probes[0]["type"] in ["code_search", "file_list", "symbol_lookup"]
    
    def test_repo_facts_enhance_probes(self):
        """Test that repo facts enhance probe generation."""
        query = "How does the application work?"
        repo_facts = RepoFacts(
            frameworks=["FastAPI", "React"],
            components=[
                Component(name="API", type="service", path="src/api", language="python", files_count=10)
            ]
        )
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0
        # Should include framework-specific probes
        assert any("fastapi" in p["query"].lower() for p in probes)
        assert any("react" in p["query"].lower() for p in probes)
    
    def test_max_probes_limit(self):
        """Test that probe count is limited."""
        query = "authentication database api frontend testing deployment configuration"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) <= 5  # Should be limited to max 5 probes
    
    def test_probe_deduplication(self):
        """Test that duplicate probes are removed."""
        query = "authentication auth login security authentication"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        # Check for unique probe queries
        probe_keys = [(p["type"], p["query"]) for p in probes]
        assert len(probe_keys) == len(set(probe_keys))
    
    def test_empty_query_handling(self):
        """Test handling of empty or minimal queries."""
        query = ""
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        assert len(probes) > 0  # Should still generate some fallback probes
        assert probes[0]["type"] == "code_search"
    
    def test_probe_expected_files(self):
        """Test that probes have reasonable expected file counts."""
        query = "How does authentication work?"
        repo_facts = RepoFacts()
        
        probes = create_probe_plan(query, repo_facts)
        
        for probe in probes:
            assert "expected_files" in probe
            assert 1 <= probe["expected_files"] <= 15  # Reasonable range