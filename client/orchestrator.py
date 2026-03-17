#!/usr/bin/env python3
"""
ROME Headless Orchestrator Client.
Runs standalone using Claude Sonnet 4.6 or Gemini 1.5 Flash.
Connects to ROME daemon WS to dispatch tasks and stream progress.
"""

import asyncio
import aiohttp
import json
import os
import sys
import uuid
from pathlib import Path
import time
# Removed urllib.request and urllib.error as aiohttp replaces them

try:
    import websockets
except ImportError:
    print(json.dumps({"type": "error", "message": "websockets package is required. Install with: pip install websockets"}))
    sys.exit(1)

_ARSENAL_PATH = Path(__file__).parent.parent / "arsenal" / "core_arsenal.json"

def load_arsenal() -> dict:
    """Loads the arsenal from core_arsenal.json."""
    try:
        return json.loads(_ARSENAL_PATH.read_text())
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to load arsenal: {e}"}))
        return {"capabilities": {}}

def get_available_capabilities_from_arsenal(arsenal: dict) -> dict[str, bool]:
    """Determines which capabilities are available based on API keys."""
    available = {}
    capabilities = arsenal.get("capabilities", {})
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    for cap_name, cap_def in capabilities.items():
        if cap_name in ["CLAUDE", "CENTURION_CLAUDE"] and not anthropic_key:
            available[cap_name] = False
            continue
        if cap_name in ["GEMINI", "CENTURION_GEMINI"] and not gemini_key:
            available[cap_name] = False
            continue
        available[cap_name] = True # Mark as available based on API key
    return available

SYSTEM_PROMPT = """You are a headless orchestrator (similar to Claude Code's Claude personality).
Read the user's task, understand the requirements, and break it into subtasks if needed.
You have access to a tool called `rome_dispatch`. Available capabilities: {available_capabilities_str}.
For each subtask, decide the capability and prompt. Use fire_and_forget=true for long background tasks or parallel tasks.

Output ONLY a JSON array of subtasks. Do not wrap it in markdown block quotes (like ```json), just output the raw JSON.
Example:
[
  {{"capability": "GEMINI", "prompt": "Analyze main.py and determine next steps.", "fire_and_forget": false}},
  {{"capability": "SAFE_SHELL", "prompt": "npm run build", "fire_and_forget": true}}
]
"""

