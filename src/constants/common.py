"""
Common application constants.

Ports: constants/common.ts, constants/product.ts, constants/figures.ts,
       constants/files.ts, constants/keys.ts, constants/spinnerVerbs.ts,
       constants/turnCompletionVerbs.ts, constants/xml.ts
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Product info (constants/product.ts)
# ---------------------------------------------------------------------------

PRODUCT_NAME = "Claw Code"
PRODUCT_SHORT = "claw"
PRODUCT_VERSION = "0.1.0"
GITHUB_URL = "https://github.com/anthropics/claw-code"
DOCS_URL = "https://docs.anthropic.com/claw-code"

# ---------------------------------------------------------------------------
# File names / paths (constants/files.ts)
# ---------------------------------------------------------------------------

CONFIG_FILE_NAME = ".clawcode"
CONFIG_DIR_NAME = ".claw"
MEMORY_DIR_NAME = "memory"
SKILLS_DIR_NAME = "skills"
PLUGINS_DIR_NAME = "plugins"
TRANSCRIPT_FILE = "transcript.json"
SESSION_FILE = "session.json"
GITIGNORE_FILE = ".gitignore"

# ---------------------------------------------------------------------------
# Keyboard shortcuts / key names (constants/keys.ts)
# ---------------------------------------------------------------------------

KEY_ESCAPE = "escape"
KEY_CTRL_C = "ctrl+c"
KEY_CTRL_D = "ctrl+d"
KEY_CTRL_Z = "ctrl+z"
KEY_ENTER = "enter"
KEY_TAB = "tab"
KEY_UP = "up"
KEY_DOWN = "down"

# ---------------------------------------------------------------------------
# Spinner / progress verbs (constants/spinnerVerbs.ts)
# ---------------------------------------------------------------------------

SPINNER_VERBS: tuple[str, ...] = (
    "Thinking",
    "Reasoning",
    "Analysing",
    "Planning",
    "Working",
    "Computing",
    "Processing",
    "Generating",
)

# ---------------------------------------------------------------------------
# Turn completion verbs (constants/turnCompletionVerbs.ts)
# ---------------------------------------------------------------------------

TURN_COMPLETION_VERBS: tuple[str, ...] = (
    "Done",
    "Complete",
    "Finished",
    "Ready",
)

# ---------------------------------------------------------------------------
# Figures / UI characters (constants/figures.ts)
# ---------------------------------------------------------------------------

FIGURE_TICK = "✓"
FIGURE_CROSS = "✗"
FIGURE_ARROW = "→"
FIGURE_BULLET = "•"
FIGURE_ELLIPSIS = "…"
FIGURE_INFO = "ℹ"
FIGURE_WARNING = "⚠"

# ---------------------------------------------------------------------------
# XML tags used in prompts (constants/xml.ts)
# ---------------------------------------------------------------------------

XML_TOOL_RESULT = "tool_result"
XML_TOOL_USE = "tool_use"
XML_THINKING = "thinking"
XML_DOCUMENT = "document"
XML_SEARCH_RESULTS = "search_results"
XML_RESULT = "result"

__all__ = [
    # product
    "DOCS_URL",
    "GITHUB_URL",
    "PRODUCT_NAME",
    "PRODUCT_SHORT",
    "PRODUCT_VERSION",
    # files
    "CONFIG_DIR_NAME",
    "CONFIG_FILE_NAME",
    "GITIGNORE_FILE",
    "MEMORY_DIR_NAME",
    "PLUGINS_DIR_NAME",
    "SESSION_FILE",
    "SKILLS_DIR_NAME",
    "TRANSCRIPT_FILE",
    # keys
    "KEY_CTRL_C",
    "KEY_CTRL_D",
    "KEY_CTRL_Z",
    "KEY_DOWN",
    "KEY_ENTER",
    "KEY_ESCAPE",
    "KEY_TAB",
    "KEY_UP",
    # verbs
    "SPINNER_VERBS",
    "TURN_COMPLETION_VERBS",
    # figures
    "FIGURE_ARROW",
    "FIGURE_BULLET",
    "FIGURE_CROSS",
    "FIGURE_ELLIPSIS",
    "FIGURE_INFO",
    "FIGURE_TICK",
    "FIGURE_WARNING",
    # xml
    "XML_DOCUMENT",
    "XML_RESULT",
    "XML_SEARCH_RESULTS",
    "XML_THINKING",
    "XML_TOOL_RESULT",
    "XML_TOOL_USE",
]
