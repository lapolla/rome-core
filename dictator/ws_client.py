"""Thread-safe WebSocket client for MCP tools → daemon communication.

Two modes:
- send_event()        — fire-and-forget via persistent background connection
- send_command_sync() — short-lived connection for infrequent sync commands (reset, clear)
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import time
import threading
import sys
import uuid
from typing import Any

try:
    from dictator.rome_log import log_event
except ImportError:
    def log_event(**kwargs): pass

_WS_URL = "ws://127.0.0.1:8741/ws"

def _ws_headers() -> dict:
    try:
        import json as _json
        from pathlib import Path as _Path
        cfg = _json.loads((_Path(__file__).parent / "config.json").read_text())
        token = str(cfg.get("ws_token") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}
    except Exception:
        return {}


_HEARTBEAT_TIMEOUT = 120 # If no message for this long, consider connection dead

def _read_report_content(report_path: str) -> str | None:
    from pathlib import Path
    rp = Path(report_path)
    if not rp.exists():
        return None
    try:
        content = rp.read_text(encoding="utf-8")
        if len(content) > 4000:
            return content[:4000] + "\n...[TRUNCATED]"
        return content
    except Exception:
        return None

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
                async with websockets.connect(_WS_URL, open_timeout=30, additional_headers=_ws_headers()) as ws:
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
                sys.stderr.write(f"WS send error. Reconnecting in {delay:.1f}s...\n")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 16.0)

    def send(self, msg: dict) -> None:
        try:
            self._queue.put_nowait(msg)
        except queue.Full:
            log_event(tool='ws_client', status='dropped', message=f'queue full, dropped {msg.get("payload",{}).get("type","?")}:{msg.get("payload",{}).get("task_id","?")}')

    def flush(self, timeout: float = 5.0) -> None:
        """Blocks until the queue is empty or timeout expires."""
        deadline = time.time() + timeout
        while not self._queue.empty():
            if time.time() >= deadline:
                break
            time.sleep(0.05)
        time.sleep(0.05)


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


def flush(timeout: float = 5.0) -> None:
    """Blocks until the event queue is empty or timeout expires."""
    _get_sender().flush(timeout)


def send_command_sync(command: str, payload: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """Short-lived WS connection for sync commands (reset, clear, status).
    Safe to call from any thread — uses asyncio.run() on a fresh loop."""
    import websockets

    async def _run() -> dict[str, Any]:
        async with websockets.connect(_WS_URL, open_timeout=30, additional_headers=_ws_headers()) as ws:
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
        async with websockets.connect(_WS_URL, open_timeout=30, additional_headers=_ws_headers()) as ws:
            req_id = uuid.uuid4().hex[:8]
            await ws.send(json.dumps({
                "type": "command",
                "command": command,
                "request_id": req_id,
                "payload": payload,
            }))

            import sys; print(f"[AWAIT_DEBUG] send_command_async command={command}", file=sys.stderr, flush=True)
            if command == "await":
                # Initial response from server for await command
                initial_response: dict[str, Any] = {}
                deadline = asyncio.get_event_loop().time() + timeout

                while True:
                    remaining_time = deadline - asyncio.get_event_loop().time()
                    if remaining_time <= 0:
                        return {"ok": False, "error": "timeout_await_initial_response"}

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=remaining_time)
                        msg = json.loads(raw)
                        if msg.get("type") == "response" and msg.get("request_id") == req_id:
                            initial_response = msg.get("payload", {})
                            break
                        # Skip non-response messages (agent_hello, events, heartbeats)
                        continue
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        return {"ok": False, "error": f"Error during await: {e}"}

                log_event(tool='ws_client', message=f"await initial_response ok={initial_response.get('ok')}, pending={initial_response.get('pending')}", task_id='await_debug')
                if initial_response.get("ok") == "pending":
                    # Server indicated pending tasks, client needs to listen for events
                    all_results = initial_response.get("completed", {})
                    pending_task_ids = set(initial_response.get("pending", []))
                    include_reports = payload.get("include_reports", False)

                    while pending_task_ids:
                        remaining_time = deadline - asyncio.get_event_loop().time()
                        if remaining_time <= 0:
                            for tid in pending_task_ids:
                                all_results[tid] = {"status": "timeout", "report_path": None, "usage": {}}
                            return {"ok": False, "error": "timeout", "tasks": all_results}

                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=remaining_time)
                            msg = json.loads(raw)

                            if msg.get("type") == "event":
                                event_data = msg.get("event", {})
                                if event_data.get("type") == "complete":
                                    tid = event_data.get("task_id")
                                    if tid in pending_task_ids:
                                        event_payload = event_data.get("payload", {})
                                        result = {
                                            "status": event_payload.get("status", "unknown"),
                                            "report_path": event_payload.get("report_path"),
                                            "usage": event_payload.get("usage", {}),
                                        }
                                        if include_reports and event_payload.get("report_path"):
                                            content = _read_report_content(event_payload["report_path"])
                                            if content:
                                                result["report"] = content
                                        all_results[tid] = result
                                        pending_task_ids.discard(tid)

                        except asyncio.TimeoutError:
                            continue # Just keep waiting, deadline check handles overall timeout
                        except Exception as e:
                            # Log error but don't stop waiting for other tasks
                            log_event(tool='ws_client', message=f"Error receiving await event: {e}", task_id='await_command')

                    # All tasks are completed or timed out by now
                    final_ok = all(r.get("status") in ("completed", "SUCCESS") for r in all_results.values())
                    return {"ok": final_ok, "tasks": all_results}
                else:
                    # Server returned final results directly (no pending)
                    return initial_response
            else:
                # Original logic for non-await commands
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


def submit_agent_result_sync(task_id: str, content: str, token: str | None = None, timeout: float = 10.0) -> dict[str, Any]:
    """Sync version of submit_agent_result — sends submit_result command."""
    if not token:
        token = os.environ.get("ROME_TASK_TOKEN", "")
    return send_command_sync("submit_result", {"task_id": task_id, "token": token, "content": content}, timeout)


async def submit_agent_result_async(task_id: str, content: str, token: str | None = None, timeout: float = 10.0) -> dict[str, Any]:
    """Async version of submit_agent_result — sends submit_result command."""
    if not token:
        token = os.environ.get("ROME_TASK_TOKEN", "")
    return await send_command_async("submit_result", {"task_id": task_id, "token": token, "content": content}, timeout)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 ws_client.py <command> <payload_json>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    try:
        payload = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        payload = {}
    
    resp = send_command_sync(cmd, payload)
    print(json.dumps(resp))
