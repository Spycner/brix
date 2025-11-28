# Profile Management

Brix provides commands to initialize, view, and edit dbt profile configurations (`profiles.yml`).

## Overview

dbt profiles define connection information for your data warehouses. Brix simplifies profile management with:

- **Templates** - Quick initialization with sensible defaults
- **Interactive editing** - Menu-driven configuration
- **CLI mode** - Scriptable, non-interactive operations
- **Multiple adapters** - DuckDB for local dev, Databricks for production

## Commands

### `brix dbt profile init`

Initialize a dbt profile from template.

```bash
brix dbt profile init [OPTIONS]
```

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--profile-path` | `-p` | `~/.dbt/profiles.yml` | Path to profiles.yml |
| `--force` | `-f` | | Overwrite existing profile |

#### Environment Variables

| Variable | Description |
|----------|-------------|
| `BRIX_DBT_PROFILE_PATH` | Default path for profiles.yml |

#### Examples

```bash
# Initialize at default location
brix dbt profile init

# Initialize at custom location
brix dbt profile init --profile-path ./profiles.yml

# Overwrite existing
brix dbt profile init --force
```

The template includes a DuckDB configuration:

```yaml
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ./dev.duckdb
```

---

### `brix dbt profile show`

Display the current profile path and contents.

```bash
brix dbt profile show
```

Shows:
- Profile file path
- Full YAML contents

---

### `brix dbt profile edit`

Edit dbt profile configuration.

```bash
brix dbt profile edit [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--profile-path` | `-p` | Path to profiles.yml |
| `--action` | `-a` | Action to perform (see below) |
| `--profile` | `-P` | Profile name |
| `--output` | `-o` | Output name |
| `--target` | `-t` | Default target name |
| `--path` | | DuckDB path |
| `--threads` | | Thread count |
| `--force` | `-f` | Skip confirmation for destructive actions |

#### Actions

| Action | Description |
|--------|-------------|
| `add-profile` | Add a new profile |
| `edit-profile` | Edit existing profile settings |
| `delete-profile` | Remove a profile |
| `add-output` | Add output to a profile |
| `edit-output` | Edit an existing output |
| `delete-output` | Remove an output |

#### Interactive Mode

Without `--action`, launches an interactive menu:

```bash
brix dbt profile edit
```

The menu provides:

1. Select profile to edit
2. Choose action (add/edit/delete profile or output)
3. Configure settings via prompts

#### CLI Mode Examples

```bash
# Add a new profile
brix dbt profile edit --action add-profile --profile myproject --target dev

# Edit profile target
brix dbt profile edit --action edit-profile --profile default --target prod

# Delete profile (with confirmation skip)
brix dbt profile edit --action delete-profile --profile old --force

# Add DuckDB output
brix dbt profile edit --action add-output --profile default --output local \
  --path ./local.duckdb --threads 4

# Edit existing output
brix dbt profile edit --action edit-output --profile default --output dev \
  --path ./new.duckdb

# Delete output
brix dbt profile edit --action delete-output --profile default --output old --force
```

## Supported Adapters

### DuckDB

For local development and testing.

```yaml
outputs:
  dev:
    type: duckdb
    path: ./dev.duckdb
    threads: 4
    extensions:
      - httpfs
      - parquet
    settings:
      memory_limit: 4GB
```

Configuration options:
- `path` - Database file path (`:memory:` for in-memory)
- `threads` - Number of threads
- `extensions` - DuckDB extensions to load
- `settings` - DuckDB configuration settings

### Databricks

For production workloads on Databricks.

#### OAuth User-to-Machine (U2M)

```yaml
outputs:
  prod:
    type: databricks
    host: dbc-abc123.cloud.databricks.com
    http_path: /sql/1.0/warehouses/xyz789
    catalog: main
    schema: analytics
    auth_type: oauth-u2m
```

#### OAuth Machine-to-Machine (M2M)

```yaml
outputs:
  prod:
    type: databricks
    host: dbc-abc123.cloud.databricks.com
    http_path: /sql/1.0/warehouses/xyz789
    catalog: main
    schema: analytics
    auth_type: oauth-m2m
    client_id: "{{ env_var('DBT_DATABRICKS_CLIENT_ID') }}"
    client_secret: "{{ env_var('DBT_DATABRICKS_CLIENT_SECRET') }}"
```

#### Personal Access Token (PAT)

```yaml
outputs:
  prod:
    type: databricks
    host: dbc-abc123.cloud.databricks.com
    http_path: /sql/1.0/warehouses/xyz789
    catalog: main
    schema: analytics
    token: "{{ env_var('DBT_DATABRICKS_TOKEN') }}"
```

## Best Practices

1. **Use environment variables** for sensitive values like tokens
2. **Keep local dev profiles** using DuckDB for fast iteration
3. **Separate targets** for dev, staging, and production
4. **Use OAuth** when possible for better security on Databricks
