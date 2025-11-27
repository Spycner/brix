"""Tests for version_check module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import respx

from brix import version_check
from brix.version_check import (
    CHECK_INTERVAL,
    GitHubRelease,
    VersionCache,
    _fetch_and_cache_latest,
    _load_cache,
    _should_refresh,
    check_for_updates,
)


class TestVersionCache:
    def test_valid_cache(self):
        cache = VersionCache(last_check=datetime.now(timezone.utc), latest_version="1.0.0")
        assert cache.latest_version == "1.0.0"

    def test_serialization_roundtrip(self):
        cache = VersionCache(last_check=datetime.now(timezone.utc), latest_version="2.0.0")
        json_str = cache.model_dump_json()
        loaded = VersionCache.model_validate_json(json_str)
        assert loaded.latest_version == cache.latest_version


class TestGitHubRelease:
    def test_valid_release(self):
        release = GitHubRelease(tag_name="v1.2.3")
        assert release.tag_name == "v1.2.3"

    def test_from_api_response(self):
        api_response = {"tag_name": "v1.0.0", "name": "Release 1.0.0", "other_field": "ignored"}
        release = GitHubRelease.model_validate(api_response)
        assert release.tag_name == "v1.0.0"


class TestLoadCache:
    def test_no_cache_file(self, temp_cache_dir):
        assert _load_cache() is None

    def test_valid_cache_file(self, temp_cache_dir):
        cache = VersionCache(last_check=datetime.now(timezone.utc), latest_version="1.0.0")
        temp_cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_cache_dir.write_text(cache.model_dump_json())
        loaded = _load_cache()
        assert loaded is not None
        assert loaded.latest_version == "1.0.0"

    def test_invalid_cache_file(self, temp_cache_dir):
        temp_cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_cache_dir.write_text("not valid json")
        assert _load_cache() is None

    def test_malformed_cache_file(self, temp_cache_dir):
        temp_cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_cache_dir.write_text('{"wrong_field": "value"}')
        assert _load_cache() is None


class TestShouldRefresh:
    def test_no_cache(self):
        assert _should_refresh(None) is True

    def test_fresh_cache(self):
        cache = VersionCache(last_check=datetime.now(timezone.utc), latest_version="1.0.0")
        assert _should_refresh(cache) is False

    def test_stale_cache(self):
        old_time = datetime.now(timezone.utc) - CHECK_INTERVAL - timedelta(hours=1)
        cache = VersionCache(last_check=old_time, latest_version="1.0.0")
        assert _should_refresh(cache) is True

    def test_cache_at_boundary(self):
        boundary_time = datetime.now(timezone.utc) - CHECK_INTERVAL + timedelta(minutes=1)
        cache = VersionCache(last_check=boundary_time, latest_version="1.0.0")
        assert _should_refresh(cache) is False


class TestFetchAndCacheLatest:
    @respx.mock
    def test_successful_fetch(self, temp_cache_dir):
        respx.get("https://api.github.com/repos/Spycner/brix/releases/latest").mock(
            return_value=httpx.Response(200, json={"tag_name": "v2.0.0"})
        )
        _fetch_and_cache_latest()
        cache = _load_cache()
        assert cache is not None
        assert cache.latest_version == "2.0.0"

    @respx.mock
    def test_strips_v_prefix(self, temp_cache_dir):
        respx.get("https://api.github.com/repos/Spycner/brix/releases/latest").mock(
            return_value=httpx.Response(200, json={"tag_name": "v1.2.3"})
        )
        _fetch_and_cache_latest()
        cache = _load_cache()
        assert cache is not None
        assert cache.latest_version == "1.2.3"

    @respx.mock
    def test_http_error(self, temp_cache_dir):
        respx.get("https://api.github.com/repos/Spycner/brix/releases/latest").mock(return_value=httpx.Response(404))
        _fetch_and_cache_latest()
        assert _load_cache() is None

    @respx.mock
    def test_invalid_response(self, temp_cache_dir):
        respx.get("https://api.github.com/repos/Spycner/brix/releases/latest").mock(
            return_value=httpx.Response(200, json={"no_tag": "here"})
        )
        _fetch_and_cache_latest()
        assert _load_cache() is None

    @respx.mock
    def test_network_error(self, temp_cache_dir):
        respx.get("https://api.github.com/repos/Spycner/brix/releases/latest").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )
        _fetch_and_cache_latest()  # Should not raise
        assert _load_cache() is None


class TestCheckForUpdates:
    def test_no_cache_returns_none(self, temp_cache_dir):
        with patch.object(version_check, "_fetch_and_cache_latest"):
            result = check_for_updates()
        assert result is None

    def test_update_available(self, temp_cache_dir, monkeypatch):
        monkeypatch.setattr(version_check, "__version__", "1.0.0")
        cache = VersionCache(last_check=datetime.now(timezone.utc), latest_version="2.0.0")
        temp_cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_cache_dir.write_text(cache.model_dump_json())
        result = check_for_updates()
        assert result == "2.0.0"

    def test_no_update_needed(self, temp_cache_dir, monkeypatch):
        monkeypatch.setattr(version_check, "__version__", "1.0.0")
        cache = VersionCache(last_check=datetime.now(timezone.utc), latest_version="1.0.0")
        temp_cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_cache_dir.write_text(cache.model_dump_json())
        result = check_for_updates()
        assert result is None

    def test_spawns_background_thread_when_stale(self, temp_cache_dir, monkeypatch):
        monkeypatch.setattr(version_check, "__version__", "1.0.0")
        old_time = datetime.now(timezone.utc) - CHECK_INTERVAL - timedelta(hours=1)
        cache = VersionCache(last_check=old_time, latest_version="1.0.0")
        temp_cache_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_cache_dir.write_text(cache.model_dump_json())

        with patch.object(version_check, "_fetch_and_cache_latest") as mock_fetch:
            check_for_updates()
            # Give thread a moment to start
            import time

            time.sleep(0.1)
            mock_fetch.assert_called_once()
