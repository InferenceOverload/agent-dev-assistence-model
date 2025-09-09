"""Probe planner for iterative evidence collection."""

from typing import List, Dict, Any
from ..analysis.models import RepoFacts
import logging

logger = logging.getLogger(__name__)


def create_probe_plan(query: str, repo_facts: RepoFacts) -> List[Dict[str, Any]]:
    """
    Analyze query to create specific probes for evidence collection.
    
    Args:
        query: User's question or search query
        repo_facts: Repository analysis facts for context
        
    Returns:
        List of probe objects with search strategies
    """
    probes = []
    query_lower = query.lower()
    
    # Identify query type and needed evidence
    if any(word in query_lower for word in ["authentication", "auth", "login", "security", "jwt", "oauth"]):
        probes.extend([
            {"type": "code_search", "query": "authentication login auth", "expected_files": 10},
            {"type": "symbol_lookup", "query": "authenticate verify_token check_auth", "expected_files": 5},
            {"type": "file_list", "query": "**/auth/**", "expected_files": 5},
            {"type": "code_search", "query": "jwt oauth bearer token", "expected_files": 5},
        ])
    
    elif any(word in query_lower for word in ["database", "db", "sql", "mongo", "redis", "postgres"]):
        probes.extend([
            {"type": "file_list", "query": "**/models/** **/migrations/**", "expected_files": 10},
            {"type": "code_search", "query": "database connection pool query", "expected_files": 8},
            {"type": "symbol_lookup", "query": "Model Schema Table Entity", "expected_files": 5},
            {"type": "code_search", "query": "CREATE TABLE INSERT SELECT UPDATE", "expected_files": 5},
        ])
    
    elif any(word in query_lower for word in ["api", "endpoint", "route", "rest", "graphql"]):
        probes.extend([
            {"type": "file_list", "query": "**/routes/** **/controllers/** **/api/**", "expected_files": 10},
            {"type": "code_search", "query": "app.get app.post router.route @app.route", "expected_files": 8},
            {"type": "symbol_lookup", "query": "Router Controller Handler Resource", "expected_files": 5},
            {"type": "code_search", "query": "request response middleware", "expected_files": 5},
        ])
        
    elif any(word in query_lower for word in ["test", "testing", "unit", "integration", "e2e"]):
        probes.extend([
            {"type": "file_list", "query": "**/test/** **/tests/** **/*test* **/*spec*", "expected_files": 15},
            {"type": "code_search", "query": "describe it test expect assert", "expected_files": 10},
            {"type": "symbol_lookup", "query": "TestCase test_ Test Suite", "expected_files": 5},
        ])
        
    elif any(word in query_lower for word in ["frontend", "ui", "react", "vue", "angular", "component"]):
        probes.extend([
            {"type": "file_list", "query": "**/components/** **/pages/** **/views/**", "expected_files": 10},
            {"type": "code_search", "query": "useState useEffect render Component", "expected_files": 8},
            {"type": "symbol_lookup", "query": "Component Page View Layout", "expected_files": 5},
            {"type": "file_list", "query": "**/*.jsx **/*.tsx **/*.vue", "expected_files": 10},
        ])
        
    elif any(word in query_lower for word in ["config", "configuration", "settings", "environment", "env"]):
        probes.extend([
            {"type": "file_list", "query": "**/config/** *.config.* .env* settings.*", "expected_files": 8},
            {"type": "code_search", "query": "process.env config.get settings environment", "expected_files": 5},
            {"type": "symbol_lookup", "query": "Config Settings Environment", "expected_files": 3},
        ])
        
    elif any(word in query_lower for word in ["deploy", "deployment", "docker", "kubernetes", "ci", "cd"]):
        probes.extend([
            {"type": "file_list", "query": "**/deploy/** Dockerfile* *.yaml *.yml .github/workflows/**", "expected_files": 8},
            {"type": "code_search", "query": "docker build deploy kubernetes helm", "expected_files": 5},
            {"type": "file_list", "query": "docker-compose* k8s/** infra/**", "expected_files": 5},
        ])
    
    # If no specific pattern matched, create generic probes based on query terms
    if not probes:
        # Extract key terms from query (simple tokenization)
        terms = [t for t in query.split() if len(t) > 2 and t.lower() not in 
                 ["the", "how", "what", "does", "where", "when", "why", "this", "that", "with", "for", "and", "are"]]
        
        if terms:
            # Generic search probes
            probes.extend([
                {"type": "code_search", "query": " ".join(terms[:3]), "expected_files": 10},
                {"type": "symbol_lookup", "query": " ".join([t.capitalize() for t in terms[:3]]), "expected_files": 5},
                {"type": "file_list", "query": f"**/*{terms[0]}*", "expected_files": 5},
            ])
        else:
            # Fallback to basic overview probes
            probes.extend([
                {"type": "code_search", "query": query, "expected_files": 10},
                {"type": "file_list", "query": "**/src/** **/lib/**", "expected_files": 10},
            ])
    
    # Add repo-specific context if available
    if repo_facts and repo_facts.frameworks:
        for framework in repo_facts.frameworks[:2]:  # Top 2 frameworks
            probes.append({
                "type": "code_search",
                "query": framework.lower(),
                "expected_files": 5
            })
    
    # Deduplicate probes by query
    seen = set()
    unique_probes = []
    for probe in probes:
        key = (probe["type"], probe["query"])
        if key not in seen:
            seen.add(key)
            unique_probes.append(probe)
    
    logger.info(f"Created {len(unique_probes)} probes for query: {query[:50]}")
    return unique_probes[:5]  # Limit to max 5 probes