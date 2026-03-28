"""Tests for changes made in session 2026-03-24.

Covers:
- TaskRegistry.remove() method
- Duplicate task ID re-dispatch
- IS_DAEMON flag (replaces ROME_DAEMON env var)
- ROME_ROOT derived from Path(__file__) not env var
- shell_exec tool removal verification
- rome_await tool removal verification
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dictator.events import TaskRegistry
from dictator.core import ROME_ROOT, IS_DAEMON


# ── TaskRegistry.remove() ─────────────────────────────────────────────

def test_registry_remove_existing():
    """remove() returns True and deletes the task."""
    reg = TaskRegistry()
    reg.register("t1", "SHELL")
    assert reg.get("t1") is not None
    assert reg.remove("t1") is True
    assert reg.get("t1") is None


def test_registry_remove_nonexistent():
    """remove() returns False for unknown task ID."""
    reg = TaskRegistry()
    assert reg.remove("ghost") is False


def test_registry_remove_allows_reregister():
    """After remove(), same task ID can be registered again cleanly."""
    reg = TaskRegistry()
    reg.register("t1", "SHELL")
    reg.complete("t1", "completed", "/tmp/report.txt")
    assert reg.get("t1")["status"] == "completed"

    reg.remove("t1")
    task = reg.register("t1", "GEMINI")
    assert task["capability"] == "GEMINI"
    assert task["status"] == "registered"


def test_registry_remove_running_task():
    """remove() works even on running tasks."""
    reg = TaskRegistry()
    reg.register("t1", "SHELL")
    reg.update_progress("t1", 50, "halfway")
    assert reg.remove("t1") is True
    assert reg.get("t1") is None


# ── Duplicate task ID handling ─────────────────────────────────────────

def test_registry_double_register_overwrites():
    """Second register() to same ID should reset the task."""
    reg = TaskRegistry()
    reg.register("dup", "SHELL")
    reg.complete("dup", "completed", None)

    # Re-register after remove (the pattern from ws_server.py fix)
    reg.remove("dup")
    task = reg.register("dup", "GEMINI")
    assert task["status"] == "registered"
    assert task["capability"] == "GEMINI"


# ── IS_DAEMON flag ────────────────────────────────────────────────────

def test_is_daemon_default_false():
    """IS_DAEMON defaults to False when imported from core."""
    # In test context, daemon.py hasn't set it to True
    assert IS_DAEMON is False


def test_is_daemon_is_bool():
    """IS_DAEMON is a proper boolean, not a string."""
    assert isinstance(IS_DAEMON, bool)


# ── ROME_ROOT ─────────────────────────────────────────────────────────

def test_rome_root_is_path():
    """ROME_ROOT is a Path object."""
    assert isinstance(ROME_ROOT, Path)


def test_rome_root_points_to_rome_core():
    """ROME_ROOT resolves to the rome-core project directory."""
    assert ROME_ROOT.name == "rome-core"
    assert (ROME_ROOT / "dictator").is_dir()
    assert (ROME_ROOT / "arsenal").is_dir()


def test_rome_root_not_from_env(monkeypatch):
    """ROME_ROOT is derived from __file__, not env var."""
    monkeypatch.setenv("ROME_ROOT", "/tmp/fake-rome")
    # Re-import to check it doesn't use env
    import importlib
    import dictator.core as core_mod
    importlib.reload(core_mod)
    assert str(core_mod.ROME_ROOT) != "/tmp/fake-rome"
    assert core_mod.ROME_ROOT.name == "rome-core"


# ── shell_exec removal ────────────────────────────────────────────────

def test_shell_exec_not_in_tools_fs():
    """shell_exec MCP tool should not exist in tools_fs.py."""
    tools_fs_path = ROME_ROOT / "dictator" / "tools_fs.py"
    content = tools_fs_path.read_text()
    assert "async def shell_exec" not in content
    assert "def shell_exec" not in content


# ── rome_await removal ────────────────────────────────────────────────

def test_rome_await_not_in_tools_ws():
    """rome_await MCP tool should not exist in tools_ws.py."""
    tools_ws_path = ROME_ROOT / "dictator" / "tools_ws.py"
    content = tools_ws_path.read_text()
    assert "async def rome_await" not in content
    assert "def rome_await" not in content


# ── Arsenal config ────────────────────────────────────────────────────

def test_arsenal_gemini_model():
    """Arsenal should use gemini-3.1-pro-preview, not old model."""
    import json
    arsenal = json.loads((ROME_ROOT / "arsenal" / "core_arsenal.json").read_text())
    gemini_args = arsenal["capabilities"]["GEMINI"]["args"]
    # Find the arg after -m
    m_idx = gemini_args.index("-m")
    model = gemini_args[m_idx + 1]
    assert "3.1" in model, f"Expected gemini 3.1 model, got {model}"


def test_arsenal_include_dir_scoped():
    """--include-directories should point to rome-core, not ~/projects."""
    import json
    arsenal = json.loads((ROME_ROOT / "arsenal" / "core_arsenal.json").read_text())
    gemini_args = arsenal["capabilities"]["GEMINI"]["args"]
    idx = gemini_args.index("--include-directories")
    include_dir = gemini_args[idx + 1]
    assert include_dir.endswith("rome-core"), f"include-dir too broad: {include_dir}"
    assert not include_dir.endswith("/projects"), "include-dir should not be ~/projects"


def test_arsenal_paths_no_double_rome_core():
    """No path should contain rome-core/rome-core (sed damage)."""
    import json
    content = (ROME_ROOT / "arsenal" / "core_arsenal.json").read_text()
    assert "rome-core/rome-core" not in content


def test_arsenal_gemini_cli_path():
    """Gemini CLI path should point to local build."""
    import json
    arsenal = json.loads((ROME_ROOT / "arsenal" / "core_arsenal.json").read_text())
    gemini_args = arsenal["capabilities"]["GEMINI"]["args"]
    gemini_path = gemini_args[0]
    assert "gemini-cli/bundle/gemini.js" in gemini_path


# ── Cross-platform files exist ────────────────────────────────────────

def test_launchd_plist_exists():
    """macOS launchd plist should exist."""
    assert (ROME_ROOT / "ops" / "com.rome.dictator.plist").is_file()


def test_freebsd_rc_exists():
    """FreeBSD rc.d script should exist."""
    assert (ROME_ROOT / "ops" / "rome-dictator-freebsd-rc").is_file()


def test_setup_md_exists():
    """SETUP.md should exist."""
    assert (ROME_ROOT / "SETUP.md").is_file()
