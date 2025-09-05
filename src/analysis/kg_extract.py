"""Extract knowledge graph from repository structure and code."""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from .kg_models import Entity, Relation, RepoKG
from ..core.types import CodeMap


def build_seed_kg(root: str, code_map: CodeMap) -> RepoKG:
    """Build initial KG using heuristics for various languages and frameworks.
    
    Args:
        root: Repository root path
        code_map: Code map with files, deps, symbols
    
    Returns:
        Initial knowledge graph with entities and relations
    """
    kg = RepoKG()
    
    for file_path in code_map.files:
        path = Path(file_path)
        content = _read_file_safe(Path(root) / file_path)
        if not content:
            continue
        
        # Detect language/framework
        if path.suffix in ['.py']:
            _extract_python(kg, file_path, content, code_map)
        elif path.suffix in ['.js', '.jsx', '.ts', '.tsx']:
            _extract_javascript(kg, file_path, content, code_map)
        elif path.suffix in ['.java']:
            _extract_java(kg, file_path, content, code_map)
        elif path.suffix in ['.tf', '.hcl']:
            _extract_terraform(kg, file_path, content, code_map)
        elif path.suffix in ['.sql']:
            _extract_sql(kg, file_path, content, code_map)
        elif path.name in ['docker-compose.yml', 'docker-compose.yaml']:
            _extract_docker_compose(kg, file_path, content)
        elif path.name == 'Dockerfile':
            _extract_dockerfile(kg, file_path, content)
    
    # Add dependency relations
    for src_file, imports in code_map.deps.items():
        src_name = Path(src_file).stem
        for imp in imports:
            # Try to find matching file
            for dst_file in code_map.files:
                if Path(dst_file).stem == imp or imp in dst_file:
                    dst_name = Path(dst_file).stem
                    kg.relations.append(Relation(
                        src=src_name,
                        dst=dst_name,
                        kind="imports"
                    ))
                    break
    
    kg.merge_duplicates()
    return kg


def _read_file_safe(path: Path) -> str:
    """Safely read file content."""
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except:
        return ""


def _extract_python(kg: RepoKG, path: str, content: str, code_map: CodeMap):
    """Extract Python entities: FastAPI/Flask routes, Django models, Spark jobs, Airflow DAGs."""
    # FastAPI/Flask routes
    for match in re.finditer(r'@(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)', content):
        method, route = match.groups()
        name = f"{Path(path).stem}_{route.replace('/', '_')}"
        kg.entities.append(Entity(
            type="API",
            name=name,
            path=path,
            attrs={"method": method.upper(), "route": route, "framework": "FastAPI/Flask"}
        ))
    
    # Django models
    if 'models.Model' in content:
        for match in re.finditer(r'class\s+(\w+)\s*\(.*models\.Model', content):
            model_name = match.group(1)
            kg.entities.append(Entity(
                type="Database",
                name=model_name,
                path=path,
                attrs={"orm": "Django", "table": model_name.lower()}
            ))
    
    # SQLAlchemy models
    if 'declarative_base' in content or 'db.Model' in content:
        for match in re.finditer(r'class\s+(\w+)\s*\(.*(?:Base|db\.Model)', content):
            model_name = match.group(1)
            kg.entities.append(Entity(
                type="Database",
                name=model_name,
                path=path,
                attrs={"orm": "SQLAlchemy", "table": model_name.lower()}
            ))
    
    # Spark jobs
    if 'SparkSession' in content or 'SparkContext' in content:
        name = Path(path).stem
        kg.entities.append(Entity(
            type="Job",
            name=f"{name}_spark",
            path=path,
            attrs={"engine": "Spark"}
        ))
    
    # Airflow DAGs
    if 'DAG(' in content or 'from airflow' in content:
        for match in re.finditer(r'(?:dag\s*=\s*)?DAG\s*\(\s*["\']([^"\']+)', content):
            dag_id = match.group(1)
            kg.entities.append(Entity(
                type="Job",
                name=dag_id,
                path=path,
                attrs={"orchestrator": "Airflow", "type": "DAG"}
            ))
    
    # Celery tasks
    if '@task' in content or '@app.task' in content:
        for match in re.finditer(r'@(?:app\.)?task.*\ndef\s+(\w+)', content, re.MULTILINE | re.DOTALL):
            task_name = match.group(1)
            kg.entities.append(Entity(
                type="Job",
                name=task_name,
                path=path,
                attrs={"engine": "Celery", "async": True}
            ))
    
    # Kafka producers/consumers
    if 'KafkaProducer' in content:
        name = Path(path).stem
        kg.entities.append(Entity(
            type="Queue",
            name=f"{name}_producer",
            path=path,
            attrs={"type": "Kafka", "role": "producer"}
        ))
    if 'KafkaConsumer' in content:
        name = Path(path).stem
        kg.entities.append(Entity(
            type="Queue",
            name=f"{name}_consumer",
            path=path,
            attrs={"type": "Kafka", "role": "consumer"}
        ))


