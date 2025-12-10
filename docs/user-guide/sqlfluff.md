# SQLFluff Setup Guide for dbt with Databricks

A comprehensive guide to configuring SQLFluff for linting and formatting SQL in dbt projects targeting Databricks.

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Rule Categories](#rule-categories)
5. [Recommended Configuration](#recommended-configuration)
6. [CI/CD Integration](#cicd-integration)
7. [Multi-Project / Monorepo Setup](#multi-project--monorepo-setup)
8. [Troubleshooting](#troubleshooting)
9. [Sources](#sources)

---

## Overview

[SQLFluff](https://github.com/sqlfluff/sqlfluff) is a modular SQL linter and auto-formatter with support for multiple dialects and templated code. When combined with dbt, it provides powerful capabilities for enforcing SQL standards across your analytics codebase.

### Key Benefits
- **Dialect-aware**: Native support for Databricks SQL syntax via the `databricks` dialect
- **dbt Integration**: Understands Jinja templating and dbt macros like `ref()`, `source()`, and `var()`
- **Auto-fix**: Can automatically fix many rule violations
- **Extensible**: Granular rule configuration for team-specific standards

---

## Installation

### Required Packages

```bash
pip install sqlfluff sqlfluff-templater-dbt dbt-databricks
```

Or with uv:

```bash
uv add sqlfluff sqlfluff-templater-dbt dbt-databricks
```

### Package Descriptions

| Package | Purpose |
|---------|---------|
| `sqlfluff` | Core linter and formatter |
| `sqlfluff-templater-dbt` | dbt templater for parsing Jinja/dbt syntax |
| `dbt-databricks` | dbt adapter for Databricks (required by templater) |

---

## Configuration

### File Structure

SQLFluff uses two configuration files in your project root:

```
your-dbt-project/
├── .sqlfluff           # Main configuration
├── .sqlfluffignore     # Files/directories to ignore
├── dbt_project.yml
├── profiles.yml        # Local profiles for linting
└── models/
```

### .sqlfluff Configuration

Create a `.sqlfluff` file in your dbt project root:

```ini
[sqlfluff]
dialect = databricks
templater = dbt
max_line_length = 120
encoding = utf-8

[sqlfluff:templater:dbt]
project_dir = ./
profiles_dir = ~/.dbt/
profile = default
target = dev
```

### Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| `dialect` | SQL dialect (`databricks` or `sparksql`) | Required |
| `templater` | Template engine (`dbt` or `jinja`) | `jinja` |
| `max_line_length` | Maximum characters per line | 80 |
| `project_dir` | Path to dbt_project.yml | `./` |
| `profiles_dir` | Path to profiles.yml directory | `~/.dbt/` |
| `profile` | dbt profile name | Required |
| `target` | dbt target within profile | Required |

### Dialect Choice: `databricks` vs `sparksql`

- **`databricks`**: Recommended for Databricks. Inherits from `sparksql` and adds Unity Catalog syntax support.
- **`sparksql`**: Use for generic Apache Spark SQL without Databricks-specific features.

### .sqlfluffignore

Create a `.sqlfluffignore` file to exclude directories:

```
target/
dbt_packages/
dbt_modules/
macros/
logs/
```

---

## Rule Categories

SQLFluff organizes rules into categories with two-letter prefixes:

### Layout Rules (LT)
Spacing, indentation, and formatting.
- `LT01`: Trailing whitespace
- `LT02`: Incorrect indentation
- `LT05`: Comma placement
- `LT12`: End of file newline

### Capitalisation Rules (CP)
Case consistency for SQL elements.
- `CP01`: Keywords (SELECT, FROM, WHERE)
- `CP02`: Identifiers (table/column names)
- `CP03`: Functions
- `CP04`: Literals (TRUE, FALSE, NULL)

### Aliasing Rules (AL)
Alias best practices.
- `AL01`: Implicit aliasing (missing AS keyword)
- `AL02`: Table aliases in column references
- `AL07`: Avoid aliases entirely (disabled by default)

### Ambiguous Rules (AM)
Query clarity.
- `AM01`: Distinct used with GROUP BY
- `AM04`: Nested CASE statements
- `AM05`: Join condition qualification

### Structure Rules (ST)
Query logic.
- `ST05`: CTE usage instead of subqueries
- `ST06`: Select targets ordering
- `ST07`: Using USING clause in joins

### Convention Rules (CV)
Code style preferences.
- `CV06`: Statement terminators (semicolons)
- `CV09`: Blocked words
- `CV11`: Casting style (CAST vs ::)

### References Rules (RF)
Column/table qualification.
- `RF01`: Quoted identifier consistency
- `RF02`: Column qualification in multi-table queries

---

## Recommended Configuration

### Complete .sqlfluff for Databricks + dbt

```ini
[sqlfluff]
dialect = databricks
templater = dbt
max_line_length = 120
exclude_rules = LT05, AM04, ST06
warnings = RF02
encoding = utf-8
large_file_skip_byte_limit = 1000000
processes = 2

[sqlfluff:indentation]
indent_unit = space
tab_space_size = 4
indented_joins = false
indented_ctes = false
indented_using_on = true
indented_on_contents = true

[sqlfluff:layout:type:comma]
line_position = trailing

[sqlfluff:templater:dbt]
project_dir = ./
profiles_dir = ./
profile = default
target = dev

[sqlfluff:rules:capitalisation.keywords]
capitalisation_policy = upper

[sqlfluff:rules:capitalisation.identifiers]
capitalisation_policy = lower

[sqlfluff:rules:capitalisation.functions]
capitalisation_policy = upper

[sqlfluff:rules:capitalisation.literals]
capitalisation_policy = upper

[sqlfluff:rules:capitalisation.types]
capitalisation_policy = upper

[sqlfluff:rules:aliasing.table]
aliasing = explicit

[sqlfluff:rules:aliasing.column]
aliasing = explicit

[sqlfluff:rules:aliasing.expression]
allow_scalar = false

[sqlfluff:rules:convention.casting_style]
preferred_type_casting_style = cast
```

### dbt Labs Style Guide Alternative

For lowercase keywords (per [dbt style guide](https://docs.getdbt.com/best-practices/how-we-style/2-how-we-style-our-sql)):

```ini
[sqlfluff:rules:capitalisation.keywords]
capitalisation_policy = lower

[sqlfluff:rules:capitalisation.functions]
capitalisation_policy = lower

[sqlfluff:rules:capitalisation.literals]
capitalisation_policy = lower
```

### Local profiles.yml for Linting

Create a minimal `profiles.yml` in your project for local/CI linting without requiring database access:

```yaml
default:
  target: dev
  outputs:
    dev:
      type: databricks
      host: "{{ env_var('DBT_HOST', 'dummy.cloud.databricks.com') }}"
      http_path: "{{ env_var('DBT_HTTP_PATH', '/sql/1.0/warehouses/dummy') }}"
      token: "{{ env_var('DBT_TOKEN', 'dummy') }}"
      catalog: main
      schema: dev
```

---

## CI/CD Integration

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/sqlfluff/sqlfluff
    rev: 3.2.5  # Use latest stable version
    hooks:
      - id: sqlfluff-lint
        additional_dependencies:
          - dbt-databricks>=1.8.0
          - sqlfluff-templater-dbt
        args: [--dialect, databricks]
      - id: sqlfluff-fix
        additional_dependencies:
          - dbt-databricks>=1.8.0
          - sqlfluff-templater-dbt
        args: [--dialect, databricks, --force]
```

### GitHub Actions Workflow

Create `.github/workflows/sqlfluff.yml`:

```yaml
name: SQLFluff Lint

on:
  pull_request:
    paths:
      - 'models/**/*.sql'
      - '.sqlfluff'

jobs:
  sqlfluff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install sqlfluff sqlfluff-templater-dbt dbt-databricks

      - name: Create dummy profiles.yml
        run: |
          cat > profiles.yml << 'EOF'
          default:
            target: dev
            outputs:
              dev:
                type: databricks
                host: dummy.cloud.databricks.com
                http_path: /sql/1.0/warehouses/dummy
                token: dummy
                catalog: main
                schema: dev
          EOF

      - name: Lint SQL
        run: sqlfluff lint models/ --format github-annotation-native
```

### GitHub PR Annotations

Use `--format github-annotation-native` to get inline PR annotations:

```bash
sqlfluff lint models/ --format github-annotation-native
```

---

## Multi-Project / Monorepo Setup

When working with multiple dbt projects in a single repository, there's an important limitation to understand.

### The Templater Limitation

**The `templater` setting cannot be overridden in subdirectory `.sqlfluff` files.** SQLFluff explicitly requires the templater to be set in the root config where SQLFluff is executed:

> "To use the dbt templater, you must set `templater = dbt` in the `.sqlfluff` config file in the directory where sqlfluff is run."

This means you **cannot** have a structure like:

```
repo/
├── .sqlfluff                    # templater = jinja (global)
└── assets/dbt_projects/
    ├── project_a/
    │   └── .sqlfluff            # templater = dbt (IGNORED!)
    └── project_b/
        └── .sqlfluff            # templater = dbt (IGNORED!)
```

### What CAN Be Inherited

All other settings follow hierarchical inheritance and can be overridden per subdirectory:
- Rules and rule configurations
- Indentation settings
- Capitalisation policies
- Line length
- Dialect (though this typically stays consistent)

### Recommended Approach: Per-Project Execution

The most reliable solution is to run SQLFluff from within each project directory:

```
repo/
├── .sqlfluff.shared             # Shared rules (not used directly)
└── assets/dbt_projects/
    ├── project_a/
    │   ├── .sqlfluff            # templater = dbt, includes shared rules
    │   ├── .sqlfluffignore
    │   ├── dbt_project.yml
    │   └── models/
    └── project_b/
        ├── .sqlfluff            # templater = jinja (different!)
        ├── .sqlfluffignore
        ├── dbt_project.yml
        └── models/
```

#### CLI Usage

```bash
# Lint project_a
cd assets/dbt_projects/project_a && sqlfluff lint models/

# Lint project_b
cd assets/dbt_projects/project_b && sqlfluff lint models/

# Or use absolute paths
sqlfluff lint assets/dbt_projects/project_a/models/ \
  --config assets/dbt_projects/project_a/.sqlfluff
```

#### GitHub Actions for Multiple Projects

```yaml
name: SQLFluff Lint

on:
  pull_request:
    paths:
      - 'assets/dbt_projects/**/*.sql'
      - 'assets/dbt_projects/**/.sqlfluff'

jobs:
  lint:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        project: [project_a, project_b, project_c]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install sqlfluff sqlfluff-templater-dbt dbt-databricks

      - name: Lint ${{ matrix.project }}
        working-directory: assets/dbt_projects/${{ matrix.project }}
        run: sqlfluff lint models/ --format github-annotation-native
```

#### Pre-commit for Multiple Projects

```yaml
repos:
  - repo: local
    hooks:
      - id: sqlfluff-lint-project-a
        name: SQLFluff Lint Project A
        entry: bash -c 'cd assets/dbt_projects/project_a && sqlfluff lint models/'
        language: system
        files: ^assets/dbt_projects/project_a/.*\.sql$
        pass_filenames: false

      - id: sqlfluff-lint-project-b
        name: SQLFluff Lint Project B
        entry: bash -c 'cd assets/dbt_projects/project_b && sqlfluff lint models/'
        language: system
        files: ^assets/dbt_projects/project_b/.*\.sql$
        pass_filenames: false
```

### Alternative: Jinja Templater with dbt Builtins

If per-project execution is too complex, you can use the Jinja templater globally with dbt builtin support:

```ini
[sqlfluff]
dialect = databricks
templater = jinja
max_line_length = 120

[sqlfluff:templater:jinja]
apply_dbt_builtins = True
```

This provides basic support for dbt macros (`ref()`, `source()`, `var()`, `is_incremental()`) without requiring the full dbt templater. Trade-offs:

| Aspect | dbt Templater | Jinja with Builtins |
|--------|---------------|---------------------|
| Accuracy | Full dbt compilation | Basic macro stubs |
| Custom macros | Fully supported | Not supported |
| Database access | Sometimes required | Never required |
| Speed | Slower | Faster |
| Multi-project | Per-project only | Global config works |

### VS Code Configuration for Multi-Project

Configure VS Code to use the file's directory for config discovery:

```json
{
  "sqlfluff.workingDirectory": "${fileDirname}",
  "sqlfluff.ignoreLocalConfig": false
}
```

This allows VS Code to find the nearest `.sqlfluff` file when linting.

### Environment Variables

You can use environment variables to dynamically set project paths:

```ini
[sqlfluff:templater:dbt]
project_dir = ./
profiles_dir = ./
```

Override in CI/CD:
```bash
export DBT_PROJECT_DIR=/path/to/project_a
export DBT_PROFILES_DIR=/path/to/project_a
sqlfluff lint models/
```

---

## Troubleshooting

### Common Errors

#### 1. "Could not find profile named 'XXX'"

**Cause**: SQLFluff cannot locate your dbt profile.

**Solution**: Ensure `profiles_dir` points to the directory containing `profiles.yml`:
```ini
[sqlfluff:templater:dbt]
profiles_dir = ./  # or ~/.dbt/
```

#### 2. "'adapter' is undefined"

**Cause**: Using Jinja templater instead of dbt templater, or missing dbt adapter.

**Solution**:
1. Set `templater = dbt` in `.sqlfluff`
2. Install the dbt adapter: `pip install dbt-databricks`

#### 3. Database Connection Errors in CI

**Cause**: The dbt templater attempts database connections for compile-time operations.

**Solution**: Create a dummy `profiles.yml` with placeholder credentials. Many SQLFluff operations don't require actual database access.

#### 4. Slow Performance with dbt Templater

**Cause**: dbt templater is slower than Jinja templater due to full dbt compilation.

**Solutions**:
- Use Jinja templater for IDE/git hooks: `templater = jinja`
- Use dbt templater for CI where accuracy matters
- Increase `processes` setting for parallelism
- Add `large_file_skip_byte_limit` to skip very large files

#### 5. Macro Linting Issues

**Cause**: SQLFluff may not properly lint SQL generated by macros.

**Workaround**: This is a [known limitation](https://github.com/sqlfluff/sqlfluff/issues/4641). Complex macros may require inline ignores:
```sql
-- sqlfluff:disable=all
{{ my_complex_macro() }}
-- sqlfluff:enable=all
```

### Debugging Commands

```bash
# Parse a file to see how SQLFluff interprets it
sqlfluff parse models/my_model.sql

# Lint with verbose output
sqlfluff lint models/my_model.sql -v

# Test configuration
sqlfluff lint --dialect databricks --templater dbt models/my_model.sql

# Fix issues automatically
sqlfluff fix models/my_model.sql
```

### Templater Comparison

| Feature | dbt Templater | Jinja Templater |
|---------|---------------|-----------------|
| Speed | Slower | Faster |
| Accuracy | Higher (full dbt context) | Lower |
| Database needed | Sometimes | No |
| Macro support | Full | Limited |
| Best for | CI/CD | IDE, git hooks |

---

## Sources

### Official Documentation
- [SQLFluff Documentation](https://docs.sqlfluff.com/en/stable/)
- [dbt Templater Configuration](https://docs.sqlfluff.com/en/stable/configuration/templating/dbt.html)
- [SQLFluff Rules Reference](https://docs.sqlfluff.com/en/stable/reference/rules.html)
- [SQLFluff Pre-commit Setup](https://docs.sqlfluff.com/en/latest/production/pre_commit.html)

### GitHub Resources
- [SQLFluff GitHub Repository](https://github.com/sqlfluff/sqlfluff)
- [SQLFluff GitHub Actions](https://github.com/sqlfluff/sqlfluff-github-actions)
- [sqlfluff-templater-dbt on PyPI](https://pypi.org/project/sqlfluff-templater-dbt/)

### dbt Resources
- [dbt SQL Style Guide](https://docs.getdbt.com/best-practices/how-we-style/2-how-we-style-our-sql)
- [dbt Labs Jaffle Shop .sqlfluff](https://github.com/dbt-labs/jaffle-shop-template/blob/main/.sqlfluff)
- [Best Practices for dbt on Databricks](https://www.databricks.com/blog/2022/12/15/best-practices-super-powering-your-dbt-project-databricks.html)

### Community & Troubleshooting
- [Troubleshooting dbt Profiles for SQLFluff](https://community.dataops.live/guides-47/crisp-understanding-troubleshooting-dbt-profiles-for-sqlfluff-pre-commit-hooks-123)
- [SQLFluff Troubleshooting Guide](https://docs.sqlfluff.com/en/stable/guides/troubleshooting/how_to.html)
- [Databricks Compatibility Issue #6006](https://github.com/sqlfluff/sqlfluff/issues/6006)
- [VS Code Multi-Project Discussion #83](https://github.com/sqlfluff/vscode-sqlfluff/issues/83)
- [SQLFluff Configuration Hierarchy](https://docs.sqlfluff.com/en/stable/configuration/setting_configuration.html)
