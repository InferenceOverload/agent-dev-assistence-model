"""Generate Mermaid component diagrams from RepoFacts or Knowledge Graph."""

from __future__ import annotations
from typing import List, Optional, Dict, Set
from src.analysis.models import RepoFacts, Component, Relation
from src.analysis.kg_models import RepoKG, Entity


def mermaid_from_kg(kg: RepoKG, max_nodes: int = 12) -> str:
    """Generate Mermaid component diagram from Knowledge Graph.
    
    Args:
        kg: Repository knowledge graph
        max_nodes: Maximum nodes before collapsing (default 12)
    
    Returns:
        Mermaid diagram string showing components and flows
    """
    if not kg or not kg.entities:
        return "graph LR\n  NoEntities[No entities detected];"
    
    lines = ["graph LR"]
    
    # Group entities by type for potential collapsing
    entity_groups: Dict[str, List[Entity]] = {}
    for entity in kg.entities:
        entity_groups.setdefault(entity.type, []).append(entity)
    
    # Determine if we need to collapse
    total_entities = len(kg.entities)
    collapse = total_entities > max_nodes
    
    if collapse:
        # Show aggregated view by type
        for entity_type, entities in entity_groups.items():
            node_id = f"{entity_type}_group"
            count = len(entities)
            label = f"{entity_type}<br/>({count} items)"
            
            # Style based on type
            if entity_type == "UI":
                lines.append(f'  {node_id}["{label}"]:::ui')
            elif entity_type in ["API", "Service"]:
                lines.append(f'  {node_id}[{label}]:::service')
            elif entity_type in ["Database", "Table", "Cache"]:
                lines.append(f'  {node_id}[({label})]:::database')
            elif entity_type in ["Job", "DAG"]:
                lines.append(f'  {node_id}[/{label}/]:::job')
            elif entity_type in ["Queue", "Topic"]:
                lines.append(f'  {node_id}[{{{label}}}]:::queue')
            elif entity_type in ["Resource", "Module"]:
                lines.append(f'  {node_id}[/{label}/]:::infra')
            else:
                lines.append(f'  {node_id}[{label}]')
        
        # Aggregate relations between types
        type_relations: Set[tuple] = set()
        for rel in kg.relations:
            src_entity = kg.entity_by_name(rel.src)
            dst_entity = kg.entity_by_name(rel.dst)
            if src_entity and dst_entity:
                src_type = f"{src_entity.type}_group"
                dst_type = f"{dst_entity.type}_group"
                if src_type != dst_type:  # Avoid self-loops in collapsed view
                    type_relations.add((src_type, dst_type, rel.kind))
        
        for src_type, dst_type, kind in type_relations:
            lines.append(f'  {src_type} -->|{kind}| {dst_type}')
    
    else:
        # Show individual entities
        for entity in kg.entities:
            node_id = _sanitize_id(entity.name)
            label = entity.name
            if entity.attrs:
                # Add key attributes to label
                if "route" in entity.attrs:
                    label += f"<br/>{entity.attrs['route']}"
                elif "table" in entity.attrs:
                    label += f"<br/>{entity.attrs['table']}"
            
            # Style based on type
            if entity.type == "UI":
                lines.append(f'  {node_id}["{label}"]:::ui')
            elif entity.type in ["API", "Service"]:
                lines.append(f'  {node_id}[{label}]:::service')
            elif entity.type in ["Database", "Table", "Cache"]:
                lines.append(f'  {node_id}[({label})]:::database')
            elif entity.type in ["Job", "DAG"]:
                lines.append(f'  {node_id}[/{label}/]:::job')
            elif entity.type in ["Queue", "Topic"]:
                lines.append(f'  {node_id}[{{{label}}}]:::queue')
            elif entity.type in ["Resource", "Module", "Storage"]:
                lines.append(f'  {node_id}[/{label}/]:::infra')
            else:
                lines.append(f'  {node_id}[{label}]')
        
        # Add relations
        for rel in kg.relations:
            src_id = _sanitize_id(rel.src)
            dst_id = _sanitize_id(rel.dst)
            
            # Style based on relation kind
            if rel.kind == "calls":
                lines.append(f'  {src_id} -->|calls| {dst_id}')
            elif rel.kind in ["reads", "queries"]:
                lines.append(f'  {src_id} ==>|{rel.kind}| {dst_id}')
            elif rel.kind == "writes":
                lines.append(f'  {src_id} ==>|writes| {dst_id}')
            elif rel.kind == "imports":
                lines.append(f'  {src_id} -.->|imports| {dst_id}')
            elif rel.kind in ["produces", "publishes"]:
                lines.append(f'  {src_id} -->|produces| {dst_id}')
            elif rel.kind in ["consumes", "subscribes"]:
                lines.append(f'  {src_id} <--|consumes| {dst_id}')
            elif rel.kind == "deploys":
                lines.append(f'  {src_id} -.-|deploys| {dst_id}')
            else:
                lines.append(f'  {src_id} --> {dst_id}')
    
    # Add styling classes
    lines.extend([
        "",
        "  %% Styling",
        "  classDef ui fill:#e1f5fe,stroke:#01579b,stroke-width:2px;",
        "  classDef service fill:#fff3e0,stroke:#e65100,stroke-width:2px;",
        "  classDef database fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;",
        "  classDef job fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;",
        "  classDef queue fill:#fce4ec,stroke:#880e4f,stroke-width:2px;",
        "  classDef infra fill:#f5f5f5,stroke:#424242,stroke-width:2px;"
    ])
    
    return "\n".join(lines) + ";"


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