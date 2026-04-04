"""ROME WebSocket endpoint and connection manager."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shlex
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
import yaml

from websockets.exceptions import ConnectionClosed

from dictator.core import event_bus, task_registry, DAEMON_START_TIME, DAEMON_START_WALL, ROME_ROOT, ARSENAL_PATH, IS_DAEMON
from dictator.events import RomeEvent, emit_complete, emit_cost_update, emit_dispatch_start, emit_error, emit_capability_status, emit_system_status
from dictator.tools_legion import _execute_legion_impl, _resolve_arsenal_paths

logger = logging.getLogger("rome.daemon")


# ── WebSocket Adapter ─────────────────────────────────────────────────
# Wraps websockets.ServerConnection to match the Starlette WebSocket API
# used throughout this file (send_json, receive_json, headers, query_params, close).

class WebSocketDisconnect(Exception):
    """Raised when the WebSocket client disconnects."""

class WSAdapter:
    """Adapts websockets.ServerConnection to Starlette-like WebSocket API."""

    def __init__(self, ws):
        self._ws = ws
        self._request = ws.request
        # Build headers dict from request
        self.headers = {k.lower(): v for k, v in self._request.headers.raw_items()}
        # Parse query params from path
        parsed = urlparse(self._request.path)
        qs = parse_qs(parsed.query)
        self.query_params = {k: v[0] if len(v) == 1 else v for k, v in qs.items()}

    async def accept(self):
        pass  # websockets auto-accepts after handshake

    async def receive_json(self) -> dict:
        try:
            raw = await self._ws.recv()
            return json.loads(raw)
        except ConnectionClosed:
            raise WebSocketDisconnect()

    async def send_json(self, data: dict) -> None:
        try:
            await self._ws.send(json.dumps(data))
        except ConnectionClosed:
            pass

    async def close(self, code: int = 1000) -> None:
        await self._ws.close(code)

CONFIG_PATH = Path(ROME_ROOT) / "dictator" / "config.json"
# Resolve GEMINI_CLI from arsenal → config → PATH fallback
def _resolve_gemini_cli() -> str:
    try:
        arsenal = _resolve_arsenal_paths(json.loads(ARSENAL_PATH.read_text()))
        return arsenal.get("capabilities", {}).get("GEMINI", {}).get("args", ["gemini"])[0]
    except Exception:
        pass
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        return str(Path(cfg["gemini_cli"]).expanduser())
    except Exception:
        pass
    return shutil.which("gemini") or "gemini"
GEMINI_CLI = _resolve_gemini_cli()

FALLBACK_CHAIN = {"GEMINI": "CODEX", "CODEX": "OPENCODE"}
BUSY_PATTERNS = ["service temporarily unavailable", "overloaded", "rate_limit",
                 "rate limit", "quota", "503", "429", "capacity"]

CACHE_DIR = ROME_ROOT / "legions" / ".cache"
CACHE_TTL = 3600  # 1 hour
MAX_OUTPUT_CHARS = 2000


def _is_busy(r: dict) -> bool:
    if r.get("ok"):
        return False
    text = (r.get("stdout", "") + r.get("stderr", "")).lower()
    # Also check if it's a dict with an 'error' or 'message' field
    if not text:
        text = str(r.get("error", "") + r.get("message", "")).lower()
    return any(p in text for p in BUSY_PATTERNS)

_SESSION_USAGE = {"worker_tokens": 0, "dictator_tokens": 0, "cost_usd": 0.0, "dictator_model": ""}


def _cache_key(capability: str, args: list, task_dir=None) -> str:
    key_str = f"{capability}:{':'.join(str(a) for a in args)}"
    if task_dir:
        t_md = task_dir / "task.md"
        if t_md.exists():
            try:
                key_str += ":" + t_md.read_text(encoding="utf-8")
            except Exception:
                pass
    for arg in args:
        if isinstance(arg, str) and arg.endswith(".md") and Path(arg).exists():
            try:
                key_str += ":" + Path(arg).read_text(encoding="utf-8")
            except Exception:
                pass
    return hashlib.sha256(key_str.encode()).hexdigest()[:16]


def _recommend_capability_impl(task_description: str) -> dict:
    """Core logic for capability recommendation."""
    desc = task_description.lower()
    word_count = len(desc.split())

    kw_gemini = ["review", "analyze", "security", "architect", "complex", "audit", "refactor", "design"]
    kw_centurion = ["multi-step", "complex", "review and fix", "analyze and edit", "refactor across"]
    kw_codex = ["fix", "implement", "update", "write", "add", "small", "patch", "rename"]
    kw_shell = ["grep", "build", "test", "find", "run", "execute", "shell", "bash", "compile", "move", "copy", "delete"]

    files_match = re.search(r'(\d+)\s+files?', desc)
    lines_match = re.search(r'(\d+)\s+lines?', desc)
    file_count = int(files_match.group(1)) if files_match else 0
    line_count = int(lines_match.group(1)) if lines_match else 0

    sg = sum(1 for k in kw_gemini if k in desc)
    scen = sum(1 for k in kw_centurion if k in desc)
    sc = sum(1 for k in kw_codex if k in desc)
    ss = sum(1 for k in kw_shell if k in desc)

    if file_count > 10 or line_count > 1000:
        sg += 3

    if ss > sg and ss > scen and ss > sc:
        rec, reason = "SAFE_SHELL", "Task dominated by execution/search/build operations."
    elif sg >= scen and sg >= sc and word_count <= 50:
        rec, reason = "GEMINI", "High reasoning or large context requirements detected."
    elif scen >= sc or word_count > 50:
        rec, reason = "CENTURION", "Multi-step complex task requiring orchestrator oversight."
    else:
        rec, reason = "CODEX", "Focused implementation or small fix with moderate context."

    return {
        "recommendation": rec,
        "reasoning": reason,
        "scores": {"gemini": sg, "centurion": scen, "codex": sc, "shell": ss},
    }


async def _summarize_report(content: str, max_input_lines: int = 200) -> str:
    """Summarize a report via Gemini Flash. Returns digest or original on failure."""
    lines = content.splitlines()
    if len(lines) > max_input_lines:
        # Keep first 150 + last 50 lines
        truncated = lines[:150] + ["", f"... ({len(lines) - 200} lines omitted) ...", ""] + lines[-50:]
        content = "\n".join(truncated)

    prompt = (
        "Summarize this task report in 3-5 bullet points. "
        "Flag any errors or failures prominently. "
        "Be extremely concise — no preamble, no markdown headers.\n\n"
        f"```\n{content}\n```"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            GEMINI_CLI, "-p", prompt,
            "--output-format", "json", "--sandbox", "false",
            "-m", "gemini-3.1-pro-preview",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        import logging
        if proc.returncode == 0 and stdout:
            raw = stdout.decode()
            # Gemini CLI may prepend non-JSON warnings — find first '{'
            json_start = raw.find("{")
            if json_start >= 0:
                data = json.loads(raw[json_start:])
                return data.get("response", content[:500])
    except Exception:
        pass
    # Fallback: head/tail truncation
    if len(lines) > 20:
        return "\n".join(lines[:15] + [f"... ({len(lines) - 20} lines omitted) ..."] + lines[-5:])
    return content

def _load_config_token() -> str:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return str(config.get("ws_token") or "").strip()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""


async def _get_session_usage(dictator_model: str = "") -> dict[str, Any]:
    """Scan rome.jsonl for all usage events (all-time, survives restarts).
    If dictator_model is set, only counts dictator entries matching that model."""
    log_path = ROME_ROOT / "logs" / "rome.jsonl"
    if not log_path.exists():
        return {"worker_tokens": 0, "dictator_tokens": 0, "cost_usd": 0.0}

    worker_tokens = 0
    dictator_tokens = 0
    cost_usd = 0.0

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    usage = entry.get("usage", {})
                    if not usage: continue

                    tokens = int(usage.get("total_tokens", 0))
                    cost = float(usage.get("cost_usd", 0.0) or 0.0)
                    is_worker = entry.get("tool") == "legion_wrapper"

                    if not is_worker and dictator_model:
                        entry_model = usage.get("model", "")
                        if entry_model and entry_model != dictator_model:
                            continue

                    if is_worker:
                        worker_tokens += tokens
                    else:
                        dictator_tokens += tokens

                    cost_usd += cost
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        logger.error("Error reading session usage from log: %s", e)

    return {
        "worker_tokens": worker_tokens,
        "dictator_tokens": dictator_tokens,
        "cost_usd": round(cost_usd, 6)
    }


async def _load_capabilities() -> dict[str, bool]:
    # ARSENAL_PATH is already imported
    import json
    import asyncio
    import os
    import logging
    import shutil

    capabilities_status = {}
    try:
        if not ARSENAL_PATH.exists():
            logging.getLogger("rome.daemon").warning("Arsenal file not found at %s", ARSENAL_PATH)
            return {}

        with open(ARSENAL_PATH, "r", encoding="utf-8") as f:
            arsenal_config = _resolve_arsenal_paths(json.load(f))
        
        # Get capabilities currently served by persistent workers
        worker_caps = set()
        for worker in await worker_registry.get_info():
            worker_caps.update(worker.get("capabilities", []))

        for capability_name, details in arsenal_config.get("capabilities", {}).items():
            exec_path = details.get("exec", "")
            
            # 1. Internal commands (always available)
            if exec_path == "internal":
                capabilities_status[capability_name] = True
            
            # 2. Persistent worker capabilities (green if worker connected)
            elif capability_name in worker_caps:
                capabilities_status[capability_name] = True

            # 3. Subprocess LLM capabilities (green if binary exists on PATH)
            elif capability_name in {"GEMINI", "CLAUDE", "CODEX", "OPENCODE"}:
                cli_args = details.get("args", [])
                cli_bin = cli_args[0] if cli_args else exec_path
                capabilities_status[capability_name] = bool(shutil.which(cli_bin) or Path(cli_bin).exists())
            
            # 3. Local capabilities (fallback to disk check)
            elif exec_path:
                capabilities_status[capability_name] = Path(exec_path).exists() or shutil.which(exec_path) is not None
            
            else:
                capabilities_status[capability_name] = False
                
    except FileNotFoundError:
        logging.getLogger("rome.daemon").warning("Arsenal file not found at %s", ARSENAL_PATH)
    except json.JSONDecodeError:
        logging.getLogger("rome.daemon").error("Error decoding JSON from %s", ARSENAL_PATH)
    except Exception as e:
        logging.getLogger("rome.daemon").error("ERROR loading capabilities: %s", e, exc_info=True)
    return capabilities_status

_WEBSOCKET_TOKEN = ""

_session_chars = 0  # cumulative chars returned to native client this session
_LEAN_THRESHOLD = 100_000  # chars before switching to lean mode
_ULTRA_LEAN_THRESHOLD = 300_000  # chars before ultra-lean mode

def _track_output(text: str) -> str:
    """Track cumulative output size and return the text unchanged."""
    global _session_chars
    _session_chars += len(text)
    return text

def get_lean_level() -> int:
    """0=normal, 1=lean (>100K chars), 2=ultra-lean (>300K chars)."""
    if _session_chars >= _ULTRA_LEAN_THRESHOLD:
        return 2
    if _session_chars >= _LEAN_THRESHOLD:
        return 1
    return 0

_HEARTBEAT_SECONDS = 15
_ACTIVE_TASKS: dict[str, asyncio.Task[Any]] = {}
_ACTIVE_TASKS_LOCK = asyncio.Lock()


# ---------------------------------------------------------------------------
# Persistent Worker Registry
# ---------------------------------------------------------------------------

class _WorkerEntry:
    __slots__ = ("ws", "capabilities", "busy_tasks", "connected_at", "version", "platform")

    def __init__(self, ws: WebSocket, capabilities: list[str], version: str = "", platform: str = "") -> None:
        self.ws = ws
        self.capabilities = [c.upper() for c in capabilities]
        self.busy_tasks: set[str] = set()
        self.connected_at = time.time()
        self.version = version
        self.platform = platform


class WorkerRegistry:
    """Tracks persistent worker connections (e.g. gemini --rome-daemon)."""

    def __init__(self) -> None:
        self._workers: dict[int, _WorkerEntry] = {}  # keyed by id(ws)
        self._lock = asyncio.Lock()

    async def register(self, ws: WebSocket, capabilities: list[str], version: str = "", platform: str = "") -> None:
        async with self._lock:
            self._workers[id(ws)] = _WorkerEntry(ws, capabilities, version, platform)

    async def unregister(self, ws: WebSocket) -> list[str]:
        """Remove worker. Returns list of task_ids that were still busy (need cleanup)."""
        async with self._lock:
            entry = self._workers.pop(id(ws), None)
        return list(entry.busy_tasks) if entry else []

    async def find_worker(self, capability: str) -> WebSocket | None:
        """Find an idle worker that supports the given capability."""
        cap = capability.upper()
        async with self._lock:
            for entry in self._workers.values():
                if cap in entry.capabilities and len(entry.busy_tasks) == 0:
                    return entry.ws
        return None

    async def mark_busy(self, ws: WebSocket, task_id: str) -> None:
        async with self._lock:
            entry = self._workers.get(id(ws))
            if entry:
                entry.busy_tasks.add(task_id)

    async def mark_idle(self, ws: WebSocket, task_id: str) -> None:
        async with self._lock:
            entry = self._workers.get(id(ws))
            if entry:
                entry.busy_tasks.discard(task_id)

    async def get_info(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [
                {
                    "worker_id": str(id(e.ws)),
                    "capabilities": e.capabilities,
                    "busy_tasks": list(e.busy_tasks),
                    "connected_at": e.connected_at,
                    "version": e.version,
                    "platform": e.platform,
                }
                for e in self._workers.values()
            ]

    async def get_ws_by_id(self, worker_id: str) -> WebSocket | None:
        async with self._lock:
            try:
                wid = int(worker_id)
                entry = self._workers.get(wid)
                return entry.ws if entry else None
            except ValueError:
                return None


worker_registry = WorkerRegistry()


def _event_to_json(event: RomeEvent) -> dict[str, Any]:
    return {
        "type": "event",
        "event": {
            "type": event.type,
            "task_id": event.task_id,
            "ts": event.ts,
            "sequence": event.sequence,
            "source": event.source,
            "payload": event.payload,
        },
    }


def _response(request_id: str | None, ok: bool, payload: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "response",
        "request_id": request_id,
        "ok": ok,
        "payload": payload or {},
    }
    if error:
        body["error"] = error
    return body


class OrchestratorUI:
    def __init__(self, task_ids):
        self.task_ids = task_ids
        self.stats = {tid: {"percent": 0, "msg": "Standing by", "elapsed": 0.0, "status": "PENDING"} for tid in task_ids}
        self.lock = threading.Lock()

    def update(self, task_id, line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            with self.lock:
                self.stats[task_id].update({
                    "percent": int(m.group(1)),
                    "elapsed": float(m.group(2)),
                    "msg": m.group(3).strip(),
                })
        elif any(x in line.upper() for x in ("MISSION COMPLETE", "SUCCESS", "COMPLETED")):
            with self.lock:
                self.stats[task_id]["status"] = "SUCCESS"
                self.stats[task_id]["percent"] = 100
        elif any(x in line.upper() for x in ("FAILED", "ERR:")):
            with self.lock:
                self.stats[task_id]["status"] = "FAILED"


async def _execute_legion_native(
    task_id: str,
    capability: str,
    args: list[str],
    input_files: list[str] | None = None,
    no_cache: bool = False,
    prompt_file: str = "",
    _is_retry: bool = False,
    parent_task_id: str | None = None,
) -> dict:
    t0 = time.monotonic()
    capability = capability.upper()
    if not task_registry.get(task_id):
        task_registry.register(task_id, capability, parent_task_id=parent_task_id)
        await emit_dispatch_start(event_bus, task_id, capability)

    async def on_progress(line):
        m = re.search(r"(\d+)%\s+.\s+\[([\d.]+)s\]\s+(.*)", line)
        if m:
            try:
                p, msg = int(m.group(1)), m.group(3).strip()
                task_registry.update_progress(task_id, p, msg)
                await emit_progress(event_bus, task_id, p, msg)
            except Exception as e: logger.debug("Swallowed exception: %s", e)

    if capability == "AUTO":
        capability = _recommend_capability_impl(args[0] if args else "")["recommendation"].upper()

    if not ARSENAL_PATH.exists(): return {"ok": False, "error": "Arsenal missing"}
    arsenal = _resolve_arsenal_paths(json.loads(ARSENAL_PATH.read_text()))
    cap = arsenal.get("capabilities", {}).get(capability)
    if not cap: return {"ok": False, "error": f"Cap {capability} unknown"}

    task_dir = ROME_ROOT / "legions" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    for f in (input_files or []):
        f_path = Path(f)
        src = f_path.resolve() if f_path.is_absolute() else (ROME_ROOT / f_path).resolve()
        dest = task_dir / f_path.name
        if src.exists() and src.resolve() != dest.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))

    if prompt_file:
        pf = Path(prompt_file)
        if pf.exists():
            (task_dir / "task.md").write_text(pf.read_text(encoding="utf-8"))
            if capability == "SAFE_SHELL": args = [pf.read_text()]

    if capability == "SAFE_SHELL":
        import subprocess as _sp
        shell_script = str(ROME_ROOT / "legions" / "shell_executor.py")
        try:
            proc = _sp.Popen(
                ["python3", shell_script, task_id, str(time.time()), args[0] if args else ""],
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, start_new_session=True,
            )
            return {"ok": True, "status": "DISPATCHED", "task_id": task_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    cap_args = " ".join(cap.get("args", []))
    quoted_args = shlex.quote(" ".join(args)) if cap_args.rstrip().endswith("-p") else " ".join(shlex.quote(a) for a in args)
    command = f"{cap['exec']} {task_id} {time.time()} {cap_args} {quoted_args}"

    # Cache check
    cache_f = CACHE_DIR / f"{_cache_key(capability, args, task_dir)}.json"
    if not no_cache and cache_f.exists():
        try:
            cached = json.loads(cache_f.read_text())
            if time.time() - cached.get("timestamp", 0) < CACHE_TTL:
                return json.loads(cached["result"])
        except Exception as e: logger.debug("Swallowed exception: %s", e)

    try:
        from dictator.core import run_cmd_stream
        r = await asyncio.wait_for(run_cmd_stream(command, cwd=task_dir, on_stderr=on_progress), timeout=cap.get("timeout", 300))
        
        # Fallback chain
        while not r.get("ok") and _is_busy(r) and FALLBACK_CHAIN.get(capability):
            capability = FALLBACK_CHAIN[capability]
            cap = arsenal["capabilities"][capability]
            command = f"{cap['exec']} {task_id} {time.time()} {' '.join(cap.get('args', []))} {shlex.quote(' '.join(args)) if ' '.join(cap.get('args', [])).endswith('-p') else quoted_args}"
            r = await asyncio.wait_for(run_cmd_stream(command, cwd=task_dir, on_stderr=on_progress), timeout=cap.get("timeout", 120))
    except Exception as e:
        return {"ok": False, "error": str(e)}

    ok, output = r.get("ok", False), r.get("stdout", "")
    report_f = task_dir / f"report_{task_id}.txt"
    if ok and not output.strip() and (not report_f.exists() or report_f.stat().st_size == 0) and not _is_retry:
        return await _execute_legion_native(task_id, capability, args, input_files, True, prompt_file, True, parent_task_id)

    # Usage parsing
    usage, manifest_f = None, task_dir / "manifest.json"
    if manifest_f.exists():
        try:
            m = json.loads(manifest_f.read_text())
            usage = m.get("usage")
        except Exception as e: logger.debug("Swallowed exception: %s", e)

    res = {"ok": ok, "task_id": task_id, "capability": capability, "elapsed_s": round(time.monotonic() - t0, 2), "usage": usage}
    if not ok: res["error"] = r.get("message", r.get("stderr", "unknown"))
    else: res["stdout"] = output

    if ok and len(output) > MAX_OUTPUT_CHARS:
        if not report_f.exists(): report_f.write_text(output)
        res["stdout"] = output[:200] + f"\n...[TRUNCATED: {report_f}]"
        res["report_path"] = str(report_f)

    if ok and not no_cache:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_f.write_text(json.dumps({"timestamp": time.time(), "result": json.dumps(res)}))
        except Exception as e: logger.debug("Swallowed exception: %s", e)

    return res


async def _emit_heartbeat(websocket: WSAdapter) -> None:
    while True:
        await asyncio.sleep(_HEARTBEAT_SECONDS)
        await websocket.send_json(
            {
                "type": "event",
                "event": {
                    "type": "heartbeat",
                    "task_id": None,
                    "ts": time.time(),
                    "payload": {},
                },
            }
        )


_ZOMBIE_TIMEOUT_SECONDS = 180  # 3 minutes at 0% with no update → auto-fail

async def _emit_system_status_loop() -> None:
    from dictator.events import emit_system_status
    from dictator.core import event_bus, task_registry, DAEMON_START_TIME
    import time, logging
    logger = logging.getLogger("rome.daemon")
    while True:
        await asyncio.sleep(30)
        now = time.time()
        tasks = task_registry.get_all()
        # Reap zombie tasks: stuck at 0% progress for too long
        for tid, t in tasks.items():
            if t.get("status") in {"registered", "running"} and t.get("progress_percent", 0) == 0:
                age = now - t.get("updated_at", t.get("created_at", now))
                if age > _ZOMBIE_TIMEOUT_SECONDS:
                    logger.warning("Reaping zombie task %s (stuck %ds at 0%%)", tid, int(age))
                    task_registry.complete(tid, "failed", None)
                    await emit_error(event_bus, tid, f"Reaped: no progress for {int(age)}s")
        # Re-read after reaping
        tasks = task_registry.get_all()
        active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
        uptime = round(time.monotonic() - DAEMON_START_TIME, 3)
        await emit_system_status(event_bus, active_tasks=active, uptime_s=uptime)

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WSAdapter] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WSAdapter) -> tuple[str, asyncio.Queue[RomeEvent]]:
        await websocket.accept()
        subscriber_id, queue = await event_bus.subscribe()
        async with self._lock:
            self._connections.add(websocket)
        return subscriber_id, queue

    async def disconnect(self, websocket: WSAdapter, subscriber_id: str | None) -> None:
        if subscriber_id:
            await event_bus.unsubscribe(subscriber_id)
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections)
        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.discard(websocket)

    async def relay_events(self, websocket: WSAdapter, queue: asyncio.Queue[RomeEvent]) -> None:
        while True:
            event = await queue.get()
            await websocket.send_json(_event_to_json(event))


manager = ConnectionManager()


async def _dispatch_runner(
    task_id: str,
    capability: str,
    prompt: str,
    input_files: list[str] | None,
    no_cache: bool,
    prompt_file: str,
    output_path: str | None = None,
) -> None:
    logger.info("_dispatch_runner START task=%s cap=%s", task_id, capability)
    if IS_DAEMON:
        task_registry.register(task_id, capability)
        await emit_dispatch_start(event_bus, task_id, capability)
        # Immediately mark as running so dashboard doesn't sit at REGISTERED
        task_registry.update_progress(task_id, 0, "Starting...")
    try:
        result = await _execute_legion_native(
            task_id=task_id,
            capability=capability,
            args=[prompt],
            input_files=input_files,
            no_cache=no_cache,
            prompt_file=prompt_file,
        )
        usage = result.get("usage")
        if usage is not None:
            if IS_DAEMON:
                task_registry.update_usage(task_id, usage)
                await emit_cost_update(event_bus, task_id, usage)
                total_tokens = usage.get("total_tokens")
                if total_tokens is not None:
                    task_registry.add_waste(total_tokens)

        # SAFE_SHELL fires shell_executor.py as a detached subprocess and returns
        # immediately with status="DISPATCHED".  The shell_executor owns the
        # completion lifecycle — it sends a "complete" event via WS when done.
        # Do NOT mark it completed here or the task will briefly flash "completed"
        # before shell_executor has even started.
        is_fire_and_forget = result.get("status") == "DISPATCHED"

        status = "completed" if result.get("ok") else "failed"
        report_path = result.get("report_path")
        if output_path and report_path:
            import shutil
            from pathlib import Path
            rp = Path(report_path)
            op = Path(output_path)
            if rp.exists() and rp.stat().st_size > 20:
                if not (op.exists() and op.stat().st_size > 0):
                    shutil.copy2(str(rp), str(op))
        if IS_DAEMON and not is_fire_and_forget:
            task_registry.complete(task_id, status, report_path)
            report_content = _read_report_content(report_path) if report_path else None
            await emit_complete(event_bus, task_id, status, report_path, usage, report=report_content)
        if not result.get("ok"):
            await emit_error(event_bus, task_id, str(result.get("error") or result.get("message") or "dispatch_failed"))
    except asyncio.CancelledError:
        if IS_DAEMON:
            task_registry.complete(task_id, "cancelled", None)
            await emit_complete(event_bus, task_id, "cancelled", None, None)
        raise
    except Exception as exc:
        import traceback, logging
        logging.getLogger("rome.daemon").error("_dispatch_runner EXCEPTION task=%s: %s", task_id, traceback.format_exc())
        if IS_DAEMON:
            task_registry.complete(task_id, "failed", None)
            await emit_error(event_bus, task_id, str(exc))
    finally:
        async with _ACTIVE_TASKS_LOCK:
            current = _ACTIVE_TASKS.get(task_id)
            if current is asyncio.current_task():
                _ACTIVE_TASKS.pop(task_id, None)


async def _dispatch_to_worker(ws: WebSocket, task_id: str, capability: str, prompt: str) -> None:
    """Forward a dispatch command to a persistent worker over WS."""
    import logging
    logger = logging.getLogger("rome.daemon")
    logger.info("Routing task %s (%s) to persistent worker", task_id, capability)
    await ws.send_json({
        "type": "command",
        "request_id": f"dispatch-{task_id}",
        "command": "dispatch",
        "payload": {
            "task_id": task_id,
            "capability": capability,
            "prompt": prompt,
        },
    })


async def handle_dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    capability = str(payload.get("capability") or "").strip().upper()
    prompt = str(payload.get("prompt") or "").strip()
    input_files = payload.get("input_files") or None
    no_cache = bool(payload.get("no_cache", False))
    prompt_file = str(payload.get("prompt_file") or "")
    if prompt_file and not prompt:
        prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    output_path = str(payload.get("output_path") or "") or None

    if not task_id:
        raise ValueError("payload.task_id is required")
    if not capability:
        raise ValueError("payload.capability is required")
    if not prompt and not prompt_file:
        raise ValueError("payload.prompt or payload.prompt_file is required")
    if input_files is not None and not isinstance(input_files, list):
        raise ValueError("payload.input_files must be a list when provided")

    # --- Native DSA Routing (ROME v4) ---
    if capability == "NATIVE_SHELL":
        if IS_DAEMON:
            task_registry.register(task_id, capability)
            await emit_dispatch_start(event_bus, task_id, capability)

        async def _run_native_background():
            try:
                # Execute immediately via native handler
                result = await handle_native_shell({"command": prompt})
                
                # Log and finalize in registry
                status = "completed" if result["ok"] else "failed"
                task_dir = ROME_ROOT / "legions" / task_id
                task_dir.mkdir(parents=True, exist_ok=True)
                rp = task_dir / f"report_{task_id}.txt"
                rp.write_text(result["stdout"] + "\n" + result["stderr"], encoding="utf-8")
                
                if IS_DAEMON:
                    task_registry.complete(task_id, status, str(rp))
                    await emit_complete(event_bus, task_id, status, str(rp), None, report=result["stdout"].strip())
            except Exception as e:
                if IS_DAEMON:
                    await emit_error(event_bus, task_id, str(e))

        # Launch in background and return immediately
        asyncio.create_task(_run_native_background(), name=f"native-shell-{task_id}")
        return {"task_id": task_id, "capability": capability, "accepted": True, "routed_to": "native_dsa_async"}

    # --- Persistent worker routing ---
    # Check if a persistent worker can handle this capability (skip if
    # input_files are set since workers don't have access to those via 
    # the forwarding protocol yet).
    worker_ws = None
    if not input_files and prompt:
        worker_ws = await worker_registry.find_worker(capability)

    if worker_ws is not None:
        # Register task in daemon's registry so await/status/dashboard work
        import os
        if IS_DAEMON:
            task_registry.register(task_id, capability)
            await emit_dispatch_start(event_bus, task_id, capability)
            task_registry.update_progress(task_id, 0, "Routing to persistent worker...")

        await worker_registry.mark_busy(worker_ws, task_id)
        try:
            await _dispatch_to_worker(worker_ws, task_id, capability, prompt)
        except Exception:
            # Worker died mid-send — fall through to subprocess
            await worker_registry.mark_idle(worker_ws, task_id)
            worker_ws = None

    if worker_ws is not None:
        return {"task_id": task_id, "capability": capability, "accepted": True, "routed_to": "persistent_worker"}

    # --- Fallback: spawn subprocess ---
    logger.info("handle_dispatch SPAWNING task=%s cap=%s", task_id, capability)
    task = asyncio.create_task(
        _dispatch_runner(task_id, capability, prompt, input_files, no_cache, prompt_file, output_path),
        name=f"rome-ws-dispatch-{task_id}",
    )
    def _task_done(t):
        if t.cancelled():
            logger.warning("Task %s was cancelled", task_id)
        elif t.exception():
            logger.error("Task %s CRASHED: %s", task_id, t.exception(), exc_info=t.exception())

    task.add_done_callback(_task_done)
    async with _ACTIVE_TASKS_LOCK:
        existing = _ACTIVE_TASKS.get(task_id)
        if existing and not existing.done():
            task.cancel()
            raise ValueError(f"task {task_id} is already running")
        _ACTIVE_TASKS[task_id] = task
        # Reset stale registry entry so re-dispatched tasks get clean state
        if task_registry.get(task_id):
            task_registry.remove(task_id)

    return {"task_id": task_id, "capability": capability, "accepted": True}


async def handle_submit_result(payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    content = str(payload.get("content") or "")
    if not task_id:
        raise ValueError("payload.task_id is required")

    task_dir = ROME_ROOT / "legions" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    report_path = task_dir / f"report_{task_id}.txt"
    report_path.write_text(content, encoding="utf-8")

    summary = None
    if len(content) > 2000:
        summary = await _summarize_report(content)
        task_registry.update_task(task_id, {"summary": summary})

    status = "completed"
    task_registry.complete(task_id, status, str(report_path))
    report_snippet = content[:4000] + "\n...[TRUNCATED]" if len(content) > 4000 else content
    await emit_complete(event_bus, task_id, status, str(report_path), None, report=report_snippet)

    return {"task_id": task_id, "status": status, "report_path": str(report_path)}


async def handle_native_shell(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a shell command natively via daemon's core.run_cmd."""
    command = payload.get("command")
    if not command:
        raise ValueError("command is required")

    from dictator.core import run_cmd
    logger.info("NATIVE_SHELL: %s", command)

    # Execute natively in the daemon's environment
    t0 = time.monotonic()
    result = await run_cmd(command)
    elapsed = round(time.monotonic() - t0, 3)

    return {
        "ok": result.get("ok", False),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "exit_code": result.get("exit_code", 0 if result.get("ok") else 1),
        "elapsed": elapsed,
    }


