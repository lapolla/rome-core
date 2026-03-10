"""Thread-safe WebSocket client for MCP tools → daemon communication.

Two modes:
- send_event()        — fire-and-forget via persistent background connection
- send_command_sync() — short-lived connection for infrequent sync commands (reset, clear)
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from typing import Any

try:
    from dictator.rome_log import log_event
except ImportError:
    def log_event(**kwargs): pass

_WS_URL = "ws://127.0.0.1:8741/ws"


# ---------------------------------------------------------------------------
# Persistent background sender (fire-and-forget events)
# ---------------------------------------------------------------------------

class _EventSender:
    def __init__(self) -> None:
        self._queue: queue.Queue[dict] = queue.Queue(maxsize=500)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="rome-ws-events")
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._loop_forever())

    async def _loop_forever(self) -> None:
        import websockets
        delay = 1.0
        while True:
            try:
                async with websockets.connect(_WS_URL) as ws:
                    delay = 1.0
                    while True:
                        try:
                            msg = self._queue.get_nowait()
                        except queue.Empty:
                            await asyncio.sleep(0.02)
                            continue
                        try:
                            await ws.send(json.dumps(msg))
                        except Exception:
                            self._queue.put_nowait(msg)
                            raise
            except Exception:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 16.0)

    def send(self, msg: dict) -> None:
        try:
            self._queue.put_nowait(msg)
        except queue.Full:
            log_event(tool='ws_client', status='dropped', message=f'queue full, dropped {msg.get("payload",{}).get("type","?")}:{msg.get("payload",{}).get("task_id","?")}')


_sender: _EventSender | None = None
_sender_lock = threading.Lock()


def _get_sender() -> _EventSender:
    global _sender
    if _sender is None:
        with _sender_lock:
            if _sender is None:
                _sender = _EventSender()
    return _sender


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_event(event_type: str, task_id: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget: relay a task event to the daemon over WS."""
    _get_sender().send({
        "type": "command",
        "command": "event",
        "request_id": uuid.uuid4().hex[:8],
        "payload": {"type": event_type, "task_id": task_id, "payload": payload},
    })


def send_command_sync(command: str, payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """Short-lived WS connection for sync commands (reset, clear, status).
    Safe to call from any thread — uses asyncio.run() on a fresh loop."""
    import websockets

    async def _run() -> dict[str, Any]:
        async with websockets.connect(_WS_URL) as ws:
            req_id = uuid.uuid4().hex[:8]
            await ws.send(json.dumps({
                "type": "command",
                "command": command,
                "request_id": req_id,
                "payload": payload,
            }))
            # Skip heartbeats/events until we get our response
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return {"ok": False, "error": "timeout"}
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("type") == "response" and msg.get("request_id") == req_id:
                    return msg.get("payload", {})

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def send_command_async(command: str, payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """Async version of send_command_sync — awaitable, safe inside a running event loop."""
    import websockets
    try:
        async with websockets.connect(_WS_URL) as ws:
            req_id = uuid.uuid4().hex[:8]
            await ws.send(json.dumps({
                "type": "command",
                "command": command,
                "request_id": req_id,
                "payload": payload,
            }))
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    return {"ok": False, "error": "timeout"}
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("type") == "response" and msg.get("request_id") == req_id:
                    return msg.get("payload", {})
    except Exception as e:
        return {"ok": False, "error": str(e)}
