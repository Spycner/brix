"""Interactive prompts for dbt profile editing using questionary.

Provides nested menu loops with context preservation for CRUD operations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import questionary
import typer

from brix.modules.dbt.profile_editor import (
    OutputAlreadyExistsError,
    OutputNotFoundError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    add_output,
    add_profile,
    delete_output,
    delete_profile,
    get_output,
    get_output_names,
    get_profile_names,
    load_profiles,
    save_profiles,
    update_output,
    update_profile_target,
)
from brix.modules.dbt.profile_models import DbtProfiles, DuckDbOutput

# Action types for main menu
MainAction = Literal[
    "add_profile",
    "edit_profile",
    "delete_profile",
    "add_output",
    "edit_output",
    "delete_output",
    "exit",
]

# Action types for profile submenu
ProfileAction = Literal["target", "edit_output", "back"]

# Action types for output submenu
OutputAction = Literal["path", "threads", "back"]


def prompt_main_action() -> MainAction:
    """Prompt user for main menu action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Add a new profile", value="add_profile"),
        questionary.Choice("Edit an existing profile", value="edit_profile"),
        questionary.Choice("Delete a profile", value="delete_profile"),
        questionary.Choice("Add an output to a profile", value="add_output"),
        questionary.Choice("Edit an output", value="edit_output"),
        questionary.Choice("Delete an output", value="delete_output"),
        questionary.Choice("Exit", value="exit"),
    ]
    result = questionary.select("What would you like to do?", choices=choices).ask()
    if result is None:
        return "exit"
    return result


def prompt_select_profile(profiles: DbtProfiles, message: str = "Select profile:") -> str | None:
    """Prompt user to select a profile.

    Args:
        profiles: DbtProfiles instance
        message: Prompt message

    Returns:
        Selected profile name, or None if cancelled
    """
    names = get_profile_names(profiles)
    if not names:
        typer.echo("No profiles found.", err=True)
        return None
    return questionary.select(message, choices=names).ask()


def prompt_select_output(profiles: DbtProfiles, profile_name: str, message: str = "Select output:") -> str | None:
    """Prompt user to select an output.

    Args:
        profiles: DbtProfiles instance
        profile_name: Name of the profile
        message: Prompt message

    Returns:
        Selected output name, or None if cancelled
    """
    try:
        names = get_output_names(profiles, profile_name)
    except ProfileNotFoundError:
        typer.echo(f"Profile '{profile_name}' not found.", err=True)
        return None

    if not names:
        typer.echo("No outputs found.", err=True)
        return None
    return questionary.select(message, choices=names).ask()


