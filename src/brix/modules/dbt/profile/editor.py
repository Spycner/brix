"""Profile editing service for dbt profiles.yml.

Provides CRUD operations for profiles and outputs with atomic save-on-change behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from brix.modules.dbt.profile.models import DbtProfiles, OutputConfig, ProfileTarget
from brix.modules.dbt.profile.service import get_default_profile_path
from brix.utils.logging import get_logger


class ProfileNotFoundError(Exception):
    """Raised when a profile does not exist."""


class OutputNotFoundError(Exception):
    """Raised when an output does not exist."""


class ProfileAlreadyExistsError(Exception):
    """Raised when attempting to create a profile that already exists."""


class OutputAlreadyExistsError(Exception):
    """Raised when attempting to create an output that already exists."""


def load_profiles(path: Path | None = None) -> DbtProfiles:
    """Load profiles from disk.

    Args:
        path: Path to profiles.yml, uses default if None

    Returns:
        Parsed DbtProfiles instance

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid
    """
    target_path = path or get_default_profile_path()
    logger = get_logger()
    logger.debug("Loading profiles from %s", target_path)
    return DbtProfiles.from_file(target_path)


def save_profiles(profiles: DbtProfiles, path: Path | None = None) -> None:
    """Validate and save profiles to disk.

    Args:
        profiles: DbtProfiles instance to save
        path: Path to profiles.yml, uses default if None

    Raises:
        ValueError: If profiles fail validation
        IOError: If file cannot be written
    """
    target_path = path or get_default_profile_path()
    logger = get_logger()

    # Validate by re-parsing (ensures YAML roundtrip is valid)
    yaml_content = profiles.to_yaml()
    DbtProfiles.from_yaml(yaml_content)

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to disk
    target_path.write_text(yaml_content)
    logger.debug("Saved profiles to %s", target_path)


def get_profile_names(profiles: DbtProfiles) -> list[str]:
    """Get list of profile names.

    Args:
        profiles: DbtProfiles instance

    Returns:
        List of profile names
    """
    return list(profiles.root.keys())


def get_output_names(profiles: DbtProfiles, profile_name: str) -> list[str]:
    """Get list of output names for a profile.

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile

    Returns:
        List of output names

    Raises:
        ProfileNotFoundError: If profile doesn't exist
    """
    if profile_name not in profiles.root:
        msg = f"Profile '{profile_name}' not found"
        raise ProfileNotFoundError(msg)
    return list(profiles.root[profile_name].outputs.keys())


def add_profile(
    profiles: DbtProfiles,
    name: str,
    target: str,
    output_name: str,
    output_config: OutputConfig,
) -> DbtProfiles:
    """Add a new profile.

    Args:
        profiles: DbtProfiles instance
        name: Profile name
        target: Default target name
        output_name: Initial output name
        output_config: Initial output configuration (DuckDbOutput or DatabricksOutput)

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileAlreadyExistsError: If profile already exists
    """
    if name in profiles.root:
        msg = f"Profile '{name}' already exists"
        raise ProfileAlreadyExistsError(msg)

    profiles.root[name] = ProfileTarget(
        target=target,
        outputs={output_name: output_config},
    )
    return profiles


def update_profile_target(profiles: DbtProfiles, name: str, target: str) -> DbtProfiles:
    """Update a profile's default target.

    Args:
        profiles: DbtProfiles instance
        name: Profile name
        target: New default target name

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileNotFoundError: If profile doesn't exist
    """
    if name not in profiles.root:
        msg = f"Profile '{name}' not found"
        raise ProfileNotFoundError(msg)

    profiles.root[name].target = target
    return profiles


def delete_profile(profiles: DbtProfiles, name: str) -> DbtProfiles:
    """Delete a profile.

    Args:
        profiles: DbtProfiles instance
        name: Profile name to delete

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileNotFoundError: If profile doesn't exist
    """
    if name not in profiles.root:
        msg = f"Profile '{name}' not found"
        raise ProfileNotFoundError(msg)

    del profiles.root[name]
    return profiles


def add_output(
    profiles: DbtProfiles,
    profile_name: str,
    output_name: str,
    output_config: OutputConfig,
) -> DbtProfiles:
    """Add an output to a profile.

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile
        output_name: Name for the new output
        output_config: Output configuration (DuckDbOutput or DatabricksOutput)

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileNotFoundError: If profile doesn't exist
        OutputAlreadyExistsError: If output already exists
    """
    if profile_name not in profiles.root:
        msg = f"Profile '{profile_name}' not found"
        raise ProfileNotFoundError(msg)

    if output_name in profiles.root[profile_name].outputs:
        msg = f"Output '{output_name}' already exists in profile '{profile_name}'"
        raise OutputAlreadyExistsError(msg)

    profiles.root[profile_name].outputs[output_name] = output_config
    return profiles


def update_output(
    profiles: DbtProfiles,
    profile_name: str,
    output_name: str,
    *,
    path: str | None = None,
    threads: int | None = None,
) -> DbtProfiles:
    """Update a DuckDB output's configuration (legacy interface).

    For updating any adapter type, use update_output_fields() instead.

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile
        output_name: Name of the output
        path: New path value (optional, DuckDB only)
        threads: New threads value (optional)

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileNotFoundError: If profile doesn't exist
        OutputNotFoundError: If output doesn't exist
        ValueError: If threads is not a positive integer
    """
    updates: dict[str, Any] = {}
    if path is not None:
        updates["path"] = path
    if threads is not None:
        updates["threads"] = threads
    return update_output_fields(profiles, profile_name, output_name, updates)


def update_output_fields(
    profiles: DbtProfiles,
    profile_name: str,
    output_name: str,
    updates: dict[str, Any],
) -> DbtProfiles:
    """Update an output's configuration with arbitrary field updates.

    Works with any adapter type (DuckDB, Databricks, etc.).

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile
        output_name: Name of the output
        updates: Dictionary of field names to new values

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileNotFoundError: If profile doesn't exist
        OutputNotFoundError: If output doesn't exist
        ValueError: If validation fails (e.g., threads < 1)
    """
    if profile_name not in profiles.root:
        msg = f"Profile '{profile_name}' not found"
        raise ProfileNotFoundError(msg)

    if output_name not in profiles.root[profile_name].outputs:
        msg = f"Output '{output_name}' not found in profile '{profile_name}'"
        raise OutputNotFoundError(msg)

    output = profiles.root[profile_name].outputs[output_name]

    # Validate threads if being updated
    if "threads" in updates:
        threads = updates["threads"]
        if threads is not None and threads < 1:
            msg = "threads must be a positive integer"
            raise ValueError(msg)

    # Apply updates to the output
    for field, value in updates.items():
        if value is not None:
            setattr(output, field, value)

    return profiles


def delete_output(
    profiles: DbtProfiles,
    profile_name: str,
    output_name: str,
) -> DbtProfiles:
    """Delete an output from a profile.

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile
        output_name: Name of the output to delete

    Returns:
        Updated DbtProfiles instance

    Raises:
        ProfileNotFoundError: If profile doesn't exist
        OutputNotFoundError: If output doesn't exist
        ValueError: If this is the last output in the profile
    """
    if profile_name not in profiles.root:
        msg = f"Profile '{profile_name}' not found"
        raise ProfileNotFoundError(msg)

    if output_name not in profiles.root[profile_name].outputs:
        msg = f"Output '{output_name}' not found in profile '{profile_name}'"
        raise OutputNotFoundError(msg)

    if len(profiles.root[profile_name].outputs) == 1:
        msg = f"Cannot delete last output from profile '{profile_name}'. Delete the profile instead."
        raise ValueError(msg)

    del profiles.root[profile_name].outputs[output_name]
    return profiles


def get_output(profiles: DbtProfiles, profile_name: str, output_name: str) -> OutputConfig:
    """Get an output configuration.

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile
        output_name: Name of the output

    Returns:
        Output configuration (DuckDbOutput or DatabricksOutput)

    Raises:
        ProfileNotFoundError: If profile doesn't exist
        OutputNotFoundError: If output doesn't exist
    """
    if profile_name not in profiles.root:
        msg = f"Profile '{profile_name}' not found"
        raise ProfileNotFoundError(msg)

    if output_name not in profiles.root[profile_name].outputs:
        msg = f"Output '{output_name}' not found in profile '{profile_name}'"
        raise OutputNotFoundError(msg)

    return profiles.root[profile_name].outputs[output_name]
