"""
Logging configuration helpers.

Provides consistent log formatting across the claw-code project.
"""
from __future__ import annotations

import logging
import sys
from typing import IO


_LEVEL_COLORS = {
    "DEBUG": "\033[36m",     # cyan
    "INFO": "\033[32m",      # green
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[35m",  # magenta
}
_RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    """Log formatter that adds ANSI color to the level name."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, use_color: bool = True) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if self._use_color:
            color = _LEVEL_COLORS.get(record.levelname, "")
            return f"{color}{record.levelname}{_RESET}: {msg}" if color else msg
        return msg


def configure_logging(
    level: str | int = "WARNING",
    stream: IO = sys.stderr,
    use_color: bool = True,
    fmt: str = "%(name)s — %(message)s",
) -> None:
    """
    Set up root logger with a color-aware handler.

    Safe to call multiple times; clears existing handlers first.
    """
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(ColorFormatter(fmt=fmt, use_color=use_color and stream.isatty()))
    root.addHandler(handler)
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.WARNING)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger (convenience wrapper)."""
    return logging.getLogger(name)


__all__ = [
    "ColorFormatter",
    "configure_logging",
    "get_logger",
]
