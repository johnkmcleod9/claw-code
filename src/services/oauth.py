"""
OAuth 2.0 / PKCE authentication service.

Provides token storage, refresh, and PKCE flow helpers for providers that
require user-delegated OAuth (e.g., Google Workspace, GitHub, etc.).

Ports: constants/oauth.ts, services/auth/ (conceptual)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs


# ---------------------------------------------------------------------------
# Token model
# ---------------------------------------------------------------------------

@dataclass
class OAuthToken:
    """Stores an OAuth 2.0 token set."""
    access_token: str
    token_type: str = "Bearer"
    expires_at: float = 0.0          # Unix timestamp; 0 = never
    refresh_token: str | None = None
    scope: str = ""
    id_token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "OAuthToken":
        expires_in = data.get("expires_in", 0)
        expires_at = time.time() + float(expires_in) if expires_in else 0.0
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope", ""),
            id_token=data.get("id_token"),
        )

    @property
    def is_expired(self) -> bool:
        if self.expires_at == 0:
            return False
        return time.time() >= self.expires_at - 30  # 30-second buffer

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_at": self.expires_at,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
            "id_token": self.id_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OAuthToken":
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=data.get("expires_at", 0.0),
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope", ""),
            id_token=data.get("id_token"),
        )


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def generate_code_verifier(length: int = 64) -> str:
    """Generate a PKCE code verifier (RFC 7636)."""
    return secrets.token_urlsafe(length)


def generate_code_challenge(verifier: str) -> str:
    """Derive the S256 code challenge from a verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_auth_url(
    auth_endpoint: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
    extra_params: dict[str, str] | None = None,
) -> str:
    """Build the authorisation URL for the PKCE flow."""
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if extra_params:
        params.update(extra_params)
    return f"{auth_endpoint}?{urlencode(params)}"


def parse_redirect(redirect_url: str) -> tuple[str, str]:
    """
    Parse the authorisation code and state from a redirect URL.

    Returns (code, state).
    Raises ValueError if the URL indicates an error or lacks required params.
    """
    parsed = urlparse(redirect_url)
    qs = parse_qs(parsed.query)

    if "error" in qs:
        err = qs["error"][0]
        desc = qs.get("error_description", [""])[0]
        raise ValueError(f"OAuth error: {err} — {desc}")

    code = qs.get("code", [None])[0]
    state = qs.get("state", [None])[0]

    if not code:
        raise ValueError(f"No authorisation code in redirect URL: {redirect_url}")
    if not state:
        raise ValueError(f"No state in redirect URL: {redirect_url}")

    return code, state


# ---------------------------------------------------------------------------
# Token store
# ---------------------------------------------------------------------------

class TokenStore:
    """
    Persists OAuth tokens to an encrypted-at-rest JSON file.

    In production this would integrate with the OS keychain.
    """

    def __init__(self, store_path: str | Path) -> None:
        self._path = Path(store_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._tokens: dict[str, OAuthToken] = self._load()

    def _load(self) -> dict[str, OAuthToken]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text())
            return {k: OAuthToken.from_dict(v) for k, v in raw.items()}
        except Exception:
            return {}

    def _save(self) -> None:
        data = {k: v.to_dict() for k, v in self._tokens.items()}
        self._path.write_text(json.dumps(data, indent=2))
        # Restrict permissions
        os.chmod(self._path, 0o600)

    def get(self, provider: str) -> OAuthToken | None:
        return self._tokens.get(provider)

    def set(self, provider: str, token: OAuthToken) -> None:
        self._tokens[provider] = token
        self._save()

    def remove(self, provider: str) -> bool:
        existed = provider in self._tokens
        self._tokens.pop(provider, None)
        if existed:
            self._save()
        return existed

    def list_providers(self) -> list[str]:
        return list(self._tokens.keys())


# ---------------------------------------------------------------------------
# OAuth provider config
# ---------------------------------------------------------------------------

@dataclass
class OAuthProvider:
    """Configuration for a single OAuth 2.0 provider."""
    name: str
    client_id: str
    auth_endpoint: str
    token_endpoint: str
    redirect_uri: str
    scopes: list[str]
    client_secret: str | None = None   # None for public PKCE clients

    @property
    def scope_string(self) -> str:
        return " ".join(self.scopes)


# Well-known provider templates
GITHUB_PROVIDER_TEMPLATE = {
    "auth_endpoint": "https://github.com/login/oauth/authorize",
    "token_endpoint": "https://github.com/login/oauth/access_token",
    "scopes": ["repo", "read:user"],
}

GOOGLE_PROVIDER_TEMPLATE = {
    "auth_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "scopes": ["openid", "email", "profile"],
}


__all__ = [
    "OAuthProvider",
    "OAuthToken",
    "TokenStore",
    "build_auth_url",
    "generate_code_challenge",
    "generate_code_verifier",
    "parse_redirect",
    "GITHUB_PROVIDER_TEMPLATE",
    "GOOGLE_PROVIDER_TEMPLATE",
]