def prompt_profile_action() -> ProfileAction:
    """Prompt user for profile editing action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Edit target", value="target"),
        questionary.Choice("Edit an output", value="edit_output"),
        questionary.Choice("Back to main menu", value="back"),
    ]
    result = questionary.select("What would you like to edit?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_output_action() -> OutputAction:
    """Prompt user for output editing action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Edit path", value="path"),
        questionary.Choice("Edit threads", value="threads"),
        questionary.Choice("Back to profile menu", value="back"),
    ]
    result = questionary.select("What would you like to edit?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_new_profile_details() -> tuple[str, str, str, DuckDbOutput] | None:
    """Prompt user for new profile details.

    Returns:
        Tuple of (profile_name, target, output_name, output_config), or None if cancelled
    """
    profile_name = questionary.text("Enter profile name:").ask()
    if not profile_name:
        return None

    target = questionary.text("Enter default target name:", default="dev").ask()
    if not target:
        return None

    output_name = questionary.text("Enter initial output name:", default=target).ask()
    if not output_name:
        return None

    path = questionary.text("Enter DuckDB path:", default=":memory:").ask()
    if path is None:
        return None

    threads_str = questionary.text("Enter thread count:", default="1").ask()
    if threads_str is None:
        return None

    try:
        threads = int(threads_str)
    except ValueError:
        typer.echo("Invalid thread count, using 1", err=True)
        threads = 1

    output_config = DuckDbOutput(type="duckdb", path=path, threads=threads)
    return (profile_name, target, output_name, output_config)


def prompt_new_output_details() -> tuple[str, DuckDbOutput] | None:
    """Prompt user for new output details.

    Returns:
        Tuple of (output_name, output_config), or None if cancelled
    """
    output_name = questionary.text("Enter output name:").ask()
    if not output_name:
        return None

    path = questionary.text("Enter DuckDB path:", default=":memory:").ask()
    if path is None:
        return None

    threads_str = questionary.text("Enter thread count:", default="1").ask()
    if threads_str is None:
        return None

    try:
        threads = int(threads_str)
    except ValueError:
        typer.echo("Invalid thread count, using 1", err=True)
        threads = 1

    output_config = DuckDbOutput(type="duckdb", path=path, threads=threads)
    return (output_name, output_config)


def prompt_confirm_delete(item_description: str) -> bool:
    """Prompt user to confirm deletion.

    Args:
        item_description: Description of item being deleted

    Returns:
        True if confirmed, False otherwise
    """
    result = questionary.confirm(f"Delete {item_description}?", default=False).ask()
    return result is True


def _handle_add_profile(profiles: DbtProfiles, profile_path: Path) -> DbtProfiles:
    """Handle adding a new profile.

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles

    Returns:
        Updated profiles
    """
    details = prompt_new_profile_details()
    if details is None:
        return profiles

    profile_name, target, output_name, output_config = details

    try:
        profiles = add_profile(profiles, profile_name, target, output_name, output_config)
        save_profiles(profiles, profile_path)
        typer.echo(f"Added profile '{profile_name}'")
    except ProfileAlreadyExistsError as e:
        typer.echo(str(e), err=True)

    return profiles


def _handle_delete_profile(profiles: DbtProfiles, profile_path: Path) -> DbtProfiles:
    """Handle deleting a profile.

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles

    Returns:
        Updated profiles
    """
    profile_name = prompt_select_profile(profiles, "Select profile to delete:")
    if profile_name is None:
        return profiles

    if not prompt_confirm_delete(f"profile '{profile_name}'"):
        typer.echo("Cancelled")
        return profiles

    try:
        profiles = delete_profile(profiles, profile_name)
        save_profiles(profiles, profile_path)
        typer.echo(f"Deleted profile '{profile_name}'")
    except ProfileNotFoundError as e:
        typer.echo(str(e), err=True)

    return profiles


def _handle_add_output(profiles: DbtProfiles, profile_path: Path) -> DbtProfiles:
    """Handle adding an output to a profile.

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles

    Returns:
        Updated profiles
    """
    profile_name = prompt_select_profile(profiles, "Select profile to add output to:")
    if profile_name is None:
        return profiles

    details = prompt_new_output_details()
    if details is None:
        return profiles

    output_name, output_config = details

    try:
        profiles = add_output(profiles, profile_name, output_name, output_config)
        save_profiles(profiles, profile_path)
        typer.echo(f"Added output '{output_name}' to profile '{profile_name}'")
    except (ProfileNotFoundError, OutputAlreadyExistsError) as e:
        typer.echo(str(e), err=True)

    return profiles


def _handle_delete_output(profiles: DbtProfiles, profile_path: Path) -> DbtProfiles:
    """Handle deleting an output.

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles

    Returns:
        Updated profiles
    """
    profile_name = prompt_select_profile(profiles, "Select profile:")
    if profile_name is None:
        return profiles

    output_name = prompt_select_output(profiles, profile_name, "Select output to delete:")
    if output_name is None:
        return profiles

    if not prompt_confirm_delete(f"output '{output_name}' from profile '{profile_name}'"):
        typer.echo("Cancelled")
        return profiles

    try:
        profiles = delete_output(profiles, profile_name, output_name)
        save_profiles(profiles, profile_path)
        typer.echo(f"Deleted output '{output_name}' from profile '{profile_name}'")
    except (ProfileNotFoundError, OutputNotFoundError, ValueError) as e:
        typer.echo(str(e), err=True)

    return profiles


def _update_output_path(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, current_path: str
) -> DbtProfiles:
    """Prompt and update output path."""
    new_path = questionary.text("Enter new path:", default=current_path).ask()
    if new_path is not None:
        try:
            profiles = update_output(profiles, profile_name, output_name, path=new_path)
            save_profiles(profiles, profile_path)
            typer.echo(f"Updated path to '{new_path}'")
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)
    return profiles


def _update_output_threads(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, current_threads: int
) -> DbtProfiles:
    """Prompt and update output threads."""
    threads_str = questionary.text("Enter new thread count:", default=str(current_threads)).ask()
    if threads_str is not None:
        try:
            threads = int(threads_str)
            profiles = update_output(profiles, profile_name, output_name, threads=threads)
            save_profiles(profiles, profile_path)
            typer.echo(f"Updated threads to {threads}")
        except ValueError:
            typer.echo("Invalid thread count", err=True)
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)
    return profiles


