"""Extract run instructions from repository files."""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


def how_to_run(root: str = ".") -> Dict[str, List[str]]:
    """Extract runnable instructions from repository.
    
    Parses package.json scripts, Makefile targets, docker-compose, 
    pyproject/pip, Gradle/Maven, etc.
    
    Args:
        root: Repository root path
    
    Returns:
        Dict with local, docker, tests, env, and gaps instructions
    """
    root_path = Path(root)
    
    result = {
        "local": [],
        "docker": [],
        "tests": [],
        "env": [],
        "gaps": []
    }
    
    # Extract from various sources
    _extract_npm_scripts(root_path, result)
    _extract_python_setup(root_path, result)
    _extract_makefile(root_path, result)
    _extract_docker(root_path, result)
    _extract_gradle_maven(root_path, result)
    _extract_go_mod(root_path, result)
    _extract_env_files(root_path, result)
    
    # Identify gaps
    _identify_gaps(root_path, result)
    
    return result


def _extract_npm_scripts(root_path: Path, result: Dict[str, List[str]]):
    """Extract scripts from package.json."""
    # Check root and common subdirectories
    package_locations = [
        root_path / "package.json",
        root_path / "frontend" / "package.json",
        root_path / "client" / "package.json",
        root_path / "web" / "package.json",
    ]
    
    for package_json in package_locations:
        if not package_json.exists():
            continue
        
        try:
            with open(package_json) as f:
                data = json.load(f)
            
            scripts = data.get("scripts", {})
            
            # Add directory prefix if in subdirectory
            prefix = ""
            if package_json.parent != root_path:
                prefix = f"cd {package_json.parent.relative_to(root_path)} && "
            
            # Common script patterns
            for script_name, command in scripts.items():
                if script_name in ["start", "dev", "serve"]:
                    result["local"].append(f"{prefix}npm run {script_name}  # {command}")
                elif script_name in ["test", "test:unit", "test:e2e"]:
                    result["tests"].append(f"{prefix}npm run {script_name}  # {command}")
                elif script_name in ["build", "compile"]:
                    result["local"].insert(0, f"{prefix}npm run {script_name}  # {command}")
            
            # Dependencies install
            if "dependencies" in data or "devDependencies" in data:
                result["local"].insert(0, f"{prefix}npm install")
            
        except (json.JSONDecodeError, KeyError):
            result["gaps"].append(f"Failed to parse {package_json}")


def _extract_python_setup(root_path: Path, result: Dict[str, List[str]]):
    """Extract Python setup instructions."""
    # Check root and common subdirectories for requirements.txt
    req_locations = [
        root_path / "requirements.txt",
        root_path / "backend" / "requirements.txt",
        root_path / "server" / "requirements.txt",
        root_path / "api" / "requirements.txt",
    ]
    
    for req_file in req_locations:
        if req_file.exists():
            prefix = ""
            if req_file.parent != root_path:
                prefix = f"cd {req_file.parent.relative_to(root_path)} && "
            result["local"].insert(0, f"{prefix}pip install -r requirements.txt")
    
    # pyproject.toml (Poetry/setuptools)
    pyproject = root_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        
        if "[tool.poetry]" in content:
            result["local"].insert(0, "poetry install")
            
            # Extract poetry scripts
            if "[tool.poetry.scripts]" in content:
                # Parse scripts section
                scripts_match = re.search(r'\[tool\.poetry\.scripts\](.*?)\n\[', content, re.DOTALL)
                if scripts_match:
                    for line in scripts_match.group(1).split('\n'):
                        if '=' in line:
                            script_name = line.split('=')[0].strip()
                            if script_name:
                                result["local"].append(f"poetry run {script_name}")
        
        elif "[project]" in content:
            # Modern setuptools
            result["local"].insert(0, "pip install -e .")
        
        # Extract test commands
        if "pytest" in content:
            result["tests"].append("pytest")
        if "unittest" in content:
            result["tests"].append("python -m unittest")
    
    # setup.py
    if (root_path / "setup.py").exists():
        result["local"].insert(0, "pip install -e .")
    
    # Pipfile
    if (root_path / "Pipfile").exists():
        result["local"].insert(0, "pipenv install")
        result["local"].append("pipenv shell")
    
    # Common Python run files
    for run_file in ["main.py", "app.py", "run.py", "server.py", "manage.py"]:
        if (root_path / run_file).exists():
            if run_file == "manage.py":
                result["local"].append(f"python {run_file} runserver")
            else:
                result["local"].append(f"python {run_file}")


