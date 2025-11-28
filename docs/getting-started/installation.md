# Installation

## Prerequisites

- Python 3.10 or higher
- pip, uv, or pipx for installation

## Installation Methods

### Using pip

```bash
pip install brix
```

### Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager:

```bash
# Install as a tool (isolated environment)
uv tool install brix

# Or add to a project
uv add brix
```

### Using pipx

For isolated installation:

```bash
pipx install brix
```

### From Source

```bash
git clone https://github.com/Spycner/brix.git
cd brix
uv sync
uv run brix --help
```

## Verify Installation

```bash
brix --version
```

You should see output like:

```
brix 1.2.0
```

## Shell Completion

Brix supports shell completion for bash, zsh, and fish.

### Install Completion

```bash
brix --install-completion
```

### Show Completion Script

```bash
brix --show-completion
```

## Upgrading

### pip

```bash
pip install --upgrade brix
```

### uv

```bash
uv tool upgrade brix
```

### pipx

```bash
pipx upgrade brix
```

## Next Steps

- Follow the [Quick Start](quickstart.md) guide to create your first project
- Read the [Commands Overview](../user-guide/commands.md) for all available commands
