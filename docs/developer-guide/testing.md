# Testing

Guide for testing brix functionality.

## Test Structure

```
tests/
├── unit/           # No external dependencies
├── integration/    # May require dbt, real files
└── e2e/           # Full dbt execution
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast tests with no external dependencies:
- Model validation
- Pure functions
- Mocked I/O

```bash
uv run poe test-unit
```

Example:

```python
from brix.modules.dbt.profile.models import DuckDbOutput

def test_duckdb_output_defaults():
    output = DuckDbOutput(path="./test.duckdb")
    assert output.type == "duckdb"
    assert output.threads == 4  # default
```

### Integration Tests (`tests/integration/`)

Tests requiring real file operations or dbt:
- File creation/modification
- YAML parsing
- Template rendering

```bash
uv run poe test-integration
```

Mark with `@pytest.mark.integration`:

```python
import pytest
from pathlib import Path

@pytest.mark.integration
def test_profile_yaml_creation(tmp_path: Path):
    from brix.modules.dbt.profile.service import init_profile

    result = init_profile(tmp_path / "profiles.yml")
    assert result.success
    assert (tmp_path / "profiles.yml").exists()
```

### E2E Tests (`tests/e2e/`)

Full workflow tests with real dbt execution:
- Project initialization
- dbt command passthrough
- Complete user workflows

```bash
uv run poe test-e2e
```

Mark with `@pytest.mark.e2e`:

```python
import pytest
import subprocess

@pytest.mark.e2e
def test_dbt_run_passthrough(tmp_path: Path, initialized_project):
    result = subprocess.run(
        ["brix", "dbt", "-p", str(initialized_project), "debug"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
```

## Running Tests

### All Tests

```bash
uv run poe test
```

### Specific Category

```bash
uv run poe test-unit
uv run poe test-integration
uv run poe test-e2e
```

### Specific File

```bash
uv run pytest tests/unit/test_profile_models.py -v
```

### Specific Test

```bash
uv run pytest tests/unit/test_profile_models.py::test_duckdb_output -v
```

### With Coverage

```bash
uv run pytest --cov=brix --cov-report=html
# Open htmlcov/index.html
```

### Verbose Output

```bash
uv run pytest -v --tb=long
```

## Fixtures

### Common Fixtures

```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def tmp_profiles(tmp_path: Path) -> Path:
    """Create temporary profiles.yml."""
    profiles_path = tmp_path / "profiles.yml"
    profiles_path.write_text("""
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ./dev.duckdb
""")
    return profiles_path

@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create temporary dbt project."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    (project_path / "dbt_project.yml").write_text("""
name: test_project
version: '1.0.0'
profile: default
""")
    return project_path
```

### Mocking

```python
from unittest.mock import patch, MagicMock

def test_version_check_disabled():
    with patch("brix.version_check.httpx.get") as mock_get:
        mock_get.side_effect = Exception("Network error")
        # Version check should fail silently
        from brix.version_check import check_version
        result = check_version()
        assert result is None  # No crash
```

## Test Patterns

### Testing CLI Commands

```python
from typer.testing import CliRunner
from brix.main import app

runner = CliRunner()

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "brix" in result.output

def test_profile_init(tmp_path: Path):
    result = runner.invoke(app, [
        "dbt", "profile", "init",
        "--profile-path", str(tmp_path / "profiles.yml"),
    ])
    assert result.exit_code == 0
```

### Testing Interactive Prompts

```python
from unittest.mock import patch

def test_interactive_profile_edit():
    with patch("questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = "add-profile"
        # Test prompt behavior
```

### Testing Pydantic Models

```python
import pytest
from pydantic import ValidationError

def test_required_field_validation():
    with pytest.raises(ValidationError):
        DatabricksOutput()  # Missing required fields

def test_discriminated_union():
    from pydantic import TypeAdapter
    adapter = TypeAdapter(OutputConfig)

    duckdb_data = {"type": "duckdb", "path": "./test.db"}
    result = adapter.validate_python(duckdb_data)
    assert isinstance(result, DuckDbOutput)
```

### Testing File Operations

```python
@pytest.mark.integration
def test_yaml_roundtrip(tmp_path: Path):
    original = DbtProfiles(profiles={"test": {...}})
    yaml_path = tmp_path / "profiles.yml"

    # Write
    yaml_path.write_text(original.to_yaml())

    # Read back
    loaded = DbtProfiles.from_yaml(yaml_path.read_text())

    assert loaded == original
```

## Debugging Tests

### Print Output

```bash
uv run pytest -v -s  # -s shows print statements
```

### Stop on First Failure

```bash
uv run pytest -x
```

### Drop into Debugger

```bash
uv run pytest --pdb
```

Or in code:

```python
def test_something():
    import pdb; pdb.set_trace()
    # ...
```

### Show Local Variables

```bash
uv run pytest -l --tb=long
```

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Pushes to main

GitHub Actions workflow runs:
1. `uv run poe lint`
2. `uv run poe typecheck`
3. `uv run poe test`

See `.github/workflows/ci.yml` for configuration.
