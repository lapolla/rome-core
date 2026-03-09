#!/usr/bin/env python3
"""
ROME Headless Orchestrator Client.
Runs standalone using a cheap model (Claude 3 Haiku or Gemini 1.5 Flash).
Connects to ROME daemon WS to dispatch tasks and stream progress.
"""

import sys
import os
import json
import asyncio
import urllib.request
import urllib.error
import uuid

try:
    import websockets
except ImportError:
    print(json.dumps({"type": "error", "message": "websockets package is required. Install with: pip install websockets"}))
    sys.exit(1)

SYSTEM_PROMPT = """You are a headless orchestrator (similar to Claude Code's Claude personality).
Read the user's task, understand the requirements, and break it into subtasks if needed.
You have access to a tool called `rome_dispatch`. Available capabilities: GEMINI, CODEX, SAFE_SHELL, OPENCODE.
For each subtask, decide the capability and prompt. Use fire_and_forget=true for long background tasks or parallel tasks.

Output ONLY a JSON array of subtasks. Do not wrap it in markdown block quotes (like ```json), just output the raw JSON.
Example:
[
  {"capability": "GEMINI", "prompt": "Analyze main.py and determine next steps.", "fire_and_forget": false},
  {"capability": "SAFE_SHELL", "prompt": "npm run build", "fire_and_forget": true}
]
"""

def orchestrate_task(task_description: str) -> list:
    """Uses LLM (Haiku or Flash) to break the task down and decide capabilities."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not anthropic_key and not gemini_key:
        print(json.dumps({"type": "progress", "task_id": "orchestrator", "percent": 0, "message": "No API keys found. Falling back to single GEMINI dispatch."}))
        return [{"capability": "GEMINI", "prompt": task_description, "fire_and_forget": False}]

    try:
        if anthropic_key:
            req_data = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": task_description}]
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(req_data).encode("utf-8"),
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
            )
            with urllib.request.urlopen(req) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                content = res_body["content"][0]["text"]
        elif gemini_key:
            req_data = {
                "system_instruction": {"parts": {"text": SYSTEM_PROMPT}},
                "contents": [{"parts": [{"text": task_description}]}]
            }
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                data=json.dumps(req_data).encode("utf-8"),
                headers={"content-type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                content = res_body["candidates"][0]["content"]["parts"][0]["text"]

        # Parse JSON array from LLM response
        start = content.find('[')
        end = content.rfind(']')
        if start != -1 and end != -1:
            return json.loads(content[start:end+1])
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Orchestrator LLM failed: {e}. Falling back to default GEMINI."}))
        
    return [{"capability": "GEMINI", "prompt": task_description, "fire_and_forget": False}]


async def listen_to_ws(websocket, active_tasks, exit_code_ref):
    """Listens for WS events and prints JSONL progress."""
    while True:
        try:
            msg_str = await websocket.recv()
            msg = json.loads(msg_str)
            
            if msg.get("type") == "response":
                if not msg.get("ok"):
                    print(json.dumps({"type": "error", "message": msg.get("error", "Command failed")}), flush=True)
                    exit_code_ref[0] = 1
            elif msg.get("type") == "event":
                event = msg.get("event", {})
                ev_type = event.get("type")
                t_id = event.get("task_id")
                payload = event.get("payload", {})
                
                if ev_type == "dispatch_start":
                    print(json.dumps({
                        "type": "dispatch_start",
                        "task_id": t_id,
                        "capability": payload.get("capability", "UNKNOWN")
                    }), flush=True)
                elif ev_type == "progress":
                    print(json.dumps({
                        "type": "progress",
                        "task_id": t_id,
                        "percent": payload.get("percent", 50),
                        "message": payload.get("message", "Working...")
                    }), flush=True)
                elif ev_type == "complete":
                    status = payload.get("status", "SUCCESS")
                    print(json.dumps({
                        "type": "complete",
                        "task_id": t_id,
                        "status": status,
                        "report": payload.get("report_path", "")
                    }), flush=True)
                    if status not in ("completed", "SUCCESS", "success"):
                        exit_code_ref[0] = 1
                    active_tasks.discard(t_id)
                elif ev_type == "error":
                    print(json.dumps({
                        "type": "error",
                        "task_id": t_id,
                        "message": str(payload.get("error") or "Task error")
                    }), flush=True)
                    exit_code_ref[0] = 1
                    active_tasks.discard(t_id)
        except websockets.exceptions.ConnectionClosed:
            break
        except Exception:
            break


async def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "-":
            task_desc = sys.stdin.read()
        else:
            with open(sys.argv[1], "r") as f:
                task_desc = f.read()
    else:
        if not sys.stdin.isatty():
            task_desc = sys.stdin.read()
        else:
            print(json.dumps({"type": "error", "message": "Usage: python3 orchestrator.py <task_file>"}))
            sys.exit(1)

    subtasks = orchestrate_task(task_desc)
    uri = "ws://localhost:8741/ws"
    
    exit_code_ref = [0]
    active_tasks = set()
    
    try:
        async with websockets.connect(uri) as websocket:
            listener = asyncio.create_task(listen_to_ws(websocket, active_tasks, exit_code_ref))
            
            for task_def in subtasks:
                t_id = f"task-{uuid.uuid4().hex[:8]}"
                capability = task_def.get("capability", "GEMINI")
                prompt = task_def.get("prompt", task_desc)
                fire_and_forget = task_def.get("fire_and_forget", False)
                
                if not fire_and_forget:
                    active_tasks.add(t_id)
                    
                cmd = {
                    "type": "command",
                    "command": "dispatch",
                    "request_id": f"req-{uuid.uuid4().hex[:8]}",
                    "payload": {
                        "task_id": t_id,
                        "capability": capability,
                        "prompt": prompt,
                        "fire_and_forget": fire_and_forget
                    }
                }
                
                await websocket.send(json.dumps(cmd))
                
                if not fire_and_forget:
                    # Wait for this specific subtask to finish before dispatching the next
                    while t_id in active_tasks:
                        await asyncio.sleep(0.1)
                        
            # Wait for any straggler tasks if there's a logic error, though we awaited them sequentially above.
            while active_tasks:
                await asyncio.sleep(0.1)
                
            listener.cancel()
            
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to connect to ROME WS: {e}"}))
        sys.exit(1)
        
    sys.exit(exit_code_ref[0])

if __name__ == "__main__":
    asyncio.run(main())