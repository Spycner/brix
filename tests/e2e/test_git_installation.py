"""End-to-end tests for git source installation.

These tests verify that brix can be installed from git source using release tags
with both uv and pip package managers.
"""

import subprocess

import pytest

REPO_URL = "https://github.com/Spycner/brix.git"


def get_latest_tag() -> str:
    """Get the latest release tag from the remote repository."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", REPO_URL],
        capture_output=True,
        text=True,
        check=True,
    )
    # Parse tags and sort by semantic version
    tags = [line.split("refs/tags/")[1] for line in result.stdout.strip().split("\n") if line]
    return sorted(tags, key=lambda t: [int(x) for x in t.lstrip("v").split(".")])[-1]


@pytest.fixture(scope="module")
def latest_tag():
    """Fixture to get latest tag once per test module."""
    return get_latest_tag()


@pytest.mark.e2e
class TestGitInstallation:
    """E2E tests for installing brix from git source."""

    @pytest.mark.xfail(reason="v1.3.0 missing pyyaml dependency - remove after next release")
    def test_uv_install_from_git_tag(self, tmp_path, latest_tag):
        """Test installing brix from git with release tag using uv."""
        venv_path = tmp_path / "venv"
        git_url = f"git+{REPO_URL}@{latest_tag}"

        # Create venv with uv
        result = subprocess.run(["uv", "venv", str(venv_path)], capture_output=True, text=True)
        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"

        # Install from git
        python_path = venv_path / "bin" / "python"
        result = subprocess.run(
            ["uv", "pip", "install", git_url, "--python", str(python_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to install from git: {result.stderr}"

        # Verify installation
        brix_path = venv_path / "bin" / "brix"
        result = subprocess.run([str(brix_path), "--version"], capture_output=True, text=True)
        assert result.returncode == 0, f"brix --version failed: {result.stderr}"
        assert "brix" in result.stdout.lower() or latest_tag.lstrip("v") in result.stdout

    @pytest.mark.xfail(reason="v1.3.0 missing pyyaml dependency - remove after next release")
    def test_pip_install_from_git_tag(self, tmp_path, latest_tag):
        """Test installing brix from git with release tag using pip."""
        venv_path = tmp_path / "venv_pip"
        git_url = f"git+{REPO_URL}@{latest_tag}"

        # Create venv with python
        result = subprocess.run(["python3", "-m", "venv", str(venv_path)], capture_output=True, text=True)
        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"

        # Install from git using pip
        pip_path = venv_path / "bin" / "pip"
        result = subprocess.run([str(pip_path), "install", git_url], capture_output=True, text=True)
        assert result.returncode == 0, f"Failed to install from git: {result.stderr}"

        # Verify installation
        brix_path = venv_path / "bin" / "brix"
        result = subprocess.run([str(brix_path), "--version"], capture_output=True, text=True)
        assert result.returncode == 0, f"brix --version failed: {result.stderr}"
        assert "brix" in result.stdout.lower() or latest_tag.lstrip("v") in result.stdout
