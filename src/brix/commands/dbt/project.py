"""Project management commands for dbt."""

from pathlib import Path
from typing import Annotated, Literal

import typer

from brix.modules.dbt.project.models import HubPackage, ProjectNameError
from brix.modules.dbt.project.prompts import run_dbt_deps, run_interactive_init
from brix.modules.dbt.project.service import (
    ProjectExistsError,
    get_package_version,
    init_project,
)
from brix.utils.logging import get_logger

MaterializationType = Literal["view", "table", "ephemeral"]

# Known package mappings for short names
KNOWN_PACKAGES = {
    "dbt_utils": "dbt-labs/dbt_utils",
    "dbt-utils": "dbt-labs/dbt_utils",
    "elementary": "elementary-data/elementary",
    "codegen": "dbt-labs/codegen",
    "dbt_expectations": "calogica/dbt_expectations",
    "dbt-expectations": "calogica/dbt_expectations",
    "audit_helper": "dbt-labs/audit_helper",
    "audit-helper": "dbt-labs/audit_helper",
}

app = typer.Typer(
    help="Manage dbt projects.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _resolve_package_name(short_name: str) -> str:
    """Resolve short package name to full namespace/name format."""
    return KNOWN_PACKAGES.get(short_name, short_name)


def _build_package_list(packages: list[str] | None) -> list[HubPackage]:
    """Build package list with versions from dbt Hub."""
    pkg_names = ["dbt-labs/dbt_utils"]
    if packages:
        for pkg in packages:
            resolved = _resolve_package_name(pkg) if "/" not in pkg else pkg
            if resolved not in pkg_names:
                pkg_names.append(resolved)

    typer.echo("Fetching package versions...")
    pkg_list = []
    for pkg_name in pkg_names:
        version = get_package_version(pkg_name)
        pkg_list.append(HubPackage(package=pkg_name, version=version))
        typer.echo(f"  {pkg_name}: {version}")
    return pkg_list


def _run_cli_init(
    project_name: str,
    profile: str,
    base_dir: Path | None,
    team: str | None,
    packages: list[str] | None,
    no_packages: bool,
    materialization: MaterializationType | None,
    persist_docs: bool | None,
    with_example: bool | None,
    run_deps: bool | None,
    force: bool,
) -> None:
    """Run project initialization in CLI mode."""
    logger = get_logger()

    pkg_list = None if no_packages else _build_package_list(packages)

    try:
        result = init_project(
            project_name=project_name,
            profile_name=profile,
            base_dir=base_dir,
            team=team,
            packages=pkg_list,
            materialization=materialization,
            persist_docs=persist_docs or False,
            with_example=with_example if with_example is not None else False,
            force=force,
        )
        typer.echo(f"\n{result.message}")
        typer.echo("\nFiles created:")
        for f in result.files_created:
            typer.echo(f"  {f}")

        if run_deps is True:
            run_dbt_deps(result.project_path)
        elif run_deps is None and not no_packages:
            typer.echo(f"\nRun 'dbt deps' in {result.project_path} to install packages.")

        typer.echo("\nProject initialization complete!")

    except ProjectExistsError as e:
        logger.debug("Project exists error", exc_info=e)
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    except ProjectNameError as e:
        logger.debug("Project name error", exc_info=e)
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    except ValueError as e:
        logger.debug("Validation error", exc_info=e)
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def init(
    # Basic options
    project_name: Annotated[
        str | None,
        typer.Option(
            "--project-name",
            "-n",
            help="Name of the dbt project",
        ),
    ] = None,
    base_dir: Annotated[
        Path | None,
        typer.Option(
            "--base-dir",
            "-b",
            help="Base directory for project (default: current dir, env: BRIX_DBT_PROJECT_BASE_DIR)",
            envvar="BRIX_DBT_PROJECT_BASE_DIR",
        ),
    ] = None,
    team: Annotated[
        str | None,
        typer.Option(
            "--team",
            "-t",
            help="Team subdirectory (optional)",
        ),
    ] = None,
    # Profile options
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile name to use in dbt_project.yml",
        ),
    ] = None,
    profile_path: Annotated[
        Path | None,
        typer.Option(
            "--profile-path",
            help="Path to profiles.yml for validation",
            envvar="BRIX_DBT_PROFILE_PATH",
        ),
    ] = None,
    # Package options
    packages: Annotated[
        list[str] | None,
        typer.Option(
            "--packages",
            help="Additional packages to include (can specify multiple times)",
        ),
    ] = None,
    no_packages: Annotated[
        bool,
        typer.Option(
            "--no-packages",
            help="Skip package installation",
        ),
    ] = False,
    # Databricks-specific options
    materialization: Annotated[
        MaterializationType | None,
        typer.Option(
            "--materialization",
            help="Default materialization (view, table, ephemeral)",
        ),
    ] = None,
    persist_docs: Annotated[
        bool | None,
        typer.Option(
            "--persist-docs/--no-persist-docs",
            help="Enable persist_docs for Unity Catalog",
        ),
    ] = None,
    # Post-init options
    run_deps: Annotated[
        bool | None,
        typer.Option(
            "--run-deps/--no-run-deps",
            help="Run 'dbt deps' after project creation",
        ),
    ] = None,
    # Example model
    with_example: Annotated[
        bool | None,
        typer.Option(
            "--with-example/--no-example",
            help="Create example model",
        ),
    ] = None,
    # Other
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing project",
        ),
    ] = False,
) -> None:
    r"""Initialize a new dbt project with sensible defaults.

    Without --project-name, launches an interactive wizard.
    With --project-name, runs in CLI mode with all options via flags.

    Examples:
        brix dbt project init
        brix dbt project init -n my_project -p default
    """
    if project_name is None:
        run_interactive_init(profile_path)
        return

    if profile is None:
        typer.echo("--profile is required in CLI mode", err=True)
        raise typer.Exit(1)

    _run_cli_init(
        project_name=project_name,
        profile=profile,
        base_dir=base_dir,
        team=team,
        packages=packages,
        no_packages=no_packages,
        materialization=materialization,
        persist_docs=persist_docs,
        with_example=with_example,
        run_deps=run_deps,
        force=force,
    )