def _edit_output_loop(profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str) -> DbtProfiles:
    """Output editing submenu loop.

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles
        profile_name: Name of the profile
        output_name: Name of the output

    Returns:
        Updated profiles
    """
    while True:
        try:
            output = get_output(profiles, profile_name, output_name)
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)
            break

        typer.echo(f"\n[Editing output: {profile_name}.{output_name}]")
        typer.echo(f"  path: {output.path}")
        typer.echo(f"  threads: {output.threads}")

        action = prompt_output_action()

        if action == "back":
            break
        if action == "path":
            profiles = _update_output_path(profiles, profile_path, profile_name, output_name, output.path)
        elif action == "threads":
            profiles = _update_output_threads(profiles, profile_path, profile_name, output_name, output.threads)

    return profiles


def _edit_profile_loop(profiles: DbtProfiles, profile_path: Path, profile_name: str) -> DbtProfiles:
    """Profile editing submenu loop.

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles
        profile_name: Name of the profile

    Returns:
        Updated profiles
    """
    while True:
        if profile_name not in profiles.root:
            typer.echo(f"Profile '{profile_name}' not found.", err=True)
            break

        profile = profiles.root[profile_name]
        typer.echo(f"\n[Editing profile: {profile_name}]")
        typer.echo(f"  target: {profile.target}")
        typer.echo(f"  outputs: {', '.join(profile.outputs.keys())}")

        action = prompt_profile_action()

        if action == "back":
            break

        if action == "target":
            new_target = questionary.text("Enter new target:", default=profile.target).ask()
            if new_target is not None:
                try:
                    profiles = update_profile_target(profiles, profile_name, new_target)
                    save_profiles(profiles, profile_path)
                    typer.echo(f"Updated target to '{new_target}'")
                except ProfileNotFoundError as e:
                    typer.echo(str(e), err=True)

        elif action == "edit_output":
            output_name = prompt_select_output(profiles, profile_name)
            if output_name is not None:
                profiles = _edit_output_loop(profiles, profile_path, profile_name, output_name)

    return profiles


def _handle_edit_profile(profiles: DbtProfiles, profile_path: Path) -> DbtProfiles:
    """Handle edit profile action from main menu."""
    profile_name = prompt_select_profile(profiles, "Select profile to edit:")
    if profile_name is not None:
        profiles = _edit_profile_loop(profiles, profile_path, profile_name)
    return profiles


def _handle_edit_output(profiles: DbtProfiles, profile_path: Path) -> DbtProfiles:
    """Handle edit output action from main menu."""
    profile_name = prompt_select_profile(profiles, "Select profile:")
    if profile_name is not None:
        output_name = prompt_select_output(profiles, profile_name)
        if output_name is not None:
            profiles = _edit_output_loop(profiles, profile_path, profile_name, output_name)
    return profiles


def _dispatch_action(action: MainAction, profiles: DbtProfiles, target_path: Path) -> DbtProfiles:
    """Dispatch main menu action to handler."""
    handlers = {
        "add_profile": _handle_add_profile,
        "edit_profile": _handle_edit_profile,
        "delete_profile": _handle_delete_profile,
        "add_output": _handle_add_output,
        "edit_output": _handle_edit_output,
        "delete_output": _handle_delete_output,
    }
    handler = handlers.get(action)
    if handler:
        return handler(profiles, target_path)
    return profiles


def run_interactive_edit(profile_path: Path | None = None) -> None:
    """Run the interactive profile editor.

    Main entry point for interactive editing with nested loops.

    Args:
        profile_path: Path to profiles.yml, uses default if None
    """
    from brix.modules.dbt.profile import get_default_profile_path

    target_path = profile_path or get_default_profile_path()

    # Load profiles or create empty structure if file doesn't exist
    try:
        profiles = load_profiles(target_path)
    except FileNotFoundError:
        typer.echo(f"No profiles found at {target_path}. Creating new file.")
        profiles = DbtProfiles(root={})

    typer.echo(f"Editing profiles at: {target_path}")

    try:
        while True:
            action = prompt_main_action()
            if action == "exit":
                typer.echo("Goodbye!")
                break
            profiles = _dispatch_action(action, profiles, target_path)
    except KeyboardInterrupt:
        typer.echo("\nExiting...")
