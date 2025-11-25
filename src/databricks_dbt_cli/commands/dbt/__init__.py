"""dbt CLI commands."""

import typer

from databricks_dbt_cli.commands.dbt.token import app as token_app

app: typer.Typer = typer.Typer(help="dbt-related commands")

app.add_typer(token_app, name="token", help="Manage Databricks tokens for dbt")
