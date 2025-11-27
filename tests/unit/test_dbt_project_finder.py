"""Unit tests for dbt project finder module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from brix.modules.dbt.project.finder import (
    EXCLUDE_DIRS,
    _format_project_choice,
    _should_exclude,
    find_dbt_projects,
    get_search_root,
)


class TestGetSearchRoot:
    """Tests for get_search_root function."""

    def test_in_git_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns git root when in a git repo."""
        git_root = tmp_path / "repo"
        git_root.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = str(git_root) + "\n"

            result = get_search_root()

            assert result == git_root

    def test_not_in_git_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns cwd when not in a git repo."""
        import subprocess

        monkeypatch.chdir(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")

            result = get_search_root()

            assert result == tmp_path


class TestShouldExclude:
    """Tests for _should_exclude function."""

    def test_excludes_venv(self) -> None:
        """Test excludes .venv directory."""
        path = Path("/project/.venv/some/path")
        assert _should_exclude(path) is True

    def test_excludes_node_modules(self) -> None:
        """Test excludes node_modules directory."""
        path = Path("/project/node_modules/package/file")
        assert _should_exclude(path) is True

    def test_excludes_dbt_packages(self) -> None:
        """Test excludes dbt_packages directory."""
        path = Path("/project/dbt_packages/dbt_utils/file")
        assert _should_exclude(path) is True

    def test_excludes_target(self) -> None:
        """Test excludes target directory."""
        path = Path("/project/target/compiled/file")
        assert _should_exclude(path) is True

    def test_excludes_git(self) -> None:
        """Test excludes .git directory."""
        path = Path("/project/.git/objects/file")
        assert _should_exclude(path) is True

    def test_does_not_exclude_normal_path(self) -> None:
        """Test does not exclude normal project paths."""
        path = Path("/project/models/staging/file.sql")
        assert _should_exclude(path) is False

    def test_exclude_dirs_constant(self) -> None:
        """Test EXCLUDE_DIRS contains expected values."""
        assert ".venv" in EXCLUDE_DIRS
        assert "venv" in EXCLUDE_DIRS
        assert "node_modules" in EXCLUDE_DIRS
        assert "dbt_packages" in EXCLUDE_DIRS
        assert "target" in EXCLUDE_DIRS
        assert ".git" in EXCLUDE_DIRS


class TestFindDbtProjects:
    """Tests for find_dbt_projects function."""

    def test_finds_projects(self, tmp_path: Path) -> None:
        """Test finds dbt projects."""
        # Create a dbt project
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test\nprofile: default\n")

        projects = find_dbt_projects(tmp_path)

        assert len(projects) == 1
        assert projects[0] == (project_dir / "dbt_project.yml").resolve()

    def test_finds_multiple_projects(self, tmp_path: Path) -> None:
        """Test finds multiple projects."""
        # Create two dbt projects
        for name in ["project_a", "project_b"]:
            project_dir = tmp_path / name
            project_dir.mkdir()
            (project_dir / "dbt_project.yml").write_text(f"name: {name}\nprofile: default\n")

        projects = find_dbt_projects(tmp_path)

        assert len(projects) == 2

    def test_excludes_venv(self, tmp_path: Path) -> None:
        """Test excludes projects in .venv."""
        # Create project in .venv (should be excluded)
        venv_dir = tmp_path / ".venv" / "some_project"
        venv_dir.mkdir(parents=True)
        (venv_dir / "dbt_project.yml").write_text("name: test\nprofile: default\n")

        # Create normal project
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: test\nprofile: default\n")

        projects = find_dbt_projects(tmp_path)

        assert len(projects) == 1
        assert ".venv" not in str(projects[0])

    def test_excludes_dbt_packages(self, tmp_path: Path) -> None:
        """Test excludes projects in dbt_packages."""
        # Create project in dbt_packages (should be excluded)
        pkgs_dir = tmp_path / "my_project" / "dbt_packages" / "dbt_utils"
        pkgs_dir.mkdir(parents=True)
        (pkgs_dir / "dbt_project.yml").write_text("name: dbt_utils\nprofile: default\n")

        # Create main project
        project_dir = tmp_path / "my_project"
        (project_dir / "dbt_project.yml").write_text("name: test\nprofile: default\n")

        projects = find_dbt_projects(tmp_path)

        # Should find only the main project, not the one in dbt_packages
        assert len(projects) == 1
        assert projects[0] == (project_dir / "dbt_project.yml").resolve()

    def test_respects_max_depth(self, tmp_path: Path) -> None:
        """Test respects max_depth parameter."""
        # Create deeply nested project
        deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e" / "project"
        deep_dir.mkdir(parents=True)
        (deep_dir / "dbt_project.yml").write_text("name: deep\nprofile: default\n")

        # Create shallow project
        shallow_dir = tmp_path / "shallow"
        shallow_dir.mkdir()
        (shallow_dir / "dbt_project.yml").write_text("name: shallow\nprofile: default\n")

        # With max_depth=2, should only find shallow
        projects = find_dbt_projects(tmp_path, max_depth=2)

        assert len(projects) == 1
        assert "shallow" in str(projects[0])

    def test_returns_empty_if_none_found(self, tmp_path: Path) -> None:
        """Test returns empty list if no projects found."""
        projects = find_dbt_projects(tmp_path)

        assert projects == []

    def test_returns_sorted_paths(self, tmp_path: Path) -> None:
        """Test returns paths sorted by path."""
        # Create projects in non-alphabetical order
        for name in ["z_project", "a_project", "m_project"]:
            project_dir = tmp_path / name
            project_dir.mkdir()
            (project_dir / "dbt_project.yml").write_text(f"name: {name}\nprofile: default\n")

        projects = find_dbt_projects(tmp_path)

        # Should be sorted alphabetically
        assert "a_project" in str(projects[0])
        assert "m_project" in str(projects[1])
        assert "z_project" in str(projects[2])

    def test_handles_nonexistent_root(self, tmp_path: Path) -> None:
        """Test handles non-existent root gracefully."""
        nonexistent = tmp_path / "nonexistent"

        projects = find_dbt_projects(nonexistent)

        assert projects == []


class TestFormatProjectChoice:
    """Tests for _format_project_choice function."""

    def test_formats_relative_path(self, tmp_path: Path) -> None:
        """Test formats path relative to search root."""
        project_path = tmp_path / "projects" / "my_project" / "dbt_project.yml"

        result = _format_project_choice(project_path, tmp_path)

        assert result == "projects/my_project"

    def test_formats_root_project(self, tmp_path: Path) -> None:
        """Test formats project at root."""
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        project_path = project_dir / "dbt_project.yml"

        result = _format_project_choice(project_path, tmp_path)

        assert result == "my_project"

    def test_handles_path_outside_root(self, tmp_path: Path) -> None:
        """Test handles path outside search root."""
        other_root = tmp_path / "other"
        other_root.mkdir()
        project_path = other_root / "project" / "dbt_project.yml"

        result = _format_project_choice(project_path, tmp_path / "different")

        # Should fall back to absolute path parent
        assert str(project_path.parent) in result
