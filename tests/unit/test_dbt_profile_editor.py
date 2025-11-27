"""Tests for dbt profile editor CRUD operations."""

import pytest
from typer.testing import CliRunner

from brix.main import app
from brix.modules.dbt.profile import (
    DbtProfiles,
    DuckDbOutput,
    OutputAlreadyExistsError,
    OutputNotFoundError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    add_output,
    add_profile,
    delete_output,
    delete_profile,
    get_output,
    get_output_names,
    get_profile_names,
    load_profiles,
    save_profiles,
    update_output,
    update_profile_target,
)

runner = CliRunner()


@pytest.fixture
def sample_profiles():
    """Create sample profiles for testing."""
    yaml_content = """
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: dev.duckdb
      threads: 1
    prod:
      type: duckdb
      path: prod.duckdb
      threads: 4
other:
  target: staging
  outputs:
    staging:
      type: duckdb
      path: staging.duckdb
      threads: 2
"""
    return DbtProfiles.from_yaml(yaml_content)


@pytest.fixture
def profiles_file(tmp_path, sample_profiles):
    """Create a profiles file for testing."""
    profile_path = tmp_path / "profiles.yml"
    profile_path.write_text(sample_profiles.to_yaml())
    return profile_path


class TestLoadSaveProfiles:
    """Tests for load/save operations."""

    def test_load_profiles(self, profiles_file):
        profiles = load_profiles(profiles_file)
        assert "default" in profiles.root
        assert "other" in profiles.root

    def test_load_profiles_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_profiles(tmp_path / "nonexistent.yml")

    def test_save_profiles(self, tmp_path, sample_profiles):
        profile_path = tmp_path / "test_profiles.yml"
        save_profiles(sample_profiles, profile_path)

        assert profile_path.exists()
        loaded = load_profiles(profile_path)
        assert "default" in loaded.root

    def test_save_profiles_creates_parent_dirs(self, tmp_path, sample_profiles):
        profile_path = tmp_path / "deep" / "nested" / "profiles.yml"
        save_profiles(sample_profiles, profile_path)

        assert profile_path.exists()


class TestGetNames:
    """Tests for getting profile and output names."""

    def test_get_profile_names(self, sample_profiles):
        names = get_profile_names(sample_profiles)
        assert set(names) == {"default", "other"}

    def test_get_output_names(self, sample_profiles):
        names = get_output_names(sample_profiles, "default")
        assert set(names) == {"dev", "prod"}

    def test_get_output_names_profile_not_found(self, sample_profiles):
        with pytest.raises(ProfileNotFoundError):
            get_output_names(sample_profiles, "nonexistent")


class TestAddProfile:
    """Tests for adding profiles."""

    def test_add_profile(self, sample_profiles):
        output_config = DuckDbOutput(type="duckdb", path=":memory:", threads=1)
        updated = add_profile(sample_profiles, "new_profile", "dev", "dev", output_config)

        assert "new_profile" in updated.root
        assert updated.root["new_profile"].target == "dev"
        assert "dev" in updated.root["new_profile"].outputs

    def test_add_profile_already_exists(self, sample_profiles):
        output_config = DuckDbOutput(type="duckdb", path=":memory:", threads=1)
        with pytest.raises(ProfileAlreadyExistsError, match="already exists"):
            add_profile(sample_profiles, "default", "dev", "dev", output_config)


class TestUpdateProfile:
    """Tests for updating profiles."""

    def test_update_profile_target(self, sample_profiles):
        updated = update_profile_target(sample_profiles, "default", "prod")
        assert updated.root["default"].target == "prod"

    def test_update_profile_not_found(self, sample_profiles):
        with pytest.raises(ProfileNotFoundError):
            update_profile_target(sample_profiles, "nonexistent", "prod")


class TestDeleteProfile:
    """Tests for deleting profiles."""

    def test_delete_profile(self, sample_profiles):
        updated = delete_profile(sample_profiles, "other")
        assert "other" not in updated.root
        assert "default" in updated.root

    def test_delete_profile_not_found(self, sample_profiles):
        with pytest.raises(ProfileNotFoundError):
            delete_profile(sample_profiles, "nonexistent")


