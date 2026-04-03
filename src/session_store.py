"""
Session persistence — save and restore full conversations across restarts.

WP 8615: Full save/restore with:
- Rich message serialisation (role, content, tool_calls, tool_call_id)
- Session index for listing/picking recent sessions
- Project-scoped sessions (keyed to workdir)
- Metadata: model, workdir, timestamp, token counts, title
- Auto-title from first user message
- CLI helpers: list, show, delete sessions
- Graceful migration from old minimal StoredSession format
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ── Public storage roots ───────────────────────────────────────────────────

DEFAULT_SESSION_DIR = Path.home() / ".claw" / "sessions"
_INDEX_FILE = "index.json"
_SESSION_VERSION = 2


# ── Data models ────────────────────────────────────────────────────────────

@dataclass
class StoredMessage:
    """A single message in the conversation, serialisation-safe."""
    role: str
    content: str | list[Any]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # for tool role

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StoredMessage":
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=d.get("tool_calls", []),
            tool_call_id=d.get("tool_call_id"),
            name=d.get("name"),
        )

    @classmethod
    def from_message(cls, msg: Any) -> "StoredMessage":
        """Convert a providers.base.Message to StoredMessage."""
        tool_calls: list[dict[str, Any]] = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if hasattr(tc, "name"):
                    tool_calls.append({
                        "id": getattr(tc, "id", ""),
                        "name": tc.name,
                        "arguments": getattr(tc, "arguments", {}),
                    })
        content = msg.content if msg.content is not None else ""
        return cls(
            role=msg.role,
            content=content,
            tool_calls=tool_calls,
            tool_call_id=getattr(msg, "tool_call_id", None),
            name=getattr(msg, "name", None),
        )


@dataclass
class StoredSession:
    """A complete saved conversation session."""
    session_id: str
    version: int = _SESSION_VERSION
    title: str = ""
    model: str = ""
    workdir: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # Rich messages (new format)
    stored_messages: list[StoredMessage] = field(default_factory=list)
    # Token / cost accounting
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    # Legacy compat: raw string messages from v1
    messages: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "session_id": self.session_id,
            "title": self.title,
            "model": self.model,
            "workdir": self.workdir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.stored_messages],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_cost_usd": self.total_cost_usd,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StoredSession":
        version = d.get("version", 1)
        if version >= 2:
            msgs = [StoredMessage.from_dict(m) for m in d.get("messages", [])]
        else:
            # Legacy v1: messages were raw strings
            msgs = [
                StoredMessage(role="user", content=m)
                for m in d.get("messages", [])
            ]
        return cls(
            session_id=d["session_id"],
            version=version,
            title=d.get("title", ""),
            model=d.get("model", ""),
            workdir=d.get("workdir", ""),
            created_at=d.get("created_at", 0.0),
            updated_at=d.get("updated_at", 0.0),
            stored_messages=msgs,
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            total_cost_usd=d.get("total_cost_usd", 0.0),
        )

    @property
    def message_count(self) -> int:
        return len(self.stored_messages)

    @property
    def display_title(self) -> str:
        if self.title:
            return self.title
        if self.stored_messages:
            for m in self.stored_messages:
                if m.role == "user" and isinstance(m.content, str) and m.content.strip():
                    return m.content.strip()[:60]
        return f"Session {self.session_id[:8]}"

    def age_label(self) -> str:
        """Human-readable age for display."""
        delta = time.time() - self.updated_at
        if delta < 60:
            return "just now"
        if delta < 3600:
            return f"{int(delta / 60)}m ago"
        if delta < 86400:
            return f"{int(delta / 3600)}h ago"
        return f"{int(delta / 86400)}d ago"


# ── Index management ───────────────────────────────────────────────────────

@dataclass
class SessionIndexEntry:
    session_id: str
    title: str
    model: str
    workdir: str
    created_at: float
    updated_at: float
    message_count: int
    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionIndexEntry":
        return cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__})  # type: ignore[attr-defined]

    @classmethod
    def from_session(cls, s: StoredSession) -> "SessionIndexEntry":
        return cls(
            session_id=s.session_id,
            title=s.display_title,
            model=s.model,
            workdir=s.workdir,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=s.message_count,
            input_tokens=s.input_tokens,
            output_tokens=s.output_tokens,
        )


def _load_index(directory: Path) -> list[SessionIndexEntry]:
    index_path = directory / _INDEX_FILE
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text())
        return [SessionIndexEntry.from_dict(e) for e in data]
    except Exception:
        return []


def _save_index(directory: Path, entries: list[SessionIndexEntry]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    index_path = directory / _INDEX_FILE
    index_path.write_text(json.dumps([e.to_dict() for e in entries], indent=2))


def _upsert_index(directory: Path, session: StoredSession) -> None:
    """Add or update this session in the index."""
    entries = _load_index(directory)
    new_entry = SessionIndexEntry.from_session(session)
    updated = False
    for i, e in enumerate(entries):
        if e.session_id == session.session_id:
            entries[i] = new_entry
            updated = True
            break
    if not updated:
        entries.append(new_entry)
    # Sort by updated_at descending (most recent first)
    entries.sort(key=lambda e: e.updated_at, reverse=True)
    _save_index(directory, entries)


def _remove_from_index(directory: Path, session_id: str) -> None:
    entries = _load_index(directory)
    entries = [e for e in entries if e.session_id != session_id]
    _save_index(directory, entries)


# ── Core API ───────────────────────────────────────────────────────────────

def make_session_id(workdir: str | Path | None = None, model: str = "") -> str:
    """
    Generate a deterministic-ish session ID.
    Uses workdir + model + timestamp for reasonable uniqueness.
    """
    ts = str(time.time())
    base = f"{workdir or ''}:{model}:{ts}"
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def save_session(session: StoredSession, directory: Path | None = None) -> Path:
    """
    Persist a session to disk and update the index.

    Args:
        session: The session to save.
        directory: Override the default session directory.

    Returns:
        Path to the saved session file.
    """
    target_dir = directory or DEFAULT_SESSION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    session.updated_at = time.time()
    session.version = _SESSION_VERSION

    path = target_dir / f"{session.session_id}.json"
    path.write_text(json.dumps(session.to_dict(), indent=2))

    _upsert_index(target_dir, session)
    return path


def load_session(session_id: str, directory: Path | None = None) -> StoredSession:
    """
    Load a session by ID.

    Raises:
        FileNotFoundError: If the session file does not exist.
        ValueError: If the session file is corrupt.
    """
    target_dir = directory or DEFAULT_SESSION_DIR
    path = target_dir / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Session {session_id!r} not found at {path}")
    try:
        data = json.loads(path.read_text())
        return StoredSession.from_dict(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupt session file {path}: {e}") from e


def list_sessions(
    directory: Path | None = None,
    workdir: str | None = None,
    limit: int = 20,
) -> list[SessionIndexEntry]:
    """
    List recent sessions, optionally filtered by workdir.

    Args:
        directory: Override the default session directory.
        workdir: If set, only return sessions in this workdir.
        limit: Maximum number of sessions to return.

    Returns:
        List of index entries sorted by updated_at descending.
    """
    target_dir = directory or DEFAULT_SESSION_DIR
    entries = _load_index(target_dir)
    if workdir:
        entries = [e for e in entries if e.workdir == str(workdir)]
    return entries[:limit]


def delete_session(session_id: str, directory: Path | None = None) -> bool:
    """
    Delete a session file and remove from index.

    Returns:
        True if deleted, False if not found.
    """
    target_dir = directory or DEFAULT_SESSION_DIR
    path = target_dir / f"{session_id}.json"
    existed = path.exists()
    if existed:
        path.unlink()
    _remove_from_index(target_dir, session_id)
    return existed


def auto_title_from_messages(messages: list[Any]) -> str:
    """
    Generate an auto-title from the first meaningful user message.
    Works with both Message objects and StoredMessage objects.
    """
    for msg in messages:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", "")
        if role == "user" and isinstance(content, str) and content.strip():
            text = content.strip()
            # Take first line, max 60 chars
            first_line = text.splitlines()[0][:60]
            return first_line
    return ""


# ── Helpers for repl.py integration ───────────────────────────────────────

def session_from_repl(
    session_id: str,
    messages: list[Any],  # list[providers.base.Message]
    model: str,
    workdir: str | Path,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_cost_usd: float = 0.0,
    title: str = "",
) -> StoredSession:
    """
    Build a StoredSession from the repl's live state.

    Converts Message objects to StoredMessage objects for serialisation.
    """
    stored_messages = [StoredMessage.from_message(m) for m in messages]
    auto_title = title or auto_title_from_messages(messages)
    return StoredSession(
        session_id=session_id,
        title=auto_title,
        model=model,
        workdir=str(workdir),
        stored_messages=stored_messages,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost_usd=total_cost_usd,
    )


def restore_messages_to_provider(
    session: StoredSession,
    message_class: type,
) -> list[Any]:
    """
    Convert StoredMessages back to provider Message objects.

    Args:
        session: The loaded session.
        message_class: The Message class from providers.base.

    Returns:
        List of Message objects ready for the provider.
    """
    result = []
    for sm in session.stored_messages:
        try:
            msg = message_class(
                role=sm.role,
                content=sm.content,
            )
            # Restore tool_call_id if present
            if sm.tool_call_id is not None and hasattr(msg, "tool_call_id"):
                object.__setattr__(msg, "tool_call_id", sm.tool_call_id)
            result.append(msg)
        except Exception:
            # Skip messages that can't be restored rather than crashing
            pass
    return result


# ── CLI display helpers ────────────────────────────────────────────────────

def format_session_list(entries: list[SessionIndexEntry], color: bool = True) -> str:
    """Format session list for terminal display."""
    if not entries:
        return "  (no saved sessions)"

    lines: list[str] = []
    for i, e in enumerate(entries):
        idx = f"{i + 1:2}."
        sid = e.session_id[:8]
        title = (e.title or "(untitled)")[:50]
        model = (e.model or "?")[:20]
        age = _age_label(e.updated_at)
        msgs = e.message_count
        cost_str = ""

        if color:
            lines.append(
                f"  {idx} \033[36m{sid}\033[0m  \033[1m{title:<50}\033[0m"
                f"  {model:<20}  {age:<10}  {msgs} msgs"
            )
        else:
            lines.append(
                f"  {idx} {sid}  {title:<50}  {model:<20}  {age:<10}  {msgs} msgs"
            )

    return "\n".join(lines)


def _age_label(ts: float) -> str:
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    return f"{int(delta / 86400)}d ago"
