"""Tests for documentation generation and run instructions extraction."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.services.docsgen import generate_docs, _generate_overview, _generate_api_docs
from src.services.run_hints import how_to_run
from src.analysis.kg_models import Entity, Relation, RepoKG
from src.core.types import CodeMap


class TestDocsGeneration:
    """Test documentation generation."""
    
    def create_test_kg(self) -> RepoKG:
        """Create a test knowledge graph."""
        return RepoKG(
            entities=[
                Entity(type="API", name="UserAPI", path="api/user.py", 
                       attrs={"method": "GET", "route": "/users"}),
                Entity(type="API", name="AuthAPI", path="api/auth.py",
                       attrs={"method": "POST", "route": "/login"}),
                Entity(type="Database", name="UserDB", path="models/user.py",
                       attrs={"orm": "SQLAlchemy", "table": "users"}),
                Entity(type="UI", name="UserList", path="frontend/UserList.jsx",
                       attrs={"framework": "React"}),
                Entity(type="Job", name="process_data", path="jobs/processor.py",
                       attrs={"engine": "Celery"}),
                Entity(type="Service", name="app", path="docker-compose.yml",
                       attrs={"container": True, "ports": [8000]}),
            ],
            relations=[
                Relation(src="UserAPI", dst="UserDB", kind="reads"),
                Relation(src="UserList", dst="UserAPI", kind="calls"),
            ]
        )
    
    def create_test_codemap(self) -> CodeMap:
        """Create a test code map."""
        return CodeMap(
            repo="test-repo",
            commit="abc123",
            files=["api/user.py", "api/auth.py", "models/user.py", "frontend/UserList.jsx"],
            deps={"api/user.py": ["models.user"], "frontend/UserList.jsx": ["api"]},
            symbol_index={"UserAPI": ["api/user.py"], "UserDB": ["models/user.py"]}
        )
    
    def test_generate_overview(self):
        """Test overview generation."""
        kg = self.create_test_kg()
        code_map = self.create_test_codemap()
        
        overview = _generate_overview(kg, code_map)
        
        assert "# Repository Overview" in overview
        assert "## Components" in overview
        assert "API**: 2 components" in overview
        assert "Database**: 1 components" in overview
        assert "## Technology Stack" in overview
        assert "React" in overview
        assert "SQLAlchemy" in overview
        assert "## Statistics" in overview
        assert "Files**: 4" in overview
    
    def test_generate_api_docs(self):
        """Test API documentation generation."""
        kg = self.create_test_kg()
        
        api_docs = _generate_api_docs(kg)
        
        assert "# API Documentation" in api_docs
        assert "## Endpoints" in api_docs
        assert "`GET /users`" in api_docs
        assert "`POST /login`" in api_docs
        assert "Implementation: `api/user.py`" in api_docs
        assert "Reads: UserDB" in api_docs
    
    def test_generate_docs_full_scope(self, tmp_path):
        """Test full documentation generation."""
        # Create test repo structure
        (tmp_path / "package.json").write_text('{"name": "test", "scripts": {"start": "node app.js"}}')
        (tmp_path / "requirements.txt").write_text("flask==2.0.0")
        (tmp_path / "docker-compose.yml").write_text("version: '3'\nservices:\n  app:\n    build: .")
        
        kg = self.create_test_kg()
        code_map = self.create_test_codemap()
        
        docs = generate_docs(str(tmp_path), "full", kg, code_map)
        
        assert "# Repository Overview" in docs
        assert "# Architecture" in docs
        assert "# Setup Instructions" in docs
        assert "# API Documentation" in docs
        assert "# Database Schema" in docs
        assert "# Infrastructure" in docs
        assert "# Configuration" in docs
        assert "# Documentation Gaps" in docs
    
    def test_generate_docs_setup_scope(self, tmp_path):
        """Test setup scope documentation."""
        kg = self.create_test_kg()
        code_map = self.create_test_codemap()
        
        docs = generate_docs(str(tmp_path), "setup", kg, code_map)
        
        assert "# Repository Overview" in docs
        assert "# Architecture" in docs
        assert "# Setup Instructions" in docs
        assert "# API Documentation" not in docs
        assert "# Infrastructure" not in docs
    
    def test_generate_docs_api_scope(self, tmp_path):
        """Test API scope documentation."""
        kg = self.create_test_kg()
        code_map = self.create_test_codemap()
        
        docs = generate_docs(str(tmp_path), "api", kg, code_map)
        
        assert "# API Documentation" in docs
        assert "# Setup Instructions" not in docs
        assert "# Infrastructure" not in docs
    
    def test_generate_docs_with_mermaid(self):
        """Test that Mermaid diagrams are included."""
        kg = self.create_test_kg()
        code_map = self.create_test_codemap()
        
        docs = generate_docs(".", "full", kg, code_map)
        
        assert "```mermaid" in docs
        assert "graph LR" in docs
        assert "```" in docs
    
    def test_docs_citations(self):
        """Test that citations are included."""
        kg = self.create_test_kg()
        code_map = self.create_test_codemap()
        
        docs = generate_docs(".", "full", kg, code_map)
        
        # Check for file path citations
        assert "`api/user.py`" in docs
        assert "`models/user.py`" in docs
    
    def test_docs_gaps_detection(self):
        """Test documentation gaps detection."""
        # Empty KG to trigger gaps
        kg = RepoKG()
        code_map = CodeMap(repo="test", commit="abc", files=[], deps={}, symbol_index={})
        
        docs = generate_docs(".", "full", kg, code_map)
        
        assert "# Documentation Gaps" in docs
        assert "No UI/Frontend components detected" in docs
        assert "No API endpoints detected" in docs
        assert "No database entities detected" in docs


class TestRunHints:
    """Test run instructions extraction."""
    
    def test_extract_npm_scripts(self, tmp_path):
        """Test extraction from package.json."""
        package_json = {
            "name": "test-app",
            "scripts": {
                "start": "node server.js",
                "dev": "nodemon server.js",
                "test": "jest",
                "build": "webpack"
            },
            "dependencies": {
                "express": "^4.0.0"
            }
        }
        
        import json
        (tmp_path / "package.json").write_text(json.dumps(package_json))
        
        result = how_to_run(str(tmp_path))
        
        assert "npm install" in result["local"]
        assert any("npm run build" in cmd for cmd in result["local"])
        assert any("npm run start" in cmd for cmd in result["local"])
        assert any("npm run test" in cmd for cmd in result["tests"])
    
    def test_extract_python_setup(self, tmp_path):
        """Test Python setup extraction."""
        # requirements.txt
        (tmp_path / "requirements.txt").write_text("flask==2.0.0\npytest==7.0.0")
        
        # pyproject.toml with Poetry
        pyproject = """