async def handle_interrupt(payload: dict[str, Any]) -> dict[str, Any]:
    """Interrupt/steer a running task or worker."""
    task_id = payload.get("task_id")
    worker_id = payload.get("worker_id") # Optional: steer by worker WS id
    interrupt_type = payload.get("type", "cancel") # cancel, inject_prompt, signal

    if not task_id and not worker_id:
        raise ValueError("task_id or worker_id is required")

    logger.info("INTERRUPT: %s on %s", interrupt_type, task_id or worker_id)

    if interrupt_type == "cancel" and task_id:
        return await handle_cancel({"task_id": task_id})

    # Forward to specific worker if requested
    if worker_id:
        target_ws = await worker_registry.get_ws_by_id(worker_id)
        if target_ws:
            await target_ws.send_json({
                "type": "interrupt",
                "payload": payload
            })
            return {"ok": True, "message": "Interrupt forwarded to worker"}

    if interrupt_type == "inject_prompt" and task_id:
        target_ws = await worker_registry.get_ws_by_task_id(task_id)
        if target_ws:
            await target_ws.send_json({"type": "steer", "payload": payload})
            return {"ok": True, "message": "Prompt injected"}

    return {"ok": False, "error": "Steering failed"}


async def handle_status(payload: dict[str, Any]) -> dict[str, Any]:
    lean_level = get_lean_level()
    caps = await _load_capabilities()
    workers = await worker_registry.get_info()

    if payload.get("summary"):
        tasks = task_registry.get_all()
        active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
        usage = await _get_session_usage(_SESSION_USAGE["dictator_model"])
        session_worker_tokens = usage["worker_tokens"]
        session_dictator_tokens = usage["dictator_tokens"]
        session_cost_usd = usage["cost_usd"]

        return {"ok": True, "active_tasks": active, "total_tasks": len(tasks),
                "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
                "capabilities": list(caps.keys()),
                "capability_status": caps,
                "workers": workers,
                "session_worker_tokens": session_worker_tokens,
                "session_dictator_tokens": session_dictator_tokens,
                "session_cost_usd": session_cost_usd}
    task_id = str(payload.get("task_id") or "").strip()
    if task_id:
        task = task_registry.get(task_id)
        return {"task": task, "found": task is not None, "workers": workers, "capability_status": caps}
    
    # Normal client request for all tasks
    all_tasks = task_registry.get_all()
    if lean_level >= 2: # Ultra-lean mode: only return active task count and IDs
        active_tasks_count = sum(1 for t in all_tasks.values() if t.get("status") in {"registered", "running"})
        return {"active_tasks_count": active_tasks_count, "task_ids": list(all_tasks.keys()), "workers": workers, "capability_status": caps}

    return {"tasks": all_tasks, "workers": workers, "capability_status": caps}


