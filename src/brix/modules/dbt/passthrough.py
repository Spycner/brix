"""dbt module - business logic for dbt operations."""

import subprocess

from brix.utils.logging import get_logger


def pre_dbt_hook() -> None:
    """Hook for setup before running dbt. Placeholder for future logic."""
    pass


def run_dbt(args: list[str]) -> int:
    """Run dbt with the given arguments and return exit code.

    Args:
        args: List of arguments to pass to dbt.

    Returns:
        Exit code from the dbt process.
    """
    logger = get_logger()

    pre_dbt_hook()

    logger.debug("Executing dbt command: dbt %s", " ".join(args))
    # "unsafe" passthrough is intended, we trust the user to pass valid arguments. Its their local machine.
    result = subprocess.run(["dbt", *args])  # noqa: S603, S607
    logger.debug("dbt exited with code: %d", result.returncode)

    return result.returncode
