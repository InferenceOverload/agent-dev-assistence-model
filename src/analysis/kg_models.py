"""Knowledge Graph models for repository analysis."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Entity(BaseModel):
    """An entity in the repository (component, service, resource, etc.)."""
    type: str = Field(..., description="Entity type: Service, Database, Job, Queue, Topic, Table, Resource, UI, API, etc.")
    name: str = Field(..., description="Entity name/identifier")
    path: str = Field(..., description="File path where defined")
    attrs: Dict[str, Any] = Field(default_factory=dict, description="Additional attributes")
    
    def __hash__(self):
        return hash((self.type, self.name, self.path))


class Relation(BaseModel):
    """A relationship between entities."""
    src: str = Field(..., description="Source entity name")
    dst: str = Field(..., description="Destination entity name")
    kind: str = Field(..., description="Relation kind: calls, reads, writes, deploys, produces, consumes, extends, implements")
    attrs: Dict[str, Any] = Field(default_factory=dict, description="Additional attributes like method, protocol, etc.")
    
    def __hash__(self):
        return hash((self.src, self.dst, self.kind))


class RepoKG(BaseModel):
    """Repository Knowledge Graph."""
    entities: List[Entity] = Field(default_factory=list)
    relations: List[Relation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list, description="Extraction warnings/issues")
    
    def entity_by_name(self, name: str) -> Optional[Entity]:
        """Find entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None
    
    def entities_by_type(self, type: str) -> List[Entity]:
        """Find all entities of a given type."""
        return [e for e in self.entities if e.type == type]
    
    def relations_from(self, src: str) -> List[Relation]:
        """Find all relations from a source entity."""
        return [r for r in self.relations if r.src == src]
    
    def relations_to(self, dst: str) -> List[Relation]:
        """Find all relations to a destination entity."""
        return [r for r in self.relations if r.dst == dst]
    
    def merge_duplicates(self):
        """Merge duplicate entities and relations."""
        # Deduplicate entities by (type, name)
        entity_map = {}
        for e in self.entities:
            key = (e.type, e.name)
            if key not in entity_map:
                entity_map[key] = e
            else:
                # Merge attributes
                entity_map[key].attrs.update(e.attrs)
        self.entities = list(entity_map.values())
        
        # Deduplicate relations
        self.relations = list(set(self.relations))