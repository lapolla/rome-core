"""Tests for WS command handlers — handle_await, handle_status, handle_reset, etc."""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dictator.events import EventBus, TaskRegistry, RomeEvent, emit_complete


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def fresh_registry():
    """Isolated TaskRegistry + EventBus for each test."""
    bus = EventBus(max_queue_size=1000)
    reg = TaskRegistry(ttl_seconds=3600)
    return bus, reg


# ── handle_await ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_await_already_complete(fresh_registry):
    """Tasks already completed resolve immediately."""
    bus, reg = fresh_registry

    # Simulate a completed task
    reg.register("done-1", "SAFE_SHELL")
    reg.complete("done-1", "completed", "/tmp/report.txt")

    # Import and patch the handler's globals
    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):
        result = await ws_server.handle_await({
            "task_ids": ["done-1"],
            "include_reports": False,
        })

    assert result["ok"] is True
    assert "done-1" in result["tasks"]
    assert result["tasks"]["done-1"]["status"] == "completed"


@pytest.mark.asyncio
async def test_handle_await_waits_for_completion(fresh_registry):
    """Await blocks until task completes via EventBus."""
    bus, reg = fresh_registry

    # Register a running task
    reg.register("pending-1", "GEMINI")
    reg.update_progress("pending-1", 50, "working")

    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):

        async def complete_after_delay():
            await asyncio.sleep(0.3)
            reg.complete("pending-1", "completed", "/tmp/r.txt")
            await emit_complete(bus, "pending-1", "completed", "/tmp/r.txt", {"total_tokens": 100})

        # Fire completion in background, await should catch it
        task = asyncio.create_task(complete_after_delay())
        result = await ws_server.handle_await({
            "task_ids": ["pending-1"],
            "include_reports": False,
        })
        await task

    assert result["ok"] is True
    assert result["tasks"]["pending-1"]["status"] == "completed"


@pytest.mark.asyncio
async def test_handle_await_mixed_complete_and_pending(fresh_registry):
    """Mix of already-done and pending tasks."""
    bus, reg = fresh_registry

    reg.register("a", "SAFE_SHELL")
    reg.complete("a", "completed", None)
    reg.register("b", "GEMINI")

    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):

        async def complete_b():
            await asyncio.sleep(0.2)
            reg.complete("b", "completed", None)
            await emit_complete(bus, "b", "completed", None, None)

        task = asyncio.create_task(complete_b())
        result = await ws_server.handle_await({"task_ids": ["a", "b"]})
        await task

    assert result["ok"] is True
    assert result["tasks"]["a"]["status"] == "completed"
    assert result["tasks"]["b"]["status"] == "completed"


@pytest.mark.asyncio
async def test_handle_await_failed_task(fresh_registry):
    """Failed tasks are returned as-is, ok=False."""
    bus, reg = fresh_registry

    reg.register("fail-1", "CODEX")
    reg.complete("fail-1", "failed", None)

    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):
        result = await ws_server.handle_await({"task_ids": ["fail-1"]})

    assert result["ok"] is False
    assert result["tasks"]["fail-1"]["status"] == "failed"


@pytest.mark.asyncio
async def test_handle_await_empty_task_ids(fresh_registry):
    """Empty task list raises ValueError."""
    bus, reg = fresh_registry

    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):
        with pytest.raises(ValueError, match="task_ids"):
            await ws_server.handle_await({"task_ids": []})


@pytest.mark.asyncio
async def test_handle_await_with_reports(fresh_registry, tmp_path):
    """include_reports=True returns report content inline."""
    bus, reg = fresh_registry

    report = tmp_path / "report.txt"
    report.write_text("test output data")

    reg.register("rpt-1", "SAFE_SHELL")
    reg.complete("rpt-1", "completed", str(report))

    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):
        result = await ws_server.handle_await({
            "task_ids": ["rpt-1"],
            "include_reports": True,
        })

    assert result["tasks"]["rpt-1"]["report"] == "test output data"


@pytest.mark.asyncio
async def test_handle_await_report_truncation(fresh_registry, tmp_path):
    """Reports > 4000 chars are truncated."""
    bus, reg = fresh_registry

    report = tmp_path / "big_report.txt"
    report.write_text("x" * 5000)

    reg.register("big-1", "GEMINI")
    reg.complete("big-1", "completed", str(report))

    from dictator import ws_server
    with patch.object(ws_server, "event_bus", bus), \
         patch.object(ws_server, "task_registry", reg):
        result = await ws_server.handle_await({
            "task_ids": ["big-1"],
            "include_reports": True,
        })

    content = result["tasks"]["big-1"]["report"]
    assert len(content) < 5000
    assert "[TRUNCATED]" in content


# ── recommend_capability ──────────────────────────────────────────────

def test_recommend_shell_for_grep():
    from dictator.tools_legion import _recommend_capability_impl
    r = _recommend_capability_impl("grep for TODO in all python files")
    assert r["recommendation"] == "SAFE_SHELL"


def test_recommend_gemini_for_analysis():
    from dictator.tools_legion import _recommend_capability_impl
    r = _recommend_capability_impl("analyze the authentication architecture")
    assert r["recommendation"] == "GEMINI"


def test_recommend_codex_for_fix():
    from dictator.tools_legion import _recommend_capability_impl
    r = _recommend_capability_impl("fix the typo in config.py")
    assert r["recommendation"] == "CODEX"


def test_recommend_shell_for_build():
    from dictator.tools_legion import _recommend_capability_impl
    r = _recommend_capability_impl("run the test suite and build")
    assert r["recommendation"] == "SAFE_SHELL"


# ── _is_busy ──────────────────────────────────────────────────────────

def test_is_busy_detects_rate_limit():
    from dictator.tools_legion import _is_busy
    assert _is_busy({"ok": False, "stdout": "Error: rate_limit_exceeded"}) is True
    assert _is_busy({"ok": False, "stderr": "503 service temporarily unavailable"}) is True


def test_is_busy_false_for_success():
    from dictator.tools_legion import _is_busy
    assert _is_busy({"ok": True, "stdout": "rate_limit"}) is False


def test_is_busy_false_for_normal_error():
    from dictator.tools_legion import _is_busy
    assert _is_busy({"ok": False, "stdout": "file not found"}) is False