async def orchestrate_task(task_description: str, available_capabilities: dict[str, bool]) -> list:
    """Uses LLM (Haiku or Flash) to break the task down and decide capabilities."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    # Filter for actually available capabilities to pass to the LLM prompt
    llm_available_caps = [cap for cap, status in available_capabilities.items() if status]

    if not anthropic_key and not gemini_key:
        print(json.dumps({"type": "progress", "task_id": "orchestrator", "percent": 0, "message": "No API keys found. Falling back to single GEMINI dispatch."}))
        # Fallback to a single dispatch with a "default" task type to choose capability
        chosen_cap = "GEMINI" if available_capabilities.get("GEMINI") else "UNKNOWN"
        if chosen_cap == "UNKNOWN":
            print(json.dumps({"type": "error", "message": "No suitable capability found. Exiting."}))
            sys.exit(1)
        return [{"capability": chosen_cap, "prompt": task_description, "fire_and_forget": False}]

    # Dynamically build SYSTEM_PROMPT based on available capabilities
    available_capabilities_str = ", ".join(llm_available_caps)
    current_system_prompt = SYSTEM_PROMPT.format(available_capabilities_str=available_capabilities_str)

    try:
        async with aiohttp.ClientSession() as session:
            if anthropic_key and (("CLAUDE" in llm_available_caps) or ("CENTURION_CLAUDE" in llm_available_caps)):
                req_data = {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1024,
                    "system": current_system_prompt,
                    "messages": [{"role": "user", "content": task_description}]
                }
                async with session.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json=req_data
                ) as response:
                    response.raise_for_status()
                    res_body = await response.json()
                    content = res_body["content"][0]["text"]
            elif gemini_key and (("GEMINI" in llm_available_caps) or ("CENTURION_GEMINI" in llm_available_caps)):
                req_data = {
                    "system_instruction": {"parts": [{"text": current_system_prompt}]},
                    "contents": [{"parts": [{"text": task_description}]}]
                }
                async with session.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash:generateContent?key={gemini_key}",
                    headers={"content-type": "application/json"},
                    json=req_data
                ) as response:
                    response.raise_for_status()
                    res_body = await response.json()
                    content = res_body["candidates"][0]["content"]["parts"][0]["text"]
            else:
                raise Exception("No suitable LLM for orchestration available.")

        # Parse JSON array from LLM response
        start = content.find('[')
        end = content.rfind(']')
        if start != -1 and end != -1:
            return json.loads(content[start:end+1])
        else:
            raise ValueError("LLM response did not contain a valid JSON array.")
    except aiohttp.ClientResponseError as e:
        print(json.dumps({"type": "error", "message": f"Orchestrator LLM HTTP error: {e.status} {e.message}. Falling back to a selected default capability."}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Orchestrator LLM failed: {e}. Falling back to a selected default capability."}), flush=True)
    
    # Fallback if LLM fails or returns nothing
    chosen_cap = "GEMINI" if available_capabilities.get("GEMINI") else "UNKNOWN"
    if chosen_cap == "UNKNOWN":
        print(json.dumps({"type": "error", "message": "No suitable capability found. Exiting."}))
        sys.exit(1)
    return [{"capability": chosen_cap, "prompt": task_description, "fire_and_forget": False}]

async def listen_to_ws(websocket, exit_code_ref, capabilities_ref):
    """Listens for WS events and prints JSONL progress, updates capabilities."""
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
                
                if ev_type == "agent_hello":
                    # Update capabilities from agent_hello
                    for cap_name, status in payload.get("capabilities", {}).items():
                        capabilities_ref[0][cap_name] = status
                    print(json.dumps({"type": "debug", "message": f"Updated capabilities from agent_hello: {capabilities_ref[0]}"}), flush=True)
                elif ev_type == "capability_status":
                    # Update capabilities from capability_status event
                    cap_name = payload.get("capability")
                    status = payload.get("available")
                    if cap_name:
                        capabilities_ref[0][cap_name] = status
                        print(json.dumps({"type": "debug", "message": f"Capability status updated for {cap_name}: {status}. Current capabilities: {capabilities_ref[0]}"}), flush=True)
                elif ev_type == "dispatch_start":
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
                elif ev_type == "error":
                    print(json.dumps({
                        "type": "error",
                        "task_id": t_id,
                        "message": str(payload.get("error") or "Task error")
                    }), flush=True)
                    exit_code_ref[0] = 1
        except websockets.exceptions.ConnectionClosed:
            print(json.dumps({"type": "debug", "message": "WebSocket connection closed."}), flush=True)
            break
        except Exception as e:
            print(json.dumps({"type": "error", "message": f"Error in WS listener: {e}"}), flush=True)
            break

def _ws_headers() -> dict:
    """Loads ws_token from config.json and returns it as an Authorization header."""
    try:
        cfg_path = Path(__file__).parent.parent / "dictator" / "config.json"
        cfg = json.loads(cfg_path.read_text())
        token = str(cfg.get("ws_token") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Failed to load ws_token: {e}"}), file=sys.stderr, flush=True)
        return {}

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

    arsenal_data = load_arsenal()
    
    # Initialize capabilities based on arsenal and API keys
    # This will be updated by agent_hello and capability_status events
    initial_capabilities = get_available_capabilities_from_arsenal(arsenal_data)
    capabilities_ref = [initial_capabilities] # Use a list to pass by reference

    uri = "ws://localhost:8741/ws"
    
    exit_code_ref = [0]
    
    try:
        async with websockets.connect(uri, extra_headers=_ws_headers()) as websocket:
            # Start listener task
            listener = asyncio.create_task(listen_to_ws(websocket, exit_code_ref, capabilities_ref))

            # Wait for agent_hello for up to 3 seconds
            start_time = time.time()
            agent_hello_received = False
            while time.time() - start_time < 3:
                # Check if capabilities_ref[0] has been updated from agent_hello
                if any(status for status in capabilities_ref[0].values()):
                    agent_hello_received = True
                    break
                await asyncio.sleep(0.1)

            if not agent_hello_received:
                print(json.dumps({"type": "debug", "message": "agent_hello not received within 3 seconds. Using initial capabilities from arsenal."}), flush=True)
            else:
                print(json.dumps({"type": "debug", "message": f"agent_hello received. Current capabilities: {capabilities_ref[0]}"}), flush=True)

            # Now, orchestrate task using potentially updated capabilities
            subtasks = await orchestrate_task(task_desc, capabilities_ref[0])

            if not any(capabilities_ref[0].values()): # If no capabilities are available after trying agent_hello
                print(json.dumps({"type": "error", "message": "No capabilities available to run tasks. Ensure ROME daemon is running and agents are configured."}))
                sys.exit(1)
            
            dispatched_task_ids = []
            for task_def in subtasks:
                t_id = f"task-{uuid.uuid4().hex[:8]}"
                
                capability = task_def.get("capability", "GEMINI")
                if not capabilities_ref[0].get(capability, False):
                    capability = "GEMINI" if capabilities_ref[0].get("GEMINI", False) else "UNKNOWN"

                if capability == "UNKNOWN":
                    print(json.dumps({"type": "error", "message": f"No suitable capability found for subtask: {task_def.get('prompt')}. Skipping."}), flush=True)
                    exit_code_ref[0] = 1
                    continue
                
                prompt = task_def.get("prompt", task_desc)
                
                cmd = {
                    "type": "command",
                    "command": "dispatch",
                    "request_id": f"req-{uuid.uuid4().hex[:8]}",
                    "payload": {
                        "task_id": t_id,
                        "capability": capability,
                        "prompt": prompt,
                        "fire_and_forget": True
                    }
                }
                
                await websocket.send(json.dumps(cmd))
                dispatched_task_ids.append(t_id)
                        
            # Use rome_await to wait for all non-fire_and_forget tasks
            if dispatched_task_ids:
                await_request_id = f"req-{uuid.uuid4().hex[:8]}"
                await websocket.send(json.dumps({
                    "type": "command",
                    "command": "await",
                    "request_id": await_request_id,
                    "payload": {
                        "task_ids": dispatched_task_ids,
                        "include_reports": True
                    }
                }))
                
                # Wait for the specific response to the await command
                await_response = None
                while True:
                    msg_str = await websocket.recv()
                    msg = json.loads(msg_str)
                    if msg.get("type") == "response" and msg.get("request_id") == await_request_id:
                        await_response = msg
                        break
                    # If it's an event, let the listener handle it (important for progress updates)
                    elif msg.get("type") == "event":
                        # This will be handled by the listener task, no need to process here
                        pass
                
                if await_response and await_response.get("ok"):
                    results = await_response["payload"].get("tasks", {})
                    for t_id, res in results.items():
                        status = res.get("status", "UNKNOWN")
                        report_path = res.get("report_path", "")
                        report_content = res.get("report", "")
                        
                        print(json.dumps({
                            "type": "complete",
                            "task_id": t_id,
                            "status": status,
                            "report": report_path
                        }), flush=True)
                        if status not in ("completed", "SUCCESS", "success"):
                            exit_code_ref[0] = 1
                        # Basic error handling: log to stderr if task failed
                        if status == "failed":
                             print(json.dumps({
                                 "type": "error",
                                 "task_id": t_id,
                                 "message": f"Task {t_id} failed. Report: {report_path}. Content: {report_content}"
                             }), file=sys.stderr, flush=True)
                elif await_response:
                    print(json.dumps({"type": "error", "message": f"Await command failed: {await_response.get('error', 'Unknown error')}"}), flush=True)
                    exit_code_ref[0] = 1
                else:
                    print(json.dumps({"type": "error", "message": "Did not receive a response for await command."}), flush=True)
                    exit_code_ref[0] = 1
            
            listener.cancel()
            await listener # Ensure the listener task is properly cancelled and cleaned up
            
    except websockets.exceptions.ConnectionRefusedError:
        print(json.dumps({"type": "error", "message": f"Failed to connect to ROME WS at {uri}. Is the ROME daemon running?"}), flush=True)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"type": "error", "message": f"Orchestrator encountered an error: {e}"}), flush=True)
        sys.exit(1)
        
    sys.exit(exit_code_ref[0])

if __name__ == "__main__":
    asyncio.run(main())