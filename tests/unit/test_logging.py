"""Tests for logging module."""

import json
import logging
from unittest.mock import patch

from typer.testing import CliRunner

from brix.main import app
from brix.utils.logging import (
    BrixFormatter,
    BrixJsonFormatter,
    LogConfig,
    LogLevel,
    get_logger,
    setup_logging,
)


class TestLogLevel:
    def test_trace_below_debug(self):
        assert LogLevel.TRACE < LogLevel.DEBUG

    def test_level_values(self):
        assert LogLevel.DEBUG == logging.DEBUG
        assert LogLevel.INFO == logging.INFO
        assert LogLevel.WARN == logging.WARNING
        assert LogLevel.ERROR == logging.ERROR

    def test_off_highest(self):
        assert LogLevel.OFF > LogLevel.ERROR


class TestLogConfig:
    def test_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            config = LogConfig()
            assert config.log == "ERROR"
            assert config.log_path is None
            assert config.log_json is False

    def test_env_var_log_level(self):
        with patch.dict("os.environ", {"BRIX_LOG": "DEBUG"}):
            config = LogConfig()
            assert config.log == "DEBUG"

    def test_env_var_case_insensitive(self):
        with patch.dict("os.environ", {"BRIX_LOG": "debug"}):
            config = LogConfig()
            assert config.log == "DEBUG"

    def test_env_var_log_path(self, tmp_path):
        log_path = tmp_path / "test.log"
        with patch.dict("os.environ", {"BRIX_LOG_PATH": str(log_path)}):
            config = LogConfig()
            assert config.log_path == log_path

    def test_env_var_log_json(self):
        with patch.dict("os.environ", {"BRIX_LOG_JSON": "true"}):
            config = LogConfig()
            assert config.log_json is True

    def test_warning_alias(self):
        with patch.dict("os.environ", {"BRIX_LOG": "WARNING"}):
            config = LogConfig()
            assert config.log == "WARN"


class TestBrixFormatter:
    def test_format_output(self):
        formatter = BrixFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "[DEBUG]" in output
        assert "Test message" in output
        assert "[" in output
        assert "]" in output

    def test_format_with_args(self):
        formatter = BrixFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "Hello world" in output


class TestBrixJsonFormatter:
    def test_json_output(self):
        formatter = BrixJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["@level"] == "INFO"
        assert data["@message"] == "Test message"
        assert "@timestamp" in data
        assert "@module" in data

    def test_json_with_exception(self):
        formatter = BrixJsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "@exception" in data
        assert "ValueError" in data["@exception"]


class TestSetupLogging:
    def test_default_error(self):
        with patch.dict("os.environ", {}, clear=True):
            logger = setup_logging()
            assert logger.level == LogLevel.ERROR
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_cli_overrides_env(self):
        with patch.dict("os.environ", {"BRIX_LOG": "ERROR"}):
            logger = setup_logging(level="DEBUG")
            assert logger.level == logging.DEBUG

    def test_debug_level(self):
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_file_handler(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logging(level="DEBUG", log_path=log_file)
        # Should have console + file handlers
        assert len(logger.handlers) == 2
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1

    def test_file_uses_json_by_default(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logging(level="DEBUG", log_path=log_file)
        file_handler = next(h for h in logger.handlers if isinstance(h, logging.FileHandler))
        assert isinstance(file_handler.formatter, BrixJsonFormatter)

    def test_json_to_console(self):
        logger = setup_logging(level="DEBUG", json_format=True)
        console_handler = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler))
        assert isinstance(console_handler.formatter, BrixJsonFormatter)

    def test_singleton_pattern(self):
        logger1 = setup_logging(level="DEBUG")
        logger2 = setup_logging(level="ERROR")  # Should return same logger
        assert logger1 is logger2
        assert logger1.level == logging.DEBUG  # First call wins


class TestGetLogger:
    def test_get_logger_initializes(self):
        with patch.dict("os.environ", {}, clear=True):
            logger = get_logger()
            assert logger is not None
            assert logger.name == "brix"

    def test_get_logger_returns_same_instance(self):
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2


# Disable Rich/ANSI colors for consistent CI output
_CLI_ENV = {"NO_COLOR": "1", "TERM": "dumb"}


class TestCliIntegration:
    runner = CliRunner(mix_stderr=False)

    def test_log_level_option_shows_in_help(self):
        result = self.runner.invoke(app, ["--help"], env=_CLI_ENV)
        assert result.exit_code == 0
        assert "--log-level" in result.output

    def test_log_path_option_shows_in_help(self):
        result = self.runner.invoke(app, ["--help"], env=_CLI_ENV)
        assert "--log-path" in result.output

    def test_log_json_option_shows_in_help(self):
        result = self.runner.invoke(app, ["--help"], env=_CLI_ENV)
        assert "--log-json" in result.output

    def test_cli_with_log_level(self):
        result = self.runner.invoke(app, ["--log-level", "DEBUG"], env=_CLI_ENV)
        assert result.exit_code == 0
