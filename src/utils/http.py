"""
HTTP request helpers with retry support.

Ports: utils/api.ts, utils/apiPreconnect.ts
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .retry import retry_sync, with_retry


@dataclass(frozen=True)
class HttpResponse:
    """Lightweight HTTP response wrapper."""
    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        # Try to sniff encoding from Content-Type
        encoding = "utf-8"
        if "charset=" in content_type:
            try:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            except Exception:
                pass
        return self.body.decode(encoding, errors="replace")

    @property
    def json(self) -> Any:
        return json.loads(self.body)

    def raise_for_status(self) -> "HttpResponse":
        if not self.ok:
            raise urllib.error.HTTPError(
                url="", code=self.status, msg=f"HTTP {self.status}", hdrs=None, fp=None  # type: ignore[arg-type]
            )
        return self


_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    max_attempts: int = 3,
) -> HttpResponse:
    """
    Perform an HTTP GET request with automatic retry on transient errors.

    Args:
        url: Target URL.
        headers: Optional extra request headers.
        timeout: Request timeout in seconds.
        max_attempts: Number of retry attempts on failure.
    """
    def _do_get() -> HttpResponse:
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return HttpResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    body=resp.read(),
                )
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRYABLE_STATUS:
                raise  # let retry handle it
            return HttpResponse(
                status=exc.code,
                headers={},
                body=b"",
            )

    return retry_sync(_do_get, max_attempts=max_attempts, retryable=(urllib.error.HTTPError, OSError))


def http_post(
    url: str,
    *,
    body: bytes | dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    max_attempts: int = 3,
) -> HttpResponse:
    """
    Perform an HTTP POST request.

    If *body* is a dict it is JSON-encoded and Content-Type is set automatically.
    """
    hdrs = dict(headers or {})
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif isinstance(body, bytes):
        data = body
    else:
        data = None

    def _do_post() -> HttpResponse:
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return HttpResponse(
                    status=resp.status,
                    headers=dict(resp.headers),
                    body=resp.read(),
                )
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRYABLE_STATUS:
                raise
            return HttpResponse(status=exc.code, headers={}, body=b"")

    return retry_sync(_do_post, max_attempts=max_attempts, retryable=(urllib.error.HTTPError, OSError))


def build_url(base: str, path: str = "", params: dict[str, str] | None = None) -> str:
    """
    Construct a URL from a base, optional path, and query parameters.

    Example::

        build_url("https://api.example.com", "/v1/chat", {"model": "gpt-4"})
        # → "https://api.example.com/v1/chat?model=gpt-4"
    """
    url = base.rstrip("/") + ("/" + path.lstrip("/") if path else "")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def parse_sse_line(line: str) -> tuple[str, str] | None:
    """
    Parse a Server-Sent Events data line.

    Returns ``(field, value)`` or None for empty/comment lines.
    """
    line = line.rstrip("\n\r")
    if not line or line.startswith(":"):
        return None
    if ":" in line:
        field, _, value = line.partition(":")
        return field.strip(), value.lstrip(" ")
    return line.strip(), ""


__all__ = [
    "HttpResponse",
    "http_get",
    "http_post",
    "build_url",
    "parse_sse_line",
]
