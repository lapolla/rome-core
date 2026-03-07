"""ROME WebSocket endpoint and connection manager."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from dictator.core import event_bus, task_registry
from dictator.events import RomeEvent, emit_complete, emit_cost_update, emit_error
from dictator.tools_legion import _execute_legion_impl

_CFG_PATH = Path(__file__).with_name("config.json")
_HEARTBEAT_SECONDS = 15

try:
    _cfg = json.loads(_CFG_PATH.read_text()) if _CFG_PATH.exists() else {}
except Exception:
    _cfg = {}

_WS_TOKEN = str(_cfg.get("ws_token") or "")
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


def _extract_bearer_token(websocket: WebSocket) -> str | None:
    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    query_token = websocket.query_params.get("token")
    return query_token.strip() if query_token else None


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


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> tuple[str, asyncio.Queue[RomeEvent]]:
        token = _extract_bearer_token(websocket)
        if _WS_TOKEN and token != _WS_TOKEN:
            await websocket.close(code=4401, reason="Unauthorized")
            raise PermissionError("unauthorized")

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
) -> None:
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
            task_registry.update_usage(task_id, usage)
            await emit_cost_update(event_bus, task_id, usage)

        status = "completed" if result.get("ok") else "failed"
        report_path = result.get("report_path")
        task_registry.complete(task_id, status, report_path)
        await emit_complete(event_bus, task_id, status, report_path, usage)
        if not result.get("ok"):
            await emit_error(event_bus, task_id, str(result.get("error") or result.get("message") or "dispatch_failed"))
    except asyncio.CancelledError:
        task_registry.complete(task_id, "cancelled", None)
        await emit_complete(event_bus, task_id, "cancelled", None, None)
        raise
    except Exception as exc:
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

    if not task_id:
        raise ValueError("payload.task_id is required")
    if not capability:
        raise ValueError("payload.capability is required")
    if not prompt and not prompt_file:
        raise ValueError("payload.prompt or payload.prompt_file is required")
    if input_files is not None and not isinstance(input_files, list):
        raise ValueError("payload.input_files must be a list when provided")

    task = asyncio.create_task(
        _dispatch_runner(task_id, capability, prompt, input_files, no_cache, prompt_file),
        name=f"rome-ws-dispatch-{task_id}",
    )
    async with _ACTIVE_TASKS_LOCK:
        existing = _ACTIVE_TASKS.get(task_id)
        if existing and not existing.done():
            task.cancel()
            raise ValueError(f"task {task_id} is already running")
        _ACTIVE_TASKS[task_id] = task

    return {
        "task_id": task_id,
        "capability": capability,
        "accepted": True,
    }


async def handle_status(payload: dict[str, Any]) -> dict[str, Any]:
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
        "cancel": handle_cancel,
        "ping": _handle_ping,
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
        subscriber_id, queue = await manager.connect(websocket)
        relay_task = asyncio.create_task(manager.relay_events(websocket, queue), name="rome-ws-relay")
        heartbeat_task = asyncio.create_task(_emit_heartbeat(websocket), name="rome-ws-heartbeat")

        while True:
            message = await websocket.receive_json()
            request_id = message.get("request_id")
            try:
                payload = await _handle_command(message)
                await websocket.send_json(_response(request_id, True, payload))
            except ValueError as exc:
                await websocket.send_json(_response(request_id, False, error=str(exc)))
    except PermissionError:
        return
    except WebSocketDisconnect:
        pass
    finally:
        for task in (relay_task, heartbeat_task):
            if task:
                task.cancel()
        if relay_task or heartbeat_task:
            await asyncio.gather(
                *(task for task in (relay_task, heartbeat_task) if task),
                return_exceptions=True,
            )
        await manager.disconnect(websocket, subscriber_id)


routes = [WebSocketRoute("/ws", endpoint=rome_ws_endpoint)]


__all__ = ["ConnectionManager", "manager", "rome_ws_endpoint", "routes"]
