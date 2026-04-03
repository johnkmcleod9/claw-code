"""
Output style constants and ANSI colour helpers.

Ports: constants/outputStyles.ts
"""
from __future__ import annotations

import os
import sys


# ---------------------------------------------------------------------------
# Detect colour support
# ---------------------------------------------------------------------------

def _supports_colour() -> bool:
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR") or os.environ.get("CLAW_NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLAW_COLOR"):
        return True
    return True


COLOUR_ENABLED = _supports_colour()


# ---------------------------------------------------------------------------
# ANSI codes
# ---------------------------------------------------------------------------

class _A:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    ITALIC = "\033[3m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN   = "\033[36m"
    WHITE  = "\033[37m"
    GREY   = "\033[90m"
    BRIGHT_RED    = "\033[91m"
    BRIGHT_GREEN  = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE   = "\033[94m"
    BRIGHT_CYAN   = "\033[96m"


def _c(code: str, text: str) -> str:
    if not COLOUR_ENABLED:
        return text
    return f"{code}{text}{_A.RESET}"


# ---------------------------------------------------------------------------
# Semantic colour functions
# ---------------------------------------------------------------------------

def bold(text: str) -> str:
    return _c(_A.BOLD, text)

def dim(text: str) -> str:
    return _c(_A.DIM, text)

def success(text: str) -> str:
    return _c(_A.BRIGHT_GREEN, text)

def error(text: str) -> str:
    return _c(_A.BRIGHT_RED, text)

def warning(text: str) -> str:
    return _c(_A.BRIGHT_YELLOW, text)

def info(text: str) -> str:
    return _c(_A.BRIGHT_CYAN, text)

def muted(text: str) -> str:
    return _c(_A.GREY, text)

def code_text(text: str) -> str:
    return _c(_A.CYAN, text)

def user_label(text: str) -> str:
    return _c(_A.BRIGHT_BLUE + _A.BOLD, text)

def assistant_label(text: str) -> str:
    return _c(_A.BRIGHT_GREEN + _A.BOLD, text)


# ---------------------------------------------------------------------------
# Output width
# ---------------------------------------------------------------------------

def terminal_width(default: int = 80) -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return default


def hr(char: str = "─", width: int | None = None) -> str:
    w = width or terminal_width()
    line = char * w
    return muted(line)


__all__ = [
    "COLOUR_ENABLED",
    "assistant_label",
    "bold",
    "code_text",
    "dim",
    "error",
    "hr",
    "info",
    "muted",
    "success",
    "terminal_width",
    "user_label",
    "warning",
]
