import asyncio
import json
import yaml
import websockets
import os
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Assuming ROME_ROOT is accessible or can be derived
ROME_ROOT = os.environ.get("ROME_ROOT", "/home/paul-kane/projects/rome-core")
CONFIG_PATH = os.path.join(ROME_ROOT, "dictator", "config.json")
_WS_URL = os.environ.get("ROME_WS_URL", "ws://127.0.0.1:8741/ws")

def _ws_headers() -> Dict[str, str]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        token = str(cfg.get("ws_token") or "").strip()
        return {"Authorization": f"Bearer {token}"} if token else {}
    except Exception:
        return {}

async def _send_command(ws: websockets.WebSocketClientProtocol, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req_id = os.urandom(4).hex()
    await ws.send(json.dumps({
        "type": "command",
        "command": command,
        "request_id": req_id,
        "payload": payload,
    }))
    # Wait for the specific response to this command
    while True:
        message = await ws.recv()
        msg = json.loads(message)
        if msg.get("type") == "response" and msg.get("request_id") == req_id:
            return msg.get("payload", {})

async def run_campaign(campaign_file: str) -> None:
    print(f"Loading campaign from {campaign_file}...")
    try:
        with open(campaign_file, "r", encoding="utf-8") as f:
            campaign_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Campaign file not found at {campaign_file}", file=sys.stderr)
        return
    except yaml.YAMLError as e:
        print(f"Error parsing YAML campaign file: {e}", file=sys.stderr)
        return

    campaign_name = campaign_data.get("name", "Unnamed Campaign")
    tasks_definition = campaign_data.get("tasks", [])

    if not tasks_definition:
        print("No tasks defined in the campaign.", file=sys.stderr)
        return

    # Validate tasks and build dependency graph
    tasks: Dict[str, Dict[str, Any]] = {t["id"]: t for t in tasks_definition}
    if len(tasks) != len(tasks_definition):
        print("Error: Duplicate task IDs found in campaign.", file=sys.stderr)
        return

    # Initialize task states
    task_statuses: Dict[str, str] = {task_id: "pending" for task_id in tasks}
    task_results: Dict[str, Dict[str, Any]] = {} # Store full results including report_path, usage etc.

    print(f"Running campaign: {campaign_name}")

    async with websockets.connect(_WS_URL, open_timeout=30, additional_headers=_ws_headers()) as ws:
        # Background task to listen for events from the daemon
        event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        async def event_listener():
            try:
                while True:
                    message = await ws.recv()
                    msg = json.loads(message)
                    if msg.get("type") == "event":
                        await event_queue.put(msg["event"])
            except websockets.exceptions.ConnectionClosedOK:
                pass
            except Exception as e:
                print(f"Error in event listener: {e}", file=sys.stderr)

        listener_task = asyncio.create_task(event_listener())

        try:
            total_tasks = len(tasks)
            dispatched_tasks: Set[str] = set() # Tasks that have been sent to the daemon for dispatch
            running_dispatch_futures: Dict[str, asyncio.Future] = {} # Futures for the _send_command("dispatch") call

            while True:
                # Check for completion criteria
                completed_count = sum(1 for status in task_statuses.values() if status in {"completed", "failed", "cancelled"})
                if completed_count == total_tasks:
                    break # All tasks are done

                # Dispatch tasks whose dependencies are met and haven't been dispatched yet
                for task_id, task_def in tasks.items():
                    if task_statuses[task_id] == "pending" and task_id not in dispatched_tasks:
                        # Check dependencies
                        dependencies_met = True
                        for dep_id in task_def.get("depends_on", []):
                            if task_statuses.get(dep_id) != "completed": # Only 'completed' status counts as successful dependency
                                dependencies_met = False
                                break

                        if dependencies_met:
                            print(f"-> Dispatching task: {task_id}")
                            task_statuses[task_id] = "dispatching"
                            dispatched_tasks.add(task_id)
                            # Use asyncio.ensure_future to dispatch in background and get a future
                            future = asyncio.ensure_future(_send_command(ws, "dispatch", {
                                "task_id": task_id,
                                "capability": task_def["capability"],
                                "prompt": task_def["prompt"],
                                "input_files": task_def.get("input_files"),
                            }))
                            running_dispatch_futures[task_id] = future
                
                # Process completed dispatch futures
                done_dispatch_futures = [f for f in running_dispatch_futures.values() if f.done()]
                for future in done_dispatch_futures:
                    for task_id, f in list(running_dispatch_futures.items()): # Iterate over copy as we modify dict
                        if f == future:
                            try:
                                dispatch_response = await future
                                if not dispatch_response.get("accepted"): # The daemon can reject a dispatch
                                    print(f"Daemon rejected task {task_id} dispatch: {dispatch_response.get('error', 'Unknown error')}", file=sys.stderr)
                                    task_statuses[task_id] = "failed"
                                    task_results[task_id] = {"status": "failed", "error": dispatch_response.get("error")}
                                    # Propagate failure to dependents
                                    for dep_task_id, dep_task_def in tasks.items():
                                        if task_id in dep_task_def.get("depends_on", []):
                                            # Mark dependent as failed if its dependency failed
                                            task_statuses[dep_task_id] = "failed"
                                            task_results[dep_task_id] = {"status": "failed", "error": f"Dependency {task_id} failed"}
                                else:
                                    # Dispatch accepted, now wait for completion event
                                    task_statuses[task_id] = "running"
                            except Exception as e:
                                print(f"Error dispatching task {task_id}: {e}", file=sys.stderr)
                                task_statuses[task_id] = "failed"
                                task_results[task_id] = {"status": "failed", "error": str(e)}
                                # Propagate failure
                                for dep_task_id, dep_task_def in tasks.items():
                                    if task_id in dep_task_def.get("depends_on", []):
                                        task_statuses[dep_task_id] = "failed"
                                        task_results[dep_task_id] = {"status": "failed", "error": f"Dependency {task_id} failed"}
                            finally:
                                del running_dispatch_futures[task_id]
                            break # Move to next future

                # Process events from the daemon
                while not event_queue.empty():
                    event = await event_queue.get()
                    event_type = event.get("type")
                    event_task_id = event.get("task_id")
                    payload = event.get("payload", {})

                    if event_type == "complete" and event_task_id in tasks:
                        status = payload.get("status", "unknown")
                        report_path = payload.get("report_path")
                        usage = payload.get("usage", {})
                        
                        task_statuses[event_task_id] = status
                        task_results[event_task_id] = {
                            "status": status,
                            "report_path": report_path,
                            "usage": usage
                        }
                        print(f"Task {event_task_id} completed with status: {status}")

                        if status != "completed": # If a task fails or is cancelled
                            # Mark dependents as failed
                            for dep_task_id, dep_task_def in tasks.items():
                                if event_task_id in dep_task_def.get("depends_on", []):
                                    task_statuses[dep_task_id] = "failed"
                                    task_results[dep_task_id] = {"status": "failed", "error": f"Dependency {event_task_id} failed with status {status}"}
                                    print(f"Task {dep_task_id} marked as failed due to dependency {event_task_id} failure.")
                
                # Small delay to prevent busy-waiting
                await asyncio.sleep(0.05)

        finally:
            listener_task.cancel()
            await asyncio.gather(listener_task, return_exceptions=True)

        print("
--- Campaign Summary ---")
        for task_id in tasks:
            result = task_results.get(task_id, {"status": task_statuses.get(task_id, "NOT RUN")})
            print(f"Task {task_id}: Status={result['status']}")
            if result.get("report_path"):
                # Fetch report content
                read_report_response = await _send_command(ws, "read_report", {"report_path": result["report_path"]})
                if read_report_response.get("ok"):
                    print(f"  Report:
{read_report_response['content']}")
                else:
                    print(f"  Failed to read report: {read_report_response.get('error', 'Unknown error')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python loader.py <campaign_file.yaml>", file=sys.stderr)
        sys.exit(1)
    campaign_file = sys.argv[1]
    asyncio.run(run_campaign(campaign_file))

if __name__ == "__main__":
    main()
