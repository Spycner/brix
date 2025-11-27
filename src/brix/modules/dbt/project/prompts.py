"""Interactive prompts for dbt project initialization and editing using questionary.

Provides a wizard-style flow for creating new dbt projects with
profile selection, package configuration, and Databricks-specific options.
Also provides interactive editing for existing projects.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

import questionary
import typer

from brix.modules.dbt.profile.models import DatabricksOutput, DbtProfiles
from brix.modules.dbt.profile.service import get_default_profile_path
from brix.modules.dbt.project.models import DbtPackages, DbtProject, HubPackage, ProjectNameError, validate_project_name
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


# =============================================================================
# Project Edit Prompts
# =============================================================================

# Action types for edit main menu
EditMainAction = Literal[
    "edit_settings",
    "manage_packages",
    "edit_paths",
    "exit",
]

# Action types for settings submenu
SettingsAction = Literal["name", "profile", "version", "require_dbt_version", "back"]

# Action types for packages submenu
PackageAction = Literal[
    "add_hub",
    "add_git",
    "add_local",
    "remove",
    "update_version",
    "back",
]

# Action types for paths submenu
PathAction = Literal[
    "model_paths",
    "seed_paths",
    "test_paths",
    "macro_paths",
    "snapshot_paths",
    "analysis_paths",
    "asset_paths",
    "clean_targets",
    "back",
]

# Action types for path editing
PathEditAction = Literal["add", "remove", "view", "back"]


def prompt_edit_main_action() -> EditMainAction:
    """Prompt user for main edit menu action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Edit project settings", value="edit_settings"),
        questionary.Choice("Manage packages", value="manage_packages"),
        questionary.Choice("Edit path configurations", value="edit_paths"),
        questionary.Choice("Exit", value="exit"),
    ]
    result = questionary.select("What would you like to do?", choices=choices).ask()
    if result is None:
        return "exit"
    return result


