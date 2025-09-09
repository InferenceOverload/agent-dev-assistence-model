"""Tests for task decomposer module."""

import pytest
from src.agents.task_decomposer import decompose_feature_request, _identify_risks
from src.analysis.models import RepoFacts, Component


class TestTaskDecomposer:
    """Test task decomposition functionality."""
    
    def test_api_feature_decomposition(self):
        """Test decomposition of API feature request."""
        requirement = "Add a REST API endpoint for user profile management"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert result["requirement"] == requirement
        assert len(result["design_decisions"]) > 0
        assert any("REST" in decision for decision in result["design_decisions"])
        assert len(result["files_to_modify"]) > 0
        assert any("api" in path.lower() or "route" in path.lower() 
                  for path in result["files_to_modify"])
        assert len(result["tests_needed"]) > 0
        assert result["estimated_effort_hours"] >= 4
    
    def test_ui_feature_decomposition(self):
        """Test decomposition of UI feature request."""
        requirement = "Create a dashboard component with charts and data visualization"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert len(result["design_decisions"]) > 0
        assert any("responsive" in decision.lower() for decision in result["design_decisions"])
        assert len(result["files_to_modify"]) > 0
        assert any("component" in path.lower() for path in result["files_to_modify"])
        assert result["complexity"] in ["low", "medium", "high"]
    
    def test_database_feature_decomposition(self):
        """Test decomposition of database feature request."""
        requirement = "Add database models for order tracking system"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert len(result["design_decisions"]) > 0
        assert any("schema" in decision.lower() for decision in result["design_decisions"])
        assert len(result["files_to_modify"]) > 0
        assert any("model" in path.lower() or "migration" in path.lower() 
                  for path in result["files_to_modify"])
        assert len(result["deployment_steps"]) > 0
        assert any("migration" in step.lower() for step in result["deployment_steps"])
    
    def test_auth_feature_decomposition(self):
        """Test decomposition of authentication feature request."""
        requirement = "Implement JWT-based authentication with refresh tokens"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert len(result["design_decisions"]) > 0
        assert len(result["files_to_modify"]) > 0
        assert any("auth" in path.lower() for path in result["files_to_modify"])
        assert len(result["risks"]) > 0
        assert any("security" in risk.lower() for risk in result["risks"])
    
    def test_integration_feature_decomposition(self):
        """Test decomposition of integration feature request."""
        requirement = "Integrate with third-party payment processing API"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert result["estimated_effort_hours"] >= 8  # Integration adds complexity
        assert len(result["risks"]) > 0
        assert any("external" in risk.lower() or "api" in risk.lower() 
                  for risk in result["risks"])
    
    def test_framework_specific_decisions(self):
        """Test that framework information influences decisions."""
        requirement = "Add a new API endpoint"
        repo_facts = RepoFacts(
            frameworks=["FastAPI", "React"],
            components=[
                Component(name="API", type="service", path="src/api", 
                         language="python", files_count=20)
            ]
        )
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert any("FastAPI" in decision for decision in result["design_decisions"])
        assert any("Pydantic" in decision for decision in result["design_decisions"])
        # Files should adapt to actual component paths
        assert any("src/api" in path for path in result["files_to_modify"])
    
    def test_django_framework_decisions(self):
        """Test Django-specific decomposition."""
        requirement = "Create user management system"
        repo_facts = RepoFacts(frameworks=["Django"])
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert any("Django" in decision for decision in result["design_decisions"])
        assert any("REST Framework" in decision for decision in result["design_decisions"])
    
    def test_complexity_calculation(self):
        """Test complexity calculation based on requirements."""
        simple_req = "Add a simple static page"
        repo_facts = RepoFacts()
        
        simple_result = decompose_feature_request(simple_req, repo_facts)
        assert simple_result["complexity"] == "low"
        assert simple_result["estimated_effort_hours"] <= 6
        
        complex_req = "Build a real-time dashboard with authentication, database integration, and external API webhooks"
        complex_result = decompose_feature_request(complex_req, repo_facts)
        assert complex_result["complexity"] == "high"
        assert complex_result["estimated_effort_hours"] > 10
    
    def test_implementation_phases(self):
        """Test that implementation phases are generated."""
        requirement = "Add user profile feature"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert "implementation_phases" in result
        assert len(result["implementation_phases"]) == 4
        
        phases = result["implementation_phases"]
        assert phases[0]["phase"] == "Setup & Design"
        assert phases[1]["phase"] == "Core Implementation"
        assert phases[2]["phase"] == "Testing & Refinement"
        assert phases[3]["phase"] == "Documentation & Deploy"
        
        # Check effort distribution
        total_effort = sum(p["effort_hours"] for p in phases)
        assert abs(total_effort - result["estimated_effort_hours"]) < 0.1
    
    def test_risk_identification(self):
        """Test risk identification logic."""
        assert len(_identify_risks("simple feature", False, False, False)) == 0
        
        data_risks = _identify_risks("", True, False, False)
        assert len(data_risks) > 0
        assert any("migration" in risk.lower() for risk in data_risks)
        
        auth_risks = _identify_risks("", False, True, False)
        assert len(auth_risks) > 0
        assert any("security" in risk.lower() for risk in auth_risks)
        
        integration_risks = _identify_risks("", False, False, True)
        assert len(integration_risks) > 0
        assert any("external" in risk.lower() for risk in integration_risks)
        
        realtime_risks = _identify_risks("add real-time updates", False, False, False)
        assert any("scalability" in risk.lower() for risk in realtime_risks)
        
        payment_risks = _identify_risks("payment processing", False, False, False)
        assert any("compliance" in risk.lower() for risk in payment_risks)
    
    def test_test_strategy_generation(self):
        """Test that appropriate test strategies are generated."""
        requirement = "Add API endpoint with database integration"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        tests = result["tests_needed"]
        assert len(tests) > 0
        assert any("unit" in test.lower() for test in tests)
        assert any("integration" in test.lower() for test in tests)
    
    def test_deployment_steps_generation(self):
        """Test deployment steps are appropriate."""
        requirement = "Add new feature"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        steps = result["deployment_steps"]
        assert len(steps) > 0
        assert any("lint" in step.lower() for step in steps)
        assert any("test" in step.lower() for step in steps)
        assert any("review" in step.lower() for step in steps)
    
    def test_output_limits(self):
        """Test that outputs are limited to reasonable sizes."""
        requirement = "Complex feature with many aspects"
        repo_facts = RepoFacts()
        
        result = decompose_feature_request(requirement, repo_facts)
        
        assert len(result["design_decisions"]) <= 8
        assert len(result["files_to_modify"]) <= 10
        assert len(result["tests_needed"]) <= 6
        assert len(result["deployment_steps"]) <= 8
        assert len(result["risks"]) <= 4