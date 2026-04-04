#!/usr/bin/env python3
import asyncio
import json
import sys
import websockets

TOKEN = "ROME_V4_SECURE_TOKEN"

async def send_command(command, payload):
    uri = f"ws://127.0.0.1:8741/ws?token={TOKEN}"
    try:
        async with websockets.connect(uri) as websocket:
            # Skip daemon_hello
            hello = await websocket.recv()
            await websocket.send(json.dumps({
                "type": "command",
                "command": command,
                "payload": payload
            }))
            response = await websocket.recv()
            print(response)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    
    cmd = sys.argv[1]
    pld = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    asyncio.run(send_command(cmd, pld))
