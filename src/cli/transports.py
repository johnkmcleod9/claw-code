"""
CLI transport layer.

Provides abstractions for sending events from the agent process to
consuming clients via SSE, WebSocket, or batched HTTP.

Ports: cli/transports/HybridTransport.ts, cli/transports/SSETransport.ts,
       cli/transports/WebSocketTransport.ts,
       cli/transports/SerialBatchEventUploader.ts,
       cli/transports/WorkerStateUploader.ts,
       cli/transports/ccrClient.ts, cli/transports/transportUtils.ts
"""
from __future__ import annotations

import json
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Transport event
# ---------------------------------------------------------------------------

@dataclass
class TransportEvent:
    """A single event dispatched over a transport."""
    event_type: str
    data: Any
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.event_type,
                "data": self.data,
                "seq": self.sequence,
                "ts": self.timestamp,
            },
            ensure_ascii=False,
        )

    def to_sse(self) -> str:
        """Format as SSE wire format."""
        return f"event: {self.event_type}\ndata: {self.to_json()}\n\n"


# ---------------------------------------------------------------------------
# Base transport
# ---------------------------------------------------------------------------

class BaseTransport(ABC):
    """Abstract base for all transports."""

    def __init__(self) -> None:
        self._closed = False
        self._seq = 0

    @abstractmethod
    def send(self, event: TransportEvent) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def emit(self, event_type: str, data: Any = None) -> None:
        self._seq += 1
        self.send(TransportEvent(event_type=event_type, data=data, sequence=self._seq))

    @property
    def is_closed(self) -> bool:
        return self._closed


# ---------------------------------------------------------------------------
# In-memory transport (testing / local)
# ---------------------------------------------------------------------------

class InMemoryTransport(BaseTransport):
    """Collects events in a list — useful for tests and local runs."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[TransportEvent] = []

    def send(self, event: TransportEvent) -> None:
        if not self._closed:
            self.events.append(event)

    def close(self) -> None:
        self._closed = True

    def drain(self) -> list[TransportEvent]:
        events, self.events = self.events, []
        return events


# ---------------------------------------------------------------------------
# SSE transport stub (cli/transports/SSETransport.ts)
# ---------------------------------------------------------------------------

class SSETransport(BaseTransport):
    """
    Server-Sent Events transport.

    In a real deployment this writes to an HTTP response stream.
    Here we accept any writable text stream.
    """

    def __init__(self, stream) -> None:
        super().__init__()
        self._stream = stream
        self._lock = threading.Lock()

    def send(self, event: TransportEvent) -> None:
        if self._closed:
            return
        with self._lock:
            self._stream.write(event.to_sse())
            if hasattr(self._stream, "flush"):
                self._stream.flush()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            try:
                self._stream.write("event: close\ndata: {}\n\n")
                self._stream.flush()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Batch uploader (cli/transports/SerialBatchEventUploader.ts)
# ---------------------------------------------------------------------------

class SerialBatchUploader(BaseTransport):
    """
    Buffers events and uploads them in batches via an HTTP callback.

    Ports: cli/transports/SerialBatchEventUploader.ts
    """

    def __init__(
        self,
        upload_fn,  # Callable[[list[TransportEvent]], None]
        max_batch: int = 50,
        flush_interval: float = 1.0,
    ) -> None:
        super().__init__()
        self._upload_fn = upload_fn
        self._max_batch = max_batch
        self._flush_interval = flush_interval
        self._buffer: list[TransportEvent] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._schedule_flush()

    def send(self, event: TransportEvent) -> None:
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= self._max_batch:
                self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        try:
            self._upload_fn(batch)
        except Exception:
            pass  # Never crash the caller

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _schedule_flush(self) -> None:
        if self._closed:
            return
        self._timer = threading.Timer(self._flush_interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        self.flush()
        self._schedule_flush()

    def close(self) -> None:
        self._closed = True
        if self._timer:
            self._timer.cancel()
        self.flush()


# ---------------------------------------------------------------------------
# Hybrid transport (cli/transports/HybridTransport.ts)
# ---------------------------------------------------------------------------

class HybridTransport(BaseTransport):
    """
    Fans events out to multiple child transports.

    Ports: cli/transports/HybridTransport.ts
    """

    def __init__(self, *transports: BaseTransport) -> None:
        super().__init__()
        self._transports = list(transports)

    def add(self, transport: BaseTransport) -> None:
        self._transports.append(transport)

    def send(self, event: TransportEvent) -> None:
        for t in self._transports:
            if not t.is_closed:
                try:
                    t.send(event)
                except Exception:
                    pass

    def close(self) -> None:
        self._closed = True
        for t in self._transports:
            try:
                t.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Transport utilities (cli/transports/transportUtils.ts)
# ---------------------------------------------------------------------------

def pick_transport(
    mode: str,
    **kwargs: Any,
) -> BaseTransport:
    """
    Factory: select a transport by name.

    Supported modes: "memory", "sse", "batch"
    """
    if mode == "memory":
        return InMemoryTransport()
    if mode == "sse":
        stream = kwargs.get("stream")
        if stream is None:
            raise ValueError("SSE transport requires stream= kwarg")
        return SSETransport(stream)
    if mode == "batch":
        upload_fn = kwargs.get("upload_fn")
        if upload_fn is None:
            raise ValueError("batch transport requires upload_fn= kwarg")
        return SerialBatchUploader(
            upload_fn=upload_fn,
            max_batch=kwargs.get("max_batch", 50),
            flush_interval=kwargs.get("flush_interval", 1.0),
        )
    raise ValueError(f"Unknown transport mode: {mode!r}")


__all__ = [
    "BaseTransport",
    "HybridTransport",
    "InMemoryTransport",
    "SSETransport",
    "SerialBatchUploader",
    "TransportEvent",
    "pick_transport",
]
