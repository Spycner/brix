"""Brix CLI - an exploration for Databricks."""

from typing import Annotated

import typer

from brix import __version__
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
) -> None:
    """Brix CLI entry point."""
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