def _extract_javascript(kg: RepoKG, path: str, content: str, code_map: CodeMap):
    """Extract JS/TS entities: React components, Express routes, GraphQL schemas."""
    # React components - improved detection
    # Match function components
    for match in re.finditer(r'(?:export\s+)?(?:default\s+)?function\s+(\w+)\s*\([^)]*\)\s*{[^}]*return\s*[<(]', content):
        comp_name = match.group(1)
        kg.entities.append(Entity(
            type="UI",
            name=comp_name,
            path=path,
            attrs={"framework": "React"}
        ))
    
    # Match arrow function components
    for match in re.finditer(r'(?:export\s+)?(?:default\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>\s*[^{]*[<(]', content):
        comp_name = match.group(1)
        kg.entities.append(Entity(
            type="UI",
            name=comp_name,
            path=path,
            attrs={"framework": "React"}
        ))
    
    # Match class components
    for match in re.finditer(r'class\s+(\w+)\s+extends\s+(?:React\.)?Component', content):
        comp_name = match.group(1)
        kg.entities.append(Entity(
            type="UI",
            name=comp_name,
            path=path,
            attrs={"framework": "React"}
        ))
    
    # Express routes
    for match in re.finditer(r'(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)', content):
        method, route = match.groups()
        name = f"{Path(path).stem}_{route.replace('/', '_')}"
        kg.entities.append(Entity(
            type="API",
            name=name,
            path=path,
            attrs={"method": method.upper(), "route": route, "framework": "Express"}
        ))
    
    # GraphQL schemas
    if 'type Query' in content or 'type Mutation' in content:
        name = Path(path).stem
        kg.entities.append(Entity(
            type="API",
            name=f"{name}_graphql",
            path=path,
            attrs={"protocol": "GraphQL"}
        ))
    
    # Next.js API routes (from path structure)
    if '/pages/api/' in path or '/app/api/' in path:
        route = path.split('/api/')[-1].replace('.js', '').replace('.ts', '')
        kg.entities.append(Entity(
            type="API",
            name=f"api_{route.replace('/', '_')}",
            path=path,
            attrs={"framework": "Next.js", "route": f"/api/{route}"}
        ))


