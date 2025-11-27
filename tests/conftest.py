"""Shared pytest fixtures for brix tests."""

import pytest

from brix import version_check
from brix.utils.logging import reset_logger


@pytest.fixture(autouse=True)
def reset_logger_fixture():
    """Reset logger before and after each test."""
    reset_logger()
    yield
    reset_logger()


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Use temporary directory for version check cache."""
    cache_dir = tmp_path / ".cache" / "brix"
    cache_file = cache_dir / "version_check.json"
    monkeypatch.setattr(version_check, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(version_check, "CACHE_FILE", cache_file)
    return cache_file
