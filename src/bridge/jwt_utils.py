"""
JWT utilities for bridge authentication.

Ports: bridge/jwtUtils.ts
"""
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JWTPayload:
    """Parsed JWT payload (not verified — use only after verification)."""
    sub: str = ""          # subject / session ID
    iss: str = ""          # issuer
    exp: float = 0.0       # expiry Unix timestamp
    iat: float = 0.0       # issued at
    aud: str = ""          # audience
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.exp - 10  # 10s clock-skew buffer

    @property
    def is_valid(self) -> bool:
        return bool(self.sub) and not self.is_expired


def decode_jwt_payload(token: str) -> JWTPayload | None:
    """
    Decode a JWT payload without verifying the signature.

    This is intentionally partial — callers must verify the signature
    with the known secret before trusting any claims.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # JWT padding uses '=' which gets stripped in URL-safe encoding
        def _unpad(s: str) -> str:
            return s + "=" * (4 - len(s) % 4)

        payload_b64 = _unpad(parts[1].replace("-", "+").replace("_", "/"))
        raw = base64.b64decode(payload_b64)
        data: dict[str, Any] = json.loads(raw)
        return JWTPayload(
            sub=data.get("sub", ""),
            iss=data.get("iss", ""),
            exp=float(data.get("exp", 0)),
            iat=float(data.get("iat", 0)),
            aud=data.get("aud", ""),
            claims={k: v for k, v in data.items()
                    if k not in ("sub", "iss", "exp", "iat", "aud")},
        )
    except Exception:
        return None


def encode_jwt_payload(
    payload: dict[str, Any],
    secret: str,
    expires_in: int = 3600,
) -> str:
    """
    Create a signed JWT (HS256) for bridge session authentication.

    For production use the built-in ``PyJWT`` library; this is a
    minimal self-contained implementation.
    """
    import hashlib
    import hmac
    import json as _json

    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    data = {
        **payload,
        "iat": now,
        "exp": now + expires_in,
    }

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header_b64 = _b64url(_json.dumps(header, separators=(",", ":")).encode())
    data_b64 = _b64url(_json.dumps(data, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{data_b64}"

    signature = hmac.new(
        secret.encode("ascii"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url(signature)

    return f"{signing_input}.{sig_b64}"


__all__ = [
    "JWTPayload",
    "decode_jwt_payload",
    "encode_jwt_payload",
]
