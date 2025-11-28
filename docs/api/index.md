# API Reference

Brix can be used as a Python library in addition to the CLI.

## Overview

The brix package is organized into modules that can be imported directly:

```python
from brix.modules.dbt.profile.models import DbtProfiles, DuckDbOutput
from brix.modules.dbt.profile.service import init_profile
from brix.modules.dbt.project.models import DbtProject
```

## Package Structure

```
brix.modules.dbt.profile
├── models      # Pydantic models for profiles.yml
├── service     # Profile initialization and operations
├── editor      # Profile CRUD operations
└── prompts     # Interactive prompts

brix.modules.dbt.project
├── models      # Pydantic models for dbt_project.yml
├── service     # Project initialization
├── editor      # Project CRUD operations
├── finder      # Project discovery
└── prompts     # Interactive prompts

brix.utils
└── logging     # Terraform-style logger
```

## Quick Examples

### Working with Profiles

```python
from brix.modules.dbt.profile.models import DbtProfiles, DuckDbOutput

# Create a profile programmatically
profiles = DbtProfiles(
    profiles={
        "my_project": {
            "target": "dev",
            "outputs": {
                "dev": DuckDbOutput(path="./dev.duckdb"),
            },
        },
    },
)

# Serialize to YAML
yaml_content = profiles.to_yaml()

# Parse from YAML
loaded = DbtProfiles.from_yaml(yaml_content)
```

### Working with Projects

```python
from brix.modules.dbt.project.models import DbtProject

# Load a project
with open("dbt_project.yml") as f:
    project = DbtProject.from_yaml(f.read())

# Modify
project.name = "new_name"

# Save
with open("dbt_project.yml", "w") as f:
    f.write(project.to_yaml())
```

## Reference Sections

- [Modules](modules.md) - Service and editor functions
- [Models](models.md) - Pydantic data models
