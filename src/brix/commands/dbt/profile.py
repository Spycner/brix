"""Profile management commands for dbt."""

from pathlib import Path
from typing import Annotated, Literal

import typer

from brix.modules.dbt.profile import ProfileExistsError, get_default_profile_path, init_profile
from brix.modules.dbt.profile_editor import (
    OutputAlreadyExistsError,
    OutputNotFoundError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    add_output,
    add_profile,
    delete_output,
    delete_profile,
    load_profiles,
    save_profiles,
    update_output,
    update_profile_target,
)
from brix.modules.dbt.profile_models import DbtProfiles, DuckDbOutput
from brix.modules.dbt.profile_prompts import run_interactive_edit

ActionType = Literal[
    "add-profile",
    "edit-profile",
    "delete-profile",
    "add-output",
    "edit-output",
    "delete-output",
]

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


@app.command()
def edit(
    profile_path: Annotated[
        Path | None,
        typer.Option(
            "--profile-path",
            "-p",
            help="Path to profiles.yml (default: ~/.dbt/profiles.yml, env: BRIX_DBT_PROFILE_PATH)",
            envvar="BRIX_DBT_PROFILE_PATH",
        ),
    ] = None,
    action: Annotated[
        ActionType | None,
        typer.Option(
            "--action",
            "-a",
            help="Action: add-profile, edit-profile, delete-profile, add-output, edit-output, delete-output",
        ),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-P",
            help="Profile name",
        ),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Output name",
        ),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option(
            "--target",
            "-t",
            help="Default target name",
        ),
    ] = None,
    path_value: Annotated[
        str | None,
        typer.Option(
            "--path",
            help="DuckDB path",
        ),
    ] = None,
    threads: Annotated[
        int | None,
        typer.Option(
            "--threads",
            help="Thread count",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation for destructive actions",
        ),
    ] = False,
) -> None:
    """Edit dbt profile configuration.

    Without --action, launches interactive editor with menus.
    With --action, performs the specified action non-interactively.

    Examples:
        brix dbt profile edit  # Interactive mode

        brix dbt profile edit --action add-profile --profile myproj --target dev

        brix dbt profile edit --action edit-output --profile default --output dev --path ./new.duckdb

        brix dbt profile edit --action delete-profile --profile old --force
    """
    if action is None:
        run_interactive_edit(profile_path)
        return

    _run_cli_action(action, profile_path, profile, output, target, path_value, threads, force)