class TestAddOutput:
    """Tests for adding outputs."""

    def test_add_output(self, sample_profiles):
        output_config = DuckDbOutput(type="duckdb", path="new.duckdb", threads=2)
        updated = add_output(sample_profiles, "default", "new_output", output_config)

        assert "new_output" in updated.root["default"].outputs
        assert updated.root["default"].outputs["new_output"].path == "new.duckdb"

    def test_add_output_profile_not_found(self, sample_profiles):
        output_config = DuckDbOutput(type="duckdb", path=":memory:", threads=1)
        with pytest.raises(ProfileNotFoundError):
            add_output(sample_profiles, "nonexistent", "output", output_config)

    def test_add_output_already_exists(self, sample_profiles):
        output_config = DuckDbOutput(type="duckdb", path=":memory:", threads=1)
        with pytest.raises(OutputAlreadyExistsError):
            add_output(sample_profiles, "default", "dev", output_config)


class TestUpdateOutput:
    """Tests for updating outputs."""

    def test_update_output_path(self, sample_profiles):
        updated = update_output(sample_profiles, "default", "dev", path="new_path.duckdb")
        assert updated.root["default"].outputs["dev"].path == "new_path.duckdb"

    def test_update_output_threads(self, sample_profiles):
        updated = update_output(sample_profiles, "default", "dev", threads=8)
        assert updated.root["default"].outputs["dev"].threads == 8

    def test_update_output_both(self, sample_profiles):
        updated = update_output(sample_profiles, "default", "dev", path="both.duckdb", threads=16)
        assert updated.root["default"].outputs["dev"].path == "both.duckdb"
        assert updated.root["default"].outputs["dev"].threads == 16

    def test_update_output_profile_not_found(self, sample_profiles):
        with pytest.raises(ProfileNotFoundError):
            update_output(sample_profiles, "nonexistent", "dev", path="x")

    def test_update_output_not_found(self, sample_profiles):
        with pytest.raises(OutputNotFoundError):
            update_output(sample_profiles, "default", "nonexistent", path="x")

    @pytest.mark.parametrize("invalid_threads", [0, -1, -10])
    def test_update_output_invalid_threads(self, sample_profiles, invalid_threads):
        with pytest.raises(ValueError, match="threads must be a positive integer"):
            update_output(sample_profiles, "default", "dev", threads=invalid_threads)


class TestDeleteOutput:
    """Tests for deleting outputs."""

    def test_delete_output(self, sample_profiles):
        updated = delete_output(sample_profiles, "default", "prod")
        assert "prod" not in updated.root["default"].outputs
        assert "dev" in updated.root["default"].outputs

    def test_delete_output_profile_not_found(self, sample_profiles):
        with pytest.raises(ProfileNotFoundError):
            delete_output(sample_profiles, "nonexistent", "dev")

    def test_delete_output_not_found(self, sample_profiles):
        with pytest.raises(OutputNotFoundError):
            delete_output(sample_profiles, "default", "nonexistent")

    def test_delete_last_output_raises(self, sample_profiles):
        # other profile only has one output
        with pytest.raises(ValueError, match="Cannot delete last output"):
            delete_output(sample_profiles, "other", "staging")


class TestGetOutput:
    """Tests for getting output configuration."""

    def test_get_output(self, sample_profiles):
        output = get_output(sample_profiles, "default", "dev")
        assert output.path == "dev.duckdb"
        assert output.threads == 1

    def test_get_output_profile_not_found(self, sample_profiles):
        with pytest.raises(ProfileNotFoundError):
            get_output(sample_profiles, "nonexistent", "dev")

    def test_get_output_not_found(self, sample_profiles):
        with pytest.raises(OutputNotFoundError):
            get_output(sample_profiles, "default", "nonexistent")