def _extract_java(kg: RepoKG, path: str, content: str, code_map: CodeMap):
    """Extract Java entities: Spring controllers, JPA entities, Kafka listeners."""
    # Spring REST controllers
    if '@RestController' in content or '@Controller' in content:
        name = Path(path).stem
        kg.entities.append(Entity(
            type="API",
            name=name,
            path=path,
            attrs={"framework": "Spring"}
        ))
        
        # Extract endpoints
        for match in re.finditer(r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\(["\']([^"\']+)', content):
            route = match.group(1)
            kg.entities.append(Entity(
                type="API",
                name=f"{name}_{route.replace('/', '_')}",
                path=path,
                attrs={"framework": "Spring", "route": route}
            ))
    
    # JPA entities
    if '@Entity' in content:
        for match in re.finditer(r'@Entity.*class\s+(\w+)', content, re.MULTILINE | re.DOTALL):
            entity_name = match.group(1)
            kg.entities.append(Entity(
                type="Database",
                name=entity_name,
                path=path,
                attrs={"orm": "JPA", "table": entity_name.lower()}
            ))
    
    # Kafka listeners
    if '@KafkaListener' in content:
        for match in re.finditer(r'@KafkaListener\(.*topics?\s*=\s*["\']([^"\']+)', content):
            topic = match.group(1)
            kg.entities.append(Entity(
                type="Queue",
                name=f"{Path(path).stem}_{topic}",
                path=path,
                attrs={"type": "Kafka", "topic": topic, "role": "consumer"}
            ))


def _extract_terraform(kg: RepoKG, path: str, content: str, code_map: CodeMap):
    """Extract Terraform resources and modules."""
    # Resources
    for match in re.finditer(r'resource\s+"([^"]+)"\s+"([^"]+)"', content):
        res_type, res_name = match.groups()
        entity_type = "Resource"
        
        # Map common resource types to entity types
        if 'database' in res_type or 'rds' in res_type or 'sql' in res_type:
            entity_type = "Database"
        elif 'function' in res_type or 'lambda' in res_type:
            entity_type = "Job"
        elif 'queue' in res_type or 'sqs' in res_type or 'sns' in res_type:
            entity_type = "Queue"
        elif 'storage' in res_type or 's3' in res_type or 'bucket' in res_type:
            entity_type = "Storage"
        
        kg.entities.append(Entity(
            type=entity_type,
            name=res_name,
            path=path,
            attrs={"tf_type": res_type, "iac": "Terraform"}
        ))
    
    # Modules
    for match in re.finditer(r'module\s+"([^"]+)"', content):
        mod_name = match.group(1)
        kg.entities.append(Entity(
            type="Module",
            name=mod_name,
            path=path,
            attrs={"iac": "Terraform"}
        ))


def _extract_sql(kg: RepoKG, path: str, content: str, code_map: CodeMap):
    """Extract SQL tables, views, and procedures."""
    # Tables
    for match in re.finditer(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(]+)', content, re.IGNORECASE):
        table_name = match.group(1).strip('`"[]')
        kg.entities.append(Entity(
            type="Table",
            name=table_name,
            path=path,
            attrs={"ddl": "table"}
        ))
    
    # Views
    for match in re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([^\s(]+)', content, re.IGNORECASE):
        view_name = match.group(1).strip('`"[]')
        kg.entities.append(Entity(
            type="Table",
            name=view_name,
            path=path,
            attrs={"ddl": "view"}
        ))
    
    # Procedures
    for match in re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+([^\s(]+)', content, re.IGNORECASE):
        proc_name = match.group(1).strip('`"[]')
        kg.entities.append(Entity(
            type="Job",
            name=proc_name,
            path=path,
            attrs={"type": "stored_procedure"}
        ))


def _extract_docker_compose(kg: RepoKG, path: str, content: str):
    """Extract services from docker-compose.yml."""
    import yaml
    try:
        data = yaml.safe_load(content)
        if 'services' in data:
            for service_name, config in data['services'].items():
                entity_type = "Service"
                attrs = {"container": True}
                
                # Infer type from image
                image = config.get('image', '')
                if 'postgres' in image or 'mysql' in image or 'mongo' in image:
                    entity_type = "Database"
                    attrs['engine'] = image.split(':')[0]
                elif 'redis' in image:
                    entity_type = "Cache"
                    attrs['engine'] = 'Redis'
                elif 'kafka' in image or 'rabbitmq' in image:
                    entity_type = "Queue"
                    attrs['engine'] = image.split(':')[0]
                
                kg.entities.append(Entity(
                    type=entity_type,
                    name=service_name,
                    path=path,
                    attrs=attrs
                ))
    except:
        kg.warnings.append(f"Failed to parse docker-compose at {path}")


def _extract_dockerfile(kg: RepoKG, path: str, content: str):
    """Extract service info from Dockerfile."""
    # Extract exposed ports
    ports = []
    for match in re.finditer(r'EXPOSE\s+(\d+)', content):
        ports.append(int(match.group(1)))
    
    if ports:
        name = Path(path).parent.name or "app"
        kg.entities.append(Entity(
            type="Service",
            name=f"{name}_container",
            path=path,
            attrs={"ports": ports, "container": True}
        ))


def refine_with_llm(kg: RepoKG, retrieve_fn: Callable) -> RepoKG:
    """Refine KG using LLM to classify entities and add missing relations.
    
    Args:
        kg: Initial knowledge graph
        retrieve_fn: Function to retrieve relevant code context
    
    Returns:
        Refined knowledge graph
    """
    # In production, this would:
    # 1. Group similar entities for classification
    # 2. Retrieve relevant code context
    # 3. Ask LLM to classify entities more precisely
    # 4. Ask LLM to identify missing relations with citations
    
    # For now, just apply some heuristic refinements
    _infer_relations(kg)
    return kg


def _infer_relations(kg: RepoKG):
    """Infer relations between entities based on patterns."""
    # API -> Database relations
    apis = kg.entities_by_type("API")
    dbs = kg.entities_by_type("Database")
    tables = kg.entities_by_type("Table")
    
    for api in apis:
        # If API and DB are in related files, assume API reads/writes DB
        for db in dbs + tables:
            if _files_related(api.path, db.path):
                kg.relations.append(Relation(
                    src=api.name,
                    dst=db.name,
                    kind="reads"
                ))
    
    # UI -> API relations
    uis = kg.entities_by_type("UI")
    for ui in uis:
        for api in apis:
            if _files_related(ui.path, api.path):
                kg.relations.append(Relation(
                    src=ui.name,
                    dst=api.name,
                    kind="calls"
                ))
    
    # Job -> Database/Queue relations
    jobs = kg.entities_by_type("Job")
    queues = kg.entities_by_type("Queue")
    
    for job in jobs:
        for db in dbs + tables:
            if _files_related(job.path, db.path):
                kg.relations.append(Relation(
                    src=job.name,
                    dst=db.name,
                    kind="writes"
                ))
        for queue in queues:
            if _files_related(job.path, queue.path):
                # Determine if producer or consumer
                if queue.attrs.get("role") == "producer":
                    kg.relations.append(Relation(
                        src=job.name,
                        dst=queue.name,
                        kind="produces"
                    ))
                else:
                    kg.relations.append(Relation(
                        src=queue.name,
                        dst=job.name,
                        kind="consumes"
                    ))


def _files_related(path1: str, path2: str) -> bool:
    """Check if two file paths are related (same dir or similar names)."""
    p1, p2 = Path(path1), Path(path2)
    # Same directory
    if p1.parent == p2.parent:
        return True
    # Similar names
    if p1.stem in p2.stem or p2.stem in p1.stem:
        return True
    # Common patterns
    if ('model' in p1.stem and 'controller' in p2.stem) or \
       ('model' in p2.stem and 'controller' in p1.stem):
        return True
    return False


def analyze_repo_kg(root: str, code_map: CodeMap, retrieve_fn: Optional[Callable] = None) -> RepoKG:
    """Main entry point: analyze repository and extract knowledge graph.
    
    Args:
        root: Repository root path
        code_map: Code map with files and dependencies
        retrieve_fn: Optional function to retrieve code for LLM refinement
    
    Returns:
        Repository knowledge graph
    """
    # Build initial KG with heuristics
    kg = build_seed_kg(root, code_map)
    
    # Refine with LLM if retriever available
    if retrieve_fn:
        kg = refine_with_llm(kg, retrieve_fn)
    
    return kg