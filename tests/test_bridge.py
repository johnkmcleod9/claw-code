"""
Tests for bridge subsystem — jwt_utils and debug_utils.
"""
from __future__ import annotations

import time

import pytest

from src.bridge.jwt_utils import (
    JWTPayload,
    encode_jwt_payload,
    decode_jwt_payload,
    make_bridge_token,
)
from src.bridge.debug_utils import (
    hexdump,
    BridgeLogger,
    BridgeLogLevel,
    get_bridge_logger,
)


# ── JWT ────────────────────────────────────────────────────────────────────

def test_jwt_payload_properties():
    now = time.time()
    p = JWTPayload(sub="session-123", exp=now + 60, iat=now)
    assert p.sub == "session-123"
    assert not p.is_expired
    assert p.ttl_seconds > 0


def test_jwt_payload_expired():
    past = time.time() - 10
    p = JWTPayload(sub="session-123", exp=past, iat=past - 60)
    assert p.is_expired
    assert p.ttl_seconds == 0


def test_encode_decode_roundtrip():
    now = time.time()
    payload = JWTPayload(
        sub="bridge-session-abc",
        exp=now + 300,
        iat=now,
        iss="claw-code",
        scope="bridge:read",
    )
    secret = "test-secret-key"
    token = encode_jwt_payload(payload, secret)

    decoded = decode_jwt_payload(token, secret, verify=True)
    assert decoded.sub == "bridge-session-abc"
    assert decoded.iss == "claw-code"
    assert decoded.scope == "bridge:read"


def test_decode_wrong_secret_raises():
    now = time.time()
    payload = JWTPayload(sub="s", exp=now + 60, iat=now)
    token = encode_jwt_payload(payload, "correct-secret")

    with pytest.raises(ValueError, match="signature"):
        decode_jwt_payload(token, "wrong-secret", verify=True)


def test_decode_expired_raises():
    past = time.time() - 10
    payload = JWTPayload(sub="s", exp=past, iat=past - 60)
    token = encode_jwt_payload(payload, "secret")

    with pytest.raises(ValueError, match="expired"):
        decode_jwt_payload(token, "secret", verify=True)


def test_decode_malformed_raises():
    with pytest.raises(ValueError):
        decode_jwt_payload("not.a.jwt", "secret")


def test_decode_verify_false_allows_expired():
    past = time.time() - 10
    payload = JWTPayload(sub="s", exp=past, iat=past - 60)
    token = encode_jwt_payload(payload, "secret")
    decoded = decode_jwt_payload(token, "secret", verify=False)
    assert decoded.sub == "s"


def test_make_bridge_token():
    token = make_bridge_token("session-xyz", "secret", ttl_seconds=60)
    assert token.count(".") == 2
    decoded = decode_jwt_payload(token, "secret")
    assert decoded.sub == "session-xyz"
    assert "bridge" in decoded.scope


def test_encode_unsupported_algorithm_raises():
    now = time.time()
    payload = JWTPayload(sub="s", exp=now + 60, iat=now)
    with pytest.raises(ValueError, match="Unsupported"):
        encode_jwt_payload(payload, "secret", algorithm="RS256")


def test_jwt_extra_fields():
    now = time.time()
    payload = JWTPayload(sub="s", exp=now + 60, iat=now)
    payload.extra = {"custom": "value"}
    token = encode_jwt_payload(payload, "secret")
    decoded = decode_jwt_payload(token, "secret")
    assert decoded.extra is not None
    assert decoded.extra.get("custom") == "value"


# ── Debug utils ─────────────────────────────────────────────────────────────

def test_hexdump_basic():
    data = b"Hello, World!"
    result = hexdump(data)
    assert "48 65 6c 6c 6f" in result  # "Hell" in hex
    assert "|Hello, World!|" in result


def test_hexdump_with_offset():
    data = b"test"
    result = hexdump(data, offset=0x100)
    assert "00000100" in result


def test_hexdump_with_length():
    data = b"Hello, World!"
    result = hexdump(data, length=5)
    assert len(result.splitlines()) == 1


def test_hexdump_non_printable():
    data = bytes(range(32))
    result = hexdump(data)
    assert "2e" * 16 in result  # dots for non-printable


def test_bridge_logger_levels():
    logger = BridgeLogger(level=BridgeLogLevel.ERROR)
    # Should not emit for debug/info/warn
    # We verify by checking it doesn't raise
    logger.debug("debug msg")
    logger.info("info msg")
    logger.warn("warn msg")
    logger.error("error msg")  # Should emit


def test_bridge_logger_to_file(tmp_path):
    log_path = tmp_path / "bridge.log"
    logger = BridgeLogger(output_path=log_path, level=BridgeLogLevel.DEBUG)
    logger.info("test message")
    logger.close()

    content = log_path.read_text()
    assert "test message" in content


def test_get_bridge_logger_singleton():
    import src.bridge.debug_utils as du
    du._logger = None  # reset singleton
    logger1 = get_bridge_logger()
    logger2 = get_bridge_logger()
    assert logger1 is logger2
    du._logger = None  # reset for other tests
