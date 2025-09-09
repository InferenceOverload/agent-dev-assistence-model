"""Reusable prompts for different languages and frameworks."""

from typing import Dict, Any


# Python prompts
PYTHON_PROMPTS = {
    "fastapi_endpoint": """
Create a FastAPI endpoint following these patterns:
- Use Pydantic models for request/response validation
- Include proper type hints
- Add OpenAPI documentation via docstrings
- Follow RESTful conventions
- Include error handling with HTTPException
- Use dependency injection where appropriate
Context: {context}
""",
    
    "django_view": """
Create a Django view following these patterns:
- Use class-based views when appropriate
- Include proper permission checks
- Add CSRF protection for POST requests
- Use Django ORM for database queries
- Include proper error handling
- Add logging for debugging
Context: {context}
""",
    
    "flask_route": """
Create a Flask route following these patterns:
- Use Flask-RESTful for API endpoints
- Include request validation
- Add proper error responses
- Use Flask blueprints for organization
- Include CORS handling if needed
Context: {context}
""",
    
    "pytest_test": """
Write pytest tests following these patterns:
- Use fixtures for setup/teardown
- Include parametrized tests for multiple cases
- Mock external dependencies
- Assert specific behaviors and edge cases
- Use descriptive test names
Context: {context}
"""
}

# JavaScript/TypeScript prompts
JAVASCRIPT_PROMPTS = {
    "react_component": """
Create a React component following these patterns:
- Use functional components with hooks
- Include PropTypes or TypeScript interfaces
- Follow single responsibility principle
- Add proper error boundaries
- Include accessibility attributes
- Use CSS modules or styled-components for styling
Context: {context}
""",
    
    "express_middleware": """
Create Express middleware following these patterns:
- Handle async operations properly
- Include error handling with next()
- Add request validation
- Log important events
- Follow middleware chain pattern
Context: {context}
""",
    
    "vue_component": """
Create a Vue component following these patterns:
- Use Composition API for Vue 3
- Include proper props validation
- Add emits declaration
- Use scoped styles
- Include lifecycle hooks as needed
Context: {context}
""",
    
    "jest_test": """
Write Jest tests following these patterns:
- Use describe/it blocks for organization
- Mock modules and external dependencies
- Test user interactions for components
- Include snapshot tests where appropriate
- Test async operations properly
Context: {context}
"""
}

# Java prompts
JAVA_PROMPTS = {
    "spring_controller": """
Create a Spring Boot controller following these patterns:
- Use @RestController for REST APIs
- Include proper request mappings
- Add validation with @Valid
- Use ResponseEntity for responses
- Include exception handling with @ExceptionHandler
- Add Swagger documentation
Context: {context}
""",
    
    "spring_service": """
Create a Spring service following these patterns:
- Use @Service annotation
- Include @Transactional for database operations
- Implement proper logging with SLF4J
- Use dependency injection with constructor
- Include proper error handling
Context: {context}
""",
    
    "junit_test": """
Write JUnit tests following these patterns:
- Use JUnit 5 annotations
- Include @BeforeEach for setup
- Mock dependencies with Mockito
- Use assertThat for readable assertions
- Test edge cases and exceptions
Context: {context}
"""
}

# SQL prompts
SQL_PROMPTS = {
    "create_table": """
Create a SQL table following these patterns:
- Include primary key with appropriate type
- Add foreign key constraints
- Include indexes for frequently queried columns
- Add check constraints for data validation
- Include created_at and updated_at timestamps
- Add comments for documentation
Context: {context}
""",
    
    "migration": """
Create a database migration following these patterns:
- Include both UP and DOWN migrations
- Make changes reversible
- Preserve existing data
- Add proper transaction boundaries
- Include migration versioning
Context: {context}
""",
    
    "optimized_query": """
Write an optimized SQL query following these patterns:
- Use appropriate indexes
- Avoid N+1 queries
- Use JOIN instead of subqueries when possible
- Include EXPLAIN plan considerations
- Add query hints if needed
Context: {context}
"""
}

# Go prompts
GO_PROMPTS = {
    "http_handler": """
Create a Go HTTP handler following these patterns:
- Use standard library or popular framework (gin, echo)
- Include proper error handling
- Add request validation
- Use context for cancellation
- Include structured logging
- Return appropriate HTTP status codes
Context: {context}
""",
    
    "go_test": """
Write Go tests following these patterns:
- Use table-driven tests
- Include subtests with t.Run
- Mock interfaces for dependencies
- Test error cases
- Use testify for assertions if available
Context: {context}
"""
}

# Infrastructure prompts
INFRA_PROMPTS = {
    "dockerfile": """
Create a Dockerfile following these patterns:
- Use multi-stage builds for smaller images
- Run as non-root user
- Include health checks
- Minimize layers
- Use specific base image versions
- Add proper labels
Context: {context}
""",
    
    "kubernetes_manifest": """
Create Kubernetes manifests following these patterns:
- Include resource limits and requests
- Add liveness and readiness probes
- Use ConfigMaps and Secrets appropriately
- Include proper labels and selectors
- Add network policies if needed
Context: {context}
""",
    
    "terraform": """
Create Terraform configuration following these patterns:
- Use variables for configuration
- Include proper resource tagging
- Add outputs for important values
- Use data sources for existing resources
- Include proper state management
Context: {context}
"""
}


def get_prompt(language: str, pattern: str, context: Dict[str, Any]) -> str:
    """
    Get a prompt template for a specific language and pattern.
    
    Args:
        language: Programming language (python, javascript, java, sql, go, infra)
        pattern: Specific pattern within the language
        context: Context dictionary to format the prompt
        
    Returns:
        Formatted prompt string
    """
    prompt_map = {
        "python": PYTHON_PROMPTS,
        "javascript": JAVASCRIPT_PROMPTS,
        "typescript": JAVASCRIPT_PROMPTS,
        "java": JAVA_PROMPTS,
        "sql": SQL_PROMPTS,
        "go": GO_PROMPTS,
        "golang": GO_PROMPTS,
        "infra": INFRA_PROMPTS,
        "infrastructure": INFRA_PROMPTS,
    }
    
    language_prompts = prompt_map.get(language.lower(), {})
    prompt_template = language_prompts.get(pattern, "")
    
    if not prompt_template:
        # Fallback to generic prompt
        return f"Create {pattern} for {language} following best practices. Context: {context}"
    
    # Format with context
    try:
        return prompt_template.format(context=context)
    except Exception:
        return prompt_template.replace("{context}", str(context))


def get_review_prompt(code: str, language: str) -> str:
    """
    Get a code review prompt for the given code.
    
    Args:
        code: Code to review
        language: Programming language
        
    Returns:
        Review prompt string
    """
    return f"""
Review this {language} code for:
1. Security vulnerabilities
2. Performance issues
3. Code style and best practices
4. Potential bugs
5. Test coverage gaps

Code:
```{language}
{code}
```

Provide specific, actionable feedback with line numbers where applicable.
"""


def get_refactor_prompt(code: str, language: str, goal: str) -> str:
    """
    Get a refactoring prompt for the given code.
    
    Args:
        code: Code to refactor
        language: Programming language
        goal: Refactoring goal
        
    Returns:
        Refactor prompt string
    """
    return f"""
Refactor this {language} code to {goal}.

Original code:
```{language}
{code}
```

Requirements:
- Maintain existing functionality
- Improve code quality and readability
- Follow {language} best practices
- Add comments explaining significant changes
- Ensure backward compatibility if this is a public API
"""