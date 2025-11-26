"""Brix CLI - an exploration for Databricks."""

from pathlib import Path
from typing import Annotated

import typer

from brix import __version__
from brix.utils.logging import setup_logging
from brix.version_check import check_for_updates

app = typer.Typer(help="Brix CLI - an exploration for Databricks.")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"brix {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit."),
    ] = False,
    log_level: Annotated[
        str | None,
        typer.Option("--log-level", help="Log level: TRACE, DEBUG, INFO, WARN, ERROR, OFF", case_sensitive=False),
    ] = None,
    log_path: Annotated[
        Path | None,
        typer.Option("--log-path", help="File path for log output."),
    ] = None,
    log_json: Annotated[
        bool | None,
        typer.Option("--log-json/--no-log-json", help="Enable JSON log format."),
    ] = None,
) -> None:
    """Brix CLI entry point."""
    # Initialize logging (CLI args override env vars)
    setup_logging(level=log_level, log_path=log_path, json_format=log_json)

    # Check for updates (silent on failure)
    if latest := check_for_updates():
        typer.secho(
            f"Update available: {__version__} → {latest}\n"
            "  pip: pip install --upgrade brix\n"
            "  uv:  uv pip install --upgrade brix",
            fg=typer.colors.YELLOW,
            err=True,
        )

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
