"""Custom exceptions for databricks-dbt-cli."""


class CliError(Exception):
    """Base exception for all CLI errors."""


class ProfileNotFoundError(CliError):
    """Raised when the dbt profile file or profile name is not found."""


class ProfileValidationError(CliError):
    """Raised when the dbt profile configuration is invalid."""


class AzureAuthError(CliError):
    """Raised when Azure authentication fails."""


class DatabricksApiError(CliError):
    """Raised when Databricks API calls fail."""


class TokenStorageError(CliError):
    """Raised when token storage operations fail."""
