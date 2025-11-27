"""Profile management service for dbt profiles.yml.

Handles loading templates, validating profiles, and writing to disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from brix.modules.dbt.profile_models import DbtProfiles
from brix.templates import get_template
from brix.utils.logging import get_logger

DEFAULT_PROFILE_PATH = Path.home() / ".dbt" / "profiles.yml"


class ProfileConfig(BaseSettings):
    """Profile configuration from environment variables.

    Environment variables:
        BRIX_DBT_PROFILE_PATH: Override default profile path
    """

    model_config = SettingsConfigDict(
        env_prefix="BRIX_DBT_",
        case_sensitive=False,
    )

    profile_path: Path | None = None


def get_default_profile_path() -> Path:
    """Get the default profile path, checking env var first.

    Returns:
        Path from BRIX_DBT_PROFILE_PATH env var, or ~/.dbt/profiles.yml
    """
    config = ProfileConfig()
    return config.profile_path or DEFAULT_PROFILE_PATH


def load_template(template_name: str = "profiles.yml") -> tuple[str, DbtProfiles]:
    """Load and validate the bundled profile template.

    Args:
        template_name: Name of the template file

    Returns:
        Tuple of (raw template content, validated DbtProfiles)

    Raises:
        FileNotFoundError: If template doesn't exist
        ValueError: If template is invalid YAML or doesn't match schema
    """
    logger = get_logger()
    logger.debug("Loading template: %s", template_name)

    content = get_template(template_name)
    profiles = DbtProfiles.from_yaml(content)

    logger.debug("Template validated successfully")
    return content, profiles


class ProfileExistsError(Exception):
    """Raised when profile already exists and force is not set."""


class ProfileInitResult:
    """Result of profile initialization."""

    def __init__(
        self,
        *,
        success: bool,
        path: Path,
        action: Literal["created", "overwritten", "skipped"],
        message: str,
    ) -> None:
        """Initialize profile init result.

        Args:
            success: Whether initialization succeeded
            path: Path to the profile file
            action: What action was taken (created, overwritten, skipped)
            message: Human-readable result message
        """
        self.success = success
        self.path = path
        self.action = action
        self.message = message


def init_profile(
    profile_path: Path | None = None,
    *,
    force: bool = False,
    template_name: str = "profiles.yml",
) -> ProfileInitResult:
    """Initialize a dbt profile from template.

    Args:
        profile_path: Target path for profiles.yml (uses default if None)
        force: Overwrite existing file if True
        template_name: Name of template to use

    Returns:
        ProfileInitResult with success status and details

    Raises:
        ProfileExistsError: If file exists and force is False
        FileNotFoundError: If template doesn't exist
        ValueError: If template validation fails
    """
    logger = get_logger()

    # Determine target path
    target_path = profile_path or get_default_profile_path()
    logger.debug("Target profile path: %s", target_path)

    # Check if file exists
    if target_path.exists() and not force:
        msg = f"Profile already exists at {target_path}. Use --force to overwrite."
        raise ProfileExistsError(msg)

    # Load and validate template
    content, _ = load_template(template_name)

    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine action for result
    action: Literal["created", "overwritten", "skipped"] = "overwritten" if target_path.exists() else "created"

    # Write profile
    target_path.write_text(content)
    logger.info("Profile %s at %s", action, target_path)

    return ProfileInitResult(
        success=True,
        path=target_path,
        action=action,
        message=f"Profile {action} at {target_path}",
    )
