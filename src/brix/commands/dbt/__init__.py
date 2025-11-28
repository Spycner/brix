"""dbt command - CLI interface for dbt operations."""

from pathlib import Path
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

from brix.commands.dbt.profile import app as profile_app
from brix.commands.dbt.project import app as project_app
from brix.modules.dbt import CachedPathNotFoundError, load_project_cache, run_dbt, save_project_cache


class DbtGroup(TyperGroup):
    """Custom Typer Group that passes unknown commands through to dbt."""

    # Return type matches Click's Command.resolve_command() signature
    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        """Override to catch unknown commands and pass them to dbt."""
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            # Unknown command - pass through to dbt
            return None, None, args

    def invoke(self, ctx: click.Context) -> None:
        """Override to handle passthrough when no command matched."""
        cmd_name = ctx.protected_args[0] if ctx.protected_args else None
        cmd = self.get_command(ctx, cmd_name) if cmd_name else None

        if cmd is None and ctx.protected_args:
            # No matching command - pass through to dbt
            # Extract --project option from context params (set by option parsing)
            project_param = ctx.params.get("project")
            project_path: Path | None = Path(project_param) if project_param else None

            # If project path provided, save to cache
            if project_path is not None:
                save_project_cache(project_path)
            else:
                # Try to load from cache
                try:
                    project_path = load_project_cache()
                except CachedPathNotFoundError as e:
                    typer.echo(f"Error: {e}", err=True)
                    typer.echo("Please specify a valid project path with --project", err=True)
                    ctx.exit(1)

            exit_code = run_dbt(ctx.protected_args + ctx.args, project_path=project_path)
            ctx.exit(exit_code)
        else:
            super().invoke(ctx)


app = typer.Typer(
    cls=DbtGroup,
    help="Run dbt commands.\n\nCommands not matching built-in commands will be passed through to dbt CLI.",
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True, "help_option_names": ["-h", "--help"]},
)
app.add_typer(profile_app, name="profile")
app.add_typer(project_app, name="project")


@app.callback()
def dbt_callback(
    ctx: typer.Context,
    project: Annotated[
        Path | None,
        typer.Option(
            "--project",
            "-p",
            help="Path to dbt project directory. Cached for subsequent commands.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Run dbt commands - custom commands or passthrough to dbt CLI."""
    # Store project path in context for use by DbtGroup.invoke()
    ctx.ensure_object(dict)
    ctx.obj["project_path"] = project

    # If no args at all, show help
    if ctx.invoked_subcommand is None and not ctx.args and not ctx.protected_args:
        typer.echo(ctx.get_help())