async def handle_cancel(payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("payload.task_id is required")

    async with _ACTIVE_TASKS_LOCK:
        task = _ACTIVE_TASKS.get(task_id)

    if task is None or task.done():
        # No running asyncio task — just clean the registry entry (zombie)
        removed = task_registry.remove(task_id)
        return {"task_id": task_id, "cancelled": removed, "reason": "cleaned" if removed else "not_found"}

    task.cancel()
    task_registry.remove(task_id)
    return {"task_id": task_id, "cancelled": True}


async def _handle_ping(_: dict[str, Any]) -> dict[str, Any]:
    return {"pong": True, "ts": time.time()}


def _read_report_content(report_path: str) -> str | None:
    from pathlib import Path
    rp = Path(report_path)
    if not rp.exists():
        return None
    try:
        content = rp.read_text(encoding="utf-8")
        # Truncate for context safety
        if len(content) > 4000:
            return content[:4000] + "\n...[TRUNCATED]"
        return content
    except Exception:
        return None

async def handle_read_report(payload: dict[str, Any]) -> dict[str, Any]:
    report_path = str(payload.get("report_path") or "").strip()
    if not report_path:
        raise ValueError("payload.report_path is required")
    content = _read_report_content(report_path)
    if content is None:
        return {"report_path": report_path, "content": "File not found or no report generated."}
    return {"report_path": report_path, "content": content}


async def handle_read_file(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload.get('path', '')).expanduser().resolve()
    start_line = int(payload.get('start_line', 1))
    end_line = payload.get('end_line')
    if end_line is not None:
        end_line = int(end_line)

    if not await asyncio.to_thread(path.exists):
        return {'ok': False, 'error': f'File not found: {path}'}

    try:
        if start_line == 0:
            # Special overview mode
            import subprocess
            def _grep():
                return subprocess.run(['grep', '-n', '.', str(path)], capture_output=True, text=True, timeout=5)
            res = await asyncio.to_thread(_grep)
            lines_out = res.stdout.splitlines()
            overview = []
            # Heuristic for important lines (imports, defs, classes)
            for l in lines_out:
                if any(x in l for x in ('import ', 'from ', 'def ', 'class ', 'async def ')):
                    overview.append(l)
                if len(overview) > 100: break
            return {'ok': True, 'path': str(path), 'overview': '\n'.join(overview), 'total_lines': len(lines_out)}

        def _read():
            with open(path, 'r', encoding='utf-8') as f:
                return f.readlines()
        
        all_lines = await asyncio.to_thread(_read)

        if end_line is None:
            selected = all_lines[start_line-1:]
        else:
            selected = all_lines[start_line-1:end_line]
        
        return {
            'ok': True,
            'path': str(path),
            'content': ''.join(selected),
            'start_line': start_line,
            'end_line': start_line + len(selected) - 1,
            'total_lines': len(all_lines)
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}


async def handle_write_file(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload.get('path', '')).expanduser().resolve()
    content = payload.get('content', '')
    try:
        def _write():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        await asyncio.to_thread(_write)
        return {'ok': True, 'path': str(path), 'size': len(content)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

async def handle_list_dir(payload: dict[str, Any]) -> dict[str, Any]:
    dir_path = Path(payload.get('dir_path', '.')).expanduser().resolve()
    max_depth = int(payload.get('max_depth', 2))
    limit = int(payload.get('limit', 100))

    if not await asyncio.to_thread(dir_path.is_dir):
        return {'ok': False, 'error': f'Not a directory: {dir_path}'}

    try:
        def _list():
            entries = []
            for p in dir_path.rglob('*'):
                rel = p.relative_to(dir_path)
                depth = len(rel.parts)
                if depth > max_depth: continue
                entries.append({
                    'name': p.name,
                    'path': str(p),
                    'type': 'directory' if p.is_dir() else 'file',
                    'depth': depth - 1
                })
                if len(entries) >= limit: break
            return entries
        
        entries = await asyncio.to_thread(_list)
        return {'ok': True, 'dir_path': str(dir_path), 'entries': entries, 'count': len(entries)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

async def handle_await(payload: dict[str, Any]) -> dict[str, Any]:
    """Block until all specified tasks complete. Event-driven via EventBus."""
    task_ids = payload.get("task_ids", [])
    include_reports = payload.get("include_reports", False)
    full = payload.get("full", False)
    timeout = float(payload.get("timeout", 120))

    if not task_ids:
        raise ValueError("payload.task_ids is required (non-empty list)")

    pending = set(task_ids)
    results: dict[str, dict[str, Any]] = {}

    async def _collect_completed(tid: str, task: dict[str, Any]) -> None:
        if tid not in pending: return
        status = task.get("status", "")
        normalized = "completed" if status.upper() in ("SUCCESS", "OK", "COMPLETED") else status
        
        lean_level = get_lean_level()
        results[tid] = {
            "status": normalized,
            "report_path": task.get("report_path"),
            "usage": task.get("usage", {}),
        }
        if lean_level >= 2:
            pending.discard(tid)
            return

        if include_reports and task.get("report_path"):
            if not full and task.get("summary"):
                results[tid]["report"] = _track_output(task["summary"])
            else:
                content = _read_report_content(task["report_path"])
                if content:
                    results[tid]["report"] = _track_output(content)
        pending.discard(tid)

    # 1. Subscribe FIRST to avoid race condition
    sub_id, queue = await event_bus.subscribe()
    try:
        # 2. Check already-completed tasks in registry IMMEDIATELY after subscription
        for tid in list(pending):
            task = task_registry.get(tid)
            if task and task.get("status", "").upper() in ("COMPLETED", "FAILED", "CANCELLED", "SUCCESS", "OK"):
                await _collect_completed(tid, task)

        if not pending:
            all_ok = all(r.get("status") in ("completed", "SUCCESS") for r in results.values())
            return {"ok": all_ok, "tasks": results}

        # 3. Wait for remaining tasks via queue
        deadline = asyncio.get_event_loop().time() + timeout
        while pending:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0: break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=remaining)
                if event.type == "complete" and event.task_id in pending:
                    task = task_registry.get(event.task_id)
                    await _collect_completed(event.task_id, task or event.payload)
            except asyncio.TimeoutError: break
    finally:
        await event_bus.unsubscribe(sub_id)

    # 4. Final timeout cleanup
    for tid in list(pending):
        results[tid] = {"status": "timeout", "report_path": None, "usage": {}}
    
    all_ok = all(r.get("status") in ("completed", "SUCCESS") for r in results.values())
    return {"ok": all_ok if not pending else False, "tasks": results}


async def handle_reset(_: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cleared": task_registry.clear_all()}


async def handle_clear(_: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cleared": task_registry.clear_finished()}




async def handle_recent_events(payload: dict[str, Any]) -> dict[str, Any]:
    """Return tasks that changed since a given timestamp. Used by hooks for event injection."""
    since = payload.get("since", time.time() - 30)  # default: last 30 seconds
    limit = payload.get("limit", 3)  # cap events for context diet

    lean_level = get_lean_level()
    if lean_level >= 2:
        return {"ok": True, "events": [], "since": since}
    if lean_level >= 1:
        limit = 1

    tasks = task_registry.get_all()
    recent = []
    for tid, t in tasks.items():
        if t.get("updated_at", 0) >= since:
            status = t.get("status", "?")
            cap = t.get("capability", "?")
            if status in ("completed", "failed", "SUCCESS"):
                recent.append(_track_output(f"[{status.upper()}] {tid} ({cap})"))
            elif status == "running":
                pct = t.get("progress_percent", 0)
                msg = t.get("progress_message", "")
                recent.append(_track_output(f"[RUNNING] {tid} ({cap}) {pct:.0f}% {msg}"))
    return {"ok": True, "events": recent[-limit:], "since": since}

async def handle_get_state(payload: dict[str, Any]) -> dict[str, Any]:
    import time
    from dictator.core import DAEMON_START_TIME
    tasks = task_registry.get_all()
    active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
    caps = await _load_capabilities()
    workers = await worker_registry.get_info()
    usage = await _get_session_usage(_SESSION_USAGE["dictator_model"])
    session_worker_tokens = usage["worker_tokens"]
    session_dictator_tokens = usage["dictator_tokens"]
    session_cost_usd = usage["cost_usd"]
    # Read dictator identity from config
    dictator_name = "unknown"
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
        dictator_name = cfg.get("dictator", "unknown")
    except Exception:
        pass

    return {
        "ok": True,
        "tasks": tasks,
        "session_waste_tokens": task_registry.get_waste(),
        "session_events": task_registry.get_replay_event_count(),
        "active_tasks": active,
        "total_tasks": len(tasks),
        "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
        "capabilities": list(caps.keys()),
        "capability_status": caps,
        "workers": workers,
        "session_worker_tokens": session_worker_tokens,
        "session_dictator_tokens": session_dictator_tokens,
        "session_cost_usd": session_cost_usd,
        "dictator": dictator_name,
        "dictator_model": _SESSION_USAGE["dictator_model"],
    }


async def handle_event(payload: dict[str, Any]) -> dict[str, Any]:
    from dictator.events import emit_dispatch_start, emit_complete, emit_error, emit_progress, RomeEvent
    import time
    t = payload.get("type", "")
    tid = str(payload.get("task_id") or "")
    p = payload.get("payload", {})
    if t == "dispatch_start":
        task_registry.register(tid, p.get("capability", "?"))
        await emit_dispatch_start(event_bus, tid, p.get("capability", "?"))
    elif t == "complete":
        usage = p.get("usage")
        if usage:
            task_registry.update_usage(tid, usage)
            total_tokens = usage.get("total_tokens")
            if total_tokens is not None:
                task_registry.add_waste(total_tokens)
        task_registry.complete(tid, p.get("status", "SUCCESS"), p.get("report_path"))
        await emit_complete(event_bus, tid, p.get("status"), p.get("report_path"), usage)
    elif t == "progress":
        task_registry.update_progress(tid, p.get("percent", 0), p.get("message", ""))
        await emit_progress(event_bus, tid, p.get("percent", 0), p.get("message", ""))
    elif t == "error":
        await emit_error(event_bus, tid, p.get("message", ""))
    elif t == "dictator_waste":
        usage = p.get("usage", {})
        tokens = usage.get("total_tokens", 0)
        task_registry.add_waste(tokens)
        await event_bus.publish(
            RomeEvent(
                type="dictator_waste",
                task_id=tid,
                ts=time.time(),
                sequence=0,
                source="dictator",
                payload={"usage": usage}
            )
        )
    return {"ok": True}


async def handle_report_usage(payload: dict[str, Any]) -> dict[str, Any]:
    """Dictator self-reporting its own usage via WS."""
    from dictator.rome_log import log_event
    from dictator.events import RomeEvent
    
    tokens = int(payload.get("tokens", 0))
    cost = float(payload.get("cost", 0.0))
    msg = str(payload.get("message", ""))
    tool = str(payload.get("tool", "dictator"))
    
    model_id = str(payload.get("model", ""))
    usage = {"total_tokens": tokens, "cost_usd": cost}
    if model_id and tool == "dictator":
        usage["model"] = model_id

    # Update in-memory session stats
    if tool == "dictator":
        _SESSION_USAGE["dictator_tokens"] += tokens
    else:
        _SESSION_USAGE["worker_tokens"] += tokens
    _SESSION_USAGE["cost_usd"] += cost
    if model_id and tool == "dictator":
        _SESSION_USAGE["dictator_model"] = model_id

    # 1. Permanent Log
    log_event(tool=tool, status="usage", message=msg, usage=usage)
    
    # 2. Real-time Mesh Broadcast
    await event_bus.publish(
        RomeEvent(
            type="dictator_waste",
            task_id="",
            ts=time.time(),
            sequence=0,
            source="dictator",
            payload={"usage": usage, "message": msg, "tool": tool}
        )
    )
    return {"ok": True, "tokens_logged": tokens}


async def handle_dashboard_stats(_: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    tasks = task_registry.get_all()
    caps = await _load_capabilities()
    workers = await worker_registry.get_info()

    total_cost_usd = 0.0
    tasks_completed_count = 0
    tasks_failed_count = 0
    tasks_running_count = 0
    tasks_pending_count = 0
    throughput_per_min = 0

    for task in tasks.values():
        usage = task.get("usage", {})
        total_cost_usd += float(usage.get("total_cost_usd", 0.0))

        status = task.get("status")
        if status == "completed":
            tasks_completed_count += 1
            completed_at = task.get("completed_at", 0)
            if now - completed_at <= 60:  # Within the last 60 seconds
                throughput_per_min += 1
        elif status == "failed":
            tasks_failed_count += 1
        elif status == "running":
            tasks_running_count += 1
        elif status == "registered":
            tasks_pending_count += 1

    uptime_seconds = round(time.monotonic() - DAEMON_START_TIME, 3)
    active_ws_connections = len(manager._connections)

    return {
        "total_cost_usd": total_cost_usd,
        "tasks_completed_count": tasks_completed_count,
        "tasks_failed_count": tasks_failed_count,
        "tasks_running_count": tasks_running_count,
        "tasks_pending_count": tasks_pending_count,
        "uptime_seconds": uptime_seconds,
        "active_ws_connections": active_ws_connections,
        "throughput_per_min": throughput_per_min,
        "capabilities": list(caps.keys()),
        "capability_status": caps,
        "workers": workers,
    }

async def _handle_command(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("type") != "command":
        raise ValueError("message.type must be 'command'")

    command = str(message.get("command") or "").strip().lower()
    payload = message.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("message.payload must be an object")

    handlers = {
        "dispatch": handle_dispatch,
        "status": handle_status,
        "get_state": handle_get_state,
        "cancel": handle_cancel,
        "ping": _handle_ping,
        "read_report": handle_read_report,
        "await": handle_await,
        "reset": handle_reset,
        "clear": handle_clear,
        "recent_events": handle_recent_events,
        "event": handle_event,
        "submit_result": handle_submit_result,
        "dashboard_stats": handle_dashboard_stats,
        "workers": _handle_workers,
        "read_file": handle_read_file,
        "write_file": handle_write_file,
        "list_dir": handle_list_dir,
        "native_shell": handle_native_shell,
        "interrupt": handle_interrupt,
        "report_usage": handle_report_usage,
    }
    handler = handlers.get(command)
    if handler is None:
        raise ValueError(f"unsupported command: {command}")
    return await handler(payload)


async def _handle_workers(_: dict[str, Any]) -> dict[str, Any]:
    workers = await worker_registry.get_info()
    return {"ok": True, "workers": workers, "count": len(workers)}


async def _handle_worker_event(ws: WebSocket, event_data: dict[str, Any]) -> None:
    """Process an event sent by a persistent worker (progress, complete, error)."""
    import logging
    logger = logging.getLogger("rome.daemon")
    ev_type = event_data.get("type", "")
    task_id = event_data.get("task_id", "")
    payload = event_data.get("payload", {})

    if ev_type == "dispatch_start":
        # Worker accepted — task already registered by handle_dispatch
        pass
    elif ev_type == "progress":
        task_registry.update_progress(task_id, payload.get("percent", 0), payload.get("message", ""))
        from dictator.events import emit_progress
        await emit_progress(event_bus, task_id, payload.get("percent", 0), payload.get("message", ""))
    elif ev_type == "complete":
        status_raw = str(payload.get("status", "completed")).upper()
        status = "completed" if status_raw in ("SUCCESS", "OK", "COMPLETED") else "failed"

        # If the worker sent inline report content, save it to a report file
        report_path = payload.get("report_path")
        report_content = payload.get("report")
        if report_content and not report_path:
            task_dir = ROME_ROOT / "legions" / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            rp = task_dir / f"report_{task_id}.txt"
            rp.write_text(str(report_content), encoding="utf-8")
            report_path = str(rp)

        usage = payload.get("usage")
        if usage:
            task_registry.update_usage(task_id, usage)
            await emit_cost_update(event_bus, task_id, usage)
            total_tokens = usage.get("total_tokens")
            if total_tokens is not None:
                task_registry.add_waste(total_tokens)

        task_registry.complete(task_id, status, report_path)
        await emit_complete(event_bus, task_id, status, report_path, usage)
        await worker_registry.mark_idle(ws, task_id)
        logger.info("Worker completed task %s → %s", task_id, status)
    elif ev_type == "error":
        await emit_error(event_bus, task_id, payload.get("message", "worker error"))
    else:
        logger.debug("Unknown worker event type: %s", ev_type)


async def rome_ws_endpoint(websocket: WSAdapter) -> None:
    subscriber_id: str | None = None
    relay_task: asyncio.Task[Any] | None = None
    heartbeat_task: asyncio.Task[Any] | None = None
    is_worker = False
    try:
        # Auth via Authorization: Bearer <token> header or ?token= query param
        # Skip auth for same-origin dashboard connections (Origin matches host)
        if _WEBSOCKET_TOKEN:
            origin = websocket.headers.get("origin", "")
            host = websocket.headers.get("host", "")
            is_dashboard = origin and host and (origin.endswith("://" + host))
            if not is_dashboard:
                auth_header = websocket.headers.get("authorization", "")
                header_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
                query_token = websocket.query_params.get("token", "")
                provided_token = header_token or query_token
                if provided_token != _WEBSOCKET_TOKEN:
                    await websocket.close(code=1008)
                    return

        subscriber_id, queue = await manager.connect(websocket)
        relay_task = asyncio.create_task(manager.relay_events(websocket, queue), name="rome-ws-relay")
        heartbeat_task = asyncio.create_task(_emit_heartbeat(websocket), name="rome-ws-heartbeat")

        capabilities = await _load_capabilities()
        await websocket.send_json({
            "type": "daemon_hello",
            "capabilities": capabilities,
            "active_tasks": len(task_registry.get_all()),
            "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
        })
        system_status_task = asyncio.create_task(_emit_system_status_loop(), name="rome-ws-system-status")

        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type", "")

            # --- Persistent worker registration ---
            if msg_type == "agent_hello":
                import logging
                logger = logging.getLogger("rome.daemon")
                worker_caps = message.get("capabilities", [])
                worker_version = message.get("version", "")
                worker_platform = message.get("platform", "")
                await worker_registry.register(websocket, worker_caps, worker_version, worker_platform)
                is_worker = True
                logger.info(
                    "Persistent worker registered: caps=%s version=%s platform=%s",
                    worker_caps, worker_version, worker_platform,
                )
                await websocket.send_json({
                    "type": "worker_ack",
                    "ok": True,
                    "message": "Registered as persistent worker",
                    "capabilities_accepted": worker_caps,
                })
                continue

            # --- Worker sending events back (progress/complete/error) ---
            if msg_type == "event" and is_worker:
                event_data = message.get("event", {})
                await _handle_worker_event(websocket, event_data)
                continue

            # --- Worker sending response to dispatch ack ---
            if msg_type == "response" and is_worker:
                # Worker acknowledging a dispatch — nothing to do, task is already
                # registered in handle_dispatch. Log if not ok.
                if not message.get("ok"):
                    import logging
                    logging.getLogger("rome.daemon").warning(
                        "Worker rejected dispatch: %s", message.get("error")
                    )
                continue

            # --- Standard client command ---
            request_id = message.get("request_id")
            try:
                payload = await _handle_command(message)
                await websocket.send_json(_response(request_id, True, payload))
            except ValueError as exc:
                await websocket.send_json(_response(request_id, False, error=str(exc)))
    except WebSocketDisconnect:
        pass
    finally:
        if is_worker:
            orphaned = await worker_registry.unregister(websocket)
            if orphaned:
                import logging
                logger = logging.getLogger("rome.daemon")
                logger.warning("Worker disconnected with active tasks: %s", orphaned)
                # Mark orphaned tasks as failed
                for tid in orphaned:
                    task_registry.complete(tid, "failed", None)
                    await emit_error(event_bus, tid, "Persistent worker disconnected")
                    await emit_complete(event_bus, tid, "failed", None, None)
        for task in (relay_task, heartbeat_task, system_status_task):
            if task:
                task.cancel()
        if relay_task or heartbeat_task or system_status_task:
            await asyncio.gather(
                *(task for task in (relay_task, heartbeat_task, system_status_task) if task),
                return_exceptions=True,
            )
        await manager.disconnect(websocket, subscriber_id)


async def rome_ws_handler(ws) -> None:
    """Raw websockets entry point — wraps connection in WSAdapter and delegates."""
    adapter = WSAdapter(ws)
    await rome_ws_endpoint(adapter)


__all__ = ["ConnectionManager", "WorkerRegistry", "manager", "worker_registry", "rome_ws_endpoint", "rome_ws_handler"]