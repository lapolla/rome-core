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
        for capability_name, details in arsenal_config.get("capabilities", {}).items():
            binary = details.get("binary")
            if binary:
                # Check if the binary exists in PATH
                proc = await asyncio.create_subprocess_exec(
                    "which",
                    binary,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                capabilities_status[capability_name] = proc.returncode == 0
            else:
                capabilities_status[capability_name] = False # No binary specified
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
        if os.environ.get("ROME_DAEMON"):
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
        return {"ok": True, "active_tasks": active, "total_tasks": len(tasks),
                "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3)}
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


async def handle_read_report(payload: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path
    report_path = str(payload.get("report_path") or "").strip()
    if not report_path:
        raise ValueError("payload.report_path is required")
    rp = Path(report_path)
    if not rp.exists():
        return {"report_path": report_path, "content": "File not found or no report generated."}
    try:
        content = rp.read_text(encoding="utf-8")
        return {"report_path": report_path, "content": content}
    except Exception as exc:
        return {"report_path": report_path, "content": f"Error reading report: {exc}"}


async def handle_await(payload: dict[str, Any]) -> dict[str, Any]:
    """Block until all requested tasks complete. Event-driven via EventBus."""
    task_ids = payload.get("task_ids", [])
    include_reports = payload.get("include_reports", False)

    if not task_ids:
        raise ValueError("payload.task_ids is required (non-empty list)")

    pending = set(task_ids)
    results: dict[str, dict[str, Any]] = {}

    # Phase 1: Check already-completed tasks in registry
    for tid in list(pending):
        task = task_registry.get(tid)
        if task and task.get("status") in ("completed", "failed", "cancelled"):
            results[tid] = {
                "status": task["status"],
                "report_path": task.get("report_path"),
                "usage": task.get("usage", {}),
            }
            if include_reports and task.get("report_path"):
                try:
                    from pathlib import Path
                    rp = Path(task["report_path"])
                    if rp.exists():
                        content = rp.read_text(encoding="utf-8")
                        # Truncate for context safety
                        if len(content) > 4000:
                            results[tid]["report"] = content[:4000] + "\n...[TRUNCATED]"
                        else:
                            results[tid]["report"] = content
                except Exception:
                    pass
            pending.discard(tid)

    if not pending:
        all_ok = all(r.get("status") in ("completed", "SUCCESS") for r in results.values())
        return {"ok": all_ok, "tasks": results}

    # Phase 2: Subscribe to EventBus and wait for remaining completions
    subscriber_id, queue = await event_bus.subscribe()
    try:
        # Use a generous internal timeout (caller controls outer timeout via WS)
        deadline = asyncio.get_event_loop().time() + 300  # 5 min max internal
        while pending:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                # Timeout — return what we have, mark rest as timeout
                for tid in pending:
                    results[tid] = {"status": "timeout", "report_path": None, "usage": {}}
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=min(remaining, 1.0))
            except asyncio.TimeoutError:
                # Check registry in case we missed the event (task completed before subscribe)
                for tid in list(pending):
                    task = task_registry.get(tid)
                    if task and task.get("status") in ("completed", "failed", "cancelled"):
                        results[tid] = {
                            "status": task["status"],
                            "report_path": task.get("report_path"),
                            "usage": task.get("usage", {}),
                        }
                        if include_reports and task.get("report_path"):
                            try:
                                from pathlib import Path
                                rp = Path(task["report_path"])
                                if rp.exists():
                                    content = rp.read_text(encoding="utf-8")
                                    if len(content) > 4000:
                                        results[tid]["report"] = content[:4000] + "\n...[TRUNCATED]"
                                    else:
                                        results[tid]["report"] = content
                            except Exception:
                                pass
                        pending.discard(tid)
                continue

            # Only care about complete events for our tasks
            if event.type == "complete" and event.task_id in pending:
                tid = event.task_id
                p = event.payload
                results[tid] = {
                    "status": p.get("status", "unknown"),
                    "report_path": p.get("report_path"),
                    "usage": p.get("usage", {}),
                }
                if include_reports and p.get("report_path"):
                    try:
                        from pathlib import Path
                        rp = Path(p["report_path"])
                        if rp.exists():
                            content = rp.read_text(encoding="utf-8")
                            if len(content) > 4000:
                                results[tid]["report"] = content[:4000] + "\n...[TRUNCATED]"
                            else:
                                results[tid]["report"] = content
                    except Exception:
                        pass
                pending.discard(tid)
    finally:
        await event_bus.unsubscribe(subscriber_id)

    all_ok = all(r.get("status") in ("completed", "SUCCESS") for r in results.values())
    return {"ok": all_ok, "tasks": results}


async def handle_reset(_: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cleared": task_registry.clear_all()}


async def handle_clear(_: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "cleared": task_registry.clear_finished()}


async def handle_get_state(payload: dict[str, Any]) -> dict[str, Any]:
    import time
    from dictator.core import DAEMON_START_TIME
    tasks = task_registry.get_all()
    active = sum(1 for t in tasks.values() if t.get("status") in {"registered", "running"})
    return {
        "ok": True,
        "tasks": tasks,
        "session_waste_tokens": task_registry.get_waste(),
        "session_events": task_registry.get_replay_event_count(),
        "active_tasks": active,
        "total_tasks": len(tasks),
        "uptime_s": round(time.monotonic() - DAEMON_START_TIME, 3),
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
        "event": handle_event,
        "submit_result": handle_submit_result,
    }
    handler = handlers.get(command)
    if handler is None:
        raise ValueError(f"unsupported command: {command}")
    return await handler(payload)


async def rome_ws_endpoint(websocket: WebSocket) -> None:
    subscriber_id: str | None = None
    relay_task: asyncio.Task[Any] | None = None
    heartbeat_task: asyncio.Task[Any] | None = None
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
            request_id = message.get("request_id")
            try:
                payload = await _handle_command(message)
                await websocket.send_json(_response(request_id, True, payload))
            except ValueError as exc:
                await websocket.send_json(_response(request_id, False, error=str(exc)))
    except WebSocketDisconnect:
        pass
    finally:
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

__all__ = ["ConnectionManager", "manager", "rome_ws_endpoint", "routes"]