def _extract_makefile(root_path: Path, result: Dict[str, List[str]]):
    """Extract Makefile targets."""
    makefile = root_path / "Makefile"
    if not makefile.exists():
        makefile = root_path / "makefile"
    
    if makefile.exists():
        content = makefile.read_text()
        
        # Extract targets (lines starting with target:)
        targets = re.findall(r'^([a-zA-Z0-9_-]+):', content, re.MULTILINE)
        
        for target in targets:
            if target in ["all", "build", "compile"]:
                result["local"].insert(0, f"make {target}")
            elif target in ["run", "start", "serve"]:
                result["local"].append(f"make {target}")
            elif target in ["test", "tests", "check"]:
                result["tests"].append(f"make {target}")
            elif target in ["docker", "docker-build", "container"]:
                result["docker"].append(f"make {target}")
            elif target in ["clean", "install", "setup"]:
                result["local"].insert(0, f"make {target}")


def _extract_docker(root_path: Path, result: Dict[str, List[str]]):
    """Extract Docker commands."""
    # docker-compose.yml/yaml
    compose_file = root_path / "docker-compose.yml"
    if not compose_file.exists():
        compose_file = root_path / "docker-compose.yaml"
    
    if compose_file.exists():
        result["docker"].append("docker-compose up")
        result["docker"].append("docker-compose up -d  # detached mode")
        result["docker"].append("docker-compose down")
        
        # Parse services
        try:
            import yaml
            with open(compose_file) as f:
                data = yaml.safe_load(f)
            
            if "services" in data:
                for service_name in data["services"]:
                    result["docker"].append(f"docker-compose up {service_name}  # specific service")
                    break  # Just show one example
        except:
            pass  # yaml might not be installed
    
    # Dockerfile
    if (root_path / "Dockerfile").exists():
        # Infer image name from directory
        image_name = root_path.name.lower().replace(" ", "-")
        result["docker"].insert(0, f"docker build -t {image_name} .")
        result["docker"].append(f"docker run {image_name}")
        
        # Check for common ports in Dockerfile
        dockerfile_content = (root_path / "Dockerfile").read_text()
        ports = re.findall(r'EXPOSE\s+(\d+)', dockerfile_content)
        if ports:
            port = ports[0]
            result["docker"].append(f"docker run -p {port}:{port} {image_name}")


def _extract_gradle_maven(root_path: Path, result: Dict[str, List[str]]):
    """Extract Gradle/Maven commands."""
    # Gradle
    if (root_path / "build.gradle").exists() or (root_path / "build.gradle.kts").exists():
        wrapper = "./gradlew" if (root_path / "gradlew").exists() else "gradle"
        
        result["local"].insert(0, f"{wrapper} build")
        result["local"].append(f"{wrapper} run")
        result["tests"].append(f"{wrapper} test")
        
        # Gradle with Spring Boot
        if (root_path / "src/main/java").exists():
            result["local"].append(f"{wrapper} bootRun")
    
    # Maven
    if (root_path / "pom.xml").exists():
        wrapper = "./mvnw" if (root_path / "mvnw").exists() else "mvn"
        
        result["local"].insert(0, f"{wrapper} clean install")
        result["local"].append(f"{wrapper} compile")
        result["tests"].append(f"{wrapper} test")
        
        # Check for Spring Boot
        pom_content = (root_path / "pom.xml").read_text()
        if "spring-boot" in pom_content:
            result["local"].append(f"{wrapper} spring-boot:run")
        
        # Check for exec plugin
        if "exec-maven-plugin" in pom_content:
            result["local"].append(f"{wrapper} exec:java")


