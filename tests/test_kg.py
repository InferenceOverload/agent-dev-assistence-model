"""Tests for Knowledge Graph extraction and diagram generation."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.analysis.kg_models import Entity, Relation, RepoKG
from src.analysis.kg_extract import (
    build_seed_kg, 
    analyze_repo_kg,
    refine_with_llm,
    _files_related
)
from src.tools.diagram_components import mermaid_from_kg
from src.tools.diagram_sequence import sequence_from_kg
from src.core.types import CodeMap


class TestKGModels:
    """Test KG data models."""
    
    def test_entity_creation(self):
        """Test Entity model creation."""
        entity = Entity(
            type="API",
            name="UserService",
            path="src/api/user.py",
            attrs={"method": "POST", "route": "/users"}
        )
        
        assert entity.type == "API"
        assert entity.name == "UserService"
        assert entity.path == "src/api/user.py"
        assert entity.attrs["method"] == "POST"
    
    def test_relation_creation(self):
        """Test Relation model creation."""
        rel = Relation(
            src="UserAPI",
            dst="UserDB",
            kind="reads",
            attrs={"protocol": "SQL"}
        )
        
        assert rel.src == "UserAPI"
        assert rel.dst == "UserDB"
        assert rel.kind == "reads"
    
    def test_repo_kg_operations(self):
        """Test RepoKG operations."""
        kg = RepoKG()
        
        # Add entities
        api = Entity(type="API", name="UserAPI", path="api.py")
        db = Entity(type="Database", name="UserDB", path="models.py")
        kg.entities = [api, db]
        
        # Add relation
        rel = Relation(src="UserAPI", dst="UserDB", kind="reads")
        kg.relations = [rel]
        
        # Test lookups
        assert kg.entity_by_name("UserAPI") == api
        assert kg.entities_by_type("API") == [api]
        assert kg.relations_from("UserAPI") == [rel]
        assert kg.relations_to("UserDB") == [rel]
    
    def test_kg_deduplication(self):
        """Test KG merge_duplicates."""
        kg = RepoKG()
        
        # Add duplicate entities
        kg.entities = [
            Entity(type="API", name="UserAPI", path="api1.py", attrs={"v": "1"}),
            Entity(type="API", name="UserAPI", path="api2.py", attrs={"v": "2"}),
        ]
        
        # Add duplicate relations
        kg.relations = [
            Relation(src="A", dst="B", kind="calls"),
            Relation(src="A", dst="B", kind="calls"),
        ]
        
        kg.merge_duplicates()
        
        assert len(kg.entities) == 1
        assert len(kg.relations) == 1
        assert kg.entities[0].attrs["v"] == "2"  # Later attr wins


class TestKGExtraction:
    """Test KG extraction from code."""
    
    def create_test_repo(self, tmpdir):
        """Create a mixed test repository."""
        repo = Path(tmpdir)
        
        # Python: FastAPI + SQLAlchemy
        (repo / "src" / "api").mkdir(parents=True)
        (repo / "src" / "api" / "users.py").write_text("""
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
async def get_users():
    return []

@router.post("/users")
async def create_user():
    return {}
""")
        
        (repo / "src" / "models").mkdir(parents=True)
        (repo / "src" / "models" / "user.py").write_text("""
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String)
""")
        
        # JavaScript: React + Express
        (repo / "frontend").mkdir()
        (repo / "frontend" / "UserList.jsx").write_text("""
import React from 'react';

export default function UserList() {
    return <div>Users</div>;
}
""")
        
        (repo / "backend").mkdir()
        (repo / "backend" / "server.js").write_text("""
const express = require('express');
const app = express();

app.get('/api/users', (req, res) => {
    res.json([]);
});

app.post('/api/users', (req, res) => {
    res.json({});
});
""")
        
        # Terraform
        (repo / "infra").mkdir()
        (repo / "infra" / "main.tf").write_text("""
resource "aws_rds_instance" "users_db" {
  identifier = "users-database"
  engine     = "postgres"
}

resource "aws_lambda_function" "user_processor" {
  function_name = "process-users"
  runtime       = "python3.9"
}
""")
        
        # SQL
        (repo / "schema").mkdir()
        (repo / "schema" / "users.sql").write_text("""
CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100)
);

CREATE VIEW active_users AS
SELECT * FROM users WHERE active = true;
""")
        
        # Docker
        (repo / "docker-compose.yml").write_text("""
version: '3'
services:
  postgres:
    image: postgres:14
    ports:
      - "5432:5432"
  redis:
    image: redis:7
  app:
    build: .
    ports:
      - "8000:8000"
