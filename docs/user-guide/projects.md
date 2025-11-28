# Project Management

Brix provides commands to create and edit dbt projects with sensible defaults and package management.

## Overview

- **Project scaffolding** - Create complete dbt projects with one command
- **Package management** - Add packages from dbt Hub, Git, or local paths
- **Interactive wizard** - Guided setup for new projects
- **CLI mode** - Fully scriptable project creation and modification

## Commands

### `brix dbt project init`

Initialize a new dbt project with sensible defaults.

```bash
brix dbt project init [OPTIONS]
```

#### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--project-name` | `-n` | | Name of the dbt project (interactive if not provided) |
| `--base-dir` | `-b` | `.` | Base directory for project |
| `--team` | `-t` | | Team subdirectory (optional) |
| `--profile` | `-p` | | Profile name to use |
| `--profile-path` | | `~/.dbt/profiles.yml` | Path to profiles.yml for validation |
| `--packages` | | | Packages to include (can repeat) |
| `--no-packages` | | | Skip package installation |
| `--materialization` | | | Default: view, table, or ephemeral |
| `--persist-docs` | | | Enable persist_docs for Unity Catalog |
| `--run-deps` | | | Run `dbt deps` after creation |
| `--with-example` | | | Create example model |
| `--force` | `-f` | | Overwrite existing project |

#### Environment Variables

| Variable | Description |
|----------|-------------|
| `BRIX_DBT_PROJECT_BASE_DIR` | Default base directory |
| `BRIX_DBT_PROFILE_PATH` | Default profiles.yml path |

#### Interactive Mode

Without `--project-name`, launches a wizard:

```bash
brix dbt project init
```

The wizard guides you through:

1. **Project name** - Validates naming conventions
2. **Team directory** - Optional subdirectory organization
3. **Profile selection** - Lists available profiles
4. **Packages** - Select from common packages or enter custom
5. **Databricks settings** - Materialization and persist_docs
6. **Example model** - Generate a sample model

#### CLI Mode Examples

```bash
# Minimal project
brix dbt project init -n my_project

# Full configuration
brix dbt project init \
  --project-name analytics \
  --base-dir ./projects \
  --team data-engineering \
  --profile production \
  --packages dbt_utils \
  --packages elementary \
  --materialization table \
  --persist-docs \
  --run-deps \
  --with-example

# Overwrite existing
brix dbt project init -n my_project --force
```

#### Generated Structure

```
my_project/
├── dbt_project.yml
├── packages.yml
├── models/
│   └── example/
│       ├── example_model.sql
│       └── schema.yml
├── seeds/
├── macros/
├── snapshots/
├── tests/
└── .gitignore
```

---

### `brix dbt project edit`

Edit dbt project configuration.

```bash
brix dbt project edit [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Path to dbt_project.yml |
| `--action` | `-a` | Action to perform |
| `--name` | | New project name |
| `--profile` | | New profile name |
| `--version` | `-v` | New project version |
| `--require-dbt-version` | | dbt version constraint |
| `--path-field` | | Path field to modify |
| `--path` | | Path value |
| `--create-dir` | | Create directory when adding path |
| `--package` | | Package name |
| `--package-version` | | Package version specifier |
| `--revision` | | Git revision |
| `--subdirectory` | | Subdirectory in git repo |
| `--force` | `-f` | Skip confirmations |

#### Actions

**Project Settings:**

| Action | Description |
|--------|-------------|
| `set-name` | Change project name |
| `set-profile` | Change profile reference |
| `set-version` | Change project version |
| `set-require-dbt-version` | Set dbt version constraint |

**Path Management:**

| Action | Description |
|--------|-------------|
| `add-path` | Add to path arrays (model-paths, seed-paths, etc.) |
| `remove-path` | Remove from path arrays |

**Package Management:**

| Action | Description |
|--------|-------------|
| `add-hub-package` | Add package from dbt Hub |
| `add-git-package` | Add package from Git repository |
| `add-local-package` | Add local package |
| `remove-package` | Remove a package |
| `update-package-version` | Update package version |

#### Interactive Mode

Without `--action`, launches interactive editor:

```bash
brix dbt project edit
```

Features:
- Project discovery (finds dbt_project.yml in current directory tree)
- Menu-driven action selection
- Guided prompts for each action

#### CLI Mode Examples

**Project Settings:**

```bash
# Change project name
brix dbt project edit -p ./dbt_project.yml --action set-name --name new_name

# Change profile
brix dbt project edit --action set-profile --profile production

# Set version
brix dbt project edit --action set-version --version 2.0.0

# Set dbt version constraint
brix dbt project edit --action set-require-dbt-version --require-dbt-version ">=1.7.0"
```

**Path Management:**

```bash
# Add model path with directory creation
brix dbt project edit --action add-path \
  --path-field model-paths \
  --path staging \
  --create-dir

# Remove seed path
brix dbt project edit --action remove-path \
  --path-field seed-paths \
  --path old_seeds
```

**Package Management:**

```bash
# Add dbt Hub package
brix dbt project edit --action add-hub-package \
  --package dbt-labs/dbt_utils \
  --package-version ">=1.0.0"

# Add Git package
brix dbt project edit --action add-git-package \
  --package https://github.com/org/repo.git \
  --revision main \
  --subdirectory dbt

# Add local package
brix dbt project edit --action add-local-package \
  --package ../shared_macros

# Remove package
brix dbt project edit --action remove-package \
  --package dbt-labs/dbt_utils \
  --force

# Update package version
brix dbt project edit --action update-package-version \
  --package dbt-labs/dbt_utils \
  --package-version ">=2.0.0"
```

## Package Shortcuts

When using interactive mode, brix recognizes common package shortcuts:

| Shortcut | Full Package |
|----------|-------------|
| `dbt_utils` | dbt-labs/dbt_utils |
| `elementary` | elementary-data/elementary |
| `codegen` | dbt-labs/codegen |
| `audit_helper` | dbt-labs/audit_helper |
| `dbt_expectations` | calogica/dbt_expectations |
| `dbt_date` | calogica/dbt_date |

## Best Practices

1. **Use semantic versioning** for package versions (`>=1.0.0,<2.0.0`)
2. **Pin to specific versions** in production for reproducibility
3. **Run `dbt deps`** after modifying packages
4. **Use persist_docs** with Databricks Unity Catalog
5. **Organize models** in subdirectories (staging, marts, etc.)
