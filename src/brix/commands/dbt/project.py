"""Project management commands for dbt."""

from pathlib import Path
from typing import Annotated, Literal

import typer

from brix.modules.dbt.project.models import HubPackage, PackageNameError, ProjectNameError, validate_hub_package_name
from brix.modules.dbt.project.prompts import run_dbt_deps, run_interactive_edit, run_interactive_init
from brix.modules.dbt.project.service import (
    ProjectExistsError,
    fetch_package_versions_parallel,
    get_package_version,
    init_project,
)
from brix.utils.logging import get_logger

MaterializationType = Literal["view", "table", "ephemeral"]

# Action types for CLI edit command
EditActionType = Literal[
    "set-name",
    "set-profile",
    "set-version",
    "set-require-dbt-version",
    "add-path",
    "remove-path",
    "add-hub-package",
    "add-git-package",
    "add-local-package",
    "remove-package",
    "update-package-version",
]

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
    """Resolve short package name to full namespace/name format.

    Args:
        short_name: Short or full package name

    Returns:
        Full package name in namespace/name format

    Raises:
        PackageNameError: If resolved name is not valid hub format
    """
    resolved = KNOWN_PACKAGES.get(short_name, short_name)
    validate_hub_package_name(resolved)
    return resolved


def _build_package_list(packages: list[str] | None) -> list[HubPackage]:
    """Build package list with versions from dbt Hub."""
    pkg_names = ["dbt-labs/dbt_utils"]
    if packages:
        for pkg in packages:
            resolved = _resolve_package_name(pkg) if "/" not in pkg else pkg
            validate_hub_package_name(resolved)
            if resolved not in pkg_names:
                pkg_names.append(resolved)

    typer.echo("Fetching package versions...")
    versions = fetch_package_versions_parallel(pkg_names)

    pkg_list = []
    for pkg_name in pkg_names:
        version = versions[pkg_name]
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

    try:
        pkg_list = None if no_packages else _build_package_list(packages)
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
    except PackageNameError as e:
        logger.debug("Package name error", exc_info=e)
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


