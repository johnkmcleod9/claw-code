"""
Progress indicators and spinners for terminal output.

Ports: components/BashModeProgress.tsx, components/AgentProgressLine.tsx,
       components/ProgressBar.tsx, components/Spinner.tsx
"""
from __future__ import annotations

import sys
import time
import threading
from contextlib import contextmanager
from typing import Iterator

from .formatter import Color, style, strip_ansi, terminal_width


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

SPINNER_FRAMES = {
    "dots":   ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "line":   ["-", "\\", "|", "/"],
    "circle": ["◐", "◓", "◑", "◒"],
    "arrow":  ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
    "braille":["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
    "bounce": ["⠁", "⠂", "⠄", "⡀", "⢀", "⠠", "⠐", "⠈"],
    "claude": ["◇", "◈", "◆", "◈"],
}


class Spinner:
    """
    Animated terminal spinner with optional message.

    Usage:
        spinner = Spinner("Loading…")
        spinner.start()
        ...
        spinner.stop("Done!")
    """

    def __init__(
        self,
        message: str = "",
        style_name: str = "dots",
        color: Color = Color.CYAN,
        fps: float = 12.0,
        stream=None,
    ):
        self.message = message
        self.frames = SPINNER_FRAMES.get(style_name, SPINNER_FRAMES["dots"])
        self.color = color
        self.interval = 1.0 / fps
        self.stream = stream or sys.stderr
        self._frame_idx = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _render(self) -> str:
        frame = self.frames[self._frame_idx % len(self.frames)]
        colored = style(frame, self.color)
        msg = f" {self.message}" if self.message else ""
        return f"\r{colored}{msg}"

    def _run(self) -> None:
        while self._running:
            with self._lock:
                self.stream.write(self._render())
                self.stream.flush()
                self._frame_idx += 1
            time.sleep(self.interval)

    def start(self) -> "Spinner":
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def update(self, message: str) -> None:
        with self._lock:
            self.message = message

    def stop(self, final_message: str = "", success: bool = True) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        # Clear spinner line
        self.stream.write("\r" + " " * (terminal_width()) + "\r")
        if final_message:
            icon = style("✓", Color.GREEN) if success else style("✗", Color.RED)
            self.stream.write(f"{icon} {final_message}\n")
        self.stream.flush()

    def fail(self, message: str = "") -> None:
        self.stop(final_message=message or "Failed", success=False)


@contextmanager
def spinner(
    message: str = "",
    final_message: str = "",
    style_name: str = "claude",
    color: Color = Color.CYAN,
) -> Iterator[Spinner]:
    """Context manager spinner — stops automatically on exit."""
    s = Spinner(message=message, style_name=style_name, color=color)
    s.start()
    try:
        yield s
        s.stop(final_message=final_message or message, success=True)
    except Exception:
        s.fail(f"Failed: {message}")
        raise


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

class ProgressBar:
    """
    Simple terminal progress bar.

    Usage:
        bar = ProgressBar(total=100, label="Processing")
        bar.update(50)
        bar.finish()
    """

    def __init__(
        self,
        total: int,
        label: str = "",
        width: int | None = None,
        fill: str = "█",
        empty: str = "░",
        color: Color = Color.BLUE,
        stream=None,
    ):
        self.total = max(1, total)
        self.label = label
        self.bar_width = width or max(20, terminal_width() - len(label) - 20)
        self.fill = fill
        self.empty = empty
        self.color = color
        self.stream = stream or sys.stderr
        self._current = 0
        self._finished = False

    def _render(self, current: int) -> str:
        pct = min(1.0, current / self.total)
        filled = int(self.bar_width * pct)
        empty = self.bar_width - filled

        bar = style(self.fill * filled, self.color) + style(self.empty * empty, Color.DIM)
        pct_str = f"{pct * 100:5.1f}%"

        label = f"{self.label} " if self.label else ""
        counter = f" {current}/{self.total}"
        return f"\r{label}[{bar}]{counter} {pct_str}"

    def update(self, current: int | None = None, increment: int = 0) -> None:
        if current is not None:
            self._current = current
        else:
            self._current = min(self.total, self._current + increment)
        self.stream.write(self._render(self._current))
        self.stream.flush()

    def increment(self, n: int = 1) -> None:
        self.update(increment=n)

    def finish(self, message: str = "") -> None:
        if not self._finished:
            self.update(self.total)
            self.stream.write("\n")
            if message:
                self.stream.write(f"{style('✓', Color.GREEN)} {message}\n")
            self.stream.flush()
            self._finished = True

    @contextmanager
    @staticmethod
    def context(total: int, label: str = "", **kwargs) -> Iterator["ProgressBar"]:
        bar = ProgressBar(total=total, label=label, **kwargs)
        try:
            yield bar
            bar.finish()
        except Exception:
            bar.stream.write("\n")
            raise


# ---------------------------------------------------------------------------
# Step-based progress (like agent task lists)
# ---------------------------------------------------------------------------

class TaskList:
    """
    Display a list of tasks with status indicators.

    Ports: components/AgentProgressLine.tsx
    """

    PENDING  = style("○", Color.DIM)
    RUNNING  = style("◉", Color.CYAN)
    DONE     = style("✓", Color.GREEN)
    FAILED   = style("✗", Color.RED)
    SKIPPED  = style("–", Color.GRAY)

    def __init__(self, tasks: list[str], stream=None):
        self.tasks = tasks
        self.statuses: list[str] = ["pending"] * len(tasks)
        self.stream = stream or sys.stdout

    def _icon(self, status: str) -> str:
        return {
            "pending": self.PENDING,
            "running": self.RUNNING,
            "done":    self.DONE,
            "failed":  self.FAILED,
            "skipped": self.SKIPPED,
        }.get(status, self.PENDING)

    def set_status(self, idx: int, status: str) -> None:
        self.statuses[idx] = status
        self._redraw()

    def _redraw(self) -> None:
        lines = []
        for i, (task, status) in enumerate(zip(self.tasks, self.statuses)):
            icon = self._icon(status)
            color = Color.DIM if status in ("pending", "skipped") else None
            label = style(task, color) if color else task
            lines.append(f"  {icon} {label}")
        output = "\n".join(lines)
        # Move cursor up and rewrite
        if hasattr(self, "_last_line_count"):
            up = f"\033[{self._last_line_count}A"
            self.stream.write(up)
        self.stream.write(output + "\n")
        self.stream.flush()
        self._last_line_count = len(lines)

    def start(self) -> None:
        self._redraw()

    def begin(self, idx: int) -> None:
        self.set_status(idx, "running")

    def complete(self, idx: int) -> None:
        self.set_status(idx, "done")

    def fail(self, idx: int) -> None:
        self.set_status(idx, "failed")

    def skip(self, idx: int) -> None:
        self.set_status(idx, "skipped")


# ---------------------------------------------------------------------------
# Simple agent progress line (one-liner)
# ---------------------------------------------------------------------------

def agent_progress(
    tool: str,
    target: str = "",
    status: str = "running",
    elapsed: float | None = None,
) -> str:
    """
    Format a single agent progress line.

    Example: ◉ bash › echo hello  (1.2s)
    """
    icons = {"running": "◉", "done": "✓", "failed": "✗"}
    colors = {"running": Color.CYAN, "done": Color.GREEN, "failed": Color.RED}

    icon = style(icons.get(status, "·"), colors.get(status, Color.WHITE))
    tool_str = style(tool, Color.BOLD)
    sep = style(" › ", Color.DIM)
    elapsed_str = ""
    if elapsed is not None:
        elapsed_str = style(f"  ({elapsed:.1f}s)", Color.DIM)

    return f"{icon} {tool_str}{sep}{target}{elapsed_str}"


__all__ = [
    "SPINNER_FRAMES",
    "Spinner", "spinner",
    "ProgressBar",
    "TaskList",
    "agent_progress",
]
