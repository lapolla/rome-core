#!/usr/bin/env python3
import asyncio
import json
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

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("rome.peer")

class PeerServer:
    """ROME V5 Peer Server. Every agent is a server."""
    
    def __init__(self, port: int = 8742, token: str = TOKEN):
        self.port = port
        self.token = token
        self.peers = {} # url -> websocket
        self._server = None

    async def handle_connection(self, websocket):
        """Handle incoming ROME protocol messages."""
        # 1. Handshake
        await websocket.send(json.dumps({
            "type": "daemon_hello",
            "version": "5.0.0",
            "platform": sys.platform,
            "capabilities": ["GEMINI", "NATIVE_SHELL"]
        }))

        try:
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "agent_hello":
                    # Peer registration
                    peer_id = data.get("agent_id", "unknown")
                    logger.info(f"Peer connected: {peer_id}")
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
                        logger.info(f"Received dispatch request: {payload.get('task_id')}")
                        # Stub: in a real implementation, this would call legion_wrapper or internal logic
                        await websocket.send(json.dumps({
                            "type": "response",
                            "request_id": request_id,
                            "ok": True,
                            "payload": {"accepted": True, "routed_to": "peer_native"}
                        }))
                    
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
            logger.error(f"Error handling connection: {e}")

    async def start(self):
        self._server = await websockets.serve(
            self.handle_connection, "0.0.0.0", self.port
        )
        logger.info(f"ROME Peer Server started on port {self.port}")
        await self._server.wait_closed()

async def send_command(command: str, payload: dict, uri: str):
    """Low-level command sender."""
    if "?" not in uri:
        uri = f"{uri}?token={TOKEN}"
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for handshake (daemon_hello)
            await websocket.recv()
            
            request_id = str(uuid.uuid4())[:8]
            await websocket.send(json.dumps({
                "type": "command",
                "request_id": request_id,
                "command": command,
                "payload": payload
            }))
            response = await websocket.recv()
            return json.loads(response)
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def rome_dispatch(capability: str, prompt: str, task_id: str = None, peer: str = None):
    """
    ROME V5 Dispatch: Direct A2A with fallback to daemon.
    """
    task_id = task_id or f"task-{uuid.uuid4().hex[:8]}"
    payload = {
        "task_id": task_id,
        "capability": capability,
        "prompt": prompt
    }

    # 1. Try direct peer if provided
    if peer:
        logger.info(f"Attempting direct dispatch to peer: {peer}")
        res = await send_command("dispatch", payload, peer)
        if res.get("ok"):
            logger.info(f"Peer {peer} accepted task {task_id}")
            return res
        logger.warning(f"Direct dispatch to {peer} failed: {res.get('error')}. Falling back to daemon.")

    # 2. Fallback to daemon
    daemon_uri = DEFAULT_DAEMON_URI
    logger.info(f"Dispatching task {task_id} via daemon: {daemon_uri}")
    return await send_command("dispatch", payload, daemon_uri)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  rome_native.py serve [port]")
        print("  rome_native.py dispatch <capability> <prompt> [peer_uri]")
        print("  rome_native.py <command> <payload_json> [uri]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "serve":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8742
        asyncio.run(PeerServer(port=port).start())
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
