"""Databricks token creation via REST API."""

from datetime import datetime, timezone
from typing import NamedTuple

import httpx

from databricks_dbt_cli.utils.exceptions import DatabricksApiError


class DatabricksToken(NamedTuple):
    """Result of creating a Databricks token."""

    token_value: str
    token_id: str
    expires_at: datetime


async def create_databricks_token(
    workspace_url: str,
    azure_token: str,
    lifetime_hours: int = 24,
    comment: str | None = None,
) -> DatabricksToken:
    """Create a new Databricks personal access token.

    Args:
        workspace_url: The Databricks workspace URL (e.g., https://adb-xxx.azuredatabricks.net).
        azure_token: The Azure AD access token for authentication.
        lifetime_hours: Token lifetime in hours (1-24).
        comment: Optional comment for the token.

    Returns:
        A DatabricksToken with the token value and expiration.

    Raises:
        DatabricksApiError: If the API call fails.
    """
    if comment is None:
        comment = f"ddbt token created on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"

    url = f"{workspace_url.rstrip('/')}/api/2.0/token/create"
    lifetime_seconds = lifetime_hours * 3600

    headers = {
        "Authorization": f"Bearer {azure_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "comment": comment,
        "lifetime_seconds": lifetime_seconds,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            msg = f"Databricks API error ({e.response.status_code}): {e.response.text}"
            raise DatabricksApiError(msg) from e
        except httpx.RequestError as e:
            msg = f"Failed to connect to Databricks: {e}"
            raise DatabricksApiError(msg) from e

    data = response.json()

    token_value = data.get("token_value")
    token_id = data.get("token_info", {}).get("token_id", "")

    if not token_value:
        msg = "Databricks API did not return a token"
        raise DatabricksApiError(msg)

    expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    expires_at = expires_at.replace(
        hour=expires_at.hour,
        minute=expires_at.minute,
        second=expires_at.second,
    )
    from datetime import timedelta

    expires_at = expires_at + timedelta(hours=lifetime_hours)

    return DatabricksToken(
        token_value=token_value,
        token_id=token_id,
        expires_at=expires_at,
    )
