# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Use `uv` for all Python operations. Task runner commands via poethepoet:

```bash
uv run poe lint       # Run ruff linting
uv run poe format     # Run ruff formatting
uv run poe typecheck  # Run ty type checking
uv run poe test       # Run pytest
uv run poe check      # Run lint + typecheck together
```

Single test: `uv run pytest test/test_file.py::test_name -v`

## Code Style

- Python 3.10+, strict type hints required (ANN rules enforced)
- Google-style docstrings
- Line length: 120 characters
- Ruff handles linting and formatting
- ty for type checking (src-layout aware via `tool.ty.environment.root`)

## Project Structure

- `src/databricks_dbt_cli/` - Main package (src-layout)
- `test/` - Tests (relaxed rules: no type hints, docstrings, or assert warnings required)
- Uses Typer for CLI interface
- Never add new dependencies on your own, ask me to do it