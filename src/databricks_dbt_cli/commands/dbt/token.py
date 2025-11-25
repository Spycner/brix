"""CLI commands for Databricks token management."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from databricks_dbt_cli.modules.auth import AuthMethod
from databricks_dbt_cli.modules.dbt import get_default_profiles_path, load_profile
from databricks_dbt_cli.modules.token import check_token, refresh_all_tokens, refresh_token
from databricks_dbt_cli.utils.exceptions import CliError

app: typer.Typer = typer.Typer(help="Manage Databricks tokens")


def _print_error(message: str) -> None:
    """Print an error message in red."""
    typer.echo(typer.style(f"Error: {message}", fg=typer.colors.RED), err=True)


def _print_success(message: str) -> None:
    """Print a success message in green."""
    typer.echo(typer.style(message, fg=typer.colors.GREEN))


def _print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    typer.echo(typer.style(message, fg=typer.colors.YELLOW))


def _print_info(message: str) -> None:
    """Print an info message."""
    typer.echo(message)


@app.command()
def refresh(
    environment: Annotated[
        str | None,
        typer.Option("--environment", "-e", help="Target environment to refresh (default: all)"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force refresh even if token is still valid"),
    ] = False,
    auth_method: Annotated[
        AuthMethod,
        typer.Option("--auth-method", "-a", help="Azure authentication method"),
    ] = AuthMethod.AUTO,
    profile_path: Annotated[
        Path | None,
        typer.Option("--profile-path", "-p", help="Path to profiles.yml"),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", "-n", help="dbt profile name"),
    ] = "DDBT",
    lifetime_hours: Annotated[
        int,
        typer.Option("--lifetime", "-l", min=1, max=24, help="Token lifetime in hours"),
    ] = 24,
) -> None:
    """Refresh Databricks token(s) for dbt.

    If no environment is specified, refreshes tokens for all environments in the profile.
    """
    try:
        path = profile_path or get_default_profiles_path()
        profile = load_profile(path, profile_name)

        if environment:
            result = asyncio.run(refresh_token(environment, profile, auth_method, force, lifetime_hours))
            if result.success:
                _print_success(f"[{environment}] {result.message}")
            else:
                _print_error(f"[{environment}] {result.message}")
                raise typer.Exit(1)
        else:
            results = asyncio.run(refresh_all_tokens(profile, None, auth_method, force, lifetime_hours))
            has_failures = False
            for result in results:
                if result.success:
                    _print_success(f"[{result.environment}] {result.message}")
                else:
                    _print_error(f"[{result.environment}] {result.message}")
                    has_failures = True

            if has_failures:
                raise typer.Exit(1)

    except CliError as e:
        _print_error(str(e))
        raise typer.Exit(1) from e


@app.command()
def check(
    environment: Annotated[
        str | None,
        typer.Option("--environment", "-e", help="Target environment to check (default: all)"),
    ] = None,
    profile_path: Annotated[
        Path | None,
        typer.Option("--profile-path", "-p", help="Path to profiles.yml"),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", "-n", help="dbt profile name"),
    ] = "DDBT",
) -> None:
    """Check the status of Databricks token(s).

    Shows whether tokens need refresh and their expiration status.
    """
    try:
        path = profile_path or get_default_profiles_path()
        profile = load_profile(path, profile_name)

        environments = [environment] if environment else list(profile.targets.keys())

        needs_refresh_count = 0
        for env in environments:
            result = check_token(env, profile)
            if result.needs_refresh:
                needs_refresh_count += 1
                _print_warning(f"[{env}] {result.message}")
                if result.token_variable:
                    _print_info(f"  Token variable: {result.token_variable}")
            else:
                _print_success(f"[{env}] {result.message}")
                if result.expires_at:
                    _print_info(f"  Expires: {result.expires_at.strftime('%Y-%m-%d %H:%M UTC')}")

        if needs_refresh_count > 0:
            _print_info(f"\n{needs_refresh_count} token(s) need refresh. Run 'ddbt dbt token refresh' to update.")

    except CliError as e:
        _print_error(str(e))
        raise typer.Exit(1) from e


@app.command()
def status(
    environment: Annotated[
        str | None,
        typer.Option("--environment", "-e", help="Target environment (default: all)"),
    ] = None,
    profile_path: Annotated[
        Path | None,
        typer.Option("--profile-path", "-p", help="Path to profiles.yml"),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", "-n", help="dbt profile name"),
    ] = "DDBT",
) -> None:
    """Show detailed status of Databricks token(s).

    Displays token configuration and expiration information.
    """
    try:
        path = profile_path or get_default_profiles_path()
        profile = load_profile(path, profile_name)

        environments = [environment] if environment else list(profile.targets.keys())

        _print_info(f"Profile: {profile.name}")
        _print_info(f"Profile path: {path}")
        _print_info("")

        for env in environments:
            target = profile.targets.get(env)
            if not target:
                _print_warning(f"[{env}] Not found in profile")
                continue

            _print_info(f"[{env}]")
            _print_info(f"  Host: {target.host}")
            _print_info(f"  Token variable: {target.token_env_var or '(not configured)'}")

            if target.token_env_var:
                result = check_token(env, profile)
                if result.needs_refresh:
                    _print_warning(f"  Status: {result.message}")
                else:
                    _print_success(f"  Status: {result.message}")
                if result.expires_at:
                    _print_info(f"  Expires: {result.expires_at.strftime('%Y-%m-%d %H:%M UTC')}")

            _print_info("")

    except CliError as e:
        _print_error(str(e))
        raise typer.Exit(1) from e
