"""Tests for dbt profile commands and models."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from brix.main import app
from brix.modules.dbt.profile import (
    DatabricksOutput,
    DbtProfiles,
    DuckDbOutput,
    ProfileExistsError,
    get_default_profile_path,
    init_profile,
    load_template,
)

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

    def test_parse_duckdb_profile_with_all_options(self):
        """Test DuckDB profile with schema, database, extensions, and settings."""
        yaml_content = """
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: data.duckdb
      schema: analytics
      database: main
      threads: 4
      extensions:
        - httpfs
        - parquet
      settings:
        memory_limit: 4GB
        threads: 8
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output = profiles["default"].outputs["dev"]
        assert isinstance(output, DuckDbOutput)
        assert output.path == "data.duckdb"
        assert output.schema_ == "analytics"
        assert output.database == "main"
        assert output.threads == 4
        assert output.extensions == ["httpfs", "parquet"]
        assert output.settings == {"memory_limit": "4GB", "threads": 8}

    def test_duckdb_default_values(self):
        """Test default values for optional DuckDB fields."""
        output = DuckDbOutput(type="duckdb")
        assert output.path == ":memory:"
        assert output.schema_ == "main"
        assert output.database == "main"
        assert output.threads == 1
        assert output.extensions == []
        assert output.settings == {}

    def test_duckdb_yaml_roundtrip_with_extensions_and_settings(self):
        """Test YAML roundtrip preserves extensions and settings."""
        yaml_content = """
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: test.duckdb
      schema: custom_schema
      database: mydb
      extensions:
        - httpfs
        - parquet
      settings:
        memory_limit: 2GB
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output_yaml = profiles.to_yaml()
        profiles2 = DbtProfiles.from_yaml(output_yaml)
        output = profiles2["default"].outputs["dev"]
        assert isinstance(output, DuckDbOutput)
        assert output.schema_ == "custom_schema"
        assert output.database == "mydb"
        assert output.extensions == ["httpfs", "parquet"]
        assert output.settings == {"memory_limit": "2GB"}


class TestDatabricksOutput:
    """Tests for DatabricksOutput pydantic model and validation.

    Note: S105/S106 noqa comments suppress false positives for test fixture secrets.
    """

    def test_parse_databricks_profile_with_token(self):
        """Test basic Databricks profile with PAT authentication."""
        yaml_content = """
databricks_project:
  target: dev
  outputs:
    dev:
      type: databricks
      schema: my_schema
      host: myorg.databricks.com
      http_path: /sql/1.0/warehouses/abc123
      token: dapi123456789
      catalog: main
      threads: 4
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        assert "databricks_project" in profiles
        output = profiles["databricks_project"].outputs["dev"]
        assert isinstance(output, DatabricksOutput)
        assert output.type == "databricks"
        assert output.schema_ == "my_schema"
        assert output.host == "myorg.databricks.com"
        assert output.http_path == "/sql/1.0/warehouses/abc123"
        assert output.token == "dapi123456789"  # noqa: S105
        assert output.catalog == "main"
        assert output.threads == 4

    def test_parse_databricks_profile_oauth_u2m(self):
        """Test Databricks profile with OAuth U2M (browser-based) authentication."""
        yaml_content = """
databricks_project:
  target: dev
  outputs:
    dev:
      type: databricks
      schema: my_schema
      host: myorg.databricks.com
      http_path: /sql/1.0/warehouses/abc123
      auth_type: oauth
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output = profiles["databricks_project"].outputs["dev"]
        assert isinstance(output, DatabricksOutput)
        assert output.auth_type == "oauth"
        assert output.token is None
        assert output.client_id is None

    def test_parse_databricks_profile_oauth_m2m_aws(self):
        """Test Databricks profile with OAuth M2M (AWS/GCP) authentication."""
        yaml_content = """
