"""ROME core — shared config, paths, run_cmd, events."""

from collections.abc import Callable
import asyncio
import json
import os
import sys
import time as _time
import uuid
from pathlib import Path

from dictator.rome_log import log_event

# ── Config ─────────────────────────────────────────────────────────────
_CFG_PATH = Path(__file__).parent / "config.json"
_cfg = {}
if _CFG_PATH.exists():
    try:
        with open(_CFG_PATH) as f:
            _cfg = json.load(f)
    except Exception:
        pass

# ── Paths (all from config.json, with ~ expansion) ────────────────────
def _p(key: str, fallback: str) -> Path:
    return Path(_cfg.get(key, fallback)).expanduser()

ROOT_DIR = _p("root_dir", "/var/www/ftk_lms")
GIT_ROOT = _p("git_root", "~/projects/Drupal11")
ROME_ROOT = Path(__file__).resolve().parent.parent
IS_DAEMON = False
ARSENAL_PATH = ROME_ROOT / "arsenal" / "core_arsenal.json"

# Drupal paths
DRUPAL_MODULES_SRC = _p("drupal_modules_src", "~/projects/Drupal11/modules/custom/")
DRUPAL_MODULES_DEST = _p("drupal_modules_dest", "/var/www/ftk_lms/web/modules/custom/")
DRUPAL_THEMES_SRC = _p("drupal_themes_src", "~/projects/Drupal11/themes/custom/")
DRUPAL_THEMES_DEST = _p("drupal_themes_dest", "/var/www/ftk_lms/web/themes/custom/")

# ── Event Bus & Task Registry (Phase 1 WS) ────────────────────────────
from dictator.events import EventBus, TaskRegistry
event_bus = EventBus(source="dictator")
task_registry = TaskRegistry()
DAEMON_START_TIME = _time.monotonic()
DAEMON_START_WALL = _time.time()
SESSION_ID = str(uuid.uuid4())

MAX_BUF = _cfg.get("max_output_bytes", 10 * 1024 * 1024)
LLM_LIMIT = 100 * 1024  # 100KB soft limit for LLM context safety


async def run_cmd(
    cmd: str | list[str],
    cwd: str | Path = ROOT_DIR,
    env: dict | None = None,
    max_output: int = LLM_LIMIT,
) -> dict:
    """Run a shell command and return {ok, stdout, stderr} or error info."""
    t0 = _time.monotonic()
    try:
        if isinstance(cmd, list):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
        else:
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
            stdout += "\n[ROME: output truncated]"
            log_event(tool="run_cmd", status="truncated", duration_s=elapsed, message=str(cmd)[:200])

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
        
        log_event(tool="run_cmd", status="ok" if result["ok"] else "error", duration_s=elapsed, message=str(cmd)[:200])
        return result
    except Exception as e:
        elapsed = _time.monotonic() - t0
        log_event(tool="run_cmd", status="exception", duration_s=elapsed, message=f"{type(e).__name__}: {str(e)} | cmd={str(cmd)}")
        return {"ok": False, "message": f"{type(e).__name__}: {str(e)}"}


async def run_cmd_stream(
    cmd: str | list[str],
    cwd: str | Path = ROOT_DIR,
    env: dict | None = None,
    max_output: int = MAX_BUF,
    on_stderr: Callable | None = None,
) -> dict:
    """Like run_cmd but streams stderr to terminal in real-time (for legion progress bars)."""
    t0 = _time.monotonic()
    try:
        if isinstance(cmd, list):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
        else:
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
            stdout += "\n[ROME: output truncated]"
            log_event(tool="run_cmd_stream", status="truncated", duration_s=elapsed, message=str(cmd)[:200])

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

        log_event(tool="run_cmd_stream", status="ok" if result["ok"] else "error", duration_s=elapsed, message=str(cmd)[:200])
        return result
    except Exception as e:
        elapsed = _time.monotonic() - t0
        log_event(tool="run_cmd_stream", status="exception", duration_s=elapsed, message=f"{type(e).__name__}: {str(e)} | cmd={str(cmd)}")
        return {"ok": False, "message": f"{type(e).__name__}: {str(e)}"}

class DictatorResponse:
    """Standardized response format for all ROME tools."""
    def __init__(self, ok: bool = True, message: str = "", data: any = None, error: str = "", **metadata):
        self.ok = ok
        self.message = message
        self.data = data
        self.error = error
        self.metadata = metadata

    def to_dict(self) -> dict:
        res = {"ok": self.ok}
        if self.message: res["message"] = self.message
        if self.error: res["error"] = self.error
        if self.data is not None: res["data"] = self.data
        if self.metadata: res.update(self.metadata)
        return res

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def success(cls, message: str = "OK", data: any = None, **metadata):
        return cls(ok=True, message=message, data=data, **metadata)

    @classmethod
    def fail(cls, error: str, message: str = "Error", **metadata):
        return cls(ok=False, error=error, message=message, **metadata)

from functools import wraps

def dictator_tool(func):
    """Decorator to standardize tool responses and handle exceptions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, DictatorResponse):
                return str(result)
            if isinstance(result, dict) and "ok" in result:
                return json.dumps(result)
            return result
        except Exception as e:
            return str(DictatorResponse.fail(error=str(e), message=f"Exception in {func.__name__}"))
    return wrapper