def prompt_settings_action() -> SettingsAction:
    """Prompt user for settings submenu action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Edit project name", value="name"),
        questionary.Choice("Edit profile name", value="profile"),
        questionary.Choice("Edit version", value="version"),
        questionary.Choice("Edit require-dbt-version", value="require_dbt_version"),
        questionary.Choice("Back to main menu", value="back"),
    ]
    result = questionary.select("What would you like to edit?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_package_action() -> PackageAction:
    """Prompt user for package submenu action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Add hub package", value="add_hub"),
        questionary.Choice("Add git package", value="add_git"),
        questionary.Choice("Add local package", value="add_local"),
        questionary.Choice("Remove package", value="remove"),
        questionary.Choice("Update package version", value="update_version"),
        questionary.Choice("Back to main menu", value="back"),
    ]
    result = questionary.select("What would you like to do?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_path_field_action() -> PathAction:
    """Prompt user for path field selection.

    Returns:
        Selected path field or back
    """
    choices = [
        questionary.Choice("model-paths", value="model_paths"),
        questionary.Choice("seed-paths", value="seed_paths"),
        questionary.Choice("test-paths", value="test_paths"),
        questionary.Choice("macro-paths", value="macro_paths"),
        questionary.Choice("snapshot-paths", value="snapshot_paths"),
        questionary.Choice("analysis-paths", value="analysis_paths"),
        questionary.Choice("asset-paths", value="asset_paths"),
        questionary.Choice("clean-targets", value="clean_targets"),
        questionary.Choice("Back to main menu", value="back"),
    ]
    result = questionary.select("Select path field to edit:", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_path_edit_action(field_name: str, current_paths: list[str]) -> PathEditAction:
    """Prompt user for path edit action.

    Args:
        field_name: Name of the path field
        current_paths: Current paths in the field

    Returns:
        Selected action
    """
    typer.echo(f"\nCurrent {field_name}: {', '.join(current_paths) if current_paths else '(none)'}")

    choices = [
        questionary.Choice("Add path", value="add"),
        questionary.Choice("Remove path", value="remove"),
        questionary.Choice("View current paths", value="view"),
        questionary.Choice("Back", value="back"),
    ]
    result = questionary.select("What would you like to do?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_edit_project_name(current: str) -> str | None:
    """Prompt for new project name with validation.

    Args:
        current: Current project name

    Returns:
        New project name or None if cancelled
    """
    while True:
        name = questionary.text(
            "Enter new project name:",
            default=current,
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


def prompt_edit_profile_name(current: str) -> str | None:
    """Prompt for new profile name.

    Args:
        current: Current profile name

    Returns:
        New profile name or None if cancelled
    """
    return questionary.text("Enter new profile name:", default=current).ask()


def prompt_edit_version(current: str) -> str | None:
    """Prompt for new version.

    Args:
        current: Current version

    Returns:
        New version or None if cancelled
    """
    return questionary.text("Enter new version:", default=current).ask()


def prompt_edit_require_dbt_version(current: str | None) -> str | None:
    """Prompt for new require-dbt-version.

    Args:
        current: Current constraint (may be None)

    Returns:
        New constraint or None if cancelled/cleared
    """
    result = questionary.text(
        "Enter dbt version constraint (empty to clear):",
        default=current or "",
        instruction="e.g., >=1.0.0,<2.0.0",
    ).ask()

    if result is None:
        return current  # Cancelled, keep current
    return result.strip() or None


def prompt_add_hub_package_details() -> tuple[str, str] | None:
    """Prompt for hub package details.

    Returns:
        Tuple of (package_name, version) or None if cancelled
    """
    # Offer popular packages or custom entry
    choices = [questionary.Choice(f"{pkg} - {desc}", value=pkg) for pkg, desc in POPULAR_PACKAGES]
    choices.append(questionary.Choice("Enter custom package name", value="_custom_"))

    selected = questionary.select("Select package:", choices=choices).ask()
    if selected is None:
        return None

    if selected == "_custom_":
        package_name = questionary.text(
            "Enter package name:",
            instruction="e.g., dbt-labs/dbt_utils",
        ).ask()
        if not package_name:
            return None
    else:
        package_name = selected

    # Fetch version
    typer.echo(f"Fetching latest version for {package_name}...")
    version = get_package_version(package_name)
    typer.echo(f"  Found version: {version}")

    # Allow override
    custom_version = questionary.text(
        "Version (press Enter to accept):",
        default=version,
    ).ask()

    if custom_version is None:
        return None

    return (package_name, custom_version)


def prompt_add_git_package_details() -> tuple[str, str, str | None] | None:
    """Prompt for git package details.

    Returns:
        Tuple of (git_url, revision, subdirectory) or None if cancelled
    """
    git_url = questionary.text(
        "Enter git URL:",
        instruction="e.g., https://github.com/org/repo.git",
    ).ask()
    if not git_url:
        return None

    revision = questionary.text(
        "Enter revision:",
        default="main",
        instruction="Branch, tag, or commit hash",
    ).ask()
    if not revision:
        return None

    subdirectory = questionary.text(
        "Enter subdirectory (optional):",
        instruction="Leave empty if package is at repo root",
    ).ask()

    if subdirectory is None:
        return None

    return (git_url, revision, subdirectory.strip() or None)


def prompt_add_local_package_path() -> str | None:
    """Prompt for local package path.

    Returns:
        Local path or None if cancelled
    """
    return questionary.text(
        "Enter local path:",
        instruction="e.g., ../shared_macros",
    ).ask()


def prompt_select_package(packages: DbtPackages) -> str | None:
    """Prompt user to select a package.

    Args:
        packages: DbtPackages instance

    Returns:
        Selected package identifier or None if cancelled
    """
    from brix.modules.dbt.project.editor import get_package_display_info

    if not packages.packages:
        typer.echo("No packages configured.", err=True)
        return None

    display_info = get_package_display_info(packages)
    choices = [questionary.Choice(f"{ident} ({info})", value=ident) for ident, info in display_info]

    return questionary.select("Select package:", choices=choices).ask()


def prompt_new_package_version(current: str) -> str | None:
    """Prompt for new package version.

    Args:
        current: Current version

    Returns:
        New version or None if cancelled
    """
    return questionary.text("Enter new version:", default=current).ask()


def prompt_add_path(field_name: str) -> str | None:
    """Prompt to add a path.

    Args:
        field_name: Name of the path field

    Returns:
        Path to add or None if cancelled
    """
    return questionary.text(f"Enter path to add to {field_name}:").ask()


def prompt_remove_path(current_paths: list[str]) -> str | None:
    """Prompt to select a path to remove.

    Args:
        current_paths: Current paths

    Returns:
        Path to remove or None if cancelled
    """
    if not current_paths:
        typer.echo("No paths to remove.", err=True)
        return None

    return questionary.select("Select path to remove:", choices=current_paths).ask()


def prompt_create_directory(path: Path) -> bool:
    """Ask user if they want to create a directory.

    Args:
        path: Directory path

    Returns:
        True if user wants to create it
    """
    return (
        questionary.confirm(
            f"Directory '{path}' does not exist. Create it?",
            default=True,
        ).ask()
        or False
    )


def prompt_confirm_delete(item_description: str) -> bool:
    """Prompt user to confirm deletion.

    Args:
        item_description: Description of item being deleted

    Returns:
        True if confirmed
    """
    result = questionary.confirm(f"Remove {item_description}?", default=False).ask()
    return result is True


def _display_project_status(project: DbtProject, packages: DbtPackages, project_path: Path) -> None:
    """Display current project configuration.

    Args:
        project: DbtProject instance
        packages: DbtPackages instance
        project_path: Path to dbt_project.yml
    """
    typer.echo(f"\n[Editing: {project_path.parent}]")
    typer.echo(f"  name: {project.name}")
    typer.echo(f"  profile: {project.profile}")
    typer.echo(f"  version: {project.version}")
    if project.require_dbt_version:
        typer.echo(f"  require-dbt-version: {project.require_dbt_version}")
    typer.echo(f"  packages: {len(packages.packages)}")


def _handle_settings_action(
    action: SettingsAction,
    project: DbtProject,
    project_path: Path,
) -> DbtProject:
    """Handle settings menu action.

    Args:
        action: Selected action
        project: Current project
        project_path: Path to dbt_project.yml

    Returns:
        Updated project
    """
    from brix.modules.dbt.project.editor import save_project, update_project_field

    if action == "back":
        return project

    # Handle require_dbt_version separately since it can be None
    if action == "require_dbt_version":
        new_value = prompt_edit_require_dbt_version(project.require_dbt_version)
        if new_value != project.require_dbt_version:
            try:
                project = update_project_field(project, action, new_value)
                save_project(project, project_path)
                typer.echo("Updated require-dbt-version")
            except Exception as e:
                typer.echo(f"Error: {e}", err=True)
        return project

    # Handle other string fields
    field_values: dict[str, str] = {
        "name": project.name,
        "profile": project.profile,
        "version": project.version,
    }
    field_prompts = {
        "name": prompt_edit_project_name,
        "profile": prompt_edit_profile_name,
        "version": prompt_edit_version,
    }

    if action not in field_values:
        return project

    current_value = field_values[action]
    new_value = field_prompts[action](current_value)

    if new_value is not None and new_value != current_value:
        try:
            project = update_project_field(project, action, new_value)
            save_project(project, project_path)
            typer.echo(f"Updated {action.replace('_', '-')}")
        except Exception as e:
            typer.echo(f"Error: {e}", err=True)

    return project


def _handle_package_action(  # noqa: C901
    action: PackageAction,
    packages: DbtPackages,
    project_path: Path,
) -> DbtPackages:
    """Handle package menu action.

    Args:
        action: Selected action
        packages: Current packages
        project_path: Path to dbt_project.yml (for directory)

    Returns:
        Updated packages
    """
    from brix.modules.dbt.project.editor import (
        PackageAlreadyExistsError,
        PackageNotFoundError,
        add_git_package,
        add_hub_package,
        add_local_package,
        remove_package,
        save_packages,
        update_package_version,
    )

    if action == "add_hub":
        details = prompt_add_hub_package_details()
        if details:
            package_name, version = details
            try:
                packages = add_hub_package(packages, package_name, version)
                save_packages(packages, project_path)
                typer.echo(f"Added package: {package_name} ({version})")
            except PackageAlreadyExistsError as e:
                typer.echo(str(e), err=True)

    elif action == "add_git":
        details = prompt_add_git_package_details()
        if details:
            git_url, revision, subdirectory = details
            try:
                packages = add_git_package(packages, git_url, revision, subdirectory)
                save_packages(packages, project_path)
                typer.echo(f"Added git package: {git_url}")
            except PackageAlreadyExistsError as e:
                typer.echo(str(e), err=True)

    elif action == "add_local":
        local_path = prompt_add_local_package_path()
        if local_path:
            try:
                packages = add_local_package(packages, local_path)
                save_packages(packages, project_path)
                typer.echo(f"Added local package: {local_path}")
            except PackageAlreadyExistsError as e:
                typer.echo(str(e), err=True)

    elif action == "remove":
        identifier = prompt_select_package(packages)
        if identifier and prompt_confirm_delete(f"package '{identifier}'"):
            try:
                packages = remove_package(packages, identifier)
                save_packages(packages, project_path)
                typer.echo(f"Removed package: {identifier}")
            except PackageNotFoundError as e:
                typer.echo(str(e), err=True)

    elif action == "update_version":
        identifier = prompt_select_package(packages)
        if identifier:
            # Find current version
            from brix.modules.dbt.project.editor import find_package_index
            from brix.modules.dbt.project.models import HubPackage as HubPkg

            idx = find_package_index(packages, identifier)
            if idx is not None:
                pkg = packages.packages[idx]
                if isinstance(pkg, HubPkg):
                    new_version = prompt_new_package_version(pkg.version)
                    if new_version and new_version != pkg.version:
                        try:
                            packages = update_package_version(packages, identifier, new_version)
                            save_packages(packages, project_path)
                            typer.echo(f"Updated {identifier} to {new_version}")
                        except (PackageNotFoundError, ValueError) as e:
                            typer.echo(str(e), err=True)
                else:
                    typer.echo("Can only update version for hub packages.", err=True)

    return packages


def _handle_path_action(  # noqa: C901
    field: PathAction,
    project: DbtProject,
    project_path: Path,
) -> DbtProject:
    """Handle path field editing.

    Args:
        field: Path field to edit
        project: Current project
        project_path: Path to dbt_project.yml

    Returns:
        Updated project
    """
    from brix.modules.dbt.project.editor import save_project, update_path_field

    if field == "back":
        return project

    current_paths: list[str] = getattr(project, field, [])

    while True:
        action = prompt_path_edit_action(field.replace("_", "-"), current_paths)

        if action == "back":
            break

        if action == "view":
            if current_paths:
                typer.echo(f"\n{field.replace('_', '-')}:")
                for p in current_paths:
                    typer.echo(f"  - {p}")
            else:
                typer.echo(f"\n{field.replace('_', '-')}: (none)")
            continue

        if action == "add":
            new_path = prompt_add_path(field.replace("_", "-"))
            if new_path:
                try:
                    project = update_path_field(project, field, "add", new_path)
                    save_project(project, project_path)
                    current_paths = getattr(project, field, [])
                    typer.echo(f"Added '{new_path}' to {field.replace('_', '-')}")

                    # Offer to create directory
                    full_path = project_path.parent / new_path
                    if not full_path.exists() and prompt_create_directory(full_path):
                        full_path.mkdir(parents=True, exist_ok=True)
                        typer.echo(f"Created directory: {full_path}")
                except Exception as e:
                    typer.echo(f"Error: {e}", err=True)

        elif action == "remove":
            path_to_remove = prompt_remove_path(current_paths)
            if path_to_remove:
                try:
                    project = update_path_field(project, field, "remove", path_to_remove)
                    save_project(project, project_path)
                    current_paths = getattr(project, field, [])
                    typer.echo(f"Removed '{path_to_remove}' from {field.replace('_', '-')}")
                except Exception as e:
                    typer.echo(f"Error: {e}", err=True)

    return project


def _edit_settings_loop(project: DbtProject, project_path: Path) -> DbtProject:
    """Settings editing submenu loop.

    Args:
        project: Current project
        project_path: Path to dbt_project.yml

    Returns:
        Updated project
    """
    while True:
        typer.echo(f"\n[Project Settings: {project.name}]")
        typer.echo(f"  name: {project.name}")
        typer.echo(f"  profile: {project.profile}")
        typer.echo(f"  version: {project.version}")
        typer.echo(f"  require-dbt-version: {project.require_dbt_version or '(not set)'}")

        action = prompt_settings_action()
        if action == "back":
            break

        project = _handle_settings_action(action, project, project_path)

    return project


def _edit_packages_loop(packages: DbtPackages, project_path: Path) -> DbtPackages:
    """Packages editing submenu loop.

    Args:
        packages: Current packages
        project_path: Path to dbt_project.yml

    Returns:
        Updated packages
    """
    from brix.modules.dbt.project.editor import get_package_display_info

    while True:
        typer.echo("\n[Packages]")
        if packages.packages:
            for ident, info in get_package_display_info(packages):
                typer.echo(f"  - {ident} ({info})")
        else:
            typer.echo("  (no packages)")

        action = prompt_package_action()
        if action == "back":
            break

        packages = _handle_package_action(action, packages, project_path)

    return packages


def _edit_paths_loop(project: DbtProject, project_path: Path) -> DbtProject:
    """Path configurations editing submenu loop.

    Args:
        project: Current project
        project_path: Path to dbt_project.yml

    Returns:
        Updated project
    """
    while True:
        typer.echo("\n[Path Configurations]")
        typer.echo(f"  model-paths: {', '.join(project.model_paths)}")
        typer.echo(f"  seed-paths: {', '.join(project.seed_paths)}")
        typer.echo(f"  test-paths: {', '.join(project.test_paths)}")
        typer.echo(f"  macro-paths: {', '.join(project.macro_paths)}")
        typer.echo(f"  snapshot-paths: {', '.join(project.snapshot_paths)}")
        typer.echo(f"  analysis-paths: {', '.join(project.analysis_paths)}")
        typer.echo(f"  asset-paths: {', '.join(project.asset_paths)}")
        typer.echo(f"  clean-targets: {', '.join(project.clean_targets)}")

        field = prompt_path_field_action()
        if field == "back":
            break

        project = _handle_path_action(field, project, project_path)

    return project


def run_interactive_edit(project_path: Path | None = None) -> None:
    """Run the interactive project editor.

    Main entry point for interactive project editing with nested loops.

    Args:
        project_path: Path to dbt_project.yml, discovers project if None
    """
    from brix.modules.dbt.project.editor import load_packages, load_project
    from brix.modules.dbt.project.finder import discover_and_select_project

    # Discover or use provided project
    if project_path is None:
        result = discover_and_select_project()
        if result is None:
            return
        project_path, project = result
    else:
        try:
            project = load_project(project_path)
        except Exception as e:
            typer.echo(f"Error loading project: {e}", err=True)
            return

    # Load packages
    packages = load_packages(project_path)

    typer.echo(f"Editing project at: {project_path.parent}")

    try:
        while True:
            _display_project_status(project, packages, project_path)
            action = prompt_edit_main_action()

            if action == "exit":
                typer.echo("Goodbye!")
                break

            if action == "edit_settings":
                project = _edit_settings_loop(project, project_path)
            elif action == "manage_packages":
                packages = _edit_packages_loop(packages, project_path)
            elif action == "edit_paths":
                project = _edit_paths_loop(project, project_path)

    except KeyboardInterrupt:
        typer.echo("\nExiting...")
