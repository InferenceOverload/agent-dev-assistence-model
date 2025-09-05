"""Generate comprehensive documentation from repository analysis."""

from typing import Literal, List, Dict, Any, Optional
from pathlib import Path
import json
import re

from ..analysis.kg_models import RepoKG
from ..analysis.kg_extract import analyze_repo_kg
from ..core.types import CodeMap
from ..tools.diagram_components import mermaid_from_kg


def generate_docs(
    root: str = ".",
    scope: Literal["full", "setup", "api", "infra"] = "full",
    kg: Optional[RepoKG] = None,
    code_map: Optional[CodeMap] = None
) -> str:
    """Generate high-quality documentation from evidence and KG.
    
    Args:
        root: Repository root path
        scope: Documentation scope (full, setup, api, or infra)
        kg: Optional pre-computed knowledge graph
        code_map: Optional pre-computed code map
    
    Returns:
        Markdown documentation with citations
    """
    # Get KG and code map if not provided
    if not kg or not code_map:
        from ..agents.repo_ingestor import ingest_repo
        code_map, _ = ingest_repo(root)
        kg = analyze_repo_kg(root, code_map)
    
    # Generate sections based on scope
    sections = []
    
    if scope in ["full", "setup"]:
        sections.append(_generate_overview(kg, code_map))
        sections.append(_generate_architecture(kg))
        sections.append(_generate_setup_instructions(root, kg))
    
    if scope in ["full", "api"]:
        sections.append(_generate_api_docs(kg))
    
    if scope in ["full", "infra"]:
        sections.append(_generate_infra_docs(kg))
        sections.append(_generate_db_schema(kg))
    
    if scope == "full":
        sections.append(_generate_config_docs(root, kg))
        sections.append(_generate_gaps(kg))
    
    return "\n\n".join(filter(None, sections))


def _generate_overview(kg: RepoKG, code_map: CodeMap) -> str:
    """Generate overview section."""
    lines = ["# Repository Overview"]
    
    # Count entities by type
    entity_counts = {}
    for entity in kg.entities:
        entity_counts[entity.type] = entity_counts.get(entity.type, 0) + 1
    
    lines.append("\n## Components")
    for entity_type, count in sorted(entity_counts.items()):
        lines.append(f"- **{entity_type}**: {count} components")
    
    lines.append("\n## Technology Stack")
    # Infer tech stack from entities
    frameworks = set()
    for entity in kg.entities:
        if "framework" in entity.attrs:
            frameworks.add(entity.attrs["framework"])
        if "engine" in entity.attrs:
            frameworks.add(entity.attrs["engine"])
        if "orm" in entity.attrs:
            frameworks.add(entity.attrs["orm"])
    
    if frameworks:
        for fw in sorted(frameworks):
            lines.append(f"- {fw}")
    
    # Add file statistics
    lines.append(f"\n## Statistics")
    lines.append(f"- **Files**: {len(code_map.files)}")
    lines.append(f"- **Dependencies**: {len(code_map.deps)}")
    lines.append(f"- **Symbols**: {len(code_map.symbol_index)}")
    
    return "\n".join(lines)


def _generate_architecture(kg: RepoKG) -> str:
    """Generate architecture section with diagram."""
    lines = ["# Architecture"]
    
    # Generate Mermaid diagram
    mermaid = mermaid_from_kg(kg, max_nodes=15)
    
    lines.append("\n```mermaid")
    lines.append(mermaid)
    lines.append("```")
    
    # Describe major components
    lines.append("\n## Component Details")
    
    # Group by type
    by_type = {}
    for entity in kg.entities:
        by_type.setdefault(entity.type, []).append(entity)
    
    for entity_type, entities in sorted(by_type.items()):
        if len(entities) > 0:
            lines.append(f"\n### {entity_type}")
            for entity in entities[:5]:  # Limit to first 5
                citation = f"`{entity.path}`"
                lines.append(f"- **{entity.name}**: {citation}")
                if "route" in entity.attrs:
                    lines.append(f"  - Route: `{entity.attrs['route']}`")
                if "table" in entity.attrs:
                    lines.append(f"  - Table: `{entity.attrs['table']}`")
    
    return "\n".join(lines)


