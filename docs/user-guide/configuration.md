# Configuration

Brix uses environment variables and CLI options for configuration.

## Configuration Precedence

1. **CLI arguments** - Highest priority
2. **Environment variables** - Override defaults
3. **Defaults** - Built-in values

## Environment Variables

### Profile Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BRIX_DBT_PROFILE_PATH` | `~/.dbt/profiles.yml` | Path to dbt profiles.yml |

### Project Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BRIX_DBT_PROJECT_BASE_DIR` | `.` | Base directory for new projects |

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BRIX_LOG` | `OFF` | Log level: TRACE, DEBUG, INFO, WARN, ERROR, OFF |
| `BRIX_LOG_PATH` | | File path for log output |
| `BRIX_LOG_JSON` | `false` | Enable JSON log format |

## CLI Options

### Global Options

```bash
brix --log-level DEBUG dbt run
brix --log-path ./brix.log dbt test
brix --log-json dbt build
```

### Profile Options

```bash
brix dbt profile init --profile-path ./profiles.yml
brix dbt profile edit -p ./profiles.yml
```

### Project Options

```bash
brix dbt -p ./my_project run
brix dbt project init --base-dir ./projects
```

## Cache Locations

Brix stores cache files in `~/.cache/brix/`:

| File | Purpose |
|------|---------|
| `dbt_project_path.json` | Last used project path |
| `version_check.json` | Version check results (24-hour TTL) |

## Logging

Brix uses Terraform-style logging with customizable output.

### Log Levels

| Level | Description |
|-------|-------------|
| `TRACE` | Most verbose, debugging internals |
| `DEBUG` | Detailed debugging information |
| `INFO` | General operational information |
| `WARN` | Warning messages |
| `ERROR` | Error messages only |
| `OFF` | Disable logging (default) |

### Examples

**Console logging:**

```bash
BRIX_LOG=DEBUG brix dbt run
```

**File logging:**

```bash
BRIX_LOG=INFO BRIX_LOG_PATH=./brix.log brix dbt run
```

**JSON logging:**

```bash
BRIX_LOG=DEBUG BRIX_LOG_JSON=true brix dbt run
```

**Via CLI:**

```bash
brix --log-level DEBUG --log-path ./debug.log dbt run
```

## Version Checking

Brix checks for updates in the background:

- Runs in a non-blocking background thread
- Results cached for 24 hours
- Shows notification if a newer version is available
- Never blocks command execution

To disable version checks, the feature fails silently if network is unavailable.

## Example: Production Setup

```bash
# .env file
export BRIX_DBT_PROFILE_PATH=/etc/dbt/profiles.yml
export BRIX_DBT_PROJECT_BASE_DIR=/var/dbt/projects
export BRIX_LOG=INFO
export BRIX_LOG_PATH=/var/log/brix/brix.log
export BRIX_LOG_JSON=true
```

## Example: Development Setup

```bash
# Development .env
export BRIX_LOG=DEBUG
export BRIX_DBT_PROFILE_PATH=./profiles.yml
```

## Shell Completion

Enable tab completion for faster command entry:

```bash
# Install completion for your shell
brix --install-completion

# View completion script
brix --show-completion
```

Supported shells:
- bash
- zsh
- fish
- PowerShell
