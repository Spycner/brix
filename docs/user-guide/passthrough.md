# dbt Passthrough

Brix transparently passes through any dbt command that isn't a built-in brix command.

## How It Works

When you run a command like `brix dbt run`, brix checks if `run` is a built-in subcommand. Since it isn't, brix passes the command directly to the dbt CLI.

```bash
brix dbt run        # Executes: dbt run
brix dbt test       # Executes: dbt test
brix dbt build      # Executes: dbt build
```

## Project Path Caching

Brix caches the project path for convenience. When you specify a project once, subsequent commands use the same path:

```bash
# First command sets the project path
brix dbt -p ./my_project run

# Subsequent commands use the cached path
brix dbt test
brix dbt docs generate
```

The cache is stored in `~/.cache/brix/dbt_project_path.json`.

To use a different project:

```bash
brix dbt -p ./other_project run
```

## Common dbt Commands

### Model Execution

```bash
# Run all models
brix dbt run

# Run specific model
brix dbt run --select my_model

# Run models with tags
brix dbt run --select tag:daily

# Full refresh incremental models
brix dbt run --full-refresh
```

### Testing

```bash
# Run all tests
brix dbt test

# Test specific model
brix dbt test --select my_model

# Run only data tests
brix dbt test --select test_type:data

# Run only schema tests
brix dbt test --select test_type:schema
```

### Build

```bash
# Run + test in dependency order
brix dbt build

# Build specific models
brix dbt build --select staging.*
```

### Seeds

```bash
# Load all seed files
brix dbt seed

# Load specific seed
brix dbt seed --select countries
```

### Snapshots

```bash
# Run all snapshots
brix dbt snapshot

# Run specific snapshot
brix dbt snapshot --select orders_snapshot
```

### Documentation

```bash
# Generate docs
brix dbt docs generate

# Serve docs locally
brix dbt docs serve

# Serve on specific port
brix dbt docs serve --port 8080
```

### Dependencies

```bash
# Install packages
brix dbt deps
```

### Debugging

```bash
# Debug configuration
brix dbt debug

# Show compiled SQL
brix dbt compile --select my_model

# List resources
brix dbt ls
brix dbt ls --select tag:pii
```

### Source Management

```bash
# Check source freshness
brix dbt source freshness
```

## Passing Arguments

All dbt arguments work as expected:

```bash
# Multiple selectors
brix dbt run --select model1 model2

# Exclude models
brix dbt run --exclude staging.*

# Set variables
brix dbt run --vars '{"start_date": "2024-01-01"}'

# Target specific environment
brix dbt run --target prod

# Thread count
brix dbt run --threads 8

# Fail fast
brix dbt run --fail-fast
```

## Environment Variables

dbt environment variables work normally:

```bash
export DBT_PROFILES_DIR=./custom_profiles
export DBT_TARGET=production

brix dbt run
```

## Limitations

- The project path cache is per-user, not per-terminal session
- brix-specific options (`--log-level`, etc.) must come before `dbt`

```bash
# Correct
brix --log-level DEBUG dbt run

# Also correct
brix dbt -p ./project run --select my_model
```