def _generate_setup_instructions(root: str, kg: RepoKG) -> str:
    """Generate setup and run instructions."""
    lines = ["# Setup Instructions"]
    
    # Check for common setup files
    setup_files = []
    root_path = Path(root)
    
    if (root_path / "package.json").exists():
        setup_files.append(("package.json", "npm/yarn"))
    if (root_path / "requirements.txt").exists():
        setup_files.append(("requirements.txt", "pip"))
    if (root_path / "pyproject.toml").exists():
        setup_files.append(("pyproject.toml", "poetry/pip"))
    if (root_path / "go.mod").exists():
        setup_files.append(("go.mod", "go"))
    if (root_path / "pom.xml").exists():
        setup_files.append(("pom.xml", "maven"))
    if (root_path / "build.gradle").exists():
        setup_files.append(("build.gradle", "gradle"))
    
    lines.append("\n## Prerequisites")
    for file, tool in setup_files:
        lines.append(f"- {tool} (`{file}` found)")
    
    lines.append("\n## Installation")
    
    if any("npm" in str(f) for f, _ in setup_files):
        lines.append("```bash\nnpm install\n```")
    if any("pip" in str(f) or "requirements" in str(f) for f, _ in setup_files):
        lines.append("```bash\npip install -r requirements.txt\n```")
    if any("poetry" in str(f) for f, _ in setup_files):
        lines.append("```bash\npoetry install\n```")
    
    # Check for Docker
    if (root_path / "docker-compose.yml").exists() or (root_path / "docker-compose.yaml").exists():
        lines.append("\n## Docker Setup")
        lines.append("```bash\ndocker-compose up\n```")
        lines.append("*Citation: `docker-compose.yml`*")
    
    if (root_path / "Dockerfile").exists():
        lines.append("\n## Container Build")
        lines.append("```bash\ndocker build -t app .\n```")
        lines.append("*Citation: `Dockerfile`*")
    
    return "\n".join(lines)


def _generate_api_docs(kg: RepoKG) -> str:
    """Generate API documentation."""
    lines = ["# API Documentation"]
    
    apis = kg.entities_by_type("API")
    if not apis:
        lines.append("\nNo API endpoints detected.")
        return "\n".join(lines)
    
    lines.append("\n## Endpoints")
    
    # Group by route prefix
    by_prefix = {}
    for api in apis:
        route = api.attrs.get("route", "/")
        prefix = route.split("/")[1] if "/" in route else "root"
        by_prefix.setdefault(prefix, []).append(api)
    
    for prefix, endpoints in sorted(by_prefix.items()):
        lines.append(f"\n### /{prefix}")
        for endpoint in endpoints:
            method = endpoint.attrs.get("method", "GET")
            route = endpoint.attrs.get("route", "/")
            lines.append(f"- `{method} {route}`")
            lines.append(f"  - Implementation: `{endpoint.path}`")
            
            # Check relations for this endpoint
            for rel in kg.relations_from(endpoint.name):
                if rel.kind in ["reads", "writes"]:
                    lines.append(f"  - {rel.kind.title()}: {rel.dst}")
    
    return "\n".join(lines)


def _generate_db_schema(kg: RepoKG) -> str:
    """Generate database schema documentation."""
    lines = ["# Database Schema"]
    
    # Find database entities
    dbs = kg.entities_by_type("Database")
    tables = kg.entities_by_type("Table")
    
    if not dbs and not tables:
        lines.append("\nNo database entities detected.")
        return "\n".join(lines)
    
    if dbs:
        lines.append("\n## Models/Entities")
        for db in dbs:
            orm = db.attrs.get("orm", "Unknown")
            table = db.attrs.get("table", db.name.lower())
            lines.append(f"- **{db.name}** ({orm})")
            lines.append(f"  - Table: `{table}`")
            lines.append(f"  - Source: `{db.path}`")
    
    if tables:
        lines.append("\n## Tables")
        for table in tables:
            ddl_type = table.attrs.get("ddl", "table")
            lines.append(f"- **{table.name}** ({ddl_type})")
            lines.append(f"  - Definition: `{table.path}`")
    
    # Document relationships
    lines.append("\n## Data Flow")
    for entity in dbs + tables:
        # Find who reads/writes this entity
        readers = kg.relations_to(entity.name)
        for rel in readers:
            if rel.kind in ["reads", "writes"]:
                lines.append(f"- {rel.src} → {rel.kind} → {entity.name}")
    
    return "\n".join(lines)


