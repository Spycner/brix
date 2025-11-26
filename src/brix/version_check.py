"""Version update checker using GitHub releases."""

import threading
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, ValidationError

from brix import __version__

GITHUB_REPO = "Spycner/brix"
CACHE_DIR = Path.home() / ".cache" / "brix"
CACHE_FILE = CACHE_DIR / "version_check.json"
CHECK_INTERVAL = timedelta(hours=24)


class VersionCache(BaseModel):
    """Cached version check result."""

    last_check: datetime
    latest_version: str


class GitHubRelease(BaseModel):
    """GitHub release response (subset of fields)."""

    tag_name: str


def _fetch_and_cache_latest() -> None:
    """Fetch latest version from GitHub and cache it (runs in background thread)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        resp = httpx.get(url, timeout=5.0, follow_redirects=True)
        resp.raise_for_status()
        release = GitHubRelease.model_validate(resp.json())
        latest = release.tag_name.lstrip("v")
        # Save to cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = VersionCache(last_check=datetime.now(), latest_version=latest)
        CACHE_FILE.write_text(cache.model_dump_json())
    except (httpx.HTTPError, ValidationError, OSError):
        pass  # Silent failure


def _load_cache() -> VersionCache | None:
    """Load cached version check result."""
    if not CACHE_FILE.exists():
        return None
    try:
        return VersionCache.model_validate_json(CACHE_FILE.read_text())
    except (ValidationError, OSError):
        return None


def _should_refresh(cache: VersionCache | None) -> bool:
    """Check if cache is stale and needs refresh."""
    if cache is None:
        return True
    return datetime.now() - cache.last_check > CHECK_INTERVAL


def check_for_updates() -> str | None:
    """Check for updates (non-blocking).

    Returns latest version if update available (from cache).
    Spawns background thread to refresh cache if stale.
    """
    cache = _load_cache()

    # Spawn background refresh if needed (non-blocking)
    if _should_refresh(cache):
        thread = threading.Thread(target=_fetch_and_cache_latest, daemon=True)
        thread.start()

    # Return cached result immediately (or None if no cache yet)
    if cache and cache.latest_version != __version__:
        return cache.latest_version
    return None
