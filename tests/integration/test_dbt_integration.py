"""Integration tests for dbt passthrough with actual dbt execution."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from brix.main import app
from brix.modules.dbt import run_dbt

# Path to the test dbt project fixture
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
DBT_PROJECT_DIR = FIXTURES_DIR / "dbt_project"

runner = CliRunner()


@pytest.fixture
def dbt_project(tmp_path):
    """Copy the dbt project fixture to a temporary directory."""
    project_dir = tmp_path / "dbt_project"
    shutil.copytree(DBT_PROJECT_DIR, project_dir)
    return project_dir


@pytest.mark.integration
class TestDbtIntegration:
    """Integration tests that actually run dbt commands."""

    def test_dbt_version(self):
        """Test that dbt --version runs successfully."""
        exit_code = run_dbt(["--version"])
        assert exit_code == 0

    def test_dbt_debug(self, dbt_project):
        """Test dbt debug in a project directory."""
        exit_code = run_dbt(["debug", "--project-dir", str(dbt_project), "--profiles-dir", str(dbt_project)])
        assert exit_code == 0

    def test_dbt_parse(self, dbt_project):
        """Test dbt parse to validate project structure."""
        exit_code = run_dbt(["parse", "--project-dir", str(dbt_project), "--profiles-dir", str(dbt_project)])
        assert exit_code == 0

    def test_dbt_run(self, dbt_project):
        """Test dbt run executes models successfully."""
        exit_code = run_dbt(["run", "--project-dir", str(dbt_project), "--profiles-dir", str(dbt_project)])
        assert exit_code == 0


@pytest.mark.integration
class TestBrixDbtIntegration:
    """Integration tests for dbt passthrough via the brix CLI."""

    def test_brix_dbt_version(self):
        """Test brix dbt --version runs successfully."""
        # Note: dbt output goes to stdout via subprocess, not through Typer's output
        result = runner.invoke(app, ["dbt", "--version"])
        assert result.exit_code == 0

    def test_brix_dbt_debug(self, dbt_project):
        """Test brix dbt debug in a project directory."""
        result = runner.invoke(
            app,
            ["dbt", "debug", "--project-dir", str(dbt_project), "--profiles-dir", str(dbt_project)],
        )
        assert result.exit_code == 0

    def test_brix_dbt_run(self, dbt_project):
        """Test brix dbt run executes models successfully via CLI."""
        result = runner.invoke(
            app,
            ["dbt", "run", "--project-dir", str(dbt_project), "--profiles-dir", str(dbt_project)],
        )
        assert result.exit_code == 0
