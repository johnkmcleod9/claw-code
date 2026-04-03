"""
Suggestion hooks for autocomplete / file suggestions.

Ports: hooks/fileSuggestions.ts, hooks/unifiedSuggestions.ts,
       hooks/useAfterFirstRender.ts
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Sequence

from .state_hooks import Signal, Derived


# ---------------------------------------------------------------------------
# File suggestions
# ---------------------------------------------------------------------------

def get_file_suggestions(
    query: str,
    cwd: Path | None = None,
    max_results: int = 20,
    include_hidden: bool = False,
) -> list[str]:
    """
    Get file path suggestions matching a query.

    Ports: hooks/fileSuggestions.ts
    """
    root = cwd or Path.cwd()
    query_lower = query.lower().strip()
    results: list[tuple[int, str]] = []

    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden directories
            if not include_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            for name in filenames:
                if not include_hidden and name.startswith("."):
                    continue

                full = Path(dirpath) / name
                try:
                    rel = str(full.relative_to(root))
                except ValueError:
                    rel = str(full)

                # Score match
                name_lower = name.lower()
                rel_lower = rel.lower()

                score = 0
                if query_lower in name_lower:
                    score += 3
                if query_lower in rel_lower:
                    score += 1
                if name_lower.startswith(query_lower):
                    score += 5

                if score > 0 or not query_lower:
                    results.append((score, rel))

            if len(results) >= max_results * 2:
                break

    except PermissionError:
        pass

    results.sort(key=lambda x: (-x[0], x[1]))
    return [path for _, path in results[:max_results]]


# ---------------------------------------------------------------------------
# Unified suggestions (file + slash commands + @-mentions)
# ---------------------------------------------------------------------------

class SuggestionType:
    FILE    = "file"
    COMMAND = "command"
    MEMORY  = "memory"
    MODEL   = "model"
    SKILL   = "skill"


class Suggestion:
    __slots__ = ("type", "value", "label", "description", "icon")

    def __init__(
        self,
        type: str,
        value: str,
        label: str = "",
        description: str = "",
        icon: str = "",
    ):
        self.type = type
        self.value = value
        self.label = label or value
        self.description = description
        self.icon = icon

    def __repr__(self) -> str:
        return f"Suggestion({self.type}:{self.value!r})"


class UnifiedSuggestionEngine:
    """
    Unified autocomplete suggestion engine.

    Ports: hooks/unifiedSuggestions.ts
    Combines file suggestions, slash commands, and @-references.
    """

    SLASH_COMMANDS = {
        "/help":    ("Show help", "?"),
        "/clear":   ("Clear history", "🗑"),
        "/model":   ("Switch model", "🤖"),
        "/cost":    ("Show costs", "💰"),
        "/status":  ("Session status", "ℹ"),
        "/compact": ("Compact context", "📦"),
        "/exit":    ("Exit session", "🚪"),
        "/debug":   ("Toggle debug", "🔧"),
    }

    def __init__(
        self,
        cwd: Path | None = None,
        custom_commands: dict[str, tuple[str, str]] | None = None,
    ):
        self._cwd = cwd or Path.cwd()
        self._commands = dict(self.SLASH_COMMANDS)
        if custom_commands:
            self._commands.update(custom_commands)

    def suggest(
        self,
        text: str,
        max_results: int = 10,
    ) -> list[Suggestion]:
        """
        Get suggestions for the current input text.

        Handles:
        - "/" prefix → slash commands
        - "@" prefix → file references
        - "#" prefix → context files
        - Everything else → generic file suggestions
        """
        if not text:
            return []

        text = text.strip()

        if text.startswith("/"):
            return self._slash_suggestions(text[1:], max_results)
        elif text.startswith("@") or text.startswith("#"):
            return self._file_ref_suggestions(text[1:], max_results)
        else:
            # Inline file completion
            paths = get_file_suggestions(text, cwd=self._cwd, max_results=max_results)
            return [
                Suggestion(SuggestionType.FILE, p, icon="📄")
                for p in paths
            ]

    def _slash_suggestions(self, query: str, limit: int) -> list[Suggestion]:
        q = query.lower()
        matches = []
        for cmd, (desc, icon) in self._commands.items():
            cmd_lower = cmd.lstrip("/").lower()
            if not q or cmd_lower.startswith(q) or q in cmd_lower:
                matches.append(Suggestion(
                    type=SuggestionType.COMMAND,
                    value=cmd,
                    label=cmd,
                    description=desc,
                    icon=icon,
                ))
        return matches[:limit]

    def _file_ref_suggestions(self, query: str, limit: int) -> list[Suggestion]:
        paths = get_file_suggestions(query, cwd=self._cwd, max_results=limit)
        return [
            Suggestion(SuggestionType.FILE, p, label=f"@{p}", icon="📄")
            for p in paths
        ]


# ---------------------------------------------------------------------------
# Reactive suggestion state
# ---------------------------------------------------------------------------

class SuggestionState:
    """
    Reactive suggestion state for UI integration.
    """

    def __init__(self, engine: UnifiedSuggestionEngine | None = None):
        self.engine = engine or UnifiedSuggestionEngine()
        self.query = Signal("")
        self.suggestions: Signal[list[Suggestion]] = Signal([])
        self.selected_index = Signal(0)
        self.is_open = Signal(False)

        # Auto-update suggestions when query changes
        self.query.subscribe(self._on_query_change)

    def _on_query_change(self, q: str) -> None:
        if not q.strip():
            self.suggestions.set([])
            self.is_open.set(False)
            return

        results = self.engine.suggest(q)
        self.suggestions.set(results)
        self.is_open.set(bool(results))
        self.selected_index.set(0)

    def set_query(self, q: str) -> None:
        self.query.set(q)

    def move_up(self) -> None:
        subs = self.suggestions.get()
        if subs:
            idx = (self.selected_index.get() - 1) % len(subs)
            self.selected_index.set(idx)

    def move_down(self) -> None:
        subs = self.suggestions.get()
        if subs:
            idx = (self.selected_index.get() + 1) % len(subs)
            self.selected_index.set(idx)

    def accept(self) -> Suggestion | None:
        subs = self.suggestions.get()
        idx = self.selected_index.get()
        if subs and 0 <= idx < len(subs):
            selected = subs[idx]
            self.close()
            return selected
        return None

    def close(self) -> None:
        self.is_open.set(False)
        self.suggestions.set([])
        self.selected_index.set(0)


__all__ = [
    "get_file_suggestions",
    "SuggestionType",
    "Suggestion",
    "UnifiedSuggestionEngine",
    "SuggestionState",
]
