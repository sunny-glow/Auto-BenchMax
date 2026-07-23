import logging
import os
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

# Suppress noisy loggers from MCP library
logging.getLogger("mcp").setLevel(logging.WARNING)  # covers mcp.server.*, etc.

# Suppress root logger warnings (e.g., "Failed to validate notification")
logging.getLogger().setLevel(logging.ERROR)


def _get_relative_path(pathname: str) -> str:
    """Helper function to get relative path from the package root."""
    path_parts = pathname.split(os.sep)
    if "agent_environment" in path_parts:
        agent_env_index = path_parts.index("agent_environment")
        return os.sep.join(path_parts[agent_env_index:])
    return pathname


class RelativePathFormatter(logging.Formatter):
    """Custom formatter that shows relative path from the package root."""

    def format(self, record: logging.LogRecord) -> str:
        # Get the relative path from the package root
        if hasattr(record, "pathname"):
            record.pathname = _get_relative_path(record.pathname)
        return super().format(record)


class RelativePathJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that shows relative path from the package root."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        # Get the relative path from the package root
        if hasattr(record, "pathname"):
            log_record["pathname"] = _get_relative_path(record.pathname)


def create_logger(name: Optional[str] = None) -> logging.Logger:
    """Create a logger with console and file handlers that track module path and line number."""
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler with simple format including module path and line number
    console_handler = logging.StreamHandler()
    simple_formatter = RelativePathFormatter(
        "%(asctime)s %(name)s [%(pathname)s:%(lineno)d] - %(levelname)s:%(message)s"
    )
    console_handler.setFormatter(simple_formatter)

    # File handler with JSON format including module path and line number
    # file_handler = logging.FileHandler("/tmp/agent-environment.log")
    # json_formatter = RelativePathJsonFormatter(
    #     "%(asctime)s %(name)s %(levelname)s %(pathname)s %(lineno)d %(message)s"
    # )
    # file_handler.setFormatter(json_formatter)

    logger.addHandler(console_handler)
    # logger.addHandler(file_handler)

    return logger