def _cli_set_project_field(
    project_path: Path,
    field: str,
    value: str | None,
    required_msg: str,
    success_msg: str,
) -> None:
    """Handle CLI set-* actions for project fields."""
    from brix.modules.dbt.project.editor import (
        InvalidFieldError,
        ProjectNotFoundError,
        load_project,
        save_project,
        update_project_field,
    )

    if not value:
        typer.echo(required_msg, err=True)
        raise typer.Exit(1)

    try:
        project = load_project(project_path)
        project = update_project_field(project, field, value)
        save_project(project, project_path)
        typer.echo(success_msg.format(value=value))
    except (ProjectNotFoundError, InvalidFieldError, ProjectNameError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None


def _cli_set_require_dbt_version(project_path: Path, value: str | None) -> None:
    """Handle CLI set-require-dbt-version action."""
    from brix.modules.dbt.project.editor import (
        InvalidFieldError,
        ProjectNotFoundError,
        load_project,
        save_project,
        update_project_field,
    )

    try:
        project = load_project(project_path)
        project = update_project_field(project, "require_dbt_version", value or None)
        save_project(project, project_path)
        if value:
            typer.echo(f"Updated require-dbt-version to '{value}'")
        else:
            typer.echo("Cleared require-dbt-version")
    except (ProjectNotFoundError, InvalidFieldError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None


def _cli_path_action(
    project_path: Path,
    action: str,
    path_field: str | None,
    path_value: str | None,
    create_dir: bool | None,
) -> None:
    """Handle CLI add-path/remove-path actions."""
    from brix.modules.dbt.project.editor import (
        InvalidFieldError,
        ProjectNotFoundError,
        load_project,
        save_project,
        update_path_field,
    )

    if not path_field or not path_value:
        typer.echo(f"--path-field and --path are required for {action} action", err=True)
        raise typer.Exit(1)

    operation = "add" if action == "add-path" else "remove"
    try:
        project = load_project(project_path)
        project = update_path_field(project, path_field, operation, path_value)
        save_project(project, project_path)
        verb = "Added" if operation == "add" else "Removed"
        prep = "to" if operation == "add" else "from"
        typer.echo(f"{verb} '{path_value}' {prep} {path_field}")

        if operation == "add" and create_dir:
            full_path = project_path.parent / path_value
            if not full_path.exists():
                full_path.mkdir(parents=True, exist_ok=True)
                typer.echo(f"Created directory: {full_path}")
    except (ProjectNotFoundError, InvalidFieldError, ValueError) as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None


def _cli_package_action(  # noqa: C901
    project_path: Path,
    action: EditActionType,
    package: str | None,
    package_version: str | None,
    revision: str | None,
    subdirectory: str | None,
) -> None:
    """Handle CLI package actions."""
    from brix.modules.dbt.project.editor import (
        PackageAlreadyExistsError,
        PackageNotFoundError,
        add_git_package,
        add_hub_package,
        add_local_package,
        load_packages,
        remove_package,
        save_packages,
        update_package_version,
    )

    if action == "add-hub-package":
        if not package:
            typer.echo("--package is required for add-hub-package action", err=True)
            raise typer.Exit(1)
        try:
            resolved = _resolve_package_name(package) if "/" not in package else package
            validate_hub_package_name(resolved)
            ver = package_version or get_package_version(resolved)
            pkgs = load_packages(project_path)
            pkgs = add_hub_package(pkgs, resolved, ver)
            save_packages(pkgs, project_path)
            typer.echo(f"Added hub package: {resolved} ({ver})")
        except PackageNameError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None
        except PackageAlreadyExistsError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None

    elif action == "add-git-package":
        if not package or not revision:
            typer.echo("--package (git URL) and --revision required for add-git-package", err=True)
            raise typer.Exit(1)
        try:
            pkgs = load_packages(project_path)
            pkgs = add_git_package(pkgs, package, revision, subdirectory)
            save_packages(pkgs, project_path)
            typer.echo(f"Added git package: {package} ({revision})")
        except PackageAlreadyExistsError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None

    elif action == "add-local-package":
        if not package:
            typer.echo("--package (local path) is required for add-local-package action", err=True)
            raise typer.Exit(1)
        try:
            pkgs = load_packages(project_path)
            pkgs = add_local_package(pkgs, package)
            save_packages(pkgs, project_path)
            typer.echo(f"Added local package: {package}")
        except PackageAlreadyExistsError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None

    elif action == "remove-package":
        if not package:
            typer.echo("--package is required for remove-package action", err=True)
            raise typer.Exit(1)
        try:
            pkgs = load_packages(project_path)
            pkgs = remove_package(pkgs, package)
            save_packages(pkgs, project_path)
            typer.echo(f"Removed package: {package}")
        except PackageNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None

    elif action == "update-package-version":
        if not package or not package_version:
            typer.echo("--package and --package-version required for update-package-version", err=True)
            raise typer.Exit(1)
        try:
            pkgs = load_packages(project_path)
            pkgs = update_package_version(pkgs, package, package_version)
            save_packages(pkgs, project_path)
            typer.echo(f"Updated {package} to version {package_version}")
        except (PackageNotFoundError, ValueError) as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None


def _run_cli_edit_action(
    action: EditActionType,
    project_path: Path,
    name: str | None,
    profile_name: str | None,
    version: str | None,
    require_dbt_version: str | None,
    path_field: str | None,
    path_value: str | None,
    create_dir: bool | None,
    package: str | None,
    package_version: str | None,
    revision: str | None,
    subdirectory: str | None,
    force: bool,
) -> None:
    """Execute a CLI edit action."""
    logger = get_logger()

    if action == "set-name":
        _cli_set_project_field(
            project_path,
            "name",
            name,
            "--name is required for set-name action",
            "Updated project name to '{value}'",
        )
    elif action == "set-profile":
        _cli_set_project_field(
            project_path,
            "profile",
            profile_name,
            "--profile is required for set-profile action",
            "Updated profile to '{value}'",
        )
    elif action == "set-version":
        _cli_set_project_field(
            project_path,
            "version",
            version,
            "--version is required for set-version action",
            "Updated version to '{value}'",
        )
    elif action == "set-require-dbt-version":
        _cli_set_require_dbt_version(project_path, require_dbt_version)
    elif action in ("add-path", "remove-path"):
        _cli_path_action(project_path, action, path_field, path_value, create_dir)
    else:
        _cli_package_action(project_path, action, package, package_version, revision, subdirectory)

    logger.debug("Completed action: %s", action)


@app.command()
def edit(
    # Project selection
    project_path: Annotated[
        Path | None,
        typer.Option(
            "--project",
            "-p",
            help="Path to dbt_project.yml (interactive selection if not provided)",
        ),
    ] = None,
    # Action specification
    action: Annotated[
        EditActionType | None,
        typer.Option(
            "--action",
            "-a",
            help="Action to perform (interactive if not provided)",
        ),
    ] = None,
    # Project settings
    name: Annotated[
        str | None,
        typer.Option("--name", help="New project name (for set-name action)"),
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option("--profile", help="New profile name (for set-profile action)"),
    ] = None,
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="New project version (for set-version action)"),
    ] = None,
    require_dbt_version: Annotated[
        str | None,
        typer.Option("--require-dbt-version", help="dbt version constraint"),
    ] = None,
    # Path field operations
    path_field: Annotated[
        str | None,
        typer.Option(
            "--path-field",
            help="Path field to modify (model-paths, seed-paths, etc.)",
        ),
    ] = None,
    path_value: Annotated[
        str | None,
        typer.Option("--path", help="Path value to add/remove"),
    ] = None,
    create_dir: Annotated[
        bool | None,
        typer.Option(
            "--create-dir/--no-create-dir",
            help="Create directory when adding path",
        ),
    ] = None,
    # Package operations
    package: Annotated[
        str | None,
        typer.Option("--package", help="Package name (hub: org/name, git: URL, local: path)"),
    ] = None,
    package_version: Annotated[
        str | None,
        typer.Option("--package-version", help="Package version specifier"),
    ] = None,
    revision: Annotated[
        str | None,
        typer.Option("--revision", help="Git revision (branch, tag, commit)"),
    ] = None,
    subdirectory: Annotated[
        str | None,
        typer.Option("--subdirectory", help="Subdirectory within git repo"),
    ] = None,
    # Flags
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmations"),
    ] = False,
) -> None:
    r"""Edit dbt project configuration.

    Without --action, launches interactive editor with project discovery.
    With --action, performs the specified action non-interactively.

    Examples:
        # Interactive mode with project discovery
        brix dbt project edit

        # Interactive mode for specific project
        brix dbt project edit -p ./my_project/dbt_project.yml

        # CLI: Update project name
        brix dbt project edit -p ./proj/dbt_project.yml --action set-name --name new_name

        # CLI: Add hub package
        brix dbt project edit -p ./proj/dbt_project.yml --action add-hub-package \
            --package dbt-labs/dbt_utils --package-version ">=1.0.0"

        # CLI: Add path with directory creation
        brix dbt project edit -p ./proj/dbt_project.yml --action add-path \
            --path-field model-paths --path staging --create-dir

        # CLI: Remove a package
        brix dbt project edit -p ./proj/dbt_project.yml --action remove-package \
            --package dbt-labs/dbt_utils
    """
    if action is None:
        # Interactive mode
        run_interactive_edit(project_path)
        return

    # CLI mode - project_path is required
    if project_path is None:
        typer.echo("--project is required in CLI mode", err=True)
        raise typer.Exit(1)

    if not project_path.exists():
        typer.echo(f"Project file not found: {project_path}", err=True)
        raise typer.Exit(1)

    _run_cli_edit_action(
        action=action,
        project_path=project_path,
        name=name,
        profile_name=profile_name,
        version=version,
        require_dbt_version=require_dbt_version,
        path_field=path_field,
        path_value=path_value,
        create_dir=create_dir,
        package=package,
        package_version=package_version,
        revision=revision,
        subdirectory=subdirectory,
        force=force,
    )
