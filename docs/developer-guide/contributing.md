# Contributing

Guide for contributing to brix development.

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### Clone and Install

```bash
git clone https://github.com/Spycner/brix.git
cd brix
uv sync
```

### Verify Setup

```bash
uv run brix --version
uv run poe test
```

## Development Workflow

### Task Runner

Use poethepoet for common tasks:

```bash
uv run poe lint            # Run ruff linting
uv run poe format          # Run ruff formatting
uv run poe typecheck       # Run ty type checking
uv run poe test            # Run all tests
uv run poe test-unit       # Run unit tests only
uv run poe test-integration # Run integration tests
uv run poe test-e2e        # Run e2e tests
uv run poe check           # Run lint + typecheck
uv run poe pre-commit      # Run pre-commit hooks
```

### Running the CLI

```bash
uv run brix --help
uv run brix dbt profile init
```

### Running Tests

```bash
# All tests
uv run poe test

# Specific test file
uv run pytest tests/unit/test_profile_models.py -v

# Specific test
uv run pytest tests/unit/test_profile_models.py::test_duckdb_output -v

# With coverage
uv run pytest --cov=brix
```

## Code Style

### Linting and Formatting

Brix uses ruff for linting and formatting:

```bash
# Check for issues
uv run poe lint

# Auto-format
uv run poe format
```

### Type Hints

All public functions require type hints (ANN rules enforced):

```python
def init_profile(
    profile_path: Path,
    force: bool = False,
    template_name: str = "profiles.yml",
) -> ProfileInitResult:
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def init_profile(profile_path: Path, force: bool = False) -> ProfileInitResult:
    """Initialize a dbt profile from template.

    Creates a profiles.yml file at the specified path with a DuckDB
    configuration for local development.

    Args:
        profile_path: Path where profiles.yml will be created.
        force: If True, overwrite existing file.

    Returns:
        ProfileInitResult with success status and message.

    Raises:
        ProfileExistsError: If file exists and force is False.
    """
```

### Line Length

Maximum 120 characters per line.

## Pre-commit Hooks

Always run pre-commit before committing:

```bash
uv run poe pre-commit
```

Or install hooks to run automatically:

```bash
uv run pre-commit install
```

## Pull Request Process

1. **Fork** the repository
2. **Create a branch** from `main`
3. **Make changes** following code style guidelines
4. **Add tests** for new functionality
5. **Run checks**: `uv run poe check && uv run poe test`
6. **Run pre-commit**: `uv run poe pre-commit`
7. **Create PR** with clear description

### Commit Messages

Follow conventional commits:

```
feat: add snowflake adapter support
fix: handle empty profiles.yml gracefully
docs: update installation instructions
test: add integration tests for project init
refactor: extract validation logic to separate module
```

### PR Description

Include:
- Summary of changes
- Related issues
- Test coverage
- Breaking changes (if any)

## Adding Features

### Adding a New Command

1. Create command file in `commands/dbt/`:

```python
# commands/dbt/new_command.py
import typer

app = typer.Typer()

@app.command()
def action(name: str) -> None:
    """Command description."""
    from brix.modules.dbt.new_feature import do_action
    result = do_action(name)
    typer.echo(result.message)
```

2. Register in `commands/dbt/__init__.py`:

```python
from brix.commands.dbt.new_command import app as new_command_app

app.add_typer(new_command_app, name="new-command")
```

3. Add business logic in `modules/dbt/new_feature/`

### Adding Tests

Place tests in the appropriate directory:

- `tests/unit/` - No external dependencies, mocked I/O
- `tests/integration/` - May require dbt, real file operations
- `tests/e2e/` - Full dbt execution, real commands

Use markers for non-unit tests:

```python
import pytest

@pytest.mark.integration
def test_profile_creation():
    ...

@pytest.mark.e2e
def test_full_workflow():
    ...
```

## Release Process

Releases are automated via semantic-release:

1. Merge PR to `main`
2. GitHub Action analyzes commits
3. Bumps version based on commit types
4. Creates GitHub release
5. Publishes to PyPI

Version bumps:
- `fix:` → patch (1.0.x)
- `feat:` → minor (1.x.0)
- `BREAKING CHANGE:` → major (x.0.0)
