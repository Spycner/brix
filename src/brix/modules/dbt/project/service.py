"""Project management service for dbt projects.

Handles project initialization, path resolution, and package version fetching.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from brix.modules.dbt.project.models import (
    DbtPackages,
    DbtProject,
    HubPackage,
    validate_project_name,
)
from brix.templates import get_template
from brix.utils.logging import get_logger

# Default fallback versions if API fetch fails
DEFAULT_PACKAGE_VERSIONS: dict[str, str] = {
    "dbt-labs/dbt_utils": ">=1.0.0",
    "elementary-data/elementary": ">=0.13.0",
    "dbt-labs/codegen": ">=0.12.0",
    "calogica/dbt_expectations": ">=0.10.0",
    "dbt-labs/audit_helper": ">=0.9.0",
}

# Popular packages to offer in the wizard
POPULAR_PACKAGES: list[tuple[str, str]] = [
    ("dbt-labs/dbt_utils", "Common utility macros and tests"),
    ("elementary-data/elementary", "Data observability and quality monitoring"),
    ("dbt-labs/codegen", "Code generation helpers"),
    ("calogica/dbt_expectations", "Great Expectations-style tests"),
    ("dbt-labs/audit_helper", "Data auditing utilities"),
]


class ProjectConfig(BaseSettings):
    """Project configuration from environment variables.

    Environment variables:
        BRIX_DBT_PROJECT_BASE_DIR: Default base directory for projects
    """

    model_config = SettingsConfigDict(
        env_prefix="BRIX_DBT_PROJECT_",
        case_sensitive=False,
    )

    base_dir: Path | None = None


class ProjectExistsError(Exception):
    """Raised when project already exists and force is not set."""


@dataclass
class ProjectInitResult:
    """Result of project initialization."""

    success: bool
    project_path: Path
    action: Literal["created", "overwritten", "skipped"]
    message: str
    files_created: list[str] = field(default_factory=list)


def resolve_project_path(
    project_name: str,
    base_dir: Path | None = None,
    team: str | None = None,
) -> Path:
    """Resolve the final project path from components.

    Args:
        project_name: Name of the project (becomes directory name)
        base_dir: Base directory (uses env var or cwd if None)
        team: Optional team subdirectory

    Returns:
        Resolved absolute path to project directory

    Example:
        >>> resolve_project_path("my_project")
        PosixPath('/current/dir/my_project')
        >>> resolve_project_path("my_project", Path("assets/dbt_projects"), "analytics")
        PosixPath('/current/dir/assets/dbt_projects/analytics/my_project')
    """
    config = ProjectConfig()
    effective_base = base_dir or config.base_dir or Path.cwd()

    # Make path absolute if relative
    if not effective_base.is_absolute():
        effective_base = Path.cwd() / effective_base

    if team:
        return effective_base / team / project_name
    return effective_base / project_name


def fetch_package_version(package: str) -> str | None:
    """Fetch the latest version of a package from dbt Hub.

    Args:
        package: Package name (e.g., "dbt-labs/dbt_utils")

    Returns:
        Version string (e.g., ">=1.3.0") or None if fetch fails
    """
    logger = get_logger()

    try:
        namespace, name = package.split("/")
        url = f"https://hub.getdbt.com/api/v1/{namespace}/{name}/latest.json"

        logger.debug("Fetching package version from: %s", url)

        # Simple HTTP GET with timeout
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
            import json

            data = json.loads(response.read().decode())
            version = data.get("version")
            if version:
                logger.debug("Found version %s for %s", version, package)
                return f">={version}"
    except Exception as e:
        logger.debug("Failed to fetch version for %s: %s", package, e)

    return None


def get_package_version(package: str) -> str:
    """Get the version for a package, with fallback to defaults.

    Args:
        package: Package name (e.g., "dbt-labs/dbt_utils")

    Returns:
        Version string (e.g., ">=1.0.0")
    """
    # Try to fetch from API
    version = fetch_package_version(package)
    if version:
        return version

    # Fall back to defaults
    return DEFAULT_PACKAGE_VERSIONS.get(package, ">=0.1.0")


def create_project_structure(
    project_path: Path,
    project_name: str,
    profile_name: str,
    *,
    packages: list[HubPackage] | None = None,
    materialization: str | None = None,
    persist_docs: bool = False,
    with_example: bool = False,
) -> list[str]:
    """Create the dbt project directory structure and files.

    Args:
        project_path: Path to create project in
        project_name: Name of the project
        profile_name: Name of the profile to use
        packages: List of packages to include (uses template default if None)
        materialization: Default materialization (view, table, ephemeral)
        persist_docs: Whether to enable persist_docs for Databricks
        with_example: Whether to create example model

    Returns:
        List of created file paths (relative to project_path)
    """
    logger = get_logger()
    created_files: list[str] = []

    # Create main directories
    directories = ["models", "seeds", "tests", "macros", "snapshots", "analyses"]
    for dir_name in directories:
        dir_path = project_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        # Add .gitkeep to empty directories
        gitkeep = dir_path / ".gitkeep"
        gitkeep.touch()
        created_files.append(f"{dir_name}/.gitkeep")
        logger.debug("Created directory: %s", dir_path)

    # Build dbt_project.yml content
    project_config: dict = {
        "name": project_name,
        "version": "1.0.0",
        "profile": profile_name,
        "config-version": 2,
        "model-paths": ["models"],
        "analysis-paths": ["analyses"],
        "test-paths": ["tests"],
        "seed-paths": ["seeds"],
        "macro-paths": ["macros"],
        "snapshot-paths": ["snapshots"],
        "clean-targets": ["target", "dbt_packages"],
    }

    # Add models config if needed (materialization or persist_docs)
    if materialization or persist_docs:
        models_config: dict = {}
        if materialization and materialization != "view":
            models_config["+materialized"] = materialization
        if persist_docs:
            models_config["+persist_docs"] = {"relation": True, "columns": True}
        if models_config:
            project_config["models"] = {project_name: models_config}

    # Create dbt_project.yml
    project = DbtProject(**project_config)
    project_yml_path = project_path / "dbt_project.yml"
    project_yml_path.write_text(project.to_yaml())
    created_files.append("dbt_project.yml")
    logger.debug("Created: %s", project_yml_path)

    # Create packages.yml
    if packages:
        dbt_packages = DbtPackages(packages=list(packages))
        packages_content = dbt_packages.to_yaml()
    else:
        # Use template with examples
        packages_content = get_template("packages.yml")

    packages_yml_path = project_path / "packages.yml"
    packages_yml_path.write_text(packages_content)
    created_files.append("packages.yml")
    logger.debug("Created: %s", packages_yml_path)

    # Create .gitignore
    gitignore_content = get_template("dbt_gitignore")
    gitignore_path = project_path / ".gitignore"
    gitignore_path.write_text(gitignore_content)
    created_files.append(".gitignore")
    logger.debug("Created: %s", gitignore_path)

    # Create example model if requested
    if with_example:
        example_dir = project_path / "models" / "example"
        example_dir.mkdir(parents=True, exist_ok=True)

        # Create example model SQL
        model_content = get_template("example_model.sql")
        model_path = example_dir / "my_first_model.sql"
        model_path.write_text(model_content)
        created_files.append("models/example/my_first_model.sql")
        logger.debug("Created: %s", model_path)

        # Create example schema YAML
        schema_content = get_template("example_schema.yml")
        schema_path = example_dir / "schema.yml"
        schema_path.write_text(schema_content)
        created_files.append("models/example/schema.yml")
        logger.debug("Created: %s", schema_path)

    return created_files


def init_project(
    project_name: str,
    profile_name: str,
    base_dir: Path | None = None,
    team: str | None = None,
    *,
    packages: list[HubPackage] | None = None,
    materialization: str | None = None,
    persist_docs: bool = False,
    with_example: bool = False,
    force: bool = False,
) -> ProjectInitResult:
    """Initialize a new dbt project.

    Args:
        project_name: Name of the project
        profile_name: Name of the profile to use
        base_dir: Base directory for project (uses env var or cwd if None)
        team: Optional team subdirectory
        packages: List of packages to include
        materialization: Default materialization (view, table, ephemeral)
        persist_docs: Whether to enable persist_docs for Databricks
        with_example: Whether to create example model
        force: Overwrite existing project if True

    Returns:
        ProjectInitResult with success status and details

    Raises:
        ProjectExistsError: If project exists and force is False
        ProjectNameError: If project name is invalid
    """
    logger = get_logger()

    # Validate project name
    validate_project_name(project_name)

    # Resolve project path
    project_path = resolve_project_path(project_name, base_dir, team)
    logger.debug("Project path: %s", project_path)

    # Check if project exists
    dbt_project_yml = project_path / "dbt_project.yml"
    if dbt_project_yml.exists() and not force:
        msg = f"Project already exists at {project_path}. Use --force to overwrite."
        raise ProjectExistsError(msg)

    # Determine action
    action: Literal["created", "overwritten", "skipped"] = "overwritten" if dbt_project_yml.exists() else "created"

    # Create project directory if needed
    project_path.mkdir(parents=True, exist_ok=True)

    # Create project structure
    files_created = create_project_structure(
        project_path=project_path,
        project_name=project_name,
        profile_name=profile_name,
        packages=packages,
        materialization=materialization,
        persist_docs=persist_docs,
        with_example=with_example,
    )

    logger.info("Project %s at %s", action, project_path)

    return ProjectInitResult(
        success=True,
        project_path=project_path,
        action=action,
        message=f"Project {action} at {project_path}",
        files_created=files_created,
    )
