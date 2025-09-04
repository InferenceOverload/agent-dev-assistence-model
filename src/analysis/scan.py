"""Repository scanner with language-specific heuristics."""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict

from .models import Component, Relation, RepoFacts
from ..core.types import CodeMap


def analyze_repo(root: str, code_map: Optional[CodeMap] = None) -> RepoFacts:
    """
    Analyze repository structure and extract facts.
    
    Args:
        root: Repository root path
        code_map: Optional pre-computed code map
        
    Returns:
        RepoFacts with components, relations, and metadata
    """
    facts = RepoFacts()
    root_path = Path(root)
    
    # Get files from code_map or scan directory
    if code_map and code_map.files:
        files = code_map.files
    else:
        files = []
        for ext in ["*.py", "*.java", "*.js", "*.jsx", "*.ts", "*.tsx", "*.sql", "*.tf", "*.rs"]:
            files.extend([str(p.relative_to(root_path)) for p in root_path.rglob(ext)])
    
    # Count languages
    lang_counts = defaultdict(int)
    for f in files:
        lang = _detect_language(f)
        if lang:
            lang_counts[lang] += 1
    facts.languages = dict(lang_counts)
    
    # Detect components by directory structure
    components_map = {}
    component_files = defaultdict(list)
    
    for f in files:
        comp = _identify_component(f)
        if comp and comp.name not in components_map:
            components_map[comp.name] = comp
        if comp:
            component_files[comp.name].append(f)
    
    # Update file counts
    for name, comp in components_map.items():
        comp.files_count = len(component_files[name])
    
    facts.components = list(components_map.values())
    
    # Detect entry points
    facts.entry_points = _find_entry_points(files)
    
    # Detect frameworks
    facts.frameworks = _detect_frameworks(files, root_path)
    
    # Detect databases
    facts.databases = _detect_databases(files, root_path)
    
    # Detect deploy targets
    facts.deploy_targets = _detect_deploy_targets(files, root_path)
    
    # Infer relations
    facts.relations = _infer_relations(files, components_map, root_path)
    
    return facts


def _detect_language(filepath: str) -> Optional[str]:
    """Detect language from file extension."""
    ext = Path(filepath).suffix.lower()
    mapping = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".sql": "sql",
        ".plsql": "plsql",
        ".tf": "terraform",
        ".rs": "rust",
    }
    return mapping.get(ext)


def _identify_component(filepath: str) -> Optional[Component]:
    """Identify component from file path using heuristics."""
    path_lower = filepath.lower()
    parts = filepath.split(os.sep)
    
    # UI/Frontend patterns
    if any(p in path_lower for p in ["frontend", "client", "ui", "web", "app/assets", "src/components", "src/pages"]):
        return Component(
            name="Frontend",
            type="ui",
            path=parts[0] if parts else "frontend",
            language="javascript"
        )
    
    # API/Backend patterns
    if any(p in path_lower for p in ["backend", "api", "server", "service", "src/main/java", "app/controllers"]):
        lang = _detect_language(filepath) or "python"
        return Component(
            name="API",
            type="service",
            path=parts[0] if parts else "backend",
            language=lang
        )
    
    # Database/SQL patterns
    if any(p in path_lower for p in ["database", "db", "migrations", "schema", "ddl", "dml"]) or filepath.endswith(".sql"):
        return Component(
            name="Database",
            type="database",
            path=parts[0] if parts else "db",
            language="sql"
        )
    
    # Infrastructure patterns
    if any(p in path_lower for p in ["terraform", "infra", "infrastructure", "deploy", ".github/workflows"]):
        return Component(
            name="Infrastructure",
            type="infra",
            path=parts[0] if parts else "infra",
            language="terraform"
        )
    
    # Library patterns
    if any(p in path_lower for p in ["lib", "libs", "packages", "shared", "common", "utils", "tools"]):
        lang = _detect_language(filepath) or "python"
        return Component(
            name="Library",
            type="library",
            path=parts[0] if parts else "lib",
            language=lang
        )
    
    # Tests
    if any(p in path_lower for p in ["test", "tests", "spec", "__tests__"]):
        lang = _detect_language(filepath) or "python"
        return Component(
            name="Tests",
            type="tests",
            path=parts[0] if parts else "tests",
            language=lang
        )
    
    return None


def _find_entry_points(files: List[str]) -> List[str]:
    """Find likely entry point files."""
    entry_patterns = [
        "main.py", "app.py", "server.py", "run.py", "__main__.py",
        "index.js", "server.js", "app.js", "index.ts", "main.ts",
        "Main.java", "Application.java",
        "main.rs", "lib.rs",
        "main.tf", "variables.tf"
    ]
    
    entries = []
    for f in files:
        filename = Path(f).name
        if filename in entry_patterns or filename.endswith("Application.java"):
            entries.append(f)
    
    # Also check for package.json scripts, pyproject.toml scripts, etc.
    for f in files:
        if Path(f).name in ["package.json", "pyproject.toml", "Cargo.toml", "pom.xml", "build.gradle"]:
            entries.append(f)
    
    return entries[:10]  # Limit to top 10


