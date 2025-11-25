"""Azure authentication credential management."""

from enum import Enum

from azure.core.credentials import AccessToken, TokenCredential
from azure.identity import (
    AzureCliCredential,
    ChainedTokenCredential,
    EnvironmentCredential,
    InteractiveBrowserCredential,
    ManagedIdentityCredential,
)

from databricks_dbt_cli.utils.exceptions import AzureAuthError

DATABRICKS_RESOURCE_ID = "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d"  #!TODO: make configurable
DATABRICKS_SCOPE = f"{DATABRICKS_RESOURCE_ID}/.default"


class AuthMethod(str, Enum):
    """Available Azure authentication methods."""

    AUTO = "auto"
    CLI = "cli"
    BROWSER = "browser"
    ENVIRONMENT = "environment"
    MANAGED_IDENTITY = "managed-identity"


def get_credential(method: AuthMethod = AuthMethod.AUTO) -> TokenCredential:
    """Get Azure credential based on specified method.

    Args:
        method: The authentication method to use.

    Returns:
        A TokenCredential instance for the specified method.

    Raises:
        AzureAuthError: If an invalid auth method is specified.
    """
    if method == AuthMethod.CLI:
        return AzureCliCredential()
    if method == AuthMethod.BROWSER:
        return InteractiveBrowserCredential()
    if method == AuthMethod.ENVIRONMENT:
        return EnvironmentCredential()
    if method == AuthMethod.MANAGED_IDENTITY:
        return ManagedIdentityCredential()
    if method == AuthMethod.AUTO:
        return ChainedTokenCredential(
            EnvironmentCredential(),
            ManagedIdentityCredential(),
            AzureCliCredential(),
            InteractiveBrowserCredential(),
        )
    msg = f"Invalid auth method: {method}"
    raise AzureAuthError(msg)


def get_azure_token(credential: TokenCredential) -> AccessToken:
    """Get an Azure access token for Databricks.

    Args:
        credential: The Azure credential to use.

    Returns:
        An AccessToken for Databricks API access.

    Raises:
        AzureAuthError: If token acquisition fails.
    """
    try:
        return credential.get_token(DATABRICKS_SCOPE)
    except Exception as e:
        msg = f"Failed to acquire Azure token: {e}"
        raise AzureAuthError(msg) from e