class TestEditCommand:
    """Tests for the edit CLI command."""

    def test_edit_help(self):
        result = runner.invoke(app, ["dbt", "profile", "edit", "--help"])
        assert result.exit_code == 0
        assert "action" in result.output.lower()
        assert "add-profile" in result.output

    def test_add_profile_cli(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"

        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profile_path),
                "--action",
                "add-profile",
                "--profile",
                "myproj",
                "--target",
                "dev",
                "--path",
                "./data.duckdb",
            ],
        )

        assert result.exit_code == 0
        assert "Added profile 'myproj'" in result.output

        # Verify file
        profiles = load_profiles(profile_path)
        assert "myproj" in profiles.root
        assert profiles.root["myproj"].target == "dev"

    def test_add_profile_cli_missing_profile(self, tmp_path):
        profile_path = tmp_path / "profiles.yml"

        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profile_path),
                "--action",
                "add-profile",
            ],
        )

        assert result.exit_code == 1
        assert "--profile is required" in result.output

    def test_edit_profile_cli(self, profiles_file):
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "edit-profile",
                "--profile",
                "default",
                "--target",
                "production",
            ],
        )

        assert result.exit_code == 0
        assert "Updated profile" in result.output

        profiles = load_profiles(profiles_file)
        assert profiles.root["default"].target == "production"

    def test_delete_profile_cli_with_force(self, profiles_file):
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "delete-profile",
                "--profile",
                "other",
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert "Deleted profile" in result.output

        profiles = load_profiles(profiles_file)
        assert "other" not in profiles.root

    def test_add_output_cli(self, profiles_file):
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "add-output",
                "--profile",
                "default",
                "--output",
                "test",
                "--path",
                "./test.duckdb",
                "--threads",
                "2",
            ],
        )

        assert result.exit_code == 0
        assert "Added output" in result.output

        profiles = load_profiles(profiles_file)
        assert "test" in profiles.root["default"].outputs

    def test_edit_output_cli(self, profiles_file):
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "edit-output",
                "--profile",
                "default",
                "--output",
                "dev",
                "--path",
                "./updated.duckdb",
            ],
        )

        assert result.exit_code == 0
        assert "Updated output" in result.output

        profiles = load_profiles(profiles_file)
        assert profiles.root["default"].outputs["dev"].path == "./updated.duckdb"

    def test_delete_output_cli_with_force(self, profiles_file):
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "delete-output",
                "--profile",
                "default",
                "--output",
                "prod",
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert "Deleted output" in result.output

        profiles = load_profiles(profiles_file)
        assert "prod" not in profiles.root["default"].outputs

    def test_profile_not_found_error(self, profiles_file):
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "edit-profile",
                "--profile",
                "nonexistent",
                "--target",
                "x",
            ],
        )

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_delete_target_output_with_fallback(self, profiles_file):
        """Test deleting the current target output with --target to specify fallback."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "delete-output",
                "--profile",
                "default",
                "--output",
                "dev",  # dev is the current target
                "--target",
                "prod",  # fallback to prod
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert "Changed target to 'prod'" in result.output
        assert "Deleted output 'dev'" in result.output

        profiles = load_profiles(profiles_file)
        assert "dev" not in profiles.root["default"].outputs
        assert profiles.root["default"].target == "prod"

    def test_delete_target_output_force_without_fallback_fails(self, profiles_file):
        """Test that deleting target output with --force but no --target fails."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "delete-output",
                "--profile",
                "default",
                "--output",
                "dev",  # dev is the current target
                "--force",
            ],
        )

        assert result.exit_code == 1
        assert "Cannot delete target output" in result.output
        assert "--target for fallback" in result.output

    def test_delete_target_output_invalid_fallback_fails(self, profiles_file):
        """Test that specifying an invalid fallback target fails."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "delete-output",
                "--profile",
                "default",
                "--output",
                "dev",
                "--target",
                "nonexistent",
                "--force",
            ],
        )

        assert result.exit_code == 1
        assert "not a valid output" in result.output

    def test_delete_only_target_output_fails(self, profiles_file):
        """Test that deleting the only output (which is also the target) fails."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "profile",
                "edit",
                "-p",
                str(profiles_file),
                "--action",
                "delete-output",
                "--profile",
                "other",  # has only one output: staging
                "--output",
                "staging",
                "--force",
            ],
        )

        assert result.exit_code == 1
        assert "no other outputs exist" in result.output