[tool.poetry]
name = "test-app"

[tool.poetry.scripts]
app = "app:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        (tmp_path / "pyproject.toml").write_text(pyproject)
        
        # main.py
        (tmp_path / "main.py").write_text("print('hello')")
        
        result = how_to_run(str(tmp_path))
        
        assert "pip install -r requirements.txt" in result["local"]
        assert "poetry install" in result["local"]
        assert "poetry run app" in result["local"]
        assert "python main.py" in result["local"]
        assert "pytest" in result["tests"]
    
    def test_extract_makefile(self, tmp_path):
        """Test Makefile target extraction."""
        makefile = """
all: build

build:
\tgcc -o app main.c

run:
\t./app

test:
\tpytest tests/

docker:
\tdocker build -t app .

clean:
\trm -rf build/
"""
        (tmp_path / "Makefile").write_text(makefile)
        
        result = how_to_run(str(tmp_path))
        
        assert "make build" in result["local"]
        assert "make run" in result["local"]
        assert "make test" in result["tests"]
        assert "make docker" in result["docker"]
    
    def test_extract_docker(self, tmp_path):
        """Test Docker commands extraction."""
        # docker-compose.yml
        compose = """
version: '3'
services:
  web:
    build: .
    ports:
      - "8000:8000"
  postgres:
    image: postgres:14
    ports:
      - "5432:5432"
"""
        (tmp_path / "docker-compose.yml").write_text(compose)
        
        # Dockerfile
        dockerfile = """
FROM python:3.9
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
"""
        (tmp_path / "Dockerfile").write_text(dockerfile)
        
        result = how_to_run(str(tmp_path))
        
        assert "docker-compose up" in result["docker"]
        assert "docker-compose down" in result["docker"]
        assert any("docker build" in cmd for cmd in result["docker"])
        assert any("8000:8000" in cmd for cmd in result["docker"])
    
    def test_extract_gradle_maven(self, tmp_path):
        """Test Gradle/Maven extraction."""
        # build.gradle
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'")
        
        # pom.xml
        pom = """
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter</artifactId>
    </dependency>
  </dependencies>
</project>
"""
        (tmp_path / "pom.xml").write_text(pom)
        
        result = how_to_run(str(tmp_path))
        
        assert any("gradle build" in cmd or "gradlew build" in cmd for cmd in result["local"])
        assert any("gradle test" in cmd or "gradlew test" in cmd for cmd in result["tests"])
        assert any("mvn clean install" in cmd or "mvnw clean install" in cmd for cmd in result["local"])
        assert any("spring-boot:run" in cmd for cmd in result["local"])
    
    def test_extract_go_mod(self, tmp_path):
        """Test Go module extraction."""
        (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.19")
        (tmp_path / "main.go").write_text("package main\n\nfunc main() {}")
        
        # Create cmd directory
        cmd_dir = tmp_path / "cmd" / "server"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "main.go").write_text("package main")
        
        result = how_to_run(str(tmp_path))
        
        assert "go mod download" in result["local"]
        assert "go build" in result["local"]
        assert "go run ." in result["local"]
        assert "go run main.go" in result["local"]
        assert any("cmd/server" in cmd for cmd in result["local"])
        assert "go test ./..." in result["tests"]
    
    def test_extract_env_files(self, tmp_path):
        """Test environment file extraction."""
        # .env.example
        env_example = """
DATABASE_URL=postgresql://localhost/db
API_KEY=your-api-key
SECRET_KEY=change-me
"""
        (tmp_path / ".env.example").write_text(env_example)
        
        result = how_to_run(str(tmp_path))
        
        assert any("cp .env.example .env" in cmd for cmd in result["env"])
        assert any("Edit .env" in cmd for cmd in result["env"])
        assert any("DATABASE_URL" in cmd for cmd in result["env"])
    
    def test_identify_gaps(self, tmp_path):
        """Test gaps identification."""
        # Empty directory - should identify gaps
        result = how_to_run(str(tmp_path))
        
        assert len(result["gaps"]) > 0
        assert "No clear run instructions found" in result["gaps"]
        assert "No dependency manifest found" in result["gaps"]
        assert any("No README" in gap for gap in result["gaps"])
        
        # Add some Python files without clear entry
        (tmp_path / "utils.py").write_text("def helper(): pass")
        (tmp_path / "src").mkdir()
        
        result = how_to_run(str(tmp_path))
        
        assert any("Python files found" in gap for gap in result["gaps"])
        assert any("src/" in gap for gap in result["gaps"])
    
    def test_mixed_repository(self, tmp_path):
        """Test extraction from a mixed technology repository."""
        # Create a realistic mixed repo
        import json
        
        # Frontend (React)
        frontend = tmp_path / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text(json.dumps({
            "scripts": {"start": "react-scripts start", "test": "jest"}
        }))
        
        # Backend (Python)
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / "requirements.txt").write_text("fastapi\nuvicorn")
        (backend / "main.py").write_text("# FastAPI app")
        
        # Docker
        (tmp_path / "docker-compose.yml").write_text("""
version: '3'
services:
  frontend:
    build: ./frontend
  backend:
    build: ./backend
""")
        
        # Makefile
        (tmp_path / "Makefile").write_text("""
dev:
\tdocker-compose up
test:
\tcd frontend && npm test
\tcd backend && pytest
""")
        
        result = how_to_run(str(tmp_path))
        
        # Should extract from all sources
        assert any("npm" in cmd for cmd in result["local"])
        assert any("pip" in cmd for cmd in result["local"])
        assert "docker-compose up" in result["docker"]
        assert any("make" in cmd for cmd in result["local"] + result["tests"])  # Make commands should be found