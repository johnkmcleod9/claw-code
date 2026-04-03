"""
API client utilities.

Ports: services/api/client.ts, services/api/errorUtils.ts,
       services/api/errors.ts, services/api/emptyUsage.ts
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from src.utils.http import HttpResponse, build_url, http_get, http_post
from src.utils.retry import with_retry


# ---------------------------------------------------------------------------
# Error types (ports services/api/errors.ts)
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Base class for API errors."""
    def __init__(self, message: str, status: int = 0, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class RateLimitError(ApiError):
    """HTTP 429 — rate limit exceeded."""
    pass


class AuthError(ApiError):
    """HTTP 401/403 — authentication or authorization failure."""
    pass


class ServerError(ApiError):
    """HTTP 5xx — server-side error."""
    pass


def raise_for_status(response: HttpResponse, context: str = "") -> HttpResponse:
    """
    Raise a typed ApiError for non-2xx responses.

    Ports: services/api/errorUtils.ts
    """
    if response.ok:
        return response
    prefix = f"{context}: " if context else ""
    try:
        body = response.json
    except Exception:
        body = response.text

    msg = f"{prefix}HTTP {response.status}"
    if response.status == 429:
        raise RateLimitError(msg, response.status, body)
    if response.status in (401, 403):
        raise AuthError(msg, response.status, body)
    if response.status >= 500:
        raise ServerError(msg, response.status, body)
    raise ApiError(msg, response.status, body)


# ---------------------------------------------------------------------------
# Usage tracking (ports services/api/emptyUsage.ts)
# ---------------------------------------------------------------------------

@dataclass
class UsageStats:
    """Token and cost usage for an API call."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = field(init=False)
    cached_tokens: int = 0
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "total_tokens", self.input_tokens + self.output_tokens)

    @classmethod
    def empty(cls) -> "UsageStats":
        return cls()

    def __add__(self, other: "UsageStats") -> "UsageStats":
        return UsageStats(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "UsageStats":
        usage = data.get("usage", {})
        return cls(
            input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)),
            output_tokens=usage.get("output_tokens", usage.get("completion_tokens", 0)),
            cached_tokens=usage.get("cache_read_input_tokens", 0),
        )


# ---------------------------------------------------------------------------
# Base API client
# ---------------------------------------------------------------------------

@dataclass
class ClientConfig:
    base_url: str
    api_key: str = ""
    default_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0
    max_retries: int = 3


class ApiClient:
    """
    Thin HTTP client for JSON APIs with auth, retry, and error handling.

    Ports: services/api/client.ts
    """

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._total_usage = UsageStats()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        hdrs: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.config.api_key:
            hdrs["Authorization"] = f"Bearer {self.config.api_key}"
        hdrs.update(self.config.default_headers)
        if extra:
            hdrs.update(extra)
        return hdrs

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        """Perform a GET request and return the JSON response."""
        url = build_url(self.config.base_url, path, params)

        @with_retry(max_attempts=self.config.max_retries, retryable=(Exception,))
        def _call() -> dict[str, Any]:
            resp = http_get(url, headers=self._headers(), timeout=self.config.timeout)
            raise_for_status(resp, f"GET {path}")
            return resp.json

        return _call()

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """Perform a POST request and return the JSON response."""
        url = build_url(self.config.base_url, path)

        @with_retry(max_attempts=self.config.max_retries, retryable=(ServerError, OSError))
        def _call() -> dict[str, Any]:
            resp = http_post(url, body=body, headers=self._headers(), timeout=self.config.timeout)
            raise_for_status(resp, f"POST {path}")
            data = resp.json
            usage = UsageStats.from_response(data)
            self._total_usage = self._total_usage + usage
            return data

        return _call()

    @property
    def total_usage(self) -> UsageStats:
        return self._total_usage

    def reset_usage(self) -> None:
        self._total_usage = UsageStats()


__all__ = [
    "ApiError",
    "RateLimitError",
    "AuthError",
    "ServerError",
    "raise_for_status",
    "UsageStats",
    "ClientConfig",
    "ApiClient",
]