""")
        
        return str(repo)
    
    def test_build_seed_kg(self, tmp_path):
        """Test building initial KG from repo."""
        repo = self.create_test_repo(tmp_path)
        
        # Create code map
        code_map = CodeMap(
            repo="test",
            commit="abc",
            files=[
                "src/api/users.py",
                "src/models/user.py",
                "frontend/UserList.jsx",
                "backend/server.js",
                "infra/main.tf",
                "schema/users.sql",
                "docker-compose.yml"
            ],
            deps={},
            symbol_index={}
        )
        
        kg = build_seed_kg(repo, code_map)
        
        # Check entities were extracted
        assert len(kg.entities) > 0
        
        # Check for specific entity types
        entity_types = {e.type for e in kg.entities}
        assert "API" in entity_types  # FastAPI/Express endpoints
        assert "Database" in entity_types  # SQLAlchemy model or Terraform RDS
        assert "UI" in entity_types  # React component
        assert "Job" in entity_types or "Resource" in entity_types  # Lambda
        assert "Table" in entity_types  # SQL table
        assert "Service" in entity_types or "Cache" in entity_types  # Docker services
        
        # Check some entities have expected attributes
        apis = kg.entities_by_type("API")
        assert any("route" in api.attrs for api in apis)
    
    def test_python_extraction(self):
        """Test Python-specific extraction."""
        kg = RepoKG()
        content = """
from fastapi import FastAPI
from sqlalchemy import Column
from airflow import DAG

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

class User(db.Model):
    id = Column(Integer)

dag = DAG('data_pipeline', schedule='@daily')

@task
def process_data():
    pass
"""
        
        from src.analysis.kg_extract import _extract_python
        code_map = CodeMap(repo="test", commit="abc", files=[], deps={}, symbol_index={})
        _extract_python(kg, "app.py", content, code_map)
        
        # Check extracted entities
        entity_types = {e.type for e in kg.entities}
        assert "API" in entity_types  # FastAPI route
        assert "Database" in entity_types  # SQLAlchemy model
        assert "Job" in entity_types  # Airflow DAG or Celery task
    
    def test_javascript_extraction(self):
        """Test JavaScript/TypeScript extraction."""
        kg = RepoKG()
        content = """
import React from 'react';
import express from 'express';

export function UserProfile() {
    return <div>Profile</div>;
}

const app = express();
app.post('/api/login', handler);

type Query {
    user(id: ID!): User
}
"""
        
        from src.analysis.kg_extract import _extract_javascript
        code_map = CodeMap(repo="test", commit="abc", files=[], deps={}, symbol_index={})
        _extract_javascript(kg, "app.jsx", content, code_map)
        
        # Check extracted entities
        entity_types = {e.type for e in kg.entities}
        assert "UI" in entity_types  # React component
        assert "API" in entity_types  # Express route or GraphQL
    
    def test_terraform_extraction(self):
        """Test Terraform extraction."""
        kg = RepoKG()
        content = """
resource "aws_s3_bucket" "data_lake" {
  bucket = "my-data-lake"
}

resource "aws_sqs_queue" "task_queue" {
  name = "task-queue"
}

