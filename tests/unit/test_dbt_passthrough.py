"""Tests for dbt passthrough command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

import brix.modules.dbt.passthrough as passthrough_module
from brix.main import app
from brix.modules.dbt import run_dbt

runner = CliRunner()


class TestRunDbt:
    def test_forwards_arguments_to_subprocess(self):
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)
            exit_code = run_dbt(["run", "--select", "my_model"])
            mock_subprocess.run.assert_called_once_with(["dbt", "run", "--select", "my_model"])
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
            mock_subprocess.run.assert_called_once_with(["dbt"])
            assert exit_code == 0


class TestDbtCommand:
    def test_dbt_command_exists(self):
        result = runner.invoke(app, ["dbt", "--help"])
        assert result.exit_code == 0
        assert "dbt" in result.output.lower()

    def test_dbt_passthrough_args(self):
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["dbt", "run", "--select", "my_model"])
            mock_subprocess.run.assert_called_once_with(["dbt", "run", "--select", "my_model"])
            assert result.exit_code == 0

    def test_dbt_preserves_exit_code(self):
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=2)
            result = runner.invoke(app, ["dbt", "run"])
            assert result.exit_code == 2

    def test_custom_command_not_passed_through(self):
        """Custom commands like 'setup' should not be passed to dbt."""
        with patch.object(passthrough_module, "subprocess") as mock_subprocess:
            result = runner.invoke(app, ["dbt", "setup"])
            assert result.exit_code == 0
            assert "not yet implemented" in result.output
            mock_subprocess.run.assert_not_called()
