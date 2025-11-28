"""dbt module - business logic for dbt operations."""

import subprocess
from pathlib import Path

from pydantic import BaseModel, ValidationError

from brix.utils.logging import get_logger

CACHE_DIR = Path.home() / ".cache" / "brix"
PROJECT_CACHE_FILE = CACHE_DIR / "dbt_project_path.json"


class DbtNotFoundError(Exception):
    """Raised when dbt executable cannot be found."""


class ProjectPathCache(BaseModel):
    """Cached project path for dbt passthrough."""

    project_path: Path


class CachedPathNotFoundError(FileNotFoundError):
    """Raised when cached project path no longer exists."""


def load_project_cache() -> Path | None:
    """Load cached project path.

    Returns:
        Cached project path if valid, None otherwise.

    Raises:
        CachedPathNotFoundError: If cached path no longer exists or is not a directory.
    """
    logger = get_logger()
    if not PROJECT_CACHE_FILE.exists():
        logger.debug("Project cache file not found: %s", PROJECT_CACHE_FILE)
        return None
    try:
        cache = ProjectPathCache.model_validate_json(PROJECT_CACHE_FILE.read_text())
    except (ValidationError, OSError) as e:
        logger.debug("Failed to load project cache: %s", e)
        return None

    # Check if cached path still exists (outside try/except to propagate error)
    if not cache.project_path.exists():
        logger.debug("Cached project path no longer exists: %s", cache.project_path)
        raise CachedPathNotFoundError(f"Cached project path no longer exists: {cache.project_path}")
    if not cache.project_path.is_dir():
        logger.debug("Cached project path is not a directory: %s", cache.project_path)
        raise CachedPathNotFoundError(f"Cached project path is not a directory: {cache.project_path}")

    logger.debug("Loaded project cache: %s", cache.project_path)
    return cache.project_path


def save_project_cache(project_path: Path) -> None:
    """Save project path to cache.

    Converts relative paths to absolute before saving.

    Args:
        project_path: The project path to cache.
    """
    logger = get_logger()
    absolute_path = project_path.resolve()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = ProjectPathCache(project_path=absolute_path)
    PROJECT_CACHE_FILE.write_text(cache.model_dump_json())
    logger.debug("Project cache saved: %s", absolute_path)


def find_dbt_executable() -> str:
    """Find the dbt executable path.

    This function handles two scenarios:
    1. brix is installed in the same venv as dbt - dbt should be directly available
    2. brix is installed as a global tool - need to discover project venv with dbt

    Returns:
        Path to the dbt executable.

    Raises:
        DbtNotFoundError: If dbt cannot be found.
    """
    # TODO: Implement venv discovery logic for when brix is installed globally
    # but dbt is in a project-specific venv. This could involve:
    # - Looking for .venv/ in current directory or parent directories
    # - Checking for pyproject.toml/requirements.txt to identify project root
    # - Activating the discovered venv or returning path to its dbt executable

    # For now, assume dbt is available in PATH (same venv scenario)
    return "dbt"


def pre_dbt_hook() -> None:
    """Hook for setup before running dbt. Placeholder for future logic."""
    # TODO: Placeholder for other stuff that has to happen before running dbt.
    pass


def run_dbt(args: list[str], project_path: Path | None = None) -> int:
    """Run dbt with the given arguments and return exit code.

    Args:
        args: List of arguments to pass to dbt.
        project_path: Optional directory to run dbt in.

    Returns:
        Exit code from the dbt process (1 if dbt not found or invalid project path).
    """
    logger = get_logger()

    pre_dbt_hook()

    # Validate project path if provided
    if project_path is not None:
        if not project_path.exists():
            logger.error("Project path does not exist: %s", project_path)
            return 1
        if not project_path.is_dir():
            logger.error("Project path is not a directory: %s", project_path)
            return 1

    try:
        dbt_path = find_dbt_executable()
    except DbtNotFoundError as e:
        logger.error(str(e))
        return 1

    cwd = project_path.resolve() if project_path else None
    logger.debug("Executing dbt command: %s %s (cwd=%s)", dbt_path, " ".join(args), cwd)
    try:
        # "unsafe" passthrough is intended, we trust the user to pass valid arguments. Its their local machine.
        result = subprocess.run([dbt_path, *args], cwd=cwd)  # noqa: S603
    except FileNotFoundError:
        logger.error(
            "dbt not found in PATH. Ensure dbt is installed and available.\n"
            "If using a virtual environment, make sure it's activated or install brix in the same environment as dbt."
        )
        return 1
    except OSError as e:
        logger.error("Failed to execute dbt: %s", e)
        return 1

    logger.debug("dbt exited with code: %d", result.returncode)

    return result.returncode
