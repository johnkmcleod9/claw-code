"""Tests for _raw tool call argument unwrapping and JSON repair."""
import json
import pytest
import asyncio
from pathlib import Path

# Test the _repair_json function from both providers
from src.providers.openrouter import _repair_json as or_repair
from src.providers.lmstudio import _repair_json as lm_repair


class TestRepairJson:
    """Test JSON repair for malformed model outputs."""

    def test_valid_json_passthrough(self):
        result = or_repair('{"path": "test.py", "content": "hello"}')
        assert result == {"path": "test.py", "content": "hello"}

    def test_whitespace_handling(self):
        result = or_repair('  {"path": "test.py"}  ')
        assert result == {"path": "test.py"}

    def test_truncated_json_one_brace(self):
        result = or_repair('{"path": "test.py", "content": "hello"')
        assert result == {"path": "test.py", "content": "hello"}

    def test_truncated_json_nested(self):
        result = or_repair('{"path": "test.py", "options": {"a": 1}')
        assert result is not None
        assert result["path"] == "test.py"

    def test_double_encoded_json(self):
        inner = json.dumps({"path": "test.py", "content": "hello"})
        outer = json.dumps(inner)  # double-encoded
        result = or_repair(outer)
        assert result == {"path": "test.py", "content": "hello"}

    def test_empty_string(self):
        assert or_repair("") is None
        assert or_repair("   ") is None

    def test_non_dict_json(self):
        assert or_repair("[1, 2, 3]") is None
        assert or_repair('"just a string"') is None

    def test_truly_broken_json(self):
        assert or_repair("not json at all {{{") is None

    def test_lmstudio_same_behavior(self):
        """Both providers should have identical repair logic."""
        test_cases = [
            '{"path": "test.py"}',
            '{"path": "test.py"',
            "",
            "broken",
        ]
        for case in test_cases:
            assert or_repair(case) == lm_repair(case), f"Mismatch for: {case!r}"


class TestRegistryRawUnwrap:
    """Test the safety net in ToolRegistry.execute."""

    @pytest.fixture
    def registry(self, tmp_path):
        from src.tools_impl.registry import create_default_registry
        return create_default_registry()

    @pytest.fixture
    def context(self, tmp_path):
        from src.tools_impl.base import ToolContext
        return ToolContext(cwd=tmp_path)

    def test_raw_unwrap_file_write(self, registry, context, tmp_path):
        """_raw containing valid JSON should be unwrapped and executed."""
        target = tmp_path / "output.txt"
        args = {"_raw": json.dumps({"path": str(target), "content": "hello world"})}

        result = asyncio.run(registry.execute("file_write", args, context))
        assert result.success, f"Expected success but got: {result.error}"
        assert target.read_text() == "hello world"

    def test_raw_unwrap_file_read(self, registry, context, tmp_path):
        """_raw unwrap should work for file_read too."""
        target = tmp_path / "input.txt"
        target.write_text("test content")
        args = {"_raw": json.dumps({"path": str(target)})}

        result = asyncio.run(registry.execute("file_read", args, context))
        assert result.success
        assert "test content" in result.output

    def test_non_json_raw_passes_through(self, registry, context):
        """If _raw isn't valid JSON, pass it through unchanged (tool will error gracefully)."""
        args = {"_raw": "not valid json"}
        result = asyncio.run(registry.execute("file_write", args, context))
        assert not result.success  # Expected — path is required

    def test_normal_args_unaffected(self, registry, context, tmp_path):
        """Normal args dict should work as before."""
        target = tmp_path / "normal.txt"
        args = {"path": str(target), "content": "normal write"}

        result = asyncio.run(registry.execute("file_write", args, context))
        assert result.success
        assert target.read_text() == "normal write"

    def test_raw_dict_unwrap(self, registry, context, tmp_path):
        """_raw containing a dict (not string) should be unwrapped."""
        target = tmp_path / "dict_raw.txt"
        args = {"_raw": {"path": str(target), "content": "dict raw content"}}

        result = asyncio.run(registry.execute("file_write", args, context))
        assert result.success, f"Expected success but got: {result.error}"
        assert target.read_text() == "dict raw content"
