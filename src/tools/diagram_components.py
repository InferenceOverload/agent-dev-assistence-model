"""Generate Mermaid component diagrams from RepoFacts."""

from __future__ import annotations
from typing import List
from src.analysis.models import RepoFacts, Component, Relation


def mermaid_components(facts: RepoFacts) -> str:
    """
    Generate a Mermaid component diagram from RepoFacts.
    
    Args:
        facts: Repository facts with components and relations
        
    Returns:
        Mermaid diagram string (graph LR format)
    """
    if not facts or not facts.components:
        return "graph LR;\n  NoComponents[No components detected];"
    
    lines = ["graph LR"]
    
    # Define component nodes with styling based on type
    for comp in facts.components:
        node_id = _sanitize_id(comp.name)
        label = f"{comp.name}<br/>[{comp.language}]<br/>{comp.files_count} files"
        
        # Style based on component type
        if comp.type == "ui":
            lines.append(f"  {node_id}[\"{label}\"]:::ui")
        elif comp.type == "service":
            lines.append(f"  {node_id}[{label}]:::service")
        elif comp.type == "database":
            lines.append(f"  {node_id}[({label})]:::database")
        elif comp.type == "infra":
            lines.append(f"  {node_id}[/{label}/]:::infra")
        elif comp.type == "library":
            lines.append(f"  {node_id}[{{{label}}}]:::library")
        else:
            lines.append(f"  {node_id}[{label}]")
    
    # Add relations with styled arrows based on type
    for rel in facts.relations:
        source_id = _sanitize_id(rel.source)
        target_id = _sanitize_id(rel.target)
        
        # Style arrows based on relation type
        if rel.type == "calls":
            lines.append(f"  {source_id} -->|calls| {target_id}")
        elif rel.type == "queries":
            lines.append(f"  {source_id} ==>|queries| {target_id}")
        elif rel.type == "imports":
            lines.append(f"  {source_id} -.->|imports| {target_id}")
        elif rel.type == "deploys":
            lines.append(f"  {source_id} -.-|deploys| {target_id}")
        elif rel.type == "tests":
            lines.append(f"  {source_id} -.->|tests| {target_id}")
        else:
            lines.append(f"  {source_id} --> {target_id}")
    
    # Add metadata section if present
    if facts.frameworks or facts.databases:
        lines.append("")
        lines.append("  %% Metadata")
        if facts.frameworks:
            lines.append(f"  %% Frameworks: {', '.join(facts.frameworks)}")
        if facts.databases:
            lines.append(f"  %% Databases: {', '.join(facts.databases)}")
        if facts.deploy_targets:
            lines.append(f"  %% Deploy: {', '.join(facts.deploy_targets)}")
    
    # Add styling classes
    lines.extend([
        "",
        "  %% Styling",
        "  classDef ui fill:#e1f5fe,stroke:#01579b,stroke-width:2px;",
        "  classDef service fill:#fff3e0,stroke:#e65100,stroke-width:2px;",
        "  classDef database fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;",
        "  classDef infra fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;",
        "  classDef library fill:#fce4ec,stroke:#880e4f,stroke-width:2px;"
    ])
    
    return "\n".join(lines) + ";"


def _sanitize_id(name: str) -> str:
    """Sanitize component name for Mermaid node ID."""
    return name.replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "_")