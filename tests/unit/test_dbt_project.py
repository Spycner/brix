"""Tests for dbt project commands and models."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from brix.main import app
from brix.modules.dbt.project.models import (
    DbtPackages,
    DbtProject,
    GitPackage,
    HubPackage,
    LocalPackage,
    ProjectNameError,
    validate_project_name,
)
from brix.modules.dbt.project.service import (
    ProjectExistsError,
    init_project,
    resolve_project_path,
)

runner = CliRunner()


class TestProjectNameValidation:
    """Tests for project name validation."""

    def test_valid_project_names(self):
        """Test that valid project names pass validation."""
        valid_names = [
            "my_project",
            "MyProject",
            "_private",
            "project123",
            "a",
            "_",
            "my_dbt_project_v2",
        ]
        for name in valid_names:
            assert validate_project_name(name) == name

    def test_invalid_project_names(self):
        """Test that invalid project names raise errors."""
        invalid_names = [
            "my-project",  # hyphens not allowed
            "123project",  # can't start with number
            "my project",  # spaces not allowed
            "my.project",  # dots not allowed
            "",  # empty not allowed
            "project@name",  # special chars not allowed
        ]
        for name in invalid_names:
            with pytest.raises(ProjectNameError):
                validate_project_name(name)


class TestDbtProject:
    """Tests for DbtProject pydantic model."""

    def test_parse_simple_project(self):
        yaml_content = """
name: my_project
version: '1.0.0'
profile: default
config-version: 2

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
"""
        project = DbtProject.from_yaml(yaml_content)
        assert project.name == "my_project"
        assert project.version == "1.0.0"
        assert project.profile == "default"
        assert project.config_version == 2
        assert project.model_paths == ["models"]

    def test_parse_invalid_yaml_raises(self):
        with pytest.raises(ValueError, match="Invalid YAML"):
            DbtProject.from_yaml("{ invalid yaml")

    def test_parse_non_mapping_raises(self):
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            DbtProject.from_yaml("- list item")

    def test_to_yaml_roundtrip(self):
        project = DbtProject(
            name="test_project",
            profile="my_profile",
            version="2.0.0",
        )
        yaml_output = project.to_yaml()
        project2 = DbtProject.from_yaml(yaml_output)
        assert project2.name == "test_project"
        assert project2.profile == "my_profile"
        assert project2.version == "2.0.0"

    def test_default_values(self):
        """Test default values for optional fields."""
        project = DbtProject(name="test", profile="default")
        assert project.version == "1.0.0"
        assert project.config_version == 2
        assert project.model_paths == ["models"]
        assert project.seed_paths == ["seeds"]
        assert project.test_paths == ["tests"]
        assert project.clean_targets == ["target", "dbt_packages"]

    def test_project_with_models_config(self):
        """Test project with models configuration."""
        project = DbtProject(
            name="test_project",
            profile="databricks_dev",
            models={
                "test_project": {
                    "+materialized": "table",
                    "+persist_docs": {"relation": True, "columns": True},
                }
            },
        )
        yaml_output = project.to_yaml()
        assert "+materialized" in yaml_output
        assert "table" in yaml_output
        assert "+persist_docs" in yaml_output

    def test_invalid_project_name_raises(self):
        """Test that invalid project name in model raises error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Invalid project name"):
            DbtProject(name="invalid-name", profile="default")