module "vpc" {
  source = "./modules/vpc"
}
"""
        
        from src.analysis.kg_extract import _extract_terraform
        code_map = CodeMap(repo="test", commit="abc", files=[], deps={}, symbol_index={})
        _extract_terraform(kg, "main.tf", content, code_map)
        
        # Check extracted entities
        entity_types = {e.type for e in kg.entities}
        assert "Storage" in entity_types  # S3 bucket
        assert "Queue" in entity_types  # SQS queue
        assert "Module" in entity_types  # Terraform module
    
    def test_files_related(self):
        """Test file relationship detection."""
        # Same directory
        assert _files_related("src/api/user.py", "src/api/auth.py")
        
        # Similar names
        assert _files_related("user_model.py", "user_controller.py")
        
        # Model-controller pattern
        assert _files_related("models/user.py", "controllers/user.py")
        
        # Not related
        assert not _files_related("frontend/app.js", "backend/db.py")
    
    def test_refine_with_llm_mock(self):
        """Test LLM refinement with mocked retriever."""
        kg = RepoKG(
            entities=[
                Entity(type="API", name="UserAPI", path="api.py"),
                Entity(type="Database", name="UserDB", path="api.py"),
            ]
        )
        
        mock_retriever = Mock()
        refined = refine_with_llm(kg, mock_retriever)
        
        # Should infer relations
        assert len(refined.relations) > 0
        
        # API should read from DB (same file heuristic)
        api_relations = refined.relations_from("UserAPI")
        assert any(r.dst == "UserDB" and r.kind == "reads" for r in api_relations)


class TestDiagramGeneration:
    """Test diagram generation from KG."""
    
    def test_mermaid_from_kg_simple(self):
        """Test simple component diagram generation."""
        kg = RepoKG(
            entities=[
                Entity(type="UI", name="WebApp", path="app.jsx"),
                Entity(type="API", name="Backend", path="server.py"),
                Entity(type="Database", name="PostgresDB", path="models.py"),
            ],
            relations=[
                Relation(src="WebApp", dst="Backend", kind="calls"),
                Relation(src="Backend", dst="PostgresDB", kind="reads"),
            ]
        )
        
        diagram = mermaid_from_kg(kg)
        
        assert "graph LR" in diagram
        assert "WebApp" in diagram
        assert "Backend" in diagram
        assert "PostgresDB" in diagram
        assert "calls" in diagram
        assert "reads" in diagram
    
    def test_mermaid_from_kg_collapsed(self):
        """Test diagram collapsing when too many nodes."""
        # Create many entities
        entities = []
        for i in range(20):
            entities.append(Entity(
                type="API" if i < 10 else "Database",
                name=f"Entity{i}",
                path=f"file{i}.py"
            ))
        
        kg = RepoKG(entities=entities)
        diagram = mermaid_from_kg(kg, max_nodes=12)
        
        # Should show aggregated groups
        assert "API_group" in diagram
        assert "Database_group" in diagram
        assert "(10 items)" in diagram
    
    def test_sequence_from_kg(self):
        """Test sequence diagram generation."""
        kg = RepoKG(
            entities=[
                Entity(type="UI", name="LoginForm", path="login.jsx"),
                Entity(type="API", name="AuthAPI", path="auth.py"),
                Entity(type="Database", name="UserDB", path="db.py"),
                Entity(type="Queue", name="EventQueue", path="events.py"),
            ],
            relations=[
                Relation(src="LoginForm", dst="AuthAPI", kind="calls"),
                Relation(src="AuthAPI", dst="UserDB", kind="reads"),
                Relation(src="AuthAPI", dst="EventQueue", kind="produces"),
            ]
        )
        
        diagram = sequence_from_kg(kg, "User login flow")
        
        assert "sequenceDiagram" in diagram
        assert "Use Case: User login flow" in diagram
        assert "actor LoginForm" in diagram
        assert "participant AuthAPI" in diagram
        assert "participant UserDB" in diagram
        assert "->>+" in diagram  # Interaction arrow
    
    def test_sequence_from_kg_no_ui(self):
        """Test sequence diagram when no UI entities."""
        kg = RepoKG(
            entities=[
                Entity(type="API", name="DataAPI", path="api.py"),
                Entity(type="Database", name="DataDB", path="db.py"),
            ],
            relations=[
                Relation(src="DataAPI", dst="DataDB", kind="reads"),
            ]
        )
        
        diagram = sequence_from_kg(kg, "Data processing")
        
        assert "sequenceDiagram" in diagram
        assert "actor User" in diagram  # Default actor
        assert "participant DataAPI" in diagram


class TestAgentIntegration:
    """Test agent integration with KG tools."""
    
    @patch("src.agents.repo_ingestor.ingest_repo")
    @patch("src.analysis.kg_extract.analyze_repo_kg")
    def test_analyze_repo_kg_tool(self, mock_analyze, mock_ingest):
        """Test analyze_repo_kg agent tool."""
        from src.agents.agent import analyze_repo_kg
        
        # Mock returns
        mock_code_map = CodeMap(
            repo="test", commit="abc", files=[], deps={}, symbol_index={}
        )
        mock_ingest.return_value = (mock_code_map, [])
        
        mock_kg = RepoKG(
            entities=[Entity(type="API", name="TestAPI", path="test.py")],
            relations=[],
            warnings=["test warning"]
        )
        mock_analyze.return_value = mock_kg
        
        result = analyze_repo_kg(".")
        
        assert "entities" in result
        assert "relations" in result
        assert "warnings" in result
        assert len(result["entities"]) == 1
        assert result["entities"][0]["type"] == "API"
    
    @patch("src.agents.repo_ingestor.ingest_repo")
    @patch("src.analysis.kg_extract.analyze_repo_kg")
    def test_arch_diagram_plus_tool(self, mock_analyze, mock_ingest):
        """Test arch_diagram_plus agent tool."""
        from src.agents.agent import arch_diagram_plus
        
        mock_code_map = CodeMap(
            repo="test", commit="abc", files=[], deps={}, symbol_index={}
        )
        mock_ingest.return_value = (mock_code_map, [])
        
        mock_kg = RepoKG(
            entities=[Entity(type="API", name="TestAPI", path="test.py")]
        )
        mock_analyze.return_value = mock_kg
        
        result = arch_diagram_plus(".")
        
        assert "mermaid" in result
        assert "graph LR" in result["mermaid"]
    
    @patch("src.agents.repo_ingestor.ingest_repo")
    @patch("src.analysis.kg_extract.analyze_repo_kg")
    def test_sequence_diagram_tool(self, mock_analyze, mock_ingest):
        """Test sequence_diagram agent tool."""
        from src.agents.agent import sequence_diagram
        
        mock_code_map = CodeMap(
            repo="test", commit="abc", files=[], deps={}, symbol_index={}
        )
        mock_ingest.return_value = (mock_code_map, [])
        
        mock_kg = RepoKG(
            entities=[Entity(type="UI", name="TestUI", path="test.jsx")]
        )
        mock_analyze.return_value = mock_kg
        
        result = sequence_diagram(".", "Test flow")
        
        assert "mermaid" in result
        assert "sequenceDiagram" in result["mermaid"]
        assert "Use Case: Test flow" in result["mermaid"]