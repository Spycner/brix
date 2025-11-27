"""dbt command - CLI interface for dbt operations."""

import click
import typer
from typer.core import TyperGroup

from brix.commands.dbt.profile import app as profile_app
from brix.commands.dbt.project import app as project_app
from brix.modules.dbt import run_dbt


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
            exit_code = run_dbt(ctx.protected_args + ctx.args)
            ctx.exit(exit_code)
        else:
            super().invoke(ctx)


app = typer.Typer(
    cls=DbtGroup,
    help="Run dbt commands.",
    invoke_without_command=True,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True, "help_option_names": ["-h", "--help"]},
)
app.add_typer(profile_app, name="profile")
app.add_typer(project_app, name="project")


@app.callback()
def dbt_callback(ctx: typer.Context) -> None:
    """Run dbt commands - custom commands or passthrough to dbt CLI."""
    # If no args at all, show help
    if ctx.invoked_subcommand is None and not ctx.args and not ctx.protected_args:
        typer.echo(ctx.get_help())


@app.command()
def setup() -> None:
    """Setup dbt project configuration (placeholder)."""
    typer.echo("dbt setup - not yet implemented")
