"""Logging configuration with colored console and file output.

Call ``setup_logging()`` at application startup to configure the root
logger with both a coloured console handler and a rotating file handler.
"""

import logging
import os
import sys

from app.config import get_settings


class ColoredFormatter(logging.Formatter):
    """Custom log formatter that adds ANSI colour codes to log levels.

    Provides visual distinction between log levels in terminal output.
    """

    COLORS: dict[str, str] = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colour codes around the level name.

        Args:
            record: The log record to format.

        Returns:
            The formatted log string with ANSI colour codes.
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging() -> None:
    """Configure application-wide logging.

    Sets up two handlers on the root logger:

    1. **Console handler** — coloured output to ``stderr``.
    2. **File handler** — plain-text output to ``logs/app.log``.

    The log level is read from ``Settings.LOG_LEVEL``.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Ensure the logs directory exists
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates on reload
    root_logger.handlers.clear()

    # Console handler with colour
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        ColoredFormatter(fmt=log_format, datefmt=date_format)
    )
    root_logger.addHandler(console_handler)

    # File handler (plain text)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(fmt=log_format, datefmt=date_format)
    )
    root_logger.addHandler(file_handler)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.DEBUG else logging.WARNING
    )
