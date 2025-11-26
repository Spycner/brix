"""Terraform-style logging system for brix CLI.

Environment variables:
    BRIX_LOG: Log level (TRACE, DEBUG, INFO, WARN, ERROR, OFF)
    BRIX_LOG_PATH: File path for log output
    BRIX_LOG_JSON: Enable JSON format (true/false)
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from typing import Any

# Register custom TRACE level (below DEBUG)
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


class LogLevel(IntEnum):
    """Log levels matching Terraform's TF_LOG.

    Custom TRACE level added below DEBUG (Python's DEBUG=10).
    """

    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    OFF = 100


class LogConfig(BaseSettings):
    """Logging configuration from environment variables.

    Environment variables:
        BRIX_LOG: Log level (TRACE, DEBUG, INFO, WARN, ERROR, OFF)
        BRIX_LOG_PATH: File path for log output
        BRIX_LOG_JSON: Enable JSON format (true/false)
    """

    model_config = SettingsConfigDict(
        env_prefix="BRIX_",
        case_sensitive=False,
    )

    log: Literal["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "OFF"] = "OFF"
    log_path: Path | None = None
    log_json: bool = False

    @field_validator("log", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase."""
        if isinstance(v, str):
            v = v.upper()
            # Handle WARNING -> WARN alias
            if v == "WARNING":
                return "WARN"
        return v


class BrixFormatter(logging.Formatter):
    """Human-readable log formatter for console output.

    Format: [2024-01-15T10:30:45Z] [DEBUG] message
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as human-readable text."""
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        level = record.levelname
        return f"[{timestamp}] [{level}] {record.getMessage()}"


class BrixJsonFormatter(logging.Formatter):
    """JSON log formatter for file output and machine parsing.

    Output: {"@timestamp": "...", "@level": "DEBUG", "@message": "...", "@module": "..."}
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_obj: dict[str, Any] = {
            "@timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "@level": record.levelname,
            "@message": record.getMessage(),
            "@module": record.module,
        }
        if record.exc_info:
            log_obj["@exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


# Thread-safe singleton logger
_logger: logging.Logger | None = None
_lock = threading.Lock()


def setup_logging(
    level: str | None = None,
    log_path: Path | None = None,
    json_format: bool | None = None,
) -> logging.Logger:
    """Initialize the brix logger with config from env and CLI overrides.

    CLI arguments override environment variables.
    Thread-safe initialization with singleton pattern.

    Args:
        level: CLI override for BRIX_LOG
        log_path: CLI override for BRIX_LOG_PATH
        json_format: CLI override for BRIX_LOG_JSON

    Returns:
        Configured logger instance
    """
    global _logger

    with _lock:
        if _logger is not None:
            return _logger

        # Load config from env vars
        config = LogConfig()

        # Apply CLI overrides
        effective_level = (level.upper() if level else None) or config.log
        effective_path = log_path if log_path is not None else config.log_path
        effective_json = json_format if json_format is not None else config.log_json

        # Create logger
        _logger = logging.getLogger("brix")
        _logger.setLevel(LogLevel[effective_level].value)
        _logger.handlers.clear()  # Prevent duplicate handlers

        if effective_level == "OFF":
            _logger.addHandler(logging.NullHandler())
            return _logger

        # Console handler (stderr, human-readable by default)
        console_handler = logging.StreamHandler()
        if effective_json and not effective_path:
            # JSON to console only if no file path and JSON requested
            console_handler.setFormatter(BrixJsonFormatter())
        else:
            console_handler.setFormatter(BrixFormatter())
        _logger.addHandler(console_handler)

        # File handler (JSON by default for files)
        if effective_path:
            file_handler = logging.FileHandler(effective_path)
            # JSON is default for file output
            if effective_json or not config.log_json:
                # Use JSON unless explicitly disabled via env var
                file_handler.setFormatter(BrixJsonFormatter())
            else:
                file_handler.setFormatter(BrixFormatter())
            _logger.addHandler(file_handler)

        return _logger


def get_logger() -> logging.Logger:
    """Get the brix logger (initializes with defaults if needed).

    For use throughout the codebase.
    """
    global _logger
    if _logger is None:
        return setup_logging()
    return _logger


def reset_logger() -> None:
    """Reset the logger singleton (for testing)."""
    global _logger
    with _lock:
        if _logger is not None:
            _logger.handlers.clear()
            _logger = None
