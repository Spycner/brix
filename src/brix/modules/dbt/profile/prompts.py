"""Interactive prompts for dbt profile editing using questionary.

Provides nested menu loops with context preservation for CRUD operations.
Supports both DuckDB and Databricks adapter configurations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import questionary
import typer

from brix.modules.dbt.profile.editor import (
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
    update_output_fields,
    update_profile_target,
)
from brix.modules.dbt.profile.models import DatabricksOutput, DbtProfiles, DuckDbOutput, OutputConfig

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

# Action types for output submenus
DuckDbOutputAction = Literal["path", "schema", "database", "threads", "extensions", "settings", "back"]
DatabricksOutputAction = Literal["host", "http_path", "schema", "catalog", "token", "threads", "back"]

# Adapter types
AdapterType = Literal["duckdb", "databricks"]

# Databricks authentication methods
DatabricksAuthMethod = Literal["token", "oauth_u2m", "oauth_m2m_aws", "oauth_m2m_azure"]


def prompt_adapter_type() -> AdapterType | None:
    """Prompt user to select adapter type.

    Returns:
        Selected adapter type, or None if cancelled
    """
    choices = [
        questionary.Choice("DuckDB (local/in-memory database)", value="duckdb"),
        questionary.Choice("Databricks (cloud data platform)", value="databricks"),
    ]
    return questionary.select("Select adapter type:", choices=choices).ask()


def prompt_databricks_auth_method() -> DatabricksAuthMethod | None:
    """Prompt user to select Databricks authentication method.

    Returns:
        Selected auth method, or None if cancelled
    """
    choices = [
        questionary.Choice("Personal Access Token (PAT)", value="token"),
        questionary.Choice("OAuth U2M (browser login)", value="oauth_u2m"),
        questionary.Choice("OAuth M2M - AWS/GCP (client credentials)", value="oauth_m2m_aws"),
        questionary.Choice("OAuth M2M - Azure (client credentials)", value="oauth_m2m_azure"),
    ]
    return questionary.select("Select authentication method:", choices=choices).ask()


def _parse_extensions(input_str: str) -> list[str]:
    """Parse comma-separated extensions string into list."""
    if not input_str.strip():
        return []
    return [ext.strip() for ext in input_str.split(",") if ext.strip()]


def _parse_setting(input_str: str) -> tuple[str, str] | None:
    """Parse a key=value setting string.

    Returns:
        Tuple of (key, value) or None if invalid format
    """
    if "=" not in input_str:
        return None
    key, _, value = input_str.partition("=")
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    return (key, value)


def _prompt_settings_loop() -> dict[str, str]:
    """Prompt for settings as key=value pairs until empty input."""
    settings: dict[str, str] = {}
    typer.echo("Enter settings as key=value pairs (empty to finish):")
    while True:
        setting_str = questionary.text("  Setting:").ask()
        if setting_str is None or not setting_str.strip():
            break
        parsed = _parse_setting(setting_str)
        if parsed:
            key, value = parsed
            settings[key] = value
            typer.echo(f"    Added: {key}={value}")
        else:
            typer.echo("    Invalid format, use key=value", err=True)
    return settings


def prompt_duckdb_output_details() -> DuckDbOutput | None:
    """Prompt user for DuckDB output configuration.

    Returns:
        DuckDbOutput configuration, or None if cancelled
    """
    typer.echo("\n[DuckDB Configuration]")

    path = questionary.text(
        "Database path:",
        default=":memory:",
        instruction="Use ':memory:' for in-memory database or a file path",
    ).ask()
    if path is None:
        return None

    schema = questionary.text(
        "Schema:",
        default="main",
        instruction="Default schema for models",
    ).ask()
    if schema is None:
        return None

    database = questionary.text(
        "Database:",
        default="main",
        instruction="Database name (usually 'main')",
    ).ask()
    if database is None:
        return None

    threads_str = questionary.text("Thread count:", default="1").ask()
    if threads_str is None:
        return None

    try:
        threads = int(threads_str)
        if threads < 1:
            typer.echo("Invalid thread count, using 1", err=True)
            threads = 1
    except ValueError:
        typer.echo("Invalid thread count, using 1", err=True)
        threads = 1

    # Extensions (optional)
    typer.echo("\nOptional: DuckDB Extensions")
    extensions_str = questionary.text(
        "Extensions:",
        default="",
        instruction="Comma-separated list (e.g., httpfs,parquet) or leave empty",
    ).ask()
    if extensions_str is None:
        return None
    extensions = _parse_extensions(extensions_str)

    # Settings (optional)
    typer.echo("\nOptional: DuckDB Settings")
    add_settings = questionary.confirm("Add custom settings?", default=False).ask()
    if add_settings is None:
        return None
    settings = _prompt_settings_loop() if add_settings else {}

    return DuckDbOutput(
        type="duckdb",
        path=path,
        schema_=schema,
        database=database,
        threads=threads,
        extensions=extensions,
        settings=settings,
    )


def _prompt_databricks_connection() -> tuple[str, str, str, str | None] | None:
    """Prompt for Databricks connection settings.

    Returns:
        Tuple of (host, http_path, schema, catalog), or None if cancelled
    """
    typer.echo("\n[Databricks Configuration]")
    typer.echo("Required connection settings:")

    host = questionary.text(
        "Host:",
        instruction="e.g., myorg.databricks.com (without https://)",
    ).ask()
    if not host:
        return None

    http_path = questionary.text(
        "HTTP path:",
        instruction="e.g., /sql/1.0/warehouses/abc123",
    ).ask()
    if not http_path:
        return None

    schema = questionary.text(
        "Schema:",
        instruction="The default schema for your models",
    ).ask()
    if not schema:
        return None

    catalog = questionary.text(
        "Catalog (optional):",
        default="",
        instruction="Leave empty if not using Unity Catalog",
    ).ask()
    if catalog is None:
        return None

    return (host, http_path, schema, catalog or None)


def _prompt_databricks_auth(auth_method: DatabricksAuthMethod) -> dict[str, str | None] | None:
    """Prompt for Databricks authentication fields based on method.

    Returns:
        Dict with auth fields, or None if cancelled
    """
    if auth_method == "token":
        token = questionary.password(
            "Personal Access Token:",
            instruction="Your Databricks PAT (starts with dapi...)",
        ).ask()
        if not token:
            return None
        return {"token": token, "auth_type": None}

    if auth_method == "oauth_u2m":
        typer.echo("OAuth U2M configured - browser login will be used at runtime")
        return {"token": None, "auth_type": "oauth"}

    if auth_method == "oauth_m2m_aws":
        client_id = questionary.text("Client ID:").ask()
        if not client_id:
            return None
        client_secret = questionary.password("Client Secret:").ask()
        if not client_secret:
            return None
        return {"token": None, "auth_type": "oauth", "client_id": client_id, "client_secret": client_secret}

    # oauth_m2m_azure
    azure_client_id = questionary.text("Azure Client ID:").ask()
    if not azure_client_id:
        return None
    azure_client_secret = questionary.password("Azure Client Secret:").ask()
    if not azure_client_secret:
        return None
    return {
        "token": None,
        "auth_type": "oauth",
        "azure_client_id": azure_client_id,
        "azure_client_secret": azure_client_secret,
    }


def prompt_databricks_output_details() -> DatabricksOutput | None:
    """Prompt user for Databricks output configuration with guided wizard.

    Returns:
        DatabricksOutput configuration, or None if cancelled
    """
    # Connection settings
    conn = _prompt_databricks_connection()
    if conn is None:
        return None
    host, http_path, schema, catalog = conn

    # Authentication
    typer.echo("\nAuthentication:")
    auth_method = prompt_databricks_auth_method()
    if auth_method is None:
        return None

    auth = _prompt_databricks_auth(auth_method)
    if auth is None:
        return None

    # Optional settings
    typer.echo("\nOptional settings:")
    threads_str = questionary.text("Thread count:", default="1").ask()
    if threads_str is None:
        return None
    try:
        threads = int(threads_str)
        if threads < 1:
            threads = 1
    except ValueError:
        threads = 1

    return DatabricksOutput(
        type="databricks",
        schema=schema,
        host=host,
        http_path=http_path,
        catalog=catalog,
        token=auth.get("token"),
        auth_type=auth.get("auth_type"),  # type: ignore[arg-type]
        client_id=auth.get("client_id"),
        client_secret=auth.get("client_secret"),
        azure_client_id=auth.get("azure_client_id"),
        azure_client_secret=auth.get("azure_client_secret"),
        threads=threads,
    )


def prompt_output_config() -> OutputConfig | None:
    """Prompt user for output configuration (adapter selection + details).

    Returns:
        Output configuration (DuckDbOutput or DatabricksOutput), or None if cancelled
    """
    adapter_type = prompt_adapter_type()
    if adapter_type is None:
        return None

    if adapter_type == "duckdb":
        return prompt_duckdb_output_details()
    else:
        return prompt_databricks_output_details()


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


def prompt_duckdb_output_action() -> DuckDbOutputAction:
    """Prompt user for DuckDB output editing action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Edit path", value="path"),
        questionary.Choice("Edit schema", value="schema"),
        questionary.Choice("Edit database", value="database"),
        questionary.Choice("Edit threads", value="threads"),
        questionary.Choice("Edit extensions", value="extensions"),
        questionary.Choice("Edit settings", value="settings"),
        questionary.Choice("Back to profile menu", value="back"),
    ]
    result = questionary.select("What would you like to edit?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_databricks_output_action() -> DatabricksOutputAction:
    """Prompt user for Databricks output editing action.

    Returns:
        Selected action
    """
    choices = [
        questionary.Choice("Edit host", value="host"),
        questionary.Choice("Edit HTTP path", value="http_path"),
        questionary.Choice("Edit schema", value="schema"),
        questionary.Choice("Edit catalog", value="catalog"),
        questionary.Choice("Edit token", value="token"),
        questionary.Choice("Edit threads", value="threads"),
        questionary.Choice("Back to profile menu", value="back"),
    ]
    result = questionary.select("What would you like to edit?", choices=choices).ask()
    if result is None:
        return "back"
    return result


def prompt_new_profile_details() -> tuple[str, str, str, OutputConfig] | None:
    """Prompt user for new profile details with adapter selection.

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

    # Adapter selection and configuration
    output_config = prompt_output_config()
    if output_config is None:
        return None

    return (profile_name, target, output_name, output_config)


def prompt_new_output_details() -> tuple[str, OutputConfig] | None:
    """Prompt user for new output details with adapter selection.

    Returns:
        Tuple of (output_name, output_config), or None if cancelled
    """
    output_name = questionary.text("Enter output name:").ask()
    if not output_name:
        return None

    # Adapter selection and configuration
    output_config = prompt_output_config()
    if output_config is None:
        return None

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

    # Check if deleting the current target
    profile = profiles.root[profile_name]
    new_target: str | None = None
    if profile.target == output_name:
        other_outputs = [name for name in profile.outputs if name != output_name]
        if not other_outputs:
            typer.echo(
                f"Cannot delete output '{output_name}' - it is the current target and no other outputs exist.",
                err=True,
            )
            return profiles

        typer.echo(f"Output '{output_name}' is the current target. Select a new target:")
        new_target = questionary.select("New target:", choices=other_outputs).ask()
        if new_target is None:
            typer.echo("Cancelled")
            return profiles

    try:
        if new_target:
            profiles = update_profile_target(profiles, profile_name, new_target)
            typer.echo(f"Changed target to '{new_target}'")
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


def _update_duckdb_schema(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, current_schema: str
) -> DbtProfiles:
    """Prompt and update DuckDB schema."""
    new_schema = questionary.text("Enter new schema:", default=current_schema).ask()
    if new_schema is not None and new_schema:
        try:
            profiles = update_output_fields(profiles, profile_name, output_name, {"schema_": new_schema})
            save_profiles(profiles, profile_path)
            typer.echo(f"Updated schema to '{new_schema}'")
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)
    return profiles


def _update_duckdb_database(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, current_database: str
) -> DbtProfiles:
    """Prompt and update DuckDB database."""
    new_database = questionary.text("Enter new database:", default=current_database).ask()
    if new_database is not None and new_database:
        try:
            profiles = update_output_fields(profiles, profile_name, output_name, {"database": new_database})
            save_profiles(profiles, profile_path)
            typer.echo(f"Updated database to '{new_database}'")
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)
    return profiles


def _update_duckdb_extensions(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, current_extensions: list[str]
) -> DbtProfiles:
    """Prompt and update DuckDB extensions."""
    current_str = ",".join(current_extensions) if current_extensions else ""
    typer.echo(f"Current extensions: {current_str or '(none)'}")

    choices = [
        questionary.Choice("Replace all", value="replace"),
        questionary.Choice("Clear all", value="clear"),
        questionary.Choice("Cancel", value="cancel"),
    ]
    action = questionary.select("What would you like to do?", choices=choices).ask()

    if action == "replace":
        new_extensions_str = questionary.text(
            "Enter extensions (comma-separated):",
            default=current_str,
            instruction="e.g., httpfs,parquet",
        ).ask()
        if new_extensions_str is not None:
            new_extensions = _parse_extensions(new_extensions_str)
            try:
                profiles = update_output_fields(profiles, profile_name, output_name, {"extensions": new_extensions})
                save_profiles(profiles, profile_path)
                typer.echo(f"Updated extensions to: {','.join(new_extensions) or '(none)'}")
            except (ProfileNotFoundError, OutputNotFoundError) as e:
                typer.echo(str(e), err=True)
    elif action == "clear":
        try:
            profiles = update_output_fields(profiles, profile_name, output_name, {"extensions": []})
            save_profiles(profiles, profile_path)
            typer.echo("Cleared all extensions")
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)

    return profiles


def _add_duckdb_setting(
    profiles: DbtProfiles,
    profile_path: Path,
    profile_name: str,
    output_name: str,
    current_settings: dict[str, str],
) -> DbtProfiles:
    """Add or update a single DuckDB setting."""
    setting_str = questionary.text("Enter setting (key=value):").ask()
    if not setting_str:
        return profiles

    parsed = _parse_setting(setting_str)
    if not parsed:
        typer.echo("Invalid format, use key=value", err=True)
        return profiles

    key, value = parsed
    new_settings = dict(current_settings)
    new_settings[key] = value
    try:
        profiles = update_output_fields(profiles, profile_name, output_name, {"settings": new_settings})
        save_profiles(profiles, profile_path)
        typer.echo(f"Added setting: {key}={value}")
    except (ProfileNotFoundError, OutputNotFoundError) as e:
        typer.echo(str(e), err=True)
    return profiles


def _remove_duckdb_setting(
    profiles: DbtProfiles,
    profile_path: Path,
    profile_name: str,
    output_name: str,
    current_settings: dict[str, str],
) -> DbtProfiles:
    """Remove a single DuckDB setting."""
    if not current_settings:
        typer.echo("No settings to remove", err=True)
        return profiles

    key_to_remove = questionary.select("Select setting to remove:", choices=list(current_settings.keys())).ask()
    if not key_to_remove:
        return profiles

    new_settings = {k: v for k, v in current_settings.items() if k != key_to_remove}
    try:
        profiles = update_output_fields(profiles, profile_name, output_name, {"settings": new_settings})
        save_profiles(profiles, profile_path)
        typer.echo(f"Removed setting: {key_to_remove}")
    except (ProfileNotFoundError, OutputNotFoundError) as e:
        typer.echo(str(e), err=True)
    return profiles


def _update_duckdb_settings(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, current_settings: dict[str, str]
) -> DbtProfiles:
    """Prompt and update DuckDB settings."""
    if current_settings:
        typer.echo("Current settings:")
        for key, value in current_settings.items():
            typer.echo(f"  {key}={value}")
    else:
        typer.echo("Current settings: (none)")

    choices = [
        questionary.Choice("Add/update a setting", value="add"),
        questionary.Choice("Remove a setting", value="remove"),
        questionary.Choice("Clear all settings", value="clear"),
        questionary.Choice("Cancel", value="cancel"),
    ]
    action = questionary.select("What would you like to do?", choices=choices).ask()

    if action == "add":
        return _add_duckdb_setting(profiles, profile_path, profile_name, output_name, current_settings)
    if action == "remove":
        return _remove_duckdb_setting(profiles, profile_path, profile_name, output_name, current_settings)
    if action == "clear":
        try:
            profiles = update_output_fields(profiles, profile_name, output_name, {"settings": {}})
            save_profiles(profiles, profile_path)
            typer.echo("Cleared all settings")
        except (ProfileNotFoundError, OutputNotFoundError) as e:
            typer.echo(str(e), err=True)

    return profiles


def _display_duckdb_output_status(profile_name: str, output_name: str, output: DuckDbOutput) -> None:
    """Display current DuckDB output configuration."""
    typer.echo(f"\n[Editing DuckDB output: {profile_name}.{output_name}]")
    typer.echo(f"  path: {output.path}")
    typer.echo(f"  schema: {output.schema_}")
    typer.echo(f"  database: {output.database}")
    typer.echo(f"  threads: {output.threads}")
    typer.echo(f"  extensions: {','.join(output.extensions) if output.extensions else '(none)'}")
    if output.settings:
        typer.echo("  settings:")
        for key, value in output.settings.items():
            typer.echo(f"    {key}={value}")
    else:
        typer.echo("  settings: (none)")


def _handle_duckdb_action(
    action: DuckDbOutputAction,
    profiles: DbtProfiles,
    profile_path: Path,
    profile_name: str,
    output_name: str,
    output: DuckDbOutput,
) -> DbtProfiles:
    """Handle a single DuckDB edit action."""
    if action == "path":
        return _update_output_path(profiles, profile_path, profile_name, output_name, output.path)
    if action == "schema":
        return _update_duckdb_schema(profiles, profile_path, profile_name, output_name, output.schema_)
    if action == "database":
        return _update_duckdb_database(profiles, profile_path, profile_name, output_name, output.database)
    if action == "threads":
        return _update_output_threads(profiles, profile_path, profile_name, output_name, output.threads)
    if action == "extensions":
        return _update_duckdb_extensions(profiles, profile_path, profile_name, output_name, output.extensions)
    if action == "settings":
        return _update_duckdb_settings(profiles, profile_path, profile_name, output_name, output.settings)
    return profiles


def _edit_duckdb_output_loop(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, output: DuckDbOutput
) -> DbtProfiles:
    """DuckDB output editing submenu loop."""
    while True:
        _display_duckdb_output_status(profile_name, output_name, output)
        action = prompt_duckdb_output_action()

        if action == "back":
            break

        profiles = _handle_duckdb_action(action, profiles, profile_path, profile_name, output_name, output)

        # Refresh output reference
        try:
            output = get_output(profiles, profile_name, output_name)  # type: ignore[assignment]
        except (ProfileNotFoundError, OutputNotFoundError):
            break

    return profiles


def _handle_databricks_action(
    action: DatabricksOutputAction,
    profiles: DbtProfiles,
    profile_path: Path,
    profile_name: str,
    output_name: str,
    output: DatabricksOutput,
) -> DbtProfiles:
    """Handle a single Databricks edit action."""
    field_prompts = {
        "host": ("Enter new host:", output.host, False),
        "http_path": ("Enter new HTTP path:", output.http_path, False),
        "schema": ("Enter new schema:", output.schema_, False),
        "catalog": ("Enter new catalog (empty to clear):", output.catalog or "", True),
    }

    if action in field_prompts:
        prompt, default, allow_empty = field_prompts[action]
        field_name = "schema_" if action == "schema" else action
        new_value = questionary.text(prompt, default=default).ask()
        if new_value is not None and (new_value or allow_empty):
            profiles = _update_databricks_field(
                profiles, profile_path, profile_name, output_name, field_name, new_value or None
            )
    elif action == "token":
        new_token = questionary.password("Enter new token (empty to clear):").ask()
        if new_token is not None:
            profiles = _update_databricks_field(
                profiles, profile_path, profile_name, output_name, "token", new_token or None
            )
    elif action == "threads":
        profiles = _update_output_threads(profiles, profile_path, profile_name, output_name, output.threads)

    return profiles


def _edit_databricks_output_loop(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, output: DatabricksOutput
) -> DbtProfiles:
    """Databricks output editing submenu loop."""
    while True:
        typer.echo(f"\n[Editing Databricks output: {profile_name}.{output_name}]")
        typer.echo(f"  host: {output.host}")
        typer.echo(f"  http_path: {output.http_path}")
        typer.echo(f"  schema: {output.schema_}")
        typer.echo(f"  catalog: {output.catalog or '(not set)'}")
        typer.echo(f"  auth: {'token' if output.token else 'oauth' if output.auth_type else '(not configured)'}")
        typer.echo(f"  threads: {output.threads}")

        action = prompt_databricks_output_action()
        if action == "back":
            break

        profiles = _handle_databricks_action(action, profiles, profile_path, profile_name, output_name, output)

        # Refresh output reference
        try:
            output = get_output(profiles, profile_name, output_name)  # type: ignore[assignment]
        except (ProfileNotFoundError, OutputNotFoundError):
            break

    return profiles


def _update_databricks_field(
    profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str, field: str, value: str | None
) -> DbtProfiles:
    """Update a Databricks output field."""
    try:
        profiles = update_output_fields(profiles, profile_name, output_name, {field: value})
        save_profiles(profiles, profile_path)
        typer.echo(f"Updated {field}")
    except (ProfileNotFoundError, OutputNotFoundError, ValueError) as e:
        typer.echo(str(e), err=True)
    return profiles


def _edit_output_loop(profiles: DbtProfiles, profile_path: Path, profile_name: str, output_name: str) -> DbtProfiles:
    """Output editing submenu loop (dispatches to adapter-specific loop).

    Args:
        profiles: Current profiles
        profile_path: Path to save profiles
        profile_name: Name of the profile
        output_name: Name of the output

    Returns:
        Updated profiles
    """
    try:
        output = get_output(profiles, profile_name, output_name)
    except (ProfileNotFoundError, OutputNotFoundError) as e:
        typer.echo(str(e), err=True)
        return profiles

    if isinstance(output, DatabricksOutput):
        return _edit_databricks_output_loop(profiles, profile_path, profile_name, output_name, output)
    else:
        return _edit_duckdb_output_loop(profiles, profile_path, profile_name, output_name, output)  # type: ignore[arg-type]


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
    from brix.modules.dbt.profile.service import get_default_profile_path

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
