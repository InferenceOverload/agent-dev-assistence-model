"""Session context helper for gathering available repo information."""

from typing import Dict, Any, Optional


def get_context(orchestrator) -> Dict[str, Any]:
    """Extract available context from orchestrator session.
    
    Args:
        orchestrator: OrchestratorAgent instance
        
    Returns:
        Dictionary with available context fields:
        - code_map: CodeMap if loaded
        - repo_facts: RepoFacts if analyzed  
        - kg: KnowledgeGraph if available
        - last_evidence: Last doc_pack from evidence collection
        - last_query: Last user query
        - repo_root: Current repository root path
        - files: List of repository files
        - commit: Current commit hash
    """
    context = {}
    
    # Get basic repo info
    if hasattr(orchestrator, 'root') and orchestrator.root:
        context['repo_root'] = orchestrator.root
        
    # Get code map
    if hasattr(orchestrator, 'code_map') and orchestrator.code_map:
        context['code_map'] = orchestrator.code_map
        context['files'] = orchestrator.code_map.files if hasattr(orchestrator.code_map, 'files') else []
        context['commit'] = orchestrator.code_map.commit if hasattr(orchestrator.code_map, 'commit') else None
        
        # Build a summary of the code map
        if context['files'] and isinstance(context['files'], list):
            # Group files by directory
            dirs = {}
            for f in context['files']:
                parts = f.split('/')
                if len(parts) > 1:
                    dir_name = parts[0]
                    if dir_name not in dirs:
                        dirs[dir_name] = []
                    dirs[dir_name].append(f)
            context['code_map_summary'] = {
                'total_files': len(context['files']),
                'directories': list(dirs.keys())[:10],  # Top 10 dirs
                'languages': _detect_languages(context['files'])
            }
    
    # Get repo facts from analysis (if available via global cache)
    try:
        import adam_agent
        if hasattr(adam_agent, '_cached_facts') and adam_agent._cached_facts:
            context['repo_facts'] = adam_agent._cached_facts
            # Extract key info
            if context['repo_facts']:
                context['components'] = list(context['repo_facts'].components.keys()) if hasattr(context['repo_facts'], 'components') else []
                context['frameworks'] = context['repo_facts'].frameworks if hasattr(context['repo_facts'], 'frameworks') else []
    except:
        pass
    
    # Get knowledge graph if available
    if hasattr(orchestrator, 'kg') and orchestrator.kg:
        context['kg'] = orchestrator.kg
        
    # Get last evidence/doc_pack
    if hasattr(orchestrator, '_last_evidence'):
        context['last_evidence'] = orchestrator._last_evidence
        
    # Get last query
    if hasattr(orchestrator, '_last_query'):
        context['last_query'] = orchestrator._last_query
        
    # Get sizing info
    if hasattr(orchestrator, 'sizer') and orchestrator.sizer:
        try:
            context['repo_size'] = {
                'total_files': orchestrator.sizer.total_files if hasattr(orchestrator.sizer, 'total_files') else 0,
                'total_lines': orchestrator.sizer.total_lines if hasattr(orchestrator.sizer, 'total_lines') else 0,
                'size_mb': float(orchestrator.sizer.size_bytes) / 1024 / 1024 if hasattr(orchestrator.sizer, 'size_bytes') and orchestrator.sizer.size_bytes else 0
            }
        except (TypeError, AttributeError):
            pass
        
    return context


def _detect_languages(files: list) -> list:
    """Detect programming languages from file extensions."""
    extensions = set()
    lang_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.jsx': 'React',
        '.tsx': 'React TypeScript',
        '.java': 'Java',
        '.go': 'Go',
        '.rs': 'Rust',
        '.cpp': 'C++',
        '.c': 'C',
        '.cs': 'C#',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.scala': 'Scala',
        '.r': 'R',
        '.sql': 'SQL',
        '.sh': 'Shell',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.json': 'JSON',
        '.xml': 'XML',
        '.html': 'HTML',
        '.css': 'CSS',
        '.scss': 'SCSS',
        '.tf': 'Terraform',
        '.vue': 'Vue',
        '.dart': 'Dart'
    }
    
    for f in files:
        for ext, lang in lang_map.items():
            if f.endswith(ext):
                extensions.add(lang)
                break
                
    return sorted(list(extensions))