# Brix

**CLI for dbt project and profile management with Databricks focus**

[![PyPI version](https://badge.fury.io/py/brix.svg)](https://badge.fury.io/py/brix)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What is Brix?

Brix is a command-line tool that simplifies dbt project and profile management. It wraps the dbt CLI, adding convenience commands while allowing full passthrough to native dbt commands.

### Key Features

- **Profile Management** - Initialize, view, and edit `profiles.yml` with interactive or CLI modes
- **Project Scaffolding** - Create new dbt projects with sensible defaults and package management
- **dbt Passthrough** - Run any dbt command through brix (`brix dbt run`, `brix dbt test`, etc.)
- **Multiple Adapters** - Built-in support for DuckDB (local development) and Databricks
- **Interactive & CLI Modes** - Use guided wizards or script with CLI flags

## Quick Install

```bash
pip install brix
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install brix
```

## Quick Start

```bash
# Initialize a dbt profile
brix dbt profile init

# Create a new dbt project
brix dbt project init

# Run dbt commands through brix
brix dbt run
brix dbt test
```

## Documentation

- [Installation](getting-started/installation.md) - Detailed installation instructions
- [Quick Start](getting-started/quickstart.md) - Get up and running in minutes
- [User Guide](user-guide/commands.md) - Complete command reference
- [Developer Guide](developer-guide/architecture.md) - Contribute to brix
- [API Reference](api/index.md) - Python API documentation

## License

MIT License - see [LICENSE](https://github.com/Spycner/brix/blob/main/LICENSE) for details.
