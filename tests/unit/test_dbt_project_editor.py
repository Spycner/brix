"""Unit tests for dbt project editor module."""

from pathlib import Path

import pytest

from brix.modules.dbt.project.editor import (
    EDITABLE_FIELDS,
    PATH_FIELDS,
    InvalidFieldError,
    PackageAlreadyExistsError,
    PackageNotFoundError,
    ProjectNotFoundError,
    add_git_package,
    add_hub_package,
    add_local_package,
    find_package_index,
    get_package_display_info,
    get_package_identifiers,
    has_package,
    load_packages,
    load_project,
    remove_package,
    save_packages,
    save_project,
    update_package_version,
    update_path_field,
    update_project_field,
)
from brix.modules.dbt.project.models import DbtPackages, DbtProject, GitPackage, HubPackage, LocalPackage


class TestLoadSaveProject:
    """Tests for project loading and saving."""

    def test_load_project(self, tmp_path: Path) -> None:
        """Test loading a valid project."""
        project_file = tmp_path / "dbt_project.yml"
        project_file.write_text(
            """
name: test_project
profile: default
version: "1.0.0"
"""
        )

        project = load_project(project_file)
        assert project.name == "test_project"
        assert project.profile == "default"
        assert project.version == "1.0.0"

    def test_load_project_not_found(self, tmp_path: Path) -> None:
        """Test loading a non-existent project."""
        project_file = tmp_path / "dbt_project.yml"

        with pytest.raises(ProjectNotFoundError):
            load_project(project_file)

    def test_save_project(self, tmp_path: Path) -> None:
        """Test saving a project."""
        project_file = tmp_path / "dbt_project.yml"
        project = DbtProject(name="new_project", profile="test")

        save_project(project, project_file)

        assert project_file.exists()
        content = project_file.read_text()
        assert "new_project" in content
        assert "test" in content

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test saving creates parent directories."""
        project_file = tmp_path / "nested" / "dir" / "dbt_project.yml"
        project = DbtProject(name="nested_project", profile="test")

        save_project(project, project_file)

        assert project_file.exists()


class TestUpdateProjectField:
    """Tests for project field updates."""

    def test_update_name(self) -> None:
        """Test updating project name."""
        project = DbtProject(name="old_name", profile="default")

        updated = update_project_field(project, "name", "new_name")

        assert updated.name == "new_name"

    def test_update_profile(self) -> None:
        """Test updating profile."""
        project = DbtProject(name="test", profile="old_profile")

        updated = update_project_field(project, "profile", "new_profile")

        assert updated.profile == "new_profile"

    def test_update_version(self) -> None:
        """Test updating version."""
        project = DbtProject(name="test", profile="default", version="1.0.0")

        updated = update_project_field(project, "version", "2.0.0")

        assert updated.version == "2.0.0"

    def test_update_require_dbt_version(self) -> None:
        """Test updating require_dbt_version."""
        project = DbtProject(name="test", profile="default")

        updated = update_project_field(project, "require_dbt_version", ">=1.0.0")

        assert updated.require_dbt_version == ">=1.0.0"

    def test_update_invalid_field_raises(self) -> None:
        """Test updating an invalid field raises error."""
        project = DbtProject(name="test", profile="default")

        with pytest.raises(InvalidFieldError):
            update_project_field(project, "invalid_field", "value")

    def test_update_restricted_field_raises(self) -> None:
        """Test updating a restricted field raises error."""
        project = DbtProject(name="test", profile="default")

        # vars is not in EDITABLE_FIELDS
        with pytest.raises(InvalidFieldError):
            update_project_field(project, "vars", "some_value")

    def test_field_name_with_dashes(self) -> None:
        """Test field names with dashes are converted to underscores."""
        project = DbtProject(name="test", profile="default")

        # Should work with dashes
        updated = update_project_field(project, "require-dbt-version", ">=1.0.0")

        assert updated.require_dbt_version == ">=1.0.0"

    def test_editable_fields_constant(self) -> None:
        """Test that EDITABLE_FIELDS contains expected values."""
        assert "name" in EDITABLE_FIELDS
        assert "profile" in EDITABLE_FIELDS
        assert "version" in EDITABLE_FIELDS
        assert "require_dbt_version" in EDITABLE_FIELDS


class TestUpdatePathField:
    """Tests for path field updates."""

    def test_add_path(self) -> None:
        """Test adding a path."""
        project = DbtProject(name="test", profile="default", model_paths=["models"])

        updated = update_path_field(project, "model_paths", "add", "staging")

        assert "staging" in updated.model_paths
        assert "models" in updated.model_paths

    def test_add_path_no_duplicate(self) -> None:
        """Test adding an existing path doesn't duplicate."""
        project = DbtProject(name="test", profile="default", model_paths=["models"])

        updated = update_path_field(project, "model_paths", "add", "models")

        assert updated.model_paths.count("models") == 1

    def test_remove_path(self) -> None:
        """Test removing a path."""
        project = DbtProject(name="test", profile="default", model_paths=["models", "staging"])

        updated = update_path_field(project, "model_paths", "remove", "staging")

        assert "staging" not in updated.model_paths
        assert "models" in updated.model_paths

    def test_remove_nonexistent_path_raises(self) -> None:
        """Test removing a non-existent path raises error."""
        project = DbtProject(name="test", profile="default", model_paths=["models"])

        with pytest.raises(ValueError, match="not found"):
            update_path_field(project, "model_paths", "remove", "nonexistent")

    def test_set_paths(self) -> None:
        """Test setting paths completely."""
        project = DbtProject(name="test", profile="default", model_paths=["models"])

        updated = update_path_field(project, "model_paths", "set", ["new_models", "staging"])

        assert updated.model_paths == ["new_models", "staging"]

    def test_invalid_path_field_raises(self) -> None:
        """Test invalid path field raises error."""
        project = DbtProject(name="test", profile="default")

        with pytest.raises(InvalidFieldError):
            update_path_field(project, "invalid_paths", "add", "value")

    def test_path_field_with_dashes(self) -> None:
        """Test path fields with dashes are converted."""
        project = DbtProject(name="test", profile="default", model_paths=["models"])

        updated = update_path_field(project, "model-paths", "add", "staging")

        assert "staging" in updated.model_paths

    def test_path_fields_constant(self) -> None:
        """Test that PATH_FIELDS contains expected values."""
        assert "model_paths" in PATH_FIELDS
        assert "seed_paths" in PATH_FIELDS
        assert "test_paths" in PATH_FIELDS
        assert "macro_paths" in PATH_FIELDS
        assert "clean_targets" in PATH_FIELDS


