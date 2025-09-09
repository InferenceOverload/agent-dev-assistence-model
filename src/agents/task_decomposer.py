"""Task decomposer for breaking down feature requests into implementation steps."""

from typing import Dict, List, Any, Optional
from ..analysis.models import RepoFacts
import logging

logger = logging.getLogger(__name__)


def decompose_feature_request(requirement: str, repo_facts: RepoFacts) -> Dict[str, Any]:
    """
    Break down a feature request into structured implementation plan.
    
    Args:
        requirement: Plain text feature requirement
        repo_facts: Repository analysis facts for context
        
    Returns:
        Dictionary with design decisions, files to modify, tests, and deployment steps
    """
    requirement_lower = requirement.lower()
    
    # Analyze requirement type
    is_api = any(word in requirement_lower for word in ["api", "endpoint", "rest", "graphql", "route"])
    is_ui = any(word in requirement_lower for word in ["ui", "frontend", "dashboard", "page", "component", "view"])
    is_data = any(word in requirement_lower for word in ["database", "model", "schema", "migration", "storage"])
    is_auth = any(word in requirement_lower for word in ["auth", "login", "permission", "security", "token"])
    is_integration = any(word in requirement_lower for word in ["integrate", "webhook", "external", "third-party"])
    
    # Base effort calculation (in hours)
    base_effort = 2  # Start with minimal base
    if is_api:
        base_effort += 2
    if is_ui:
        base_effort += 3
    if is_data:
        base_effort += 2
    if is_auth:
        base_effort += 3
    if is_integration:
        base_effort += 4
    
    # Design decisions based on repo context
    design_decisions = []
    
    # Add default design decisions if none from frameworks
    if not design_decisions and not (repo_facts and repo_facts.frameworks):
        design_decisions.append("Follow existing code patterns and conventions")
        design_decisions.append("Ensure proper error handling and logging")
    
    # Framework-specific decisions
    if repo_facts and repo_facts.frameworks:
        for framework in repo_facts.frameworks:
            if "react" in framework.lower():
                design_decisions.append("Use React functional components with hooks")
                design_decisions.append("Follow existing component structure in src/components")
            elif "django" in framework.lower():
                design_decisions.append("Use Django REST Framework for API endpoints")
                design_decisions.append("Create models in appropriate app directory")
            elif "fastapi" in framework.lower():
                design_decisions.append("Use FastAPI with Pydantic models for validation")
                design_decisions.append("Add endpoints to existing routers")
            elif "express" in framework.lower():
                design_decisions.append("Use Express middleware pattern")
                design_decisions.append("Add routes following RESTful conventions")
    
    # General design principles
    if is_api:
        design_decisions.extend([
            "Follow RESTful API design principles",
            "Include proper error handling and status codes",
            "Add request validation and sanitization",
            "Document API endpoints with examples"
        ])
    
    if is_ui:
        design_decisions.extend([
            "Ensure responsive design for mobile/desktop",
            "Follow existing UI/UX patterns in the codebase",
            "Add loading states and error handling",
            "Include accessibility features (ARIA labels, keyboard nav)"
        ])
    
    if is_data:
        design_decisions.extend([
            "Design database schema with proper normalization",
            "Add indexes for query optimization",
            "Include data validation constraints",
            "Plan for data migration if modifying existing schema"
        ])
    
    # Files to modify based on feature type
    files_to_modify = []
    
    if is_api:
        files_to_modify.extend([
            "src/routes/api.py",
            "src/controllers/feature_controller.py",
            "src/middleware/validation.py",
            "tests/api/test_feature_endpoints.py"
        ])
    
    if is_ui:
        files_to_modify.extend([
            "src/components/NewFeature.jsx",
            "src/pages/FeaturePage.jsx",
            "src/styles/feature.css",
            "src/utils/featureHelpers.js",
            "tests/components/NewFeature.test.jsx"
        ])
    
    if is_data:
        files_to_modify.extend([
            "src/models/feature_model.py",
            "migrations/add_feature_tables.sql",
            "src/repositories/feature_repository.py",
            "tests/models/test_feature_model.py"
        ])
    
    if is_auth:
        files_to_modify.extend([
            "src/auth/authentication.py",
            "src/middleware/auth_middleware.py",
            "src/utils/token_handler.py",
            "tests/auth/test_authentication.py"
        ])
    
    # Adapt paths based on repo structure
    if repo_facts and repo_facts.components:
        # Look for actual component paths
        for component in repo_facts.components:
            if component.type == "service" and is_api:
                files_to_modify[0] = f"{component.path}/routes.py"
            elif component.type == "ui" and is_ui:
                files_to_modify[0] = f"{component.path}/components/NewFeature.jsx"
            elif component.type == "database" and is_data:
                files_to_modify[0] = f"{component.path}/models.py"
    
    # Tests needed
    tests_needed = []
    
    if is_api:
        tests_needed.extend([
            "Unit tests for endpoint handlers",
            "Integration tests for API routes",
            "Validation tests for request/response",
            "Performance tests for API endpoints"
        ])
    
    if is_ui:
        tests_needed.extend([
            "Component unit tests",
            "User interaction tests",
            "Visual regression tests",
            "Accessibility tests"
        ])
    
    if is_data:
        tests_needed.extend([
            "Model validation tests",
            "Database query tests",
            "Migration rollback tests",
            "Data integrity tests"
        ])
    
    # Deployment steps
    deployment_steps = [
        "Run linting and formatting checks",
        "Execute full test suite",
        "Update API documentation if applicable",
        "Review code changes in pull request"
    ]
    
    if is_data:
        deployment_steps.insert(0, "Run database migrations in staging")
        deployment_steps.append("Backup database before production deploy")
    
    if is_api:
        deployment_steps.append("Update API version if breaking changes")
        deployment_steps.append("Test API endpoints in staging environment")
    
    if is_ui:
        deployment_steps.append("Build and optimize frontend assets")
        deployment_steps.append("Test UI in multiple browsers")
    
    # Implementation phases
    implementation_phases = []
    
    # Phase 1: Setup and design
    phase1_tasks = ["Review requirements and existing code", "Design technical approach"]
    if is_data:
        phase1_tasks.append("Design database schema")
    if is_api:
        phase1_tasks.append("Define API contract")
    implementation_phases.append({
        "phase": "Setup & Design",
        "tasks": phase1_tasks,
        "effort_hours": base_effort * 0.2
    })
    
    # Phase 2: Core implementation
    phase2_tasks = ["Implement core functionality"]
    if is_data:
        phase2_tasks.append("Create models and migrations")
    if is_api:
        phase2_tasks.append("Implement API endpoints")
    if is_ui:
        phase2_tasks.append("Build UI components")
    implementation_phases.append({
        "phase": "Core Implementation",
        "tasks": phase2_tasks,
        "effort_hours": base_effort * 0.5
    })
    
    # Phase 3: Testing and refinement
    implementation_phases.append({
        "phase": "Testing & Refinement",
        "tasks": ["Write unit tests", "Fix bugs", "Refactor code"],
        "effort_hours": base_effort * 0.2
    })
    
    # Phase 4: Documentation and deployment
    implementation_phases.append({
        "phase": "Documentation & Deploy",
        "tasks": ["Update documentation", "Create PR", "Deploy to staging"],
        "effort_hours": base_effort * 0.1
    })
    
    return {
        "requirement": requirement,
        "design_decisions": design_decisions[:8],  # Limit to 8 most relevant
        "files_to_modify": files_to_modify[:10],  # Limit to 10 files
        "tests_needed": tests_needed[:6],  # Limit to 6 test types
        "deployment_steps": deployment_steps[:8],  # Limit to 8 steps
        "implementation_phases": implementation_phases,
        "estimated_effort_hours": base_effort,
        "complexity": "high" if base_effort > 10 else "medium" if base_effort > 5 else "low",
        "risks": _identify_risks(requirement_lower, is_data, is_auth, is_integration)
    }


def _identify_risks(requirement: str, is_data: bool, is_auth: bool, is_integration: bool) -> List[str]:
    """Identify potential risks in the implementation."""
    risks = []
    
    if is_data:
        risks.append("Data migration complexity if schema changes affect existing data")
        risks.append("Performance impact on database queries")
    
    if is_auth:
        risks.append("Security vulnerabilities if not properly implemented")
        risks.append("Session management complexity")
    
    if is_integration:
        risks.append("External API reliability and rate limits")
        risks.append("Data synchronization challenges")
    
    if "real-time" in requirement or "websocket" in requirement:
        risks.append("Scalability concerns with real-time features")
    
    if "payment" in requirement or "billing" in requirement:
        risks.append("Payment processing compliance requirements")
    
    return risks[:4]  # Limit to top 4 risks