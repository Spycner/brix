# Brix

[![PyPI version](https://badge.fury.io/py/brix.svg)](https://badge.fury.io/py/brix)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://spycner.github.io/brix/)

**CLI for dbt project and profile management with Databricks focus**

Brix simplifies dbt workflow by providing convenient commands for profile and project management while allowing full passthrough to the native dbt CLI.

## Features

- **Profile Management** - Initialize, view, and edit `profiles.yml` with interactive or CLI modes
- **Project Scaffolding** - Create dbt projects with sensible defaults and package management
- **dbt Passthrough** - Run any dbt command through brix (`brix dbt run`, `brix dbt test`, etc.)
- **Multiple Adapters** - Built-in support for DuckDB (local development) and Databricks
- **Interactive & CLI Modes** - Use guided wizards or script with CLI flags

## Installation

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

# Run dbt commands
brix dbt run
brix dbt test
```

## Documentation

Full documentation is available at **[spycner.github.io/brix](https://spycner.github.io/brix/)**

- [Installation](https://spycner.github.io/brix/getting-started/installation/)
- [Quick Start](https://spycner.github.io/brix/getting-started/quickstart/)
- [Command Reference](https://spycner.github.io/brix/user-guide/commands/)
- [Developer Guide](https://spycner.github.io/brix/developer-guide/architecture/)
- [API Reference](https://spycner.github.io/brix/api/)

## Development

```bash
git clone https://github.com/Spycner/brix.git
cd brix
uv sync
uv run brix --help
```

See the [Contributing Guide](https://spycner.github.io/brix/developer-guide/contributing/) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
