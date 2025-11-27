"""Pydantic models for dbt project configuration.

These models provide type-safe parsing and validation of dbt_project.yml
and packages.yml files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Project name validation regex - must start with letter/underscore, contain only alphanumeric/underscore
PROJECT_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class ProjectNameError(ValueError):
    """Raised when project name is invalid."""


def validate_project_name(name: str) -> str:
    """Validate a dbt project name.

    Args:
        name: Project name to validate

    Returns:
        The validated project name

    Raises:
        ProjectNameError: If name doesn't match dbt requirements
    """
    if not PROJECT_NAME_PATTERN.match(name):
        msg = (
            f"Invalid project name: '{name}'. "
            "Project name must start with a letter or underscore and contain only "
            "alphanumeric characters and underscores."
        )
        raise ProjectNameError(msg)
    return name


class DbtProject(BaseModel):
    """Pydantic model for dbt_project.yml configuration.

    Represents the structure and configuration options for a dbt project.
    Supports YAML serialization via from_yaml() and to_yaml() methods.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Required fields
    name: str
    profile: str

    # Version fields
    version: str = "1.0.0"
    config_version: Literal[2] = Field(default=2, alias="config-version")

    # Path configurations
    model_paths: list[str] = Field(default=["models"], alias="model-paths")
    seed_paths: list[str] = Field(default=["seeds"], alias="seed-paths")
    test_paths: list[str] = Field(default=["tests"], alias="test-paths")
    macro_paths: list[str] = Field(default=["macros"], alias="macro-paths")
    snapshot_paths: list[str] = Field(default=["snapshots"], alias="snapshot-paths")
    analysis_paths: list[str] = Field(default=["analyses"], alias="analysis-paths")
    asset_paths: list[str] = Field(default=["assets"], alias="asset-paths")

    # Build configuration
    clean_targets: list[str] = Field(default=["target", "dbt_packages"], alias="clean-targets")
    require_dbt_version: str | None = Field(default=None, alias="require-dbt-version")

    # Model defaults (optional)
    models: dict[str, Any] | None = None
    seeds: dict[str, Any] | None = None
    vars: dict[str, Any] | None = None

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate project name follows dbt requirements."""
        return validate_project_name(v)

    @classmethod
    def from_yaml(cls, content: str) -> DbtProject:
        """Parse project configuration from YAML string.

        Args:
            content: YAML string content of dbt_project.yml

        Returns:
            Parsed DbtProject instance

        Raises:
            ValueError: If YAML is invalid or doesn't match schema
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            msg = f"Invalid YAML: {e}"
            raise ValueError(msg) from e

        if not isinstance(data, dict):
            msg = "dbt_project.yml must be a YAML mapping"
            raise ValueError(msg)

        return cls(**data)

    @classmethod
    def from_file(cls, path: Path) -> DbtProject:
        """Load project configuration from a file path.

        Args:
            path: Path to dbt_project.yml file

        Returns:
            Parsed DbtProject instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or doesn't match schema
        """
        content = path.read_text()
        return cls.from_yaml(content)

    def to_yaml(self) -> str:
        """Serialize project configuration to YAML string.

        Returns:
            YAML string representation
        """
        # Convert to dict, using aliases for YAML keys
        data = self.model_dump(exclude_none=True, by_alias=True)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)


# Package type models for packages.yml


class HubPackage(BaseModel):
    """A package from the dbt Hub (hub.getdbt.com).

    Example:
        - package: dbt-labs/dbt_utils
          version: ">=1.0.0"
    """

    model_config = ConfigDict(extra="forbid")

    package: str
    version: str


class GitPackage(BaseModel):
    """A package from a Git repository.

    Example:
        - git: "https://github.com/org/repo.git"
          revision: main
          subdirectory: "path/to/dbt_project"
    """

    model_config = ConfigDict(extra="forbid")

    git: str
    revision: str
    subdirectory: str | None = None


class LocalPackage(BaseModel):
    """A package from the local filesystem.

    Example:
        - local: ../shared_macros
    """

    model_config = ConfigDict(extra="forbid")

    local: str


# Union of all package types
Package = Annotated[HubPackage | GitPackage | LocalPackage, Field(discriminator=None)]


class DbtPackages(BaseModel):
    """Pydantic model for packages.yml configuration.

    Represents the list of dbt packages to install.
    """

    model_config = ConfigDict(extra="forbid")

    packages: list[HubPackage | GitPackage | LocalPackage] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, content: str) -> DbtPackages:
        """Parse packages configuration from YAML string.

        Args:
            content: YAML string content of packages.yml

        Returns:
            Parsed DbtPackages instance

        Raises:
            ValueError: If YAML is invalid or doesn't match schema
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            msg = f"Invalid YAML: {e}"
            raise ValueError(msg) from e

        if data is None:
            return cls(packages=[])

        if not isinstance(data, dict):
            msg = "packages.yml must be a YAML mapping"
            raise ValueError(msg)

        return cls(**data)

    @classmethod
    def from_file(cls, path: Path) -> DbtPackages:
        """Load packages configuration from a file path.

        Args:
            path: Path to packages.yml file

        Returns:
            Parsed DbtPackages instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or doesn't match schema
        """
        content = path.read_text()
        return cls.from_yaml(content)

    def to_yaml(self) -> str:
        """Serialize packages configuration to YAML string.

        Returns:
            YAML string representation
        """
        data = self.model_dump(exclude_none=True)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def add_hub_package(self, package: str, version: str) -> None:
        """Add a hub package to the list.

        Args:
            package: Package name (e.g., "dbt-labs/dbt_utils")
            version: Version specifier (e.g., ">=1.0.0")
        """
        self.packages.append(HubPackage(package=package, version=version))

    def add_git_package(self, git: str, revision: str, subdirectory: str | None = None) -> None:
        """Add a git package to the list.

        Args:
            git: Git repository URL
            revision: Branch, tag, or commit hash
            subdirectory: Optional subdirectory within repo
        """
        self.packages.append(GitPackage(git=git, revision=revision, subdirectory=subdirectory))

    def add_local_package(self, local: str) -> None:
        """Add a local package to the list.

        Args:
            local: Local filesystem path
        """
        self.packages.append(LocalPackage(local=local))
