#!/usr/bin/env python3
import asyncio
import json
import os
import shutil
import sys
import uuid
import time
import logging
from pathlib import Path
import websockets
from typing import Any

# Default ROME configuration
TOKEN = "ROME_V4_SECURE_TOKEN"
DEFAULT_DAEMON_URI = "ws://127.0.0.1:8741/ws"
LOG_LEVEL = logging.INFO
ROME_ROOT = os.environ.get("ROME_ROOT", str(Path(__file__).parent))

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("rome.peer")


def _load_arsenal(rome_root: str) -> dict:
    """Load arsenal and resolve {ROME_ROOT} / {GEMINI_CLI} placeholders."""
    arsenal_path = Path(rome_root) / "arsenal" / "core_arsenal.json"
    raw = json.loads(arsenal_path.read_text())
    gemini_cli = shutil.which("gemini") or "gemini"

    def resolve(val):
        if isinstance(val, str):
            return val.replace("{ROME_ROOT}", rome_root).replace("{GEMINI_CLI}", gemini_cli)
        if isinstance(val, list):
            return [resolve(v) for v in val]
        return val

    return {name: {k: resolve(v) for k, v in cap.items()} for name, cap in raw.get("capabilities", {}).items()}


async def _run_legion(websocket, task_id: str, capability: str, prompt: str, rome_root: str) -> None:
    """Spawn a legion subprocess and relay completion back to the caller via WS events."""
    try:
        caps = _load_arsenal(rome_root)
        cap = caps.get(capability)
        if not cap:
            await websocket.send(json.dumps({
                "type": "event",
                "event": {"type": "error", "task_id": task_id, "ts": time.time(),
                          "payload": {"error": f"Unknown capability: {capability}"}}
            }))
            return

        task_dir = Path(rome_root) / "legions" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        exec_bin = cap["exec"]
        args = cap.get("args", [])
        timeout = cap.get("timeout", 300)
        # legion_wrapper.py --mode once: task_id timestamp <cli-args> <prompt>
        cmd = [exec_bin, task_id, str(time.time())] + args + [prompt]
        env = {**os.environ, "PYTHONUNBUFFERED": "1",
               "ROME_TASK_DIR": str(task_dir), "ROME_ROOT": rome_root}

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(task_dir),
            env=env,
            start_new_session=True,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await websocket.send(json.dumps({
                "type": "event",
                "event": {"type": "error", "task_id": task_id, "ts": time.time(),
                          "payload": {"error": "timeout"}}
            }))
            return

        ok = proc.returncode == 0
        manifest: dict = {}
        manifest_path = task_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                pass

        report = ""
        report_path = task_dir / f"report_{task_id}.txt"
        if report_path.exists():
            report = report_path.read_text(encoding="utf-8")[:4000]

        await websocket.send(json.dumps({
            "type": "event",
            "event": {
                "type": "complete",
                "task_id": task_id,
                "ts": time.time(),
                "payload": {
                    "status": "completed" if ok else "failed",
                    "ok": ok,
                    "manifest": manifest,
                    "report": report,
                    "usage": manifest.get("usage"),
                }
            }
        }))
    except Exception as e:
        logger.error("_run_legion error task=%s: %s", task_id, e)
        try:
            await websocket.send(json.dumps({
                "type": "event",
                "event": {"type": "error", "task_id": task_id, "ts": time.time(),
                          "payload": {"error": str(e)}}
            }))
        except Exception:
            pass


