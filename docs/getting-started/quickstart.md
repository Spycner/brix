# Quick Start

This guide will help you get started with brix in just a few minutes.

## Step 1: Initialize a Profile

Before creating a dbt project, you need a profile configuration. Brix can initialize one for you:

```bash
brix dbt profile init
```

This creates a `profiles.yml` at `~/.dbt/profiles.yml` with a DuckDB configuration for local development.

!!! tip "Custom Location"
    Specify a custom path with `--profile-path`:
    ```bash
    brix dbt profile init --profile-path ./profiles.yml
    ```

## Step 2: Create a Project

Create a new dbt project with the interactive wizard:

```bash
brix dbt project init
```

The wizard will guide you through:

1. **Project name** - Name for your dbt project
2. **Profile selection** - Which profile to use
3. **Packages** - Add common packages (dbt_utils, elementary, etc.)
4. **Databricks settings** - Materialization and documentation options
5. **Example model** - Generate a sample model to get started

!!! info "Non-Interactive Mode"
    For scripting, use CLI flags:
    ```bash
    brix dbt project init --project-name my_project --profile default
    ```

## Step 3: Run dbt Commands

Brix passes through any dbt command:

```bash
# Install packages
brix dbt deps

# Run models
brix dbt run

# Test models
brix dbt test

# Generate documentation
brix dbt docs generate
brix dbt docs serve
```

## Common Workflows

### Local Development with DuckDB

```bash
# Initialize profile with DuckDB
brix dbt profile init

# Create project
brix dbt project init

# Run locally
brix dbt run
```

### Add a Databricks Connection

```bash
# Edit profile to add Databricks
brix dbt profile edit

# Select "Add new output"
# Choose "databricks" adapter
# Configure authentication (OAuth or Personal Access Token)
```

### Manage Packages

```bash
# Add a package from dbt Hub
brix dbt project edit --action add-hub-package

# Or non-interactively
brix dbt project edit --action add-hub-package --package-name dbt_utils --package-version ">=1.0.0"

# Install packages
brix dbt deps
```

## Next Steps

- [Commands Overview](../user-guide/commands.md) - Full command reference
- [Profile Management](../user-guide/profiles.md) - Deep dive into profiles
- [Project Management](../user-guide/projects.md) - Advanced project configuration
- [Configuration](../user-guide/configuration.md) - Environment variables and settings