def _detect_frameworks(files: List[str], root: Path) -> List[str]:
    """Detect frameworks from file patterns and config files."""
    frameworks = set()
    
    # Check config files
    config_files = ["package.json", "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle", "Cargo.toml"]
    for cf in config_files:
        config_path = root / cf
        if config_path.exists():
            try:
                content = config_path.read_text()[:5000]  # Read first 5KB
                
                # Python frameworks
                if cf in ["requirements.txt", "pyproject.toml"]:
                    if "django" in content.lower():
                        frameworks.add("Django")
                    if "flask" in content.lower():
                        frameworks.add("Flask")
                    if "fastapi" in content.lower():
                        frameworks.add("FastAPI")
                    if "pytest" in content.lower():
                        frameworks.add("pytest")
                
                # JavaScript frameworks
                if cf == "package.json":
                    if "react" in content.lower():
                        frameworks.add("React")
                    if "angular" in content.lower():
                        frameworks.add("Angular")
                    if "vue" in content.lower():
                        frameworks.add("Vue")
                    if "express" in content.lower():
                        frameworks.add("Express")
                    if "next" in content.lower():
                        frameworks.add("Next.js")
                
                # Java frameworks
                if cf in ["pom.xml", "build.gradle"]:
                    if "spring" in content.lower():
                        frameworks.add("Spring")
                    if "junit" in content.lower():
                        frameworks.add("JUnit")
            except:
                pass
    
    # File pattern detection
    for f in files[:100]:  # Sample first 100 files
        if "django" in f.lower() or "models.py" in f or "views.py" in f:
            frameworks.add("Django")
        if "@app.route" in f or "flask" in f.lower():
            frameworks.add("Flask")
        if ".jsx" in f or ".tsx" in f:
            frameworks.add("React")
        if ".tf" in f:
            frameworks.add("Terraform")
    
    return sorted(list(frameworks))


def _detect_databases(files: List[str], root: Path) -> List[str]:
    """Detect database systems from file patterns."""
    databases = set()
    
    # Check for database-specific files
    for f in files:
        f_lower = f.lower()
        if "postgres" in f_lower or "psql" in f_lower:
            databases.add("PostgreSQL")
        if "mysql" in f_lower or "mariadb" in f_lower:
            databases.add("MySQL")
        if "mongo" in f_lower or "mongodb" in f_lower:
            databases.add("MongoDB")
        if "redis" in f_lower:
            databases.add("Redis")
        if "oracle" in f_lower or ".plsql" in f:
            databases.add("Oracle")
        if "sqlite" in f_lower or ".db" in f:
            databases.add("SQLite")
        if "cassandra" in f_lower:
            databases.add("Cassandra")
        if "elastic" in f_lower:
            databases.add("Elasticsearch")
    
    # Check docker-compose or config files
    docker_compose = root / "docker-compose.yml"
    if docker_compose.exists():
        try:
            content = docker_compose.read_text()[:5000]
            if "postgres" in content.lower():
                databases.add("PostgreSQL")
            if "mysql" in content.lower():
                databases.add("MySQL")
            if "mongo" in content.lower():
                databases.add("MongoDB")
            if "redis" in content.lower():
                databases.add("Redis")
        except:
            pass
    
    return sorted(list(databases))


def _detect_deploy_targets(files: List[str], root: Path) -> List[str]:
    """Detect deployment targets from configuration files."""
    targets = set()
    
    # Check for cloud provider files
    for f in files:
        f_lower = f.lower()
        if ".tf" in f or "terraform" in f_lower:
            targets.add("Terraform")
        if "dockerfile" in f_lower:
            targets.add("Docker")
        if "kubernetes" in f_lower or "k8s" in f_lower or ".yaml" in f:
            targets.add("Kubernetes")
        if ".github/workflows" in f:
            targets.add("GitHub Actions")
        if "cloudformation" in f_lower:
            targets.add("AWS CloudFormation")
        if "azure-pipelines" in f_lower:
            targets.add("Azure DevOps")
        if "cloudbuild" in f_lower:
            targets.add("Google Cloud Build")
    
    # Check for specific cloud provider references
    if any("aws" in f.lower() or "lambda" in f.lower() for f in files[:50]):
        targets.add("AWS")
    if any("azure" in f.lower() for f in files[:50]):
        targets.add("Azure")
    if any("gcp" in f.lower() or "google-cloud" in f.lower() for f in files[:50]):
        targets.add("Google Cloud")
    
    return sorted(list(targets))


def _infer_relations(files: List[str], components: Dict[str, Component], root: Path) -> List[Relation]:
    """Infer relations between components."""
    relations = []
    
    # Simple heuristic: Frontend calls API
    if "Frontend" in components and "API" in components:
        relations.append(Relation(
            source="Frontend",
            target="API",
            type="calls",
            confidence=0.9
        ))
    
    # API queries Database
    if "API" in components and "Database" in components:
        relations.append(Relation(
            source="API",
            target="Database",
            type="queries",
            confidence=0.9
        ))
    
    # Library is imported by API and Frontend
    if "Library" in components:
        if "API" in components:
            relations.append(Relation(
                source="API",
                target="Library",
                type="imports",
                confidence=0.8
            ))
        if "Frontend" in components:
            relations.append(Relation(
                source="Frontend",
                target="Library",
                type="imports",
                confidence=0.8
            ))
    
    # Infrastructure deploys services
    if "Infrastructure" in components:
        for comp in ["API", "Frontend", "Database"]:
            if comp in components:
                relations.append(Relation(
                    source="Infrastructure",
                    target=comp,
                    type="deploys",
                    confidence=0.7
                ))
    
    # Tests test other components
    if "Tests" in components:
        for comp in ["API", "Frontend", "Library"]:
            if comp in components:
                relations.append(Relation(
                    source="Tests",
                    target=comp,
                    type="tests",
                    confidence=0.8
                ))
    
    return relations