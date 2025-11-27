"""Profile management submodule for dbt.

Re-exports public API from submodules.
"""

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
from brix.modules.dbt.profile.models import (
    DatabricksAuthType,
    DatabricksOutput,
    DbtProfiles,
    DuckDbOutput,
    OutputConfig,
    ProfileTarget,
)
from brix.modules.dbt.profile.prompts import run_interactive_edit
from brix.modules.dbt.profile.service import (
    ProfileConfig,
    ProfileExistsError,
    ProfileInitResult,
    get_default_profile_path,
    init_profile,
    load_template,
)

__all__ = [  # noqa: RUF022
    # Models
    "DatabricksAuthType",
    "DatabricksOutput",
    "DbtProfiles",
    "DuckDbOutput",
    "OutputConfig",
    "ProfileTarget",
    # Service
    "ProfileConfig",
    "ProfileExistsError",
    "ProfileInitResult",
    "get_default_profile_path",
    "init_profile",
    "load_template",
    # Editor
    "OutputAlreadyExistsError",
    "OutputNotFoundError",
    "ProfileAlreadyExistsError",
    "ProfileNotFoundError",
    "add_output",
    "add_profile",
    "delete_output",
    "delete_profile",
    "get_output",
    "get_output_names",
    "get_profile_names",
    "load_profiles",
    "save_profiles",
    "update_output",
    "update_output_fields",
    "update_profile_target",
    # Prompts
    "run_interactive_edit",
]
