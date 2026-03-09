"""ROME MCP Server core — shared config, paths, run_cmd, FastMCP instance."""

from collections.abc import Callable
import asyncio
import json
import os
import sys
import time as _time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from dictator.rome_log import log_event

# ── Config ─────────────────────────────────────────────────────────────
_CFG_PATH = Path(__file__).parent / "config.json"
_cfg = {}
if _CFG_PATH.exists():
    try:
        _cfg = json.loads(_CFG_PATH.read_text())
    except Exception:
        pass

# ── Paths (all from config.json, with hardcoded fallbacks) ─────────────
ROOT_DIR = Path(_cfg.get("root_dir", "/var/www/ftk_lms"))
GIT_ROOT = Path(_cfg.get("git_root", "/home/paul-kane/projects/Drupal11"))
ROME_ROOT = Path(os.environ.get("ROME_ROOT", _cfg.get("rome_root", "/home/paul-kane/projects/rome-core")))
ARSENAL_PATH = ROME_ROOT / "arsenal" / "core_arsenal.json"
SKYRIM_STATE_FILE = Path(
    _cfg.get("skyrim_state_file",
             "/media/paul-kane/SteamGames/steamapps/compatdata/489830/pfx/drive_c/tmp/skyrim_state.json")
)
_mo2_raw = _cfg.get("mo2_downloads", "~/Games/MO2/downloads")
MO2_DOWNLOADS = Path(_mo2_raw).expanduser()

# Drupal paths (Phase 4: config-driven, no more hardcoded in tools_drupal)
DRUPAL_MODULES_SRC = Path(_cfg.get("drupal_modules_src", "/home/paul-kane/projects/Drupal11/modules/custom/"))
DRUPAL_MODULES_DEST = Path(_cfg.get("drupal_modules_dest", "/var/www/ftk_lms/web/modules/custom/"))
DRUPAL_THEMES_SRC = Path(_cfg.get("drupal_themes_src", "/home/paul-kane/projects/Drupal11/themes/custom/"))
DRUPAL_THEMES_DEST = Path(_cfg.get("drupal_themes_dest", "/var/www/ftk_lms/web/themes/custom/"))

# Skyrim/modding paths
PAPYRUS_COMPILER = Path(_cfg.get("papyrus_compiler", "/media/paul-kane/SteamGames/Games/mods/compile_papyrus.sh"))

# ── Server ─────────────────────────────────────────────────────────────
mcp = FastMCP("asshole")
DAEMON_START_TIME = _time.monotonic()

# ── Event Bus & Task Registry (Phase 1 WS) ────────────────────────────
from dictator.events import EventBus, TaskRegistry
event_bus = EventBus(source="dictator")
task_registry = TaskRegistry()

MAX_BUF = _cfg.get("max_output_bytes", 10 * 1024 * 1024)


async def run_cmd(
    cmd: str,
    cwd: str | Path = ROOT_DIR,
    env: dict | None = None,
    max_output: int = MAX_BUF,
) -> dict:
    """Run a shell command and return {ok, stdout, stderr} or error info."""
    t0 = _time.monotonic()
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        stdout_b, stderr_b = await proc.communicate()
        elapsed = _time.monotonic() - t0

        truncated = len(stdout_b) > max_output or len(stderr_b) > max_output
        stdout = stdout_b.decode(errors="replace")[:max_output]
        stderr = stderr_b.decode(errors="replace")[:max_output]
        if truncated:
            stdout += "\n[ROME: output truncated at 10MB]"
            log_event(tool="run_cmd", status="truncated", duration_s=elapsed, message=cmd[:200])

        result: dict
        if proc.returncode == 0:
            result = {"ok": True, "stdout": stdout, "stderr": stderr}
        else:
            result = {
                "ok": False,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        if truncated:
            result["truncated"] = True

        log_event(tool="run_cmd", status="ok" if result["ok"] else "error", duration_s=elapsed, message=cmd[:200])
        return result
    except Exception as e:
        elapsed = _time.monotonic() - t0
        log_event(tool="run_cmd", status="exception", duration_s=elapsed, message=str(e)[:200])
        return {"ok": False, "message": str(e)}


async def run_cmd_stream(
    cmd: str,
    cwd: str | Path = ROOT_DIR,
    env: dict | None = None,
    max_output: int = MAX_BUF,
    on_stderr: Callable | None = None,
) -> dict:
    """Like run_cmd but streams stderr to terminal in real-time (for legion progress bars)."""
    t0 = _time.monotonic()
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=True,
        )

        stderr_chunks = []

        async def _stream_stderr():
            while True:
                chunk = await proc.stderr.read(1024)
                if not chunk:
                    break
                
                stderr_chunks.append(chunk)
                if on_stderr:
                    try:
                        # Call progress callback if it looks like a progress line
                        text = chunk.decode(errors="replace")
                        for line in text.splitlines():
                            on_stderr(line.strip())
                    except Exception:
                        pass

        stderr_task = asyncio.create_task(_stream_stderr())
        stdout_b = await proc.stdout.read()
        await stderr_task
        await proc.wait()
        elapsed = _time.monotonic() - t0

        stderr_b = b"".join(stderr_chunks)
        truncated = len(stdout_b) > max_output or len(stderr_b) > max_output
        stdout = stdout_b.decode(errors="replace")[:max_output]
        stderr = stderr_b.decode(errors="replace")[:max_output]
        if truncated:
            stdout += "\n[ROME: output truncated at 10MB]"
            log_event(tool="run_cmd_stream", status="truncated", duration_s=elapsed, message=cmd[:200])

        result: dict
        if proc.returncode == 0:
            result = {"ok": True, "stdout": stdout, "stderr": stderr}
        else:
            result = {
                "ok": False,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        if truncated:
            result["truncated"] = True

        log_event(tool="run_cmd_stream", status="ok" if result["ok"] else "error", duration_s=elapsed, message=cmd[:200])
        return result
    except Exception as e:
        elapsed = _time.monotonic() - t0
        log_event(tool="run_cmd_stream", status="exception", duration_s=elapsed, message=str(e)[:200])
        return {"ok": False, "message": str(e)}
