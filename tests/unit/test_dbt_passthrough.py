"""Tests for dbt passthrough command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

import brix.commands.dbt as dbt_command_module
import brix.modules.dbt.passthrough as passthrough_module
from brix.main import app
from brix.modules.dbt import CachedPathNotFoundError, load_project_cache, run_dbt, save_project_cache

runner = CliRunner()


class TestRunDbt:
    def test_forwards_arguments_to_subprocess(self):
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)
            exit_code = run_dbt(["run", "--select", "my_model"])
            mock_subprocess.run.assert_called_once_with(["dbt", "run", "--select", "my_model"], cwd=None)
            assert exit_code == 0

    def test_returns_exit_code_from_dbt(self):
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=1)
            exit_code = run_dbt(["run"])
            assert exit_code == 1

    def test_empty_args(self):
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)
            exit_code = run_dbt([])
            mock_subprocess.run.assert_called_once_with(["dbt"], cwd=None)
            assert exit_code == 0

    def test_with_project_path(self, tmp_path: Path):
        """Test run_dbt uses project_path as cwd."""
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)
            exit_code = run_dbt(["run"], project_path=tmp_path)
            mock_subprocess.run.assert_called_once_with(["dbt", "run"], cwd=tmp_path.resolve())
            assert exit_code == 0

    def test_with_nonexistent_project_path(self):
        """Test run_dbt returns error for nonexistent path."""
        nonexistent = Path("/nonexistent/path/that/does/not/exist")
        exit_code = run_dbt(["run"], project_path=nonexistent)
        assert exit_code == 1

    def test_with_file_as_project_path(self, tmp_path: Path):
        """Test run_dbt returns error when project_path is a file."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.touch()
        exit_code = run_dbt(["run"], project_path=file_path)
        assert exit_code == 1


class TestProjectPathCache:
    def test_save_and_load_cache(self, tmp_path: Path, monkeypatch: MagicMock):
        """Test saving and loading project path cache."""
        cache_dir = tmp_path / ".cache" / "brix"
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        save_project_cache(project_dir)
        loaded = load_project_cache()

        assert loaded == project_dir.resolve()

    def test_load_cache_nonexistent_path_raises(self, tmp_path: Path, monkeypatch: MagicMock):
        """Test loading cache raises CachedPathNotFoundError when cached path doesn't exist."""
        cache_dir = tmp_path / ".cache" / "brix"
        cache_dir.mkdir(parents=True)
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        save_project_cache(project_dir)

        # Delete the project directory
        project_dir.rmdir()

        import pytest

        with pytest.raises(CachedPathNotFoundError, match="no longer exists"):
            load_project_cache()

    def test_load_cache_no_cache_file(self, tmp_path: Path, monkeypatch: MagicMock):
        """Test loading cache returns None when no cache file exists."""
        cache_dir = tmp_path / ".cache" / "brix"
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        result = load_project_cache()
        assert result is None

    def test_relative_path_converted_to_absolute(self, tmp_path: Path, monkeypatch: MagicMock):
        """Test relative paths are converted to absolute before caching."""
        import os

        cache_dir = tmp_path / ".cache" / "brix"
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        # Change to tmp_path and use relative path
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            save_project_cache(Path("my_project"))
            loaded = load_project_cache()
            assert loaded is not None
            assert loaded.is_absolute()
            assert loaded == project_dir.resolve()
        finally:
            os.chdir(original_cwd)


class TestDbtCommand:
    def test_dbt_command_exists(self):
        result = runner.invoke(app, ["dbt", "--help"])
        assert result.exit_code == 0
        assert "dbt" in result.output.lower()

    def test_dbt_passthrough_args(self, tmp_path: Path, monkeypatch: MagicMock):
        """Test passthrough with --project option."""
        cache_dir = tmp_path / ".cache" / "brix"
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        with patch.object(dbt_command_module, "run_dbt", return_value=0) as mock_run_dbt:
            result = runner.invoke(app, ["dbt", "--project", str(project_dir), "run", "--select", "my_model"])
            mock_run_dbt.assert_called_once_with(["run", "--select", "my_model"], project_path=project_dir.resolve())
            assert result.exit_code == 0

    def test_dbt_preserves_exit_code(self, tmp_path: Path, monkeypatch: MagicMock):
        cache_dir = tmp_path / ".cache" / "brix"
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        with patch.object(dbt_command_module, "run_dbt", return_value=2):
            result = runner.invoke(app, ["dbt", "--project", str(project_dir), "run"])
            assert result.exit_code == 2

    def test_custom_command_not_passed_through(self):
        """Custom commands like 'profile' should not be passed to dbt."""
        with patch.object(dbt_command_module, "run_dbt", return_value=0) as mock_run_dbt:
            result = runner.invoke(app, ["dbt", "profile", "-h"])
            assert result.exit_code == 0
            assert "profile" in result.output.lower()  # Shows profile help
            mock_run_dbt.assert_not_called()

    def test_cached_project_path_used_on_subsequent_calls(self, tmp_path: Path, monkeypatch: MagicMock):
        """Test that cached project path is used when --project not provided."""
        cache_dir = tmp_path / ".cache" / "brix"
        monkeypatch.setattr(passthrough_module, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(passthrough_module, "PROJECT_CACHE_FILE", cache_dir / "dbt_project_path.json")

        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        # First call with --project to cache it
        with patch.object(dbt_command_module, "run_dbt", return_value=0):
            result = runner.invoke(app, ["dbt", "--project", str(project_dir), "run"])
            assert result.exit_code == 0

        # Second call without --project should use cached path
        with patch.object(dbt_command_module, "run_dbt", return_value=0) as mock_run_dbt:
            result = runner.invoke(app, ["dbt", "run"])
            mock_run_dbt.assert_called_once_with(["run"], project_path=project_dir.resolve())
            assert result.exit_code == 0
