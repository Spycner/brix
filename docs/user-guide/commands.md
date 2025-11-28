# Commands Overview

Brix provides a hierarchical command structure centered around dbt operations.

## Command Structure

```
brix [global-options] dbt [dbt-options] [subcommand] [args]
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-v` | Show version and exit |
| `--log-level` | | Log level: TRACE, DEBUG, INFO, WARN, ERROR, OFF |
| `--log-path` | | File path for log output |
| `--log-json` | | Enable JSON log format |
| `--install-completion` | | Install shell completion |
| `--show-completion` | | Show shell completion script |
| `--help` | `-h` | Show help message |

## Command Groups

### `brix dbt`

Main command group for dbt operations.

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Path to dbt project directory (cached for subsequent commands) |

#### Subcommands

| Command | Description |
|---------|-------------|
| `profile` | Manage dbt profile configuration |
| `project` | Manage dbt projects |
| *any dbt command* | Passed through to dbt CLI |

### `brix dbt profile`

Manage `profiles.yml` configuration.

| Command | Description |
|---------|-------------|
| `init` | Initialize a dbt profile from template |
| `show` | Show the current profile path and contents |
| `edit` | Edit profile configuration (interactive or CLI) |

### `brix dbt project`

Manage dbt projects.

| Command | Description |
|---------|-------------|
| `init` | Initialize a new dbt project |
| `edit` | Edit project configuration |

## Quick Reference

### Profile Commands

```bash
# Initialize profile
brix dbt profile init
brix dbt profile init --profile-path ./profiles.yml --force

# View profile
brix dbt profile show

# Edit profile (interactive)
brix dbt profile edit

# Edit profile (CLI)
brix dbt profile edit --action add-profile --profile myproj --target dev
brix dbt profile edit --action delete-profile --profile old --force
```

### Project Commands

```bash
# Create project (interactive)
brix dbt project init

# Create project (CLI)
brix dbt project init -n my_project -p default --materialization table

# Edit project (interactive)
brix dbt project edit

# Edit project (CLI)
brix dbt project edit -p ./dbt_project.yml --action set-name --name new_name
brix dbt project edit --action add-hub-package --package dbt_utils
```

### dbt Passthrough

```bash
# Any dbt command works
brix dbt run
brix dbt test
brix dbt build
brix dbt docs generate
brix dbt docs serve
brix dbt seed
brix dbt snapshot
```

## Detailed Command Reference

- [Profile Management](profiles.md) - Complete profile command reference
- [Project Management](projects.md) - Complete project command reference
- [dbt Passthrough](passthrough.md) - Using native dbt commands
