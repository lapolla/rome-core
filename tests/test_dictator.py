"""Tests for dictator.py MCP tools — direct function calls, no framework gymnastics."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from dictator.dictator import (
    run_cmd,
    fs_read,
    fs_write,
    read_anywhere,
    write_anywhere,
    list_directory,
    execute_legion,
    execute_campaign,
    ROOT_DIR,
)
from legions.legion_wrapper import parse_rome_signals


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
async def test_fs_read_write_roundtrip(tmp_path, monkeypatch):
    """Round-trip through fs_write → fs_read using a temp ROOT_DIR."""
    import dictator.dictator as d
    monkeypatch.setattr(d, "ROOT_DIR", tmp_path)

    result = await fs_write("test.txt", "imperial data")
    assert "imperial data" not in json.dumps({"err": True})  # no error
    assert "Wrote" in result

    content = await fs_read("test.txt")
    assert content == "imperial data"


# ── path traversal guard ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fs_read_path_traversal(tmp_path, monkeypatch):
    import dictator.dictator as d
    monkeypatch.setattr(d, "ROOT_DIR", tmp_path)

    result = await fs_read("../../etc/passwd")
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "escapes" in parsed["message"]


@pytest.mark.asyncio
async def test_fs_write_path_traversal(tmp_path, monkeypatch):
    import dictator.dictator as d
    monkeypatch.setattr(d, "ROOT_DIR", tmp_path)

    result = await fs_write("../../tmp/evil.txt", "nope")
    parsed = json.loads(result)
    assert parsed["ok"] is False
    assert "escapes" in parsed["message"]


# ── read_anywhere / write_anywhere round-trip ─────────────────────────

@pytest.mark.asyncio
async def test_read_write_anywhere_roundtrip(tmp_path):
    target = str(tmp_path / "anywhere.txt")
    r = await write_anywhere(target, "absolute power")
    parsed = json.loads(r)
    assert parsed["ok"] is True

    content = await read_anywhere(target)
    assert content == "absolute power"


# ── list_directory ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_directory():
    r = json.loads(await list_directory("/tmp"))
    assert r["ok"] is True
    assert isinstance(r["entries"], list)


# ── execute_legion error path ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_legion_invalid_capability():
    r = await execute_legion(task_id="TEST_INVALID", capability="NONEXISTENT", args=["echo", "hi"])
    assert "not found" in r


# ── execute_campaign empty ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_campaign_empty():
    r = json.loads(await execute_campaign(campaign_id="EMPTY_TEST", tasks=[]))
    assert r["campaign_id"] == "EMPTY_TEST"
    assert r["results"] == {}


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
