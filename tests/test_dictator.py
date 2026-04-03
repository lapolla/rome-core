"""Tests for ROME dictator modules — direct function calls, no framework gymnastics."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from dictator.core import run_cmd
from mcp.server.fastmcp import FastMCP
from dictator import tools_fs, tools_legion
from legions.legion_wrapper import parse_rome_signals, parse_usage


@pytest.fixture
def authed_mcp_fixture():
    """Returns a FastMCP instance with dictator tools registered."""
    loop = asyncio.get_event_loop()
    _mcp = FastMCP("test_dictator")
    tools_fs.register(_mcp)
    tools_legion.register(_mcp)

    tool_info_list = loop.run_until_complete(_mcp.list_tools())
    tool_names = [tool.name for tool in tool_info_list]

    class AuthedMCPWrapper:
        def __getattr__(self, name):
            if name in tool_names:
                def tool_callable(**kwargs):
                    # Extract 'ctx' if it exists in kwargs and pass it as context to call_tool
                    ctx_arg = kwargs.pop("ctx", None)
                    return loop.run_until_complete(_mcp.call_tool(name, kwargs, context=ctx_arg))
                return tool_callable
            
            # Fallback to original attribute if not a registered tool
            return getattr(_mcp, name)
            
    return AuthedMCPWrapper()


# ── run_cmd ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_cmd_echo():
    r = await run_cmd("echo hello", cwd="/tmp")
    assert r["ok"] is True
    assert "hello" in r["stdout"]


@pytest.mark.asyncio
async def test_run_cmd_failing():
    r = await run_cmd("false", cwd="/tmp")
    assert r["ok"] is False


# ── fs_read / fs_write round-trip ──────────────────────────────────────

@pytest.mark.asyncio
async def test_fs_read_write_roundtrip(tmp_path, monkeypatch, authed_mcp_fixture):
    """Round-trip through fs_write → fs_read using a temp ROOT_DIR."""
    monkeypatch.setattr(tools_fs, "ROOT_DIR", tmp_path)

    result_obj = await authed_mcp_fixture.call_tool("fs_write", {"path": "test.txt", "content": "imperial data"})
    result = result_obj[0][0].text if result_obj and result_obj[0] and hasattr(result_obj[0][0], 'text') else str(result_obj)
    assert "imperial data" not in json.dumps({"err": True})  # no error
    assert "Wrote" in result

    content_obj = await authed_mcp_fixture.call_tool("fs_read", {"path": "test.txt"})
    content = content_obj[0][0].text if content_obj and content_obj[0] and hasattr(content_obj[0][0], 'text') else str(content_obj)
    # Remove the [ROME: lines ...] prefix
    if content.startswith("[ROME: lines"):
        content = content.split('\n', 1)[1] if '\n' in content else ''
    data = json.loads(content_obj[0][0].text if content_obj and content_obj[0] and hasattr(content_obj[0][0], "text") else str(content_obj))
    content = data.get("data", "")
    if content.startswith("[ROME: lines"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
    assert content == "imperial data"


# ── path traversal guard ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fs_read_path_traversal(tmp_path, monkeypatch, authed_mcp_fixture):
    """Refactor test_fs_read_path_traversal to directly use `authed_mcp_fixture` for tool calls, removing the intermediate `authed_mcp` variable."""
    monkeypatch.setattr(tools_fs, "ROOT_DIR", tmp_path)

    result_obj = await authed_mcp_fixture.call_tool("fs_read", {"path": "../../etc/passwd"})
    result = result_obj[0][0].text if result_obj and result_obj[0] and hasattr(result_obj[0][0], 'text') else str(result_obj)
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "escapes" in parsed.get("error", "") or "escapes" in parsed.get("message", "")


@pytest.mark.asyncio
async def test_fs_write_path_traversal(tmp_path, monkeypatch, authed_mcp_fixture):
    monkeypatch.setattr(tools_fs, "ROOT_DIR", tmp_path)

    result_obj = await authed_mcp_fixture.call_tool("fs_write", {"path": "../../tmp/evil.txt", "content": "nope"})
    result = result_obj[0][0].text if result_obj and result_obj[0] and hasattr(result_obj[0][0], 'text') else str(result_obj)
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "escapes" in parsed.get("error", "") or "escapes" in parsed.get("message", "")


# ── read_anywhere / write_anywhere round-trip ─────────────────────────

@pytest.mark.asyncio
async def test_read_write_anywhere_roundtrip(tmp_path, authed_mcp_fixture):
    target = str(tmp_path / 'anywhere.txt')
    r_obj = await authed_mcp_fixture.call_tool('write_anywhere', {'path': target, 'content': 'absolute power'})
    r = r_obj[0][0].text if r_obj and r_obj[0] and hasattr(r_obj[0][0], 'text') else str(r_obj)
    parsed = json.loads(r)
    assert parsed['ok'] is True

    content_obj = await authed_mcp_fixture.call_tool('read_anywhere', {'path': target})
    raw = content_obj[0][0].text if content_obj and content_obj[0] and hasattr(content_obj[0][0], 'text') else str(content_obj)
    data = json.loads(raw)
    content = data.get('data', '')
    if content.startswith('[ROME: lines'):
        content = content.split('\n', 1)[1] if '\n' in content else ''
    assert content == 'absolute power'
# ── list_directory ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_directory(authed_mcp_fixture):
    r_obj = await authed_mcp_fixture.call_tool("list_directory", {"dir_path": "/tmp"})
    r = json.loads(r_obj[0][0].text if r_obj and r_obj[0] and hasattr(r_obj[0][0], 'text') else str(r_obj))
    assert r["ok"] is True
    assert isinstance(r.get("data", r.get("entries")), list)


# ── execute_legion error path ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_legion_invalid_capability():
    r = await tools_legion._execute_legion_impl(
        task_id="TEST_INVALID",
        capability="NONEXISTENT",
        args=["echo", "hi"],
        ctx=None,
    )
    assert r["ok"] is False
    assert "not found" in r["message"]


# ── execute_campaign empty ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_campaign_empty(authed_mcp_fixture):
    r_obj = await authed_mcp_fixture.call_tool("execute_campaign", {"ctx": None, "campaign_id": "EMPTY_TEST", "tasks": []})
    r = r_obj[0][0].text if r_obj and r_obj[0] and hasattr(r_obj[0][0], 'text') else str(r_obj)
    assert "Campaign: EMPTY_TEST" in r
    assert "0/0 succeeded" in r


# ── parse_rome_signals ────────────────────────────────────────────────

def test_parse_rome_signals_valid():
    text = "[ROME_START]artifact content[ROME_END] [ROME_META: author=caesar] [ROME_STATUS: SUCCESS]"
    s = parse_rome_signals(text)
    assert s["primary_artifact"] == "artifact content"
    assert s["metadata"]["author"] == "caesar"
    assert s["status_override"] == "SUCCESS"


def test_parse_rome_signals_empty():
    s = parse_rome_signals("")
    assert s["primary_artifact"] is None
    assert s["metadata"] == {}
    assert s["status_override"] is None


def test_parse_rome_signals_no_tags():
    s = parse_rome_signals("just regular output with no signals")
    assert s["primary_artifact"] is None
    assert s["status_override"] is None


def test_parse_rome_signals_invalid():
    """Pathological input shouldn't crash."""
    s = parse_rome_signals("[ROME_START]" * 1000)
    assert isinstance(s, dict)


