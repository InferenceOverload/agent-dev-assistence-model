"""Rally planner agent that creates work items from requirements.

Maps requirements to features, stories, and tasks using the knowledge graph
to identify impacted components and appropriate owners.
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from src.services.rally import RallyClient
from src.core.logging import get_logger
from src.core.types import KnowledgeGraph

logger = get_logger(__name__)


class WorkItemType(Enum):
    """Rally work item types."""
    FEATURE = "feature"
    STORY = "story"
    TASK = "task"


@dataclass
class WorkItem:
    """Represents a Rally work item to be created."""
    type: WorkItemType
    title: str
    description: str
    parent_id: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    estimate: Optional[float] = None
    tags: Optional[List[str]] = None
    impacted_paths: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "parent_id": self.parent_id,
            "acceptance_criteria": self.acceptance_criteria,
            "estimate": self.estimate,
            "tags": self.tags,
            "impacted_paths": self.impacted_paths
        }


@dataclass
class RallyPlan:
    """A plan for creating Rally work items."""
    plan_id: str
    feature: Optional[WorkItem]
    stories: List[WorkItem]
    tasks: List[WorkItem]
    total_estimate: float
    impacted_components: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plan_id": self.plan_id,
            "feature": self.feature.to_dict() if self.feature else None,
            "stories": [s.to_dict() for s in self.stories],
            "tasks": [t.to_dict() for t in self.tasks],
            "total_estimate": self.total_estimate,
            "impacted_components": self.impacted_components
        }
        
    def preview(self) -> str:
        """Generate preview text for the plan."""
        lines = ["Rally Work Item Plan", "=" * 40]
        
        if self.feature:
            lines.append(f"\nFeature: {self.feature.title}")
            lines.append(f"  Description: {self.feature.description[:100]}...")
            if self.feature.tags:
                lines.append(f"  Tags: {', '.join(self.feature.tags)}")
                
        if self.stories:
            lines.append(f"\nStories ({len(self.stories)}):")
            for story in self.stories:
                lines.append(f"  - {story.title}")
                if story.estimate:
                    lines.append(f"    Estimate: {story.estimate} points")
                if story.acceptance_criteria:
                    lines.append(f"    ACs: {len(story.acceptance_criteria)} criteria")
                    
        if self.tasks:
            lines.append(f"\nTasks ({len(self.tasks)}):")
            for task in self.tasks:
                lines.append(f"  - {task.title}")
                if task.estimate:
                    lines.append(f"    Estimate: {task.estimate} hours")
                    
        lines.append(f"\nTotal Estimate: {self.total_estimate} points")
        lines.append(f"Impacted Components: {', '.join(self.impacted_components)}")
        
        return "\n".join(lines)


class RallyPlanner:
    """Plans and creates Rally work items from requirements."""
    
    def __init__(self, rally_client: Optional[RallyClient] = None):
        """Initialize the planner.
        
        Args:
            rally_client: Optional Rally client instance
        """
        self.rally_client = rally_client or RallyClient()
        self._plans: Dict[str, RallyPlan] = {}
        
    def _analyze_requirement(self, requirement_text: str, kg: Optional[KnowledgeGraph] = None) -> Tuple[List[str], Dict[str, List[str]]]:
        """Analyze requirement to identify impacted components and paths.
        
        Args:
            requirement_text: The requirement text
            kg: Optional knowledge graph
            
        Returns:
            Tuple of (impacted_components, component_to_paths_map)
        """
        impacted_components = []
        component_paths = {}
        
        if not kg:
            return impacted_components, component_paths
            
        # Scan requirement for component/file references
        requirement_lower = requirement_text.lower()
        
        # Look for component names in the requirement
        for component_name in kg.components.keys():
            if component_name.lower() in requirement_lower:
                impacted_components.append(component_name)
                component = kg.components[component_name]
                component_paths[component_name] = component.files[:5]  # Top 5 files
                
        # Look for file paths in the requirement
        for node_id, node in kg.nodes.items():
            if node.path and node.path.lower() in requirement_lower:
                # Find which component this file belongs to
                for comp_name, component in kg.components.items():
                    if node.path in component.files:
                        if comp_name not in impacted_components:
                            impacted_components.append(comp_name)
                        if comp_name not in component_paths:
                            component_paths[comp_name] = []
                        if node.path not in component_paths[comp_name]:
                            component_paths[comp_name].append(node.path)
                            
        return impacted_components, component_paths
        
    def _decompose_requirement(self, requirement_text: str, 
                              impacted_components: List[str],
                              component_paths: Dict[str, List[str]]) -> Tuple[Optional[WorkItem], List[WorkItem], List[WorkItem]]:
        """Decompose requirement into feature, stories, and tasks.
        
        Args:
            requirement_text: The requirement text
            impacted_components: List of impacted components
            component_paths: Map of component to file paths
            
        Returns:
            Tuple of (feature, stories, tasks)
        """
        # Simple heuristic-based decomposition
        # In production, this would use an LLM for better parsing
        
        lines = requirement_text.strip().split('\n')
        title = lines[0][:100] if lines else "New Feature"
        
        # Determine if this is complex enough for a feature
        is_complex = (
            len(impacted_components) > 1 or
            len(requirement_text) > 500 or
            any(keyword in requirement_text.lower() for keyword in 
                ['multiple', 'system', 'integration', 'refactor', 'architecture'])
        )
        
        feature = None
        stories = []
        tasks = []
        
        if is_complex:
            # Create feature
            feature = WorkItem(
                type=WorkItemType.FEATURE,
                title=f"Feature: {title}",
                description=requirement_text,
                tags=impacted_components[:3]  # Top 3 components as tags
            )
            
            # Create stories per component
            for comp_name in impacted_components:
                paths = component_paths.get(comp_name, [])
                
                story = WorkItem(
                    type=WorkItemType.STORY,
                    title=f"Implement {title} for {comp_name}",
                    description=f"Implementation of requirement in {comp_name} component",
                    acceptance_criteria=[
                        f"All changes in {comp_name} are implemented",
                        f"Unit tests pass for {comp_name}",
                        f"Integration tests pass with other components",
                        "Code review completed"
                    ],
                    estimate=len(paths) * 2,  # Rough estimate based on file count
                    impacted_paths=paths
                )
                stories.append(story)
                
                # Create tasks for each story
                if paths:
                    # Implementation task
                    tasks.append(WorkItem(
                        type=WorkItemType.TASK,
                        title=f"Update {comp_name} implementation",
                        description=f"Modify files: {', '.join(paths[:3])}",
                        estimate=len(paths) * 1.5
                    ))
                    
                    # Test task
                    tasks.append(WorkItem(
                        type=WorkItemType.TASK,
                        title=f"Write tests for {comp_name} changes",
                        description=f"Add unit and integration tests",
                        estimate=len(paths) * 0.5
                    ))
        else:
            # Simple requirement - just create a story with tasks
            story = WorkItem(
                type=WorkItemType.STORY,
                title=title,
                description=requirement_text,
                acceptance_criteria=[
                    "Implementation complete",
                    "Tests pass",
                    "Code review completed"
                ],
                estimate=5,  # Default estimate
                impacted_paths=sum(component_paths.values(), [])
            )
            stories.append(story)
            
            # Basic tasks
            tasks.extend([
                WorkItem(
                    type=WorkItemType.TASK,
                    title="Implement changes",
                    description="Implement the required changes",
                    estimate=3
                ),
                WorkItem(
                    type=WorkItemType.TASK,
                    title="Write tests",
                    description="Add test coverage",
                    estimate=2
                )
            ])
            
        return feature, stories, tasks
        
    def plan_to_rally(self, requirement_text: str, kg: Optional[KnowledgeGraph] = None) -> RallyPlan:
        """Create a Rally work item plan from a requirement.
        
        Args:
            requirement_text: The requirement text
            kg: Optional knowledge graph for component mapping
            
        Returns:
            RallyPlan object with planned work items
        """
        # Analyze requirement
        impacted_components, component_paths = self._analyze_requirement(requirement_text, kg)
        
        # Decompose into work items
        feature, stories, tasks = self._decompose_requirement(
            requirement_text, impacted_components, component_paths
        )
        
        # Calculate total estimate
        total_estimate = sum(s.estimate or 0 for s in stories)
        
        # Create plan
        import uuid
        plan_id = str(uuid.uuid4())[:8]
        
        plan = RallyPlan(
            plan_id=plan_id,
            feature=feature,
            stories=stories,
            tasks=tasks,
            total_estimate=total_estimate,
            impacted_components=impacted_components
        )
        
        # Store plan for later execution
        self._plans[plan_id] = plan
        
        logger.info(f"Created Rally plan {plan_id} with {len(stories)} stories and {len(tasks)} tasks")
        
        return plan
        
    def apply_plan(self, plan_id: str, dry_run: bool = False) -> Dict[str, Any]:
        """Apply a Rally plan by creating the work items.
        
        Args:
            plan_id: The plan ID to apply
            dry_run: If True, don't actually create items
            
        Returns:
            Dictionary with created item IDs
        """
        if plan_id not in self._plans:
            raise ValueError(f"Plan {plan_id} not found")
            
        plan = self._plans[plan_id]
        
        if dry_run:
            logger.info(f"DRY RUN: Would create {len(plan.stories)} stories and {len(plan.tasks)} tasks")
            return {
                "dry_run": True,
                "plan_preview": plan.preview()
            }
            
        created = {
            "feature_id": None,
            "story_ids": [],
            "task_ids": []
        }
        
        try:
            # Create feature if present
            if plan.feature:
                feature_id = self.rally_client.create_feature(
                    plan.feature.title,
                    plan.feature.description,
                    plan.feature.tags
                )
                created["feature_id"] = feature_id
                
            # Create stories
            story_task_map = {}  # Map story index to task indices
            for i, story in enumerate(plan.stories):
                story_id = self.rally_client.create_story(
                    created["feature_id"],
                    story.title,
                    story.description,
                    story.acceptance_criteria or [],
                    int(story.estimate) if story.estimate else None
                )
                created["story_ids"].append(story_id)
                
                # Track which tasks belong to this story
                story_task_map[i] = []
                
                # Find tasks that should be linked to this story
                # (Simple heuristic: tasks that mention the same component)
                story_comp = None
                for comp in plan.impacted_components:
                    if comp in story.title:
                        story_comp = comp
                        break
                        
                for j, task in enumerate(plan.tasks):
                    if story_comp and story_comp in task.title:
                        story_task_map[i].append(j)
                        
            # Create tasks
            for i, task in enumerate(plan.tasks):
                # Find which story this task belongs to
                parent_story_id = None
                for story_idx, task_indices in story_task_map.items():
                    if i in task_indices and story_idx < len(created["story_ids"]):
                        parent_story_id = created["story_ids"][story_idx]
                        break
                        
                # If no specific story, link to first one
                if not parent_story_id and created["story_ids"]:
                    parent_story_id = created["story_ids"][0]
                    
                if parent_story_id:
                    task_id = self.rally_client.create_task(
                        parent_story_id,
                        task.title,
                        task.description,
                        task.estimate
                    )
                    created["task_ids"].append(task_id)
                    
            logger.info(f"Successfully applied Rally plan {plan_id}")
            
            # Clean up stored plan
            del self._plans[plan_id]
            
            return created
            
        except Exception as e:
            logger.error(f"Failed to apply Rally plan: {e}")
            raise
            
    def get_plan(self, plan_id: str) -> Optional[RallyPlan]:
        """Get a stored plan by ID.
        
        Args:
            plan_id: The plan ID
            
        Returns:
            RallyPlan or None if not found
        """
        return self._plans.get(plan_id)
        
    def list_plans(self) -> List[str]:
        """List all stored plan IDs.
        
        Returns:
            List of plan IDs
        """
        return list(self._plans.keys())