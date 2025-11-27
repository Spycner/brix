# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Use `uv` for all Python operations. Task runner commands via poethepoet:

```bash
uv run poe lint            # Run ruff linting
uv run poe format          # Run ruff formatting
uv run poe typecheck       # Run ty type checking
uv run poe test            # Run all tests
uv run poe test-unit       # Run unit tests only
uv run poe test-integration # Run integration tests only
uv run poe check           # Run lint + typecheck together
```

Single test: `uv run pytest tests/unit/test_file.py::test_name -v`

Run the CLI: `uv run brix --help`

## Before Committing

**Always run pre-commit before committing to avoid CI failures:**

```bash
uv run pre-commit run --all-files
```

## Code Style

- Python 3.10+, strict type hints required (ANN rules enforced)
- Google-style docstrings
- Line length: 120 characters
- Ruff handles linting and formatting
- ty for type checking (src-layout aware via `tool.ty.environment.root`)

## Architecture

### Layer Separation

```
commands/          CLI layer (Typer) - argument parsing, output, errors
    └── dbt/
        └── profile.py
modules/           Business logic layer - reusable, CLI-independent
    └── dbt/
        └── profile/
            ├── service.py   # Core operations, configuration
            ├── editor.py    # CRUD operations
            ├── models.py    # Pydantic models
            └── prompts.py   # Interactive questionary prompts
```

### Key Patterns

**dbt Passthrough**: Custom `DbtGroup` class in `commands/dbt/__init__.py` intercepts unknown commands and passes them to the dbt CLI. This allows `brix dbt run` to execute `dbt run` while `brix dbt profile` is handled by brix.

**Profile Models** (`modules/dbt/profile/models.py`): Pydantic models with discriminated unions for adapter types (DuckDB, Databricks). `DbtProfiles` provides YAML serialization via `from_yaml()`/`to_yaml()`.

**Template System** (`templates/`): Bundled files loaded via `importlib.resources`. Use `get_template(name)` to load content.

**Configuration**: Uses `pydantic-settings` with `BRIX_` prefix (e.g., `BRIX_DBT_PROFILE_PATH`). CLI arguments override environment variables.

**Logging** (`utils/logging.py`): Terraform-style with env vars (`BRIX_LOG`, `BRIX_LOG_PATH`, `BRIX_LOG_JSON`). Thread-safe singleton; use `get_logger()` from any module.

**Version Checking** (`version_check.py`): Non-blocking background thread with 24-hour cache in `~/.cache/brix/`.