databricks_project:
  target: dev
  outputs:
    dev:
      type: databricks
      schema: my_schema
      host: myorg.databricks.com
      http_path: /sql/1.0/warehouses/abc123
      auth_type: oauth
      client_id: my-client-id
      client_secret: my-client-secret
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output = profiles["databricks_project"].outputs["dev"]
        assert isinstance(output, DatabricksOutput)
        assert output.auth_type == "oauth"
        assert output.client_id == "my-client-id"
        assert output.client_secret == "my-client-secret"  # noqa: S105

    def test_parse_databricks_profile_oauth_m2m_azure(self):
        """Test Databricks profile with OAuth M2M (Azure) authentication."""
        yaml_content = """
databricks_project:
  target: dev
  outputs:
    dev:
      type: databricks
      schema: my_schema
      host: myorg.azuredatabricks.net
      http_path: /sql/1.0/warehouses/abc123
      auth_type: oauth
      azure_client_id: azure-client-id
      azure_client_secret: azure-client-secret
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output = profiles["databricks_project"].outputs["dev"]
        assert isinstance(output, DatabricksOutput)
        assert output.auth_type == "oauth"
        assert output.azure_client_id == "azure-client-id"
        assert output.azure_client_secret == "azure-client-secret"  # noqa: S105

    def test_host_validator_strips_https_prefix(self):
        """Test that https:// prefix is stripped from host."""
        output = DatabricksOutput(
            type="databricks",
            schema="my_schema",
            host="https://myorg.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
            token="dapi123",  # noqa: S106
        )
        assert output.host == "myorg.databricks.com"

    def test_host_validator_strips_http_prefix(self):
        """Test that http:// prefix is stripped from host."""
        output = DatabricksOutput(
            type="databricks",
            schema="my_schema",
            host="http://myorg.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
            token="dapi123",  # noqa: S106
        )
        assert output.host == "myorg.databricks.com"

    def test_http_path_validator_adds_leading_slash(self):
        """Test that missing leading slash is added to http_path."""
        output = DatabricksOutput(
            type="databricks",
            schema="my_schema",
            host="myorg.databricks.com",
            http_path="sql/1.0/warehouses/abc123",
            token="dapi123",  # noqa: S106
        )
        assert output.http_path == "/sql/1.0/warehouses/abc123"

    def test_http_path_validator_preserves_existing_slash(self):
        """Test that existing leading slash is preserved."""
        output = DatabricksOutput(
            type="databricks",
            schema="my_schema",
            host="myorg.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
            token="dapi123",  # noqa: S106
        )
        assert output.http_path == "/sql/1.0/warehouses/abc123"

    def test_auth_error_token_with_oauth(self):
        """Test that token + auth_type raises error."""
        with pytest.raises(ValueError, match="Cannot use token authentication with OAuth"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                token="dapi123",  # noqa: S106
                auth_type="oauth",
            )

    def test_auth_error_token_with_client_id(self):
        """Test that token + client_id raises error."""
        with pytest.raises(ValueError, match="Cannot use token authentication with OAuth"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                token="dapi123",  # noqa: S106
                client_id="some-client",
            )

    def test_auth_error_incomplete_client_creds(self):
        """Test that incomplete client credentials raises error."""
        with pytest.raises(ValueError, match="Both client_id and client_secret are required"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                auth_type="oauth",
                client_id="my-client-id",
                # missing client_secret
            )

    def test_auth_error_incomplete_azure_creds(self):
        """Test that incomplete Azure credentials raises error."""
        with pytest.raises(ValueError, match="Both azure_client_id and azure_client_secret are required"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                auth_type="oauth",
                azure_client_id="azure-client",
                # missing azure_client_secret
            )

    def test_auth_error_mixed_client_and_azure(self):
        """Test that mixing AWS/GCP and Azure credentials raises error."""
        with pytest.raises(ValueError, match="Cannot mix AWS/GCP and Azure OAuth"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                auth_type="oauth",
                client_id="aws-client",
                client_secret="aws-secret",  # noqa: S106
                azure_client_id="azure-client",
            )

    def test_auth_error_client_without_auth_type(self):
        """Test that client credentials without auth_type raises error."""
        with pytest.raises(ValueError, match="OAuth credentials require auth_type='oauth'"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                client_id="my-client",
            )

    def test_threads_validation_error(self):
        """Test that threads < 1 raises error."""
        with pytest.raises(ValueError, match="threads must be at least 1"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                token="dapi123",  # noqa: S106
                threads=0,
            )

    def test_connect_retries_validation_error(self):
        """Test that connect_retries < 0 raises error."""
        with pytest.raises(ValueError, match="connect_retries must be non-negative"):
            DatabricksOutput(
                type="databricks",
                schema="my_schema",
                host="myorg.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                token="dapi123",  # noqa: S106
                connect_retries=-1,
            )

    def test_no_auth_allowed(self):
        """Test that no auth is allowed (for env var token references)."""
        # This should not raise - user may be using env var for token
        output = DatabricksOutput(
            type="databricks",
            schema="my_schema",
            host="myorg.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
        )
        assert output.token is None
        assert output.auth_type is None

    def test_default_values(self):
        """Test default values for optional fields."""
        output = DatabricksOutput(
            type="databricks",
            schema="my_schema",
            host="myorg.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
            token="dapi123",  # noqa: S106
        )
        assert output.threads == 1
        assert output.connect_retries == 0
        assert output.connect_timeout is None
        assert output.catalog is None

    def test_yaml_roundtrip_databricks(self):
        """Test YAML serialization roundtrip for Databricks profile."""
        yaml_content = """
databricks_project:
  target: dev
  outputs:
    dev:
      type: databricks
      schema: my_schema
      host: myorg.databricks.com
      http_path: /sql/1.0/warehouses/abc123
      token: dapi123456789
      catalog: main
      threads: 4
"""
        profiles = DbtProfiles.from_yaml(yaml_content)
        output_yaml = profiles.to_yaml()
        profiles2 = DbtProfiles.from_yaml(output_yaml)
        output = profiles2["databricks_project"].outputs["dev"]
        assert isinstance(output, DatabricksOutput)
        assert output.schema_ == "my_schema"
        assert output.host == "myorg.databricks.com"
        assert output.token == "dapi123456789"  # noqa: S105


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
        # Check for short options as Rich formatting may wrap/truncate long options
        assert "-p" in result.output
        assert "-f" in result.output

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
