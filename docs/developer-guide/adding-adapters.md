# Adding Adapters

Guide for adding new database adapter support to brix.

## Overview

Brix supports multiple dbt adapters through Pydantic models with discriminated unions. Adding a new adapter requires:

1. Creating a Pydantic model for the adapter
2. Adding to the discriminated union
3. Implementing interactive prompts
4. Adding tests

## Step 1: Create the Model

Add a new model in `src/brix/modules/dbt/profile/models.py`:

```python
from pydantic import BaseModel, Field

class SnowflakeOutput(BaseModel):
    """Snowflake adapter output configuration."""

    type: Literal["snowflake"] = "snowflake"
    account: str = Field(..., description="Snowflake account identifier")
    user: str = Field(..., description="Username")
    password: str | None = Field(None, description="Password (use env_var)")
    role: str = Field(..., description="Role to use")
    database: str = Field(..., description="Database name")
    warehouse: str = Field(..., description="Warehouse name")
    schema_: str = Field(..., alias="schema", description="Schema name")
    threads: int = Field(4, description="Number of threads")

    model_config = ConfigDict(populate_by_name=True)
```

Key considerations:
- Use `Literal["adapter_name"]` for the `type` field
- Use `Field(...)` for required fields
- Use `Field(alias="schema")` for reserved Python keywords
- Document fields with `description`

## Step 2: Add to Discriminated Union

Update the `OutputConfig` type in `models.py`:

```python
OutputConfig = Annotated[
    DuckDbOutput | DatabricksOutput | SnowflakeOutput,
    Field(discriminator="type"),
]
```

The discriminator ensures the correct model is used based on the `type` field.

## Step 3: Add Interactive Prompts

Add prompts in `src/brix/modules/dbt/profile/prompts.py`:

```python
import questionary

def prompt_snowflake_output(name: str = "") -> SnowflakeOutput:
    """Prompt for Snowflake output configuration."""
    name = name or questionary.text(
        "Output name:",
        default="prod",
    ).ask()

    account = questionary.text(
        "Snowflake account:",
        instruction="e.g., xy12345.us-east-1",
    ).ask()

    user = questionary.text("Username:").ask()

    password = questionary.password(
        "Password (leave empty to use env var):"
    ).ask()

    role = questionary.text(
        "Role:",
        default="ACCOUNTADMIN",
    ).ask()

    database = questionary.text("Database:").ask()
    warehouse = questionary.text("Warehouse:").ask()
    schema = questionary.text("Schema:", default="public").ask()

    threads = int(questionary.text(
        "Threads:",
        default="4",
    ).ask())

    # Use env_var for password if not provided
    password_value = (
        password if password
        else "{{ env_var('DBT_SNOWFLAKE_PASSWORD') }}"
    )

    return SnowflakeOutput(
        type="snowflake",
        account=account,
        user=user,
        password=password_value,
        role=role,
        database=database,
        warehouse=warehouse,
        schema=schema,
        threads=threads,
    )
```

## Step 4: Register in Adapter Selection

Update the adapter selection in `prompts.py`:

```python
def prompt_output_type() -> str:
    """Prompt for adapter type selection."""
    return questionary.select(
        "Select adapter type:",
        choices=[
            "duckdb",
            "databricks",
            "snowflake",  # Add new adapter
        ],
    ).ask()


def prompt_new_output(adapter_type: str, name: str = "") -> OutputConfig:
    """Create output based on selected adapter type."""
    if adapter_type == "duckdb":
        return prompt_duckdb_output(name)
    elif adapter_type == "databricks":
        return prompt_databricks_output(name)
    elif adapter_type == "snowflake":
        return prompt_snowflake_output(name)
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
```

## Step 5: Add Tests

### Unit Tests

Create `tests/unit/test_snowflake_models.py`:

```python
import pytest
from brix.modules.dbt.profile.models import SnowflakeOutput, OutputConfig

def test_snowflake_output_creation():
    output = SnowflakeOutput(
        account="xy12345.us-east-1",
        user="dbt_user",
        password="{{ env_var('DBT_SNOWFLAKE_PASSWORD') }}",
        role="TRANSFORM_ROLE",
        database="ANALYTICS",
        warehouse="COMPUTE_WH",
        schema="dbt_prod",
    )
    assert output.type == "snowflake"
    assert output.account == "xy12345.us-east-1"

def test_snowflake_output_discriminator():
    """Test that discriminated union correctly identifies Snowflake."""
    data = {
        "type": "snowflake",
        "account": "xy12345",
        "user": "user",
        "role": "role",
        "database": "db",
        "warehouse": "wh",
        "schema": "public",
    }
    # This would be used when parsing YAML
    from pydantic import TypeAdapter
    adapter = TypeAdapter(OutputConfig)
    output = adapter.validate_python(data)
    assert isinstance(output, SnowflakeOutput)
```

### Integration Tests

Create `tests/integration/test_snowflake_profile.py`:

```python
import pytest
from pathlib import Path
from brix.modules.dbt.profile.models import DbtProfiles, SnowflakeOutput

@pytest.mark.integration
def test_snowflake_profile_yaml_roundtrip(tmp_path: Path):
    """Test Snowflake profile YAML serialization."""
    profiles = DbtProfiles(
        profiles={
            "snowflake_project": {
                "target": "prod",
                "outputs": {
                    "prod": SnowflakeOutput(
                        account="xy12345",
                        user="dbt",
                        role="transform",
                        database="analytics",
                        warehouse="compute",
                        schema="dbt",
                    ),
                },
            },
        },
    )

    yaml_path = tmp_path / "profiles.yml"
    yaml_path.write_text(profiles.to_yaml())

    loaded = DbtProfiles.from_yaml(yaml_path.read_text())
    assert "snowflake_project" in loaded.profiles
```

## Step 6: Update Documentation

Add adapter documentation in `docs/user-guide/profiles.md`:

```markdown
### Snowflake

For Snowflake data warehouse.

#### Configuration

```yaml
outputs:
  prod:
    type: snowflake
    account: xy12345.us-east-1
    user: dbt_user
    password: "{{ env_var('DBT_SNOWFLAKE_PASSWORD') }}"
    role: TRANSFORM_ROLE
    database: ANALYTICS
    warehouse: COMPUTE_WH
    schema: dbt_prod
    threads: 4
```
```

## Checklist

- [ ] Create Pydantic model with all required fields
- [ ] Add to `OutputConfig` discriminated union
- [ ] Implement `prompt_*_output()` function
- [ ] Update `prompt_output_type()` choices
- [ ] Update `prompt_new_output()` dispatcher
- [ ] Add unit tests for model validation
- [ ] Add integration tests for YAML roundtrip
- [ ] Update documentation with configuration examples
- [ ] Run full test suite: `uv run poe test`
- [ ] Run pre-commit: `uv run poe pre-commit`
