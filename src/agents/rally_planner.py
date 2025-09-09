"""Context-aware Rally planner that creates work items from requirements.

Uses repository context when available to create concrete implementation plans.
Always previews before applying changes.
"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.services.rally import RallyClient
from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WorkItem:
    """Represents a Rally work item."""
    type: str  # "feature", "story", or "task"
    title: str
    description: str
    acceptance_criteria: List[str] = field(default_factory=list)
    estimate: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    components: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "estimate": self.estimate,
            "tags": self.tags,
            "parent_id": self.parent_id,
            "components": self.components,
            "files": self.files
        }


@dataclass 
class RallyPlan:
    """Complete Rally implementation plan."""
    plan_id: str
    requirement: str
    context_available: bool
    repo_agnostic: bool
    feature: Optional[WorkItem]
    stories: List[WorkItem]
    tasks: List[WorkItem]
    components_touched: List[str]
    files_impacted: List[str]
    assumptions: List[str]
    clarifying_questions: List[str]
    risks: List[str]
    references: Dict[str, str]  # Links to PRs, docs, etc
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "requirement": self.requirement,
            "context_available": self.context_available,
            "repo_agnostic": self.repo_agnostic,
            "feature": self.feature.to_dict() if self.feature else None,
            "stories": [s.to_dict() for s in self.stories],
            "tasks": [t.to_dict() for t in self.tasks],
            "components_touched": self.components_touched,
            "files_impacted": self.files_impacted,
            "assumptions": self.assumptions,
            "clarifying_questions": self.clarifying_questions,
            "risks": self.risks,
            "references": self.references,
            "created_at": self.created_at
        }


# Plan cache for preview/confirm flow
_plan_cache: Dict[str, RallyPlan] = {}


def plan_from_requirement(requirement: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Create Rally plan from requirement using available context.
    
    Args:
        requirement: User requirement text
        context: Available context from session (code_map, repo_facts, kg, etc)
        
    Returns:
        Dictionary with plan details including preview
    """
    # Generate plan ID
    plan_id = str(uuid.uuid4())[:8]
    
    # Check what context is available
    has_repo = bool(context.get('code_map') or context.get('files'))
    has_components = bool(context.get('components') or context.get('repo_facts'))
    has_framework_info = bool(context.get('frameworks'))
    
    # Initialize plan components
    components_touched = []
    files_impacted = []
    assumptions = []
    clarifying_questions = []
    risks = []
    references = {}
    
    # Extract repo name if available
    repo_name = None
    if context.get('repo_root'):
        repo_name = os.path.basename(context['repo_root'])
    
    # Analyze requirement against context
    req_lower = requirement.lower()
    
    if has_repo:
        # We have repository context - create concrete plan
        files = context.get('files', [])
        components = context.get('components', [])
        frameworks = context.get('frameworks', [])
        
        # Find relevant files and components
        
        # Search for mentioned files
        for f in files[:500]:  # Limit to avoid huge lists
            file_lower = f.lower()
            # Check if file might be relevant
            for keyword in req_lower.split():
                if len(keyword) > 3 and keyword in file_lower:
                    files_impacted.append(f)
                    break
                    
        # Identify impacted components
        for comp in components:
            if comp.lower() in req_lower or _is_component_relevant(comp, requirement):
                components_touched.append(comp)
        
        # If requirement mentions multiple/system/integration, include more components
        if any(word in req_lower for word in ['multiple', 'system', 'integration', 'all']):
            for comp in components[:4]:  # Add up to 4 components for complex requirements
                if comp not in components_touched:
                    components_touched.append(comp)
                
        # If no specific components found, use top-level dirs
        if not components_touched and files:
            dirs = set()
            for f in files[:100]:
                if '/' in f:
                    dirs.add(f.split('/')[0])
            components_touched = list(dirs)[:5]
            
        # Add framework-specific considerations
        if frameworks:
            references['frameworks'] = ', '.join(frameworks)
            
    else:
        # No repo context - create generic plan
        assumptions = [
            "No repository loaded - creating generic plan",
            "Assuming standard project structure",
            "Component names and file paths are tentative"
        ]
        
        clarifying_questions = [
            "What is the repository URL or project structure?",
            "What frameworks/technologies are used?",
            "Are there existing patterns to follow?",
            "What are the current testing requirements?"
        ]
        
    # Create work items based on requirement complexity
    feature = None
    stories = []
    tasks = []
    
    # Determine if this needs a feature (complex requirement)
    is_complex = (
        len(requirement) > 200 or
        'multiple' in req_lower or
        'system' in req_lower or
        'integration' in req_lower or
        len(components_touched) > 2
    )
    
    # Create feature if complex
    if is_complex:
        feature = WorkItem(
            type="feature",
            title=f"Feature: {requirement[:80]}",
            description=requirement + f"\n\nRepository: {repo_name or 'Not specified'}",
            tags=[repo_name] if repo_name else [],
            components=components_touched[:3] if components_touched else []
        )
        
    # Create stories
    if components_touched:
        # Story per component
        for comp in components_touched[:5]:  # Limit stories
            # Find files for this component
            comp_files = [f for f in files_impacted if comp in f or f.startswith(comp + '/')][:5]
            
            story = WorkItem(
                type="story",
                title=f"Implement {requirement[:50]} in {comp}",
                description=f"Implementation for {comp} component\n\nFiles to modify:\n" + 
                           '\n'.join(f"- {f}" for f in comp_files),
                acceptance_criteria=[
                    f"All changes in {comp} are implemented",
                    f"Unit tests pass for {comp}",
                    "Integration tests pass",
                    "Code review completed",
                    "Documentation updated"
                ],
                estimate=3 if len(comp_files) <= 2 else 5 if len(comp_files) <= 5 else 8,
                tags=[repo_name, comp] if repo_name else [comp],
                components=[comp],
                files=comp_files
            )
            stories.append(story)
            
            # Create tasks for story
            if comp_files:
                tasks.append(WorkItem(
                    type="task",
                    title=f"Update {comp} implementation",
                    description=f"Modify files:\n" + '\n'.join(f"- {f}" for f in comp_files[:3]),
                    estimate=len(comp_files) * 2,
                    tags=[comp],
                    files=comp_files
                ))
                
            tasks.append(WorkItem(
                type="task",
                title=f"Write tests for {comp} changes",
                description=f"Add unit and integration tests for {comp}",
                estimate=2,
                tags=[comp, "testing"]
            ))
    else:
        # No components identified - create generic story
        story = WorkItem(
            type="story",
            title=requirement[:100],
            description=requirement + "\n\nNote: No specific components identified",
            acceptance_criteria=[
                "Requirements implemented",
                "Tests pass",
                "Code reviewed",
                "Documentation updated"
            ],
            estimate=5,
            tags=[repo_name] if repo_name else []
        )
        stories.append(story)
        
        # Generic tasks
        tasks.extend([
            WorkItem(
                type="task",
                title="Implement core changes",
                description="Implement the required functionality",
                estimate=5,
                tags=["implementation"]
            ),
            WorkItem(
                type="task",
                title="Write tests",
                description="Add test coverage for changes",
                estimate=3,
                tags=["testing"]
            ),
            WorkItem(
                type="task",
                title="Update documentation",
                description="Document changes and usage",
                estimate=1,
                tags=["documentation"]
            )
        ])
        
    # Add risks based on context
    if not has_repo:
        risks.append("No repository context - plan may need adjustment after code review")
    if len(components_touched) > 3:
        risks.append("Multiple components affected - consider breaking into phases")
    if not has_framework_info:
        risks.append("Framework requirements unknown - may need framework-specific adjustments")
        
    # Add references
    if context.get('last_query'):
        references['last_analysis'] = context['last_query']
    if context.get('commit'):
        references['commit'] = context['commit']
        
    # Create plan
    plan = RallyPlan(
        plan_id=plan_id,
        requirement=requirement,
        context_available=has_repo,
        repo_agnostic=not has_repo,
        feature=feature,
        stories=stories,
        tasks=tasks,
        components_touched=components_touched,
        files_impacted=files_impacted[:20],  # Limit for preview
        assumptions=assumptions,
        clarifying_questions=clarifying_questions,
        risks=risks,
        references=references,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    
    # Cache plan
    _plan_cache[plan_id] = plan
    
    return plan.to_dict()


def preview_payload(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Create preview of Rally items to be created.
    
    Args:
        plan: Plan dictionary from plan_from_requirement
        
    Returns:
        Preview dictionary with formatted items
    """
    preview = {
        "plan_id": plan['plan_id'],
        "summary": f"Creating {len(plan['stories'])} stories and {len(plan['tasks'])} tasks",
        "context_available": plan['context_available'],
        "repo_agnostic": plan['repo_agnostic'],
        "items": []
    }
    
    # Add feature to preview
    if plan['feature']:
        f = plan['feature']
        preview['items'].append({
            "type": "FEATURE",
            "title": f['title'],
            "description": f['description'][:200] + "...",
            "tags": f['tags'],
            "components": f['components']
        })
        
    # Add stories
    for s in plan['stories']:
        preview['items'].append({
            "type": "STORY",
            "title": s['title'],
            "estimate": f"{s['estimate']} points" if s['estimate'] else "Not estimated",
            "acceptance_criteria": len(s['acceptance_criteria']),
            "files": len(s['files']),
            "components": s['components']
        })
        
    # Add tasks summary
    preview['tasks_summary'] = f"{len(plan['tasks'])} tasks to be created"
    
    # Add context warnings
    if plan['repo_agnostic']:
        preview['context_request'] = (
            "No repository loaded. Please provide a repository URL for more accurate planning:\n"
            "Example: load_repo('https://github.com/owner/repo')"
        )
        
    # Add assumptions and questions
    if plan['assumptions']:
        preview['assumptions'] = plan['assumptions']
    if plan['clarifying_questions']:
        preview['clarifying_questions'] = plan['clarifying_questions']
    if plan['risks']:
        preview['risks'] = plan['risks']
        
    # Add action required
    preview['requires_confirmation'] = True
    preview['confirm_message'] = "Run rally_confirm(requirement, confirm=True) to create these items in Rally"
    
    return preview


def apply_to_rally(plan: Dict[str, Any], confirm: bool, feature_id: Optional[str] = None) -> Dict[str, Any]:
    """Apply plan to Rally, creating actual work items with optional feature validation.
    
    Args:
        plan: Plan dictionary
        confirm: If False, return preview; if True, create items
        feature_id: Optional existing feature ID to validate against
        
    Returns:
        Result dictionary with created IDs or preview
    """
    if not confirm:
        preview = preview_payload(plan)
        preview['requires_confirmation'] = True
        return {"preview": preview, "requires_confirmation": True}
        
    # Check Rally configuration
    if not os.getenv('RALLY_API_KEY'):
        return {
            "error": "Rally not configured",
            "message": "Set RALLY_API_KEY environment variable to create items",
            "preview": preview_payload(plan)
        }
        
    # Initialize Rally client
    try:
        client = RallyClient()
    except Exception as e:
        return {
            "error": "Failed to initialize Rally client",
            "message": str(e),
            "preview": preview_payload(plan)
        }
        
    # Validate against existing feature if provided
    parent_feature_id = feature_id
    if feature_id:
        try:
            # Get the feature from Rally
            feature_details = client.get_feature(feature_id)
            
            # Validate requirement against feature
            validation = client.validate_feature_context(feature_details, plan['requirement'])
            
            if not validation['valid']:
                # Feature doesn't match - warn user
                return {
                    "warning": "Feature context mismatch",
                    "feature": feature_details,
                    "validation": validation,
                    "message": f"Feature {feature_id} ({feature_details['name']}) doesn't match the requirement well. "
                              f"Confidence: {validation['confidence']:.2f}. {validation['reason']}",
                    "preview": preview_payload(plan),
                    "confirm_anyway": f"To proceed anyway, run: rally_confirm(requirement, confirm=True, force=True)"
                }
            elif validation['confidence'] < 0.5:
                # Low confidence - inform user
                logger.info(f"Feature validation: {validation['reason']} (confidence: {validation['confidence']:.2f})")
                
            # Use the existing feature instead of creating a new one
            parent_feature_id = feature_details['id']
            logger.info(f"Using existing feature {feature_id}: {feature_details['name']}")
            
        except Exception as e:
            return {
                "error": f"Feature {feature_id} not found",
                "message": str(e),
                "preview": preview_payload(plan)
            }
    
    # Track created items
    created = {
        "feature": None,
        "feature_used": parent_feature_id,
        "stories": [],
        "tasks": [],
        "audit": []
    }
    
    try:
        # Create feature if present and no existing feature provided
        if plan['feature'] and not parent_feature_id:
            f = plan['feature']
            result = client.create_feature(f['title'], f['description'], f['tags'])
            created['feature'] = result
            created['audit'].append(f"Created feature: {result['id']}")
            
        # Create stories
        for story in plan['stories']:
            feature_id = created['feature']['id'] if created['feature'] else None
            result = client.create_story(
                feature_id,
                story['title'],
                story['description'],
                story['acceptance_criteria'],
                story['estimate'],
                story['tags']
            )
            created['stories'].append(result)
            created['audit'].append(f"Created story: {result['id']}")
            
        # Create tasks (assign to first story for simplicity)
        if created['stories'] and plan['tasks']:
            first_story_id = created['stories'][0]['id']
            for task in plan['tasks']:
                result = client.create_task(
                    first_story_id,
                    task['title'],
                    task['description'],
                    task['estimate'],
                    task['tags']
                )
                created['tasks'].append(result)
                created['audit'].append(f"Created task: {result['id']}")
                
    except Exception as e:
        created['error'] = str(e)
        created['audit'].append(f"ERROR: {str(e)}")
        
    # Add summary
    created['summary'] = (
        f"Created {1 if created['feature'] else 0} feature, "
        f"{len(created['stories'])} stories, {len(created['tasks'])} tasks"
    )
    
    return created


def _is_component_relevant(component: str, requirement: str) -> bool:
    """Check if a component might be relevant to the requirement."""
    req_lower = requirement.lower()
    comp_lower = component.lower()
    
    # Common keywords that might indicate relevance
    keywords = ['api', 'ui', 'database', 'auth', 'service', 'model', 'view', 'controller']
    
    for keyword in keywords:
        if keyword in comp_lower and keyword in req_lower:
            return True
            
    return False