"""databricks-dbt-cli main entry point."""

import typer

from databricks_dbt_cli.commands.dbt import app as dbt_app

app: typer.Typer = typer.Typer(help="CLI for managing Databricks resources with dbt")

app.add_typer(dbt_app, name="dbt", help="dbt-related commands")

if __name__ == "__main__":
    app()
