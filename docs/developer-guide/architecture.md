# Architecture

Brix follows a layered architecture that separates CLI concerns from business logic.

## Project Structure

```
src/brix/
├── commands/              # CLI layer (Typer)
│   └── dbt/
│       ├── __init__.py    # DbtGroup passthrough
│       ├── profile.py     # Profile CLI commands
│       └── project.py     # Project CLI commands
├── modules/               # Business logic layer
│   └── dbt/
│       ├── passthrough.py # dbt CLI execution
│       ├── profile/
│       │   ├── models.py  # Pydantic models
│       │   ├── service.py # Core operations
│       │   ├── editor.py  # CRUD operations
│       │   └── prompts.py # Interactive prompts
│       └── project/
│           ├── models.py
│           ├── service.py
│           ├── editor.py
│           ├── prompts.py
│           └── finder.py  # Project discovery
├── templates/             # Bundled templates
├── utils/
│   └── logging.py         # Terraform-style logger
├── version_check.py       # Background version checking
└── main.py                # Entry point
```

## Layer Separation

### CLI Layer (`commands/`)

Responsibilities:
- Argument parsing with Typer
- Output formatting (typer.echo)
- Error handling and exit codes
- No business logic

### Business Logic Layer (`modules/`)

Responsibilities:
- Core operations (init, edit, validate)
- Data models (Pydantic)
- File I/O
- No CLI dependencies

This separation allows:
- Unit testing without CLI
- Reuse as a library
- Clear responsibility boundaries

## Key Patterns

### DbtGroup Passthrough

The `DbtGroup` class in `commands/dbt/__init__.py` intercepts unknown commands and passes them to the native dbt CLI.

```python
class DbtGroup(TyperGroup):
    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            return None, None, args  # Pass through to dbt

    def invoke(self, ctx):
        if no_command_matched:
            run_dbt(args)  # Execute native dbt
```

This enables `brix dbt run`, `brix dbt test`, etc. to work transparently.

### Pydantic Models with Discriminated Unions

Profile models use discriminated unions for adapter types:

```python
OutputConfig = Annotated[
    DuckDbOutput | DatabricksOutput,
    Field(discriminator="type")
]
```

This provides:
- Type-safe YAML parsing
- Automatic validation
- Clear error messages

### Configuration with pydantic-settings

All configuration uses `BaseSettings` with `BRIX_` prefix:

```python
class ProfileConfig(BaseSettings):
    profile_path: Path = Path("~/.dbt/profiles.yml")

    model_config = SettingsConfigDict(env_prefix="BRIX_DBT_")
```

Override chain: CLI args > env vars > defaults

### Result Objects

Operations return structured result objects instead of exceptions:

```python
@dataclass
class ProfileInitResult:
    success: bool
    path: Path
    action: str  # "created", "exists", "overwritten"
    message: str
```

### Thread-safe Logging

The logger is a singleton with thread-safe initialization:

```python
logger = get_logger()  # Always returns same instance
logger.debug("message %s", arg)  # Lazy evaluation
```

Features:
- Custom TRACE level
- Terraform-style output
- JSON format support
- Non-blocking version check

### Template System

Templates are bundled with the package and loaded via `importlib.resources`:

```python
from brix.templates import get_template

content = get_template("profiles.yml")
```

## Data Flow

```
User Input (CLI)
      ↓
commands/ (Typer)
      │
      ├── Parse arguments
      ├── Validate input
      └── Call business logic
      ↓
modules/
      │
      ├── models.py → Validate data structures
      ├── service.py → Execute operations
      ├── editor.py → Modify files
      └── prompts.py → Interactive input
      ↓
File System / dbt CLI
      ↓
Result object
      ↓
commands/
      │
      └── Format output (typer.echo)
      ↓
User Output
```

## Module Structure Convention

Each domain follows this structure:

| File | Purpose |
|------|---------|
| `models.py` | Pydantic data models |
| `service.py` | Initialization, resolution, fetching |
| `editor.py` | CRUD operations |
| `prompts.py` | questionary interactive prompts |

## Dependencies

**Runtime:**
- `typer` - CLI framework
- `pydantic` / `pydantic-settings` - Data validation
- `questionary` - Interactive prompts
- `httpx` - HTTP requests

**Development:**
- `ruff` - Linting and formatting
- `ty` - Type checking
- `pytest` - Testing
- `dbt-core`, `dbt-databricks`, `dbt-duckdb` - Integration tests