def _generate_infra_docs(kg: RepoKG) -> str:
    """Generate infrastructure documentation."""
    lines = ["# Infrastructure"]
    
    # Find infra entities
    resources = kg.entities_by_type("Resource")
    modules = kg.entities_by_type("Module")
    services = kg.entities_by_type("Service")
    queues = kg.entities_by_type("Queue")
    jobs = kg.entities_by_type("Job")
    
    if resources or modules:
        lines.append("\n## Infrastructure as Code")
        for resource in resources:
            tf_type = resource.attrs.get("tf_type", "resource")
            lines.append(f"- **{resource.name}** (`{tf_type}`)")
            lines.append(f"  - Source: `{resource.path}`")
        
        for module in modules:
            lines.append(f"- Module: **{module.name}**")
            lines.append(f"  - Source: `{module.path}`")
    
    if services:
        lines.append("\n## Services")
        for service in services:
            container = service.attrs.get("container", False)
            ports = service.attrs.get("ports", [])
            lines.append(f"- **{service.name}**")
            if container:
                lines.append(f"  - Type: Container")
            if ports:
                lines.append(f"  - Ports: {', '.join(map(str, ports))}")
            lines.append(f"  - Source: `{service.path}`")
    
    if queues:
        lines.append("\n## Message Queues")
        for queue in queues:
            q_type = queue.attrs.get("type", "Queue")
            role = queue.attrs.get("role", "")
            lines.append(f"- **{queue.name}** ({q_type})")
            if role:
                lines.append(f"  - Role: {role}")
            lines.append(f"  - Source: `{queue.path}`")
    
    if jobs:
        lines.append("\n## Jobs/Tasks")
        for job in jobs:
            engine = job.attrs.get("engine", "")
            orchestrator = job.attrs.get("orchestrator", "")
            lines.append(f"- **{job.name}**")
            if engine:
                lines.append(f"  - Engine: {engine}")
            if orchestrator:
                lines.append(f"  - Orchestrator: {orchestrator}")
            lines.append(f"  - Source: `{job.path}`")
    
    return "\n".join(lines)


def _generate_config_docs(root: str, kg: RepoKG) -> str:
    """Generate configuration documentation."""
    lines = ["# Configuration"]
    
    root_path = Path(root)
    config_files = []
    
    # Check for common config files
    patterns = [
        "*.env*", "config/*.yml", "config/*.yaml", "config/*.json",
        "settings.py", "config.py", "application.properties", "appsettings.json"
    ]
    
    for pattern in patterns:
        for file in root_path.glob(pattern):
            if file.is_file():
                rel_path = file.relative_to(root_path)
                config_files.append(str(rel_path))
    
    if config_files:
        lines.append("\n## Configuration Files")
        for cf in sorted(config_files)[:10]:  # Limit to 10
            lines.append(f"- `{cf}`")
    
    # Environment variables from code
    lines.append("\n## Environment Variables")
    lines.append("*Detected from code analysis:*")
    
    # This would need actual code scanning, so we'll note it as a gap
    lines.append("- See individual service documentation")
    
    return "\n".join(lines)


def _generate_gaps(kg: RepoKG) -> str:
    """Generate documentation gaps and warnings."""
    lines = ["# Documentation Gaps & Notes"]
    
    if kg.warnings:
        lines.append("\n## Extraction Warnings")
        for warning in kg.warnings[:10]:  # Limit warnings
            lines.append(f"- {warning}")
    
    lines.append("\n## Potential Gaps")
    
    # Check for missing common components
    entity_types = {e.type for e in kg.entities}
    
    if "UI" not in entity_types:
        lines.append("- No UI/Frontend components detected")
    if "API" not in entity_types:
        lines.append("- No API endpoints detected")
    if "Database" not in entity_types and "Table" not in entity_types:
        lines.append("- No database entities detected")
    if "Job" not in entity_types:
        lines.append("- No background jobs/tasks detected")
    
    # Check for missing documentation
    lines.append("\n## Missing Documentation")
    lines.append("- README.md (if not present)")
    lines.append("- API documentation/OpenAPI spec")
    lines.append("- Deployment guides")
    lines.append("- Testing instructions")
    
    return "\n".join(lines)