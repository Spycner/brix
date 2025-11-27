"""Project discovery service for dbt projects.

Provides functions to find dbt_project.yml files in a directory tree
with interactive fuzzy selection support.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import questionary

from brix.modules.dbt.project.models import DbtProject
from brix.utils.logging import get_logger

# Directories to exclude from search
EXCLUDE_DIRS = frozenset(
    {
        ".venv",
        "venv",
        ".env",
        "node_modules",
        "dbt_packages",
        "target",
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


def get_search_root() -> Path:
    """Get the search root directory.

    Returns git repository root if in a git repo, otherwise current working directory.

    Returns:
        Path to search root directory
    """
    logger = get_logger()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
        logger.debug("Using git root as search root: %s", git_root)
        return git_root
    except (subprocess.CalledProcessError, FileNotFoundError):
        cwd = Path.cwd()
        logger.debug("Not in git repo, using cwd as search root: %s", cwd)
        return cwd


def _should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from search.

    Args:
        path: Path to check

    Returns:
        True if path should be excluded
    """
    return any(part in EXCLUDE_DIRS for part in path.parts)


def find_dbt_projects(
    root: Path | None = None,
    max_depth: int = 10,
) -> list[Path]:
    """Find all dbt_project.yml files under root directory.

    Args:
        root: Search root (uses get_search_root() if None)
        max_depth: Maximum directory depth to search (default 10)

    Returns:
        List of absolute paths to dbt_project.yml files, sorted by path
    """
    logger = get_logger()
    search_root = root or get_search_root()

    if not search_root.exists():
        logger.warning("Search root does not exist: %s", search_root)
        return []

    projects: list[Path] = []

    # Use glob to find all dbt_project.yml files
    for project_file in search_root.glob("**/dbt_project.yml"):
        # Check depth
        try:
            relative = project_file.relative_to(search_root)
            depth = len(relative.parts) - 1  # Subtract 1 for the filename itself
            if depth > max_depth:
                continue
        except ValueError:
            continue

        # Check exclusions
        if _should_exclude(project_file):
            logger.debug("Excluding project in excluded directory: %s", project_file)
            continue

        projects.append(project_file.resolve())
        logger.debug("Found dbt project: %s", project_file)

    # Sort by path for consistent ordering
    projects.sort()
    logger.debug("Found %d dbt projects", len(projects))

    return projects


def _format_project_choice(project_path: Path, search_root: Path) -> str:
    """Format a project path for display in selection menu.

    Args:
        project_path: Absolute path to dbt_project.yml
        search_root: Root directory for relative path calculation

    Returns:
        Formatted string for display
    """
    try:
        # Get the project directory (parent of dbt_project.yml)
        project_dir = project_path.parent
        relative = project_dir.relative_to(search_root)
        return str(relative) if str(relative) != "." else project_dir.name
    except ValueError:
        return str(project_path.parent)


def prompt_select_project(
    projects: list[Path],
    search_root: Path | None = None,
) -> Path | None:
    """Interactive project selection with fuzzy autocomplete.

    Args:
        projects: List of dbt_project.yml paths
        search_root: Root directory for relative path display (uses get_search_root() if None)

    Returns:
        Selected project path, or None if cancelled
    """
    if not projects:
        return None

    root = search_root or get_search_root()

    # Build choice mapping: display string -> actual path
    choices: dict[str, Path] = {}
    for project_path in projects:
        display = _format_project_choice(project_path, root)
        # Handle duplicate display names by appending parent info
        if display in choices:
            display = str(project_path.parent)
        choices[display] = project_path

    # Use autocomplete for fuzzy search if many projects, otherwise select
    if len(choices) > 5:
        selected = questionary.autocomplete(
            "Select project (type to filter):",
            choices=list(choices.keys()),
            match_middle=True,
        ).ask()
    else:
        selected = questionary.select(
            "Select project:",
            choices=list(choices.keys()),
        ).ask()

    if selected is None:
        return None

    return choices.get(selected)


def discover_and_select_project(
    root: Path | None = None,
    max_depth: int = 10,
) -> tuple[Path, DbtProject] | None:
    """Combined discovery and selection flow.

    Finds dbt projects in the directory tree, prompts user to select one,
    and loads the selected project.

    Args:
        root: Search root (uses get_search_root() if None)
        max_depth: Maximum directory depth to search

    Returns:
        Tuple of (project_path, loaded DbtProject) or None if cancelled/not found
    """
    import typer

    search_root = root or get_search_root()
    projects = find_dbt_projects(search_root, max_depth)

    if not projects:
        typer.echo(f"No dbt projects found under {search_root}", err=True)
        return None

    if len(projects) == 1:
        # Only one project found, use it directly
        project_path = projects[0]
        typer.echo(f"Found project: {project_path.parent}")
    else:
        typer.echo(f"Found {len(projects)} dbt projects")
        project_path = prompt_select_project(projects, search_root)
        if project_path is None:
            return None

    # Load the project
    try:
        project = DbtProject.from_file(project_path)
        return (project_path, project)
    except Exception as e:
        typer.echo(f"Error loading project: {e}", err=True)
        return None
