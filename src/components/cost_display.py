"""
Cost and token usage display.

Ports: components/CostSummary.tsx, components/TokenUsage.tsx,
       components/CostThresholdDialog.tsx
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .formatter import Color, style, dim, bold, yellow, red, green, gray, terminal_width, table, Column


# ---------------------------------------------------------------------------
# Cost / usage data model
# ---------------------------------------------------------------------------

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )


@dataclass
class CostEntry:
    model: str
    usage: TokenUsage
    cost_usd: float
    label: str = ""


@dataclass
class CostSummary:
    entries: list[CostEntry] = field(default_factory=list)
    session_cost_usd: float = 0.0
    total_cost_usd: float = 0.0

    def total_usage(self) -> TokenUsage:
        result = TokenUsage()
        for e in self.entries:
            result = result + e.usage
        return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_tokens(n: int) -> str:
    """Format token count with K suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_cost(usd: float, warn_threshold: float = 1.0, danger_threshold: float = 5.0) -> str:
    """Format a USD cost with color based on amount."""
    s = f"${usd:.4f}"
    if usd >= danger_threshold:
        return red(s)
    if usd >= warn_threshold:
        return yellow(s)
    return green(s)


# ---------------------------------------------------------------------------
# Inline cost display (compact, one-liner)
# ---------------------------------------------------------------------------

def render_cost_inline(summary: CostSummary) -> str:
    """Compact one-line cost summary."""
    usage = summary.total_usage()
    tokens_str = dim(f"{_fmt_tokens(usage.input_tokens)}↑ {_fmt_tokens(usage.output_tokens)}↓")
    cost_str = _fmt_cost(summary.session_cost_usd)
    total_str = dim(f"total: {_fmt_cost(summary.total_cost_usd)}")
    return f"  {tokens_str}  {cost_str}  {total_str}"


# ---------------------------------------------------------------------------
# Detailed cost summary block
# ---------------------------------------------------------------------------

def render_cost_summary(summary: CostSummary, width: int | None = None) -> str:
    """Detailed cost summary with per-model breakdown."""
    w = width or terminal_width()
    lines: list[str] = []

    lines.append(bold("  Cost Summary"))
    lines.append(dim("  " + "─" * (w - 4)))

    usage = summary.total_usage()

    # Token breakdown
    lines.append(f"  {'Tokens:':<20} {_fmt_tokens(usage.input_tokens)} input, "
                 f"{_fmt_tokens(usage.output_tokens)} output")

    if usage.cache_read_tokens or usage.cache_write_tokens:
        lines.append(f"  {'Cache:':<20} {_fmt_tokens(usage.cache_read_tokens)} read, "
                     f"{_fmt_tokens(usage.cache_write_tokens)} write")

    lines.append("")

    # Per-model entries
    if summary.entries:
        for entry in summary.entries:
            model_str = style(entry.model, Color.CYAN)
            cost_str = _fmt_cost(entry.cost_usd)
            toks = f"{_fmt_tokens(entry.usage.input_tokens)}↑/{_fmt_tokens(entry.usage.output_tokens)}↓"
            label = f" ({entry.label})" if entry.label else ""
            lines.append(f"  {model_str:<30} {cost_str}  {dim(toks)}{dim(label)}")

        lines.append("")

    # Totals
    lines.append(f"  {'Session cost:':<20} {_fmt_cost(summary.session_cost_usd)}")
    if summary.total_cost_usd != summary.session_cost_usd:
        lines.append(f"  {'Total cost:':<20} {_fmt_cost(summary.total_cost_usd)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Threshold warning
# ---------------------------------------------------------------------------

def render_cost_threshold_warning(
    current_cost: float,
    threshold: float,
    action: str = "auto-approve",
) -> str:
    """Render a cost threshold warning (ports CostThresholdDialog)."""
    pct = (current_cost / threshold * 100) if threshold > 0 else 100
    bar_w = 30
    filled = int(bar_w * min(1.0, pct / 100))
    bar = style("█" * filled, Color.YELLOW) + style("░" * (bar_w - filled), Color.DIM)

    lines = [
        style("⚠  Cost threshold approaching", Color.YELLOW, Color.BOLD),
        f"   [{bar}] {pct:.0f}%",
        f"   Current: {_fmt_cost(current_cost)}  /  Threshold: {_fmt_cost(threshold)}",
        dim(f"   Auto-{action} will pause when threshold is reached."),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token context bar (for context window usage)
# ---------------------------------------------------------------------------

def render_context_bar(
    used_tokens: int,
    max_tokens: int,
    label: str = "Context",
    width: int | None = None,
) -> str:
    """Visual representation of context window usage."""
    w = width or terminal_width()
    bar_w = w - len(label) - 20
    pct = min(1.0, used_tokens / max(1, max_tokens))
    filled = int(bar_w * pct)

    if pct >= 0.90:
        color = Color.RED
    elif pct >= 0.70:
        color = Color.YELLOW
    else:
        color = Color.GREEN

    bar = style("█" * filled, color) + style("░" * (bar_w - filled), Color.DIM)
    count = f"{_fmt_tokens(used_tokens)}/{_fmt_tokens(max_tokens)}"
    pct_str = f"{pct * 100:.0f}%"

    return f"  {dim(label)} [{bar}] {style(count, color)} {dim(pct_str)}"


__all__ = [
    "TokenUsage",
    "CostEntry",
    "CostSummary",
    "render_cost_inline",
    "render_cost_summary",
    "render_cost_threshold_warning",
    "render_context_bar",
]
