"""Project editing service for dbt projects.

Provides CRUD operations for dbt_project.yml and packages.yml with atomic save-on-change behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from brix.modules.dbt.project.models import (
    DbtPackages,
    DbtProject,
    GitPackage,
    HubPackage,
    LocalPackage,
    validate_project_name,
)
from brix.utils.logging import get_logger

# Fields that can be edited via CLI
EDITABLE_FIELDS = frozenset(
    {
        "name",
        "profile",
        "version",
        "require_dbt_version",
    }
)

# Path fields that are lists of strings
PATH_FIELDS = frozenset(
    {
        "model_paths",
        "seed_paths",
        "test_paths",
        "macro_paths",
        "snapshot_paths",
        "analysis_paths",
        "asset_paths",
        "clean_targets",
    }
)


class ProjectNotFoundError(Exception):
    """Raised when dbt_project.yml does not exist."""


class PackageNotFoundError(Exception):
    """Raised when a package does not exist in packages.yml."""


class PackageAlreadyExistsError(Exception):
    """Raised when attempting to add a duplicate package."""


class InvalidFieldError(Exception):
    """Raised when attempting to edit an invalid or restricted field."""


def load_project(path: Path) -> DbtProject:
    """Load dbt_project.yml from disk.

    Args:
        path: Path to dbt_project.yml file

    Returns:
        Parsed DbtProject instance

    Raises:
        ProjectNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid
    """
    logger = get_logger()

    if not path.exists():
        msg = f"Project file not found: {path}"
        raise ProjectNotFoundError(msg)

    logger.debug("Loading project from %s", path)
    return DbtProject.from_file(path)


def save_project(project: DbtProject, path: Path) -> None:
    """Validate and save dbt_project.yml to disk.

    Args:
        project: DbtProject instance to save
        path: Path to dbt_project.yml file

    Raises:
        ValueError: If project fails validation
        IOError: If file cannot be written
    """
    logger = get_logger()

    # Validate by re-parsing (ensures YAML roundtrip is valid)
    yaml_content = project.to_yaml()
    DbtProject.from_yaml(yaml_content)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to disk
    path.write_text(yaml_content)
    logger.debug("Saved project to %s", path)


def load_packages(project_dir: Path) -> DbtPackages:
    """Load packages.yml from project directory.

    Args:
        project_dir: Path to project directory (or dbt_project.yml file)

    Returns:
        Parsed DbtPackages instance (empty if file doesn't exist)
    """
    logger = get_logger()

    # Handle both directory and file paths
    if project_dir.name == "dbt_project.yml":
        project_dir = project_dir.parent

    packages_path = project_dir / "packages.yml"

    if not packages_path.exists():
        logger.debug("No packages.yml found at %s, returning empty", packages_path)
        return DbtPackages(packages=[])

    logger.debug("Loading packages from %s", packages_path)
    return DbtPackages.from_file(packages_path)


def save_packages(packages: DbtPackages, project_dir: Path) -> None:
    """Save packages.yml to project directory.

    Args:
        packages: DbtPackages instance to save
        project_dir: Path to project directory (or dbt_project.yml file)

    Raises:
        ValueError: If packages fail validation
        IOError: If file cannot be written
    """
    logger = get_logger()

    # Handle both directory and file paths
    if project_dir.name == "dbt_project.yml":
        project_dir = project_dir.parent

    packages_path = project_dir / "packages.yml"

    # Validate by re-parsing
    yaml_content = packages.to_yaml()
    DbtPackages.from_yaml(yaml_content)

    # Write to disk
    packages_path.write_text(yaml_content)
    logger.debug("Saved packages to %s", packages_path)


def update_project_field(
    project: DbtProject,
    field: str,
    value: str | None,
) -> DbtProject:
    """Update a single project field.

    Args:
        project: DbtProject instance
        field: Field name to update
        value: New value for the field

    Returns:
        Updated DbtProject instance

    Raises:
        InvalidFieldError: If field is not editable
        ValueError: If value fails validation (e.g., invalid project name)
    """
    # Normalize field name (convert dashes to underscores)
    field = field.replace("-", "_")

    if field not in EDITABLE_FIELDS:
        msg = f"Field '{field}' is not editable. Editable fields: {', '.join(sorted(EDITABLE_FIELDS))}"
        raise InvalidFieldError(msg)

    # Special validation for project name
    if field == "name" and value is not None:
        validate_project_name(value)

    setattr(project, field, value)
    return project


def update_path_field(
    project: DbtProject,
    field: str,
    action: Literal["add", "remove", "set"],
    value: str | list[str],
) -> DbtProject:
    """Update a path list field (add/remove/set).

    Args:
        project: DbtProject instance
        field: Field name (model_paths, seed_paths, etc.)
        action: Operation to perform
        value: Path(s) to add/remove, or full list for "set"

    Returns:
        Updated DbtProject instance

    Raises:
        InvalidFieldError: If field is not a path field
        ValueError: If action is invalid or path not found for remove
    """
    # Normalize field name (convert dashes to underscores)
    field = field.replace("-", "_")

    if field not in PATH_FIELDS:
        msg = f"Field '{field}' is not a path field. Path fields: {', '.join(sorted(PATH_FIELDS))}"
        raise InvalidFieldError(msg)

    current_paths: list[str] = getattr(project, field, [])

    if action == "add":
        path_to_add = value if isinstance(value, str) else value[0]
        if path_to_add not in current_paths:
            current_paths.append(path_to_add)
    elif action == "remove":
        path_to_remove = value if isinstance(value, str) else value[0]
        if path_to_remove not in current_paths:
            msg = f"Path '{path_to_remove}' not found in {field}"
            raise ValueError(msg)
        current_paths.remove(path_to_remove)
    elif action == "set":
        current_paths = list(value) if isinstance(value, list) else [value]
    else:
        msg = f"Invalid action: {action}. Must be 'add', 'remove', or 'set'"
        raise ValueError(msg)

    setattr(project, field, current_paths)
    return project


def _get_package_identifier(pkg: HubPackage | GitPackage | LocalPackage) -> str:
    """Get the unique identifier for a package.

    Args:
        pkg: Package instance

    Returns:
        Identifier string (package name, git URL, or local path)
    """
    if isinstance(pkg, HubPackage):
        return pkg.package
    if isinstance(pkg, GitPackage):
        return pkg.git
    return pkg.local


def get_package_identifiers(packages: DbtPackages) -> list[str]:
    """Get list of all package identifiers for display.

    Args:
        packages: DbtPackages instance

    Returns:
        List of package identifiers
    """
    return [_get_package_identifier(pkg) for pkg in packages.packages]


def find_package_index(packages: DbtPackages, identifier: str) -> int | None:
    """Find package index by identifier.

    Args:
        packages: DbtPackages instance
        identifier: Package name (hub), git URL, or local path

    Returns:
        Index of package or None if not found
    """
    for i, pkg in enumerate(packages.packages):
        if _get_package_identifier(pkg) == identifier:
            return i
    return None


def has_package(packages: DbtPackages, identifier: str) -> bool:
    """Check if package exists.

    Args:
        packages: DbtPackages instance
        identifier: Package identifier

    Returns:
        True if package exists
    """
    return find_package_index(packages, identifier) is not None


def add_hub_package(
    packages: DbtPackages,
    package_name: str,
    version: str,
) -> DbtPackages:
    """Add a hub package.

    Args:
        packages: DbtPackages instance
        package_name: Package name (e.g., "dbt-labs/dbt_utils")
        version: Version specifier (e.g., ">=1.0.0")

    Returns:
        Updated DbtPackages instance

    Raises:
        PackageAlreadyExistsError: If package already exists
    """
    if has_package(packages, package_name):
        msg = f"Package '{package_name}' already exists"
        raise PackageAlreadyExistsError(msg)

    packages.packages.append(HubPackage(package=package_name, version=version))
    return packages


def add_git_package(
    packages: DbtPackages,
    git_url: str,
    revision: str,
    subdirectory: str | None = None,
) -> DbtPackages:
    """Add a git package.

    Args:
        packages: DbtPackages instance
        git_url: Git repository URL
        revision: Branch, tag, or commit hash
        subdirectory: Optional subdirectory within repo

    Returns:
        Updated DbtPackages instance

    Raises:
        PackageAlreadyExistsError: If package already exists
    """
    if has_package(packages, git_url):
        msg = f"Git package '{git_url}' already exists"
        raise PackageAlreadyExistsError(msg)

    packages.packages.append(GitPackage(git=git_url, revision=revision, subdirectory=subdirectory))
    return packages


def add_local_package(
    packages: DbtPackages,
    local_path: str,
) -> DbtPackages:
    """Add a local package.

    Args:
        packages: DbtPackages instance
        local_path: Local filesystem path

    Returns:
        Updated DbtPackages instance

    Raises:
        PackageAlreadyExistsError: If package already exists
    """
    if has_package(packages, local_path):
        msg = f"Local package '{local_path}' already exists"
        raise PackageAlreadyExistsError(msg)

    packages.packages.append(LocalPackage(local=local_path))
    return packages


def remove_package(
    packages: DbtPackages,
    identifier: str,
) -> DbtPackages:
    """Remove a package by its identifier.

    Args:
        packages: DbtPackages instance
        identifier: Package name, git URL, or local path

    Returns:
        Updated DbtPackages instance

    Raises:
        PackageNotFoundError: If package not found
    """
    index = find_package_index(packages, identifier)
    if index is None:
        msg = f"Package '{identifier}' not found"
        raise PackageNotFoundError(msg)

    packages.packages.pop(index)
    return packages


def update_package_version(
    packages: DbtPackages,
    package_name: str,
    new_version: str,
) -> DbtPackages:
    """Update a hub package version.

    Args:
        packages: DbtPackages instance
        package_name: Package name (must be a hub package)
        new_version: New version specifier

    Returns:
        Updated DbtPackages instance

    Raises:
        PackageNotFoundError: If package not found
        ValueError: If package is not a hub package
    """
    index = find_package_index(packages, package_name)
    if index is None:
        msg = f"Package '{package_name}' not found"
        raise PackageNotFoundError(msg)

    pkg = packages.packages[index]
    if not isinstance(pkg, HubPackage):
        msg = f"Package '{package_name}' is not a hub package, cannot update version"
        raise ValueError(msg)

    pkg.version = new_version
    return packages


def get_package_display_info(packages: DbtPackages) -> list[tuple[str, str]]:
    """Get package information for display.

    Args:
        packages: DbtPackages instance

    Returns:
        List of (identifier, type_info) tuples for display
    """
    result: list[tuple[str, str]] = []
    for pkg in packages.packages:
        if isinstance(pkg, HubPackage):
            result.append((pkg.package, f"hub: {pkg.version}"))
        elif isinstance(pkg, GitPackage):
            info = f"git: {pkg.revision}"
            if pkg.subdirectory:
                info += f" ({pkg.subdirectory})"
            result.append((pkg.git, info))
        else:
            result.append((pkg.local, "local"))
    return result