def _extract_go_mod(root_path: Path, result: Dict[str, List[str]]):
    """Extract Go module commands."""
    if (root_path / "go.mod").exists():
        result["local"].insert(0, "go mod download")
        result["local"].append("go build")
        result["local"].append("go run .")
        result["tests"].append("go test ./...")
        
        # Check for main.go
        if (root_path / "main.go").exists():
            result["local"].append("go run main.go")
        
        # Check for cmd directory
        cmd_dir = root_path / "cmd"
        if cmd_dir.exists() and cmd_dir.is_dir():
            for cmd_entry in cmd_dir.iterdir():
                if cmd_entry.is_dir():
                    result["local"].append(f"go run ./cmd/{cmd_entry.name}")
                    break  # Just show one example


def _extract_env_files(root_path: Path, result: Dict[str, List[str]]):
    """Extract environment setup instructions."""
    env_files = []
    
    # Check for .env files
    for env_file in [".env", ".env.example", ".env.sample", ".env.template"]:
        if (root_path / env_file).exists():
            env_files.append(env_file)
    
    if env_files:
        if ".env" not in env_files and env_files:
            result["env"].append(f"cp {env_files[0]} .env  # Copy template")
        
        result["env"].append("# Edit .env with your configuration")
        
        # Try to extract required variables from example
        example_file = None
        for ef in env_files:
            if ef != ".env":
                example_file = root_path / ef
                break
        
        if example_file and example_file.exists():
            content = example_file.read_text()
            # Extract variable names
            var_names = re.findall(r'^([A-Z_]+)=', content, re.MULTILINE)
            if var_names:
                result["env"].append(f"# Required variables: {', '.join(var_names[:5])}")
    
    # Check for config directories
    config_dirs = ["config", "configs", "settings"]
    for config_dir in config_dirs:
        if (root_path / config_dir).exists():
            result["env"].append(f"# Check {config_dir}/ directory for configuration files")
            break


def _identify_gaps(root_path: Path, result: Dict[str, List[str]]):
    """Identify missing or unclear setup instructions."""
    # Check if we found any run instructions
    if not result["local"] and not result["docker"]:
        result["gaps"].append("No clear run instructions found")
        
        # Suggest based on file presence
        if (root_path / "src").exists():
            result["gaps"].append("Source code found in src/ but no entry point detected")
        
        # Language-specific gaps
        py_files = list(root_path.glob("*.py"))
        if py_files and not any(r for r in result["local"] if "python" in r):
            result["gaps"].append(f"Python files found but no run command. Try: python {py_files[0].name}")
        
        js_files = list(root_path.glob("*.js"))
        if js_files and not any(r for r in result["local"] if "node" in r or "npm" in r):
            result["gaps"].append(f"JavaScript files found but no run command. Try: node {js_files[0].name}")
    
    # Check for tests
    if not result["tests"]:
        test_dirs = ["test", "tests", "spec", "__tests__"]
        for test_dir in test_dirs:
            if (root_path / test_dir).exists():
                result["gaps"].append(f"Test directory {test_dir}/ found but no test command detected")
                break
    
    # Check for missing dependency files
    if not any(f for f in [
        "package.json", "requirements.txt", "pyproject.toml", 
        "go.mod", "pom.xml", "build.gradle", "Gemfile", "Cargo.toml"
    ] if (root_path / f).exists()):
        result["gaps"].append("No dependency manifest found")
    
    # Check for README
    readme_files = ["README.md", "README.rst", "README.txt", "README"]
    if not any((root_path / rf).exists() for rf in readme_files):
        result["gaps"].append("No README file found - check for documentation")
    
    # Environment gaps
    if not result["env"]:
        if any("DATABASE" in str(f) or "DB_" in str(f) 
               for f in root_path.glob("**/*.py") 
               if f.is_file()):
            result["gaps"].append("Database configuration likely needed but no .env file found")