"""Generate Mermaid sequence diagrams from Knowledge Graph."""

from typing import List, Set, Optional
from src.analysis.kg_models import RepoKG, Entity, Relation


def sequence_from_kg(kg: RepoKG, use_case: str) -> str:
    """Generate Mermaid sequence diagram skeleton from KG for a use case.
    
    Args:
        kg: Repository knowledge graph
        use_case: Description of the use case/flow
    
    Returns:
        Mermaid sequence diagram string with actors and services
    """
    if not kg or not kg.entities:
        return "sequenceDiagram\n  Note over User: No entities found for sequence"
    
    lines = ["sequenceDiagram"]
    lines.append(f"  %% Use Case: {use_case}")
    lines.append("")
    
    # Identify actors and participants
    actors: Set[str] = set()
    participants: Set[str] = set()
    
    # UIs are typically actors (user-facing)
    for ui in kg.entities_by_type("UI"):
        actors.add(ui.name)
    
    # APIs and Services are participants
    for api in kg.entities_by_type("API"):
        participants.add(api.name)
    for svc in kg.entities_by_type("Service"):
        participants.add(svc.name)
    
    # Databases and Queues are also participants
    for db in kg.entities_by_type("Database"):
        participants.add(db.name)
    for table in kg.entities_by_type("Table"):
        participants.add(table.name)
    for queue in kg.entities_by_type("Queue"):
        participants.add(queue.name)
    
    # Jobs can be participants if they're part of flows
    for job in kg.entities_by_type("Job"):
        participants.add(job.name)
    
    # If no actors found, add User as default
    if not actors:
        actors.add("User")
    
    # Declare actors and participants
    for actor in sorted(actors):
        lines.append(f"  actor {_sanitize_id(actor)}")
    for participant in sorted(participants):
        lines.append(f"  participant {_sanitize_id(participant)}")
    
    lines.append("")
    
    # Generate a basic flow based on relations
    # Try to find a logical flow through the system
    flows = _generate_flows(kg, actors, participants)
    
    if flows:
        for flow in flows:
            lines.append(f"  {flow}")
    else:
        # Default skeleton flow
        lines.append("  Note over User: Add interactions based on use case")
        lines.append("  User->>+API: Request")
        lines.append("  API->>+Database: Query")
        lines.append("  Database-->>-API: Result")
        lines.append("  API-->>-User: Response")
    
    return "\n".join(lines)


def _generate_flows(kg: RepoKG, actors: Set[str], participants: Set[str]) -> List[str]:
    """Generate flow lines based on KG relations."""
    flows = []
    processed = set()
    
    # Start with UI/actor interactions
    for actor in actors:
        # Find what this actor calls
        for rel in kg.relations_from(actor):
            if rel.dst in participants and (actor, rel.dst) not in processed:
                flows.append(f"{_sanitize_id(actor)}->>+{_sanitize_id(rel.dst)}: {rel.kind}")
                processed.add((actor, rel.dst))
                
                # Follow the chain
                _follow_chain(kg, rel.dst, flows, processed, depth=0)
                
                # Return response
                flows.append(f"{_sanitize_id(rel.dst)}-->>-{_sanitize_id(actor)}: Response")
    
    # If no UI flows, start with API endpoints
    if not flows:
        apis = kg.entities_by_type("API")
        for api in apis[:3]:  # Limit to first 3 APIs
            # Find what this API interacts with
            for rel in kg.relations_from(api.name):
                if rel.dst in participants and (api.name, rel.dst) not in processed:
                    flows.append(f"{_sanitize_id(api.name)}->>+{_sanitize_id(rel.dst)}: {rel.kind}")
                    processed.add((api.name, rel.dst))
                    flows.append(f"{_sanitize_id(rel.dst)}-->>-{_sanitize_id(api.name)}: Response")
    
    return flows


def _follow_chain(kg: RepoKG, current: str, flows: List[str], processed: Set[tuple], depth: int):
    """Follow relation chain to generate sequence flow."""
    if depth > 3:  # Limit depth to avoid too complex diagrams
        return
    
    for rel in kg.relations_from(current):
        if (current, rel.dst) not in processed:
            flows.append(f"{_sanitize_id(current)}->>+{_sanitize_id(rel.dst)}: {rel.kind}")
            processed.add((current, rel.dst))
            
            # Recursively follow
            _follow_chain(kg, rel.dst, flows, processed, depth + 1)
            
            flows.append(f"{_sanitize_id(rel.dst)}-->>-{_sanitize_id(current)}: Response")


def _sanitize_id(name: str) -> str:
    """Sanitize name for Mermaid ID."""
    return name.replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "_")