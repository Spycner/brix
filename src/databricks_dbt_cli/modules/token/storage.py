"""Token metadata storage and persistence."""

import json
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import BaseModel

from databricks_dbt_cli.utils.exceptions import TokenStorageError

APP_NAME = "ddbt"


class TokenInfo(BaseModel):
    """Metadata about a stored Databricks token."""

    token_variable: str
    environment: str
    created_at: datetime
    expires_at: datetime
    workspace_url: str


def get_token_storage_path() -> Path:
    """Get the platform-specific path for token storage.

    Returns:
        Path to the token storage directory:
        - Linux: ~/.local/share/ddbt/tokens/
        - macOS: ~/Library/Application Support/ddbt/tokens/
        - Windows: C:/Users/<user>/AppData/Local/ddbt/tokens/
    """
    return Path(user_data_dir(APP_NAME)) / "tokens"


def save_token_info(info: TokenInfo) -> None:
    """Save token metadata to storage.

    Args:
        info: The token metadata to save.

    Raises:
        TokenStorageError: If saving fails.
    """
    try:
        storage_path = get_token_storage_path()
        storage_path.mkdir(parents=True, exist_ok=True)

        file_path = storage_path / f"{info.token_variable}.json"
        data = info.model_dump(mode="json")
        file_path.write_text(json.dumps(data, indent=2, default=str))
    except OSError as e:
        msg = f"Failed to save token info: {e}"
        raise TokenStorageError(msg) from e


def load_token_info(token_variable: str) -> TokenInfo | None:
    """Load token metadata from storage.

    Args:
        token_variable: The environment variable name for the token.

    Returns:
        The TokenInfo if found, None otherwise.
    """
    file_path = get_token_storage_path() / f"{token_variable}.json"

    if not file_path.exists():
        return None

    try:
        data = json.loads(file_path.read_text())
        return TokenInfo.model_validate(data)
    except (json.JSONDecodeError, OSError):
        return None


def is_token_expired(info: TokenInfo) -> bool:
    """Check if a token has expired.

    Args:
        info: The token metadata to check.

    Returns:
        True if the token has expired, False otherwise.
    """
    now = datetime.now(timezone.utc)
    expires_at = info.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return now >= expires_at


def get_hours_remaining(info: TokenInfo) -> float:
    """Get hours remaining until token expiration.

    Args:
        info: The token metadata to check.

    Returns:
        Hours remaining (negative if expired).
    """
    now = datetime.now(timezone.utc)
    expires_at = info.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - now
    return delta.total_seconds() / 3600
