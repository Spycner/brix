"""Interactive prompts for dbt project initialization using questionary.

Provides a wizard-style flow for creating new dbt projects with
profile selection, package configuration, and Databricks-specific options.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

import questionary
import typer

from brix.modules.dbt.profile.models import DatabricksOutput, DbtProfiles
from brix.modules.dbt.profile.service import get_default_profile_path
from brix.modules.dbt.project.models import HubPackage, ProjectNameError, validate_project_name
from brix.modules.dbt.project.service import (
    POPULAR_PACKAGES,
    ProjectConfig,
    ProjectExistsError,
    get_package_version,
    init_project,
    resolve_project_path,
)

# Materialization types
MaterializationType = Literal["view", "table", "ephemeral"]


def prompt_project_name() -> str | None:
    """Prompt user for project name with validation.

    Returns:
        Valid project name, or None if cancelled
    """
    while True:
        name = questionary.text(
            "Project name:",
            instruction="Must start with letter/underscore, alphanumeric only",
        ).ask()

        if name is None:
            return None

        name = name.strip()
        if not name:
            typer.echo("Project name cannot be empty.", err=True)
            continue

        try:
            validate_project_name(name)
            return name
        except ProjectNameError as e:
            typer.echo(str(e), err=True)


def prompt_base_dir() -> Path | None:
    """Prompt user for base directory.

    Returns:
        Base directory path, or None for current directory
    """
    config = ProjectConfig()
    default = str(config.base_dir) if config.base_dir else "."

    env_hint = ""
    if config.base_dir:
        env_hint = " (from BRIX_DBT_PROJECT_BASE_DIR)"

    path_str = questionary.text(
        f"Base directory{env_hint}:",
        default=default,
        instruction="Press Enter for current directory",
    ).ask()

    if path_str is None:
        return None

    path_str = path_str.strip()
    if not path_str or path_str == ".":
        return None

    return Path(path_str)


def prompt_team() -> str | None:
    """Prompt user for optional team subdirectory.

    Returns:
        Team name, or None if skipped
    """
    team = questionary.text(
        "Team (optional):",
        instruction="Press Enter to skip",
    ).ask()

    if team is None or not team.strip():
        return None

    return team.strip()


def prompt_profile_path() -> Path | None:
    """Prompt user for profiles.yml location.

    Returns:
        Path to profiles.yml, or None for default
    """
    default_path = get_default_profile_path()

    path_str = questionary.text(
        "profiles.yml location:",
        default=str(default_path),
        instruction="Press Enter for default location",
    ).ask()

    if path_str is None:
        return None

    path_str = path_str.strip()
    return Path(path_str) if path_str else default_path


def prompt_select_profile(profiles: DbtProfiles) -> str | None:
    """Prompt user to select a profile from existing profiles.

    Args:
        profiles: Loaded profiles

    Returns:
        Selected profile name, or None if cancelled
    """
    profile_names = list(profiles.root.keys())
    if not profile_names:
        typer.echo("No profiles found.", err=True)
        return None

    choices = [questionary.Choice(name, value=name) for name in profile_names]
    return questionary.select("Select profile:", choices=choices).ask()


def prompt_profile_action() -> Literal["use_existing", "create_new"] | None:
    """Prompt user to use existing profile or create new.

    Returns:
        Action choice, or None if cancelled
    """
    choices = [
        questionary.Choice("Use existing profile", value="use_existing"),
        questionary.Choice("Create new profile", value="create_new"),
    ]
    return questionary.select("Profile configuration:", choices=choices).ask()


def prompt_profile_not_found_action() -> Literal["enter_path", "create", "skip"] | None:
    """Prompt user when profiles.yml not found.

    Returns:
        Action choice, or None if cancelled
    """
    choices = [
        questionary.Choice("Enter path to existing profiles.yml", value="enter_path"),
        questionary.Choice("Create new profiles.yml", value="create"),
        questionary.Choice("Skip profile setup (configure manually)", value="skip"),
    ]
    return questionary.select(
        "No profiles.yml found at default location. What would you like to do?",
        choices=choices,
    ).ask()


def prompt_materialization() -> MaterializationType | None:
    """Prompt user for default materialization.

    Returns:
        Materialization type, or None if cancelled
    """
    choices = [
        questionary.Choice(
            "view (default) - No data stored, SQL query only. Cheaper and faster.",
            value="view",
        ),
        questionary.Choice(
            "table - Data stored physically. Better for frequently-queried models.",
            value="table",
        ),
        questionary.Choice(
            "ephemeral - Inlined as CTE. For intermediate transformations.",
            value="ephemeral",
        ),
    ]
    return questionary.select("Default materialization for models:", choices=choices).ask()


def prompt_persist_docs() -> bool:
    """Prompt user whether to enable persist_docs for Unity Catalog.

    Returns:
        True if enabled, False otherwise
    """
    return (
        questionary.confirm(
            "Enable Unity Catalog documentation sync? (persist_docs)",
            default=False,
            instruction="Pushes model/column descriptions to Unity Catalog Explorer",
        ).ask()
        or False
    )


def prompt_select_packages() -> list[str]:
    """Prompt user to select additional packages.

    Returns:
        List of selected package names (e.g., ["dbt-labs/dbt_utils"])
    """
    typer.echo("\n[Package Selection]")
    typer.echo("dbt_utils is always included. Select additional packages:\n")

    # Build choices - dbt_utils is always selected
    choices = []
    for package, description in POPULAR_PACKAGES:
        if package == "dbt-labs/dbt_utils":
            # dbt_utils is pre-selected and disabled
            choices.append(
                questionary.Choice(
                    f"{package} - {description}",
                    value=package,
                    checked=True,
                    disabled="(always included)",
                )
            )
        else:
            choices.append(
                questionary.Choice(
                    f"{package} - {description}",
                    value=package,
                    checked=False,
                )
            )

    selected = questionary.checkbox(
        "Select packages:",
        choices=choices,
    ).ask()

    if selected is None:
        return ["dbt-labs/dbt_utils"]

    # Ensure dbt_utils is always included
    if "dbt-labs/dbt_utils" not in selected:
        selected = ["dbt-labs/dbt_utils", *selected]

    return selected


def prompt_with_example() -> bool:
    """Prompt user whether to create example model.

    Returns:
        True if example should be created
    """
    return (
        questionary.confirm(
            "Create example model to help you get started?",
            default=True,
        ).ask()
        or False
    )


def prompt_run_deps(project_path: Path) -> bool:
    """Prompt user whether to run dbt deps after project creation.

    Args:
        project_path: Path to the created project

    Returns:
        True if dbt deps should be run
    """
    return (
        questionary.confirm(
            "Run 'dbt deps' to install packages now?",
            default=True,
        ).ask()
        or False
    )


def prompt_confirm_creation(
    project_name: str,
    project_path: Path,
    profile_name: str,
    packages: list[str],
    materialization: str | None,
    persist_docs: bool,
    with_example: bool,
) -> bool:
    """Show summary and confirm project creation.

    Returns:
        True if user confirms
    """
    typer.echo("\n" + "=" * 50)
    typer.echo("Project Summary")
    typer.echo("=" * 50)
    typer.echo(f"  Name:           {project_name}")
    typer.echo(f"  Path:           {project_path}")
    typer.echo(f"  Profile:        {profile_name}")
    typer.echo(f"  Packages:       {', '.join(packages)}")
    if materialization:
        typer.echo(f"  Materialization: {materialization}")
    if persist_docs:
        typer.echo("  persist_docs:   enabled")
    if with_example:
        typer.echo("  Example model:  yes")
    typer.echo("=" * 50 + "\n")

    return (
        questionary.confirm(
            "Create project with these settings?",
            default=True,
        ).ask()
        or False
    )


def _detect_profile_type(profiles: DbtProfiles, profile_name: str) -> str | None:
    """Detect the adapter type for a profile.

    Args:
        profiles: Loaded profiles
        profile_name: Name of the profile

    Returns:
        Adapter type ("databricks", "duckdb", etc.) or None
    """
    if profile_name not in profiles.root:
        return None

    profile = profiles.root[profile_name]
    target_name = profile.target
    if target_name not in profile.outputs:
        return None

    output = profile.outputs[target_name]
    if isinstance(output, DatabricksOutput):
        return "databricks"
    return getattr(output, "type", None)


def run_dbt_deps(project_path: Path) -> bool:
    """Run dbt deps in the project directory.

    Args:
        project_path: Path to the project

    Returns:
        True if successful
    """
    typer.echo("\nRunning 'dbt deps'...")
    try:
        # S607: Using partial path intentionally to use user's dbt installation
        result = subprocess.run(
            ["dbt", "deps"],  # noqa: S607
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            typer.echo(result.stdout)
            typer.echo("Packages installed successfully!")
            return True
        typer.echo(result.stderr, err=True)
        typer.echo("Failed to install packages. Run 'dbt deps' manually.", err=True)
        return False
    except FileNotFoundError:
        typer.echo("dbt command not found. Install dbt and run 'dbt deps' manually.", err=True)
        return False


def _handle_existing_profiles(profiles: DbtProfiles) -> str | None:
    """Handle profile selection when profiles.yml exists with profiles."""
    action = prompt_profile_action()
    if action is None:
        return None
    if action == "use_existing":
        return prompt_select_profile(profiles)
    typer.echo("\nUse 'brix dbt profile edit' to create a new profile first.")
    typer.echo("Then run this wizard again.")
    return None


def _handle_no_profiles(project_name: str) -> tuple[DbtProfiles | None, str | None]:
    """Handle profile setup when no profiles.yml found."""
    action = prompt_profile_not_found_action()
    if action is None:
        return None, None

    if action == "enter_path":
        custom_path = prompt_profile_path()
        if custom_path and custom_path.exists():
            try:
                profiles = DbtProfiles.from_file(custom_path)
                if profiles and profiles.root:
                    selected = prompt_select_profile(profiles)
                    return profiles, selected
            except Exception as e:
                typer.echo(f"Error parsing profiles.yml: {e}", err=True)
        else:
            typer.echo("File not found.", err=True)
        return None, None

    if action == "create":
        typer.echo("\nUse 'brix dbt profile init' to create profiles.yml first.")
        typer.echo("Then run this wizard again.")
        return None, None

    # Skip - use project name as profile
    typer.echo(f"\nSkipping profile setup. Using '{project_name}' as profile name.")
    typer.echo("Remember to configure this profile in profiles.yml manually.")
    return None, project_name


def _get_databricks_options(
    profiles: DbtProfiles | None, profile_name: str | None
) -> tuple[MaterializationType | None, bool]:
    """Get Databricks-specific options if applicable."""
    if not profiles or not profile_name:
        return None, False

    adapter_type = _detect_profile_type(profiles, profile_name)
    if adapter_type != "databricks":
        return None, False

    typer.echo("\n[Databricks Configuration]")
    materialization = prompt_materialization()
    if materialization is None:
        return None, False
    persist_docs = prompt_persist_docs()
    return materialization, persist_docs


def _create_project(
    project_name: str,
    base_dir: Path | None,
    team: str | None,
    selected_profile: str | None,
    selected_packages: list[str],
    materialization: MaterializationType | None,
    persist_docs: bool,
    with_example: bool,
) -> None:
    """Create the project with all settings."""
    typer.echo("\nFetching package versions...")
    packages = []
    for pkg_name in selected_packages:
        version = get_package_version(pkg_name)
        packages.append(HubPackage(package=pkg_name, version=version))
        typer.echo(f"  {pkg_name}: {version}")

    try:
        result = init_project(
            project_name=project_name,
            profile_name=selected_profile or project_name,
            base_dir=base_dir,
            team=team,
            packages=packages,
            materialization=materialization,
            persist_docs=persist_docs,
            with_example=with_example,
            force=True,
        )
        typer.echo(f"\n{result.message}")
        typer.echo("\nFiles created:")
        for f in result.files_created:
            typer.echo(f"  {f}")

        if prompt_run_deps(result.project_path):
            run_dbt_deps(result.project_path)
        else:
            typer.echo(f"\nRemember to run 'dbt deps' in {result.project_path} to install packages.")

        typer.echo("\nProject initialization complete!")
        typer.echo("Next steps:")
        typer.echo(f"  cd {result.project_path}")
        typer.echo("  dbt debug  # Test connection")
        typer.echo("  dbt run    # Run your models")
    except ProjectExistsError as e:
        typer.echo(str(e), err=True)


def run_interactive_init(profile_path: Path | None = None) -> None:  # noqa: C901
    """Run the interactive project initialization wizard."""
    typer.echo("\n[dbt Project Initialization Wizard]\n")

    project_name = prompt_project_name()
    if project_name is None:
        typer.echo("Cancelled.")
        return

    base_dir = prompt_base_dir()
    team = prompt_team()

    project_path = resolve_project_path(project_name, base_dir, team)
    if (project_path / "dbt_project.yml").exists():
        typer.echo(f"\nProject already exists at {project_path}")
        if not questionary.confirm("Overwrite existing project?", default=False).ask():
            typer.echo("Cancelled.")
            return

    # Profile setup
    profiles: DbtProfiles | None = None
    selected_profile: str | None = None
    effective_profile_path = profile_path or get_default_profile_path()

    if effective_profile_path.exists():
        typer.echo(f"\nFound profiles.yml at {effective_profile_path}")
        try:
            profiles = DbtProfiles.from_file(effective_profile_path)
        except Exception as e:
            typer.echo(f"Warning: Could not parse profiles.yml: {e}", err=True)

    if profiles and profiles.root:
        selected_profile = _handle_existing_profiles(profiles)
        if selected_profile is None:
            typer.echo("Cancelled.")
            return
    else:
        profiles, selected_profile = _handle_no_profiles(project_name)
        if selected_profile is None and profiles is None:
            return

    materialization, persist_docs = _get_databricks_options(profiles, selected_profile)
    if materialization is None and profiles and selected_profile:
        adapter_type = _detect_profile_type(profiles, selected_profile)
        if adapter_type == "databricks":
            typer.echo("Cancelled.")
            return

    selected_packages = prompt_select_packages()
    with_example = prompt_with_example()

    if not prompt_confirm_creation(
        project_name=project_name,
        project_path=project_path,
        profile_name=selected_profile or project_name,
        packages=selected_packages,
        materialization=materialization,
        persist_docs=persist_docs,
        with_example=with_example,
    ):
        typer.echo("Cancelled.")
        return

    _create_project(
        project_name,
        base_dir,
        team,
        selected_profile,
        selected_packages,
        materialization,
        persist_docs,
        with_example,
    )
