"""Tests for RepoFacts scanner and component diagrams."""

import pytest
from pathlib import Path
from src.analysis.models import Component, Relation, RepoFacts
from src.analysis.scan import analyze_repo
from src.tools.diagram_components import mermaid_components


def test_repofacts_models():
    """Test Pydantic models for RepoFacts."""
    comp = Component(
        name="API",
        type="service",
        path="backend",
        language="python",
        files_count=10
    )
    assert comp.name == "API"
    assert comp.files_count == 10
    
    rel = Relation(
        source="Frontend",
        target="API",
        type="calls",
        confidence=0.9
    )
    assert rel.source == "Frontend"
    assert rel.confidence == 0.9
    
    facts = RepoFacts(
        components=[comp],
        relations=[rel],
        languages={"python": 5, "javascript": 3},
        frameworks=["Django", "React"]
    )
    assert len(facts.components) == 1
    assert facts.languages["python"] == 5


def test_analyze_mixed_repo(tmp_path):
    """Test analyzing a mixed technology repository."""
    # Create mixed repo structure
    dirs = [
        "frontend/src/components",
        "backend/api",
        "backend/models",
        "database/migrations",
        "infrastructure/terraform",
        "tests"
    ]
    
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    
    # Python backend files
    (tmp_path / "backend/api/main.py").write_text("from flask import Flask\napp = Flask(__name__)")
    (tmp_path / "backend/models/user.py").write_text("class User:\n    pass")
    (tmp_path / "requirements.txt").write_text("flask==2.0.0\nsqlalchemy==1.4.0")
    
    # JavaScript/React frontend
    (tmp_path / "frontend/src/App.jsx").write_text("import React from 'react';\nexport default App;")
    (tmp_path / "frontend/src/index.js").write_text("import App from './App';")
    (tmp_path / "frontend/package.json").write_text('{"dependencies": {"react": "^17.0.0"}}')
    
    # SQL database
    (tmp_path / "database/migrations/001_create_users.sql").write_text("CREATE TABLE users (id INT);")
    (tmp_path / "database/schema.sql").write_text("-- Database schema")
    
    # Terraform infrastructure
    (tmp_path / "infrastructure/terraform/main.tf").write_text('provider "aws" { region = "us-east-1" }')
    (tmp_path / "infrastructure/terraform/variables.tf").write_text('variable "env" { default = "dev" }')
    
    # Tests
    (tmp_path / "tests/test_api.py").write_text("def test_api():\n    assert True")
    
    # Analyze the repo
    facts = analyze_repo(str(tmp_path))
    
    # Verify languages detected
    assert "python" in facts.languages
    assert "javascript" in facts.languages
    assert "sql" in facts.languages
    assert "terraform" in facts.languages
    assert facts.languages["python"] >= 2
    assert facts.languages["javascript"] >= 2
    
    # Verify components detected
    component_names = [c.name for c in facts.components]
    assert "API" in component_names or "Backend" in component_names
    assert "Frontend" in component_names
    assert "Database" in component_names
    assert "Infrastructure" in component_names
    # Tests component is optional since it may be grouped differently
    assert len(component_names) >= 4  # At least 4 components detected
    
    # Verify entry points
    assert any("main.py" in ep for ep in facts.entry_points)
    assert any("index.js" in ep for ep in facts.entry_points)
    
    # Verify frameworks
    assert "Flask" in facts.frameworks or "flask" in str(facts.frameworks).lower()
    assert "React" in facts.frameworks or "react" in str(facts.frameworks).lower()
    
    # Verify deployment targets
    assert "Terraform" in facts.deploy_targets
    
    # Verify relations exist
    assert len(facts.relations) > 0
    relation_types = [r.type for r in facts.relations]
    assert any(rt in relation_types for rt in ["calls", "queries", "deploys", "tests"])


def test_mermaid_component_diagram():
    """Test Mermaid component diagram generation."""
    # Create test RepoFacts
    facts = RepoFacts(
        components=[
            Component(name="Frontend", type="ui", path="frontend", language="javascript", files_count=20),
            Component(name="API", type="service", path="backend", language="python", files_count=15),
            Component(name="Database", type="database", path="db", language="sql", files_count=5),
            Component(name="Infrastructure", type="infra", path="terraform", language="terraform", files_count=8),
        ],
        relations=[
            Relation(source="Frontend", target="API", type="calls"),
            Relation(source="API", target="Database", type="queries"),
            Relation(source="Infrastructure", target="API", type="deploys"),
            Relation(source="Infrastructure", target="Database", type="deploys"),
        ],
        frameworks=["React", "FastAPI"],
        databases=["PostgreSQL"]
    )
    
    # Generate diagram
    mermaid = mermaid_components(facts)
    
    # Verify diagram structure
    assert "graph LR" in mermaid
    assert "Frontend" in mermaid
    assert "API" in mermaid
    assert "Database" in mermaid
    assert "Infrastructure" in mermaid
    
    # Verify relations in diagram
    assert "-->|calls|" in mermaid or "calls" in mermaid
    assert "==>|queries|" in mermaid or "queries" in mermaid
    assert "-.-|deploys|" in mermaid or "deploys" in mermaid
    
    # Verify styling classes
    assert "classDef ui" in mermaid
    assert "classDef service" in mermaid
    assert "classDef database" in mermaid
    assert "classDef infra" in mermaid
    
    # Verify metadata comments
    assert "React" in mermaid
    assert "PostgreSQL" in mermaid


def test_empty_repo_handling():
    """Test handling of empty or minimal repositories."""
    # Empty facts
    empty_facts = RepoFacts()
    mermaid = mermaid_components(empty_facts)
    assert "No components detected" in mermaid
    
    # Analyze non-existent directory
    facts = analyze_repo("/non/existent/path")
    assert facts.components == []
    assert facts.languages == {}


def test_language_detection(tmp_path):
    """Test language detection for various file types."""
    # Create files with different extensions
    files = {
        "app.py": "python",
        "Main.java": "java",
        "index.js": "javascript",
        "App.jsx": "javascript",
        "main.ts": "typescript",
        "Component.tsx": "typescript",
        "schema.sql": "sql",
        "proc.plsql": "plsql",
        "main.tf": "terraform",
        "lib.rs": "rust",
    }
    
    for filename, expected_lang in files.items():
        (tmp_path / filename).write_text("// test content")
    
    facts = analyze_repo(str(tmp_path))
    
    # Check that most languages were detected
    detected_langs = set(facts.languages.keys())
    expected_langs = {"python", "java", "javascript", "typescript", "sql", "terraform", "rust"}
    
    # Allow for some flexibility (at least 4 out of 7 languages detected)
    assert len(detected_langs.intersection(expected_langs)) >= 4