class PeerServer:
    """ROME V5 Peer Server. Every agent is a server."""

    def __init__(self, capability: str, token: str = TOKEN, rome_root: str = ROME_ROOT):
        caps = _load_arsenal(rome_root)
        cap = caps.get(capability.upper())
        if not cap:
            raise ValueError(f"Unknown capability: {capability}")
        self.capability = capability.upper()
        self.port = cap["peer_port"]
        self.token = token
        self.rome_root = rome_root
        self.peers = {}
        self._server = None

    async def handle_connection(self, websocket):
        """Handle incoming ROME protocol messages."""
        try:
            if f"token={self.token}" not in websocket.request.path and websocket.request.headers.get("Authorization") != f"Bearer {self.token}":
                await websocket.close(1008, "Unauthorized")
                return
        except AttributeError:
            pass

        # 1. Handshake — advertise capability from arsenal, not hardcoded
        await websocket.send(json.dumps({
            "type": "daemon_hello",
            "version": "5.0.0",
            "platform": sys.platform,
            "capabilities": [self.capability]
        }))

        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "agent_hello":
                    peer_id = data.get("agent_id", "unknown")
                    logger.info("Peer connected: %s", peer_id)
                    await websocket.send(json.dumps({
                        "type": "worker_ack",
                        "ok": True,
                        "message": "Registered as peer"
                    }))

                elif msg_type == "command":
                    cmd = data.get("command")
                    request_id = data.get("request_id")
                    payload = data.get("payload", {})

                    if cmd == "dispatch":
                        task_id = payload.get("task_id") or f"peer-{uuid.uuid4().hex[:8]}"
                        capability = (payload.get("capability") or "GEMINI").upper()
                        prompt = payload.get("prompt") or ""
                        logger.info("Dispatch: task=%s cap=%s", task_id, capability)

                        # Accept immediately — result arrives as a "complete" event
                        await websocket.send(json.dumps({
                            "type": "response",
                            "request_id": request_id,
                            "ok": True,
                            "payload": {"task_id": task_id, "accepted": True}
                        }))

                        asyncio.create_task(
                            _run_legion(websocket, task_id, capability, prompt, self.rome_root)
                        )

                    elif cmd == "ping":
                        await websocket.send(json.dumps({
                            "type": "response",
                            "request_id": request_id,
                            "ok": True,
                            "payload": {"pong": True}
                        }))
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error("Error handling connection: %s", e)

    async def start(self):
        self._server = await websockets.serve(
            self.handle_connection, "0.0.0.0", self.port
        )
        logger.info("ROME Peer Server started on port %d", self.port)
        await self._server.wait_closed()

async def send_command(command: str, payload: dict, uri: str):
    """Low-level command sender."""
    if "?" not in uri:
        uri = f"{uri}?token={TOKEN}"
    try:
        async with websockets.connect(uri, open_timeout=30) as websocket:
            request_id = str(uuid.uuid4())[:8]
            await websocket.send(json.dumps({
                "type": "command",
                "request_id": request_id,
                "command": command,
                "payload": payload
            }))
            # Read until we get our response — daemon sends daemon_hello first
            async for raw in websocket:
                msg = json.loads(raw)
                if msg.get("request_id") == request_id:
                    return msg
            return {"ok": False, "error": "connection closed before response"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _peer_uri(capability: str, rome_root: str = ROME_ROOT) -> str | None:
    """Return ws://localhost:<peer_port> for a capability, or None if not found."""
    cap = _load_arsenal(rome_root).get(capability.upper())
    if cap and cap.get("peer_port"):
        return f"ws://localhost:{cap['peer_port']}/ws"
    return None


async def rome_dispatch(capability: str, prompt: str, task_id: str = None, peer: str = None):
    """
    ROME V5 Dispatch: Direct A2A via arsenal peer_port, no daemon required.
    Falls back to daemon only if peer is unreachable.
    """
    task_id = task_id or f"task-{uuid.uuid4().hex[:8]}"
    payload = {
        "task_id": task_id,
        "capability": capability,
        "prompt": prompt
    }

    # 1. Resolve peer URI — explicit override or discover from arsenal
    peer_uri = peer or _peer_uri(capability)
    if peer_uri:
        logger.info("Dispatching task %s direct to %s", task_id, peer_uri)
        res = await send_command("dispatch", payload, peer_uri)
        if res.get("ok"):
            return res
        logger.warning("Peer %s rejected task %s: %s. Falling back to daemon.", peer_uri, task_id, res.get("error"))

    # 2. Fallback to daemon
    logger.info("Dispatching task %s via daemon", task_id)
    return await send_command("dispatch", payload, DEFAULT_DAEMON_URI)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  rome_native.py serve [port]")
        print("  rome_native.py dispatch <capability> <prompt> [peer_uri]")
        print("  rome_native.py <command> <payload_json> [uri]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "serve":
        if len(sys.argv) < 3:
            print("Usage: rome_native.py serve <CAPABILITY>")
            print("Available capabilities are defined in arsenal/core_arsenal.json")
            sys.exit(1)
        asyncio.run(PeerServer(capability=sys.argv[2]).start())
    elif cmd == "dispatch":
        cap = sys.argv[2]
        prompt = sys.argv[3]
        peer = sys.argv[4] if len(sys.argv) > 4 else None
        res = asyncio.run(rome_dispatch(cap, prompt, peer=peer))
        print(json.dumps(res, indent=2))
    else:
        pld = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        uri = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_DAEMON_URI
        res = asyncio.run(send_command(cmd, pld, uri))
        print(json.dumps(res, indent=2))