class TestLoadSavePackages:
    """Tests for package loading and saving."""

    def test_load_packages(self, tmp_path: Path) -> None:
        """Test loading packages."""
        packages_file = tmp_path / "packages.yml"
        packages_file.write_text(
            """
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.0.0"
"""
        )

        packages = load_packages(tmp_path)

        assert len(packages.packages) == 1
        assert isinstance(packages.packages[0], HubPackage)

    def test_load_packages_not_found_returns_empty(self, tmp_path: Path) -> None:
        """Test loading non-existent packages.yml returns empty."""
        packages = load_packages(tmp_path)

        assert packages.packages == []

    def test_load_packages_from_file_path(self, tmp_path: Path) -> None:
        """Test loading packages when given dbt_project.yml path."""
        packages_file = tmp_path / "packages.yml"
        packages_file.write_text(
            """
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.0.0"
"""
        )
        project_file = tmp_path / "dbt_project.yml"

        packages = load_packages(project_file)

        assert len(packages.packages) == 1

    def test_save_packages(self, tmp_path: Path) -> None:
        """Test saving packages."""
        packages = DbtPackages(packages=[HubPackage(package="dbt-labs/dbt_utils", version=">=1.0.0")])

        save_packages(packages, tmp_path)

        packages_file = tmp_path / "packages.yml"
        assert packages_file.exists()
        content = packages_file.read_text()
        assert "dbt-labs/dbt_utils" in content


