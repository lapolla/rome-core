"""
WebSocket tools: ws_send, rome_await, rome_events.
Standardized interface for sending commands to the ROME Daemon.
"""

import asyncio
import json
import threading
import time
from collections import deque
from dictator.ws_client import send_command_async, submit_agent_result_async

# ---------------------------------------------------------------------------
# Persistent event listener — buffers daemon events for rome_events() tool
# ---------------------------------------------------------------------------

_MAX_EVENTS = 50
_event_buffer: deque[str] = deque(maxlen=_MAX_EVENTS)
_seen_events: set[str] = set()  # dedup key = "type:task_id"
_listener_started = False
_listener_lock = threading.Lock()


def _format_event(msg: dict) -> str | None:
    """Convert a daemon WS event to a compact one-liner."""
    if msg.get("type") != "event":
        return None
    ev = msg.get("event", {})
    etype = ev.get("type", "?")
    tid = ev.get("task_id", "?")
    payload = ev.get("payload", {})

    if etype == "complete":
        status = payload.get("status", "?")
        return f"[{status.upper()}] {tid}"
    elif etype == "progress":
        pct = payload.get("percent", "?")
        msg_text = payload.get("message", "")
        return f"[PROGRESS] {tid} {pct}% {msg_text}"
    elif etype == "dispatch_start":
        cap = payload.get("capability", "?")
        return f"[DISPATCH] {tid} → {cap}"
    elif etype == "heartbeat" or etype == "system_status":
        return None  # Skip noise
    else:
        return f"[{etype.upper()}] {tid}"


def _start_listener():
    """Start background thread that listens for daemon events."""
    global _listener_started
    with _listener_lock:
        if _listener_started:
            return
        _listener_started = True

    def _run():
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(loop)
        loop.run_until_complete(_listen_forever())

    t = threading.Thread(target=_run, daemon=True, name="rome-event-listener")
    t.start()


async def _listen_forever():
    """Persistent WS connection to daemon, buffering events."""
    import websockets
    from dictator.ws_client import _WS_URL, _ws_headers

    delay = 1.0
    while True:
        try:
            async with websockets.connect(_WS_URL, open_timeout=30, additional_headers=_ws_headers()) as ws:
                delay = 1.0
                # Skip the agent_hello message
                try:
                    hello = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    pass

                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=120)
                        msg = json.loads(raw)
                        line = _format_event(msg)
                        if line:
                            # Dedup: skip if we've seen this exact type+task combo recently
                            ev = msg.get("event", {})
                            dedup_key = f"{ev.get('type')}:{ev.get('task_id')}"
                            if dedup_key not in _seen_events:
                                _seen_events.add(dedup_key)
                                _event_buffer.append(f"{time.strftime('%H:%M:%S')} {line}")
                    except asyncio.TimeoutError:
                        # No message for 120s — connection might be dead, reconnect
                        break
        except Exception:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 16.0)


def register(mcp):
    """Register WebSocket tools with the given FastMCP instance."""

    @mcp.tool()
    async def ws_send(command: str, payload: dict = {}, timeout: float = 5.0) -> str:
        """
        Sends a command to the ROME Daemon via WebSocket and waits for a response.
        Standard commands: list, status, dispatch, fire_and_forget.
        """
        result = await send_command_async(command, payload, timeout)
        return json.dumps(result)

    @mcp.tool()
    async def rome_submit_result(task_id: str, content: str, token: str | None = None) -> str:
        """
        Submits the agent's result for a given task.
        """
        result = await submit_agent_result_async(task_id, content, token=token)
        return json.dumps(result)

    @mcp.tool()
    async def rome_events() -> str:
        """
        Drain the event buffer — returns all daemon events since last call.
        Events are compact one-liners: [STATUS] task_id details.
        Returns empty string if no events. Call periodically to stay aware.
        """
        _start_listener()
        if not _event_buffer:
            return "(no events)"
        events = list(_event_buffer)
        _event_buffer.clear()
        _seen_events.clear()
        return "\n".join(events)
