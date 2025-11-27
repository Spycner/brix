"""Tests for dbt profile commands and models."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from brix.main import app
from brix.modules.dbt.profile import (
    ProfileExistsError,
    get_default_profile_path,
    init_profile,
    load_template,
)
from brix.modules.dbt.profile_models import DbtProfiles, DuckDbOutput

runner = CliRunner()


class TestDbtProfiles:
    """Tests for DbtProfiles pydantic model."""

    def test_parse_simple_duckdb_profile(self):
        yaml_content = """
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: dev.duckdb
      threads: 1
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        assert "default" in profiles
        assert profiles["default"].target == "dev"
        assert "dev" in profiles["default"].outputs
        output = profiles["default"].outputs["dev"]
        assert isinstance(output, DuckDbOutput)
        assert output.path == "dev.duckdb"
        assert output.threads == 1

    def test_parse_invalid_yaml_raises(self):
        with pytest.raises(ValueError, match="Invalid YAML"):
            DbtProfiles.from_yaml("{ invalid yaml")

    def test_parse_non_mapping_raises(self):
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            DbtProfiles.from_yaml("- list item")

    def test_to_yaml_roundtrip(self):
        yaml_content = """
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: test.duckdb
      threads: 2
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output_yaml = profiles.to_yaml()
        # Parse it again to verify roundtrip
        profiles2 = DbtProfiles.from_yaml(output_yaml)
        assert profiles2["default"].target == "dev"
        assert profiles2["default"].outputs["dev"].path == "test.duckdb"


class TestLoadTemplate:
    """Tests for template loading and validation."""

    def test_load_default_template(self):
        content, profiles = load_template()
        assert content  # Not empty
        assert "default" in profiles
        assert profiles["default"].target == "dev"

    def test_load_nonexistent_template_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent.yml")


class TestGetDefaultProfilePath:
    """Tests for profile path resolution."""

    def test_default_path_is_home_dbt(self):
        with patch.dict("os.environ", {}, clear=True):
            # Clear any BRIX_DBT_PROFILE_PATH env var
            path = get_default_profile_path()
            assert path == Path.home() / ".dbt" / "profiles.yml"

    def test_env_var_overrides_default(self, tmp_path, monkeypatch):
        custom_path = tmp_path / "custom" / "profiles.yml"
        monkeypatch.setenv("BRIX_DBT_PROFILE_PATH", str(custom_path))
        path = get_default_profile_path()
        assert path == custom_path


class TestInitProfile:
    """Tests for profile initialization."""

    def test_init_creates_profile(self, tmp_path):
        profile_path = tmp_path / ".dbt" / "profiles.yml"
        result = init_profile(profile_path=profile_path)

        assert result.success
        assert result.action == "created"
        assert profile_path.exists()
        # Verify content is valid
        profiles = DbtProfiles.from_file(profile_path)
        assert "default" in profiles

    def test_init_creates_parent_directories(self, tmp_path):
        profile_path = tmp_path / "deep" / "nested" / "dir" / "profiles.yml"
        result = init_profile(profile_path=profile_path)

        assert result.success
        assert profile_path.exists()

    def test_init_fails_if_exists(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"
        profile_path.write_text("existing content")

        with pytest.raises(ProfileExistsError, match="already exists"):
            init_profile(profile_path=profile_path)

    def test_init_force_overwrites(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"
        profile_path.write_text("old content")

        result = init_profile(profile_path=profile_path, force=True)

        assert result.success
        assert result.action == "overwritten"
        # Verify new content
        content = profile_path.read_text()
        assert "duckdb" in content


class TestProfileCommand:
    """Tests for the profile CLI commands."""

    def test_profile_help(self):
        result = runner.invoke(app, ["dbt", "profile", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "show" in result.output

    def test_profile_init_help(self):
        result = runner.invoke(app, ["dbt", "profile", "init", "--help"])
        assert result.exit_code == 0
        assert "--profile-path" in result.output
        assert "--force" in result.output

    def test_profile_init_creates_file(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"
        result = runner.invoke(app, ["dbt", "profile", "init", "-p", str(profile_path)])

        assert result.exit_code == 0
        assert "created" in result.output.lower()
        assert profile_path.exists()

    def test_profile_init_fails_if_exists(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"
        profile_path.write_text("existing")

        result = runner.invoke(app, ["dbt", "profile", "init", "-p", str(profile_path)])

        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_profile_init_force_overwrites(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"
        profile_path.write_text("old")

        result = runner.invoke(app, ["dbt", "profile", "init", "-p", str(profile_path), "--force"])

        assert result.exit_code == 0
        assert "overwritten" in result.output.lower()

    def test_profile_show(self, tmp_path, monkeypatch):
        # Create a profile file
        profile_path = tmp_path / "profiles.yml"
        profile_path.write_text("test: content")
        monkeypatch.setenv("BRIX_DBT_PROFILE_PATH", str(profile_path))

        result = runner.invoke(app, ["dbt", "profile", "show"])

        assert result.exit_code == 0
        assert "Exists: True" in result.output
        assert "test: content" in result.output

    def test_profile_show_not_exists(self, tmp_path, monkeypatch):
        profile_path = tmp_path / "nonexistent" / "profiles.yml"
        monkeypatch.setenv("BRIX_DBT_PROFILE_PATH", str(profile_path))

        result = runner.invoke(app, ["dbt", "profile", "show"])

        assert result.exit_code == 0
        assert "Exists: False" in result.output