class TestPackageOperations:
    """Tests for package CRUD operations."""

    @pytest.fixture
    def empty_packages(self) -> DbtPackages:
        """Create empty packages."""
        return DbtPackages(packages=[])

    @pytest.fixture
    def packages_with_hub(self) -> DbtPackages:
        """Create packages with a hub package."""
        return DbtPackages(packages=[HubPackage(package="dbt-labs/dbt_utils", version=">=1.0.0")])

    def test_add_hub_package(self, empty_packages: DbtPackages) -> None:
        """Test adding a hub package."""
        updated = add_hub_package(empty_packages, "dbt-labs/codegen", ">=0.10.0")

        assert len(updated.packages) == 1
        assert isinstance(updated.packages[0], HubPackage)
        assert updated.packages[0].package == "dbt-labs/codegen"

    def test_add_hub_package_duplicate_raises(self, packages_with_hub: DbtPackages) -> None:
        """Test adding duplicate hub package raises error."""
        with pytest.raises(PackageAlreadyExistsError):
            add_hub_package(packages_with_hub, "dbt-labs/dbt_utils", ">=2.0.0")

    def test_add_git_package(self, empty_packages: DbtPackages) -> None:
        """Test adding a git package."""
        updated = add_git_package(empty_packages, "https://github.com/org/repo.git", "main", "subdir")

        assert len(updated.packages) == 1
        assert isinstance(updated.packages[0], GitPackage)
        assert updated.packages[0].git == "https://github.com/org/repo.git"
        assert updated.packages[0].revision == "main"
        assert updated.packages[0].subdirectory == "subdir"

    def test_add_git_package_without_subdirectory(self, empty_packages: DbtPackages) -> None:
        """Test adding git package without subdirectory."""
        updated = add_git_package(empty_packages, "https://github.com/org/repo.git", "v1.0.0")

        assert isinstance(updated.packages[0], GitPackage)
        assert updated.packages[0].subdirectory is None

    def test_add_local_package(self, empty_packages: DbtPackages) -> None:
        """Test adding a local package."""
        updated = add_local_package(empty_packages, "../shared_macros")

        assert len(updated.packages) == 1
        assert isinstance(updated.packages[0], LocalPackage)
        assert updated.packages[0].local == "../shared_macros"

    def test_remove_package(self, packages_with_hub: DbtPackages) -> None:
        """Test removing a package."""
        updated = remove_package(packages_with_hub, "dbt-labs/dbt_utils")

        assert len(updated.packages) == 0

    def test_remove_package_not_found_raises(self, empty_packages: DbtPackages) -> None:
        """Test removing non-existent package raises error."""
        with pytest.raises(PackageNotFoundError):
            remove_package(empty_packages, "nonexistent")

    def test_update_package_version(self, packages_with_hub: DbtPackages) -> None:
        """Test updating hub package version."""
        updated = update_package_version(packages_with_hub, "dbt-labs/dbt_utils", ">=2.0.0")

        assert isinstance(updated.packages[0], HubPackage)
        assert updated.packages[0].version == ">=2.0.0"

    def test_update_package_version_not_found_raises(self, empty_packages: DbtPackages) -> None:
        """Test updating non-existent package raises error."""
        with pytest.raises(PackageNotFoundError):
            update_package_version(empty_packages, "nonexistent", "1.0.0")

    def test_update_non_hub_package_version_raises(self, empty_packages: DbtPackages) -> None:
        """Test updating non-hub package version raises error."""
        packages = add_git_package(empty_packages, "https://github.com/org/repo.git", "main")

        with pytest.raises(ValueError, match="not a hub package"):
            update_package_version(packages, "https://github.com/org/repo.git", "v2.0.0")


class TestPackageHelpers:
    """Tests for package helper functions."""

    @pytest.fixture
    def mixed_packages(self) -> DbtPackages:
        """Create packages with mixed types."""
        return DbtPackages(
            packages=[
                HubPackage(package="dbt-labs/dbt_utils", version=">=1.0.0"),
                GitPackage(git="https://github.com/org/repo.git", revision="main"),
                LocalPackage(local="../shared"),
            ]
        )

    def test_get_package_identifiers(self, mixed_packages: DbtPackages) -> None:
        """Test getting package identifiers."""
        identifiers = get_package_identifiers(mixed_packages)

        assert identifiers == [
            "dbt-labs/dbt_utils",
            "https://github.com/org/repo.git",
            "../shared",
        ]

    def test_find_package_index(self, mixed_packages: DbtPackages) -> None:
        """Test finding package index."""
        assert find_package_index(mixed_packages, "dbt-labs/dbt_utils") == 0
        assert find_package_index(mixed_packages, "https://github.com/org/repo.git") == 1
        assert find_package_index(mixed_packages, "../shared") == 2
        assert find_package_index(mixed_packages, "nonexistent") is None

    def test_has_package(self, mixed_packages: DbtPackages) -> None:
        """Test checking if package exists."""
        assert has_package(mixed_packages, "dbt-labs/dbt_utils") is True
        assert has_package(mixed_packages, "nonexistent") is False

    def test_get_package_display_info(self, mixed_packages: DbtPackages) -> None:
        """Test getting package display info."""
        info = get_package_display_info(mixed_packages)

        assert len(info) == 3
        assert info[0] == ("dbt-labs/dbt_utils", "hub: >=1.0.0")
        assert info[1] == ("https://github.com/org/repo.git", "git: main")
        assert info[2] == ("../shared", "local")

    def test_get_package_display_info_with_subdirectory(self) -> None:
        """Test display info for git package with subdirectory."""
        packages = DbtPackages(
            packages=[GitPackage(git="https://github.com/org/repo.git", revision="main", subdirectory="pkg")]
        )

        info = get_package_display_info(packages)

        assert info[0] == ("https://github.com/org/repo.git", "git: main (pkg)")
