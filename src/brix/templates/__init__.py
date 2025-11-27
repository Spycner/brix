"""Template loading utilities for brix.

Uses importlib.resources to load templates bundled with the package.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def get_template(name: str) -> str:
    """Load a template file from the templates directory.

    Args:
        name: Template filename (e.g., 'profiles.yml')

    Returns:
        Template content as a string

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    try:
        return resources.files("brix.templates").joinpath(name).read_text()
    except FileNotFoundError as e:
        msg = f"Template not found: {name}"
        raise FileNotFoundError(msg) from e


def get_template_path(name: str) -> Path:
    """Get the path to a template file.

    Note: This returns a path that may be inside a zip/wheel, so it should
    only be used for reading, not for external tool access.

    Args:
        name: Template filename

    Returns:
        Path to the template file
    """
    return Path(str(resources.files("brix.templates").joinpath(name)))
