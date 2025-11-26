"""Version update checker using GitHub releases."""

import threading
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, ValidationError

from brix import __version__
from brix.utils.logging import get_logger

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
    logger = get_logger()
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    logger.debug("Fetching latest version from %s", url)
    try:
        resp = httpx.get(url, timeout=5.0, follow_redirects=True)
        resp.raise_for_status()
        release = GitHubRelease.model_validate(resp.json())
        latest = release.tag_name.lstrip("v")
        logger.debug("Latest version from GitHub: %s", latest)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = VersionCache(last_check=datetime.now(), latest_version=latest)
        CACHE_FILE.write_text(cache.model_dump_json())
        logger.debug("Version cache updated at %s", CACHE_FILE)
    except (httpx.HTTPError, ValidationError, OSError) as e:
        logger.debug("Failed to fetch/cache version: %s", e)


def _load_cache() -> VersionCache | None:
    """Load cached version check result."""
    logger = get_logger()
    if not CACHE_FILE.exists():
        logger.debug("Version cache file not found: %s", CACHE_FILE)
        return None
    try:
        cache = VersionCache.model_validate_json(CACHE_FILE.read_text())
        logger.debug("Loaded version cache: %s (checked %s)", cache.latest_version, cache.last_check)
        return cache
    except (ValidationError, OSError) as e:
        logger.debug("Failed to load version cache: %s", e)
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
    logger = get_logger()
    cache = _load_cache()

    # Spawn background refresh if needed (non-blocking)
    if _should_refresh(cache):
        logger.debug("Version cache stale, spawning background refresh")
        thread = threading.Thread(target=_fetch_and_cache_latest, daemon=True)
        thread.start()

    # Return cached result immediately (or None if no cache yet)
    if cache and cache.latest_version != __version__:
        logger.debug("Update available: %s -> %s", __version__, cache.latest_version)
        return cache.latest_version
    return None
