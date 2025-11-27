"""Pydantic models for dbt profile configuration.

These models provide type-safe parsing and validation of dbt profiles.yml files.
Currently supports DuckDB adapter, extensible for other adapters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class DuckDbOutput(BaseModel):
    """DuckDB adapter output configuration."""

    model_config = ConfigDict(extra="allow")

    type: Literal["duckdb"]
    path: str = ":memory:"
    threads: int = 1


# Union of all supported output types - extend as needed
OutputConfig = Annotated[DuckDbOutput, Field(discriminator="type")]


class ProfileTarget(BaseModel):
    """A dbt profile with target selection and output configurations."""

    model_config = ConfigDict(extra="allow")

    target: str
    outputs: dict[str, OutputConfig]


class DbtProfiles(BaseModel):
    """Root model for profiles.yml - a mapping of profile names to configurations."""

    model_config = ConfigDict(extra="allow")

    root: dict[str, ProfileTarget]

    def __getitem__(self, key: str) -> ProfileTarget:
        """Allow dict-like access to profiles."""
        return self.root[key]

    def __contains__(self, key: str) -> bool:
        """Check if profile exists."""
        return key in self.root

    @classmethod
    def from_yaml(cls, content: str) -> DbtProfiles:
        """Parse profiles from YAML string.

        Args:
            content: YAML string content of profiles.yml

        Returns:
            Parsed DbtProfiles instance

        Raises:
            ValueError: If YAML is invalid or doesn't match schema
        """
        import yaml

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            msg = f"Invalid YAML: {e}"
            raise ValueError(msg) from e

        if not isinstance(data, dict):
            msg = "profiles.yml must be a YAML mapping"
            raise ValueError(msg)

        return cls(root=data)

    @classmethod
    def from_file(cls, path: Path) -> DbtProfiles:
        """Load profiles from a file path.

        Args:
            path: Path to profiles.yml file

        Returns:
            Parsed DbtProfiles instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or doesn't match schema
        """
        content = path.read_text()
        return cls.from_yaml(content)

    def to_yaml(self) -> str:
        """Serialize profiles to YAML string.

        Returns:
            YAML string representation
        """
        import yaml

        # Convert to dict, handling nested models
        data = {name: profile.model_dump(exclude_none=True) for name, profile in self.root.items()}
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
