"""
JWT utility helpers for the bridge.

Bridges use short-lived JWT tokens to authenticate with the IDE extension.
This module provides minimal JWT encode/decode (HS256) without external deps.

Note: For production use, prefer PyJWT. This module is a lightweight fallback.

Ports: bridge/jwtUtils.ts
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
import time
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Payload model
# ---------------------------------------------------------------------------

@dataclass
class JWTPayload:
    """Decoded JWT payload."""
    sub: str          # subject / session ID
    exp: float        # expiration timestamp
    iat: float        # issued-at timestamp
    iss: str = ""     # issuer
    aud: str = ""     # audience
    scope: str = ""   # granted scopes
    extra: dict[str, Any] | None = None

    @property
    def is_expired(self) -> bool:
        return time.time() > self.exp

    @property
    def ttl_seconds(self) -> float:
        return max(0.0, self.exp - time.time())


# ---------------------------------------------------------------------------
# Low-level base64url
# ---------------------------------------------------------------------------

def _base64url_encode(data: bytes) -> str:
    return (
        base64.urlsafe_b64encode(data)
        .rstrip(b"=")
        .decode("ascii")
    )


def _base64url_decode(data: str) -> bytes:
    # Add padding back
    rem = len(data) % 4
    if rem:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data)


# ---------------------------------------------------------------------------
# HS256 signing
# ---------------------------------------------------------------------------

def _sign(payload_bytes: bytes, secret: str) -> str:
    key = secret.encode("utf-8")
    sig = hmac.new(key, payload_bytes, hashlib.sha256).digest()
    return _base64url_encode(sig)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode_jwt_payload(
    payload: JWTPayload,
    secret: str,
    algorithm: str = "HS256",
) -> str:
    """
    Encode a JWT payload into a compact string.

    Args:
        payload: The JWT payload to encode.
        secret:  Shared secret for HS256 signing.
        algorithm: Algorithm (only HS256 supported here).

    Returns:
        ``header.payload.signature`` string.
    """
    if algorithm != "HS256":
        raise ValueError(f"Unsupported algorithm: {algorithm!r} (only HS256)")

    header_obj = {"alg": "HS256", "typ": "JWT"}
    header_bytes = json.dumps(header_obj, separators=(",", ":")).encode("utf-8")
    payload_dict: dict[str, Any] = {
        "sub": payload.sub,
        "exp": payload.exp,
        "iat": payload.iat,
    }
    if payload.iss:
        payload_dict["iss"] = payload.iss
    if payload.aud:
        payload_dict["aud"] = payload.aud
    if payload.scope:
        payload_dict["scope"] = payload.scope
    if payload.extra:
        payload_dict.update(payload.extra)

    payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")

    header_b64 = _base64url_encode(header_bytes)
    payload_b64 = _base64url_encode(payload_bytes)
    signature = _sign(header_bytes + b"." + payload_bytes, secret)

    return f"{header_b64}.{payload_b64}.{signature}"


def decode_jwt_payload(
    token: str,
    secret: str,
    verify: bool = True,
) -> JWTPayload:
    """
    Decode and optionally verify a JWT.

    Args:
        token:   The compact JWT string.
        secret:  Shared secret for HS256 verification.
        verify:  If True, verify signature and expiration.

    Returns:
        Decoded JWTPayload.

    Raises:
        ValueError: If the token is malformed, invalid, or expired.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("JWT must have 3 parts (header.payload.signature)")

    header_b64, payload_b64, signature_b64 = parts

    if verify:
        expected_sig = _sign(f"{header_b64}.{payload_b64}".encode(), secret)
        if not hmac.compare_digest(signature_b64, expected_sig):
            raise ValueError("JWT signature mismatch")

    try:
        header_bytes = _base64url_decode(header_b64)
        payload_bytes = _base64url_decode(payload_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 in JWT: {e}") from e

    try:
        header = json.loads(header_bytes)
        if header.get("alg") not in ("HS256", None):
            raise ValueError(f"Unsupported JWT algorithm: {header.get('alg')}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JWT header JSON: {e}") from e

    try:
        payload_dict = json.loads(payload_bytes)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JWT payload JSON: {e}") from e

    required = ("sub", "exp", "iat")
    for field in required:
        if field not in payload_dict:
            raise ValueError(f"Missing required JWT field: {field!r}")

    if verify and payload_dict["exp"] < time.time():
        raise ValueError("JWT has expired")

    extra = {k: v for k, v in payload_dict.items()
             if k not in ("sub", "exp", "iat", "iss", "aud", "scope")}

    return JWTPayload(
        sub=payload_dict["sub"],
        exp=float(payload_dict["exp"]),
        iat=float(payload_dict["iat"]),
        iss=payload_dict.get("iss", ""),
        aud=payload_dict.get("aud", ""),
        scope=payload_dict.get("scope", ""),
        extra=extra if extra else None,
    )


def make_bridge_token(
    session_id: str,
    secret: str,
    ttl_seconds: float = 300.0,
    scope: str = "bridge:read bridge:write",
    issuer: str = "claw-code",
) -> str:
    """
    Create a short-lived JWT for a bridge session.

    Args:
        session_id: The bridge session ID to embed as ``sub``.
        secret:     Shared JWT secret.
        ttl_seconds: Token validity period (default 5 minutes).
        scope:      Space-separated list of granted scopes.
        issuer:     Issuer string.

    Returns:
        JWT token string.
    """
    now = time.time()
    payload = JWTPayload(
        sub=session_id,
        exp=now + ttl_seconds,
        iat=now,
        iss=issuer,
        scope=scope,
    )
    return encode_jwt_payload(payload, secret)
