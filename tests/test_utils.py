"""Tests for the src/utils subsystem."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# strings
# ---------------------------------------------------------------------------
from src.utils.strings import (
    camel_to_snake,
    chunk,
    extract_code_blocks,
    first_line,
    flatten,
    format_count,
    indent,
    line_count,
    pluralize,
    slug,
    snake_to_camel,
    strip_ansi,
    substitute_args,
    truncate,
    truncate_lines,
    unique,
    word_count,
)


def test_truncate_short():
    assert truncate("hello", 10) == "hello"


def test_truncate_long():
    result = truncate("hello world", 7)
    assert len(result) == 7
    assert result.endswith("…")


def test_truncate_lines():
    text = "a\nb\nc\nd"
    assert truncate_lines(text, 2) == "a\nb\n…"


def test_strip_ansi():
    assert strip_ansi("\033[32mgreen\033[0m") == "green"


def test_slug():
    assert slug("Hello World!") == "hello-world"
    assert slug("  Leading spaces  ") == "leading-spaces"


def test_camel_to_snake():
    assert camel_to_snake("camelCase") == "camel_case"
    assert camel_to_snake("PascalCase") == "pascal_case"
    assert camel_to_snake("alreadysnake") == "alreadysnake"


def test_snake_to_camel():
    assert snake_to_camel("snake_case") == "snakeCase"
    assert snake_to_camel("snake_case", upper_first=True) == "SnakeCase"


def test_substitute_args():
    assert substitute_args("Hello {name}!", {"name": "world"}) == "Hello world!"
    # Unknown key stays
    assert substitute_args("{foo}", {}) == "{foo}"


def test_word_count():
    assert word_count("hello world foo") == 3
    assert word_count("") == 0


def test_line_count():
    assert line_count("a\nb\nc") == 3
    assert line_count("") == 0


def test_first_line():
    assert first_line("\n\nhello\nworld") == "hello"


def test_extract_code_blocks():
    md = "some text\n```python\nprint('hi')\n```\nmore"
    blocks = extract_code_blocks(md)
    assert len(blocks) == 1
    assert blocks[0][0] == "python"
    assert "print" in blocks[0][1]


def test_unique():
    assert unique([1, 2, 1, 3]) == [1, 2, 3]


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_flatten():
    assert flatten([[1, 2], [3], 4]) == [1, 2, 3, 4]


def test_pluralize():
    assert pluralize(1, "file") == "file"
    assert pluralize(2, "file") == "files"
    assert pluralize(0, "goose", "geese") == "geese"


def test_format_count():
    assert format_count(1, "file") == "1 file"
    assert format_count(3, "file") == "3 files"


def test_indent():
    result = indent("hello\nworld")
    assert result.startswith("  ")


# ---------------------------------------------------------------------------
# collections
# ---------------------------------------------------------------------------
from src.utils.collections import CircularBuffer, LRUCache, QueryGuard


def test_circular_buffer_basic():
    buf: CircularBuffer[int] = CircularBuffer(3)
    buf.push(1)
    buf.push(2)
    buf.push(3)
    assert len(buf) == 3
    assert buf.is_full
    buf.push(4)  # overwrites 1
    assert list(buf) == [2, 3, 4]


def test_circular_buffer_peek():
    buf: CircularBuffer[str] = CircularBuffer(5)
    assert buf.peek() is None
    buf.push("a")
    buf.push("b")
    assert buf.peek() == "a"
    assert buf.peek_latest() == "b"


def test_lru_cache():
    cache: LRUCache[int] = LRUCache(3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)  # evicts "a"
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_query_guard():
    guard = QueryGuard(cooldown_seconds=0.0)
    assert guard.is_allowed("key")
    # cooldown=0 means always allowed after reset
    guard.reset("key")
    assert guard.is_allowed("key")


# ---------------------------------------------------------------------------
# encoding
# ---------------------------------------------------------------------------
from src.utils.encoding import (
    detect_encoding,
    guess_language,
    is_valid_utf8,
    normalize_newlines,
    safe_decode,
)


def test_detect_encoding_utf8():
    data = "hello world".encode("utf-8")
    assert detect_encoding(data) == "utf-8"


def test_detect_encoding_bom():
    data = b"\xef\xbb\xbfhello"  # UTF-8 BOM
    assert detect_encoding(data) == "utf-8-sig"


def test_safe_decode():
    assert safe_decode(b"hello") == "hello"
    # Invalid UTF-8 fallback
    result = safe_decode(b"\xff\xfe", encoding="utf-8")
    assert isinstance(result, str)


def test_normalize_newlines():
    assert normalize_newlines("a\r\nb\rc") == "a\nb\nc"


def test_is_valid_utf8():
    assert is_valid_utf8(b"hello")
    assert not is_valid_utf8(b"\xff\xfe")


def test_guess_language():
    assert guess_language("main.py") == "python"
    assert guess_language("index.ts") == "typescript"
    assert guess_language("style.css") == "css"
    assert guess_language("README.md") == "markdown"


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
from src.utils.paths import (
    atomic_write,
    ensure_dir,
    extension_of,
    file_size_str,
    find_project_root,
    is_text_file,
    read_text_safe,
    resolve_path,
    safe_relative,
    write_text_safe,
)


def test_resolve_path_absolute():
    p = resolve_path("/tmp/foo")
    assert p.is_absolute()


def test_resolve_path_relative():
    import os
    p = resolve_path("foo/bar", base="/tmp")
    # On macOS /tmp is a symlink to /private/tmp; compare resolved paths
    expected = Path(os.path.realpath("/tmp")) / "foo" / "bar"
    assert p == expected


def test_safe_relative_inside():
    rel = safe_relative("/tmp/foo/bar", "/tmp/foo")
    assert str(rel) == "bar"


def test_safe_relative_outside():
    rel = safe_relative("/etc/hosts", "/tmp/foo")
    assert rel.is_absolute()


def test_ensure_dir(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    result = ensure_dir(target)
    assert result.is_dir()


def test_atomic_write(tmp_path):
    p = tmp_path / "test.txt"
    atomic_write(p, "hello world")
    assert p.read_text() == "hello world"


def test_read_write_safe(tmp_path):
    p = tmp_path / "safe.txt"
    assert write_text_safe(p, "content")
    assert read_text_safe(p) == "content"
    assert read_text_safe(tmp_path / "nonexistent.txt") is None


def test_is_text_file(tmp_path):
    p = tmp_path / "text.txt"
    p.write_text("hello world")
    assert is_text_file(p)
    bp = tmp_path / "binary.bin"
    bp.write_bytes(b"\x00\x01\x02")
    assert not is_text_file(bp)


def test_extension_of():
    assert extension_of("main.py") == "py"
    assert extension_of("index.TS") == "ts"
    assert extension_of("Makefile") == ""


def test_file_size_str():
    assert "B" in file_size_str(512)
    assert "KB" in file_size_str(2048)
    assert "MB" in file_size_str(2 * 1024 * 1024)


def test_find_project_root():
    # Should find this repo's root since it has pyproject.toml
    root = find_project_root(Path(__file__).parent)
    assert root is not None
    assert (root / "pyproject.toml").exists() or (root / ".git").exists()


# ---------------------------------------------------------------------------
# retry
# ---------------------------------------------------------------------------
from src.utils.retry import RetryExhausted, retry_sync, with_retry


def test_retry_success_first_try():
    calls = []

    def fn():
        calls.append(1)
        return 42

    result = retry_sync(fn, max_attempts=3)
    assert result == 42
    assert len(calls) == 1


def test_retry_fails_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("not yet")
        return "ok"

    result = retry_sync(fn, max_attempts=5, base_delay=0.0)
    assert result == "ok"
    assert len(calls) == 3


def test_retry_exhausted():
    def fn():
        raise ValueError("always fails")

    with pytest.raises(RetryExhausted):
        retry_sync(fn, max_attempts=2, base_delay=0.0)


@pytest.mark.asyncio
async def test_retry_async():
    from src.utils.retry import retry_async

    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise OSError("not yet")
        return "done"

    result = await retry_async(fn, max_attempts=3, base_delay=0.0)
    assert result == "done"


def test_with_retry_decorator():
    calls = []

    @with_retry(max_attempts=3, base_delay=0.0)
    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("fail")
        return "pass"

    assert flaky() == "pass"


# ---------------------------------------------------------------------------
# ids
# ---------------------------------------------------------------------------
from src.utils.ids import (
    agent_id,
    deterministic_id,
    new_session_id,
    new_short_id,
    timestamp_id,
)


def test_new_session_id():
    sid = new_session_id()
    # UUID4 format
    assert len(sid) == 36
    assert sid.count("-") == 4


def test_new_short_id():
    sid = new_short_id("tool")
    assert sid.startswith("tool-")
    assert len(sid) == 13  # "tool-" + 8 hex


def test_deterministic_id():
    a = deterministic_id("foo", "bar")
    b = deterministic_id("foo", "bar")
    c = deterministic_id("foo", "baz")
    assert a == b
    assert a != c


def test_timestamp_id_sortable():
    import time
    ids = []
    for _ in range(5):
        ids.append(timestamp_id())
        time.sleep(0.002)  # ensure strictly increasing timestamps
    assert ids == sorted(ids)


def test_agent_id():
    aid = agent_id("devon")
    assert aid.startswith("devon-")


# ---------------------------------------------------------------------------
# shell
# ---------------------------------------------------------------------------
from src.utils.shell import ShellResult, run, which


def test_run_echo():
    result = run("echo hello")
    assert result.success
    assert "hello" in result.stdout


def test_run_failure():
    result = run("exit 1", shell=True)
    assert not result.success
    assert result.returncode == 1


def test_run_with_cwd(tmp_path):
    result = run("pwd", cwd=tmp_path)
    assert result.success
    assert str(tmp_path) in result.stdout


def test_which_python():
    p = which("python3")
    assert p is not None


@pytest.mark.asyncio
async def test_run_async():
    from src.utils.shell import run_async

    result = await run_async("echo async_test")
    assert result.success
    assert "async_test" in result.stdout


# ---------------------------------------------------------------------------
# http (smoke test only — no network calls)
# ---------------------------------------------------------------------------
from src.utils.http import build_url, parse_sse_line


def test_build_url():
    url = build_url("https://api.example.com", "/v1/chat", {"model": "gpt-4"})
    assert url == "https://api.example.com/v1/chat?model=gpt-4"


def test_build_url_no_params():
    url = build_url("https://api.example.com", "/v1")
    assert url == "https://api.example.com/v1"


def test_parse_sse_line():
    assert parse_sse_line("data: hello") == ("data", "hello")
    assert parse_sse_line(": comment") is None
    assert parse_sse_line("") is None
    assert parse_sse_line("event: update") == ("event", "update")


# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------
from src.utils.logging import configure_logging, get_logger


def test_configure_logging():
    configure_logging(level="DEBUG", use_color=False)
    logger = get_logger("test.utils")
    logger.debug("test message — should not raise")


# ---------------------------------------------------------------------------
# __init__ re-exports
# ---------------------------------------------------------------------------
from src.utils import (
    CircularBuffer as _CB,
    ARCHIVE_NAME,
    MODULE_COUNT,
    PORTING_NOTE,
    truncate as _trunc,
)


def test_init_re_exports():
    assert ARCHIVE_NAME == "utils"
    assert MODULE_COUNT == 564
    assert "ported" in PORTING_NOTE.lower() or "Ported" in PORTING_NOTE
    buf: _CB[int] = _CB(2)
    buf.push(1)
    assert len(buf) == 1
    assert _trunc("hello world", 5) == "hell…"
