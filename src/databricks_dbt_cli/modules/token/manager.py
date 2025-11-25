"""Token lifecycle management."""

import asyncio
import os
from datetime import datetime, timezone

from pydantic import BaseModel

from databricks_dbt_cli.modules.auth import AuthMethod, create_databricks_token, get_azure_token, get_credential
from databricks_dbt_cli.modules.dbt import DbtProfile
from databricks_dbt_cli.modules.token.storage import TokenInfo, is_token_expired, load_token_info, save_token_info


class TokenRefreshResult(BaseModel):
    """Result of a token refresh operation."""

    environment: str
    success: bool
    message: str
    expires_at: datetime | None = None
    token_variable: str | None = None


class TokenCheckResult(BaseModel):
    """Result of a token check operation."""

    environment: str
    token_variable: str
    needs_refresh: bool
    expires_at: datetime | None = None
    hours_remaining: float | None = None
    message: str


def check_token(environment: str, profile: DbtProfile) -> TokenCheckResult:
    """Check the status of a token for an environment.

    Args:
        environment: The target environment name.
        profile: The dbt profile configuration.

    Returns:
        TokenCheckResult with the token status.
    """
    target = profile.targets.get(environment)
    if not target:
        return TokenCheckResult(
            environment=environment,
            token_variable="",
            needs_refresh=False,
            message=f"Environment '{environment}' not found in profile",
        )

    if not target.token_env_var:
        return TokenCheckResult(
            environment=environment,
            token_variable="",
            needs_refresh=False,
            message=f"No token env var configured for '{environment}'",
        )

    token_info = load_token_info(target.token_env_var)

    if token_info is None:
        return TokenCheckResult(
            environment=environment,
            token_variable=target.token_env_var,
            needs_refresh=True,
            message="No token info found - token needs to be created",
        )

    expired = is_token_expired(token_info)
    now = datetime.now(timezone.utc)
    expires_at = token_info.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    hours_remaining = (expires_at - now).total_seconds() / 3600

    if expired:
        return TokenCheckResult(
            environment=environment,
            token_variable=target.token_env_var,
            needs_refresh=True,
            expires_at=token_info.expires_at,
            hours_remaining=hours_remaining,
            message="Token has expired",
        )

    return TokenCheckResult(
        environment=environment,
        token_variable=target.token_env_var,
        needs_refresh=False,
        expires_at=token_info.expires_at,
        hours_remaining=hours_remaining,
        message=f"Token valid for {hours_remaining:.1f} more hours",
    )


async def refresh_token(
    environment: str,
    profile: DbtProfile,
    auth_method: AuthMethod = AuthMethod.AUTO,
    force: bool = False,
    lifetime_hours: int = 24,
) -> TokenRefreshResult:
    """Refresh a Databricks token for an environment.

    Args:
        environment: The target environment name.
        profile: The dbt profile configuration.
        auth_method: Azure authentication method to use.
        force: Force refresh even if token is still valid.
        lifetime_hours: Token lifetime in hours.

    Returns:
        TokenRefreshResult with the operation result.
    """
    target = profile.targets.get(environment)
    if not target:
        return TokenRefreshResult(
            environment=environment,
            success=False,
            message=f"Environment '{environment}' not found in profile",
        )

    if not target.token_env_var:
        return TokenRefreshResult(
            environment=environment,
            success=False,
            message=f"No token env var configured for '{environment}'",
        )

    if not force:
        token_info = load_token_info(target.token_env_var)
        if token_info and not is_token_expired(token_info):
            now = datetime.now(timezone.utc)
            expires_at = token_info.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            hours_remaining = (expires_at - now).total_seconds() / 3600
            return TokenRefreshResult(
                environment=environment,
                success=True,
                message=f"Token still valid ({hours_remaining:.1f}h remaining), skipping refresh",
                expires_at=token_info.expires_at,
                token_variable=target.token_env_var,
            )

    try:
        credential = get_credential(auth_method)
        azure_token = get_azure_token(credential)

        workspace_url = target.host
        if not workspace_url.startswith("https://"):
            workspace_url = f"https://{workspace_url}"

        db_token = await create_databricks_token(
            workspace_url=workspace_url,
            azure_token=azure_token.token,
            lifetime_hours=lifetime_hours,
        )

        os.environ[target.token_env_var] = db_token.token_value

        token_info = TokenInfo(
            token_variable=target.token_env_var,
            environment=environment,
            created_at=datetime.now(timezone.utc),
            expires_at=db_token.expires_at,
            workspace_url=workspace_url,
        )
        save_token_info(token_info)

        return TokenRefreshResult(
            environment=environment,
            success=True,
            message=f"Token refreshed (expires {db_token.expires_at.strftime('%Y-%m-%d %H:%M UTC')})",
            expires_at=db_token.expires_at,
            token_variable=target.token_env_var,
        )

    except Exception as e:
        return TokenRefreshResult(
            environment=environment,
            success=False,
            message=f"Failed to refresh token: {e}",
            token_variable=target.token_env_var,
        )


async def refresh_all_tokens(
    profile: DbtProfile,
    environments: list[str] | None = None,
    auth_method: AuthMethod = AuthMethod.AUTO,
    force: bool = False,
    lifetime_hours: int = 24,
) -> list[TokenRefreshResult]:
    """Refresh tokens for multiple environments concurrently.

    Args:
        profile: The dbt profile configuration.
        environments: List of environments to refresh. If None, refreshes all.
        auth_method: Azure authentication method to use.
        force: Force refresh even if tokens are still valid.
        lifetime_hours: Token lifetime in hours.

    Returns:
        List of TokenRefreshResult for each environment.
    """
    if environments is None:
        environments = list(profile.targets.keys())

    tasks = [refresh_token(env, profile, auth_method, force, lifetime_hours) for env in environments]

    return await asyncio.gather(*tasks)