class TestDbtPackages:
    """Tests for DbtPackages pydantic model."""

    def test_parse_hub_packages(self):
        yaml_content = """
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.0.0"
  - package: elementary-data/elementary
    version: ">=0.13.0"
"""
        packages = DbtPackages.from_yaml(yaml_content)
        assert len(packages.packages) == 2
        assert isinstance(packages.packages[0], HubPackage)
        assert packages.packages[0].package == "dbt-labs/dbt_utils"
        assert packages.packages[0].version == ">=1.0.0"

    def test_parse_git_package(self):
        yaml_content = """
packages:
  - git: "https://github.com/org/repo.git"
    revision: main
    subdirectory: dbt_project
"""
        packages = DbtPackages.from_yaml(yaml_content)
        assert len(packages.packages) == 1
        pkg = packages.packages[0]
        assert isinstance(pkg, GitPackage)
        assert pkg.git == "https://github.com/org/repo.git"
        assert pkg.revision == "main"
        assert pkg.subdirectory == "dbt_project"

    def test_parse_local_package(self):
        yaml_content = """
packages:
  - local: ../shared_macros
"""
        packages = DbtPackages.from_yaml(yaml_content)
        assert len(packages.packages) == 1
        pkg = packages.packages[0]
        assert isinstance(pkg, LocalPackage)
        assert pkg.local == "../shared_macros"

    def test_empty_packages(self):
        packages = DbtPackages.from_yaml("")
        assert packages.packages == []

    def test_add_hub_package(self):
        packages = DbtPackages()
        packages.add_hub_package("dbt-labs/dbt_utils", ">=1.0.0")
        assert len(packages.packages) == 1
        assert packages.packages[0].package == "dbt-labs/dbt_utils"

    def test_to_yaml_roundtrip(self):
        packages = DbtPackages()
        packages.add_hub_package("dbt-labs/dbt_utils", ">=1.0.0")
        packages.add_git_package("https://github.com/org/repo.git", "main")

        yaml_output = packages.to_yaml()
        packages2 = DbtPackages.from_yaml(yaml_output)

        assert len(packages2.packages) == 2
        assert isinstance(packages2.packages[0], HubPackage)
        assert isinstance(packages2.packages[1], GitPackage)


class TestResolveProjectPath:
    """Tests for project path resolution."""

    def test_simple_project_name(self, tmp_path):
        """Test resolution with just project name."""
        with patch.object(Path, "cwd", return_value=tmp_path):
            path = resolve_project_path("my_project")
            assert path == tmp_path / "my_project"

    def test_with_base_dir(self, tmp_path):
        """Test resolution with base directory."""
        base = tmp_path / "projects"
        path = resolve_project_path("my_project", base_dir=base)
        assert path == base / "my_project"

    def test_with_team(self, tmp_path):
        """Test resolution with team subdirectory."""
        base = tmp_path / "projects"
        path = resolve_project_path("my_project", base_dir=base, team="analytics")
        assert path == base / "analytics" / "my_project"

    def test_relative_base_dir(self, tmp_path):
        """Test that relative base dir is made absolute."""
        with patch.object(Path, "cwd", return_value=tmp_path):
            path = resolve_project_path("my_project", base_dir=Path("subdir"))
            assert path.is_absolute()
            assert path == tmp_path / "subdir" / "my_project"