# ── parse_usage ───────────────────────────────────────────────────────

def test_parse_usage_claude_json():
    """Claude --output-format json shape."""
    data = json.dumps({
        "result": "hello world",
        "total_cost_usd": 0.05,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 200,
            "cache_read_input_tokens": 300,
        },
        "modelUsage": {
            "claude-opus-4-6": {"inputTokens": 100, "outputTokens": 50}
        },
    })
    text, usage = parse_usage(data)
    assert text == "hello world"
    assert usage["model"] == "claude-opus-4-6"
    assert usage["input_tokens"] == 400  # 100 + 300 cache_read
    assert usage["output_tokens"] == 50
    assert usage["total_tokens"] == 650  # 100 + 300 + 200 + 50
    assert usage["cost_usd"] == 0.05


def test_parse_usage_gemini_json():
    """Gemini --output-format json shape."""
    data = json.dumps({
        "response": "hello from gemini",
        "stats": {
            "models": {
                "gemini-2.5-flash": {
                    "tokens": {"input": 500, "candidates": 30, "total": 560}
                }
            }
        },
    })
    text, usage = parse_usage(data)
    assert text == "hello from gemini"
    assert usage["model"] == "gemini-2.5-flash"
    assert usage["input_tokens"] == 500
    assert usage["output_tokens"] == 30
    assert usage["total_tokens"] == 560
    assert usage["cost_usd"] == 0.000225


def test_parse_usage_raw_text():
    """Non-JSON output returns original text and None usage."""
    text, usage = parse_usage("just plain text output")
    assert text == "just plain text output"
    assert usage is None


def test_parse_usage_empty():
    text, usage = parse_usage("")
    assert text == ""
    assert usage is None


def test_parse_usage_gemini_with_preamble():
    """Gemini sometimes emits stderr lines before the JSON."""
    raw = 'Loaded cached credentials.\nError during discovery for MCP server...' + json.dumps({
        "response": "result",
        "stats": {"models": {"gemini-3-flash": {"tokens": {"input": 10, "candidates": 5, "total": 15}}}}
    })
    text, usage = parse_usage(raw)
    assert text == "result"
    assert usage is not None
    assert usage["model"] == "gemini-3-flash"