"""dbt profiles.yml parsing and validation."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from databricks_dbt_cli.utils.exceptions import ProfileNotFoundError, ProfileValidationError


class DatabricksTarget(BaseModel):
    """A Databricks target configuration from dbt profiles.yml."""

    host: str
    token_env_var: str | None = None
    http_path: str | None = None
    catalog: str | None = None
    schema_name: str | None = None

    @field_validator("host", mode="before")
    @classmethod
    def normalize_host(cls, v: str) -> str:
        """Ensure host doesn't have trailing slashes."""
        return v.rstrip("/") if isinstance(v, str) else v


class DbtProfile(BaseModel):
    """A dbt profile with multiple targets."""

    name: str
    targets: dict[str, DatabricksTarget]
    default_target: str | None = None


def get_default_profiles_path() -> Path:
    """Get the default path to profiles.yml.

    Returns:
        Path to ~/.dbt/profiles.yml
    """
    return Path.home() / ".dbt" / "profiles.yml"


def _extract_env_var(value: str) -> str | None:
    """Extract environment variable name from env_var() syntax.

    Args:
        value: The YAML value that may contain env_var('VAR_NAME')

    Returns:
        The environment variable name, or None if not found.
    """
    if not isinstance(value, str):
        return None

    match = re.search(r"env_var\s*\(\s*['\"]([^'\"]+)['\"]", value)
    return match.group(1) if match else None


def _parse_target(target_config: dict) -> DatabricksTarget | None:
    """Parse a single target configuration.

    Args:
        target_config: The raw target configuration dict.

    Returns:
        DatabricksTarget if valid Databricks config, None otherwise.
    """
    if target_config.get("type") != "databricks":
        return None

    host = target_config.get("host")
    if not host:
        return None

    token_value = target_config.get("token", "")
    token_env_var = _extract_env_var(str(token_value)) if token_value else None

    return DatabricksTarget(
        host=host,
        token_env_var=token_env_var,
        http_path=target_config.get("http_path"),
        catalog=target_config.get("catalog"),
        schema_name=target_config.get("schema"),
    )


def _load_yaml_file(path: Path) -> dict:
    """Load and parse a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        The parsed YAML data as a dict.

    Raises:
        ProfileNotFoundError: If the file doesn't exist.
        ProfileValidationError: If the YAML is invalid.
    """
    if not path.exists():
        msg = f"profiles.yml not found at: {path}"
        raise ProfileNotFoundError(msg)

    try:
        content = path.read_text()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in profiles.yml: {e}"
        raise ProfileValidationError(msg) from e

    if not isinstance(data, dict):
        msg = "profiles.yml must contain a YAML mapping"
        raise ProfileValidationError(msg)

    return data


def _extract_profile_data(profiles_data: dict, profile_name: str) -> dict:
    """Extract and validate profile data from profiles.yml content.

    Args:
        profiles_data: The parsed profiles.yml content.
        profile_name: Name of the profile to extract.

    Returns:
        The profile data dict.

    Raises:
        ProfileNotFoundError: If the profile doesn't exist.
        ProfileValidationError: If the profile is invalid.
    """
    if profile_name not in profiles_data:
        available = [k for k in profiles_data if not k.startswith("config")]
        msg = f"Profile '{profile_name}' not found. Available profiles: {available}"
        raise ProfileNotFoundError(msg)

    profile_data = profiles_data[profile_name]
    if not isinstance(profile_data, dict):
        msg = f"Profile '{profile_name}' must be a mapping"
        raise ProfileValidationError(msg)

    return profile_data


def _parse_targets(outputs: dict, profile_name: str) -> dict[str, DatabricksTarget]:
    """Parse all Databricks targets from profile outputs.

    Args:
        outputs: The outputs section of a profile.
        profile_name: Name of the profile (for error messages).

    Returns:
        Dict of target name to DatabricksTarget.

    Raises:
        ProfileValidationError: If no valid targets found.
    """
    targets: dict[str, DatabricksTarget] = {}
    for target_name, target_config in outputs.items():
        if not isinstance(target_config, dict):
            continue
        target = _parse_target(target_config)
        if target:
            targets[target_name] = target

    if not targets:
        msg = f"Profile '{profile_name}' has no valid Databricks targets"
        raise ProfileValidationError(msg)

    return targets


def load_profile(path: Path, profile_name: str) -> DbtProfile:
    """Load and parse a dbt profile from profiles.yml.

    Args:
        path: Path to the profiles.yml file.
        profile_name: Name of the profile to load.

    Returns:
        The parsed DbtProfile.

    Raises:
        ProfileNotFoundError: If the file or profile doesn't exist.
        ProfileValidationError: If the profile configuration is invalid.
    """
    profiles_data = _load_yaml_file(path)
    profile_data = _extract_profile_data(profiles_data, profile_name)

    outputs = profile_data.get("outputs", {})
    if not outputs:
        msg = f"Profile '{profile_name}' has no outputs defined"
        raise ProfileValidationError(msg)

    targets = _parse_targets(outputs, profile_name)

    return DbtProfile(
        name=profile_name,
        targets=targets,
        default_target=profile_data.get("target"),
    )
