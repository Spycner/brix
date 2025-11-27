"""Profile management commands for dbt."""

from pathlib import Path
from typing import Annotated

import typer

from brix.modules.dbt.profile import ProfileExistsError, get_default_profile_path, init_profile

app = typer.Typer(
    help="Manage dbt profile configuration.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def init(
    profile_path: Annotated[
        Path | None,
        typer.Option(
            "--profile-path",
            "-p",
            help="Path to profiles.yml (default: ~/.dbt/profiles.yml, env: BRIX_DBT_PROFILE_PATH)",
            envvar="BRIX_DBT_PROFILE_PATH",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing profile if it exists",
        ),
    ] = False,
) -> None:
    """Initialize a dbt profile from template.

    Creates a profiles.yml file at the specified path (or default ~/.dbt/profiles.yml).
    The template includes a DuckDB configuration for local development.

    Use --force to overwrite an existing profile.
    """
    try:
        result = init_profile(profile_path=profile_path, force=force)
        typer.echo(result.message)
    except ProfileExistsError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    except FileNotFoundError as e:
        typer.echo(f"Template error: {e}", err=True)
        raise typer.Exit(1) from None
    except ValueError as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def show() -> None:
    """Show the current profile path configuration."""
    default_path = get_default_profile_path()
    exists = default_path.exists()

    typer.echo(f"Profile path: {default_path}")
    typer.echo(f"Exists: {exists}")

    if exists:
        typer.echo("\nContents:")
        typer.echo(default_path.read_text())
