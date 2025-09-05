"""Rally story extender that creates implementation tasks based on repository context."""

from typing import Dict, Any, List
from datetime import datetime, timezone
from src.core.logging import get_logger

logger = get_logger(__name__)


def extend_story_with_context(
    rally_context: Dict[str, Any],
    repo_context: Dict[str, Any],
    extension_request: str
) -> Dict[str, Any]:
    """Create implementation tasks for an existing Rally story based on repo context.
    
    Args:
        rally_context: Story and feature details from Rally
        repo_context: Current repository context (files, components, frameworks)
        extension_request: What to add to the story
        
    Returns:
        Dictionary with tasks list ready for creation
    """
    story = rally_context.get('story', {})
    feature = rally_context.get('feature', {})
    
    # Extract story details
    story_title = story.get('title', 'Unknown Story')
    story_description = story.get('description', '')
    acceptance_criteria = story.get('acceptance_criteria', '')
    
    # Determine if we have repo context
    has_context = bool(repo_context.get('files'))
    components = repo_context.get('components', [])
    frameworks = repo_context.get('frameworks', [])
    code_map = repo_context.get('code_map')
    
    logger.info(f"Extending story '{story_title}' with repo context: {has_context}")
    
    # Build tasks based on context
    tasks = []
    
    if has_context:
        # Context-aware task generation
        tasks.extend(_generate_contextual_tasks(
            story, extension_request, repo_context
        ))
    else:
        # Generic tasks when no repo context
        tasks.extend(_generate_generic_tasks(
            story, extension_request
        ))
    
    # Build the extension plan
    extension = {
        'story_id': story.get('id'),
        'story_title': story_title,
        'extension_request': extension_request,
        'tasks': tasks,
        'context_available': has_context,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    if not has_context:
        extension['note'] = "No repository context - tasks are generic. Load a repo for specific implementation details."
    
    return extension


def _generate_contextual_tasks(
    story: Dict[str, Any],
    request: str,
    context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate tasks based on repository context."""
    tasks = []
    req_lower = request.lower()
    
    # Analyze the request to determine task types
    components = context.get('components', [])
    files = context.get('files', [])
    frameworks = context.get('frameworks', [])
    
    # Map request keywords to component focus
    component_tasks = []
    
    # Authentication related
    if any(word in req_lower for word in ['auth', 'login', 'security', 'oauth', 'jwt']):
        if 'auth' in components or 'authentication' in components:
            component_tasks.append({
                'title': 'Implement authentication module',
                'description': f"Update authentication components based on: {story['title']}",
                'tags': ['auth', 'implementation'],
                'estimate': 4,
                'files': _find_related_files(files, ['auth', 'login', 'session'])
            })
        if 'api' in components:
            component_tasks.append({
                'title': 'Add authentication middleware to API endpoints',
                'description': 'Secure API routes with authentication checks',
                'tags': ['api', 'security'],
                'estimate': 3,
                'files': _find_related_files(files, ['api', 'routes', 'middleware'])
            })
    
    # API related
    if any(word in req_lower for word in ['api', 'endpoint', 'rest', 'graphql']):
        if 'api' in components or any('api' in c.lower() for c in components):
            component_tasks.append({
                'title': 'Implement API endpoints',
                'description': f"Create/modify API endpoints for: {story['title']}",
                'tags': ['api', 'endpoints'],
                'estimate': 3,
                'files': _find_related_files(files, ['api', 'routes', 'handlers'])
            })
    
    # Database related
    if any(word in req_lower for word in ['database', 'model', 'schema', 'migration']):
        if 'database' in components or 'models' in components:
            component_tasks.append({
                'title': 'Update database models',
                'description': 'Modify database schema and models',
                'tags': ['database', 'models'],
                'estimate': 2,
                'files': _find_related_files(files, ['models', 'schema', 'database'])
            })
            component_tasks.append({
                'title': 'Create database migrations',
                'description': 'Generate and test migration scripts',
                'tags': ['database', 'migration'],
                'estimate': 2
            })
    
    # Testing related
    if any(word in req_lower for word in ['test', 'testing', 'coverage']):
        test_files = _find_related_files(files, ['test', 'spec'])
        component_tasks.append({
            'title': 'Write unit tests',
            'description': f"Create unit tests for: {story['title']}",
            'tags': ['testing', 'unit-tests'],
            'estimate': 3,
            'files': test_files
        })
        if 'api' in components:
            component_tasks.append({
                'title': 'Write integration tests',
                'description': 'Create API integration tests',
                'tags': ['testing', 'integration'],
                'estimate': 2
            })
    
    # Frontend related
    if any(word in req_lower for word in ['ui', 'frontend', 'react', 'vue', 'angular']):
        ui_components = [c for c in components if any(ui in c.lower() for ui in ['ui', 'frontend', 'web'])]
        if ui_components or 'React' in frameworks or 'Vue' in frameworks:
            component_tasks.append({
                'title': 'Implement UI components',
                'description': f"Create/update frontend for: {story['title']}",
                'tags': ['frontend', 'ui'],
                'estimate': 4,
                'files': _find_related_files(files, ['components', 'views', 'pages'])
            })
    
    # If we got specific component tasks, use them
    if component_tasks:
        for task in component_tasks:
            # Add impacted files to description if found
            if task.get('files'):
                task['description'] += f"\n\nImpacted files:\n" + "\n".join(f"- {f}" for f in task['files'][:5])
            # Remove the files key before adding
            task.pop('files', None)
            tasks.append(task)
    
    # Always add some standard tasks
    if not any('research' in t.get('title', '').lower() for t in tasks):
        tasks.insert(0, {
            'title': f'Research: {request[:50]}',
            'description': f"Analyze codebase and plan implementation approach for: {story['title']}",
            'tags': ['research', 'planning'],
            'estimate': 2
        })
    
    if not any('document' in t.get('title', '').lower() for t in tasks):
        tasks.append({
            'title': 'Update documentation',
            'description': f"Document implementation of: {story['title']}",
            'tags': ['documentation'],
            'estimate': 1
        })
    
    return tasks


def _generate_generic_tasks(
    story: Dict[str, Any],
    request: str
) -> List[Dict[str, Any]]:
    """Generate generic tasks when no repo context is available."""
    tasks = []
    
    # Always start with research
    tasks.append({
        'title': f'Research: {request[:50]}',
        'description': f"Analyze requirements and plan approach for: {story['title']}",
        'tags': ['research', 'planning'],
        'estimate': 2
    })
    
    # Core implementation
    tasks.append({
        'title': f'Core implementation: {request[:50]}',
        'description': f"Implement main functionality for: {story['title']}\n\nNote: Load repository for specific file references",
        'tags': ['implementation'],
        'estimate': 4
    })
    
    # Tests
    tasks.append({
        'title': 'Write tests',
        'description': "Create unit and integration tests",
        'tags': ['testing'],
        'estimate': 3
    })
    
    # Documentation
    tasks.append({
        'title': 'Documentation',
        'description': "Update documentation and code comments",
        'tags': ['documentation'],
        'estimate': 1
    })
    
    return tasks


def _find_related_files(files: List[str], keywords: List[str]) -> List[str]:
    """Find files that match any of the keywords."""
    related = []
    for f in files:
        f_lower = f.lower()
        if any(keyword in f_lower for keyword in keywords):
            related.append(f)
    return related[:10]  # Limit to top 10 matches