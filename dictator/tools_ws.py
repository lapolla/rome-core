import asyncio
import json
import uuid
import websockets
from typing import Any

from pathlib import Path
import json as _json

from dictator.core import mcp
from dictator.rome_log import log_event

def _ws_url() -> str:
    cfg_path = Path(__file__).parent / "config.json"
    cfg = _json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    return f"ws://{cfg.get('daemon_host', '127.0.0.1')}:{cfg.get('daemon_port', 8741)}/ws"

@mcp.tool()
async def ws_send(command: str, payload: dict = {}, timeout: float = 5.0) -> str:
    """
    Opens a websocket connection to the daemon (host/port from config.json),
    sends a command, and waits for a response matching request_id.
    Returns the response payload as a JSON string.
    """
    try:
        async with websockets.connect(_ws_url()) as ws:
            req_id = uuid.uuid4().hex[:8]
            message = {
                "type": "command",
                "command": command,
                "request_id": req_id,
                "payload": payload,
            }
            await ws.send(json.dumps(message))

            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    log_event(tool='ws_send', status='timeout', message=f'ws_send timed out after {timeout}s for command {command}')
                    return json.dumps({"ok": False, "error": "timeout"})

                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                msg = json.loads(raw)
                if msg.get("type") == "response" and msg.get("request_id") == req_id:
                    return json.dumps(msg.get("payload", {}))
    except Exception as e:
        log_event(tool='ws_send', status='error', message=f'ws_send failed: {e}')
        return json.dumps({"ok": False, "error": str(e)})