def _run_cli_action(
    action: ActionType,
    profile_path: Path | None,
    profile: str | None,
    output: str | None,
    target: str | None,
    path_value: str | None,
    threads: int | None,
    force: bool,
) -> None:
    """Run non-interactive CLI action."""
    target_path = profile_path or get_default_profile_path()

    try:
        profiles = load_profiles(target_path)
    except FileNotFoundError:
        profiles = DbtProfiles(root={})

    try:
        _dispatch_cli_action(action, profiles, target_path, profile, output, target, path_value, threads, force)
    except (ProfileNotFoundError, ProfileAlreadyExistsError, OutputNotFoundError, OutputAlreadyExistsError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    except ValueError as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(1) from None


def _dispatch_cli_action(
    action: ActionType,
    profiles: DbtProfiles,
    target_path: Path,
    profile: str | None,
    output: str | None,
    target: str | None,
    path_value: str | None,
    threads: int | None,
    force: bool,
) -> None:
    """Dispatch CLI action to appropriate handler."""
    if action == "add-profile":
        _handle_add_profile(profiles, target_path, profile, target, output, path_value, threads)
    elif action == "edit-profile":
        _handle_edit_profile(profiles, target_path, profile, target)
    elif action == "delete-profile":
        _handle_delete_profile_cli(profiles, target_path, profile, force)
    elif action == "add-output":
        _handle_add_output_cli(profiles, target_path, profile, output, path_value, threads)
    elif action == "edit-output":
        _handle_edit_output_cli(profiles, target_path, profile, output, path_value, threads)
    elif action == "delete-output":
        _handle_delete_output_cli(profiles, target_path, profile, output, force)


def _handle_add_profile(
    profiles: DbtProfiles,
    target_path: Path,
    profile_name: str | None,
    target_name: str | None,
    output_name: str | None,
    path_value: str | None,
    threads: int | None,
) -> None:
    """Handle add-profile action in CLI mode."""
    if not profile_name:
        typer.echo("--profile is required for add-profile", err=True)
        raise typer.Exit(1)

    target_name = target_name or "dev"
    output_name = output_name or target_name
    path_value = path_value or ":memory:"
    threads = threads or 1

    output_config = DuckDbOutput(type="duckdb", path=path_value, threads=threads)
    add_profile(profiles, profile_name, target_name, output_name, output_config)
    save_profiles(profiles, target_path)
    typer.echo(f"Added profile '{profile_name}'")


def _handle_edit_profile(
    profiles: DbtProfiles,
    target_path: Path,
    profile_name: str | None,
    target_name: str | None,
) -> None:
    """Handle edit-profile action in CLI mode."""
    if not profile_name:
        typer.echo("--profile is required for edit-profile", err=True)
        raise typer.Exit(1)

    if not target_name:
        typer.echo("--target is required for edit-profile", err=True)
        raise typer.Exit(1)

    update_profile_target(profiles, profile_name, target_name)
    save_profiles(profiles, target_path)
    typer.echo(f"Updated profile '{profile_name}' target to '{target_name}'")


def _handle_delete_profile_cli(
    profiles: DbtProfiles,
    target_path: Path,
    profile_name: str | None,
    force: bool,
) -> None:
    """Handle delete-profile action in CLI mode."""
    if not profile_name:
        typer.echo("--profile is required for delete-profile", err=True)
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete profile '{profile_name}'?", abort=True)

    delete_profile(profiles, profile_name)
    save_profiles(profiles, target_path)
    typer.echo(f"Deleted profile '{profile_name}'")


def _handle_add_output_cli(
    profiles: DbtProfiles,
    target_path: Path,
    profile_name: str | None,
    output_name: str | None,
    path_value: str | None,
    threads: int | None,
) -> None:
    """Handle add-output action in CLI mode."""
    if not profile_name:
        typer.echo("--profile is required for add-output", err=True)
        raise typer.Exit(1)

    if not output_name:
        typer.echo("--output is required for add-output", err=True)
        raise typer.Exit(1)

    path_value = path_value or ":memory:"
    threads = threads or 1

    output_config = DuckDbOutput(type="duckdb", path=path_value, threads=threads)
    add_output(profiles, profile_name, output_name, output_config)
    save_profiles(profiles, target_path)
    typer.echo(f"Added output '{output_name}' to profile '{profile_name}'")


def _handle_edit_output_cli(
    profiles: DbtProfiles,
    target_path: Path,
    profile_name: str | None,
    output_name: str | None,
    path_value: str | None,
    threads: int | None,
) -> None:
    """Handle edit-output action in CLI mode."""
    if not profile_name:
        typer.echo("--profile is required for edit-output", err=True)
        raise typer.Exit(1)

    if not output_name:
        typer.echo("--output is required for edit-output", err=True)
        raise typer.Exit(1)

    if path_value is None and threads is None:
        typer.echo("--path or --threads is required for edit-output", err=True)
        raise typer.Exit(1)

    update_output(profiles, profile_name, output_name, path=path_value, threads=threads)
    save_profiles(profiles, target_path)
    typer.echo(f"Updated output '{output_name}' in profile '{profile_name}'")


def _handle_delete_output_cli(
    profiles: DbtProfiles,
    target_path: Path,
    profile_name: str | None,
    output_name: str | None,
    force: bool,
) -> None:
    """Handle delete-output action in CLI mode."""
    if not profile_name:
        typer.echo("--profile is required for delete-output", err=True)
        raise typer.Exit(1)

    if not output_name:
        typer.echo("--output is required for delete-output", err=True)
        raise typer.Exit(1)

    if not force:
        typer.confirm(f"Delete output '{output_name}' from profile '{profile_name}'?", abort=True)

    delete_output(profiles, profile_name, output_name)
    save_profiles(profiles, target_path)
    typer.echo(f"Deleted output '{output_name}' from profile '{profile_name}'")