class TestInitProject:
    """Tests for project initialization."""

    def test_init_creates_project(self, tmp_path):
        """Test that init_project creates all expected files."""
        result = init_project(
            project_name="test_project",
            profile_name="default",
            base_dir=tmp_path,
        )

        assert result.success
        assert result.project_path == tmp_path / "test_project"
        assert (tmp_path / "test_project" / "dbt_project.yml").exists()
        assert (tmp_path / "test_project" / "packages.yml").exists()
        assert (tmp_path / "test_project" / ".gitignore").exists()
        assert (tmp_path / "test_project" / "models").is_dir()
        assert (tmp_path / "test_project" / "seeds").is_dir()

    def test_init_with_packages(self, tmp_path):
        """Test init with custom packages."""
        packages = [
            HubPackage(package="dbt-labs/dbt_utils", version=">=1.0.0"),
            HubPackage(package="elementary-data/elementary", version=">=0.13.0"),
        ]
        result = init_project(
            project_name="test_project",
            profile_name="default",
            base_dir=tmp_path,
            packages=packages,
        )

        assert result.success
        packages_yml = (tmp_path / "test_project" / "packages.yml").read_text()
        assert "dbt-labs/dbt_utils" in packages_yml
        assert "elementary-data/elementary" in packages_yml

    def test_init_with_example(self, tmp_path):
        """Test init with example model."""
        result = init_project(
            project_name="test_project",
            profile_name="default",
            base_dir=tmp_path,
            with_example=True,
        )

        assert result.success
        assert (tmp_path / "test_project" / "models" / "example" / "my_first_model.sql").exists()
        assert (tmp_path / "test_project" / "models" / "example" / "schema.yml").exists()

    def test_init_with_materialization(self, tmp_path):
        """Test init with custom materialization."""
        result = init_project(
            project_name="test_project",
            profile_name="databricks_dev",
            base_dir=tmp_path,
            materialization="table",
        )

        assert result.success
        project_yml = (tmp_path / "test_project" / "dbt_project.yml").read_text()
        assert "+materialized: table" in project_yml

    def test_init_with_persist_docs(self, tmp_path):
        """Test init with persist_docs enabled."""
        result = init_project(
            project_name="test_project",
            profile_name="databricks_dev",
            base_dir=tmp_path,
            persist_docs=True,
        )

        assert result.success
        project_yml = (tmp_path / "test_project" / "dbt_project.yml").read_text()
        assert "+persist_docs" in project_yml
        assert "relation: true" in project_yml

    def test_init_existing_project_raises(self, tmp_path):
        """Test that init raises when project exists."""
        # Create existing project
        project_dir = tmp_path / "existing_project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: existing")

        with pytest.raises(ProjectExistsError):
            init_project(
                project_name="existing_project",
                profile_name="default",
                base_dir=tmp_path,
            )

    def test_init_force_overwrites(self, tmp_path):
        """Test that init with force overwrites existing project."""
        # Create existing project
        project_dir = tmp_path / "existing_project"
        project_dir.mkdir()
        (project_dir / "dbt_project.yml").write_text("name: old_name")

        result = init_project(
            project_name="existing_project",
            profile_name="default",
            base_dir=tmp_path,
            force=True,
        )

        assert result.success
        assert result.action == "overwritten"
        project_yml = (project_dir / "dbt_project.yml").read_text()
        assert "existing_project" in project_yml

    def test_init_invalid_name_raises(self, tmp_path):
        """Test that init raises for invalid project name."""
        with pytest.raises(ProjectNameError):
            init_project(
                project_name="invalid-name",
                profile_name="default",
                base_dir=tmp_path,
            )


class TestProjectCli:
    """Tests for project CLI commands."""

    def test_project_init_help(self):
        """Test that project init --help works."""
        result = runner.invoke(app, ["dbt", "project", "init", "--help"])
        assert result.exit_code == 0
        assert "Initialize a new dbt project" in result.stdout

    def test_project_init_requires_profile_in_cli_mode(self):
        """Test that --profile is required when --project-name is given."""
        result = runner.invoke(app, ["dbt", "project", "init", "-n", "test_project"])
        assert result.exit_code == 1
        assert "--profile is required" in result.stdout

    def test_project_init_cli_mode(self, tmp_path):
        """Test CLI mode project initialization."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "project",
                "init",
                "-n",
                "test_cli_project",
                "-b",
                str(tmp_path),
                "-p",
                "default",
                "--no-run-deps",
            ],
        )
        assert result.exit_code == 0
        assert "Project created" in result.stdout or "Project initialization complete" in result.stdout
        assert (tmp_path / "test_cli_project" / "dbt_project.yml").exists()

    def test_project_init_with_team(self, tmp_path):
        """Test CLI mode with team option."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "project",
                "init",
                "-n",
                "my_project",
                "-b",
                str(tmp_path),
                "-t",
                "data_team",
                "-p",
                "default",
                "--no-run-deps",
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "data_team" / "my_project" / "dbt_project.yml").exists()

    def test_project_init_invalid_name(self, tmp_path):
        """Test that invalid project name fails."""
        result = runner.invoke(
            app,
            [
                "dbt",
                "project",
                "init",
                "-n",
                "invalid-name",
                "-b",
                str(tmp_path),
                "-p",
                "default",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid project name" in result.stdout or "must start with" in result.stdout
