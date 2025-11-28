"""Pydantic models for dbt profile configuration.

These models provide type-safe parsing and validation of dbt profiles.yml files.
Supports DuckDB and Databricks adapters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self


class DuckDbOutput(BaseModel):
    """DuckDB adapter output configuration.

    Supports all dbt-duckdb adapter options including extensions and settings.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: Literal["duckdb"]
    path: str = ":memory:"
    schema_: str = Field(default="main", alias="schema")
    database: str = "main"
    threads: int = 1
    extensions: list[str] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_database_with_memory_path(self) -> Self:
        """Set database to 'memory' when path is ':memory:' for dbt-duckdb compatibility."""
        if self.path == ":memory:" and self.database != "memory":
            self.database = "memory"
        return self


# Authentication method types for Databricks
DatabricksAuthType = Literal["oauth"]


class DatabricksOutput(BaseModel):
    """Databricks adapter output configuration.

    Supports multiple authentication methods:
    - Token-based: Personal Access Token (PAT)
    - OAuth U2M: User-to-machine (browser-based, no secrets needed)
    - OAuth M2M (AWS/GCP): Machine-to-machine with client_id/client_secret
    - OAuth M2M (Azure): Machine-to-machine with azure_client_id/azure_client_secret
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: Literal["databricks"]

    # Required connection fields
    schema_: str = Field(alias="schema")
    host: str
    http_path: str

    # Authentication - exactly one method required (validated via model_validator)
    token: str | None = None
    auth_type: DatabricksAuthType | None = None
    client_id: str | None = None
    client_secret: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None

    # Optional fields
    catalog: str | None = None
    threads: int = 1
    connect_retries: int = 0
    connect_timeout: int | None = None

    @field_validator("host", mode="before")
    @classmethod
    def strip_host_protocol(cls, v: str) -> str:
        """Strip http:// or https:// prefix from host if present."""
        if isinstance(v, str):
            if v.startswith("https://"):
                return v[8:]
            if v.startswith("http://"):
                return v[7:]
        return v

    @field_validator("http_path", mode="before")
    @classmethod
    def ensure_http_path_starts_with_slash(cls, v: str) -> str:
        """Ensure http_path starts with /."""
        if isinstance(v, str) and not v.startswith("/"):
            return f"/{v}"
        return v

    @field_validator("threads", mode="after")
    @classmethod
    def validate_threads(cls, v: int) -> int:
        """Ensure threads is at least 1."""
        if v < 1:
            msg = "threads must be at least 1"
            raise ValueError(msg)
        return v

    @field_validator("connect_retries", mode="after")
    @classmethod
    def validate_connect_retries(cls, v: int) -> int:
        """Ensure connect_retries is non-negative."""
        if v < 0:
            msg = "connect_retries must be non-negative"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_auth_method(self) -> Self:
        """Validate that exactly one authentication method is configured.

        Valid configurations:
        - token alone (PAT)
        - auth_type='oauth' alone (U2M)
        - auth_type='oauth' + client_id + client_secret (M2M AWS/GCP)
        - auth_type='oauth' + azure_client_id + azure_client_secret (M2M Azure)
        """
        has_token = self.token is not None
        has_oauth = self.auth_type == "oauth"
        has_client_creds = self.client_id is not None or self.client_secret is not None
        has_azure_creds = self.azure_client_id is not None or self.azure_client_secret is not None

        # Token-based auth
        if has_token:
            if has_oauth or has_client_creds or has_azure_creds:
                msg = "Cannot use token authentication with OAuth settings"
                raise ValueError(msg)
            return self

        # OAuth-based auth
        if has_oauth:
            # Validate client credentials are complete if provided
            if has_client_creds:
                if not (self.client_id and self.client_secret):
                    msg = "Both client_id and client_secret are required for OAuth M2M (AWS/GCP)"
                    raise ValueError(msg)
                if has_azure_creds:
                    msg = "Cannot mix AWS/GCP and Azure OAuth credentials"
                    raise ValueError(msg)
                return self

            # Validate Azure credentials are complete if provided
            if has_azure_creds:
                if not (self.azure_client_id and self.azure_client_secret):
                    msg = "Both azure_client_id and azure_client_secret are required for OAuth M2M (Azure)"
                    raise ValueError(msg)
                return self

            # U2M OAuth (no credentials needed)
            return self

        # No auth configured - allow this for profiles with env var references
        # The connection test will catch invalid configurations at runtime
        if has_client_creds or has_azure_creds:
            msg = "OAuth credentials require auth_type='oauth'"
            raise ValueError(msg)

        return self


# Union of all supported output types
OutputConfig = Annotated[DuckDbOutput | DatabricksOutput, Field(discriminator="type")]


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
        # Use by_alias=True to output 'schema' instead of 'schema_'
        data = {name: profile.model_dump(exclude_none=True, by_alias=True) for name, profile in self.root.items()}
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
