"""ROME WebSocket endpoint and connection manager."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from dictator.core import event_bus, task_registry, DAEMON_START_TIME, ROME_ROOT, ARSENAL_PATH
from dictator.events import RomeEvent, emit_complete, emit_cost_update, emit_dispatch_start, emit_error, emit_capability_status, emit_system_status
from dictator.tools_legion import _execute_legion_impl

CONFIG_PATH = Path(ROME_ROOT) / "dictator" / "config.json"
GEMINI_CLI = "/home/paul-kane/.nvm/versions/node/v20.20.0/bin/gemini"


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


async def _load_capabilities() -> dict[str, bool]:
    # ARSENAL_PATH is already imported
    import json
    import asyncio
    import os
    import logging

    capabilities_status = {}
    try:
        if not ARSENAL_PATH.exists():
            logging.getLogger("uvicorn.error").warning("Arsenal file not found at %s", ARSENAL_PATH)
            return {}

        with open(ARSENAL_PATH, "r", encoding="utf-8") as f:
            arsenal_config = json.load(f)
        import shutil
        for capability_name, details in arsenal_config.get("capabilities", {}).items():
            exec_path = details.get("exec", "")
            if exec_path:
                capabilities_status[capability_name] = Path(exec_path).exists() or shutil.which(exec_path) is not None
            else:
                capabilities_status[capability_name] = False
    except FileNotFoundError:
        logging.getLogger("uvicorn.error").warning("Arsenal file not found at %s", ARSENAL_PATH)
    except json.JSONDecodeError:
        logging.getLogger("uvicorn.error").error("Error decoding JSON from %s", ARSENAL_PATH)
    except Exception as e:
        logging.getLogger("uvicorn.error").error("ERROR loading capabilities: %s", e, exc_info=True)
    return capabilities_status

_WEBSOCKET_TOKEN = _load_config_token()

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
                    "capabilities": e.capabilities,
                    "busy_tasks": list(e.busy_tasks),
                    "connected_at": e.connected_at,
                    "version": e.version,
                    "platform": e.platform,
                }
                for e in self._workers.values()
            ]


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


async def _emit_heartbeat(websocket: WebSocket) -> None:
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
    logger = logging.getLogger("uvicorn.error")
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
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> tuple[str, asyncio.Queue[RomeEvent]]:
        await websocket.accept()
        subscriber_id, queue = await event_bus.subscribe()
        async with self._lock:
            self._connections.add(websocket)
        return subscriber_id, queue

    async def disconnect(self, websocket: WebSocket, subscriber_id: str | None) -> None:
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

    async def relay_events(self, websocket: WebSocket, queue: asyncio.Queue[RomeEvent]) -> None:
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
    import os
    if os.environ.get("ROME_DAEMON"):
        task_registry.register(task_id, capability)
        await emit_dispatch_start(event_bus, task_id, capability)
        # Immediately mark as running so dashboard doesn't sit at REGISTERED
        task_registry.update_progress(task_id, 0, "Starting...")
    try:
        result = await _execute_legion_impl(
            task_id=task_id,
            capability=capability,
            args=[prompt],
            input_files=input_files,
            no_cache=no_cache,
            prompt_file=prompt_file,
        )
        usage = result.get("usage")
        if usage is not None:
            if os.environ.get("ROME_DAEMON"):
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
        if os.environ.get("ROME_DAEMON") and not is_fire_and_forget:
            task_registry.complete(task_id, status, report_path)
            await emit_complete(event_bus, task_id, status, report_path, usage)
        if not result.get("ok"):
            await emit_error(event_bus, task_id, str(result.get("error") or result.get("message") or "dispatch_failed"))
    except asyncio.CancelledError:
        if os.environ.get("ROME_DAEMON"):
            task_registry.complete(task_id, "cancelled", None)
            await emit_complete(event_bus, task_id, "cancelled", None, None)
        raise
    except Exception as exc:
        import traceback, logging
        logging.getLogger("uvicorn.error").error("_dispatch_runner EXCEPTION task=%s: %s", task_id, traceback.format_exc())
        if os.environ.get("ROME_DAEMON"):
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
    logger = logging.getLogger("uvicorn.error")
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
    output_path = str(payload.get("output_path") or "") or None

    if not task_id:
        raise ValueError("payload.task_id is required")
    if not capability:
        raise ValueError("payload.capability is required")
    if not prompt and not prompt_file:
        raise ValueError("payload.prompt or payload.prompt_file is required")
    if input_files is not None and not isinstance(input_files, list):
        raise ValueError("payload.input_files must be a list when provided")

    # --- Resolve prompt_file to prompt content for worker routing ---
    if prompt_file and not prompt:
        pf = Path(prompt_file)
        if pf.exists():
            prompt = pf.read_text(encoding="utf-8").strip()

    # --- Persistent worker routing ---
    # Check if a persistent worker can handle this capability (skip for SAFE_SHELL
    # which is always local, and skip if input_files are set since workers don't
    # have access to those via the forwarding protocol yet).
    worker_ws = None
    if capability != "SAFE_SHELL" and not input_files and prompt:
        worker_ws = await worker_registry.find_worker(capability)

    if worker_ws is not None:
        # Register task in daemon's registry so await/status/dashboard work
        import os
        if os.environ.get("ROME_DAEMON"):
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
    task = asyncio.create_task(
        _dispatch_runner(task_id, capability, prompt, input_files, no_cache, prompt_file, output_path),
        name=f"rome-ws-dispatch-{task_id}",
    )
    async with _ACTIVE_TASKS_LOCK:
        existing = _ACTIVE_TASKS.get(task_id)
        if existing and not existing.done():
            task.cancel()
            raise ValueError(f"task {task_id} is already running")
        _ACTIVE_TASKS[task_id] = task

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

    status = "completed"
    task_registry.complete(task_id, status, str(report_path))
    await emit_complete(event_bus, task_id, status, str(report_path), None)

    return {"task_id": task_id, "status": status, "report_path": str(report_path)}


async def handle_status(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("summary"):
        tasks = task_registry.get_all()
        active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
        caps = await _load_capabilities()
        workers = await worker_registry.get_info()
        return {"ok": True, "active_tasks": active, "total_tasks": len(tasks),
                "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
                "capabilities": list(caps.keys()),
                "capability_status": caps,
                "workers": workers}
    task_id = str(payload.get("task_id") or "").strip()
    if task_id:
        task = task_registry.get(task_id)
        return {"task": task, "found": task is not None}
    return {"tasks": task_registry.get_all()}


async def handle_cancel(payload: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("payload.task_id is required")

    async with _ACTIVE_TASKS_LOCK:
        task = _ACTIVE_TASKS.get(task_id)

    if task is None:
        return {"task_id": task_id, "cancelled": False, "reason": "not_running"}

    task.cancel()
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


async def handle_await(payload: dict[str, Any]) -> dict[str, Any]:
    """Block until all specified tasks complete. Event-driven via EventBus."""
    task_ids = payload.get("task_ids", [])
    include_reports = payload.get("include_reports", False)
    summarize = payload.get("summarize", False)
    timeout = float(payload.get("timeout", 120))

    if not task_ids:
        raise ValueError("payload.task_ids is required (non-empty list)")

    pending = set(task_ids)
    results: dict[str, dict[str, Any]] = {}

    def _collect_completed(tid: str, task: dict[str, Any]) -> None:
        status = task.get("status", "")
        # Normalize SUCCESS/OK from shell_executor to "completed"
        normalized = "completed" if status.upper() in ("SUCCESS", "OK", "COMPLETED") else status
        results[tid] = {
            "status": normalized,
            "report_path": task.get("report_path"),
            "usage": task.get("usage", {}),
        }
        if include_reports and task.get("report_path"):
            content = _read_report_content(task["report_path"])
            if content:
                results[tid]["report"] = content
        pending.discard(tid)

    # Phase 1: Check already-completed tasks in registry
    for tid in list(pending):
        task = task_registry.get(tid)
        if task and task.get("status", "").upper() in ("COMPLETED", "FAILED", "CANCELLED", "SUCCESS", "OK"):
            _collect_completed(tid, task)

    if not pending:
        # Summarize before returning
        if summarize:
            for tid, r in results.items():
                report = r.get("report")
                if report and len(report) > 500:
                    r["report"] = await _summarize_report(report)
        all_ok = all(r.get("status") in ("completed", "SUCCESS") for r in results.values())
        return {"ok": all_ok, "tasks": results}

    # Phase 2: Subscribe to EventBus and wait for remaining tasks
    sub_id, queue = await event_bus.subscribe()
    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while pending:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            if event.type == "complete" and event.task_id in pending:
                task = task_registry.get(event.task_id)
                if task:
                    _collect_completed(event.task_id, task)
                else:
                    # Fallback: use event payload directly
                    _collect_completed(event.task_id, event.payload)
    finally:
        await event_bus.unsubscribe(sub_id)

    # Any still-pending tasks are timeouts
    for tid in list(pending):
        results[tid] = {"status": "timeout", "report_path": None, "usage": {}}

    # Summarize reports via Gemini if requested
    if summarize:
        for tid, r in results.items():
            report = r.get("report")
            if report and len(report) > 500:
                r["report"] = await _summarize_report(report)

    all_ok = all(r.get("status") in ("completed", "SUCCESS") for r in results.values())
    return {"ok": all_ok if not pending else False, "tasks": results}


async def handle_reset(_: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cleared": task_registry.clear_all()}


async def handle_clear(_: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cleared": task_registry.clear_finished()}




async def handle_recent_events(payload: dict[str, Any]) -> dict[str, Any]:
    """Return tasks that changed since a given timestamp. Used by hooks for event injection."""
    since = payload.get("since", time.time() - 30)  # default: last 30 seconds
    tasks = task_registry.get_all()
    recent = []
    for tid, t in tasks.items():
        if t.get("updated_at", 0) >= since:
            status = t.get("status", "?")
            cap = t.get("capability", "?")
            if status in ("completed", "failed", "SUCCESS"):
                recent.append(f"[{status.upper()}] {tid} ({cap})")
            elif status == "running":
                pct = t.get("progress_percent", 0)
                msg = t.get("progress_message", "")
                recent.append(f"[RUNNING] {tid} ({cap}) {pct:.0f}% {msg}")
    return {"ok": True, "events": recent, "since": since}

async def handle_get_state(payload: dict[str, Any]) -> dict[str, Any]:
    import time
    from dictator.core import DAEMON_START_TIME
    tasks = task_registry.get_all()
    active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
    caps = await _load_capabilities()
    workers = await worker_registry.get_info()
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


async def handle_dashboard_stats(_: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    tasks = task_registry.get_all()

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
    logger = logging.getLogger("uvicorn.error")
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


async def rome_ws_endpoint(websocket: WebSocket) -> None:
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
            "type": "agent_hello",
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
                logger = logging.getLogger("uvicorn.error")
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
                    logging.getLogger("uvicorn.error").warning(
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
                logger = logging.getLogger("uvicorn.error")
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


routes = [WebSocketRoute("/ws", endpoint=rome_ws_endpoint)]

__all__ = ["ConnectionManager", "WorkerRegistry", "manager", "worker_registry", "rome_ws_endpoint", "routes"]
